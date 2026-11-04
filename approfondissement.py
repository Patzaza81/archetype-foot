"""Etape 6d: approfondissement de deux cas (T1 exterieur, USA BTTS), chaque championnat seul.
Contexte = conditions de la 1re famille de regles validee (familles_regles.json). Analyses: fiabilite de P1 par deciles, residus par saison, concentration par equipe,
residu du meme contexte sur tous les marches, residus selon les facteurs de la regle (classes par quantiles des donnees), sensibilite de P1 au lissage k, recherche du meme phenomene hors du contexte.
Tout est mesure sur des matchs dont les variables sont connues avant le coup d'envoi; les residus sont (issue - P1). Exploratoire: sert a expliquer, pas a valider. Aucune correction deployee."""
import json, math, os, re, sys
import numpy as np
import pouvoir_predictif as pp
import pouvoir_predictif_v3 as v3
import regles_durables as rd
import regles_conditions as rc
RACINE = pp.RACINE; SAISONS = pp.SAISONS; EVT = pp.EVT

def masque_texte(conds, X):
    m = np.ones(len(X), bool)
    for c in conds:
        a = re.match(r"^(-?[\d.]+) < (\w+) <= (-?[\d.]+)$", c)
        if a: j = rd.IDX[a.group(2)]; m &= (X[:, j] > float(a.group(1))) & (X[:, j] <= float(a.group(3))); continue
        a = re.match(r"^(\w+) (<=|>) (-?[\d.]+)$", c); j = rd.IDX[a.group(1)]; m &= (X[:, j] <= float(a.group(3))) if a.group(2) == "<=" else (X[:, j] > float(a.group(3)))
    return m

def z_res(y, p, m):
    if m.sum() < 5: return None
    return float((y[m] - p[m]).sum() / math.sqrt((p[m] * (1 - p[m])).sum()))

