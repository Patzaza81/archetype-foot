"""Etape 6: familles de regles independantes et valeur predictive (competition par competition, sans melange).
 1. Regles VALIDEES (ancetres mesures sur des saisons ulterieures a leur apprentissage) regroupees en FAMILLES: meme signe et (recouvrement Jaccard >= 0,5 OU plus petite regle incluse a >= 80 % dans l'autre) (liaison simple).
    Representant = regle au z ulterieur maximal. Autres membres: `raffinement` (sous-ensemble >= 80 % du representant dont le residu differe significativement du reste du representant, |z|>1,96, plus fort)
    ou `redondante`. Relations entre familles: complementaires (meme signe, Jaccard<0,2), chevauchantes (0,2-0,5), contradictoires (signe oppose, >=30 matchs communs).
 2. Rejeu: familles figees AVANT la saison t (regles de R_t, ancetres evalues sur t-1, t-2...) puis mesurees sur t. Correction = residu moyen MESURE hors apprentissage sur les saisons d'evaluation des ancetres
    (aucun parametre ajuste). Validation `stricte` (t=2526: >=2 saisons d'evaluation, toutes dans le sens, z cumule>1,96) ou `legere` (t=2425 ou 2526: >=1 saison, dans le sens, z>1,96).
    Comparaisons: chaque famille seule, moyenne des familles couvrant le match, somme, paires (synergie = gain de la paire - meilleur gain individuel; exploratoire).
 Bibliotheque (t=5): regles apprises sur tout l'historique 2122-2526, ancetres evalues 2324-2526.
Aucune correction n'est deployee. Statistiques d'archive, pas une performance de moteur."""
import json, math, os, sys, warnings, itertools
import numpy as np
from multiprocessing import Pool
import pouvoir_predictif as pp
import pouvoir_predictif_v3 as v3
import regles_conditions as rc
import regles_durables as rd
warnings.filterwarnings("ignore")
RACINE = pp.RACINE; SAISONS = pp.SAISONS; EVT = pp.EVT; EPS = 1e-9; J_FAM = 0.5

def evaluer_regle(q, R, t, valide, S, y, p, var):
    """ancetres de q (R_{t-1}, R_{t-2}, ...) evalues sur leur propre saison s>=2. Retourne dict(ev=[(s,somme_residu,somme_var,n,ok)], z, r_ev, ok_all)."""
    ev = []; cur = q
    for s in range(t - 1, 0, -1):
        a = rd.meilleur(cur, R.get(s, []), rd.J_EQ) if R.get(s) else None
        if a is None: break
        cur = a
        if s < 2: continue
        m = a["mem"] & valide & (S == s)
        if m.sum() >= 8: ev.append((s, float((y[m] - p[m]).sum()), float(var[m].sum()), int(m.sum()), int(np.sign((y[m] - p[m]).mean()) == np.sign(q["r"]))))
    if not ev: return None
    sg = np.sign(q["r"]); z = sum(x[1] for x in ev) * sg / math.sqrt(sum(x[2] for x in ev)); n = sum(x[3] for x in ev)
    return {"ev": ev, "z": float(z), "r_ev": sum(x[1] for x in ev) / n, "ok_all": all(x[4] for x in ev)}

def validees(R, t, mode, valide, S, y, p, var):
    out = []
    for q in R.get(t, []):
        e = evaluer_regle(q, R, t, valide, S, y, p, var)
        if e is None or not e["ok_all"] or e["z"] <= 1.96: continue
        if mode == "stricte" and len(e["ev"]) < 2: continue
        out.append(dict(q, ev=e))
    return out

