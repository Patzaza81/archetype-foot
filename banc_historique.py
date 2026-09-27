#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
banc_historique.py -- BANC DE TEST HISTORIQUE : juge n'importe quel moteur contre le marché, sur des matchs déjà joués,
avec uniquement ce qui était connu avant le coup d'envoi.

Pourquoi (27/09/2026). Aucun moteur (V0, spécifications ChatGPT, ARCHETYPE_FOOT, V2) n'a été validé sur des résultats
réels avant d'être remplacé. Mesure du 27/09 sur 501 matchs : V2 annonce 81,9 % et réussit 63,3 %, exactement ce que
prévoyait déjà le marché (62,8 %). Ce banc est la porte obligatoire avant tout branchement au pipeline.

Le banc est INDÉPENDANT de tout moteur : il juge `modele(entree) -> {marche: probabilite}` et, facultativement,
`selection(entree, probas) -> [marches]`. Un moteur s'adapte au banc, jamais l'inverse.

DEUX VERDICTS SÉPARÉS (corrections du 27/09 demandées par le concepteur de la V3) :
  1. PERFORMANCE VS MARCHÉ -- écarts Brier ET log-loss (modèle - marché sans marge), intervalles à 95 % par bootstrap
     PAR MATCH (les marchés d'un même match sont liés) :
       - ÉCHANTILLON INSUFFISANT : moins de MIN_MATCHS matchs ou MIN_OBSERVATIONS observations -> aucune conclusion ;
       - MOINS BON QUE LE MARCHÉ : significativement moins bon sur AU MOINS UNE des deux mesures ;
       - AVANTAGE MESURABLE : significativement moins bon sur AUCUNE et significativement meilleur sur au moins une ;
       - AUCUN AVANTAGE MESURABLE : sinon. Le moteur doit alors conclure « pas d'avantage mesurable -> pas de pari ».
  2. CALIBRATION -- par tranche de 10 points de probabilité annoncée : observations, annoncé, réel, écart et son
     intervalle. Tranche d'au moins MIN_TRANCHE_CALIBRATION observations : CALIBRATION_ACCEPTABLE si l'écart absolu est
     <= TOLERANCE_CALIBRATION (5 points), sinon CALIBRATION_HORS_TOLERANCE ; tranche plus petite : ÉCHANTILLON
     INSUFFISANT (jamais déclarée mauvaise sur un petit échantillon). Verdict global : HORS_TOLERANCE si une tranche
     suffisante l'est, ACCEPTABLE si toutes les tranches suffisantes le sont, sinon ÉCHANTILLON INSUFFISANT.
Le marché n'est pas une vérité absolue : c'est la référence externe à battre.

HIÉRARCHIE DU RAPPORT : marché, famille, taille d'échantillon (N au même lieu : 0-2, 3-4, 5+), tranche de cote, source.
Un groupe sous les seuils est marqué « informatif » : il n'est jamais décisionnel. La conclusion globale ne vient que du
groupe global.

CODES DE REJET (distincts, pour diagnostiquer un moteur) :
  PAS_DE_COTE (match sans aucune cote exploitable, ou probabilité fournie pour un marché sans cote), ERREUR_MOTEUR (le
  moteur lève une exception), MARCHÉ_NON_DISPONIBLE (le marché a une cote mais le moteur ne donne pas de probabilité :
  absence explicite, jamais une valeur inventée), PROBABILITÉ_INVALIDE (hors de [0 ; 1] ou non numérique),
  MARCHÉ_HORS_REGISTRE (nom de marché inconnu du banc). ÉCHANTILLON INSUFFISANT est un verdict de groupe.

REGISTRE DES MARCHÉS (périmètre gelé) : 1X2, double chance, BTTS, plus/moins 0,5 à 5,5, buts d'équipe 0,5 et 1,5, cage
inviolée, nombre exact de buts (0 à 5, 6+). Un marché n'est évalué que s'il a une cote dans la source : aucune
probabilité de marché n'est créée pour un marché absent. PAS ENCORE RÉGLABLES : handicaps (étiquettes BetPawa
incohérentes, constat du 27/09), mi-temps (aucun score de mi-temps dans les sources réglées, aucune cote relevée),
corners et cartons (aucune cote relevée). Ils seront ajoutés quand ces données existeront réellement.

