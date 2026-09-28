#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
moteur_v3_pipeline.py -- BRANCHEMENT DU MOTEUR V3 EN PARALLÈLE (décision de Patrick du 27/09/2026 : « branche-moi la V3,
je lance le run manuellement »).

Statut : EXPÉRIMENTAL, NON VALIDÉ. La V3 tourne À CÔTÉ de moteur_v2_6_9 : elle ne remplace rien sur le site, ne modifie
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
import os
import sys
from collections import Counter

import banc_historique as bh
import regles_selection as rs
from moteur_v3 import evaluate_match
from moteur_v3.calibration import CalibrationFit, IsotonicCalibrator
from moteur_v3.decision import decide
from moteur_v3.markets import derive_markets, gagne
from moteur_v3.model import build_model

DOSSIER_ARCHIVE = os.path.join("data", "archive_test")
FICHIER_SORTIE = os.path.join("data", "v3", "pronostics_v3.json")
STATUT = "EXPÉRIMENTAL — NON VALIDÉ"
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
                   "over_2_5": "Plus de 2.5 buts", "over_3_5": "Plus de 3.5 buts", "btts_yes": "BTTS - oui"}


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
        _, ligne, cote_ = marche.split("_")
        l_ = float(ligne)
        if cote_ == "1":
            return f"Domicile handicap {_jeton(-l_).replace('.', ',')}"
        if cote_ == "2":
            return f"Extérieur handicap {('+' if l_ > 0 else '') + _jeton(l_).replace('.', ',')}"
        return f"Handicap {ligne} nul"
    for prefixe, qui in (("home_", "Domicile marque "), ("away_", "Extérieur marque ")):
        if marche.startswith(prefixe):
            sens, ligne = marche[len(prefixe):].split("_", 1)
            return f"{qui}{'plus' if sens == 'over' else 'moins'} de {ligne.replace('_', ',')} but"
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
        if groupe.startswith("handicap_") and not groupe.startswith("handicap_3choix"):
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
    non_lus = sorted(g for g in bp if not (
        g in GROUPES_BETPAWA_LUS or g.startswith("over_under_")
        or (g.startswith("handicap_") and not g.startswith("handicap_3choix")
            and _ligne(g[len("handicap_"):]) is not None and _ligne(g[len("handicap_"):]) % 1 != 0)))
    return {"issues_betpawa": sum(len(v) for v in bp.values() if isinstance(v, dict)),
            "marches_cotes_calcules": len(cotes), "groupes_non_lus": non_lus}


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
        for m, p in probas.items():
            issue = gagne(m, *sc)            # AJOUT 28/09 : tous les marchés plein temps cotés, pas seulement le banc
            if m in cotes and issue is not None and 0 < p < 1:
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
    selections = _format(r["selected"])
    # APERÇU NON CALIBRÉ (décision de Patrick du 28/09 : voir les matchs pendant l'expérimentation). Tant que la
    # calibration n'est pas prête, on rejoue la décision V3 en ignorant SEULEMENT le verrou « calibration absente » :
    # tous les autres contrôles (value, double contrôle, justification, échantillon, dispersion, exposition) restent.
    # Ce ne sont PAS des sélections : la page les affiche comme « aperçu non calibré ».
    apercu = []
    if not selections and (calibrateur is None or not calibrateur.fit_result.ready):
        apercu = _format(decide([{**c, "calibrated": True} for c in r["candidates"]])[0])
    return {**base, "statut": "EVALUE", "lambda_dom": round(m.lambda_home, 3), "lambda_ext": round(m.lambda_away, 3),
            "n_dom": m.home_sample.current_n, "n_ext": m.away_sample.current_n, "couverture": cover,
            "selections": selections, "apercu_non_calibre": apercu, "candidats": candidats[:5],
            "tous_les_candidats": candidats}


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
        if cote_ == "1":
            return f"handicap_domicile_{_jeton(-l_)}"
        if cote_ == "2":
            return f"handicap_exterieur_{_jeton(l_)}"
    return V3_VERS_SITE.get(marche, marche)


VIGILANCE_V3 = "Moteur V3 expérimental : pas encore validé sur 100 matchs réels."


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


def synthese(sel, lambdas=None, apercu=False):
    """Résumé propre à la V3 (jamais une copie d'une preuve) : probabilité calibrée contre celle de la cote, double
    contrôle, et buts attendus du modèle V3 lui-même (différents des « buts attendus » simples de la règle du double
    contrôle, qui n'est qu'un filtre)."""
    texte = (f"Probabilité {'NON calibrée' if apercu else 'calibrée'} {_pct_fr(sel['probabilite'])} contre {_pct_fr(1 / sel['cote'])} selon la cote ; "
             f"double contrôle passé (saison et forme récente)")
    if lambdas and None not in lambdas:
        texte += f" ; buts attendus par la V3 : {lambdas[0]:.2f} – {lambdas[1]:.2f}".replace(".", ",")
    return texte + "."


VIGILANCE_APERCU = ("Aperçu NON calibré : la calibration n'a pas encore assez de matchs joués. Ce n'est pas une "
                    "sélection du moteur, seulement ce qu'il retiendrait si la calibration confirmait ses probabilités.")


def candidat_site(sel, rang, n_min, lambdas=None, apercu=False):
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
    return {"marche": nom_site(sel["marche"]), "marche_moteur": sel["marche"],
            "probabilite": sel["probabilite"], "cote": sel["cote"], "edge": sel["edge"], "edv": sel["edv"] / 100.0,
            "niveau": niveau_echantillon(n_min), "robustesse": None, "points_de_vigilance": vigilance, "rang": rang,
            "apercu_non_calibre": apercu,
            "justification": {"resume": synthese(sel, lambdas, apercu), "preuves": preuves,
                              "donnees_suffisantes": True, "bibliotheque": {"ev_percentage": sel["edv"]}}}


def signal_site(x):
    """Un match au format d'un signal de precalcul_leger.json, avec le seul bloc moteur_v3."""
    n_min = min(x.get("n_dom") or 0, x.get("n_ext") or 0)
    rangs = ("P1", "P2", "P3")
    lambdas = (x.get("lambda_dom"), x.get("lambda_ext"))
    apercu = not x["selections"] and bool(x.get("apercu_non_calibre"))
    source = x["selections"] or x.get("apercu_non_calibre") or []
    selection = {rang: candidat_site(s, rang, n_min, lambdas, apercu) for rang, s in zip(rangs, source)}
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
