"""Etape 5: regles durables, croisements approfondis, contextes de saison, cartographie par competition et marche.
Chaque competition apprend seule (aucun melange). Rien n'est deploye: toutes les etiquettes distinguent exploratoire / validee chronologiquement.
 - Variables: celles de l'etape 3 + sans encaisser / sans marquer par lieu, regularite offensive, journee de saison, et croisements explicites
   (attaque dom x defense ext, attaque ext x defense dom, buts attendus x solidite defensive, ecart de force x forme, regularite x sans encaisser...).
 - Ensembles de regles R_s = regles decouvertes sur les matchs strictement anterieurs a la saison s (s=1..5; R_5 = tout l'historique).
 - Equivalence de regles entre ensembles: meme signe et recouvrement (Jaccard sur les matchs de la competition) >= J. Une regle est DURABLE si elle est retrouvee dans R_{s-1}.
 - Rejeu: pour s=2324,2425,2526, regles de R_s durables ou non, mesurees sur la saison s (reproduction du residu, effectif, taux de reussite).
 - Validation d'une regle de la bibliotheque: ses ancetres (R_4,R_3,R_2) sont evalues sur les saisons 2526,2425,2324 (apres leur apprentissage); `validee` si >=2 saisons evaluables,
   toutes dans le sens annonce, z cumule > 1,96; `exploratoire` sinon. Aucune correction n'est appliquee.
 - Contextes de saison: effet du stade (tiers de journee appris sur le passe) teste sur les saisons ulterieures.
Statistiques d'archive: pas une performance de moteur. Scores joues uniquement; archives en lecture seule."""
import json, math, os, sys, warnings
import numpy as np
from multiprocessing import Pool
import pouvoir_predictif as pp
import pouvoir_predictif_v3 as v3
import regles_conditions as rc
warnings.filterwarnings("ignore")
RACINE = pp.RACINE; SAISONS = pp.SAISONS; EVT = pp.EVT; TESTS = [2, 3, 4]; J_EQ = 0.5; K = 5
NOMS_PLUS = ["dom_sans_encaisser_dom", "ext_sans_encaisser_ext", "dom_sans_marquer_dom", "ext_sans_marquer_ext", "regularite_dom", "regularite_ext", "journee_min",
             "x_att_dom_def_ext", "x_att_ext_def_dom", "x_mu_total_solidite", "x_elo_forme", "x_marquent_les_deux", "x_sans_encaisser_les_deux", "mu_dom_moins_ext"]
NOMS = v3.NOMS + NOMS_PLUS + ["logit_P1"]
IDX = {n: i for i, n in enumerate(NOMS)}; IJ = IDX["journee_min"]

def plus(M):
    """(N,7) causales: taux sans encaisser/sans marquer par lieu (lisses vers la competition), regularite (ecart-type des buts marques, 10 derniers), journee de saison."""
    N = len(M); X = np.full((N, 7), np.nan); dom = {}; ext = {}; gf = {}; nj = {}; lig = [0, 0, 0, 0, 0]
    i = 0
    while i < N:
        j = i
        while j < N and M[j][0] == M[i][0]: j += 1
        n = max(lig[0], 1); lcs_h, lcs_a, lf_h, lf_a = (lig[1] / n, lig[2] / n, lig[3] / n, lig[4] / n) if lig[0] else (.3, .25, .25, .3)
        for t in range(i, j):
            _, s, h, a, _, _ = M[t]
            dh = dom.get(h, [0, 0, 0]); ea = ext.get(a, [0, 0, 0])
            X[t, 0] = (dh[1] + K * lcs_h) / (dh[0] + K); X[t, 1] = (ea[1] + K * lcs_a) / (ea[0] + K)
            X[t, 2] = (dh[2] + K * lf_h) / (dh[0] + K); X[t, 3] = (ea[2] + K * lf_a) / (ea[0] + K)
            for c, q in ((4, h), (5, a)):
                g = gf.get(q, []); X[t, c] = np.std(g[-10:]) if len(g) >= 3 else np.nan
            X[t, 6] = min(nj.get((s, h), 0), nj.get((s, a), 0))
        for t in range(i, j):
            _, s, h, a, bd, ba = M[t]
            d = dom.setdefault(h, [0, 0, 0]); d[0] += 1; d[1] += ba == 0; d[2] += bd == 0
            e = ext.setdefault(a, [0, 0, 0]); e[0] += 1; e[1] += bd == 0; e[2] += ba == 0
            gf.setdefault(h, []).append(bd); gf.setdefault(a, []).append(ba); nj[(s, h)] = nj.get((s, h), 0) + 1; nj[(s, a)] = nj.get((s, a), 0) + 1
            lig[0] += 1; lig[1] += ba == 0; lig[2] += bd == 0; lig[3] += bd == 0; lig[4] += ba == 0
        i = j
    return X

