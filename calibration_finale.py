"""Etape 7: recalibration simple de P1, competition par competition (aucun melange), en validation chronologique; produit la configuration exploitable.
Methodes candidates (toutes sur logit P1): LEVEL (decalage b), SLOPE (a*logit+b: corrige un P1 trop resserre ou trop etale), ELO (a*logit+b+c*ecart_Elo standardise), ELO_PALIER / P_PALIER (correction additive par paliers de l'ecart Elo / de P1, seuil par arbre a une coupure, groupes >= 30 matchs). Pente a > 0 exigee (ordre de P1 conserve).
Protocole, pour chaque (competition, marche) :
 - pour chaque saison t in {2324, 2425, 2526}: ajustement sur les matchs STRICTEMENT anterieurs a t, mesure sur t;
 - SELECTION sur 2324 et 2425 seulement: meilleure methode par gain de perte log cumule; retenue si gain > 0 dans les deux saisons et z > 2,576 (Bonferroni sur 5 methodes, unilateral 2,5 %);
 - CONFIRMATION sur 2526 (jamais vue par la selection): gain de perte log > 0, gain de Brier > 0 et z > 1,645;
 - statut CORRECTION VALIDEE si tout est vrai, sinon P1 CONSERVE. Parametres de la configuration = ajustement sur tout l'historique 2122-2526 de la methode retenue.
Aucune correction forcee. Statistiques d'archive: pas une performance de moteur."""
import json, math, os, sys, warnings
import numpy as np
from multiprocessing import Pool
from statistics import NormalDist
from sklearn.tree import DecisionTreeRegressor
from sklearn.linear_model import LogisticRegression
import pouvoir_predictif as pp
import pouvoir_predictif_v3 as v3
import regles_durables as rd
import calibration_p1 as cp
warnings.filterwarnings("ignore")
RACINE = pp.RACINE; SAISONS = pp.SAISONS; EVT = pp.EVT; EPS = 1e-9; TESTS = [2, 3, 4]; METHODES = ["LEVEL", "SLOPE", "ELO", "ELO_PALIER", "P_PALIER"]; Z_SEL = NormalDist().inv_cdf(1 - 0.025 / len(METHODES)); Z_CONF = 1.645; MIN_GROUPE = 30
IELO = rd.IDX["elo_diff"]

def lb(p, y): return -(y * np.log(p) + (1 - y) * np.log(1 - p))

def ajuster(methode, lp, elo, y):
    """-> parametres ajustes sur l'apprentissage."""
    mu, sd = float(elo.mean()), float(elo.std() + 1e-9)
    if methode in ("ELO_PALIER", "P_PALIER"):
        p = 1 / (1 + np.exp(-lp)); x = elo if methode == "ELO_PALIER" else p; r = y - p
        if len(y) < 2 * MIN_GROUPE: return {"a": 1.0, "b": 0.0, "c": 0.0, "theta": float(np.median(x)), "r_bas": 0.0, "r_haut": 0.0, "palier": "elo" if methode == "ELO_PALIER" else "p"}
        tr = DecisionTreeRegressor(max_depth=1, min_samples_leaf=MIN_GROUPE, random_state=0).fit(x[:, None], r)
        if tr.tree_.node_count == 1: return {"a": 1.0, "b": 0.0, "c": 0.0, "theta": float(np.median(x)), "r_bas": float(r.mean()), "r_haut": float(r.mean()), "palier": "elo" if methode == "ELO_PALIER" else "p"}
        th = float(tr.tree_.threshold[0]); lo = x <= th
        return {"a": 1.0, "b": 0.0, "c": 0.0, "theta": th, "r_bas": float(r[lo].mean()), "r_haut": float(r[~lo].mean()), "palier": "elo" if methode == "ELO_PALIER" else "p"}
    if methode == "LEVEL":
        b = 0.0
        for _ in range(50):
            p = 1 / (1 + np.exp(-(lp + b))); g = (p - y).sum(); h = (p * (1 - p)).sum() + 1e-9; st = g / h; b -= st
            if abs(st) < 1e-9: break
        return {"a": 1.0, "b": float(b), "c": 0.0, "elo_mu": mu, "elo_sd": sd}
    if methode == "SLOPE":
        m = LogisticRegression(C=1e4, max_iter=300).fit(lp[:, None], y); return {"a": float(m.coef_[0, 0]), "b": float(m.intercept_[0]), "c": 0.0, "elo_mu": mu, "elo_sd": sd}
    m = LogisticRegression(C=1e4, max_iter=300).fit(np.column_stack([lp, (elo - mu) / sd]), y)
    return {"a": float(m.coef_[0, 0]), "b": float(m.intercept_[0]), "c": float(m.coef_[0, 1]), "elo_mu": mu, "elo_sd": sd}

