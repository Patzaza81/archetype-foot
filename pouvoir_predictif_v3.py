"""Etape 3: exploitation des historiques, competition par competition (AUCUN melange de competitions).
Pour chaque match, variables connues AVANT le coup d'envoi (force Elo, buts attendus Poisson, forme, buts pour/contre par lieu,
confrontations directes, repos, taille de l'historique); pour chaque marche, la competition apprend de SON histoire:
  CAL (recalibrage de P1), LOGI (logistique sur toutes les variables), TREE (arbre = conditions croisees, taille de feuille et lissage choisis par les donnees),
  GBM (arbres boostes peu profonds: interactions), SEL (choix par validation sur la saison precedente).
Rejeu chronologique: saison test s (2324..2526): apprentissage sur les saisons < s, choix des hyperparametres sur s-1 (appris sur < s-1). Rien de la saison test n'intervient.
Decouverte: arbre ajuste sur tout l'historique -> conditions (feuilles) les plus favorables/defavorables, avec effectif, frequence, ecart a la base et signe stable par saison.
Statistiques d'archive: pas une performance de moteur. Scores joues uniquement; archives en lecture seule."""
import json, math, os, sys, warnings
import numpy as np
from multiprocessing import Pool
from statistics import NormalDist
from sklearn.tree import DecisionTreeClassifier, _tree
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
import pouvoir_predictif as pp
import pouvoir_predictif_v2 as v2
warnings.filterwarnings("ignore")
RACINE = pp.RACINE; SAISONS = pp.SAISONS; EVT = pp.EVT; MARCHES = pp.MARCHES; EPS = 1e-9
TESTS = [2, 3, 4]
NOMS = ["elo_diff", "mu_dom", "mu_ext", "mu_total", "forme_pts_dom", "forme_pts_ext", "forme_bp_dom", "forme_bp_ext", "forme_bc_dom", "forme_bc_ext",
        "dom_bp_domicile", "dom_bc_domicile", "ext_bp_exterieur", "ext_bc_exterieur", "h2h_buts", "h2h_vict_dom", "repos_diff", "historique_min"]
K_SHR = 5

def variables(M, K, mu):
    """(N,18) causales; mu (N,2) buts attendus P1 (deja causaux)."""
    N = len(M); X = np.full((N, 18), np.nan)
    elo = {}; recent = {}; dom = {}; ext = {}; h2h = {}; last = {}; nj = {}
    tot = [0.0, 0.0, 0]                       # buts dom, ext, n (moyennes de la competition)
    ga = [0.0, 0]
    i = 0
    while i < N:
        j = i
        while j < N and M[j][0] == M[i][0]: j += 1
        day = M[i][0]; Lh = tot[0] / tot[2] if tot[2] else 1.4; La = tot[1] / tot[2] if tot[2] else 1.1
        for t in range(i, j):
            _, _, h, a, _, _ = M[t]
            X[t, 0] = elo.get(h, 0.0) - elo.get(a, 0.0)
            X[t, 1], X[t, 2] = mu[t]; X[t, 3] = mu[t].sum()
            rh, ra = recent.get(h, []), recent.get(a, [])
            if rh: X[t, 4] = np.mean([x[0] for x in rh]); X[t, 6] = np.mean([x[1] for x in rh]); X[t, 8] = np.mean([x[2] for x in rh])
            if ra: X[t, 5] = np.mean([x[0] for x in ra]); X[t, 7] = np.mean([x[1] for x in ra]); X[t, 9] = np.mean([x[2] for x in ra])
            dh = dom.get(h, [0, 0.0, 0.0]); ea = ext.get(a, [0, 0.0, 0.0])
            X[t, 10] = (dh[1] + K_SHR * Lh) / (dh[0] + K_SHR); X[t, 11] = (dh[2] + K_SHR * La) / (dh[0] + K_SHR)
            X[t, 12] = (ea[1] + K_SHR * La) / (ea[0] + K_SHR); X[t, 13] = (ea[2] + K_SHR * Lh) / (ea[0] + K_SHR)
            key = (h, a) if h < a else (a, h); hh = h2h.get(key, [0, 0.0, 0.0]); smin = hh[2] if h < a else hh[0] - hh[2]
            X[t, 14] = (hh[1] + K_SHR * (Lh + La)) / (hh[0] + K_SHR); X[t, 15] = (smin + K_SHR * 0.5) / (hh[0] + K_SHR)
            X[t, 16] = math.log1p(min(day - last.get(h, day - 60), 60)) - math.log1p(min(day - last.get(a, day - 60), 60))
            X[t, 17] = min(nj.get(h, 0), nj.get(a, 0))
        for t in range(i, j):
            _, _, h, a, bd, ba = M[t]
            err = (bd - ba) - (elo.get(h, 0.0) - elo.get(a, 0.0) + (ga[0] / ga[1] if ga[1] else 0.0))
            elo[h] = elo.get(h, 0.0) + K * err; elo[a] = elo.get(a, 0.0) - K * err
            ph = 3 if bd > ba else (1 if bd == ba else 0); pa = 3 if ba > bd else (1 if bd == ba else 0)
            recent.setdefault(h, []).append((ph, bd, ba)); recent.setdefault(a, []).append((pa, ba, bd)); recent[h] = recent[h][-5:]; recent[a] = recent[a][-5:]
            d = dom.setdefault(h, [0, 0.0, 0.0]); d[0] += 1; d[1] += bd; d[2] += ba
            e = ext.setdefault(a, [0, 0.0, 0.0]); e[0] += 1; e[1] += ba; e[2] += bd
            key = (h, a) if h < a else (a, h); q = h2h.setdefault(key, [0, 0.0, 0.0]); s_h = 1.0 if bd > ba else (0.5 if bd == ba else 0.0)
            q[0] += 1; q[1] += bd + ba; q[2] += s_h if h < a else 1.0 - s_h
            last[h] = last[a] = day; nj[h] = nj.get(h, 0) + 1; nj[a] = nj.get(a, 0) + 1
            ga[0] += bd - ba; ga[1] += 1; tot[0] += bd; tot[1] += ba; tot[2] += 1
        i = j
    return X