def familles(V, valide, y, p, var):
    n = len(V); par = list(range(n))
    def f(i):
        while par[i] != i: par[i] = par[par[i]]; i = par[i]
        return i
    for i in range(n):
        for k in range(i + 1, n):
            if np.sign(V[i]["r"]) != np.sign(V[k]["r"]): continue
            a, b = V[i]["mem"], V[k]["mem"]; inc = (a & b).sum() / max(min(a.sum(), b.sum()), 1)   # inclusion de la plus petite dans la plus grande
            if rd.jac(a, b) >= J_FAM or inc >= 0.8: par[f(i)] = f(k)
    G = {}
    for i in range(n): G.setdefault(f(i), []).append(i)
    fam = []
    for idx in G.values():
        rep = max(idx, key=lambda i: V[i]["ev"]["z"]); R0 = V[rep]; membres = []
        for i in idx:
            if i == rep: continue
            m = V[i]["mem"]; reste = R0["mem"] & ~m; role = "redondante"
            if m.sum() > 0 and (m & R0["mem"]).sum() / m.sum() >= 0.8 and m.sum() < R0["mem"].sum() and reste.sum() >= 20 and m.sum() >= 20:
                rm, rr = (y[m] - p[m]).mean(), (y[reste] - p[reste]).mean(); se = math.sqrt(var[m].sum() / m.sum() ** 2 + var[reste].sum() / reste.sum() ** 2)
                if abs(rm - rr) / se > 1.96 and np.sign(R0["r"]) * (rm - rr) > 0: role = "raffinement"
            membres.append({"conditions": rd.texte(V[i]["cond"]), "role": role, "n": int(m.sum()), "residu": round(float(V[i]["r"]), 4)})
        fam.append({"rep": R0, "membres": membres})
    return fam

def relations(F):
    c = ch = ct = 0
    for a, b in itertools.combinations(F, 2):
        A, B = a["rep"], b["rep"]; j = rd.jac(A["mem"], B["mem"]); same = np.sign(A["r"]) == np.sign(B["r"])
        if not same and (A["mem"] & B["mem"]).sum() >= 30: ct += 1
        elif same and j < 0.2: c += 1
        elif same: ch += 1
    return {"complementaires": c, "chevauchantes": ch, "contradictoires": ct}

def metriques(p, pc, y):
    L0, L1 = v3.lb(p, y), v3.lb(pc, y)
    return {"n": int(len(y)), "gain_logloss": round(float((L0 - L1).mean()), 5), "gain_brier": round(float(((p - y) ** 2 - (pc - y) ** 2).mean()), 5), "freq": round(float(y.mean()), 4), "p_avant": round(float(p.mean()), 4), "p_apres": round(float(pc.mean()), 4),
            "ecart_calib_avant": round(float(abs(p.mean() - y.mean())), 4), "ecart_calib_apres": round(float(abs(pc.mean() - y.mean())), 4), "reussite_avant": round(float(((p > .5) == (y > .5)).mean()), 4), "reussite_apres": round(float(((pc > .5) == (y > .5)).mean()), 4)}

def corr(F_, X, p, how):
    """correction par les familles (r_ev) : moyenne ou somme des familles couvrant le match."""
    Fm = rc._F(X, p); s = np.zeros(len(p)); c = np.zeros(len(p))
    for f in F_:
        m = rc.masque(f["rep"], Fm); s[m] += f["rep"]["ev"]["r_ev"]; c[m] += 1
    d = s / np.maximum(c, 1) if how == "moy" else s
    return np.clip(p + d, EPS, 1 - EPS), c > 0

