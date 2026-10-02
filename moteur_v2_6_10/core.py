# -*- coding: utf-8 -*-
"""moteur_v2_6_10 — le moteur v2.6.9 corrigé de ses points faibles mesurés, avec la même ossature.

Ce qui NE change PAS (tout vient de `moteur_v2_6_9`, importé tel quel, jamais copié) :
    validations V1-V12, Poisson, marchés, value (edge, EV, seuils), statuts, artefacts R1-R3, catégories A-D,
    désignations, verdict, schéma du résultat. La sélection P1 / P2 / P3 (`branchement_moteur.selectionne`) lit
    toujours `inventaire` de la même façon : P1 = probabilité maximale, P2 = meilleur EV restant, P3 = coup de poker.

Ce qui change :
    1. LISSAGE des moyennes de buts avant le calcul, avec une référence propre à chaque rôle (domicile / extérieur).
    2. CALIBRATION isotone optionnelle. Un calibrateur n'est appliqué que s'il a été appris pour CE modèle (signature) et
       sur des matchs ANTÉRIEURS au match analysé. Les probabilités calibrées sont rendues cohérentes (`harmonise`) puis
       edge / EV / statut / catégorie / désignations / verdict sont recalculés avec les fonctions du moteur de base.
    3. ALERTES : écart inhabituel avec le marché, buts attendus extrêmes, calibration absente ou ignorée. Sans effet sur
       la sélection.
    4. L'avertissement R5 (profil attaque/défense asymétrique) reste évalué sur les moyennes BRUTES : le lissage ne le
       masque pas.

Champs ajoutés au résultat : `moteur`, `version_moteur`, `modele`, `lissage`, `calibration`, `alertes`, et par marché
`proba_brute` (probabilité avant calibration) et `alertes`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import moteur_v2_6_9 as base

from .calibration import CalibrateurIsotone
from .coherence import harmonise
from .lissage import PARAMETRES_PAR_DEFAUT, ParametresLissage, lisser_match
from .risque import alertes_ligne, alertes_match

NOM_MOTEUR = "moteur_v2_6_10"
VERSION_MOTEUR = "2.6.10"
AVERTISSEMENT_R5 = "Profil attaque/défense très asymétrique"


def signature_modele(lisser: bool = True, params: ParametresLissage = PARAMETRES_PAR_DEFAUT) -> str:
    """Identifie le modèle qui produit les probabilités brutes. À passer à `calibration.apprendre(modele=...)` : un
    calibrateur n'est appliqué que si sa signature est celle du modèle courant."""
    return f"{NOM_MOTEUR}|{params.signature() if lisser else 'sans_lissage'}"


def _realigne_r5(res: Dict[str, Any], trace: Optional[Dict[str, Any]]) -> None:
    """R5 de la v2.6.9 est calculé sur les moyennes brutes ; le moteur de base ne voit ici que des moyennes lissées, qui
    gomment les profils asymétriques. On recalcule R5 sur les valeurs brutes (même fonction, mêmes seuils) et on remet
    l'avertissement à sa place habituelle (juste après R4) pour que l'affichage ne change pas."""
    if not trace or not trace.get("dom") or not trace.get("ext"):
        return
    d, e = trace["dom"], trace["ext"]
    brut = base.biais_asymetrique([(d["attaque_brute"], d["defense_brute"]), (e["attaque_brute"], e["defense_brute"])])
    avertissements = [a for a in res["avertissements_match"] if a != AVERTISSEMENT_R5]
    if brut:
        apres_r4 = [i for i, a in enumerate(avertissements) if a.startswith("Fenêtre d'analyse")]
        avertissements.insert(apres_r4[0] + 1 if apres_r4 else 0, AVERTISSEMENT_R5)
    res["biais_attaque_defense"] = brut
    res["avertissements_match"] = avertissements