def lb(p, y): return -(y * np.log(p) + (1 - y) * np.log(1 - p))
def lg(p): p = np.clip(p, EPS, 1 - EPS); return np.log(p / (1 - p))

def modeles(Xtr, ytr, ptr):
    """dictionnaire nom -> fonction (X, p1) -> probas ; ajustes sur l'apprentissage uniquement. Hyperparametres a choisir par validation."""
    out = {}
    ok = ytr.min() != ytr.max()
    if not ok: return out
    c = LogisticRegression(C=1e4, max_iter=200).fit(lg(ptr)[:, None], ytr); out["CAL"] = lambda X, p, c=c: c.predict_proba(lg(p)[:, None])[:, 1]
    mu, sd = Xtr.mean(0), Xtr.std(0); sd[sd < 1e-9] = 1
    for C in (0.003, 0.03, 0.3):
        m = LogisticRegression(C=C, max_iter=300).fit((Xtr - mu) / sd, ytr); out[f"LOGI@{C}"] = lambda X, p, m=m: m.predict_proba((X - mu) / sd)[:, 1]
    F = np.column_stack([Xtr, lg(ptr)])
    for L in (40, 100, 250):
        tr = DecisionTreeClassifier(min_samples_leaf=L, max_depth=4, random_state=0).fit(F, ytr)
        nf = np.bincount(tr.apply(F), minlength=tr.tree_.node_count).astype(float)
        for mm in (0, 50, 200):
            out[f"TREE@{L},{mm}"] = lambda X, p, tr=tr, nf=nf, mm=mm: _feuille(tr, nf, np.column_stack([X, lg(p)]), p, mm)
    for dep, it in ((2, 60), (3, 100)):
        g = HistGradientBoostingClassifier(max_depth=dep, max_iter=it, learning_rate=0.05, min_samples_leaf=40, l2_regularization=5.0, early_stopping=False, random_state=0).fit(F, ytr)
        out[f"GBM@{dep},{it}"] = lambda X, p, g=g: g.predict_proba(np.column_stack([X, lg(p)]))[:, 1]
    return out

def _feuille(tr, nf, F, p, mm):
    leaf = tr.apply(F); v = tr.tree_.value[leaf, 0, :]; pos = v[:, 1] * nf[leaf] if v.sum(1).max() <= 1.0001 else v[:, 1]
    n = nf[leaf]; return np.clip((pos + mm * p) / (n + mm), EPS, 1 - EPS)

