"""Etape 4: rejeu chronologique des REGLES DE CONDITIONS, competition par competition (aucun melange), sans cotes ni ROI.
Pour chaque competition, marche et saison test s (2324..2526):
 1. DECOUVERTE sur les matchs strictement anterieurs a s: arbres de regression sur le residu (issue - P1) -> feuilles = conditions croisees (profondeurs 2,3,4 x tailles de feuille 2%,4%,8%).
 2. SELECTION (sur le passe seulement): residu moyen significatif (|z|>1,96 vs P1) ET meme signe sur chaque saison passee ayant >=8 matchs dans la regle (au moins 2 saisons).
 3. FIGEAGE: conditions et residus figes avant s. Intensite d'application lambda (grille 0..1) et effectif minimal des regles (0,10,20,30 % de l'apprentissage) choisis en marche avant sur les saisons t=2..s-1 (regles de t decouvertes avant t).
 4. MESURE sur la saison s: effectif, residu observe vs residu annonce, gain de perte log vs P1 (tous matchs, et matchs couverts).
 5. ECHECS: derive des variables dans les regles qui ne se reproduisent pas; reproduction selon le stade de saison.
 6. BIBLIOTHEQUE: regles ajustees sur tout l'historique, etiquetees `validee` (rejeu gagnant 3/3 saisons, z>1,96) ou `hypothese`.
Statistiques d'archive: pas une performance de moteur. Scores joues uniquement; archives en lecture seule."""
import json, math, os, sys, warnings
import numpy as np
from multiprocessing import Pool
from statistics import NormalDist
from sklearn.tree import DecisionTreeRegressor, _tree
import pouvoir_predictif as pp
import pouvoir_predictif_v2 as v2
import pouvoir_predictif_v3 as v3
warnings.filterwarnings("ignore")
RACINE = pp.RACINE; SAISONS = pp.SAISONS; EVT = pp.EVT; EPS = 1e-9
TESTS = [2, 3, 4]; LAMBDAS = [0.0, 0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1.0]; FMIN = [0.0, 0.1, 0.2, 0.3]   # effectif minimal d'une regle en fraction de l'apprentissage
NOMS = v3.NOMS + ["logit_P1"]
PROFS = (2, 3, 4); FRACS = (0.02, 0.04, 0.08)

def preparer(code):
    M = pp.charger(code); N = len(M)
    if N < 200: return None
    S = np.array([SAISONS.index(m[1]) for m in M]); D = np.array([m[0] for m in M]); Y = pp.issues(M); ref = pp.reference(M); valide = ~np.isnan(ref[:, 0]); pre = valide & (S <= 1)
    best = None; base = {}
    for k in pp.K_GRILLE:
        for hl in pp.HL_GRILLE:
            P, mu = pp.predire(M, "P1", k, hl, ret_mu=True); base[(k, hl)] = (P, mu)
            sc = np.mean([v3.lb(np.nan_to_num(P[pre, e], nan=.5).clip(EPS, 1 - EPS), Y[pre, e]).mean() for e in range(7)])
            if best is None or sc < best[0]: best = (sc, (k, hl))
    P1, mu = base[best[1]]
    gd = np.array([m[4] - m[5] for m in M], float)
    Ks = min(v2.K_ELO, key=lambda K: np.nanmean((v2.elo_pred_gd(M, K)[pre] - gd[pre]) ** 2))
    X = v3.variables(M, Ks, np.nan_to_num(mu, nan=1.2)); X = np.where(np.isnan(X), np.nanmean(X[valide], 0), X)
    P1 = np.nan_to_num(P1, nan=.5).clip(EPS, 1 - EPS)
    return dict(M=M, S=S, D=D, Y=Y, ref=ref, valide=valide, P1=P1, X=X, start={s: D[S == s].min() for s in range(5)}, K_elo=Ks, cfg_P1=best[1])

def _F(X, p): return np.column_stack([X, v3.lg(p)])

def decouvrir(X, y, p, S):
    """regles = liste de dict(cond=[(j, '<=' ou '>', seuil)], r=residu moyen, n, z) ; X,y,p: matchs d'apprentissage uniquement."""
    F = _F(X, p); r = y - p; N = len(y); out = []
    var = p * (1 - p)
    for dep in PROFS:
        for fr in FRACS:
            L = max(20, int(fr * N))
            if N < 2 * L: continue
            tr = DecisionTreeRegressor(max_depth=dep, min_samples_leaf=L, random_state=0).fit(F, r); t = tr.tree_; leaf = tr.apply(F)
            def rec(nd, cond):
                if t.children_left[nd] == _tree.TREE_LEAF:
                    if not cond: return
                    m = leaf == nd; n = int(m.sum()); z = r[m].sum() / math.sqrt(var[m].sum())
                    if abs(z) <= 1.96: return
                    sg = []
                    for s in np.unique(S[m]):
                        mm = m & (S == s)
                        if mm.sum() >= 8: sg.append(np.sign(r[mm].mean()))
                    if len(sg) >= 2 and len(set(sg)) == 1 and sg[0] == np.sign(z):
                        out.append({"cond": cond, "r": float(r[m].mean()), "n": n, "z": float(z)})
                    return
                j = int(t.feature[nd]); th = float(t.threshold[nd])
                rec(t.children_left[nd], cond + [(j, "<=", th)]); rec(t.children_right[nd], cond + [(j, ">", th)])
            rec(0, [])
    seen = set(); uniq = []
    for q in out:
        k = tuple((j, o, round(th, 4)) for j, o, th in q["cond"])
        if k not in seen: seen.add(k); uniq.append(q)
    return uniq

