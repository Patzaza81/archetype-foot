"""Carnet des pronostics v : un pronostic (principal + autres) par match, écrit AVANT le coup d'envoi, figé ensuite ; seul le score
est ajouté, une fois. Chaque pari (principal et autres) est réglé séparément. Un match sans coup d'envoi connu n'est jamais écrit
(garde contre les cotes prises en cours de jeu)."""
import datetime
import json
import math
import os

from .marches import gagne

SEUIL_PARIS = 100          # paris réglés minimum pour juger un niveau
SEUIL_GEL = 0.10           # réussite réelle < fiabilité annoncée - 10 points (sur >= 50 paris) -> GEL
MIN_GEL = 50


def _parse(ts):
    return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None


def avant_coup_d_envoi(ligne, maintenant):
    ko = _parse(ligne.get("coup_d_envoi_utc"))
    return ko is not None and maintenant < ko


def enregistre(carnet, ligne, maintenant):
    """Écrit/met à jour tant que le coup d'envoi n'est pas passé et que la ligne n'est pas figée. Retourne True si écrit."""
    if ligne is None or not avant_coup_d_envoi(ligne, maintenant):
        return False
    ancien = carnet.get(ligne["match_id"])
    if ancien and ancien.get("fige"):
        return False
    l = dict(ligne)
    l.update(vu_le=maintenant.isoformat(), fige=False, score=None, resultat=None, profit=None)
    carnet[ligne["match_id"]] = l
    return True


def retire(carnet, match_id):
    """Retire un pronostic encore modifiable (non figé, non réglé) devenu sans pronostic fiable. Retourne True si retiré."""
    l = carnet.get(match_id)
    if l is None or l["fige"] or l["resultat"] is not None:
        return False
    del carnet[match_id]
    return True


def fige(carnet, maintenant):
    for l in carnet.values():
        if not l["fige"] and not avant_coup_d_envoi(l, maintenant):
            l["fige"] = True


def _regle_pari(p, h, a):
    r = gagne(p["marche"], h, a)
    if r is None:
        return False
    p["resultat"] = "WIN" if r else "LOSS"
    p["profit"] = (p["cote"] - 1) if r else -1.0
    return True


def regle(carnet, scores):
    """scores: {match_id: (h, a)}. Règle une seule fois une ligne figée (principal + autres). Retourne le nombre de lignes réglées."""
    n = 0
    for mid, l in carnet.items():
        if l["resultat"] is not None or not l["fige"] or mid not in scores:
            continue
        h, a = scores[mid]
        if not _regle_pari(l["principal"], h, a):
            continue
        for p in l["autres"]:
            _regle_pari(p, h, a)
        l.update(score=[h, a], resultat=l["principal"]["resultat"], profit=l["principal"]["profit"])
        n += 1
    return n


def wilson(w, n, z=1.96):
    if n == 0:
        return None
    p = w / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    e = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - e), 4), round(min(1.0, c + e), 4)]


def _stats(paris):
    n = len(paris)
    if not n:
        return dict(regles=0, gagnes=0, reussite=None, ic95=None, annonce=None, ecart=None, roi=None)
    w = sum(1 for p in paris if p["resultat"] == "WIN")
    ann = [p["p_honnete"] for p in paris if p["p_honnete"] is not None]
    ann_m = sum(ann) / len(ann) if ann else None
    return dict(regles=n, gagnes=w, reussite=round(w / n, 4), ic95=wilson(w, n), annonce=None if ann_m is None else round(ann_m, 4),
                ecart=None if ann_m is None else round(w / n - ann_m, 4), roi=round(sum(p["profit"] for p in paris) / n, 4))


def bilan(carnet):
    """Par rôle (principal / autres) et par niveau de fiabilité. Statut : gel (un niveau SÛR/MOYEN/RISQUÉ sous son annonce de plus de
    10 points sur >= 50 paris), observation (< 100 paris principaux réglés), sinon controle_ok. Aucun statut ne dit « rentable »."""
    prin = [l["principal"] for l in carnet.values() if l["principal"]["resultat"]]
    aut = [p for l in carnet.values() if l["principal"]["resultat"] for p in l["autres"] if p["resultat"]]
    niveaux = ("SÛR", "MOYEN", "RISQUÉ", "NON CALIBRÉ")
    par = {"principal": {n: _stats([p for p in prin if p["niveau"] == n]) for n in niveaux},
           "autres": {n: _stats([p for p in aut if p["niveau"] == n]) for n in niveaux}}
    gel = [n for n in niveaux[:3] for s in [par["principal"][n]]
           if s["regles"] >= MIN_GEL and s["ecart"] is not None and s["ecart"] < -SEUIL_GEL]
    statut = "gel" if gel else ("observation" if len(prin) < SEUIL_PARIS else "controle_ok")
    return dict(principal=_stats(prin), autres=_stats(aut), par_niveau=par, niveaux_geles=gel, statut=statut)


def charge(dossier):
    p = os.path.join(dossier, "carnet.json")
    return json.load(open(p)) if os.path.exists(p) else {}


def sauve(carnet, dossier):
    os.makedirs(dossier, exist_ok=True)
    json.dump(carnet, open(os.path.join(dossier, "carnet.json"), "w"), ensure_ascii=False, indent=1, sort_keys=True)
