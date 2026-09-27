#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
banc_historique.py -- BANC DE TEST HISTORIQUE : juge n'importe quel moteur contre le marché, sur des matchs déjà joués,
avec uniquement ce qui était connu avant le coup d'envoi.

Pourquoi (27/09/2026). Aucun moteur (V0, spécifications ChatGPT, ARCHETYPE_FOOT, V2) n'a été validé sur des résultats
réels avant d'être remplacé. Mesure du 27/09 sur 501 matchs : V2 annonce 81,9 % et réussit 63,3 %, exactement ce que
prévoyait déjà le marché (62,8 %). Ce banc est la porte obligatoire avant tout branchement au pipeline.

CE QUE LE BANC MESURE (critères acceptés par Patrick et par l'autre IA le 27/09) :
  - pour chaque famille et chaque marché ayant assez de données : Brier et log-loss du modèle ET du marché (cotes sans
    marge), écart modèle - marché avec intervalle de confiance à 95 % (bootstrap PAR MATCH : les marchés d'un même match
    sont liés) ;
  - calibration par tranche de probabilité annoncée ;
  - résultats par taille d'échantillon (N au même lieu : 0-2, 3-4, 5+), par tranche de cote et par source ;
  - ROI seulement comme mesure SECONDAIRE, sur les sélections d'une règle de décision fournie.
VERDICTS (par groupe) :
  - ÉCHANTILLON INSUFFISANT : moins de MIN_MATCHS matchs ou MIN_OBSERVATIONS observations -> aucune conclusion ;
  - AVANTAGE MESURABLE : log-loss du modèle meilleure que celle du marché, intervalle entièrement sous 0 ;
  - MOINS BON QUE LE MARCHÉ : intervalle entièrement au-dessus de 0 ;
  - AUCUN AVANTAGE MESURABLE : sinon. Le moteur doit alors conclure « pas d'avantage mesurable -> pas de pari ».
Le marché n'est pas une vérité absolue : c'est la référence externe à battre.

RÈGLES DU PROTOCOLE :
  1. Aucune donnée postérieure au match : le jeu figé est construit avant les scores (empreinte SHA-256 vérifiée, refus
     si elle ne correspond pas) ; pour l'archive de test, tout match d'équipe daté du jour du match ou après fait écarter
     le match (compté dans `ecartes_fuite`).
  2. Le banc VALIDE, il ne sert pas à régler : les seuils ci-dessous sont fixés ici une fois pour toutes. Régler un
     moteur jusqu'à ce qu'il passe ce banc invaliderait le test (voir evaluation/README.md).
  3. Handicaps exclus : leurs étiquettes BetPawa sont incohérentes dans la collecte (constat du 27/09).

SOURCES :
  - « snapshot » : evaluation/snapshot_historique_moteur_v2_6_9.json + scores (503 matchs, 501 avec score). Contient les
    MOYENNES d'avant-match au même lieu (pas la liste des matchs) : la règle du double contrôle n'y est pas applicable.
  - « archive » : data/archive_test/*.json.gz (archive_donnees_test.py), matchs testables AVEC score : listes complètes
    des matchs des deux équipes + assemblage Football-Data (mi-temps, tirs, corners...) quand il existe.

BRANCHER UN MOTEUR : une fonction `modele(entree) -> {marche: probabilite}` (marchés de MARCHES, sous-ensemble permis).
`entree` (même forme pour les deux sources) :
    id, date, competition, source, n_lieu (= min des matchs au même lieu des deux équipes),
    cotes {marche: cote}, equipe_dom / equipe_ext {nom, buts_marques_moy, buts_encaisses_moy, matchs_joues,
    matchs (liste complète, archive seulement, sinon None)}, assemblage (archive seulement, sinon None).
Une règle de décision (facultative) : `selection(entree, probas) -> [marches]`.

Utilisation :
    python banc_historique.py                                   # compare les modèles de référence
    python banc_historique.py --modele mon_module:ma_fonction   # juge un moteur
    python banc_historique.py --modele m:f --selection m:g --source tous --json rapport.json
"""
from __future__ import annotations

import argparse
import glob
import gzip
import hashlib
import importlib
import json
import math
import os
import random
import sys
from collections import defaultdict

RACINE = os.path.dirname(os.path.abspath(__file__))
FICHIER_SNAPSHOT = os.path.join(RACINE, "evaluation", "snapshot_historique_moteur_v2_6_9.json")
FICHIER_SCORES = os.path.join(RACINE, "evaluation", "scores_historique_moteur_v2_6_9.json")
DOSSIER_ARCHIVE = os.path.join(RACINE, "data", "archive_test")

# Seuils du protocole -- fixés ici, jamais ajustés après lecture d'un résultat.
MIN_MATCHS = 100
MIN_OBSERVATIONS = 200
MIN_TRANCHE_CALIBRATION = 30
NIVEAU_IC = 0.95
TIRAGES_BOOTSTRAP = 1000
GRAINE = 20260927
EPS = 1e-6

# --- marchés évalués : famille + règle de gain sur le score final (h = buts domicile, a = buts extérieur) -----------
MARCHES = {
    "victoire": ("resultat", lambda h, a: h > a),
    "nul": ("resultat", lambda h, a: h == a),
    "defaite": ("resultat", lambda h, a: h < a),
    "dc_1X": ("double_chance", lambda h, a: h >= a),
    "dc_X2": ("double_chance", lambda h, a: h <= a),
    "dc_12": ("double_chance", lambda h, a: h != a),
    "btts_oui": ("btts", lambda h, a: h > 0 and a > 0),
    "btts_non": ("btts", lambda h, a: h == 0 or a == 0),
}
for _x in range(5):
    MARCHES[f"over_{_x}_5"] = ("total_buts", (lambda x: lambda h, a: h + a > x)(_x))
    MARCHES[f"under_{_x}_5"] = ("total_buts", (lambda x: lambda h, a: h + a <= x)(_x))

GROUPES_MARCHE = [("victoire", "nul", "defaite"), ("btts_oui", "btts_non")] + \
                 [(f"over_{x}_5", f"under_{x}_5") for x in range(5)]


def gagne(marche, h, a):
    return bool(MARCHES[marche][1](h, a))


def probabilites_marche(cotes):
    """Probabilités du marché SANS marge : chaque groupe d'issues complémentaires est normalisé à 1. La double chance est
    déduite du 1X2 sans marge (ses propres cotes restent utilisées pour le ROI)."""
    p = {}
    for groupe in GROUPES_MARCHE:
        if all(isinstance(cotes.get(k), (int, float)) and cotes[k] > 1 for k in groupe):
            s = sum(1 / cotes[k] for k in groupe)
            for k in groupe:
                p[k] = (1 / cotes[k]) / s
    if all(k in p for k in ("victoire", "nul", "defaite")):
        p["dc_1X"] = p["victoire"] + p["nul"]
        p["dc_X2"] = p["defaite"] + p["nul"]
        p["dc_12"] = p["victoire"] + p["defaite"]
    return p


# --- chargement des sources -------------------------------------------------------------------------------------------

def empreinte(chemin):
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def verifie_empreinte(chemin):
    """True si le fichier .sha256 existe et correspond ; False sinon (fichier modifié ou empreinte absente)."""
    ref = chemin + ".sha256"
    if not os.path.exists(ref):
        return False
    with open(ref, encoding="utf-8") as f:
        attendu = f.read().split()[0].strip().lower()
    return empreinte(chemin) == attendu


def _equipe_moyennes(nom, gf, ga, n, matchs=None):
    return {"nom": nom, "buts_marques_moy": gf, "buts_encaisses_moy": ga, "matchs_joues": n, "matchs": matchs}


def charge_snapshot(fichier_snapshot=FICHIER_SNAPSHOT, fichier_scores=FICHIER_SCORES):
    """[(entree, (buts_dom, buts_ext))] du jeu figé, matchs avec score seulement."""
    with open(fichier_snapshot, encoding="utf-8") as f:
        snap = json.load(f)
    with open(fichier_scores, encoding="utf-8") as f:
        scores = json.load(f).get("scores") or {}
    out = []
    for m in snap.get("matchs") or []:
        sc = scores.get(m.get("id"))
        if not sc or not isinstance(sc.get("buts_dom"), int) or not isinstance(sc.get("buts_ext"), int):
            continue
        em = m.get("entree_moteur") or {}
        d, e = em.get("equipe_dom") or {}, em.get("equipe_ext") or {}
        nd, ne = (m.get("effectifs") or {}).get("domicile", 0), (m.get("effectifs") or {}).get("exterieur", 0)
        entree = {
            "id": m.get("id"), "date": m.get("date"), "competition": " ".join(str(m.get("competition") or "").split()),
            "source": "snapshot", "n_lieu": min(nd, ne),
            "cotes": {k: v for k, v in (em.get("cotes") or {}).items() if k in MARCHES},
            "equipe_dom": _equipe_moyennes(d.get("nom"), d.get("buts_marques_moy"), d.get("buts_encaisses_moy"), nd),
            "equipe_ext": _equipe_moyennes(e.get("nom"), e.get("buts_marques_moy"), e.get("buts_encaisses_moy"), ne),
            "assemblage": None,
        }
        out.append((entree, (sc["buts_dom"], sc["buts_ext"])))
    return out


# Cotes BetPawa brutes (cotes_manuelles) -> noms de MARCHES. Handicaps volontairement absents.
_BETPAWA = {("1x2", "1"): "victoire", ("1x2", "N"): "nul", ("1x2", "2"): "defaite",
            ("double_chance", "1N"): "dc_1X", ("double_chance", "N2"): "dc_X2", ("double_chance", "12"): "dc_12",
            ("btts", "Oui"): "btts_oui", ("btts", "Non"): "btts_non"}
_OBSERVEES = {"1X2 - 1": "victoire", "1X2 - X": "nul", "1X2 - 2": "defaite", "Double chance - 1X": "dc_1X",
              "Double chance - X2": "dc_X2", "Double chance - 12": "dc_12", "BTTS - oui": "btts_oui",
              "BTTS - non": "btts_non"}
for _x in range(5):
    _BETPAWA[(f"over_under_{_x}.5", "plus")] = f"over_{_x}_5"
    _BETPAWA[(f"over_under_{_x}.5", "moins")] = f"under_{_x}_5"
    _OBSERVEES[f"Plus de {_x}.5 buts"] = f"over_{_x}_5"
    _OBSERVEES[f"Moins de {_x}.5 buts"] = f"under_{_x}_5"


def cotes_archive(e):
    """Cotes d'un enregistrement de l'archive, en noms de MARCHES : BetPawa d'abord, cotes observées en complément."""
    cotes = {}
    for (groupe, issue), marche in _BETPAWA.items():
        v = ((e.get("cotes_betpawa") or {}).get(groupe) or {}).get(issue)
        if isinstance(v, (int, float)) and v > 1:
            cotes[marche] = v
    for nom, marche in _OBSERVEES.items():
        v = (e.get("cotes_observees") or {}).get(nom)
        if marche not in cotes and isinstance(v, (int, float)) and v > 1:
            cotes[marche] = v
    return cotes


def _moyennes_lieu(matchs, domicile):
    lieu = [m for m in matchs if bool(m.get("domicile")) is domicile]
    if not lieu:
        return None, None, 0
    return (sum(m["buts_marques"] for m in lieu) / len(lieu), sum(m["buts_encaisses"] for m in lieu) / len(lieu),
            len(lieu))


def charge_archive(dossier=DOSSIER_ARCHIVE):
    """([(entree, score)], nb_ecartes_fuite) : matchs testables de l'archive qui ont un score."""
    out, fuite = [], 0
    for chemin in sorted(glob.glob(os.path.join(dossier, "*.json.gz"))):
        with gzip.open(chemin, "rt", encoding="utf-8") as f:
            donnees = json.load(f)
        for e in donnees.values():
            sc = e.get("score") or {}
            if not e.get("testable") or not isinstance(sc.get("buts_dom"), int) or not isinstance(sc.get("buts_ext"), int):
                continue
            md = (e.get("equipe_dom") or {}).get("matchs") or []
            mx = (e.get("equipe_ext") or {}).get("matchs") or []
            if any(str(m.get("date")) >= str(e.get("date")) for m in md + mx):
                fuite += 1
                continue
            gf_d, ga_d, nd = _moyennes_lieu(md, True)
            gf_e, ga_e, ne = _moyennes_lieu(mx, False)
            entree = {
                "id": e.get("match_id"), "date": e.get("date"), "competition": e.get("competition"),
                "source": "archive", "n_lieu": min(nd, ne), "cotes": cotes_archive(e),
                "equipe_dom": _equipe_moyennes(e.get("domicile"), gf_d, ga_d, nd, md),
                "equipe_ext": _equipe_moyennes(e.get("exterieur"), gf_e, ga_e, ne, mx),
                "assemblage": e.get("assemblage"),
            }
            out.append((entree, (sc["buts_dom"], sc["buts_ext"])))
    return out, fuite


# --- modèles de référence (pour situer un moteur, pas pour être mis en production) ------------------------------------

def _poisson(l, k):
    return math.exp(-l) * l ** k / math.factorial(k)


def probas_poisson(lh, la, max_buts=10):
    """Probabilités de tous les marchés de MARCHES à partir de deux buts attendus (Poisson indépendant, grille
    normalisée)."""
    ph = [_poisson(lh, k) for k in range(max_buts + 1)]
    pa = [_poisson(la, k) for k in range(max_buts + 1)]
    z = sum(ph) * sum(pa)
    out = {}
    for marche, (_, regle) in MARCHES.items():
        out[marche] = sum(ph[i] * pa[j] for i in range(max_buts + 1) for j in range(max_buts + 1) if regle(i, j)) / z
    return out


def _moyennes(entree):
    d, e = entree["equipe_dom"], entree["equipe_ext"]
    vals = (d["buts_marques_moy"], d["buts_encaisses_moy"], e["buts_marques_moy"], e["buts_encaisses_moy"])
    return None if any(v is None for v in vals) else vals


def modele_marche(entree):
    """Référence : probabilités du marché sans marge. Écart attendu nul -- sert de contrôle du banc lui-même."""
    return probabilites_marche(entree["cotes"])


def modele_v2_produit(entree):
    """Formule V2 : λ = racine(attaque × défense adverse), plancher 0,05 (piège du zéro inclus, volontairement)."""
    m = _moyennes(entree)
    if m is None:
        return {}
    hgf, hga, agf, aga = m
    return probas_poisson(max(0.05, math.sqrt(max(0, hgf) * max(0, aga))),
                          max(0.05, math.sqrt(max(0, agf) * max(0, hga))))


def modele_moyenne(entree):
    """λ = moyenne simple (attaque, défense adverse), plancher numérique 0,2."""
    m = _moyennes(entree)
    if m is None:
        return {}
    hgf, hga, agf, aga = m
    return probas_poisson(max(0.2, (hgf + aga) / 2), max(0.2, (agf + hga) / 2))


MOYENNE_REFERENCE = 1.35       # buts par équipe et par match, ordre de grandeur fixe (pas estimé sur les résultats)


def modele_lisse(entree, k=4.0):
    """Attaque et défense relatives, tirées vers MOYENNE_REFERENCE selon le nombre de matchs (k matchs fictifs)."""
    m = _moyennes(entree)
    if m is None:
        return {}
    hgf, hga, agf, aga = m
    nd, ne = entree["equipe_dom"]["matchs_joues"], entree["equipe_ext"]["matchs_joues"]
    mu = MOYENNE_REFERENCE

    def lisse(v, n):
        return (n * v + k * mu) / (n + k)
    return probas_poisson(lisse(hgf, nd) * lisse(aga, ne) / mu, lisse(agf, ne) * lisse(hga, nd) / mu)


MODELES_REFERENCE = {"marche": modele_marche, "v2_produit": modele_v2_produit, "moyenne": modele_moyenne,
                     "lisse_k4": modele_lisse}


# --- règle de décision de référence (V2 : fenêtre de cote, P >= 60 %, EDV minimale) ----------------------------------

def _edv_minimale(p):
    if p < .60:
        return None
    return 12.0 if p < .63 else 10.0 if p < .67 else 7.0 if p < .71 else 5.0


def selection_regle_v2(entree, probas):
    """Règle de décision de V2 (value_engine + decision_engine) : cote 1,26-1,74, P >= 60 %, EDV minimale selon P, une
    seule sélection par famille, au plus 3, par EDV décroissante."""
    cands = []
    for marche, p in probas.items():
        c = entree["cotes"].get(marche)
        if not c or not 1.26 <= c <= 1.74:
            continue
        seuil = _edv_minimale(p)
        edv = 100 * (p * c - 1)
        if seuil is not None and edv >= seuil:
            cands.append((edv, p, marche))
    cands.sort(reverse=True)
    retenus, familles = [], set()
    for _, _, marche in cands:
        fam = MARCHES[marche][0]
        if fam in familles:
            continue
        retenus.append(marche)
        familles.add(fam)
        if len(retenus) == 3:
            break
    return retenus


# --- mesures ----------------------------------------------------------------------------------------------------------

def _tranche_n(n):
    return "N 0-2" if n <= 2 else "N 3-4" if n <= 4 else "N 5+"


def _tranche_cote(c):
    if c is None:
        return "sans cote"
    for borne, nom in ((1.30, "cote < 1,30"), (1.60, "cote 1,30-1,59"), (2.00, "cote 1,60-1,99"),
                       (3.00, "cote 2,00-2,99")):
        if c < borne:
            return nom
    return "cote >= 3,00"


def observations(jeu, modele):
    """Une observation par (match, marché) où le modèle ET le marché donnent une probabilité."""
    obs, rejets = [], defaultdict(int)
    for entree, (h, a) in jeu:
        pm = probabilites_marche(entree["cotes"])
        if not pm:
            rejets["sans cotes exploitables"] += 1
            continue
        try:
            probas = modele(entree) or {}
        except Exception as e:  # un moteur qui plante sur un match : compté, jamais masqué
            rejets[f"erreur du modèle : {type(e).__name__}"] += 1
            continue
        if not probas:
            rejets["le modèle ne donne aucune probabilité"] += 1
            continue
        for marche, p in probas.items():
            if marche not in MARCHES or marche not in pm:
                continue
            if not isinstance(p, (int, float)) or not 0 <= p <= 1:
                rejets["probabilité invalide"] += 1
                continue
            obs.append({"match": entree["id"], "marche": marche, "famille": MARCHES[marche][0],
                        "p": float(p), "pm": pm[marche], "y": 1.0 if gagne(marche, h, a) else 0.0,
                        "cote": entree["cotes"].get(marche), "n": entree["n_lieu"], "source": entree["source"]})
    return obs, dict(rejets)


def _ll(p, y):
    p = min(max(p, EPS), 1 - EPS)
    return -math.log(p if y else 1 - p)


def _ic_par_match(obs, cle, tirages, graine):
    """Intervalle de confiance de la moyenne de `cle(o)` par bootstrap PAR MATCH (tirage avec remise des matchs)."""
    par_match = defaultdict(lambda: [0.0, 0])
    for o in obs:
        s = par_match[o["match"]]
        s[0] += cle(o)
        s[1] += 1
    sommes = list(par_match.values())
    if len(sommes) < 2:
        return None
    rng = random.Random(graine)
    moyennes = []
    for _ in range(tirages):
        tot = cnt = 0.0
        for _ in range(len(sommes)):
            s = sommes[rng.randrange(len(sommes))]
            tot += s[0]
            cnt += s[1]
        moyennes.append(tot / cnt)
    moyennes.sort()
    a = (1 - NIVEAU_IC) / 2
    return moyennes[int(a * tirages)], moyennes[min(tirages - 1, int((1 - a) * tirages))]


def verdict(n_matchs, n_obs, ic_ll):
    if n_matchs < MIN_MATCHS or n_obs < MIN_OBSERVATIONS or ic_ll is None:
        return "ÉCHANTILLON INSUFFISANT"
    if ic_ll[1] < 0:
        return "AVANTAGE MESURABLE"
    if ic_ll[0] > 0:
        return "MOINS BON QUE LE MARCHÉ"
    return "AUCUN AVANTAGE MESURABLE"


def stats_groupe(obs, tirages=TIRAGES_BOOTSTRAP, graine=GRAINE, avec_ic=True):
    if not obs:
        return None
    n = len(obs)
    matchs = len({o["match"] for o in obs})
    brier_m = sum((o["p"] - o["y"]) ** 2 for o in obs) / n
    brier_k = sum((o["pm"] - o["y"]) ** 2 for o in obs) / n
    ll_m = sum(_ll(o["p"], o["y"]) for o in obs) / n
    ll_k = sum(_ll(o["pm"], o["y"]) for o in obs) / n
    ic_ll = ic_br = None
    if avec_ic and matchs >= 2:
        ic_ll = _ic_par_match(obs, lambda o: _ll(o["p"], o["y"]) - _ll(o["pm"], o["y"]), tirages, graine)
        ic_br = _ic_par_match(obs, lambda o: (o["p"] - o["y"]) ** 2 - (o["pm"] - o["y"]) ** 2, tirages, graine)
    return {"observations": n, "matchs": matchs, "taux_reel": sum(o["y"] for o in obs) / n,
            "p_moyenne_modele": sum(o["p"] for o in obs) / n, "p_moyenne_marche": sum(o["pm"] for o in obs) / n,
            "brier_modele": brier_m, "brier_marche": brier_k, "ecart_brier": brier_m - brier_k, "ic_ecart_brier": ic_br,
            "logloss_modele": ll_m, "logloss_marche": ll_k, "ecart_logloss": ll_m - ll_k, "ic_ecart_logloss": ic_ll,
            "verdict": verdict(matchs, n, ic_ll)}


def calibration(obs):
    """Par tranche de 10 points de probabilité annoncée : annoncé vs réel. `ecart_max` sur les tranches assez remplies."""
    tranches = defaultdict(list)
    for o in obs:
        tranches[min(9, int(o["p"] * 10))].append(o)
    lignes, ecart_max = [], None
    for t in sorted(tranches):
        grp = tranches[t]
        annonce = sum(o["p"] for o in grp) / len(grp)
        reel = sum(o["y"] for o in grp) / len(grp)
        marche = sum(o["pm"] for o in grp) / len(grp)
        lignes.append({"tranche": f"{t * 10}-{t * 10 + 10} %", "n": len(grp), "annonce": annonce, "reel": reel,
                       "marche": marche, "ecart": annonce - reel})
        if len(grp) >= MIN_TRANCHE_CALIBRATION:
            ecart_max = abs(annonce - reel) if ecart_max is None else max(ecart_max, abs(annonce - reel))
    return {"tranches": lignes, "ecart_max_tranches_suffisantes": ecart_max}


def evalue_selection(jeu, modele, selection, tirages=TIRAGES_BOOTSTRAP, graine=GRAINE):
    """Mesure SECONDAIRE : réussite et ROI à mise plate des sélections d'une règle de décision."""
    paris, erreurs = [], defaultdict(int)
    for entree, (h, a) in jeu:
        try:
            probas = modele(entree) or {}
            choix = selection(entree, probas) or []
        except Exception as e:  # compté et affiché, jamais masqué
            erreurs[f"{type(e).__name__}"] += 1
            continue
        pm = probabilites_marche(entree["cotes"])
        for marche in choix:
            c = entree["cotes"].get(marche)
            if marche not in MARCHES or not c or marche not in probas:
                continue
            y = 1.0 if gagne(marche, h, a) else 0.0
            paris.append({"match": entree["id"], "marche": marche, "p": probas[marche], "pm": pm.get(marche),
                          "cote": c, "y": y, "gain": y * c - 1})
    if not paris:
        return {"selections": 0, "erreurs": dict(erreurs)}
    n = len(paris)
    ic = _ic_par_match(paris, lambda o: o["gain"], tirages, graine) if len({p["match"] for p in paris}) >= 2 else None
    pms = [p["pm"] for p in paris if p["pm"] is not None]
    return {"selections": n, "matchs": len({p["match"] for p in paris}),
            "reussite_reelle": sum(p["y"] for p in paris) / n, "reussite_annoncee": sum(p["p"] for p in paris) / n,
            "reussite_prevue_par_le_marche": (sum(pms) / len(pms)) if pms else None,
            "roi": sum(p["gain"] for p in paris) / n, "ic_roi": ic, "erreurs": dict(erreurs)}


def evalue(jeu, modele, selection=None, tirages=TIRAGES_BOOTSTRAP, graine=GRAINE):
    obs, rejets = observations(jeu, modele)
    rapport = {"matchs_du_jeu": len(jeu), "rejets": rejets, "global": stats_groupe(obs, tirages, graine),
               "par_famille": {}, "par_marche": {}, "par_n": {}, "par_cote": {}, "par_source": {},
               "calibration": calibration(obs) if obs else None}
    for nom, cle, ic in (("par_famille", "famille", True), ("par_marche", "marche", True),
                         ("par_n", "n", True), ("par_cote", "cote", True), ("par_source", "source", True)):
        grp = defaultdict(list)
        for o in obs:
            k = _tranche_n(o["n"]) if cle == "n" else _tranche_cote(o["cote"]) if cle == "cote" else o[cle]
            grp[k].append(o)
        rapport[nom] = {k: stats_groupe(v, tirages, graine, avec_ic=ic) for k, v in sorted(grp.items())}
    if selection is not None:
        rapport["selection"] = evalue_selection(jeu, modele, selection, tirages, graine)
    return rapport


# --- rapport lisible --------------------------------------------------------------------------------------------------

def _pct(x):
    return "—" if x is None else f"{100 * x:.1f} %"


def _ic(iv, facteur=1.0, suffixe="", decimales=4):
    return "—" if not iv else f"[{iv[0] * facteur:+.{decimales}f} ; {iv[1] * facteur:+.{decimales}f}]{suffixe}"


def rapport_texte(nom, r):
    lignes = [f"=== {nom} ===", f"Matchs du jeu : {r['matchs_du_jeu']} ; rejets : {r['rejets'] or 'aucun'}"]
    g = r["global"]
    if not g:
        return "\n".join(lignes + ["Aucune observation."])
    lignes.append(f"GLOBAL : {g['verdict']} -- {g['observations']} observations sur {g['matchs']} matchs ; log-loss "
                  f"modèle {g['logloss_modele']:.4f} vs marché {g['logloss_marche']:.4f} (écart {g['ecart_logloss']:+.4f}, "
                  f"IC {_ic(g['ic_ecart_logloss'])}) ; Brier {g['brier_modele']:.4f} vs {g['brier_marche']:.4f}")
    # La réussite moyenne n'a de sens que par marché : une famille mélange des issues complémentaires (victoire + nul +
    # défaite = 100 %), sa moyenne est donc toujours la même. Elle n'est affichée que dans « Par marché ».
    for titre, cle, avec_taux in (("Par famille", "par_famille", False), ("Par marché", "par_marche", True),
                                  ("Par taille d'échantillon", "par_n", False),
                                  ("Par tranche de cote", "par_cote", True), ("Par source", "par_source", False)):
        lignes.append(f"-- {titre}")
        for k, s in r[cle].items():
            ligne = (f"   {k:<16} {s['verdict']:<26} n={s['observations']:<5} matchs={s['matchs']:<4} "
                     f"écart log-loss {s['ecart_logloss']:+.4f} IC {_ic(s['ic_ecart_logloss'])}")
            if avec_taux:
                ligne += (f" | réel {_pct(s['taux_reel'])} annoncé {_pct(s['p_moyenne_modele'])} "
                          f"marché {_pct(s['p_moyenne_marche'])}")
            lignes.append(ligne)
    cal = r.get("calibration") or {}
    lignes.append(f"-- Calibration (écart max sur tranches >= {MIN_TRANCHE_CALIBRATION} obs : "
                  f"{_pct(cal.get('ecart_max_tranches_suffisantes'))})")
    for t in cal.get("tranches", []):
        lignes.append(f"   {t['tranche']:<10} n={t['n']:<5} annoncé {_pct(t['annonce'])} réel {_pct(t['reel'])} "
                      f"marché {_pct(t['marche'])}")
    sel = r.get("selection")
    if sel:
        if sel.get("selections"):
            lignes.append(f"-- Sélections (mesure secondaire) : {sel['selections']} sur {sel['matchs']} matchs ; réussite "
                          f"réelle {_pct(sel['reussite_reelle'])}, annoncée {_pct(sel['reussite_annoncee'])}, prévue par "
                          f"le marché {_pct(sel['reussite_prevue_par_le_marche'])} ; ROI {_pct(sel['roi'])} "
                          f"IC {_ic(sel['ic_roi'], 100, ' pts', 1)}")
        else:
            lignes.append("-- Sélections : aucune.")
        if sel.get("erreurs"):
            lignes.append(f"   ERREURS du moteur ou de la règle de décision (matchs ignorés) : {sel['erreurs']}")
    return "\n".join(lignes)


def _charge_fonction(spec):
    module, _, fonction = spec.partition(":")
    if not fonction:
        raise ValueError(f"format attendu module:fonction, reçu {spec!r}")
    sys.path.insert(0, RACINE)
    return getattr(importlib.import_module(module), fonction)


def charge_jeu(source):
    jeu, infos = [], {}
    if source in ("snapshot", "tous"):
        ok = verifie_empreinte(FICHIER_SNAPSHOT)
        infos["empreinte_snapshot_conforme"] = ok
        if not ok:
            raise SystemExit("REFUS : l'empreinte SHA-256 du jeu figé ne correspond pas -- le jeu a été modifié.")
        jeu += charge_snapshot()
    if source in ("archive", "tous"):
        arch, fuite = charge_archive()
        infos["archive_matchs_avec_score"] = len(arch)
        infos["archive_ecartes_fuite"] = fuite
        jeu += arch
    return jeu, infos


def main(argv=None):
    p = argparse.ArgumentParser(description="Banc de test historique : un moteur contre le marché.")
    p.add_argument("--modele", help="module:fonction (défaut : les modèles de référence)")
    p.add_argument("--selection", default="regle_v2",
                   help="module:fonction, « regle_v2 » (défaut) ou « aucune »")
    p.add_argument("--source", choices=("snapshot", "archive", "tous"), default="snapshot")
    p.add_argument("--tirages", type=int, default=TIRAGES_BOOTSTRAP)
    p.add_argument("--json", help="écrire le rapport complet dans ce fichier")
    a = p.parse_args(argv)
    jeu, infos = charge_jeu(a.source)
    modeles = {a.modele: _charge_fonction(a.modele)} if a.modele else MODELES_REFERENCE
    selection = None if a.selection == "aucune" else selection_regle_v2 if a.selection == "regle_v2" \
        else _charge_fonction(a.selection)
    print(f"Banc historique -- source {a.source} : {len(jeu)} matchs ; {infos}")
    complet = {"source": a.source, "infos": infos, "seuils": {"min_matchs": MIN_MATCHS,
               "min_observations": MIN_OBSERVATIONS, "niveau_ic": NIVEAU_IC, "tirages": a.tirages, "graine": GRAINE},
               "modeles": {}}
    for nom, f in modeles.items():
        r = evalue(jeu, f, selection, a.tirages)
        complet["modeles"][nom] = r
        print()
        print(rapport_texte(nom, r))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(complet, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