def masque(regle, F):
    m = np.ones(len(F), bool)
    for j, o, th in regle["cond"]: m &= (F[:, j] <= th) if o == "<=" else (F[:, j] > th)
    return m

def ajuster_p(regles, X, p, lam, fmin=0.0):
    """p corrigee = p + lam * moyenne des residus figes des regles qui couvrent le match."""
    F = _F(X, p); somme = np.zeros(len(p)); cnt = np.zeros(len(p))
    for q in regles:
        if q.get("frac", 1.0) < fmin: continue
        m = masque(q, F); somme[m] += q["r"]; cnt[m] += 1
    corr = np.where(cnt > 0, somme / np.maximum(cnt, 1), 0.0)
    return np.clip(p + lam * corr, EPS, 1 - EPS), cnt > 0

def regles_avant(PR, e, s, cache):
    k = (e, s)
    if k not in cache:
        tr = PR["valide"] & (PR["D"] < PR["start"][s])
        R = decouvrir(PR["X"][tr], PR["Y"][tr, e], PR["P1"][tr, e], PR["S"][tr]) if tr.sum() > 100 else []
        for q in R: q["frac"] = q["n"] / tr.sum()
        cache[k] = R
    return cache[k]

def rejeu_marche(PR, e, s, cache=None):
    """Regles figees avant la saison s (matchs strictement anterieurs) + lambda choisi en marche avant sur les saisons t=2..s-1 (regles de t decouvertes avant t, appliquees a t)."""
    cache = {} if cache is None else cache
    S, Y, valide, X, P1 = PR["S"], PR["Y"], PR["valide"], PR["X"], PR["P1"][:, e]
    regles = regles_avant(PR, e, s, cache); lam = 0.0; fm = 0.0
    tot = {(l, f): 0.0 for l in LAMBDAS for f in FMIN}; nv = 0
    for t_ in range(2, s):
        rv = regles_avant(PR, e, t_, cache); va = valide & (S == t_)
        if not rv or not va.any(): continue
        for (l, f) in tot:
            pc, _ = ajuster_p(rv, X[va], P1[va], l, f); tot[(l, f)] += v3.lb(pc, Y[va, e]).sum()
        nv += 1
    if nv: lam, fm = min(tot, key=tot.get)
    return regles, lam, fm