def preparer(code):
    PR = rc.preparer(code)
    if PR is None: return None
    M, valide = PR["M"], PR["valide"]; B = PR["X"]; P = plus(M)
    P = np.where(np.isnan(P), np.nanmean(P[valide], 0), P)
    g = lambda n: B[:, v3.NOMS.index(n)]
    cr = np.column_stack([g("dom_bp_domicile") * g("ext_bc_exterieur"), g("ext_bp_exterieur") * g("dom_bc_domicile"), g("mu_total") * (g("dom_bc_domicile") + g("ext_bc_exterieur")),
                          g("elo_diff") * (g("forme_pts_dom") - g("forme_pts_ext")), (1 - P[:, 2]) * (1 - P[:, 3]), P[:, 0] * P[:, 1], g("mu_dom") - g("mu_ext")])
    PR["X"] = np.hstack([B, P, cr]); return PR

def texte(cond):
    """conditions simplifiees: une borne basse et une borne haute au plus par variable."""
    lo, hi = {}, {}
    for j, o, th in cond:
        if o == ">": lo[j] = max(lo.get(j, -1e18), th)
        else: hi[j] = min(hi.get(j, 1e18), th)
    out = []
    for j in sorted(set(lo) | set(hi)):
        if j in lo and j in hi: out.append(f"{lo[j]:.3f} < {NOMS[j]} <= {hi[j]:.3f}")
        elif j in lo: out.append(f"{NOMS[j]} > {lo[j]:.3f}")
        else: out.append(f"{NOMS[j]} <= {hi[j]:.3f}")
    return out

def appartenance(q, F): return rc.masque(q, F)

def ensembles(PR, e):
    """R_s pour s=1..5 : (regles avec 'mem' = appartenance sur les matchs valides de toute la competition, 'frac')."""
    S, D, Y, valide, start, X, P1 = PR["S"], PR["D"], PR["Y"], PR["valide"], PR["start"], PR["X"], PR["P1"][:, e]
    F = rc._F(X, P1); out = {}
    for s in range(1, 6):
        tr = valide & (D < start[s]) if s < 5 else valide.copy()
        if tr.sum() < 100: out[s] = []; continue
        R = rc.decouvrir(X[tr], Y[tr, e], P1[tr], S[tr])
        for q in R: q["frac"] = q["n"] / tr.sum(); q["mem"] = appartenance(q, F) & valide
        out[s] = R
    return out

def jac(a, b):
    u = (a | b).sum(); return (a & b).sum() / u if u else 0.0

def meilleur(q, R, J):
    b = None
    for p in R:
        if np.sign(p["r"]) != np.sign(q["r"]): continue
        jj = jac(q["mem"], p["mem"])
        if jj >= J and (b is None or jj > b[0]): b = (jj, p)
    return b[1] if b else None

def classe_effectif(f): return "<10%" if f < 0.1 else ("10-20%" if f < 0.2 else ("20-30%" if f < 0.3 else ">=30%"))

