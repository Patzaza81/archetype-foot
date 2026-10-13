"""Carnet des paris v2r : un pari par match, écrit AVANT le coup d'envoi, figé ensuite ; seul le score est ajouté,
une fois. C'est le seul chiffre de rentabilité qui compte (paris réellement faits à l'avance)."""
import datetime
import json
import os

import journal_rentabilite as J

from . import evaluation as E

SEUIL_PARIS = 300


def _parse(ts):
    return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None


def avant_coup_d_envoi(pick, maintenant):
    ko = _parse(pick.get("coup_d_envoi_utc"))
    return ko is not None and maintenant < ko


def enregistre(carnet, pick, maintenant):
    """carnet: {match_id: ligne}. Écrit/met à jour tant que le coup d'envoi n'est pas passé. Retourne True si écrit."""
    if pick is None or not avant_coup_d_envoi(pick, maintenant):
        return False
    ancien = carnet.get(pick["match_id"])
    if ancien and ancien.get("fige"):
        return False
    ligne = dict(pick)
    ligne.update(vu_le=maintenant.isoformat(), fige=False, score=None, resultat=None, profit=None)
    carnet[pick["match_id"]] = ligne
    return True


def fige(carnet, maintenant):
    for l in carnet.values():
        if not l["fige"] and not avant_coup_d_envoi(l, maintenant):
            l["fige"] = True


def regle(carnet, scores):
    """scores: {match_id: (h, a)}. Ajoute le résultat une seule fois à une ligne figée. Retourne le nombre réglé."""
    n = 0
    for mid, l in carnet.items():
        if l["resultat"] is not None or not l["fige"] or mid not in scores:
            continue
        h, a = scores[mid]
        an = J.analyse_libelle(l["marche"])
        r = an[1](h, a) if an else None
        if r is None:
            continue
        l["score"] = [h, a]
        l["resultat"] = "WIN" if r == 1 else ("PUSH" if r == 0 else "LOSS")
        l["profit"] = (l["cote"] - 1) if r == 1 else (0.0 if r == 0 else -1.0)
        n += 1
    return n


def bilan(carnet):
    S = [dict(mid=l["match_id"], profit=l["profit"]) for l in carnet.values() if l["resultat"] is not None]
    n = len(S)
    wins = sum(1 for l in carnet.values() if l["resultat"] == "WIN")
    roi = E.roi(S)
    ic = E.bootstrap(S, n=1000) if n >= 30 else None
    return dict(regles=n, gagnes=wins, reussite=round(wins / n, 4) if n else None,
                roi=round(roi, 4) if roi is not None else None,
                ic95=[round(ic[0], 4), round(ic[1], 4)] if ic else None, statut=statut(n, ic))


def statut(n, ic):
    """observation : < SEUIL_PARIS réglés (ne pas miser) ; actif : borne basse IC95 > 0 ; non_rentable sinon."""
    if n < SEUIL_PARIS or ic is None:
        return "observation"
    return "actif" if ic[0] > 0 else "non_rentable"


def charge(dossier):
    p = os.path.join(dossier, "carnet.json")
    return json.load(open(p)) if os.path.exists(p) else {}


def sauve(carnet, dossier):
    os.makedirs(dossier, exist_ok=True)
    json.dump(carnet, open(os.path.join(dossier, "carnet.json"), "w"), ensure_ascii=False, indent=1, sort_keys=True)
