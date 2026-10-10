#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
moteur_v3_pipeline.py -- BRANCHEMENT DU MOTEUR V3 EN PARALLÈLE (décision de Patrick du 27/09/2026 : « branche-moi la V3,
je lance le run manuellement »).

Statut : PRODUCTION PARALLÈLE. La V3 tourne à côté du moteur actif v2.6.10 : elle ne remplace pas automatiquement la décision principale, ne modifie
ni precalcul.py, ni calculs.py, ni scraper_details.py, ni les pronostics publiés. Sa validation reste celle fixée le
27/09 : 100 matchs NOUVEAUX avec score dans l'archive de test, jugés par banc_historique.py.

Ce que fait ce module, à chaque run du pipeline (appelé à la fin de enregistre_scores_historique.py, juste après
l'archive de test, dans un try : un échec ici ne bloque jamais le reste) :
  1. Lit l'archive de test (data/archive_test/) : c'est exactement l'avant-match que le pipeline vient d'enregistrer
     (listes complètes des matchs de chaque équipe, même compétition, cotes BetPawa). Aucun scraping supplémentaire.
  2. Calibration (obligatoire en V3) : apprise UNIQUEMENT sur les matchs de l'archive déjà joués, avec score, datés
     AVANT aujourd'hui. Jamais sur le jeu figé des 501 matchs (règle du 27/09 : jeu de contrôle, pas d'apprentissage).
     Moins de 300 observations : pas de calibration, donc aucune sélection (règle V3).
  3. Double contrôle (obligatoire, regles_selection.double_controle, décidé le 26/09) : saison dans les deux sens +
     forme récente. Sa liste de raisons sert de justification. Marché non couvert par la règle : pas de double contrôle,
     donc pas de sélection.
  4. Évalue chaque match à venir avec moteur_v3.evaluate_match et écrit data/v3/pronostics_v3.json : sélections,
     meilleurs candidats écartés avec la raison exacte, bilan chiffré de ce qui bloque, et `signaux` au MÊME format que
     precalcul_leger.json (bloc `moteur_v3` : statut + selection P1/P2/P3 avec justification). La page
     pronostics_v3.html est une copie de la page « Sélections Archetype » (archetype_v3.js = archetype.js avec
     CLE_MOTEUR = "moteur_v3") : même affichage, données V3 seulement, jamais mélangées avec la V2.
     data/ est commité par le workflow à chaque run.

Le nom de la compétition n'est JAMAIS transmis au moteur (règle « aucune discrimination par division »).