def analyser(code):
    PR = preparer(code)
    if PR is None: return None
    S, Y, valide, X, P1 = PR["S"], PR["Y"], PR["valide"], PR["X"], PR["P1"]; N = len(S); F_all = None
    rejeu = []; carto = {}; contexte = {}
    for e in range(7):
        R = ensembles(PR, e); y = Y[:, e]; p = P1[:, e]; F = rc._F(X, p); var = p * (1 - p)
        # --- rejeu: regles de R_t, durables (retrouvees dans R_{t-1}) ou non, mesurees sur la saison t
        for t in TESTS:
            te = valide & (S == t)
            for q in R[t]:
                m = q["mem"] & te
                if m.sum() < 8: continue
                dur = {J: meilleur(q, R[t - 1], J) is not None for J in (0.5, 0.7)}
                rt = float((y[m] - p[m]).mean())
                rejeu.append({"marche": EVT[e], "saison": SAISONS[t], "frac": round(q["frac"], 3), "classe": classe_effectif(q["frac"]), "r_passe": round(q["r"], 4), "n_test": int(m.sum()),
                              "freq_test": round(float(y[m].mean()), 4), "p1_test": round(float(p[m].mean()), 4), "r_test": round(rt, 4), "sens_ok": int(np.sign(rt) == np.sign(q["r"])),
                              "z_test": round(float((y[m] - p[m]).sum() / math.sqrt(var[m].sum())), 2), "durable": dur[0.5], "durable_j07": dur[0.7],
                              "stade": [int(((X[m][:, IJ] >= a) & (X[m][:, IJ] < b)).sum()) for a, b in _tiers(X, valide, S, t)]})
        # --- bibliotheque: regles de R_5, lignee et validation chronologique des ancetres
        lib = []; n_eval = 0
        for q in R[5]:
            lin = []; cur = q
            for s in (4, 3, 2, 1):
                a = meilleur(cur, R[s], J_EQ) if R.get(s) else None
                if a is None: break
                lin.append((s, a)); cur = a
            ev = []   # ancetres evalues sur la saison s (apres leur apprentissage), s>=2
            for s, a in lin:
                if s < 2: continue
                m = a["mem"] & valide & (S == s)
                if m.sum() >= 8: ev.append((s, float((y[m] - p[m]).sum()), float(var[m].sum()), int(m.sum()), int(np.sign((y[m] - p[m]).mean()) == np.sign(q["r"]))))
            zc = (sum(x[1] for x in ev) * np.sign(q["r"]) / math.sqrt(sum(x[2] for x in ev))) if ev else None
            ok = len(ev) >= 2 and all(x[4] for x in ev) and zc is not None and zc > 1.96
            m = q["mem"]; seas = {SAISONS[s]: round(float(y[m & (S == s)].mean()), 3) for s in range(5) if (m & (S == s)).sum() >= 8}
            n_eval += len(ev) >= 2
            lib.append({"conditions": texte(q["cond"]), "sens": "favorable" if q["r"] > 0 else "defavorable", "n": int(m.sum()), "couverture": round(float(m.sum() / valide.sum()), 4),
                        "taux_reussite": round(float(y[m].mean()), 4), "p1_moyen": round(float(p[m].mean()), 4), "residu": round(float(q["r"]), 4), "z_apprentissage": round(float(q["z"]), 2),
                        "frac": round(float(q["frac"]), 3), "classe": classe_effectif(q["frac"]), "apparitions": 1 + len(lin), "taux_par_saison": seas,
                        "evaluations_ulterieures": [{"saison": SAISONS[s], "n": n, "residu_sens_ok": bool(k)} for s, _, _, n, k in ev], "z_ulterieur": round(float(zc), 2) if zc is not None else None,
                        "statut": "validee_chronologiquement" if ok else "exploratoire", "_mem": m})
        # complementaires / contradictoires
        fav = [r for r in lib if r["sens"] == "favorable"]; dfv = [r for r in lib if r["sens"] == "defavorable"]
        contra = 0; compl = 0
        for i in range(len(lib)):
            for k in range(i + 1, len(lib)):
                a, b = lib[i], lib[k]; inter = (a["_mem"] & b["_mem"]).sum()
                if a["sens"] != b["sens"] and inter >= 30: contra += 1
                elif a["sens"] == b["sens"] and jac(a["_mem"], b["_mem"]) < 0.2: compl += 1
        union = lambda L: float((np.any([r["_mem"] for r in L], axis=0)).sum() / valide.sum()) if L else 0.0
        cf, cd = union(fav), union(dfv)
        for r in lib: del r["_mem"]
        lib.sort(key=lambda r: (-(r["statut"] == "validee_chronologiquement"), -abs(r["residu"]) * math.sqrt(r["n"])))
        carto[EVT[e]] = {"base": round(float(y[valide].mean()), 4), "n_regles": len(lib), "n_validees": sum(1 for r in lib if r["statut"] == "validee_chronologiquement"), "n_evaluables": n_eval, "validees_attendues_par_hasard": round(0.025 * n_eval, 1), "n_durables": sum(1 for r in lib if r["apparitions"] >= 2),
                         "paires_contradictoires": contra, "paires_complementaires": compl, "couverture_favorables": round(cf, 4), "couverture_defavorables": round(cd, 4),
                         "regles": lib[:12]}
        # --- contexte de saison: effet du tiers de journee appris sur le passe, teste ensuite
        ctx = []
        for t in TESTS:
            tr = valide & (S < t); te = valide & (S == t); ed = _tiers(X, valide, S, t)
            for k, (a, b) in enumerate(ed):
                mt = tr & (X[:, IJ] >= a) & (X[:, IJ] < b); mm = te & (X[:, IJ] >= a) & (X[:, IJ] < b)
                if mt.sum() < 30 or mm.sum() < 8: continue
                rp = float((y[mt] - p[mt]).mean()); zp = (y[mt] - p[mt]).sum() / math.sqrt(var[mt].sum()); rt = float((y[mm] - p[mm]).mean())
                ctx.append({"saison": SAISONS[t], "tiers": ["debut", "milieu", "fin"][k], "r_passe": round(rp, 4), "z_passe": round(float(zp), 2), "r_test": round(rt, 4), "n_test": int(mm.sum()), "sens_ok": int(np.sign(rp) == np.sign(rt)), "signif_passe": bool(abs(zp) > 1.96)})
        contexte[EVT[e]] = ctx
    return {"n_matchs": int(N), "n_valides": int(valide.sum()), "cartographie": carto, "rejeu": rejeu, "contexte": contexte}