def appliquer(par, p, elo): return cp.formule(par, p, elo if (par["c"] != 0.0 or par.get("palier") == "elo") else None)

def prediction_saison(methode, p, elo, y, valide, S, D, start, t):
    """probabilites corrigees de la saison t, ajustees sur les matchs strictement anterieurs a t (aucune donnee de t ni apres)."""
    tr = valide & (D < start[t]); te = valide & (S == t); par = ajuster(methode, v3.lg(p[tr]), elo[tr], y[tr])
    return te, appliquer(par, p[te], elo[te]), par

def calib_pente(p, y):
    try: return float(LogisticRegression(C=1e4, max_iter=300).fit(v3.lg(p)[:, None], y).coef_[0, 0])
    except Exception: return None

def mesures(p, pc, y):
    return {"n": int(len(y)), "perte_log_avant": round(float(lb(p, y).mean()), 5), "perte_log_apres": round(float(lb(pc, y).mean()), 5), "brier_avant": round(float(((p - y) ** 2).mean()), 5), "brier_apres": round(float(((pc - y) ** 2).mean()), 5),
            "ecart_moyen_avant": round(float(abs(p.mean() - y.mean())), 4), "ecart_moyen_apres": round(float(abs(pc.mean() - y.mean())), 4), "reussite_avant": round(float(((p > .5) == (y > .5)).mean()), 4), "reussite_apres": round(float(((pc > .5) == (y > .5)).mean()), 4),
            "pente_calibration_avant": calib_pente(p, y), "pente_calibration_apres": calib_pente(pc, y), "part_matchs_modifies_plus_de_1pt": round(float((np.abs(pc - p) > 0.01).mean()), 3)}

def par_ok(methode, par):
    """la correction doit conserver l'ordre de P1: pente positive pour les methodes logistiques."""
    return par['a'] > 0 if 'theta' not in par else True