Utilisation à la main :  python moteur_v3_pipeline.py
"""
from __future__ import annotations

import datetime
import glob
import gzip
import hashlib
import json
import math
import os
import sys
from collections import Counter

import banc_historique as bh
import regles_selection as rs
from moteur_v3 import evaluate_match
from moteur_v3.calibration import CalibrationFit, IsotonicCalibrator
from moteur_v3.decision import decide
from moteur_v3.markets import derive_markets, gagne
from moteur_v3.model import K_LISSAGE, MOYENNE_REFERENCE, _latest, _lisse, _strength, build_model
from moteur_v3.performance import indice_performance
from moteur_v3.risk import goal_context_dispersion
from moteur_v3.value import ODDS_MAX, ODDS_MIN, edv_threshold

DOSSIER_ARCHIVE = os.path.join("data", "archive_test")
FICHIER_SORTIE = os.path.join("data", "v3", "pronostics_v3.json")
STATUT = "PRODUCTION PARALLÈLE — CANDIDAT"
# AJOUT 28/09/2026 (question de Patrick : « tout est-il archivé pour un contrôle sans ambiguïté ? ») -- JOURNAL V3.
# pronostics_v3.json est réécrit à chaque run et un match en disparaît au coup d'envoi : ce qui était affiché avant le
# match n'était retrouvable que dans l'historique git. Le journal garde, pour chaque match, le DERNIER calcul V3 fait
# avant le coup d'envoi (sélections, aperçus, candidats, calibration, empreinte du code) dans
# data/v3/journal/AAAA-MM-JJ.json. Après le coup d'envoi, l'entrée n'est plus jamais modifiée (execution() ne traite
# que les matchs à venir). Le score se lit dans l'archive de test, par match_id.
DOSSIER_JOURNAL = os.path.join("data", "v3", "journal")
# AJOUT 28/09/2026 (décision de Patrick : « calibration à partir de 50 matchs minimum, 15 trop petit »). Les 300
# observations du calibrateur sont des PARIS : un match coté en apporte ~25, tous liés au même score. 300 observations
# pouvaient donc venir de 12 matchs seulement. La calibration exige désormais AUSSI 50 matchs joués distincts.
MIN_MATCHS_CALIBRATION = 50
FICHIERS_CODE_V3 = ("moteur_v3/*.py", "moteur_v3_pipeline.py", "regles_selection.py", "banc_historique.py")

# Noms du banc (cotes de l'archive) -> noms du moteur V3. Les compléments de cage inviolée (« _non ») n'ont pas
# d'équivalent V3 : ils sont ignorés, jamais inventés.
BANC_VERS_V3 = {"victoire": "1x2_1", "nul": "1x2_X", "defaite": "1x2_2", "dc_1X": "dc_1X", "dc_X2": "dc_X2",
                "dc_12": "dc_12", "btts_oui": "btts_yes", "btts_non": "btts_no",
                "clean_sheet_dom": "clean_home", "clean_sheet_ext": "clean_away"}
for _x in range(6):
    for _s in ("over", "under"):
        BANC_VERS_V3[f"{_s}_{_x}_5"] = f"{_s}_{_x}_5"
for _x in range(2):
    for _s in ("over", "under"):
        BANC_VERS_V3[f"buts_dom_{_s}_{_x}_5"] = f"home_{_s}_{_x}_5"
        BANC_VERS_V3[f"buts_ext_{_s}_{_x}_5"] = f"away_{_s}_{_x}_5"
for _n in list(range(6)) + ["6_plus"]:
    BANC_VERS_V3[f"exact_goals_{_n}"] = f"exact_goals_{_n}"
V3_VERS_BANC = {v: k for k, v in BANC_VERS_V3.items()}

# Marchés V3 couverts par le double contrôle (regles_selection.MARCHES_COUVERTS).
DOUBLE_CONTROLE = {"1x2_1": "1X2 - 1", "1x2_2": "1X2 - 2", "dc_1X": "Double chance - 1X",
                   "dc_X2": "Double chance - X2", "under_2_5": "Moins de 2.5 buts", "under_3_5": "Moins de 3.5 buts",
                   "over_2_5": "Plus de 2.5 buts", "over_3_5": "Plus de 3.5 buts", "btts_yes": "BTTS - oui",
                   # AJOUT 28/09/2026 -- règle du double contrôle 1.2.0 (décision de Patrick : étendre la règle)
                   "dc_12": "Double chance - 12", "btts_no": "BTTS - non",
                   "over_1_5": "Plus de 1.5 buts", "under_4_5": "Moins de 4.5 buts",
                   # handicaps : ±0,5 = mêmes paris que 1X2 / double chance, donc même règle
                   "handicap_0.5_1": "1X2 - 1", "handicap_-0.5_1": "Double chance - 1X",
                   "handicap_-0.5_2": "1X2 - 2", "handicap_0.5_2": "Double chance - X2",
                   "handicap_1.5_1": "Handicap domicile -1.5", "handicap_-1.5_1": "Handicap domicile +1.5",
                   "handicap_-1.5_2": "Handicap extérieur -1.5", "handicap_1.5_2": "Handicap extérieur +1.5",
                   # « encaisse au moins un but » = l'adversaire marque ; « cage inviolée » = l'adversaire ne marque pas
                   "clean_home_no": "Buts extérieur - plus de 0.5", "clean_away_no": "Buts domicile - plus de 0.5",
                   "clean_home": "Buts extérieur - moins de 0.5", "clean_away": "Buts domicile - moins de 0.5",
                   # AJOUT 28/09/2026 -- handicap à 3 choix (lignes V3 entières). Seules les issues identiques à un
                   # pari déjà couvert prennent sa règle ; les issues « X » (écart exact) et « gagne par 3 buts ou
                   # plus » n'ont pas de règle : calculées, jamais sélectionnables.
                   "handicap_1_1": "Handicap domicile -1.5", "handicap_1_2": "Double chance - X2",
                   "handicap_-1_1": "Double chance - 1X", "handicap_-1_2": "Handicap extérieur -1.5",
                   "handicap_2_2": "Handicap extérieur +1.5", "handicap_-2_1": "Handicap domicile +1.5"}
for _cote, _nom in (("home", "domicile"), ("away", "extérieur")):
    for _sens, _v3, _lignes in (("plus", "over", (0.5, 1.5)), ("moins", "under", (0.5, 1.5, 2.5))):
        for _l in _lignes:
            DOUBLE_CONTROLE[f"{_cote}_{_v3}_{str(_l).replace('.', '_')}"] = f"Buts {_nom} - {_sens} de {_l}"


# AJOUT 28/09/2026 (Patrick) -- lignes du « Handicap à 3 choix » BetPawa intégrées à la V3 (handicap du DOMICILE,
# convention BetPawa). Les autres lignes éventuellement cotées (±3…) sont ignorées par choix.
HANDICAP_3_ISSUES_LIGNES = (-2, -1, 1, 2)


def _signe(x):
    """-1 -> « −1 », 1.5 -> « +1,5 »."""
    return ("+" if x > 0 else "−" if x < 0 else "") + _jeton(abs(x)).replace(".", ",")


def _buts(n):
    return f"{n} but{'s' if n > 1 else ''}"


def _ecart_min(m, dom, ext):
    """Condition « buts domicile − buts extérieur ≥ m » en mots."""
    if m >= 1:
        return f"{dom} gagne" + (f" par {_buts(m)} ou plus" if m > 1 else "")
    if m == 0:
        return f"{dom} ne perd pas"
    return f"{dom} ne perd pas par {_buts(1 - m)} ou plus"


def _ecart_max(n, dom, ext):
    """Condition « buts domicile − buts extérieur ≤ n » en mots."""
    if n <= -1:
        return f"{ext} gagne" + (f" par {_buts(-n)} ou plus" if n < -1 else "")
    if n == 0:
        return f"{ext} ne perd pas"
    return f"{ext} ne perd pas par {_buts(n + 1)} ou plus"


def sens_handicap(marche, dom="domicile", ext="extérieur"):
    """Ce que le pari handicap V3 « handicap_{l}_{1|X|2} » demande, en mots (condition buts dom − l ? buts ext)."""
    _, ligne, issue = marche.split("_")
    l_ = float(ligne)
    if issue == "1":
        return _ecart_min(math.floor(l_) + 1, dom, ext)
    if issue == "2":
        return _ecart_max(math.ceil(l_) - 1, dom, ext)
    if l_ == 0:
        return "match nul"
    return f"{dom if l_ > 0 else ext} gagne par exactement {_buts(int(abs(l_)))}"


def libelle_handicap(marche, dom="Domicile", ext="Extérieur"):
    """Libellé BetPawa + sens du pari. Ligne entière = handicap à 3 choix ; demi-ligne = handicap à 2 choix."""
    _, ligne, issue = marche.split("_")
    l_ = float(ligne)
    sens = sens_handicap(marche, dom, ext)
    if l_ == int(l_):
        return f"Handicap 3 choix {dom} {_signe(-l_)} ({issue}) : {sens}"
    if issue == "1":
        return f"Handicap {dom} {_signe(-l_)} : {sens}"
    return f"Handicap {ext} {_signe(l_)} : {sens}"


def libelle(marche):
    """Libellé français d'un marché V3."""
    fixes = {"1x2_1": "Victoire domicile", "1x2_X": "Match nul", "1x2_2": "Victoire extérieur",
             "dc_1X": "Double chance 1X", "dc_X2": "Double chance X2", "dc_12": "Double chance 12",
             "btts_yes": "Les deux équipes marquent", "btts_no": "Les deux équipes ne marquent pas toutes les deux",
             "clean_home": "Domicile n'encaisse pas", "clean_away": "Extérieur n'encaisse pas",
             "exact_goals_6_plus": "6 buts ou plus"}
    if marche in fixes:
        return fixes[marche]
    if marche in ("clean_home_no", "clean_away_no"):
        return f"{'Domicile' if marche == 'clean_home_no' else 'Extérieur'} encaisse au moins un but"
    if marche in ("total_pair", "total_impair"):
        return f"Total de buts {'pair' if marche == 'total_pair' else 'impair'}"
    if marche.startswith("score_"):
        _, h, a = marche.split("_")
        return f"Score exact {h}-{a}"
    if marche.startswith("handicap_"):
        return libelle_handicap(marche)
    for prefixe, qui in (("home_", "Domicile marque "), ("away_", "Extérieur marque ")):
        if marche.startswith(prefixe):
            sens, ligne = marche[len(prefixe):].split("_", 1)
            mot = "but" if float(ligne.replace("_", ".")) < 2 else "buts"
            return f"{qui}{'plus' if sens == 'over' else 'moins'} de {ligne.replace('_', ',')} {mot}"
    if marche.startswith(("over_", "under_")):
        sens, ligne = marche.split("_", 1)
        return f"{'Plus' if sens == 'over' else 'Moins'} de {ligne.replace('_', ',')} buts"
    if marche.startswith("exact_goals_"):
        return f"Exactement {marche.removeprefix('exact_goals_')} buts"
    return marche


def groupe_exposition(marche):
    """Une seule sélection par exposition : résultat, total de buts, BTTS, buts de chaque équipe."""
    if marche.startswith(("1x2_", "dc_", "handicap_")):
        return "resultat"
    if marche.startswith("score_"):
        return "score_exact"
    if marche.startswith("total_"):
        return "parite"
    if marche == "clean_home_no":
        return "buts_exterieur"
    if marche == "clean_away_no":
        return "buts_domicile"
    if marche.startswith(("over_", "under_", "exact_goals_")):
        return "total_buts"
    if marche.startswith("btts_"):
        return "btts"
    if marche.startswith("home_") or marche == "clean_away":
        return "buts_domicile"
    if marche.startswith("away_") or marche == "clean_home":
        return "buts_exterieur"
    return marche


def _vers_double_controle(matchs):
    return [{"date": m["date"], "lieu": "D" if m.get("domicile") else "E", "bm": m["buts_marques"],
             "be": m["buts_encaisses"]} for m in matchs or []]


