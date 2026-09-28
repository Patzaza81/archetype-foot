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
from moteur_v3.calibration import IsotonicCalibrator
from moteur_v3.decision import decide
from moteur_v3.markets import derive_markets
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
            bloc["raisons_saison"] = list(r["saison"]["raisons"])
            bloc["raisons_recent"] = list(r["recent"]["raisons"])
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
            "n_dom": m.home_sample.current_n, "n_ext": m.away_sample.current_n,
            "selections": selections, "apercu_non_calibre": apercu, "candidats": candidats[:5],
            "tous_les_candidats": candidats}


# Noms de marchés V3 -> noms lus par traduction_marches.js (ceux de la page « Sélections Archetype »).
V3_VERS_SITE = {"1x2_1": "1x2_domicile", "1x2_X": "1x2_nul", "1x2_2": "1x2_exterieur",
                "dc_1X": "double_chance_1X", "dc_X2": "double_chance_X2", "dc_12": "double_chance_12",
                "btts_yes": "btts_oui", "btts_no": "btts_non",
                "clean_home": "cage_inviolee_domicile", "clean_away": "cage_inviolee_exterieur"}
for _x in range(6):
    for _s in ("over", "under"):
        V3_VERS_SITE[f"{_s}_{_x}_5"] = f"over_under_total_{_x}.5_{_s}"
for _x in range(2):
    for _s in ("over", "under"):
        V3_VERS_SITE[f"home_{_s}_{_x}_5"] = f"buts_equipe_domicile_{_x}.5_{_s}"
        V3_VERS_SITE[f"away_{_s}_{_x}_5"] = f"buts_equipe_exterieur_{_x}.5_{_s}"

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
    return {"marche": V3_VERS_SITE.get(sel["marche"], sel["marche"]), "marche_moteur": sel["marche"],
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


def journalise(matchs, calibration, maintenant, empreinte, commit=None, dossier=DOSSIER_JOURNAL):
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
                "statut_v3": STATUT}
            ecrits += 1
        os.makedirs(dossier, exist_ok=True)
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(dict(sorted(donnees.items())), f, ensure_ascii=False, indent=1)
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
    for x in matchs:
        x.pop("tous_les_candidats", None)
    empreinte = empreinte_code()
    commit = (os.environ.get("GITHUB_SHA") or "")[:7] or None
    sortie = {
        "moteur": "moteur_v3", "statut": STATUT, "genere_le": maintenant.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "empreinte_code_v3": empreinte, "commit": commit,
        "calibration": {"prete": fit.ready, "observations": fit.observations, "matchs": matchs_calib,
                        "minimum_observations": calibrateur.minimum_observations, "raison": fit.reason},
        "bilan": {"matchs": len(matchs), "statuts": dict(statuts),
                  "selections": sum(len(x["selections"]) for x in matchs),
                  "matchs_avec_selection": sum(1 for x in matchs if x["selections"]),
                  "matchs_en_apercu_non_calibre": sum(1 for x in matchs if x.get("apercu_non_calibre")),
                  "raisons_de_rejet": dict(raisons.most_common())},
        "matchs": matchs,
        "signaux": [signal_site(x) for x in matchs],
    }
    os.makedirs(os.path.dirname(fichier_sortie), exist_ok=True)
    with open(fichier_sortie, "w", encoding="utf-8") as f:
        json.dump(sortie, f, ensure_ascii=False, indent=1)
    if dossier_journal is None:
        dossier_journal = os.path.join(os.path.dirname(fichier_sortie), "journal")
    journal = journalise(matchs, sortie["calibration"], maintenant, empreinte, commit, dossier_journal)
    return sortie["bilan"] | {"calibration": sortie["calibration"], "journal_ecrits": journal,
                              "empreinte_code_v3": empreinte}


if __name__ == "__main__":
    print(json.dumps(execution(), ensure_ascii=False, indent=1))
    sys.exit(0)
