"""E10 : confirmation hors échantillon. Modèles appris sur le bloc (tout), testés sur les matchs de l'archive postérieurs au dernier jour du bloc (16/10/2026), donc jamais vus.
Ajoute le filtre opérationnel (cote Betpawa >= 1,26) APRÈS la prédiction : les cotes n'entrent dans aucun calcul prédictif. Fréquence du championnat = matchs du même championnat des 300 jours précédents (résultats connus)."""
import sys, glob, gzip, json, warnings, numpy as np
warnings.filterwarnings("ignore")
from sklearn.linear_model import LogisticRegression as LR
import commun as C
from commun import *
lg = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4)))
def ll(p, y): p = np.clip(p, 1e-6, 1 - 1e-6); return -(y * np.log(p) + (1 - y) * np.log(1 - p))
def tri(T):
    o = np.argsort(T["jour"], kind="stable"); return {k: T[k][o] for k in ("X", "P", "Y", "jour", "comp", "id")}, list(T["names"])
Tb, names = tri(np.load("sorties/table_bloc.npz", allow_pickle=True)); Ta, _ = tri(np.load("sorties/table_archive.npz", allow_pickle=True))
cols = [C.IDX[k] for k in C.CLES]
def lfreq(lm, comps, jours):
    """lm = liste (comp, jour, vecteur issue 23 marchés) ; renvoie la fréquence du marché dans le championnat sur 300 jours, NaN si < 20 matchs."""
    par = {}
    for c, j, y in lm: par.setdefault(c, []).append((np.datetime64(j, "D").astype(int), y))
    for c in par: par[c].sort(key=lambda t: t[0])
    out = np.full((len(comps), len(cols)), np.nan, np.float32)
    for i, (c, j) in enumerate(zip(comps, jours)):
        dj = np.datetime64(j, "D").astype(int); L = [y for d, y in par.get(c, []) if dj - 300 <= d < dj]
        if len(L) >= 20: out[i] = np.mean(L, axis=0)
    return out
# championnat : tous les matchs connus du bloc (clé = division) ; de l'archive (clé = nom) reconstruits depuis les fiches des équipes
mb, sb, _ = C.charger_bloc()
lm_b = [(m["competition"], m["jour"], C.TAB[min(sb[m["id"]][0], 10), min(sb[m["id"]][1], 10)][cols]) for m in mb if m["id"] in sb]
ma, sa, _ = C.charger()
seen, lm_a = set(), []
for m in ma:
    for team, recs in ((m["cle_dom"], m["md"]), (m["cle_ext"], m["me"])):
        for r in recs:
            if r["dom"] and (m["competition"], team, r["date"]) not in seen:
                seen.add((m["competition"], team, r["date"])); lm_a.append((m["competition"], r["date"], C.TAB[min(r["gf"], 10), min(r["ga"], 10)][cols]))
    if m["id"] in sa and (m["competition"], m["cle_dom"], m["jour"]) not in seen:
        seen.add((m["competition"], m["cle_dom"], m["jour"])); lm_a.append((m["competition"], m["jour"], C.TAB[min(sa[m["id"]][0], 10), min(sa[m["id"]][1], 10)][cols]))
LFb = lfreq(lm_b, Tb["comp"], Tb["jour"]); LFa = lfreq(lm_a, Ta["comp"], Ta["jour"])
LAST = str(max(Tb["jour"])); test = np.array([str(j) > LAST for j in Ta["jour"]])
print("dernier jour du bloc", LAST, "; matchs d'archive postérieurs :", int(test.sum()), "du", min(Ta["jour"][test]), "au", max(Ta["jour"][test]), "; avec fréquence championnat", int((test & ~np.isnan(LFa[:, 0])).sum()))
okb = ~np.isnan(LFb[:, 0]); oka = test & ~np.isnan(LFa[:, 0])
nb = len(Tb["X"]); cut = int(nb * .75)
lo, hi = np.percentile(Tb["X"], 1, axis=0), np.percentile(Tb["X"], 99, axis=0); mu = np.clip(Tb["X"], lo, hi).mean(0); sd = np.clip(Tb["X"], lo, hi).std(0) + 1e-9
Zb = (np.clip(Tb["X"], lo, hi) - mu) / sd; Za = (np.clip(Ta["X"], lo, hi) - mu) / sd
# cotes de l'archive (filtre opérationnel seulement)
ids = {m["id"] for m in ma}; cot = {}
for f in sorted(glob.glob(str(ROOT / "data" / "archive_test" / "*.json.gz"))):
    for k, x in json.load(gzip.open(f)).items():
        if k in ids: cot[k] = V.cotes_betpawa(x.get("cotes_betpawa") or {})
print("marché | taux test | n | Δ(a) fréq. champ. | Δ(d) croisements+fréq. | cote>=1,26 : n cas | réussite top-40 % M0 | M(a) | M(d)")
sel = {}
for j, k in enumerate(C.CLES):
    y = Tb["Y"][:, j]; lp = lg(Tb["P"][:, j]); lf = lg((LFb[:, j] * 50 + 2 * Tb["P"][:, j]) / 52)
    ya = Ta["Y"][oka, j]; lpa = lg(Ta["P"][oka, j]); lfa = lg((LFa[oka, j] * 50 + 2 * Ta["P"][oka, j]) / 52)
    m0 = LR(C=1e6, max_iter=1000).fit(lp[okb, None], y[okb]); p0 = m0.predict_proba(lpa[:, None])[:, 1]
    ma_ = LR(C=1e6, max_iter=1000).fit(np.c_[lp, lf][okb], y[okb]); pa = ma_.predict_proba(np.c_[lpa, lfa])[:, 1]
    F = np.c_[10 * lp, 10 * lf, Zb]; Fa = np.c_[10 * lpa, 10 * lfa, Za[oka]]
    best = None
    for c in (0.003, 0.01, 0.03, 0.1, 0.3):
        tr = np.where(okb & (np.arange(nb) < cut))[0]; va = np.where(okb & (np.arange(nb) >= cut))[0]
        l = ll(LR(penalty="l1", solver="liblinear", C=c, max_iter=2000).fit(F[tr], y[tr]).predict_proba(F[va])[:, 1], y[va]).mean()
        if best is None or l < best[0]: best = (l, c)
    pd_ = LR(penalty="l1", solver="liblinear", C=best[1], max_iter=2000).fit(F[okb], y[okb]).predict_proba(Fa)[:, 1]
    ga, gd = ll(p0, ya) - ll(pa, ya), ll(p0, ya) - ll(pd_, ya); se = lambda x: x.std(ddof=1) / np.sqrt(len(x))
    ids_a = Ta["id"][oka]; c_ = np.array([cot.get(i, {}).get(k, np.nan) for i in ids_a]); f = c_ >= 1.26
    r = ""
    if f.sum() >= 40:
        q = max(10, int(0.4 * f.sum())); h = lambda s: ya[f][np.argsort(-s[f], kind="stable")[:q]].mean()
        r = f"{h(p0):.3f} | {h(pa):.3f} | {h(pd_):.3f} (top {q})"
    print(f"{k:19s} {ya.mean():.3f} {len(ya)} | {1e4*ga.mean():+6.1f}±{1e4*se(ga):4.1f} | {1e4*gd.mean():+6.1f}±{1e4*se(gd):4.1f} | {int(f.sum()):4d} | {r}")