def analyser(code):
    M = pp.charger(code); N = len(M)
    if N < 200: return None
    S = np.array([SAISONS.index(m[1]) for m in M]); D = np.array([m[0] for m in M]); Y = pp.issues(M); ref = pp.reference(M); valide = ~np.isnan(ref[:, 0])
    # parametres de base choisis uniquement sur les saisons <= 2223 (avant tout test)
    pre = valide & (S <= 1)
    best = None
    base = {}
    for k in pp.K_GRILLE:
        for hl in pp.HL_GRILLE:
            P, mu = pp.predire(M, "P1", k, hl, ret_mu=True); base[(k, hl)] = (P, mu)
            sc = np.mean([lb(np.nan_to_num(P[pre, e], nan=.5).clip(EPS, 1 - EPS), Y[pre, e]).mean() for e in range(7)]) if pre.any() else 9
            if best is None or sc < best[0]: best = (sc, (k, hl))
    cfg = best[1]; P1, mu = base[cfg]
    gd = np.array([m[4] - m[5] for m in M], float)
    Ks = min(v2.K_ELO, key=lambda K: np.nanmean((v2.elo_pred_gd(M, K)[pre] - gd[pre]) ** 2) if pre.any() else 0)
    X = variables(M, Ks, np.nan_to_num(mu, nan=1.2)); X = np.where(np.isnan(X), np.nanmean(X[valide], 0) if valide.any() else 0, X)
    start = {s: D[S == s].min() for s in range(5)}
    pred = {}; choix = {}
    for s in TESTS:
        te = valide & (S == s); trf = valide & (D < start[s]); trv = valide & (D < start[s - 1]); va = valide & (S == s - 1)
        for e in range(7):
            p = np.nan_to_num(P1[:, e], nan=.5).clip(EPS, 1 - EPS); y = Y[:, e]
            mv = modeles(X[trv], y[trv], p[trv]); mf = modeles(X[trf], y[trf], p[trf])
            cands = {"P1": (lb(p[va], y[va]).mean(), p[te])}
            for nom in mv:
                if nom in mf: cands[nom] = (lb(np.clip(mv[nom](X[va], p[va]), EPS, 1 - EPS), y[va]).mean(), np.clip(mf[nom](X[te], p[te]), EPS, 1 - EPS))
            fam = lambda pre_: min((k for k in cands if k == pre_ or k.startswith(pre_ + "@")), key=lambda k: cands[k][0]) if any(k == pre_ or k.startswith(pre_ + "@") for k in cands) else None
            sel = {"P1": "P1"}
            for f in ("CAL", "LOGI", "TREE", "GBM"):
                b = fam(f)
                if b: sel[f] = b
            sel["SEL"] = min(cands, key=lambda k: cands[k][0])
            for v, k in sel.items():
                pred.setdefault(v, {}).setdefault(s, np.full((N, 7), np.nan))[te, e] = cands[k][1]
            choix.setdefault(SAISONS[s], {})[EVT[e]] = {"SEL": sel["SEL"], "TREE": sel.get("TREE")}
    # evaluation
    mask = valide & np.isin(S, TESTS); Yt = Y[mask]; Lr, Br = pp.pertes(ref[mask], Yt); Hr = pp.succes(ref[mask], Yt)
    res = {}
    for v in pred:
        P = np.full((N, 7), np.nan)
        for s in TESTS: P[S == s] = np.where(np.isnan(pred[v][s][S == s]), P[S == s], pred[v][s][S == s])
        P = P[mask]
        if np.isnan(P).any(): continue
        P3 = P.copy(); P3[:, :3] = P3[:, :3] / P3[:, :3].sum(1, keepdims=True)
        L, B = pp.pertes(np.clip(P3, EPS, 1 - EPS), Yt); H = pp.succes(P3, Yt)
        for mi, mk in enumerate(MARCHES):
            d = Lr[:, mi] - L[:, mi]; n = len(d); se = d.std(ddof=1) / math.sqrt(n)
            par = {SAISONS[s]: round(float(d[S[mask] == s].mean()), 5) for s in TESTS}
            res[f"{v}|{mk}"] = {"methode": v, "marche": mk, "n": n, "gain_logloss": round(float(d.mean()), 5), "z": round(float(d.mean() / se), 2) if se > 0 else None,
                                "reussite": round(float(H[:, mi].mean()), 4), "reussite_ref": round(float(Hr[:, mi].mean()), 4), "gain_par_saison": par,
                                "saisons_gagnantes": f"{sum(1 for q in par.values() if q > 0)}/3"}
    # decouverte: arbre sur tout l'historique (par marche), conditions croisees
    dec = decouverte(X, Y, P1, valide, S, cfg)
    return {"n_matchs": N, "n_test": int(mask.sum()), "config_P1": list(cfg), "K_elo": Ks, "resultats": res, "choix": choix, "decouverte": dec}

