# -*- coding: utf-8 -*-
"""moteur_v2_6_10 — le moteur v2.6.9 corrigé de ses points faibles mesurés, avec la même ossature.

Ce qui NE change PAS (tout vient de `moteur_v2_6_9`, importé tel quel, jamais copié) :
    validations V1-V12, Poisson, marchés, value (edge, EV, seuils), statuts, artefacts R1-R3, catégories A-D,
    désignations, verdict, schéma du résultat. La sélection P1 / P2 / P3 (`branchement_moteur.selectionne`) lit
    toujours `inventaire` de la même façon : P1 = probabilité maximale, P2 = meilleur EV restant, P3 = coup de poker.

Ce qui change :
    1. LISSAGE des moyennes de buts avant le calcul (moteur_v2_6_10.lissage) : corrige la surconfiance des petits
       échantillons. Paramètres fixés à l'avance.
    2. CALIBRATION isotone optionnelle (moteur_v2_6_10.calibration) : si un calibrateur appris sur des matchs déjà joués
       est fourni, les probabilités sont calibrées puis edge / EV / statut / catégorie / désignations / verdict sont
       recalculés avec les fonctions du moteur de base. Sans calibrateur : le moteur le dit (`calibration.statut`).
    3. ALERTES (moteur_v2_6_10.risque) : écart inhabituel avec le marché, buts attendus extrêmes, calibration absente.
       Elles n'influencent pas la sélection.

Champs ajoutés au résultat : `moteur`, `version_moteur`, `lissage`, `calibration`, `alertes`, et par marché
`proba_brute` (probabilité avant calibration) et `alertes`. Les probabilités calibrées de marchés complémentaires
(over / under, oui / non, 1X2) ne somment pas exactement à 1 : chaque marché est calibré séparément.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import moteur_v2_6_9 as base

from .calibration import CalibrateurIsotone
from .lissage import lisser_match
from .risque import alertes_ligne, alertes_match

NOM_MOTEUR = "moteur_v2_6_10"
VERSION_MOTEUR = "2.6.10"


def _reevalue(res: Dict[str, Any], calibrateur: CalibrateurIsotone) -> None:
    """Recalcule le bloc « value » de `res` avec les probabilités calibrées, en réutilisant les fonctions du moteur de
    base (mêmes seuils, mêmes statuts, mêmes catégories). Modifie `res` en place."""
    lignes: List[Dict[str, Any]] = []
    for ancienne in res["inventaire"]:
        marche, cote = ancienne["marche"], ancienne["cote"]
        p_brut = ancienne["proba_modele"]
        push = ancienne.get("push", 0.0)
        # Retrouve la probabilité de base du marché (avant retrait du push), comme analyser_match l'avait posée.
        rembourse = base.HANDICAP_ENTIER_REMBOURSE if marche.startswith("handicap_") else True
        p_base = ancienne["p_juste"] / (1.0 - push) if (rembourse and 0 < push < 1) else ancienne["p_juste"]
        nouvelle = base.evaluer_ligne(marche, calibrateur.predire(p_brut), cote, p_base, push, remboursement_push=rembourse)
        nouvelle["proba_brute"] = p_brut
        if marche in ("victoire", "defaite"):
            nouvelle["statut"] = base.statut_1x2(nouvelle["proba_modele"], cote, nouvelle["is_value"])
        else:
            nouvelle["statut"] = base.statut_autres(nouvelle["proba_modele"], cote, nouvelle["is_value"])
        lignes.append(nouvelle)
    for l in lignes:
        if l["is_value"]:
            l["artefacts"] = list(res["artefacts_match"]) + base.artefacts_marche(l)
            l["categorie"] = base.categorie_value(l["ev"], l["proba_modele"], len(l["artefacts"]))
    lignes.sort(key=base._cle_tri)
    base.attribuer_designations(lignes)
    statut_global, texte, principal = base.construire_verdict(lignes, res["lambda_dom"], res["lambda_ext"])
    res["inventaire"] = lignes
    res["statut_global"], res["verdict"], res["ecrasant_principal"] = statut_global, texte, principal
    # `coherence_marche` reste calculée sur les probabilités brutes : elle mesure le pricing du modèle, pas celui du calibrateur.


def analyser_match(match: Dict[str, Any], date_run: str = "", maintenant: Optional[datetime] = None, *,
                   calibrateur: Optional[CalibrateurIsotone] = None, lisser: bool = True) -> Dict[str, Any]:
    """Même contrat que `moteur_v2_6_9.analyser_match` (le résultat est un sur-ensemble du sien).

    calibrateur : calibrateur isotone appris UNIQUEMENT sur des matchs joués avant ce match (voir calibration.apprendre).
    lisser      : False pour retrouver exactement les moyennes brutes de la v2.6.9 (comparaison, diagnostic).
    """
    if lisser:
        match_utilise, trace = lisser_match(match)
    else:
        match_utilise, trace = match, None
    res = base.analyser_match(match_utilise, date_run, maintenant)
    pret = calibrateur is not None and calibrateur.pret
    res["moteur"], res["version_moteur"] = NOM_MOTEUR, VERSION_MOTEUR
    res["lissage"] = trace
    res["calibration"] = {"statut": "CALIBRE" if pret else "NON_CALIBRE",
                          "n_observations": calibrateur.n_observations if pret else 0,
                          "n_matchs": calibrateur.n_matchs if pret else 0}
    res["alertes"] = []
    if res["statut_global"] == "SKIP":
        return res
    if pret:
        _reevalue(res, calibrateur)
    for l in res["inventaire"]:
        l.setdefault("proba_brute", l["proba_modele"])
        l["alertes"] = alertes_ligne(l)
    res["alertes"] = alertes_match(res, pret)
    return res