def analyser(code):
    PR = rd.preparer(code)
    if PR is None: return None
    S, Y, valide, X, P1 = PR["S"], PR["Y"], PR["valide"], PR["X"], PR["P1"]; res = {}
    for e in range(7):
        R = rd.ensembles(PR, e); y = Y[:, e]; p = P1[:, e]; var = p * (1 - p); out = {}
        # --- bibliotheque (t=5)
        V = validees(R, 5, "stricte", valide, S, y, p, var); fam = familles(V, valide, y, p, var)
        lib = []
        for f in sorted(fam, key=lambda f: -f["rep"]["ev"]["z"]):
            q = f["rep"]; m = q["mem"]
            lib.append({"conditions": rd.texte(q["cond"]), "sens": "favorable" if q["r"] > 0 else "defavorable", "n": int(m.sum()), "couverture": round(float(m.sum() / valide.sum()), 4), "taux_reussite": round(float(y[m].mean()), 4), "p1_moyen": round(float(p[m].mean()), 4),
                        "residu_apprentissage": round(float(q["r"]), 4), "residu_mesure_hors_apprentissage": round(float(q["ev"]["r_ev"]), 4), "z_ulterieur": round(q["ev"]["z"], 2),
                        "saisons_evaluees": [{"saison": SAISONS[s], "n": n, "dans_le_sens": bool(k)} for s, _, _, n, k in q["ev"]["ev"]],
                        "taux_par_saison": {SAISONS[s]: round(float(y[m & (S == s)].mean()), 3) for s in range(5) if (m & (S == s)).sum() >= 8},
                        "raffinements": [x for x in f["membres"] if x["role"] == "raffinement"][:3], "n_redondantes": sum(1 for x in f["membres"] if x["role"] == "redondante")})
        un = np.any([f["rep"]["mem"] for f in fam], axis=0).sum() / valide.sum() if fam else 0.0
        out["bibliotheque"] = {"n_regles_validees": len(V), "n_familles": len(fam), "n_raffinements": sum(1 for f in fam for x in f["membres"] if x["role"] == "raffinement"), "couverture_union": round(float(un), 4), "relations": relations(fam), "familles": lib}
        # --- rejeu
        rej = {}
        for t, mode, lab in ((4, "stricte", "2526_stricte"), (4, "legere", "2526_legere"), (3, "legere", "2425_legere")):
            Vt = validees(R, t, mode, valide, S, y, p, var); Ft = familles(Vt, valide, y, p, var); te = valide & (S == t)
            if not Ft: rej[lab] = {"n_familles": 0, "n_regles_validees": len(Vt)}; continue
            Xt, pt, yt = X[te], p[te], y[te]; pm, cm = corr(Ft, Xt, pt, "moy"); ps, _ = corr(Ft, Xt, pt, "somme")
            r = {"n_familles": len(Ft), "n_regles_validees": len(Vt), "couverture_test": round(float(cm.mean()), 4), "moyenne": metriques(pt, pm, yt), "somme": metriques(pt, ps, yt),
                 "sur_matchs_couverts": metriques(pt[cm], pm[cm], yt[cm]) if cm.sum() >= 8 else None}
            sing = []
            for f in Ft:
                pc, c1 = corr([f], Xt, pt, "moy"); sing.append(float((v3.lb(pt, yt) - v3.lb(pc, yt)).mean()))
            r["gain_individuel_par_famille"] = [round(g, 5) for g in sing]
            if len(Ft) >= 2:
                syn = []
                for (i, a), (k, b) in itertools.combinations(list(enumerate(Ft)), 2):
                    pc, _ = corr([a, b], Xt, pt, "moy"); g = float((v3.lb(pt, yt) - v3.lb(pc, yt)).mean()); syn.append(g - max(sing[i], sing[k]))
                r["synergie_paires"] = {"n_paires": len(syn), "moyenne": round(float(np.mean(syn)), 6), "paires_synergiques": int(sum(1 for x in syn if x > 0)), "meilleure": round(float(max(syn)), 6)}
            r["gain_total_moyenne_ge_meilleur_individuel"] = bool(r["moyenne"]["gain_logloss"] >= max(sing))
            rej[lab] = r
        out["rejeu"] = rej; res[EVT[e]] = out
    return res

def _un(c):
    try: return c, analyser(c)
    except Exception as ex:
        import traceback; return c, {"erreur": repr(ex), "trace": traceback.format_exc()[-500:]}

def main(codes=None):
    cl = json.load(open(os.path.join(RACINE, "data", "inventaire", "classement_descriptif.json"), encoding="utf-8"))["competitions"]
    codes = codes or sorted(cl)
    with Pool(2) as pool: R = dict(pool.map(_un, codes, chunksize=1))
    R = {c: r for c, r in R.items() if r}
    json.dump({"description": "Etape 6: familles de regles independantes et rejeu (voir regles_familles.py).", "competitions": R}, open(os.path.join(RACINE, "data", "inventaire", "familles_regles.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return R

if __name__ == "__main__":
    main(sys.argv[1:] or None)