def analyser(code):
    PR = preparer(code)
    if PR is None: return None
    S, Y, valide, X, P1 = PR["S"], PR["Y"], PR["valide"], PR["X"], PR["P1"]; med = float(np.median(X[valide][:, 17]))
    res = {}; regles_rec = []; derive = {n: [] for n in NOMS}; stade = {"debut": [0, 0], "fin": [0, 0]}
    for e in range(7):
        choix_l = []; gains = {}; gains1 = {}; sl = [0.0, 0.0]; cov = 0; tot = 0; reps = [0, 0]; regs_n = 0; rec_ev = 0; att_ev = 0.0; obs_ev = 0.0; nloc = 0
        cache = {}
        for s in TESTS:
            regles, lam, fm = rejeu_marche(PR, e, s, cache); te = valide & (S == s); p = P1[te, e]; y = Y[te, e]
            pc, cv = ajuster_p(regles, X[te], p, lam, fm); choix_l.append((lam, fm))
            pc1, _ = ajuster_p(regles, X[te], p, 1.0, fm); gains1[s] = v3.lb(p, y) - v3.lb(pc1, y)
            gains[s] = v3.lb(p, y) - v3.lb(pc, y); cov += int(cv.sum()); tot += int(te.sum()); regs_n += len(regles)
            Ft = _F(X[te], p); varp = p * (1 - p)
            for q in regles:
                m = masque(q, Ft)
                if m.sum() < 8: continue
                rt = float((y[m] - p[m]).mean()); sl[0] += m.sum() * rt * q['r']; sl[1] += m.sum() * q['r'] ** 2; ok = int(np.sign(rt) == np.sign(q["r"])); reps[0] += ok; reps[1] += 1
                zt = float((y[m] - p[m]).sum() / math.sqrt(varp[m].sum()))
                regles_rec.append({"marche": EVT[e], "saison": SAISONS[s], "conditions": [f"{NOMS[j]} {o} {th:.3f}" for j, o, th in q["cond"]], "n_passe": q["n"], "residu_passe": round(q["r"], 4), "z_passe": round(q["z"], 2),
                                   "n_test": int(m.sum()), "frequence_test": round(float(y[m].mean()), 4), "p1_moyen_test": round(float(p[m].mean()), 4), "residu_test": round(rt, 4), "z_test": round(zt, 2), "lambda": lam})
                if not ok:   # derive des variables: ecart moyen test vs passe dans la regle, en ecarts-types de la competition
                    tr = valide & (PR["D"] < PR["start"][s]); Ftr = _F(X[tr], P1[tr, e]); mt = masque(q, Ftr); sd = Ftr.std(0) + 1e-9
                    for j in range(len(NOMS)): derive[NOMS[j]].append(float(abs(Ft[m][:, j].mean() - Ftr[mt][:, j].mean()) / sd[j]))
                k = "debut" if Ft[m][:, 17].mean() <= med else "fin"; stade[k][0] += ok; stade[k][1] += 1
        d = np.concatenate([gains[s] for s in TESTS]); n = len(d); se = d.std(ddof=1) / math.sqrt(n) if n > 1 else 0
        par = {SAISONS[s]: round(float(gains[s].mean()), 5) for s in TESTS}
        d1 = np.concatenate([gains1[s] for s in TESTS]); se1 = d1.std(ddof=1) / math.sqrt(n) if n > 1 else 0
        par1 = {SAISONS[s]: round(float(gains1[s].mean()), 5) for s in TESTS}
        res[EVT[e]] = {"pente_reproduction": round(sl[0] / sl[1], 3) if sl[1] > 0 else None, "gain_lambda1": round(float(d1.mean()), 6), "z_lambda1": round(float(d1.mean() / se1), 2) if se1 > 0 else None,
                       "choix_lambda_fmin": choix_l, "saisons_gagnantes_lambda1": f"{sum(1 for q in par1.values() if q > 0)}/3", "n_test": n, "regles_figees": regs_n, "couverture": round(cov / tot, 4), "reproduction_signe": f"{reps[0]}/{reps[1]}", "gain_logloss": round(float(d.mean()), 6),
                       "z": round(float(d.mean() / se), 2) if se > 0 else None, "gain_par_saison": par, "saisons_gagnantes": f"{sum(1 for q in par.values() if q > 0)}/3"}
    # bibliotheque: regles ajustees sur tout l'historique
    bib = {}
    for e in range(7):
        tr = valide; regles = decouvrir(X[tr], Y[tr, e], P1[tr, e], S[tr])
        r_ = res[EVT[e]]; etat = "validee" if (r_["saisons_gagnantes"] == "3/3" and r_["z"] is not None and r_["z"] > 1.96) else "hypothese"
        regles.sort(key=lambda q: -abs(q["z"]))
        bib[EVT[e]] = {"statut": etat, "regles": [{"conditions": [f"{NOMS[j]} {o} {th:.3f}" for j, o, th in q["cond"]], "n": q["n"], "residu": round(q["r"], 4), "z": round(q["z"], 2)} for q in regles[:10]], "n_regles_total": len(regles)}
    return {"n_matchs": len(S), "resultats": res, "regles_testees": regles_rec, "derive_variables": {k: round(float(np.mean(v)), 3) for k, v in derive.items() if v},
            "reproduction_par_stade": {k: f"{v[0]}/{v[1]}" for k, v in stade.items()}, "bibliotheque": bib}

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
    ch = os.path.join(RACINE, "data", "inventaire")
    json.dump({"description": "Etape 4 (voir en-tete de regles_conditions.py). Gain = perte log (P1 - P1 corrigee par les regles figees) par match, 2324-2526.", "tests_total": n, "z_bonferroni": round(zb, 2),
               "competitions": {c: {k: v for k, v in r.items() if k not in ("bibliotheque", "regles_testees")} for c, r in R.items()}}, open(os.path.join(ch, "regles_conditions.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"description": "Bibliotheque de regles par competition et marche, ajustees sur tout l'historique 2122-2526. statut=validee: rejeu 3/3 saisons et z>1,96; sinon hypothese.", "competitions": {c: r.get("bibliotheque") for c, r in R.items()}},
              open(os.path.join(ch, "bibliotheque_regles.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"description": "Regles figees avant chaque saison test et leur reproduction.", "competitions": {c: r.get("regles_testees") for c, r in R.items()}}, open(os.path.join(ch, "regles_conditions_rejeu.json"), "w", encoding="utf-8"), ensure_ascii=False)
    return R

if __name__ == "__main__":
    main(sys.argv[1:] or None)
