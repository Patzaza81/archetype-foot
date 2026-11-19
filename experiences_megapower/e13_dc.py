"""E13 : modèle d'équipes « tous les résultats connus » (Poisson / Dixon-Coles, attaque et défense de chaque équipe, avantage du terrain par championnat, poids décroissant avec l'âge,
historique de DEUX saisons, domicile et extérieur ensemble), validé semaine après semaine sur des matchs futurs. Comparé au modèle actuel de Mega Power. Buts seulement, aucune cote.
Réglages (décroissance, régularisation) choisis sur la période de validation V ; jugement sur la période de test T jamais utilisée."""
import sys, time, warnings, numpy as np, scipy.sparse as sp
warnings.filterwarnings("ignore")
from sklearn.linear_model import PoissonRegressor
import commun as C
from commun import *
t0 = time.time()
C.MEQ = 32.0
mb, sb, _ = C.charger_bloc(); C.MEQ = 32.0
lig = {k: M.Ligue(v) for k, v in M.index_ligues(mb).items()}
D = lambda s: int(np.datetime64(s, "D").astype(int))
# tous les matchs du bloc (résultats connus), indexés
allm = [(D(m["jour"]), m["competition"], m["domicile"], m["exterieur"], *sb[m["id"]]) for m in mb if m["id"] in sb]
LG = {c: i for i, c in enumerate(sorted({x[1] for x in allm}))}
TM = {}
for x in allm:
    for t in ((x[1], x[2]), (x[1], x[3])): TM.setdefault(t, len(TM))
nL, nT = len(LG), len(TM)
dates = np.array([x[0] for x in allm]); lgi = np.array([LG[x[1]] for x in allm]); hi = np.array([TM[(x[1], x[2])] for x in allm]); ai = np.array([TM[(x[1], x[3])] for x in allm])
gh = np.array([x[4] for x in allm], float); ga = np.array([x[5] for x in allm], float)  # float pour Poisson
def design(l, h, a):
    n = len(l); r = np.arange(n); L = 10.0                      # colonnes de championnat à l'échelle 10 : peu pénalisées
    X1 = sp.hstack([sp.csr_matrix((np.full(n, L), (r, l)), (n, nL)), sp.csr_matrix((np.full(n, L), (r, l)), (n, nL)), sp.csr_matrix((np.ones(n), (r, h)), (n, nT)), sp.csr_matrix((np.ones(n), (r, a)), (n, nT + 0))])
    return X1
def design2(l, h, a):
    """ordre des colonnes : [championnat (niveau), championnat (avantage dom.), attaque équipe, défense équipe]."""
    n = len(l); r = np.arange(n)
    Lc = sp.csr_matrix((np.full(n, 10.0), (r, l)), (n, nL)); Z = sp.csr_matrix((n, nL)); 
    Hc = Lc
    # ligne « buts du domicile » : niveau + avantage ; att[h] + def[a]
    A_h = sp.csr_matrix((np.ones(n), (r, h)), (n, nT)); D_a = sp.csr_matrix((np.ones(n), (r, a)), (n, nT)); Zt = sp.csr_matrix((n, nT))
    top = sp.hstack([Lc, Hc, A_h, Zt, Zt, D_a])
    # ligne « buts de l'extérieur » : niveau ; att[a] + def[h]
    A_a = sp.csr_matrix((np.ones(n), (r, a)), (n, nT)); D_h = sp.csr_matrix((np.ones(n), (r, h)), (n, nT))
    bot = sp.hstack([Lc, Z, Zt, A_a, D_h, Zt])
    return top, bot
# colonnes : [niveau L(nL)] [avantage H(nL)] [att pour domicile? ] -> on utilise des colonnes att (nT) et def (nT) partagées
def design3(l, h, a):
    n = len(l); r = np.arange(n)
    Lc = sp.csr_matrix((np.full(n, 10.0), (r, l)), (n, nL)); Hc = Lc; Z = sp.csr_matrix((n, nL))
    att = lambda t: sp.csr_matrix((np.ones(n), (r, t)), (n, nT))
    top = sp.hstack([Lc, Hc, att(h), att(a) * 0 + sp.csr_matrix((n, nT))]).tocsr() if False else None
    return None
def build(l, h, a):
    n = len(l); r = np.arange(n); one = np.ones(n)
    S = lambda c, k: sp.csr_matrix((one, (r, c)), (n, k))
    Lc = S(l, nL) * 10.0; Z = sp.csr_matrix((n, nL)); Zt = sp.csr_matrix((n, nT))
    top = sp.hstack([Lc, Lc, S(h, nT), Zt, S(a, nT) * 0, Zt])      # remplacé plus bas : on utilise 2 blocs att/def
    return top