def decouverte(X, Y, P1, valide, S, cfg):
    out = {}; F = np.column_stack([X, lg(np.nan_to_num(P1[:, 0], nan=.5))]); noms = NOMS + ["logit_P1_1x2"]
    for e in range(7):
        m = valide; y = Y[m, e]; Fe = np.column_stack([X, lg(np.nan_to_num(P1[:, e], nan=.5))])[m]; nm = NOMS + ["logit_P1"]
        L = max(40, int(0.04 * len(y)))
        tr = DecisionTreeClassifier(min_samples_leaf=L, max_depth=3, random_state=0).fit(Fe, y); t = tr.tree_; base = float(y.mean())
        feuilles = []
        def rec(nd, cond):
            if t.children_left[nd] == _tree.TREE_LEAF:
                idx = tr.apply(Fe) == nd; yy = y[idx]; ss = S[m][idx]
                par = {SAISONS[s]: (round(float(yy[ss == s].mean()), 3), int((ss == s).sum())) for s in range(5) if (ss == s).sum() >= 10}
                bs = {SAISONS[s]: float(y[S[m] == s].mean()) for s in range(5) if (S[m] == s).any()}
                sg = [np.sign(v[0] - bs[k]) for k, v in par.items()]
                feuilles.append({"conditions": cond, "n": int(idx.sum()), "frequence": round(float(yy.mean()), 4), "ecart_base": round(float(yy.mean() - base), 4),
                                 "par_saison": par, "signe_stable": bool(len(sg) >= 3 and len(set(sg)) == 1)}); return
            f = nm[t.feature[nd]]; th = round(float(t.threshold[nd]), 3)
            rec(t.children_left[nd], cond + [f"{f} <= {th}"]); rec(t.children_right[nd], cond + [f"{f} > {th}"])
        rec(0, [])
        imp = sorted(((nm[i], round(float(v), 3)) for i, v in enumerate(tr.feature_importances_) if v > 0), key=lambda z: -z[1])
        out[EVT[e]] = {"base": round(base, 4), "taille_min_feuille": L, "variables_determinantes": imp[:5],
                       "plus_favorables": sorted(feuilles, key=lambda f: -f["ecart_base"])[:2], "plus_defavorables": sorted(feuilles, key=lambda f: f["ecart_base"])[:2]}
    return out

def _un(code):
    try: return code, analyser(code)
    except Exception as ex: return code, {"erreur": repr(ex)}

def main(codes=None):
    cl = json.load(open(os.path.join(RACINE, "data", "inventaire", "classement_descriptif.json"), encoding="utf-8"))["competitions"]
    codes = codes or sorted(cl)
    with Pool(2) as pool: R = dict(pool.map(_un, codes, chunksize=1))
    R = {c: r for c, r in R.items() if r}
    n = sum(len(r.get("resultats", {})) for r in R.values()); zb = NormalDist().inv_cdf(1 - 0.05 / max(n, 1))
    for r in R.values():
        for q in r.get("resultats", {}).values():
            g = int(q["saisons_gagnantes"][0])
            q["verdict"] = "aucun_avantage" if (q["z"] is None or q["gain_logloss"] <= 0) else ("avantage_robuste" if q["z"] > zb and g == 3 else ("avantage" if q["z"] > 1.96 and g == 3 else "indetermine"))
    doc = {"description": "Etape 3 (voir en-tete de pouvoir_predictif_v3.py). Gain = perte log (reference - methode) par match, 2324-2526, competition par competition.", "tests_total": n, "z_bonferroni": round(zb, 2), "competitions": R}
    json.dump(doc, open(os.path.join(RACINE, "data", "inventaire", "pouvoir_predictif_v3.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return doc

if __name__ == "__main__":
    main(sys.argv[1:] or None)