def _etat_calibrateur(calibrateur: Optional[CalibrateurIsotone], modele: str, date_run: str) -> Dict[str, Any]:
    """Décide si le calibrateur peut être appliqué à CE match. Retourne le bloc `calibration` du résultat (+ clé `actif`)."""
    if calibrateur is None:
        return {"statut": "NON_CALIBRE", "raison": None, "actif": False}
    if not calibrateur.pret:
        return {"statut": "NON_CALIBRE", "raison": "calibrateur non entraîné", "actif": False}
    if calibrateur.modele != modele:
        return {"statut": "IGNORE_MODELE_DIFFERENT", "actif": False,
                "raison": f"appris pour « {calibrateur.modele or 'modèle inconnu'} », modèle courant « {modele} »"}
    if date_run and calibrateur.date_max and calibrateur.date_max >= date_run:
        return {"statut": "IGNORE_ANACHRONIQUE", "actif": False,
                "raison": f"appris jusqu'au {calibrateur.date_max}, match du {date_run} : pas antérieur"}
    return {"statut": "CALIBRE", "raison": None if date_run else "date du run inconnue : antériorité non vérifiée", "actif": True}


def _probabilites_calibrees(res: Dict[str, Any], calibrateur: CalibrateurIsotone) -> Dict[str, float]:
    calibrees: Dict[str, float] = {}
    for l in res["inventaire"]:
        if l["marche"].startswith("handicap_") and l.get("push", 0.0) > 0 and base.HANDICAP_ENTIER_REMBOURSE:
            continue    # push remboursé : la probabilité de gain seule n'est pas l'événement que le calibrateur a appris
        calibrees[l["marche"]] = calibrateur.predire(l["proba_modele"])
    return harmonise(calibrees, base.GROUPES)


def _reevalue(res: Dict[str, Any], calibrateur: CalibrateurIsotone) -> None:
    """Recalcule le bloc « value » de `res` avec les probabilités calibrées et cohérentes, en réutilisant les fonctions du
    moteur de base (mêmes seuils, mêmes statuts, mêmes catégories). Modifie `res` en place."""
    calibrees = _probabilites_calibrees(res, calibrateur)
    lignes: List[Dict[str, Any]] = []
    for ancienne in res["inventaire"]:
        marche, cote = ancienne["marche"], ancienne["cote"]
        p_brut = ancienne["proba_modele"]
        push = ancienne.get("push", 0.0)
        # Retrouve la probabilité de base du marché (avant retrait du push), comme analyser_match l'avait posée.
        rembourse = base.HANDICAP_ENTIER_REMBOURSE if marche.startswith("handicap_") else True
        p_base = ancienne["p_juste"] / (1.0 - push) if (rembourse and 0 < push < 1) else ancienne["p_juste"]
        nouvelle = base.evaluer_ligne(marche, calibrees.get(marche, p_brut), cote, p_base, push, remboursement_push=rembourse)
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
                   calibrateur: Optional[CalibrateurIsotone] = None, lisser: bool = True,
                   lissage_params: ParametresLissage = PARAMETRES_PAR_DEFAUT) -> Dict[str, Any]:
    """Même contrat que `moteur_v2_6_9.analyser_match` (le résultat est un sur-ensemble du sien).

    calibrateur    : calibrateur appris pour ce modèle (`signature_modele`) sur des matchs antérieurs au match analysé ;
                     sinon il est ignoré et `calibration.statut` le dit.
    lisser         : False pour retrouver exactement les moyennes brutes de la v2.6.9 (comparaison, diagnostic).
    lissage_params : paramètres du lissage (sensibilité) ; la signature du modèle en dépend.
    """
    modele = signature_modele(lisser, lissage_params)
    if lisser:
        match_utilise, trace = lisser_match(match, lissage_params)
    else:
        match_utilise, trace = match, None
    res = base.analyser_match(match_utilise, date_run, maintenant)
    etat = _etat_calibrateur(calibrateur, modele, date_run)
    actif = etat.pop("actif")
    res["moteur"], res["version_moteur"], res["modele"] = NOM_MOTEUR, VERSION_MOTEUR, modele
    res["lissage"] = trace
    res["calibration"] = dict(etat, n_observations=calibrateur.n_observations if actif else 0,
                              n_matchs=calibrateur.n_matchs if actif else 0)
    res["alertes"] = []
    if res["statut_global"] == "SKIP":
        return res
    _realigne_r5(res, trace)
    if actif:
        _reevalue(res, calibrateur)
    for l in res["inventaire"]:
        l.setdefault("proba_brute", l["proba_modele"])
        l["alertes"] = alertes_ligne(l)
    res["alertes"] = alertes_match(res, etat["statut"], etat.get("raison"))
    return res