def mat(l, h, a):
    """lignes domicile puis extérieur ; colonnes : niveau(nL) | avantage dom.(nL) | attaque(nT) | défense(nT)."""
    n = len(l); r = np.arange(n); one = np.ones(n)
    S = lambda c, k: sp.csr_matrix((one, (r, c)), (n, k))
    Lc = S(l, nL) * 10.0; Z = sp.csr_matrix((n, nL))
    top = sp.hstack([Lc, Lc, S(h, nT), S(a, nT)]); bot = sp.hstack([Lc, Z, S(a, nT), S(h, nT)])
    return sp.vstack([top, bot]).tocsr()
def ajuster(tmax, xi, alpha, fenetre=800):
    m = (dates < tmax) & (dates >= tmax - fenetre)
    if m.sum() < 500: return None
    Xm = mat(lgi[m], hi[m], ai[m]); y = np.r_[gh[m], ga[m]]; age = tmax - dates[m]; w = np.exp(-xi * age); w = np.r_[w, w]
    return PoissonRegressor(alpha=alpha, max_iter=300, tol=1e-6).fit(Xm, y, sample_weight=w / w.mean())
def lam(mod, l, h, a):
    n = len(l); X = mat(l, h, a); p = mod.predict(X); return p[:n], p[n:]
# lignes analysables du tableau commun (même ordre que la table) : on les retrouve par identifiant
T = np.load("sorties/table2_bloc_tous.npz", allow_pickle=True); ids = list(T["id"]); P_cur = T["P"]; Y = T["Y"]
idx = {m["id"]: m for m in mb}
mrow = [idx[i] for i in ids]
jr = np.array([D(m["jour"]) for m in mrow]); lr_ = np.array([LG[m["competition"]] for m in mrow]); hr = np.array([TM[(m["competition"], m["domicile"])] for m in mrow]); ar = np.array([TM[(m["competition"], m["exterieur"])] for m in mrow])
hh = np.array([sb[m["id"]][0] for m in mrow], int); aa = np.array([sb[m["id"]][1] for m in mrow], int)
# lambdas du modèle actuel
Lc_ = np.array([C.lambdas(C.features(m, lig), None, 0.328, "gd") for m in mrow])
d0 = D("2025-09-01"); dV = D("2026-02-01")          # V : [2025-09-01, 2026-02-01[ validation ; T : à partir du 2026-02-01
print(f"lignes {len(mrow)} ; V={int(((jr>=d0)&(jr<dV)).sum())} ; T={int((jr>=dV).sum())} ; équipes {nT} ; championnats {nL} ; préparation {time.time()-t0:.0f}s", flush=True)
def walk(xi, alpha, lo, hi_, pas=14):
    la = np.full(len(mrow), np.nan); lb = np.full(len(mrow), np.nan); t = lo
    while t < hi_:
        sel = (jr >= t) & (jr < min(t + pas, hi_))
        if sel.any():
            mod = ajuster(t, xi, alpha)
            if mod is not None: la[sel], lb[sel] = lam(mod, lr_[sel], hr[sel], ar[sel])
        t += pas
    return la, lb
def ll_scores(la, lb, sel): return C.perte_scores(la[sel], lb[sel], hh[sel], aa[sel])
selV = (jr >= d0) & (jr < dV); selT = jr >= dV
print("modèle actuel : perte V", round(ll_scores(Lc_[:, 0], Lc_[:, 1], selV), 5), "T", round(ll_scores(Lc_[:, 0], Lc_[:, 1], selT), 5))
res = {}
for xi_j in (0.0, np.log(2) / 540, np.log(2) / 270, np.log(2) / 120):
    for alpha in (0.0003, 0.001, 0.003, 0.01, 0.03):
        la, lb = walk(xi_j, alpha, d0, dV)
        v = ~np.isnan(la) & selV; res[(xi_j, alpha)] = ll_scores(la, lb, v)
        print(f"V : demi-vie {np.log(2)/xi_j if xi_j else np.inf:6.0f} j, alpha {alpha}: perte {res[(xi_j, alpha)]:.5f}  (modèle actuel sur les mêmes matchs {ll_scores(Lc_[:,0], Lc_[:,1], v):.5f}, n={int(v.sum())}) {time.time()-t0:.0f}s", flush=True)
best = min(res, key=res.get); print("réglage retenu sur V :", best, flush=True)
laV, lbV = walk(best[0], best[1], d0, dV)
la, lb = walk(best[0], best[1], dV, D("2026-10-17"))
np.savez_compressed("sorties/e13_dc_lambdas.npz", la=np.where(np.isnan(la), laV, la), lb=np.where(np.isnan(lb), lbV, lb), id=np.array(ids), cur=Lc_, jr=jr)
v = ~np.isnan(la) & selT
print(f"T : n={int(v.sum())} perte nouveau {ll_scores(la, lb, v):.5f} | modèle actuel {ll_scores(Lc_[:,0], Lc_[:,1], v):.5f} | mélange moyenne des λ {ll_scores((la+Lc_[:,0])/2, (lb+Lc_[:,1])/2, v):.5f}")