RÈGLES DU PROTOCOLE :
  1. Aucune donnée postérieure au match : le jeu figé est construit avant les scores (empreinte SHA-256 vérifiée, refus
     si elle ne correspond pas) ; pour l'archive de test, tout match d'équipe daté du jour du match ou après fait écarter
     le match (compté dans `archive_ecartes_fuite`).
  2. Le banc VALIDE, il ne sert pas à régler : les seuils ci-dessous sont fixés ici une fois pour toutes. Le jeu figé
     est un jeu de VALIDATION, jamais d'entraînement (voir evaluation/README.md, règle n°6).
  3. Verrou de non-régression : V2 sur le PERIMETRE_REFERENCE_2709 (marchés du premier banc) doit toujours redonner 548
     sélections, 81,9 % annoncés, 63,3 % réels, ROI -6,2 % (tests/test_banc_historique.py).

SOURCES :
  - « snapshot » : evaluation/snapshot_historique_moteur_v2_6_9.json + scores (503 matchs, 501 avec score). Contient les
    MOYENNES d'avant-match au même lieu (pas la liste des matchs) : la règle du double contrôle n'y est pas applicable.
  - « archive » : data/archive_test/*.json.gz (archive_donnees_test.py), matchs testables AVEC score : listes complètes
    des matchs des deux équipes + assemblage Football-Data (mi-temps, tirs, corners...) quand il existe.

`entree` (même forme pour les deux sources) :
    id, date, competition, source, n_lieu (= min des matchs au même lieu des deux équipes),
    cotes {marche: cote}, equipe_dom / equipe_ext {nom, buts_marques_moy, buts_encaisses_moy, matchs_joues,
    matchs (liste complète, archive seulement, sinon None)}, assemblage (archive seulement, sinon None).

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
TOLERANCE_CALIBRATION = 0.05
NIVEAU_IC = 0.95
TIRAGES_BOOTSTRAP = 1000
GRAINE = 20260927
EPS = 1e-6

# Verdicts et codes (chaînes exactes, utilisées par les tests et les rapports)
INSUFFISANT = "ÉCHANTILLON INSUFFISANT"
AVANTAGE = "AVANTAGE MESURABLE"
MOINS_BON = "MOINS BON QUE LE MARCHÉ"
AUCUN_AVANTAGE = "AUCUN AVANTAGE MESURABLE"
CAL_OK = "CALIBRATION_ACCEPTABLE"
CAL_HORS = "CALIBRATION_HORS_TOLERANCE"
PAS_DE_COTE = "PAS_DE_COTE"
ERREUR_MOTEUR = "ERREUR_MOTEUR"
NON_DISPONIBLE = "MARCHÉ_NON_DISPONIBLE"
INVALIDE = "PROBABILITÉ_INVALIDE"
HORS_REGISTRE = "MARCHÉ_HORS_REGISTRE"

# --- registre des marchés : famille + règle de gain sur le score final (h = buts domicile, a = buts extérieur) -------
MARCHES = {
    "victoire": ("resultat", lambda h, a: h > a),
    "nul": ("resultat", lambda h, a: h == a),
    "defaite": ("resultat", lambda h, a: h < a),
    "dc_1X": ("double_chance", lambda h, a: h >= a),
    "dc_X2": ("double_chance", lambda h, a: h <= a),
    "dc_12": ("double_chance", lambda h, a: h != a),
    "btts_oui": ("btts", lambda h, a: h > 0 and a > 0),
    "btts_non": ("btts", lambda h, a: h == 0 or a == 0),
    "clean_sheet_dom": ("cage_inviolee", lambda h, a: a == 0),
    "clean_sheet_dom_non": ("cage_inviolee", lambda h, a: a > 0),
    "clean_sheet_ext": ("cage_inviolee", lambda h, a: h == 0),
    "clean_sheet_ext_non": ("cage_inviolee", lambda h, a: h > 0),
}
for _x in range(6):
    MARCHES[f"over_{_x}_5"] = ("total_buts", (lambda x: lambda h, a: h + a > x)(_x))
    MARCHES[f"under_{_x}_5"] = ("total_buts", (lambda x: lambda h, a: h + a <= x)(_x))
for _x in range(2):
    MARCHES[f"buts_dom_over_{_x}_5"] = ("buts_domicile", (lambda x: lambda h, a: h > x)(_x))
    MARCHES[f"buts_dom_under_{_x}_5"] = ("buts_domicile", (lambda x: lambda h, a: h <= x)(_x))
    MARCHES[f"buts_ext_over_{_x}_5"] = ("buts_exterieur", (lambda x: lambda h, a: a > x)(_x))
    MARCHES[f"buts_ext_under_{_x}_5"] = ("buts_exterieur", (lambda x: lambda h, a: a <= x)(_x))
for _n in range(6):
    MARCHES[f"exact_goals_{_n}"] = ("nombre_exact_buts", (lambda n: lambda h, a: h + a == n)(_n))
MARCHES["exact_goals_6_plus"] = ("nombre_exact_buts", lambda h, a: h + a >= 6)

# Groupes d'issues complémentaires (chaque groupe est normalisé à 1 pour retirer la marge).
GROUPES_MARCHE = ([("victoire", "nul", "defaite"), ("btts_oui", "btts_non")]
                  + [(f"over_{x}_5", f"under_{x}_5") for x in range(6)]
                  + [(f"buts_{c}_over_{x}_5", f"buts_{c}_under_{x}_5") for c in ("dom", "ext") for x in range(2)]
                  + [tuple(f"exact_goals_{n}" for n in range(6)) + ("exact_goals_6_plus",)])
# Cage inviolée : complément vendu (« non ») ou, à défaut, le marché de même événement (l'adversaire marque au moins 1).
COMPLEMENT_CAGE = {"clean_sheet_dom": ("clean_sheet_dom_non", "buts_ext_over_0_5"),
                   "clean_sheet_ext": ("clean_sheet_ext_non", "buts_dom_over_0_5")}

# Marchés du premier banc (27/09) : périmètre du verrou de non-régression V2. Ne jamais le modifier.
PERIMETRE_REFERENCE_2709 = frozenset(
    ["victoire", "nul", "defaite", "dc_1X", "dc_X2", "dc_12", "btts_oui", "btts_non"]
    + [f"{s}_{x}_5" for s in ("over", "under") for x in range(5)])


def gagne(marche, h, a):
    return bool(MARCHES[marche][1](h, a))


def _cote_ok(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v > 1


def probabilites_marche(cotes):
    """Probabilités du marché SANS marge. Chaque groupe d'issues complémentaires est normalisé à 1 ; un groupe incomplet
    ne donne rien (jamais de probabilité inventée). La double chance est déduite du 1X2 sans marge (ses propres cotes
    restent utilisées pour le ROI)."""
    p = {}
    for groupe in GROUPES_MARCHE:
        if all(_cote_ok(cotes.get(k)) for k in groupe):
            s = sum(1 / cotes[k] for k in groupe)
            for k in groupe:
                p[k] = (1 / cotes[k]) / s
    for oui, complements in COMPLEMENT_CAGE.items():
        non = next((c for c in complements if _cote_ok(cotes.get(c))), None)
        if _cote_ok(cotes.get(oui)) and non:
            s = 1 / cotes[oui] + 1 / cotes[non]
            p[oui] = (1 / cotes[oui]) / s
            p[oui + "_non"] = (1 / cotes[non]) / s
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
            ("btts", "Oui"): "btts_oui", ("btts", "Non"): "btts_non",
            ("cages_inviolees_domicile", "oui"): "clean_sheet_dom",
            ("cages_inviolees_domicile", "non"): "clean_sheet_dom_non",
            ("cages_inviolees_exterieur", "oui"): "clean_sheet_ext",
            ("cages_inviolees_exterieur", "non"): "clean_sheet_ext_non"}
_OBSERVEES = {"1X2 - 1": "victoire", "1X2 - X": "nul", "1X2 - 2": "defaite", "Double chance - 1X": "dc_1X",
              "Double chance - X2": "dc_X2", "Double chance - 12": "dc_12", "BTTS - oui": "btts_oui",
              "BTTS - non": "btts_non", "Cage inviolée - Domicile": "clean_sheet_dom",
              "Encaisse au moins 1 but - Domicile": "clean_sheet_dom_non",   # complément de « Cage inviolée - Domicile »
              "Cage inviolée - Extérieur": "clean_sheet_ext",
              "Encaisse au moins 1 but - Extérieur": "clean_sheet_ext_non"}
for _x in range(6):
    _BETPAWA[(f"over_under_{_x}.5", "plus")] = f"over_{_x}_5"
    _BETPAWA[(f"over_under_{_x}.5", "moins")] = f"under_{_x}_5"
    _OBSERVEES[f"Plus de {_x}.5 buts"] = f"over_{_x}_5"
    _OBSERVEES[f"Moins de {_x}.5 buts"] = f"under_{_x}_5"
for _x in range(2):
    for _cote, _nom, _libelle in (("dom", "domicile", "Domicile"), ("ext", "exterieur", "Extérieur")):
        _BETPAWA[(f"over_under_{_nom}_{_x}.5", "plus")] = f"buts_{_cote}_over_{_x}_5"
        _BETPAWA[(f"over_under_{_nom}_{_x}.5", "moins")] = f"buts_{_cote}_under_{_x}_5"
        _OBSERVEES[f"Plus de {_x}.5 buts - {_libelle}"] = f"buts_{_cote}_over_{_x}_5"
        _OBSERVEES[f"Moins de {_x}.5 buts - {_libelle}"] = f"buts_{_cote}_under_{_x}_5"
for _n in range(6):
    _BETPAWA[("nombre_exact_buts", str(_n))] = f"exact_goals_{_n}"
_BETPAWA[("nombre_exact_buts", "6+")] = "exact_goals_6_plus"


def cotes_archive(e):
    """Cotes d'un enregistrement de l'archive, en noms de MARCHES : BetPawa d'abord, cotes observées en complément."""
    cotes = {}
    for (groupe, issue), marche in _BETPAWA.items():
        v = ((e.get("cotes_betpawa") or {}).get(groupe) or {}).get(issue)
        if _cote_ok(v):
            cotes[marche] = v
    for nom, marche in _OBSERVEES.items():
        v = (e.get("cotes_observees") or {}).get(nom)
        if marche not in cotes and _cote_ok(v):
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
    """Probabilités de tous les marchés du registre à partir de deux buts attendus (Poisson indépendant, grille
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
        if marche not in MARCHES or p is None or not c or not 1.26 <= c <= 1.74:
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


def restreint(fonction, perimetre):
    """Enveloppe un modèle (ou une règle de décision) pour ne garder que les marchés d'un périmètre donné."""
    def modele(entree, *args):
        out = fonction(entree, *args)
        if isinstance(out, dict):
            return {k: v for k, v in out.items() if k in perimetre}
        return [m for m in (out or []) if m in perimetre]
    return modele


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
    """Une observation par (match, marché) où le modèle ET le marché donnent une probabilité. Tout le reste est compté
    sous un code de rejet distinct (total et détail par marché)."""
    obs = []
    rejets = defaultdict(int)
    detail = defaultdict(lambda: defaultdict(int))
    for entree, (h, a) in jeu:
        pm = probabilites_marche(entree["cotes"])
        if not pm:
            rejets[PAS_DE_COTE] += 1
            detail[PAS_DE_COTE]["(match entier)"] += 1
            continue
        try:
            probas = modele(entree) or {}
        except Exception as e:  # un moteur qui plante sur un match : compté, jamais masqué
            rejets[ERREUR_MOTEUR] += 1
            detail[ERREUR_MOTEUR][type(e).__name__] += 1
            continue
        for marche in probas:
            if marche not in MARCHES:
                rejets[HORS_REGISTRE] += 1
                detail[HORS_REGISTRE][str(marche)] += 1
            elif marche not in pm and probas[marche] is not None:
                rejets[PAS_DE_COTE] += 1
                detail[PAS_DE_COTE][marche] += 1
        for marche, p_marche in pm.items():
            p = probas.get(marche)
            if p is None:
                rejets[NON_DISPONIBLE] += 1
                detail[NON_DISPONIBLE][marche] += 1
                continue
            if not isinstance(p, (int, float)) or isinstance(p, bool) or not 0 <= p <= 1:
                rejets[INVALIDE] += 1
                detail[INVALIDE][marche] += 1
                continue
            obs.append({"match": entree["id"], "marche": marche, "famille": MARCHES[marche][0],
                        "p": float(p), "pm": p_marche, "y": 1.0 if gagne(marche, h, a) else 0.0,
                        "cote": entree["cotes"].get(marche), "n": entree["n_lieu"], "source": entree["source"]})
    return obs, dict(rejets), {k: dict(v) for k, v in detail.items()}


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


def verdict(n_matchs, n_obs, ic_ll, ic_br):
    """Performance vs marché, sur les DEUX mesures (écarts modèle - marché : négatif = modèle meilleur)."""
    if n_matchs < MIN_MATCHS or n_obs < MIN_OBSERVATIONS or ic_ll is None or ic_br is None:
        return INSUFFISANT
    if ic_ll[0] > 0 or ic_br[0] > 0:
        return MOINS_BON
    if ic_ll[1] < 0 or ic_br[1] < 0:
        return AVANTAGE
    return AUCUN_AVANTAGE


def stats_groupe(obs, tirages=TIRAGES_BOOTSTRAP, graine=GRAINE):
    if not obs:
        return None
    n = len(obs)
    matchs = len({o["match"] for o in obs})
    brier_m = sum((o["p"] - o["y"]) ** 2 for o in obs) / n
    brier_k = sum((o["pm"] - o["y"]) ** 2 for o in obs) / n
    ll_m = sum(_ll(o["p"], o["y"]) for o in obs) / n
    ll_k = sum(_ll(o["pm"], o["y"]) for o in obs) / n
    ic_ll = ic_br = None
    if matchs >= 2:
        ic_ll = _ic_par_match(obs, lambda o: _ll(o["p"], o["y"]) - _ll(o["pm"], o["y"]), tirages, graine)
        ic_br = _ic_par_match(obs, lambda o: (o["p"] - o["y"]) ** 2 - (o["pm"] - o["y"]) ** 2, tirages, graine)
    v = verdict(matchs, n, ic_ll, ic_br)
    return {"observations": n, "matchs": matchs, "taux_reel": sum(o["y"] for o in obs) / n,
            "p_moyenne_modele": sum(o["p"] for o in obs) / n, "p_moyenne_marche": sum(o["pm"] for o in obs) / n,
            "brier_modele": brier_m, "brier_marche": brier_k, "ecart_brier": brier_m - brier_k, "ic_ecart_brier": ic_br,
            "logloss_modele": ll_m, "logloss_marche": ll_k, "ecart_logloss": ll_m - ll_k, "ic_ecart_logloss": ic_ll,
            "verdict": v, "decisionnel": v != INSUFFISANT}


def statut_tranche(n, ecart):
    """Statut de calibration d'une tranche : jamais « hors tolérance » sur un petit échantillon."""
    if n < MIN_TRANCHE_CALIBRATION:
        return INSUFFISANT
    return CAL_OK if abs(ecart) <= TOLERANCE_CALIBRATION + 1e-12 else CAL_HORS


def verdict_calibration(tranches):
    suffisantes = [t for t in tranches if t["statut"] != INSUFFISANT]
    if not suffisantes:
        return INSUFFISANT
    return CAL_HORS if any(t["statut"] == CAL_HORS for t in suffisantes) else CAL_OK


def calibration(obs, tirages=TIRAGES_BOOTSTRAP, graine=GRAINE):
    """Par tranche de 10 points de probabilité annoncée : observations, annoncé, réel, écart (annoncé - réel) et son
    intervalle (bootstrap par match), statut ; puis verdict global de calibration."""
    tranches = defaultdict(list)
    for o in obs:
        tranches[min(9, int(o["p"] * 10))].append(o)
    lignes = []
    for t in sorted(tranches):
        grp = tranches[t]
        annonce = sum(o["p"] for o in grp) / len(grp)
        reel = sum(o["y"] for o in grp) / len(grp)
        ecart = annonce - reel
        lignes.append({"tranche": f"{t * 10}-{t * 10 + 10} %", "n": len(grp), "annonce": annonce, "reel": reel,
                       "marche": sum(o["pm"] for o in grp) / len(grp), "ecart": ecart,
                       "ic_ecart": _ic_par_match(grp, lambda o: o["p"] - o["y"], tirages, graine),
                       "statut": statut_tranche(len(grp), ecart)})
    return {"tranches": lignes, "verdict": verdict_calibration(lignes)}


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
            if marche not in MARCHES or not c or probas.get(marche) is None:
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


HIERARCHIE = (("par_marche", "marche"), ("par_famille", "famille"), ("par_n", "n"), ("par_cote", "cote"),
              ("par_source", "source"))


def evalue(jeu, modele, selection=None, tirages=TIRAGES_BOOTSTRAP, graine=GRAINE):
    obs, rejets, detail = observations(jeu, modele)
    rapport = {"matchs_du_jeu": len(jeu), "rejets": rejets, "rejets_detail": detail,
               "global": stats_groupe(obs, tirages, graine),
               "calibration": calibration(obs, tirages, graine) if obs else {"tranches": [], "verdict": INSUFFISANT}}
    for nom, cle in HIERARCHIE:
        grp = defaultdict(list)
        for o in obs:
            k = _tranche_n(o["n"]) if cle == "n" else _tranche_cote(o["cote"]) if cle == "cote" else o[cle]
            grp[k].append(o)
        rapport[nom] = {k: stats_groupe(v, tirages, graine) for k, v in sorted(grp.items())}
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
    lignes.append(f"PERFORMANCE VS MARCHÉ : {g['verdict']} -- {g['observations']} observations sur {g['matchs']} matchs")
    lignes.append(f"   log-loss modèle {g['logloss_modele']:.4f} vs marché {g['logloss_marche']:.4f} "
                  f"(écart {g['ecart_logloss']:+.4f}, IC {_ic(g['ic_ecart_logloss'])})")
    lignes.append(f"   Brier    modèle {g['brier_modele']:.4f} vs marché {g['brier_marche']:.4f} "
                  f"(écart {g['ecart_brier']:+.4f}, IC {_ic(g['ic_ecart_brier'])})")
    cal = r.get("calibration") or {}
    lignes.append(f"CALIBRATION : {cal.get('verdict', INSUFFISANT)} (tolérance {TOLERANCE_CALIBRATION * 100:.0f} points, "
                  f"tranches d'au moins {MIN_TRANCHE_CALIBRATION} observations)")
    for t in cal.get("tranches", []):
        lignes.append(f"   {t['tranche']:<10} n={t['n']:<5} annoncé {_pct(t['annonce'])} réel {_pct(t['reel'])} "
                      f"écart {100 * t['ecart']:+.1f} pts IC {_ic(t['ic_ecart'], 100, ' pts', 1)} -> {t['statut']}")
    # Hiérarchie : marché, famille, N, cote, source. Un groupe sous les seuils est informatif, jamais décisionnel.
    # La réussite moyenne n'a de sens que par marché ou tranche de cote : une famille mélange des issues
    # complémentaires (victoire + nul + défaite = 100 %).
    titres = {"par_marche": ("Par marché", True), "par_famille": ("Par famille", False),
              "par_n": ("Par taille d'échantillon", False), "par_cote": ("Par tranche de cote", True),
              "par_source": ("Par source", False)}
    for nom_groupe, _ in HIERARCHIE:
        titre, avec_taux = titres[nom_groupe]
        lignes.append(f"-- {titre}")
        for k, s in r[nom_groupe].items():
            ligne = (f"   {k:<22} {s['verdict']:<26}{'' if s['decisionnel'] else ' (informatif)'} "
                     f"n={s['observations']:<5} matchs={s['matchs']:<4} log-loss {s['ecart_logloss']:+.4f} "
                     f"IC {_ic(s['ic_ecart_logloss'])} Brier {s['ecart_brier']:+.4f} IC {_ic(s['ic_ecart_brier'])}")
            if avec_taux:
                ligne += (f" | réel {_pct(s['taux_reel'])} annoncé {_pct(s['p_moyenne_modele'])} "
                          f"marché {_pct(s['p_moyenne_marche'])}")
            lignes.append(ligne)
    for code, par_marche in (r.get("rejets_detail") or {}).items():
        lignes.append(f"-- Rejets {code} : {par_marche}")
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
    p.add_argument("--perimetre", choices=("complet", "reference_2709"), default="complet",
                   help="« reference_2709 » = marchés du premier banc (périmètre du verrou de non-régression)")
    p.add_argument("--tirages", type=int, default=TIRAGES_BOOTSTRAP)
    p.add_argument("--json", help="écrire le rapport complet dans ce fichier")
    a = p.parse_args(argv)
    jeu, infos = charge_jeu(a.source)
    modeles = {a.modele: _charge_fonction(a.modele)} if a.modele else dict(MODELES_REFERENCE)
    selection = None if a.selection == "aucune" else selection_regle_v2 if a.selection == "regle_v2" \
        else _charge_fonction(a.selection)
    if a.perimetre == "reference_2709":
        modeles = {nom: restreint(f, PERIMETRE_REFERENCE_2709) for nom, f in modeles.items()}
        selection = restreint(selection, PERIMETRE_REFERENCE_2709) if selection else None
    print(f"Banc historique -- source {a.source}, périmètre {a.perimetre} : {len(jeu)} matchs ; {infos}")
    complet = {"source": a.source, "perimetre": a.perimetre, "infos": infos,
               "seuils": {"min_matchs": MIN_MATCHS, "min_observations": MIN_OBSERVATIONS,
                          "min_tranche_calibration": MIN_TRANCHE_CALIBRATION,
                          "tolerance_calibration": TOLERANCE_CALIBRATION, "niveau_ic": NIVEAU_IC,
                          "tirages": a.tirages, "graine": GRAINE},
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