def cas(code, marche, fam_idx=0):
    PR = rd.preparer(code); e = EVT.index(marche); S, Y, valide, X, P1, M = PR["S"], PR["Y"], PR["valide"], PR["X"], PR["P1"], PR["M"]; y, p = Y[:, e], P1[:, e]
    fam = json.load(open(os.path.join(RACINE, "data", "inventaire", "familles_regles.json"), encoding="utf-8"))["competitions"][code][marche]["bibliotheque"]["familles"][fam_idx]
    ctx = masque_texte(fam["conditions"], X) & valide; out = {"code": code, "marche": marche, "famille": {k: fam[k] for k in ("conditions", "sens", "n", "couverture", "taux_reussite", "p1_moyen", "z_ulterieur")}}
    # 1. fiabilite de P1 par deciles (quantiles des donnees)
    q = np.quantile(p[valide], np.linspace(0, 1, 11)); b = np.clip(np.searchsorted(q, p, side="right") - 1, 0, 9); rel = []
    for k in range(10):
        m = valide & (b == k)
        rel.append({"decile": k + 1, "n": int(m.sum()), "p_moyen": round(float(p[m].mean()), 3), "frequence": round(float(y[m].mean()), 3), "z": round(z_res(y, p, m), 2), "residus_par_saison_signe": "".join("+" if (y[m & (S == s)] - p[m & (S == s)]).mean() > 0 else "-" for s in range(5) if (m & (S == s)).sum() >= 5)})
    out["fiabilite_P1_deciles"] = rel
    # 2. par saison dans le contexte
    out["contexte_par_saison"] = {SAISONS[s]: {"n": int((ctx & (S == s)).sum()), "frequence": round(float(y[ctx & (S == s)].mean()), 3), "p1": round(float(p[ctx & (S == s)].mean()), 3)} for s in range(5) if (ctx & (S == s)).sum() >= 5}
    # 3. concentration par equipe (equipe a l'exterieur pour 'ext', a domicile sinon)
    idx = 3 if marche in ("ext",) else 2; eq = np.array([m_[idx] for m_ in M]); c = {}
    for t in np.unique(eq[ctx]):
        m = ctx & (eq == t); c[t] = (int(m.sum()), float((y[m] - p[m]).sum()))
    tot = sum(v[1] for v in c.values()); top = sorted(c.items(), key=lambda kv: -kv[1][0])[:6]
    out["equipes_du_contexte"] = {"n_equipes": len(c), "top_effectifs": [{"equipe": k, "n": v[0], "residu_moyen": round(v[1] / v[0], 3)} for k, v in top], "part_matchs_top3": round(sum(v[0] for k, v in top[:3]) / int(ctx.sum()), 3)}
    sans = ctx & ~np.isin(eq, [k for k, _ in top[:3]]); out["contexte_sans_top3_equipes"] = {"n": int(sans.sum()), "residu_moyen": round(float((y[sans] - p[sans]).mean()), 4), "z": round(z_res(y, p, sans), 2)} if sans.sum() >= 20 else None
    # 4. meme contexte, tous les marches
    out["meme_contexte_tous_marches"] = {EVT[k]: {"residu": round(float((Y[ctx, k] - P1[ctx, k]).mean()), 4), "z": round(z_res(Y[:, k], P1[:, k], ctx), 2), "frequence": round(float(Y[ctx, k].mean()), 3)} for k in range(7)}
    # 5. residu selon chaque facteur de la regle (classes par quantiles sur les matchs du championnat)
    fac = {}
    for cnd in fam["conditions"]:
        nm = re.findall(r"[a-z_0-9]+", cnd.replace("<=", " ")) ; nm = [w for w in nm if w in rd.IDX][0]; j = rd.IDX[nm]; qs = np.quantile(X[valide, j], np.linspace(0, 1, 6)); bb = np.clip(np.searchsorted(qs, X[:, j], side="right") - 1, 0, 4)
        fac[nm] = [{"classe": k + 1, "borne_haute": round(float(qs[k + 1]), 3), "n": int((valide & (bb == k)).sum()), "residu": round(float((y[valide & (bb == k)] - p[valide & (bb == k)]).mean()), 4), "z": round(z_res(y, p, valide & (bb == k)), 2)} for k in range(5)]
    out["residu_par_classe_de_facteur"] = fac
    # 6. sensibilite de P1 au lissage k (perte log sur tout l'historique valide, marche)
    k_res = {}
    for k in pp.K_GRILLE:
        P, _ = pp.predire(PR["M"], "P1", k, None, ret_mu=True); pk = np.nan_to_num(P[:, e], nan=.5).clip(1e-9, 1 - 1e-9); k_res[k] = round(float(v3.lb(pk[valide], y[valide]).mean()), 5)
    out["perte_log_P1_selon_k_sans_oubli"] = k_res
    # 7. meme phenomene hors contexte: premiers facteurs a residu significatif hors contexte (classes de quantiles)
    hors = valide & ~ctx; h = []
    for nm, j in rd.IDX.items():
        if nm == "logit_P1": continue
        qs = np.quantile(X[hors, j], np.linspace(0, 1, 6)); bb = np.clip(np.searchsorted(qs, X[:, j], side="right") - 1, 0, 4)
        for k in (0, 4):
            m = hors & (bb == k); z = z_res(y, p, m)
            if z is not None and abs(z) > 3: h.append({"facteur": nm, "classe": k + 1, "n": int(m.sum()), "residu": round(float((y[m] - p[m]).mean()), 4), "z": round(z, 2)})
    out["hors_contexte_extremes_significatifs"] = sorted(h, key=lambda r: -abs(r["z"]))[:8]
    return out

if __name__ == "__main__":
    R = {"T1_ext": cas("T1", "ext"), "USA_btts": cas("USA", "btts")}
    json.dump(R, open(os.path.join(RACINE, "data", "inventaire", "approfondissement_T1_USA.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for k, v in R.items():
        print("=====", k, v["famille"]); print("fiab", [(r["decile"], r["p_moyen"], r["frequence"], r["z"], r["residus_par_saison_signe"]) for r in v["fiabilite_P1_deciles"]])
        print("saisons", v["contexte_par_saison"]); print("equipes", v["equipes_du_contexte"], v["contexte_sans_top3_equipes"]); print("marches", {m: (x["residu"], x["z"]) for m, x in v["meme_contexte_tous_marches"].items()})
        for f, L in v["residu_par_classe_de_facteur"].items(): print("facteur", f, [(r["borne_haute"], r["n"], r["residu"], r["z"]) for r in L])
        print("k", v["perte_log_P1_selon_k_sans_oubli"]); print("hors", v["hors_contexte_extremes_significatifs"])
