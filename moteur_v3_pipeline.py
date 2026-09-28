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
  4. Évalue chaque match à venir avec moteur_v3.evaluate_match et écrit data/v3/pronostics_v3.json (lu par
     pronostics_v3.html) : sélections, meilleurs candidats écartés avec la raison exacte, et un bilan chiffré de ce
     qui bloque. data/ est commité par le workflow à chaque run.

Le nom de la compétition n'est JAMAIS transmis au moteur (règle « aucune discrimination par division »).

Utilisation à la main :  python moteur_v3_pipeline.py
"""
from __future__ import annotations

import datetime
import glob
import gzip
import json
import os
import sys
from collections import Counter

import banc_historique as bh
import regles_selection as rs
from moteur_v3 import evaluate_match
from moteur_v3.calibration import IsotonicCalibrator
from moteur_v3.markets import derive_markets
from moteur_v3.model import build_model

DOSSIER_ARCHIVE = os.path.join("data", "archive_test")
FICHIER_SORTIE = os.path.join("data", "v3", "pronostics_v3.json")
STATUT = "EXPÉRIMENTAL — NON VALIDÉ"

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
    if marche.startswith(("1x2_", "dc_")):
        return "resultat"
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
        out[m] = bloc
    return out


def cotes_v3(enreg):
    return {BANC_VERS_V3[k]: v for k, v in bh.cotes_archive(enreg).items() if k in BANC_VERS_V3}


def entree_v3(enreg):
    """Dictionnaire d'entrée de evaluate_match. Volontairement SANS le nom de la compétition."""
    return {"home_matches": (enreg.get("equipe_dom") or {}).get("matchs") or [],
            "away_matches": (enreg.get("equipe_ext") or {}).get("matchs") or [],
            "odds": cotes_v3(enreg)}


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
        try:
            probas = derive_markets(build_model(entree_v3(e)["home_matches"], entree_v3(e)["away_matches"]))
        except ValueError:
            continue
        cotes = cotes_v3(e)
        vu = False
        for m, p in probas.items():
            if m in cotes and m in V3_VERS_BANC and 0 < p < 1:
                ps.append(p)
                ys.append(1 if bh.gagne(V3_VERS_BANC[m], *sc) else 0)
                vu = True
        matchs += vu
    cal = IsotonicCalibrator()
    cal.fit(ps, ys)
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
    try:
        r = evaluate_match(entree, calibrator=calibrateur, evidence=preuves(enreg, entree["odds"]))
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
    selections = [{"marche": s.market, "libelle": libelle(s.market), "cote": s.odds,
                   "probabilite": round(s.probability, 4), "edv": round(s.edv, 1), "justification": s.reason}
                  for s in r["selected"]]
    return {**base, "statut": "EVALUE", "lambda_dom": round(m.lambda_home, 3), "lambda_ext": round(m.lambda_away, 3),
            "n_dom": m.home_sample.current_n, "n_ext": m.away_sample.current_n,
            "selections": selections, "candidats": candidats[:5], "tous_les_candidats": candidats}


def execution(dossier=DOSSIER_ARCHIVE, fichier_sortie=FICHIER_SORTIE, maintenant=None):
    maintenant = maintenant or datetime.datetime.now(datetime.timezone.utc)
    enregs = lit_archive(dossier)
    calibrateur, matchs_calib = entraine_calibration(enregs, maintenant.strftime("%Y-%m-%d"))
    fit = calibrateur.fit_result
    matchs = [evalue_enregistrement(e, calibrateur) for e in enregs if a_venir(e, maintenant)]
    matchs.sort(key=lambda x: (str(x["date"]), str(x["heure"] or ""), str(x["domicile"])))
    raisons = Counter(r for x in matchs for c in x.get("tous_les_candidats", []) for r in c["raisons"])
    statuts = Counter(x["statut"] if not x["statut"].startswith("NON_EVALUE") else "NON_EVALUE" for x in matchs)
    for x in matchs:
        x.pop("tous_les_candidats", None)
    sortie = {
        "moteur": "moteur_v3", "statut": STATUT, "genere_le": maintenant.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "calibration": {"prete": fit.ready, "observations": fit.observations, "matchs": matchs_calib,
                        "minimum_observations": calibrateur.minimum_observations, "raison": fit.reason},
        "bilan": {"matchs": len(matchs), "statuts": dict(statuts),
                  "selections": sum(len(x["selections"]) for x in matchs),
                  "matchs_avec_selection": sum(1 for x in matchs if x["selections"]),
                  "raisons_de_rejet": dict(raisons.most_common())},
        "matchs": matchs,
    }
    os.makedirs(os.path.dirname(fichier_sortie), exist_ok=True)
    with open(fichier_sortie, "w", encoding="utf-8") as f:
        json.dump(sortie, f, ensure_ascii=False, indent=1)
    return sortie["bilan"] | {"calibration": sortie["calibration"]}


if __name__ == "__main__":
    print(json.dumps(execution(), ensure_ascii=False, indent=1))
    sys.exit(0)