def preuves(enreg, marches):
    """Double contrôle + justification pour chaque marché coté (la V3 ne sélectionne rien sans eux)."""
    md = _vers_double_controle((enreg.get("equipe_dom") or {}).get("matchs"))
    mx = _vers_double_controle((enreg.get("equipe_ext") or {}).get("matchs"))
    out = {}
    for m in marches:
        g = groupe_exposition(m)
        bloc = {"family": g, "exposure_group": g, "double_control_ok": False, "justification": None}
        nom = DOUBLE_CONTROLE.get(m)
        if nom:
            r = rs.double_controle(nom, md, mx, enreg.get("domicile") or "Domicile", enreg.get("exterieur") or "Extérieur")
            bloc["double_control_ok"] = bool(r["retenu"])
            raisons = list(r["saison"]["raisons"]) + list(r["recent"]["raisons"])
            bloc["justification"] = " ; ".join(raisons) if r["retenu"] else None
            bloc["double_controle_raisons"] = raisons
            bloc["raisons_saison"] = list(r["saison"]["raisons"])
            bloc["raisons_recent"] = list(r["recent"]["raisons"])
        out[m] = bloc
    return out


def _cote_ok(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v > 1


def _ligne(texte):
    try:
        return float(texte)
    except (TypeError, ValueError):
        return None


def _jeton(x):
    return f"{float(x):g}"


def cotes_etendues(enreg):
    """AJOUT 28/09/2026 (Patrick : « intégrer le calcul de tous les marchés ») -- marchés cotés par BetPawa que le
    registre du banc ne lit pas : handicaps, score exact, pair/impair, total 6,5 / 7,5, buts d'une équipe 2,5 / 3,5,
    « encaisse au moins un but ». Noms V3. Aucune cote inventée : seules les cotes > 1 relevées sont gardées.

    Handicap BetPawa « handicap_L » : issue « domicile » = domicile avec L (gagne si buts_dom + L > buts_ext), issue
    « exterieur » = l'autre côté (buts_dom + L < buts_ext). Vérifié le 28/09 sur l'archive : handicap -0,5 domicile
    ~ cote 1X2 « 1 », +0,5 domicile ~ double chance 1X. La V3 écrit la condition « buts_dom - ligne > buts_ext » : la
    ligne V3 vaut donc -L (handicap_{-L}_1 et handicap_{-L}_2)."""
    bp = enreg.get("cotes_betpawa") or {}
    ob = enreg.get("cotes_observees") or {}
    out = {}

    def met(nom, v):
        if nom not in out and _cote_ok(v):
            out[nom] = float(v)

    for groupe, issues in bp.items():
        if not isinstance(issues, dict):
            continue
        if groupe.startswith("handicap_3issues_"):
            # Handicap à 3 choix, ligne L du DOMICILE : « 1 » = buts_dom + L > buts_ext -> V3 handicap_{-L}_1, etc.
            L = _ligne(groupe[len("handicap_3issues_"):])
            if L is not None and L in HANDICAP_3_ISSUES_LIGNES:
                for issue in ("1", "X", "2"):
                    met(f"handicap_{_jeton(-L)}_{issue}", issues.get(issue))
        elif groupe.startswith("handicap_") and not groupe.startswith("handicap_3choix"):
            L = _ligne(groupe[len("handicap_"):])
            if L is not None and L != int(L):
                met(f"handicap_{_jeton(-L)}_1", issues.get("domicile"))
                met(f"handicap_{_jeton(-L)}_2", issues.get("exterieur"))
        elif groupe == "score_exact":
            for score, v in issues.items():
                parts = str(score).split("-")
                if len(parts) == 2 and all(x.isdigit() for x in parts):
                    met(f"score_{int(parts[0])}_{int(parts[1])}", v)
        elif groupe == "pair_impair":
            met("total_pair", issues.get("pair"))
            met("total_impair", issues.get("impair"))
        elif groupe.startswith("over_under_"):
            reste = groupe[len("over_under_"):]
            for prefixe, cible in (("domicile_", "home_"), ("exterieur_", "away_"), ("", "")):
                if reste.startswith(prefixe) and _ligne(reste[len(prefixe):]) is not None:
                    jeton = reste[len(prefixe):].replace(".", "_")
                    met(f"{cible}over_{jeton}", issues.get("plus"))
                    met(f"{cible}under_{jeton}", issues.get("moins"))
                    break
        elif groupe == "cages_inviolees_domicile":
            met("clean_home_no", issues.get("non"))
        elif groupe == "cages_inviolees_exterieur":
            met("clean_away_no", issues.get("non"))
    # Cotes observées en complément (même règle : BetPawa d'abord).
    for nom, v in ob.items():
        if nom.startswith("Handicap "):
            morceaux = nom[len("Handicap "):].split(" - ")
            L = _ligne(morceaux[0]) if len(morceaux) == 2 else None
            if L is not None and L != int(L):
                met(f"handicap_{_jeton(-L)}_{'1' if morceaux[1] == 'Domicile' else '2'}", v)
        elif nom == "Total buts - pair":
            met("total_pair", v)
        elif nom == "Total buts - impair":
            met("total_impair", v)
        elif nom == "Encaisse au moins 1 but - Domicile":
            met("clean_home_no", v)
        elif nom == "Encaisse au moins 1 but - Extérieur":
            met("clean_away_no", v)
        elif nom.startswith(("Plus de ", "Moins de ")):
            sens = "over" if nom.startswith("Plus") else "under"
            corps = nom.split(" de ", 1)[1]
            ligne, _, qui = corps.partition(" buts")
            cible = {"": "", " - Domicile": "home_", " - Extérieur": "away_"}.get(qui)
            if cible is not None and _ligne(ligne) is not None:
                met(f"{cible}{sens}_{ligne.replace('.', '_')}", v)
    return out


def cotes_v3(enreg):
    cotes = {BANC_VERS_V3[k]: v for k, v in bh.cotes_archive(enreg).items() if k in BANC_VERS_V3}
    for k, v in cotes_etendues(enreg).items():
        cotes.setdefault(k, v)
    return cotes


GROUPES_BETPAWA_LUS = ("1x2", "double_chance", "btts", "cages_inviolees_domicile", "cages_inviolees_exterieur",
                       "nombre_exact_buts", "score_exact", "pair_impair")


def couverture(enreg, cotes):
    """Diagnostic : issues cotées par BetPawa, marchés que la V3 a réellement calculés, groupes qu'elle ne sait pas lire."""
    bp = enreg.get("cotes_betpawa") or {}
    ignores = sorted(g for g in bp if g.startswith("handicap_3issues_")
                     and _ligne(g[len("handicap_3issues_"):]) not in HANDICAP_3_ISSUES_LIGNES)
    non_lus = sorted(g for g in bp if g not in ignores and not (
        g in GROUPES_BETPAWA_LUS or g.startswith("over_under_") or g.startswith("handicap_3issues_")
        or (g.startswith("handicap_") and not g.startswith("handicap_3choix")
            and _ligne(g[len("handicap_"):]) is not None and _ligne(g[len("handicap_"):]) % 1 != 0)))
    return {"issues_betpawa": sum(len(v) for v in bp.values() if isinstance(v, dict)),
            "marches_cotes_calcules": len(cotes), "groupes_non_lus": non_lus,
            "groupes_ignores_par_choix": ignores}


def lignes_handicap(cotes):
    """Lignes de handicap (convention V3) présentes dans les cotes du match."""
    return sorted({float(k.split("_")[1]) for k in cotes if k.startswith("handicap_")})


def entree_v3(enreg):
    """Dictionnaire d'entrée de evaluate_match. Volontairement SANS le nom de la compétition."""
    cotes = cotes_v3(enreg)
    return {"home_matches": (enreg.get("equipe_dom") or {}).get("matchs") or [],
            "away_matches": (enreg.get("equipe_ext") or {}).get("matchs") or [],
            "odds": cotes, "handicap_lines": lignes_handicap(cotes)}


def lit_archive(dossier=DOSSIER_ARCHIVE):
    enregs = []
    for chemin in sorted(glob.glob(os.path.join(dossier, "*.json.gz"))):
        with gzip.open(chemin, "rt", encoding="utf-8") as f:
            enregs.extend(json.load(f).values())
    return enregs


def _score(enreg):
    sc = enreg.get("score") or {}
    h, a = sc.get("buts_dom"), sc.get("buts_ext")
    return (h, a) if isinstance(h, int) and isinstance(a, int) else None


def _signature_evenement_calibration(marche, max_buts=20):
    """Signature déterministe de l'événement FT pour éviter de compter deux fois le même pari.
    
    Exemple : un handicap 3 choix « issue 1 » peut être exactement le même événement
    qu'un handicap 2 choix à -1,5. Les deux marchés restent disponibles à la sélection,
    mais une seule observation alimente la calibration.
    """
    vrai = []
    for h in range(max_buts + 1):
        for a in range(max_buts + 1):
            if gagne(marche, h, a) is True:
                vrai.append((h, a))
    return tuple(vrai)


def entraine_calibration(enregs, avant_le):
    """Calibration isotone sur les matchs de l'archive JOUÉS avant `avant_le` (date AAAA-MM-JJ) : probabilité brute V3
    de chaque marché coté contre son résultat réel. Renvoie (calibrateur, nb_matchs)."""
    ps, ys, matchs = [], [], 0
    for e in enregs:
        sc = _score(e)
        if sc is None or str(e.get("date")) >= avant_le:
            continue
        entree = entree_v3(e)
        try:
            probas = derive_markets(build_model(entree["home_matches"], entree["away_matches"]),
                                    entree["handicap_lines"])
        except ValueError:
            continue
        cotes = entree["odds"]
        vu = False
        signatures_vues = set()
        for m, p in probas.items():
            issue = gagne(m, *sc)            # Tous les marchés FT cotés, pas seulement le banc.
            if m not in cotes or issue is None or not (0 < p < 1):
                continue
            signature = _signature_evenement_calibration(m)
            if not signature or signature in signatures_vues:
                continue
            signatures_vues.add(signature)
            ps.append(p)
            ys.append(1 if issue else 0)
            vu = True
        matchs += vu
    cal = IsotonicCalibrator()
    cal.fit(ps, ys)
    if cal.fit_result.ready and matchs < MIN_MATCHS_CALIBRATION:
        cal.fit_result = CalibrationFit(False, cal.fit_result.observations, "MATCHS_INSUFFISANTS", ())
    return cal, matchs


def a_venir(enreg, maintenant):
    if _score(enreg) is not None:
        return False
    ko = enreg.get("coup_d_envoi_utc")
    if ko:
        try:
            return datetime.datetime.strptime(ko, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc) > maintenant
        except ValueError:
            pass
    return str(enreg.get("date")) >= maintenant.strftime("%Y-%m-%d")


def evalue_enregistrement(enreg, calibrateur):
    """Un match : sélections V3 + meilleurs candidats écartés (avec raisons). Ne lève jamais : l'erreur est rendue."""
    base = {"match_id": enreg.get("match_id"), "date": enreg.get("date"), "heure": enreg.get("heure_cameroun"),
            "competition": enreg.get("competition"), "domicile": enreg.get("domicile"),
            "exterieur": enreg.get("exterieur")}
    entree = entree_v3(enreg)
    if not entree["odds"]:
        return {**base, "statut": "SANS_COTE", "selections": [], "candidats": []}
    cover = couverture(enreg, entree["odds"])
    evidence = preuves(enreg, entree["odds"])
    try:
        r = evaluate_match(entree, calibrator=calibrateur, evidence=evidence)
    except ValueError as e:
        return {**base, "statut": f"NON_EVALUE : {e}", "selections": [], "candidats": []}
    m = r["model"]
    rejets = dict(r["rejected"])
    candidats = []
    for c in sorted(r["candidates"], key=lambda c: c["edv"], reverse=True):
        v = r["values"][c["market"]]
        candidats.append({"marche": c["market"], "libelle": libelle(c["market"]), "cote": c["odds"],
                          "probabilite_brute": v.probability_raw, "probabilite": c["probability"],
                          "calibree": c["calibrated"], "edv": round(c["edv"], 1),
                          "raisons": sorted(set(v.reasons) | set(rejets.get(c["market"], ())))})
    def _format(liste):
        return [{"marche": s.market, "libelle": libelle(s.market), "cote": s.odds,
                 "probabilite": round(s.probability, 4), "edge": s.edge, "edv": round(s.edv, 1),
                 "justification": s.reason,
                 "raisons_saison": evidence.get(s.market, {}).get("raisons_saison", []),
                 "raisons_recent": evidence.get(s.market, {}).get("raisons_recent", [])}
                for s in liste]
    ctx = {"enreg": enreg, "entree": entree, "r": r, "evidence": evidence, "candidats": candidats,
           "calibree": calibrateur is not None and calibrateur.fit_result.ready}
    selections = [{**s_, "explication": explication(s_, ctx, apercu=False)}
                  for s_ in (_avec_indice(x, ctx) for x in _format(r["selected"]))]
    # APERÇU NON CALIBRÉ (décision de Patrick du 28/09 : voir les matchs pendant l'expérimentation). Tant que la
    # calibration n'est pas prête, on rejoue la décision V3 en ignorant SEULEMENT le verrou « calibration absente » :
    # tous les autres contrôles (value, double contrôle, justification, échantillon, dispersion, exposition) restent.
    # Ce ne sont PAS des sélections : la page les affiche comme « aperçu non calibré ».
    apercu = []
    if not selections and (calibrateur is None or not calibrateur.fit_result.ready):
        apercu = [{**s_, "explication": explication(s_, ctx, apercu=True)}
                  for s_ in (_avec_indice(x, ctx) for x in _format(decide([{**c, "calibrated": True} for c in r["candidates"]])[0]))]
    alternatives = alternatives_indice(candidats, selections or apercu, ctx, (base.get("domicile"), base.get("exterieur")))
    return {**base, "statut": "EVALUE", "lambda_dom": round(m.lambda_home, 3), "lambda_ext": round(m.lambda_away, 3),
            "n_dom": m.home_sample.current_n, "n_ext": m.away_sample.current_n, "couverture": cover,
            "selections": selections, "apercu_non_calibre": apercu, "alternatives_indice": alternatives,
            "candidats": candidats[:5],
            "tous_les_candidats": candidats}


# ---------------------------------------------------------------------------------------------------------------------
# STANDARD DE JUSTIFICATION V3 (validé par Patrick le 28/09/2026, docs/V3_PRIORITES_ET_JUSTIFICATION.md §3)
# Résumé d'une ligne + alertes + 6 blocs toujours dans le même ordre : Données, Buts attendus, Probabilité,
# Face à la cote, Contrôles, Pourquoi ce marché. Tout est calculé ici ; le site ne fait qu'afficher.
# ---------------------------------------------------------------------------------------------------------------------
RAISONS_FR = {
    "CALIBRATION_ABSENTE": "calibration pas encore prête",
    "VALUE_NON_ELIGIBLE": "pas de value exploitable",
    "DOUBLE_CONTROLE_ECHOUE_OU_ABSENT": "double contrôle non passé ou marché non couvert",
    "JUSTIFICATION_INSUFFISANTE": "pas de justification",
    "COTE_HORS_FENETRE": "cote hors de 1,26 – 1,74",
    "PROBABILITE_INF_60": "probabilité sous 60 %",
    "EDV_INSUFFISANTE": "marge insuffisante",
    "N_LIEU_INF_3": "moins de 3 matchs au même lieu",
    "N_3_4_CONTROLE_STRICT_NON_SATISFAIT": "3 ou 4 matchs au même lieu : contrôle renforcé non passé",
    "SURDISPERSION_SUP_1_50": "résultats trop irréguliers (dispersion > 1,50)",
    "SURDISPERSION_1_20_1_50_ET_P_INF_67": "résultats irréguliers et probabilité sous 67 %",
    "DISPERSION_INSUFFISANTE": "dispersion non mesurable",
    "PROBABILITE_DEGENEREE": "probabilité 0 % ou 100 %",
}
FAMILLES_FR = {"resultat": "résultat", "total_buts": "total de buts", "btts": "les deux marquent",
               "buts_domicile": "buts du domicile", "buts_exterieur": "buts de l'extérieur",
               "score_exact": "score exact", "parite": "pair / impair"}


def _n2(x):
    return f"{x:.2f}".replace(".", ",")


def _p1(x):
    return f"{100 * x:.1f} %".replace(".", ",")


def phrase_calcul(marche):
    """Bloc 3 : comment la probabilité est obtenue à partir du tableau des scores, selon la famille du marché."""
    if marche.startswith(("1x2_", "dc_")):
        cond = {"1x2_1": "domicile > extérieur", "1x2_X": "domicile = extérieur", "1x2_2": "extérieur > domicile",
                "dc_1X": "domicile ≥ extérieur", "dc_X2": "extérieur ≥ domicile", "dc_12": "domicile ≠ extérieur"}[marche]
        return f"Somme des scores où {cond}."
    if marche.startswith("handicap_"):
        _, ligne, cote_ = marche.split("_")
        l_ = float(ligne)
        if cote_ == "1":
            return f"Somme des scores où buts domicile {'−' if l_ > 0 else '+'} {_jeton(abs(l_)).replace('.', ',')} > buts extérieur."
        if cote_ == "X":
            return f"Somme des scores où buts domicile {'−' if l_ > 0 else '+'} {_jeton(abs(l_)).replace('.', ',')} = buts extérieur."
        return f"Somme des scores où buts extérieur {'+' if l_ > 0 else '−'} {_jeton(abs(l_)).replace('.', ',')} > buts domicile."
    if marche.startswith(("over_", "under_")):
        sens, ligne = marche.split("_", 1)
        n = int(float(ligne.replace("_", ".")) + 0.5)
        return (f"Somme des scores avec au moins {n} buts." if sens == "over"
                else f"Somme des scores avec au plus {n - 1} but{'s' if n - 1 > 1 else ''}.")
    if marche.startswith("exact_goals_") or marche.startswith("total_"):
        return "Somme des scores dont le total de buts correspond."
    if marche.startswith(("home_", "away_")):
        qui = "le domicile" if marche.startswith("home_") else "l'extérieur"
        sens, ligne = marche.split("_", 2)[1:]
        n = int(float(ligne.replace("_", ".")) + 0.5)
        return (f"Probabilité que {qui} marque au moins {n} but{'s' if n > 1 else ''}, avec ses seuls buts attendus."
                if sens == "over" else
                f"Probabilité que {qui} marque au plus {n - 1} but{'s' if n - 1 > 1 else ''}, avec ses seuls buts attendus.")
    if marche.startswith("btts_"):
        return ("Probabilité que chaque équipe marque au moins un but." if marche == "btts_yes"
                else "Probabilité qu'au moins une des deux équipes ne marque pas.")
    if marche.startswith("clean_"):
        qui = "l'extérieur" if marche.startswith("clean_home") else "le domicile"
        return f"Probabilité que {qui} {'marque' if marche.endswith('_no') else 'ne marque pas'}."
    if marche.startswith("score_"):
        _, h, a = marche.split("_")
        return f"Probabilité du score {h}-{a} : P(domicile marque {h}) × P(extérieur marque {a})."
    return "Somme des scores concernés."


def alertes(p, cote, n_min, lambdas, dispersion, apercu):
    out = []
    if apercu:
        out.append("Aperçu non calibré : ce n'est pas une sélection du moteur.")
    if n_min < 5:
        out.append(f"Petit échantillon : {n_min} matchs au même lieu pour l'équipe la moins fournie.")
    ecart = p - 1 / cote
    if abs(ecart) > 0.12:
        out.append(f"Écart inhabituel avec le marché : {'+' if ecart > 0 else '−'}{_p1(abs(ecart)).replace(' %', '')} points.")
    total = sum(lambdas)
    if total < 1.8 or total > 4.0:
        out.append(f"Buts attendus extrêmes : {_n2(total)} buts au total.")
    if dispersion is not None and 1.20 < dispersion <= 1.50:
        out.append(f"Résultats irréguliers : dispersion {_n2(dispersion)}.")
    return out


def explication(sel, ctx, apercu):
    """Justification standard d'une sélection (ou d'un aperçu) : alertes + 6 blocs chiffrés."""
    e, entree, r = ctx["enreg"], ctx["entree"], ctx["r"]
    model = r["model"]
    dom, ext = e.get("domicile") or "Domicile", e.get("exterieur") or "Extérieur"
    H, A = _latest(entree["home_matches"], True), _latest(entree["away_matches"], False)
    sh, sa = _strength(H), _strength(A)
    nh, na = len(H), len(A)
    att_d, def_e = _lisse(sh["attack"], nh), _lisse(sa["defense"], na)
    att_e, def_d = _lisse(sa["attack"], na), _lisse(sh["defense"], nh)
    lh, la = model.lambda_home, model.lambda_away
    scores = lambda L: ", ".join(f"{m['buts_marques']}-{m['buts_encaisses']}" for m in L)
    p, cote, marche = sel["probabilite"], sel["cote"], sel["marche"]
    impl = 1 / cote
    seuil = edv_threshold(p)
    disp = goal_context_dispersion(list(entree["home_matches"]) + list(entree["away_matches"]))
    n_min = min(nh, na)
    top = sorted(((model.score[h][a], h, a) for h in range(len(model.score)) for a in range(len(model.score))),
                 reverse=True)[:2]
    ev = ctx["evidence"].get(marche, {})
    regle = DOUBLE_CONTROLE.get(marche)

    blocs = [
        {"titre": "Données", "lignes": [
            f"{dom} à domicile ({nh}) : {scores(H)} → marque {_n2(sh['gf'])}, encaisse {_n2(sh['ga'])} par match.",
            f"{ext} à l'extérieur ({na}) : {scores(A)} → marque {_n2(sa['gf'])}, encaisse {_n2(sa['ga'])} par match."]},
        {"titre": "Buts attendus", "lignes": [
            f"Lissage vers {_n2(MOYENNE_REFERENCE)} but : (n × moyenne + {K_LISSAGE:g} × {_n2(MOYENNE_REFERENCE)}) / (n + {K_LISSAGE:g}).",
            f"{dom} : attaque {_n2(sh['attack'])} → {_n2(att_d)} ; défense {ext} {_n2(sa['defense'])} → {_n2(def_e)} ; "
            f"{_n2(att_d)} × {_n2(def_e)} / {_n2(MOYENNE_REFERENCE)} = {_n2(lh)} buts.",
            f"{ext} : attaque {_n2(sa['attack'])} → {_n2(att_e)} ; défense {dom} {_n2(sh['defense'])} → {_n2(def_d)} ; "
            f"{_n2(att_e)} × {_n2(def_d)} / {_n2(MOYENNE_REFERENCE)} = {_n2(la)} buts."]},
        {"titre": "Probabilité", "lignes": [
            f"{libelle(marche)} : {_p1(p)}{' (non calibrée)' if apercu else ''}.",
            phrase_calcul(marche),
            "Scores les plus probables : " + ", ".join(f"{h}-{a} ({_p1(q)})" for q, h, a in top) + "."]},
        {"titre": "Face à la cote", "lignes": [
            f"Cote {_n2(cote)} → {_p1(impl)} selon le bookmaker ; écart {'+' if p >= impl else '−'}"
            f"{_p1(abs(p - impl)).replace(' %', '')} points.",
            f"Marge = {_n2(cote)} × {f'{p - impl:.3f}'.replace('.', ',')} = {'+' if sel['edv'] >= 0 else ''}{str(sel['edv']).replace('.', ',')} %"
            + (f" (seuil {seuil:g} % à cette probabilité)." if seuil is not None else ".")]},
        {"titre": "Contrôles", "lignes": [
            f"Cote dans la fenêtre {_n2(ODDS_MIN)} – {_n2(ODDS_MAX)} : oui.",
            f"Dispersion des buts : {_n2(disp) if disp is not None else 'non mesurable'}"
            + (" (acceptée car probabilité ≥ 67 %)." if disp is not None and disp > 1.20 else " (accepté)."),
            f"Double contrôle « {regle} » passé : " + " ; ".join(x.lstrip("✓ ") for x in ev.get("double_controle_raisons", [])) + "."
            if regle else "Double contrôle : marché non couvert.",
            (f"{n_min} matchs au même lieu : contrôle renforcé passé (probabilité ≥ 67 % et marge ≥ 7 %)."
             if n_min < 5 else f"{n_min} matchs au même lieu : échantillon suffisant."),
            "Calibration : pas encore prête (aperçu)." if apercu else "Calibration : prête."]},
        {"titre": "Pourquoi ce marché", "lignes": alternatives(sel, ctx, apercu)},
    ]
    # AJOUT 10/10/2026 (Patrick) : 7e bloc, indice de performance du marché (information seulement).
    perf = sel["indice_performance"] if "indice_performance" in sel else indice_performance(marche, H, A)
    if perf:
        blocs.append({"titre": "Indice de performance", "lignes": lignes_indice_performance(perf, dom, ext)})
    return {"alertes": alertes(p, cote, n_min, (lh, la), disp, apercu), "blocs": blocs}


def _marge_signee(x):
    return f"{'+' if x >= 0 else '−'}{_n2(abs(x))}"


def lignes_indice_performance(perf, dom, ext):
    """Bloc 7 : indice de performance du marché = nombre de scénarios (moyen / pire des équipes concernées) qui le
    valident. Marché d'une seule équipe : 2 scénarios ; sinon 4. Détail : buts de chaque équipe, marge sur la ligne."""
    n, sur = perf["indice"], perf["sur"]
    md, me, pd, pe = perf["moyenne_domicile"], perf["moyenne_exterieur"], perf["pire_domicile"], perf["pire_exterieur"]
    lignes = [(f"Indice {n}/{sur} : {perf['libelle']}. Le marché est validé dans {n} scénario{'s' if n > 1 else ''} sur {sur}."
               if sur != 2 else f"Indice : {perf['libelle']}. {perf['phrase']}")]
    if sur == 2:
        lignes.append("Ce marché ne dépend que d'une équipe : 2 scénarios (moyen et pire de cette équipe), l'autre équipe n'entre pas.")
    if pd:
        lignes.append(f"{dom} à domicile : moyenne simple {_n2(md['marque'])} marqué(s) par match ; pire match {pd['marque']:g}-{pd['encaisse']:g}.")
    if pe:
        lignes.append(f"{ext} à l'extérieur : moyenne simple {_n2(me['marque'])} marqué(s) par match ; pire match {pe['marque']:g}-{pe['encaisse']:g}.")
    lignes.append("Buts d'un scénario = ce que chaque équipe marque dans son profil (moyen ou pire) ; les buts encaissés ne comptent pas.")
    for s in perf["scenarios"]:
        morceaux, total = [], 0.0
        if s["domicile"]:
            morceaux.append(f"{dom} {s['domicile']} : {_n2(s['buts_domicile'])}")
            total += s["buts_domicile"]
        if s["exterieur"]:
            morceaux.append(f"{ext} {s['exterieur']} : {_n2(s['buts_exterieur'])}")
            total += s["buts_exterieur"]
        suffixe = f" (total {_n2(total)})" if len(morceaux) == 2 else ""
        lignes.append(" / ".join(morceaux) + f"{suffixe} → marge {_marge_signee(s['marge'])} but : "
                      f"{'validé' if s['valide'] else 'non validé'}.")
    lignes.append("Échelle (4 scénarios) : 4/4 Sûr · 3/4 Recommandé · 2/4 Attention · 1/4 Risqué. Marché d'une seule équipe : "
                  "Sûr si tout tient, Attention si seulement la moyenne tient. Information seulement : "
                  "elle ne change ni la probabilité ni la sélection.")
    return lignes


def indice_pour(sel, ctx):
    """Indice de performance d'une sélection, sur les mêmes matchs au même lieu que sa justification."""
    entree = ctx["entree"]
    return indice_performance(sel["marche"], _latest(entree["home_matches"], True), _latest(entree["away_matches"], False))


def _avec_indice(sel, ctx):
    return {**sel, "indice_performance": indice_pour(sel, ctx)}


def alternatives_indice(candidats, retenus, ctx, equipes, max_alt=3):
    """Marchés valides mais écartés (dominés ou trop liés), avec leur indice de performance. Information seulement :
    ne change jamais la sélection. Au plus `max_alt`, les plus probables d'abord, au format d'un candidat du site."""
    pris = {x["marche"] for x in retenus}
    sortie = []
    for c in sorted(candidats, key=lambda c: c["probabilite"], reverse=True):
        if c["marche"] in pris or any(r_ != "CALIBRATION_ABSENTE" for r_ in c["raisons"]):
            continue
        perf = indice_pour(c, ctx)
        if perf is None:
            continue
        sortie.append({"marche": nom_site(c["marche"]), "marche_moteur": c["marche"],
                       "libelle": (libelle_handicap(c["marche"], *(equipes[0] or "Domicile", equipes[1] or "Extérieur"))
                                   if c["marche"].startswith("handicap_") else None),
                       "cote": c["cote"], "probabilite": c["probabilite"], "indice_performance": perf})
        if len(sortie) >= max_alt:
            break
    return sortie


def alternatives(sel, ctx, apercu):
    """Bloc 6 : famille du pari retenu + meilleurs paris des autres familles avec la raison exacte de leur rejet."""
    groupe = groupe_exposition(sel["marche"])
    lignes = [f"Un seul pari par famille ({FAMILLES_FR.get(groupe, groupe)}) : celui-ci est le plus probable des paris valides."]
    vus = {groupe}
    for c in ctx["candidats"]:
        g = groupe_exposition(c["marche"])
        if g in vus or c["marche"] == sel["marche"]:
            continue
        vus.add(g)
        raisons = [x for x in c["raisons"] if not (apercu and x == "CALIBRATION_ABSENTE")]
        motif = ("valide, mais moins bon que le pari retenu ou trop lié à lui" if not raisons
                 else " ; ".join(RAISONS_FR.get(x, x) for x in raisons[:2]))
        lignes.append(f"{c['libelle']} ({_n2(c['cote'])}, {_p1(c['probabilite'])}, marge "
                      f"{'+' if c['edv'] >= 0 else ''}{str(c['edv']).replace('.', ',')} %) : {motif}.")
        if len(lignes) >= 4:
            break
    return lignes


# Noms de marchés V3 -> noms lus par traduction_marches.js (ceux de la page « Sélections Archetype »).
V3_VERS_SITE = {"1x2_1": "1x2_domicile", "1x2_X": "1x2_nul", "1x2_2": "1x2_exterieur",
                "dc_1X": "double_chance_1X", "dc_X2": "double_chance_X2", "dc_12": "double_chance_12",
                "btts_yes": "btts_oui", "btts_no": "btts_non",
                "clean_home": "cage_inviolee_domicile", "clean_away": "cage_inviolee_exterieur"}
for _x in range(8):
    for _s in ("over", "under"):
        V3_VERS_SITE[f"{_s}_{_x}_5"] = f"over_under_total_{_x}.5_{_s}"
V3_VERS_SITE.update({"clean_home_no": "encaisse_domicile", "clean_away_no": "encaisse_exterieur"})
for _x in range(4):
    for _s in ("over", "under"):
        V3_VERS_SITE[f"home_{_s}_{_x}_5"] = f"buts_equipe_domicile_{_x}.5_{_s}"
        V3_VERS_SITE[f"away_{_s}_{_x}_5"] = f"buts_equipe_exterieur_{_x}.5_{_s}"


def nom_site(marche):
    """Nom lu par traduction_marches.js. Handicap V3 « handicap_{l}_1 » (buts_dom - l > buts_ext) = domicile avec
    handicap -l ; « handicap_{l}_2 » = extérieur avec handicap +l."""
    if marche.startswith("handicap_"):
        _, ligne, cote_ = marche.split("_")
        l_ = float(ligne)
        if l_ == int(l_):  # handicap à 3 choix : nom propre à la V3, libellé fourni par le champ « libelle »
            return f"handicap3_domicile_{_jeton(-l_)}_{cote_}"
        if cote_ == "1":
            return f"handicap_domicile_{_jeton(-l_)}"
        if cote_ == "2":
            return f"handicap_exterieur_{_jeton(l_)}"
    return V3_VERS_SITE.get(marche, marche)


VIGILANCE_V3 = "Moteur V3 en production parallèle : candidat, non promu comme moteur principal."


def niveau_echantillon(n_min):
    """Fiabilité affichée = taille de l'échantillon au même lieu de l'équipe la moins fournie (paliers de
    moteur_v3.model._sample). La V3 ne sélectionne jamais sous 3 matchs."""
    if n_min < 5:
        return "V3_ECHANTILLON_FAIBLE"
    if n_min < 8:
        return "V3_ECHANTILLON_UTILISABLE"
    if n_min < 10:
        return "V3_ECHANTILLON_SOLIDE"
    return "V3_ECHANTILLON_TRES_SOLIDE"


def _pct_fr(x):
    return f"{100 * x:.0f} %"


def synthese(sel, n_min=None, apercu=False):
    """Résumé d'une ligne (standard de justification du 28/09) : probabilité contre cote, marge, échantillon."""
    texte = (f"Probabilité {'NON calibrée' if apercu else 'calibrée'} {_pct_fr(sel['probabilite'])} contre "
             f"{_pct_fr(1 / sel['cote'])} selon la cote {sel['cote']:.2f}".replace(".", ",")
             + f" · marge {'+' if sel['edv'] >= 0 else ''}{sel['edv']:.1f} %".replace(".", ","))
    if n_min is not None:
        texte += f" · {n_min} matchs au même lieu"
    return texte + "."


VIGILANCE_APERCU = ("Aperçu NON calibré : la calibration n'a pas encore assez de matchs joués. Ce n'est pas une "
                    "sélection du moteur, seulement ce qu'il retiendrait si la calibration confirmait ses probabilités.")


def candidat_site(sel, rang, n_min, lambdas=None, apercu=False, equipes=None, alternatives_indice=None):
    """Une sélection V3 au format d'un candidat de la page « Sélections Archetype » (moteur_v2_6_9.selection.Px)."""
    preuves = []
    if sel["raisons_saison"]:
        preuves.append({"type": "v3_controle_saison", "texte": " ; ".join(r.lstrip("✓ ") for r in sel["raisons_saison"])})
    if sel["raisons_recent"]:
        preuves.append({"type": "v3_forme_recente", "texte": " ; ".join(r.lstrip("✓ ") for r in sel["raisons_recent"])})
    preuves.append({"type": "ev_percentage", "valeur": sel["edv"],
                    "texte": f"Le prix proposé laisse {sel['edv']:.1f}".replace(".", ",") + " % de marge par rapport à "
                             f"l'estimation {'NON calibrée' if apercu else 'calibrée'}."})
    vigilance = ([VIGILANCE_APERCU] if apercu else []) + [VIGILANCE_V3] + (
        ["Moins de 5 matchs au même lieu pour une des deux équipes."] if n_min < 5 else [])
    # Handicaps : libellé complet (ligne BetPawa + sens du pari) ; les autres marchés gardent traduction_marches.js.
    libelle_site = (libelle_handicap(sel["marche"], *(equipes or ("Domicile", "Extérieur")))
                    if sel["marche"].startswith("handicap_") else None)
    return {"marche": nom_site(sel["marche"]), "marche_moteur": sel["marche"], "libelle": libelle_site,
            "probabilite": sel["probabilite"], "cote": sel["cote"], "edge": sel["edge"], "edv": sel["edv"] / 100.0,
            "niveau": niveau_echantillon(n_min), "robustesse": None, "points_de_vigilance": vigilance, "rang": rang,
            "apercu_non_calibre": apercu, "indice_performance": sel.get("indice_performance"),
            "alternatives_indice": alternatives_indice or [],
            "justification": {"resume": synthese(sel, n_min, apercu), "preuves": preuves,
                              "explication": sel.get("explication"),
                              "donnees_suffisantes": True, "bibliotheque": {"ev_percentage": sel["edv"]}}}


def signal_site(x):
    """Un match au format d'un signal de precalcul_leger.json, avec le seul bloc moteur_v3."""
    n_min = min(x.get("n_dom") or 0, x.get("n_ext") or 0)
    rangs = ("P1", "P2", "P3")
    lambdas = (x.get("lambda_dom"), x.get("lambda_ext"))
    apercu = not x["selections"] and bool(x.get("apercu_non_calibre"))
    source = x["selections"] or x.get("apercu_non_calibre") or []
    equipes = (x.get("domicile") or "Domicile", x.get("exterieur") or "Extérieur")
    selection = {rang: candidat_site(s, rang, n_min, lambdas, apercu, equipes, x.get("alternatives_indice")) for rang, s in zip(rangs, source)}
    return {"match_id": x["match_id"], "date": x["date"], "heure_cameroun": x["heure"], "competition": x["competition"],
            "domicile": x["domicile"], "exterieur": x["exterieur"], "moteur_utilise": "moteur_v3",
            "moteur_v3": {"statut": "OK" if x["statut"] == "EVALUE" else x["statut"], "moteur": "moteur_v3",
                          "statut_global": STATUT, "apercu_non_calibre": apercu, "selection": selection}}


def empreinte_code(racine=None):
    """Empreinte (12 caractères) du code qui a calculé les pronostics V3 : moteur, branchement, double contrôle, banc.
    Même code = même empreinte ; une seule ligne changée = empreinte différente."""
    racine = racine or os.path.dirname(os.path.abspath(__file__))
    h = hashlib.sha256()
    for motif in FICHIERS_CODE_V3:
        for chemin in sorted(glob.glob(os.path.join(racine, motif))):
            h.update(os.path.relpath(chemin, racine).replace(os.sep, "/").encode("utf-8") + b"\0")
            with open(chemin, "rb") as f:
                h.update(f.read() + b"\0")
    return h.hexdigest()[:12]


def _ligne_diag(c):
    """Une ligne compacte du diagnostic complet : [marché, cote, probabilité, marge %, raisons de rejet]."""
    return [c["marche"], c["cote"], round(c["probabilite"], 4), c["edv"], c["raisons"]]


def journalise(matchs, calibration, maintenant, empreinte, commit=None, dossier=DOSSIER_JOURNAL, diagnostics=None):
    """Écrit le calcul V3 de chaque match À VENIR dans le journal de sa date (remplace le calcul précédent du même
    match). Les matchs déjà commencés ne sont pas dans `matchs` : leur entrée reste figée. Renvoie le nombre écrit."""
    calcule_le = maintenant.strftime("%Y-%m-%dT%H:%M:%SZ")
    par_date = {}
    for x in matchs:
        if x.get("match_id") and x.get("date"):
            par_date.setdefault(str(x["date"]), []).append(x)
    ecrits = 0
    for date_match, liste in sorted(par_date.items()):
        chemin = os.path.join(dossier, f"{date_match}.json")
        donnees = {}
        if os.path.exists(chemin):
            with open(chemin, encoding="utf-8") as f:
                donnees = json.load(f)
        for x in liste:
            ancien = donnees.get(x["match_id"]) or {}
            donnees[x["match_id"]] = {
                **{k: v for k, v in x.items() if k != "tous_les_candidats"},
                "premier_calcul_le": ancien.get("premier_calcul_le") or calcule_le,
                "calcule_le": calcule_le, "nb_calculs": int(ancien.get("nb_calculs") or 0) + 1,
                "empreinte_code_v3": empreinte, "commit": commit,
                "calibration": {k: calibration[k] for k in ("prete", "observations", "matchs")},
                "statut_v3": STATUT,
                # AJOUT 28/09 : diagnostic de TOUS les marchés cotés (pas seulement les 5 meilleurs candidats).
                "tous_les_marches": [_ligne_diag(c) for c in (diagnostics or {}).get(x["match_id"], [])]}
            ecrits += 1
        os.makedirs(dossier, exist_ok=True)
        with open(chemin, "w", encoding="utf-8") as f:      # une ligne par match : compact et lisible dans git
            f.write("{\n" + ",\n".join(f"{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}"
                                        for k, v in sorted(donnees.items())) + "\n}\n")
    return ecrits


def execution(dossier=DOSSIER_ARCHIVE, fichier_sortie=FICHIER_SORTIE, maintenant=None, dossier_journal=None):
    maintenant = maintenant or datetime.datetime.now(datetime.timezone.utc)
    enregs = lit_archive(dossier)
    calibrateur, matchs_calib = entraine_calibration(enregs, maintenant.strftime("%Y-%m-%d"))
    fit = calibrateur.fit_result
    matchs = [evalue_enregistrement(e, calibrateur) for e in enregs if a_venir(e, maintenant)]
    matchs.sort(key=lambda x: (str(x["date"]), str(x["heure"] or ""), str(x["domicile"])))
    raisons = Counter(r for x in matchs for c in x.get("tous_les_candidats", []) for r in c["raisons"])
    statuts = Counter(x["statut"] if not x["statut"].startswith("NON_EVALUE") else "NON_EVALUE" for x in matchs)
    diagnostics = {x["match_id"]: x.pop("tous_les_candidats", []) for x in matchs}
    non_lus = Counter(g for x in matchs for g in (x.get("couverture") or {}).get("groupes_non_lus", []))
    empreinte = empreinte_code()
    commit = (os.environ.get("GITHUB_SHA") or "")[:7] or None
    sortie = {
        "moteur": "moteur_v3", "statut": STATUT, "genere_le": maintenant.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "empreinte_code_v3": empreinte, "commit": commit,
        "calibration": {"prete": fit.ready, "observations": fit.observations, "matchs": matchs_calib,
                        "minimum_observations": calibrateur.minimum_observations,
                        "minimum_matchs": MIN_MATCHS_CALIBRATION, "raison": fit.reason},
        "bilan": {"matchs": len(matchs), "statuts": dict(statuts),
                  "selections": sum(len(x["selections"]) for x in matchs),
                  "matchs_avec_selection": sum(1 for x in matchs if x["selections"]),
                  "matchs_en_apercu_non_calibre": sum(1 for x in matchs if x.get("apercu_non_calibre")),
                  "raisons_de_rejet": dict(raisons.most_common()),
                  "couverture": {"marches_cotes_calcules": sum((x.get("couverture") or {}).get(
                                     "marches_cotes_calcules", 0) for x in matchs),
                                 "issues_betpawa": sum((x.get("couverture") or {}).get("issues_betpawa", 0)
                                                       for x in matchs),
                                 "groupes_betpawa_non_lus": dict(non_lus.most_common())}},
        "matchs": matchs,
        "signaux": [signal_site(x) for x in matchs],
    }
    os.makedirs(os.path.dirname(fichier_sortie), exist_ok=True)
    with open(fichier_sortie, "w", encoding="utf-8") as f:
        json.dump(sortie, f, ensure_ascii=False, indent=1)
    if dossier_journal is None:
        dossier_journal = os.path.join(os.path.dirname(fichier_sortie), "journal")
    journal = journalise(matchs, sortie["calibration"], maintenant, empreinte, commit, dossier_journal, diagnostics)
    return sortie["bilan"] | {"calibration": sortie["calibration"], "journal_ecrits": journal,
                              "empreinte_code_v3": empreinte}


if __name__ == "__main__":
    print(json.dumps(execution(), ensure_ascii=False, indent=1))
    sys.exit(0)
