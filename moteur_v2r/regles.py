"""Règles FIGÉES de v2r : fichier daté, jamais modifié après écriture ; un réentraînement crée une nouvelle version.
La méthode (seuils, coupures, paramètres) est dans CONFIG : la changer exige d'incrémenter VERSION_METHODE."""
import json
import os

from . import integration as I, modele as M, echantillon as X

VERSION_METHODE = 1
CONFIG = dict(min_paris=10, roi_min=0.30, max_par_match=1, pas_cote=X.PAS_COTE,
              coupures_ligue=list(I.COUPURES_LIGUE), coupures_match=list(I.COUPURES_MATCH), params=dict(M.PARAMS))


def entraine(matchs_joues, cree_le):
    """matchs_joues: matchs AVEC score, joués strictement avant `cree_le` (AAAA-MM-JJ). Retourne le dict de règles."""
    ms = [m for m in matchs_joues if m["h"] is not None and m["date"] < cree_le]
    if not ms:
        return None
    L = I.lignes_profil(ms)
    acc = {}
    for l in L:
        a = acc.setdefault(I.cle(l), [0.0, 0])
        a[0] += l["profit"]; a[1] += 1
    cellules = [dict(lib=k[0], tr=k[1], cl=k[2], cm=k[3], roi=s / n, n=n)
                for k, (s, n) in sorted(acc.items())
                if n >= CONFIG["min_paris"] and s / n >= CONFIG["roi_min"]]
    pri = M.prior_ligue([m["hd"] + m["he"] for m in ms])
    return dict(version=cree_le, methode=VERSION_METHODE, cree_le=cree_le, entraine_sur=len(ms),
                jusqu_au=max(m["date"] for m in ms), config=CONFIG, pri=pri,
                moyenne_ligue=I.moyenne_buts_ligue(ms), cellules=cellules)


def table(regles):
    return {(c["lib"], c["tr"], c["cl"], c["cm"]): c["roi"] for c in regles["cellules"]}


def ecrit(regles, dossier):
    os.makedirs(os.path.join(dossier, "regles"), exist_ok=True)
    chemin = os.path.join(dossier, "regles", f"regles_{regles['version']}.json")
    if os.path.exists(chemin):
        raise FileExistsError(f"règles {regles['version']} déjà figées : jamais modifiées")
    json.dump(regles, open(chemin, "w"), ensure_ascii=False, indent=1)
    return chemin


def derniere(dossier):
    d = os.path.join(dossier, "regles")
    if not os.path.isdir(d):
        return None
    fs = sorted(f for f in os.listdir(d) if f.startswith("regles_") and f.endswith(".json"))
    return json.load(open(os.path.join(d, fs[-1]))) if fs else None


def doit_reentrainer(aujourdhui, regles):
    """Lundi (weekday 0) et règles absentes ou vieilles d'au moins 6 jours. aujourdhui: datetime.date."""
    if regles is None:
        return True
    import datetime
    cree = datetime.date.fromisoformat(regles["cree_le"])
    return aujourdhui.weekday() == 0 and (aujourdhui - cree).days >= 6