def couple(PR, e):
    S, D, Y, valide, start = PR["S"], PR["D"], PR["Y"], PR["valide"], PR["start"]; y = Y[:, e]; p = PR["P1"][:, e]; elo = PR["X"][:, IELO]; res = {}
    for m in METHODES:
        res[m] = {}
        for t in TESTS:
            te, pc, _ = prediction_saison(m, p, elo, y, valide, S, D, start, t); res[m][t] = (te, pc, lb(p[te], y[te]) - lb(pc, y[te]), (p[te] - y[te]) ** 2 - (pc - y[te]) ** 2)
    sel = {}
    for m in METHODES:
        d = np.concatenate([res[m][2][2], res[m][3][2]]); sel[m] = (float(d.mean()), float(d.mean() / (d.std(ddof=1) / math.sqrt(len(d)))), res[m][2][2].mean() > 0 and res[m][3][2].mean() > 0)
    best = max(METHODES, key=lambda m: sel[m][0]); retenue = sel[best][2] and sel[best][1] > Z_SEL and par_ok(best, ajuster(best, v3.lg(p[valide]), elo[valide], y[valide]))
    te, pc, d4, b4 = res[best][4]; z4 = float(d4.mean() / (d4.std(ddof=1) / math.sqrt(len(d4)))); conf = bool(d4.mean() > 0 and b4.mean() > 0 and z4 > Z_CONF)
    statut = "CORRECTION VALIDEE" if (retenue and conf) else "P1 CONSERVE"
    # parametres sur tout l'historique
    vm = valide; par = ajuster(best, v3.lg(p[vm]), elo[vm], y[vm])
    # biais de P1 (tout l'historique): pente/intercept et residus par tiers de probabilite
    a_p1 = calib_pente(p[vm], y[vm]); q = np.quantile(p[vm], [1 / 3, 2 / 3]); tiers = {}
    for k, (lo, hi) in enumerate([(-1, q[0]), (q[0], q[1]), (q[1], 2)]):
        mm = vm & (p > lo) & (p <= hi) if k else vm & (p <= hi); r = y[mm] - p[mm]; tiers[["bas", "milieu", "haut"][k]] = {"n": int(mm.sum()), "p_moyen": round(float(p[mm].mean()), 3), "frequence": round(float(y[mm].mean()), 3), "z": round(float(r.sum() / math.sqrt((p[mm] * (1 - p[mm])).sum())), 2)}
    perf = {SAISONS[t]: mesures(p[res[best][t][0]], res[best][t][1], y[res[best][t][0]]) for t in TESTS}
    motifs = []
    if not sel[best][2]: motifs.append("gain de perte log non positif dans chacune des saisons 2324 et 2425")
    if sel[best][1] <= Z_SEL: motifs.append(f"z de selection {sel[best][1]:.2f} <= {Z_SEL:.2f}")
    if not par_ok(best, par): motifs.append("pente negative (ordre de P1 non conserve)")
    if not conf: motifs.append(f"confirmation 2526 insuffisante (gain {d4.mean():+.4f}, gain Brier {b4.mean():+.4f}, z {z4:.2f}, exige gain>0, Brier>0, z>{Z_CONF})")
    return {"observation": "aucun motif de rejet" if statut == "CORRECTION VALIDEE" else "; ".join(motifs), "methode": best if statut == "CORRECTION VALIDEE" else "P1", "meilleure_candidate": best, "statut": statut,
            "parametres": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in par.items()} if statut == "CORRECTION VALIDEE" else None, "parametres_meilleure_candidate": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in par.items()},
            "conditions_application": "tous les matchs ayant un historique dans la competition" + (" ; requiert ecart Elo (dom - ext) calcule avec K_elo de la competition" if (best in ("ELO", "ELO_PALIER") and statut == "CORRECTION VALIDEE") else ""),
            "couverture": round(float(valide[valide].mean()), 3), "selection_2324_2425": {"gain_perte_log": round(sel[best][0], 5), "z": round(sel[best][1], 2), "gain_positif_les_deux_saisons": bool(sel[best][2]),
            "gains_toutes_methodes": {m: round(sel[m][0], 5) for m in METHODES}}, "confirmation_2526": {"gain_perte_log": round(float(d4.mean()), 5), "z": round(z4, 2), "gain_brier": round(float(b4.mean()), 5)},
            "performances_par_saison": perf, "diagnostic_biais_P1": {"pente_calibration": round(a_p1, 3) if a_p1 else None, "tiers_de_probabilite": tiers}}

def analyser(code):
    PR = rd.preparer(code)
    if PR is None: return None
    return {"p1": {"k": PR["cfg_P1"][0], "demi_vie_jours": PR["cfg_P1"][1], "K_elo": PR["K_elo"]}, "n_matchs": int(len(PR["S"])), "marches": {EVT[e]: couple(PR, e) for e in range(7)}}

def _un(c):
    try: return c, analyser(c)
    except Exception as ex:
        import traceback; return c, {"erreur": repr(ex), "trace": traceback.format_exc()[-400:]}

def main(codes=None):
    cl = json.load(open(os.path.join(RACINE, "data", "inventaire", "classement_descriptif.json"), encoding="utf-8"))["competitions"]
    codes = codes or sorted(cl)
    with Pool(2) as pool: R = dict(pool.map(_un, codes, chunksize=1))
    R = {c: r for c, r in R.items() if r}
    cfg = {"description": "Configuration de calibration de P1 (etape 7). Appliquer avec calibration_p1.py. P1 = Poisson attaque/defense generales (parametres `p1`). Statut par competition et marche.",
           "protocole": "Selection sur 2324-2425, confirmation sur 2526, parametres ajustes sur 2122-2526; voir calibration_finale.py.", "seuils": {"z_selection": Z_SEL, "z_confirmation": Z_CONF},
           "competitions": {c: {"p1": r["p1"], **{m: x for m, x in r["marches"].items()}} for c, r in R.items() if "erreur" not in r}, "erreurs": {c: r for c, r in R.items() if "erreur" in r}}
    os.makedirs(os.path.join(RACINE, "data", "calibration_p1"), exist_ok=True)
    json.dump(cfg, open(os.path.join(RACINE, "data", "calibration_p1", "config_calibration.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return cfg

if __name__ == "__main__":
    main(sys.argv[1:] or None)
