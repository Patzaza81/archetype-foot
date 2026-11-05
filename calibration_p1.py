"""Module INDEPENDANT d'application des calibrations de P1 (aucun import des moteurs ni des modules de recherche; numpy seulement).
Entree: probabilites P1 d'un match (P1 = Poisson attaque/defense generales, parametres `p1` de la configuration), marche, competition, et si besoin l'ecart Elo.
Sortie: probabilite corrigee si le statut est CORRECTION VALIDEE, sinon P1 inchangee. Aucune ecriture, aucun effet de bord.
Configuration: data/calibration_p1/config_calibration.json (produite par calibration_finale.py)."""
import json, math, os
import numpy as np

CHEMIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "calibration_p1", "config_calibration.json")
MARCHES = ("dom", "nul", "ext", "o15", "o25", "o35", "btts")
EPS = 1e-9

def charger(chemin=None):
    with open(chemin or CHEMIN, encoding="utf-8") as f: return json.load(f)

def _logit(p): p = np.clip(np.asarray(p, float), EPS, 1 - EPS); return np.log(p / (1 - p))
def _sigm(z): return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))

def formule(par, p, elo_diff=None):
    """LEVEL / SLOPE / ELO: sigmoid(a*logit(p) + b + c*(elo_diff-elo_mu)/elo_sd).
    ELO_PALIER / P_PALIER: p + r_bas si x <= theta, p + r_haut sinon (x = ecart Elo ou p), borne dans ]0,1[."""
    if "theta" in par:
        p = np.asarray(p, float)
        if par["palier"] == "elo":
            if elo_diff is None: raise ValueError("elo_diff requis par la methode ELO_PALIER")
            x = np.asarray(elo_diff, float)
        else: x = p
        return np.clip(p + np.where(x <= par["theta"], par["r_bas"], par["r_haut"]), EPS, 1 - EPS)
    z = par["a"] * _logit(p) + par["b"]
    if par.get("c", 0.0) != 0.0:
        if elo_diff is None: raise ValueError("elo_diff requis par la methode ELO")
        z = z + par["c"] * (np.asarray(elo_diff, float) - par["elo_mu"]) / par["elo_sd"]
    return np.clip(_sigm(z), EPS, 1 - EPS)

def appliquer(config, competition, marche, p, elo_diff=None):
    """-> (p_corrigee, info). P1 conserve (statut P1 CONSERVE ou couple absent): p renvoyee telle quelle."""
    e = config["competitions"].get(competition, {}).get(marche)
    p = np.asarray(p, float)
    if e is None or e["statut"] != "CORRECTION VALIDEE": return p, {"statut": "P1 CONSERVE", "methode": "P1"}
    return formule(e["parametres"], p, elo_diff), {"statut": e["statut"], "methode": e["methode"]}

def appliquer_1x2(config, competition, p_dom, p_nul, p_ext, elo_diff=None):
    """Applique les calibrations disponibles a dom/nul/ext puis renormalise a 1 (seulement si au moins une est validee)."""
    out = []; any_ = False
    for m, p in (("dom", p_dom), ("nul", p_nul), ("ext", p_ext)):
        q, info = appliquer(config, competition, m, p, elo_diff); any_ |= info["methode"] != "P1"; out.append(np.asarray(q, float))
    if not any_: return tuple(np.asarray(p, float) for p in (p_dom, p_nul, p_ext))
    s = out[0] + out[1] + out[2]; return tuple(q / s for q in out)

def elo_diff_depuis_historique(matchs, K, equipe_dom, equipe_ext):
    """Ecart Elo (dom - ext) AVANT un match futur, a partir des matchs joues (jour, dom, ext, buts_dom, buts_ext), tries par jour croissant.
    Meme logique que la recherche: matchs traites dans l'ordre, avantage domicile = ecart de buts moyen des matchs precedents, pas K propre a la competition."""
    elo = {}; ga = [0.0, 0]; i = 0; m = sorted(matchs, key=lambda x: x[0])
    while i < len(m):
        j = i
        while j < len(m) and m[j][0] == m[i][0]: j += 1
        for jour, h, a, bd, ba in m[i:j]:
            err = (bd - ba) - (elo.get(h, 0.0) - elo.get(a, 0.0) + (ga[0] / ga[1] if ga[1] else 0.0))
            elo[h] = elo.get(h, 0.0) + K * err; elo[a] = elo.get(a, 0.0) - K * err; ga[0] += bd - ba; ga[1] += 1
        i = j
    return elo.get(equipe_dom, 0.0) - elo.get(equipe_ext, 0.0)