def _tiers(X, valide, S, t):
    """bornes (a,b) des tiers de journee calculees sur les matchs des saisons < t."""
    v = X[valide & (S < t), IJ]; q1, q2 = np.quantile(v, [1 / 3, 2 / 3]); return [(-1, q1 + 1e-9), (q1 + 1e-9, q2 + 1e-9), (q2 + 1e-9, 1e9)]

def _un(c):
    try: return c, analyser(c)
    except Exception as ex:
        import traceback; return c, {"erreur": repr(ex), "trace": traceback.format_exc()[-600:]}

def main(codes=None):
    cl = json.load(open(os.path.join(RACINE, "data", "inventaire", "classement_descriptif.json"), encoding="utf-8"))["competitions"]
    codes = codes or sorted(cl)
    with Pool(2) as pool: R = dict(pool.map(_un, codes, chunksize=1))
    R = {c: r for c, r in R.items() if r}
    ch = os.path.join(RACINE, "data", "inventaire")
    json.dump({"description": "Cartographie des conditions par competition et marche (etape 5); statut validee_chronologiquement / exploratoire; aucune correction deployee.", "variables": NOMS,
               "competitions": {c: r.get("cartographie", r) for c, r in R.items()}}, open(os.path.join(ch, "cartographie_conditions.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"rejeu": {c: r.get("rejeu") for c, r in R.items()}, "contexte": {c: r.get("contexte") for c, r in R.items()}}, open(os.path.join(ch, "regles_durables_rejeu.json"), "w", encoding="utf-8"), ensure_ascii=False)
    return R

if __name__ == "__main__":
    main(sys.argv[1:] or None)
