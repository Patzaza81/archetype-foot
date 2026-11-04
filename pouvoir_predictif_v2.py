"""Etape 2b: recherche de solutions pour ameliorer le pouvoir predictif (scores + tirs/cadres si disponibles).
Methodes ajoutees aux familles P1/P2/F de `pouvoir_predictif.py`:
  - variables croisees: ecart de force Elo en buts (pas K choisi sur le passe), forme (5 derniers matchs), repos, buts attendus Poisson (domicile, exterieur, total), taille de l'historique,
    tirs cadres attendus (competitions ou la colonne existe);
  - META: regression logistique (par marche) qui combine les probabilites des familles, la reference et ces variables; regularisation choisie sur la saison precedente;
  - versions: LOC (entrainee sur la competition), POOL (toutes competitions, strictement avant la 1re saison test), SOT (LOC + tirs cadres si dispo);
  - SEL: choix par donnees (saison de validation s-1) parmi toutes les methodes (familles de base, LOC, POOL, SOT, et leurs regularisations).
Chronologie: pour la saison test s, tout (familles, Elo, regularisation, choix de methode) est decide avec des matchs anterieurs a s; la saison s-1 sert de validation.
Saisons test: 2324, 2425, 2526. Aucune cote, aucun ROI; archives en lecture seule; scores joues."""
import csv, json, math, os, sys
import numpy as np
from statistics import NormalDist
import pouvoir_predictif as pp
RACINE = pp.RACINE
SAISONS = pp.SAISONS; EVT = pp.EVT; MARCHES = pp.MARCHES
TESTS = [2, 3, 4]
LAM_GRILLE = [0.1, 1.0, 10.0, 100.0, 1000.0]
K_ELO = [0.01, 0.03, 0.1, 0.2]
EPS = 1e-9

def charger_sot(code):
    """Tirs cadres (HST, AST) alignes sur pp.charger(code) (meme tri); NaN si absent. Retourne (N,2) ou None si la colonne n'existe pas."""
    out = []; present = False
    for s in SAISONS:
        for p in (os.path.join(pp.SNAP, s, "raw", code + ".csv"), os.path.join(pp.SNAP, s, "nouvelles_ligues", "raw", code + ".csv")):
            if not os.path.exists(p): continue
            R = pp._lire(p)
            if not R: continue
            hk, ak = ("HomeTeam", "AwayTeam") if "HomeTeam" in R[0] else ("Home", "Away")
            gh, ga = ("FTHG", "FTAG") if "FTHG" in R[0] else ("HG", "AG")
            for r in R:
                try: int(float(r[gh])), int(float(r[ga]))
                except (ValueError, TypeError, KeyError): continue
                d = pp._date(r.get("Date", ""))
                if d is None or not r[hk] or not r[ak]: continue
                try: x = (float(r["HST"]), float(r["AST"])); present = True
                except (ValueError, TypeError, KeyError): x = (float("nan"), float("nan"))
                out.append((d, SAISONS.index(s), x))
            break
    out.sort(key=lambda m: (m[0], m[1]))
    return np.array([m[2] for m in out]) if present else None

def extras(matchs, K, sot=None, k_sot=10):
    """Variables causales (N, d): [ecart Elo en buts, |ecart|, forme points, forme diff de buts, repos, log tirs cadres att. dom, ext] ; NaN pour les 2 dernieres si pas de tirs."""
    N = len(matchs); X = np.zeros((N, 7)); X[:, 5:] = np.nan
    elo = {}; hist = {}; dernier = {}; sots = {}   # sots: equipe -> [n, pour, contre]
    ga = [0.0, 0]; gs = [0.0, 0.0, 0]              # somme diff de buts / n ; somme tirs cadres dom, ext / n
    i = 0
    while i < N:
        j = i
        while j < N and matchs[j][0] == matchs[i][0]: j += 1
        jour = matchs[i][0]
        for t in range(i, j):
            _, _, h, a, _, _ = matchs[t]
            X[t, 0] = elo.get(h, 0.0) - elo.get(a, 0.0); X[t, 1] = abs(X[t, 0])
            fh, fa = hist.get(h, []), hist.get(a, [])
            if fh and fa:
                X[t, 2] = np.mean([x[0] for x in fh]) - np.mean([x[0] for x in fa]); X[t, 3] = np.mean([x[1] for x in fh]) - np.mean([x[1] for x in fa])
            rh = min(jour - dernier[h], 60) if h in dernier else 60; ra = min(jour - dernier[a], 60) if a in dernier else 60
            X[t, 4] = math.log1p(rh) - math.log1p(ra)
            if sot is not None and gs[2] > 0:
                Lh, La = gs[0] / gs[2], gs[1] / gs[2]; g = (Lh + La) / 2
                sh = sots.get(h, [0, 0, 0]); sa = sots.get(a, [0, 0, 0])
                att_h = (sh[1] + k_sot * g) / (sh[0] + k_sot); def_h = (sh[2] + k_sot * g) / (sh[0] + k_sot)
                att_a = (sa[1] + k_sot * g) / (sa[0] + k_sot); def_a = (sa[2] + k_sot * g) / (sa[0] + k_sot)
                X[t, 5] = math.log(max(att_h * def_a / g * Lh / g, 1e-6)); X[t, 6] = math.log(max(att_a * def_h / g * La / g, 1e-6))
        for t in range(i, j):
            _, _, h, a, bd, ba = matchs[t]
            ha = ga[0] / ga[1] if ga[1] else 0.0
            err = (bd - ba) - (elo.get(h, 0.0) - elo.get(a, 0.0) + ha)
            elo[h] = elo.get(h, 0.0) + K * err; elo[a] = elo.get(a, 0.0) - K * err
            pts_h = 3 if bd > ba else (1 if bd == ba else 0)
            hist.setdefault(h, []).append((pts_h, bd - ba)); hist.setdefault(a, []).append((3 - pts_h if pts_h != 1 else 1, ba - bd))
            hist[h] = hist[h][-5:]; hist[a] = hist[a][-5:]
            dernier[h] = jour; dernier[a] = jour
            ga[0] += bd - ba; ga[1] += 1
            if sot is not None and not (math.isnan(sot[t][0]) or math.isnan(sot[t][1])):
                for eq, pour, contre in ((h, sot[t][0], sot[t][1]), (a, sot[t][1], sot[t][0])):
                    q = sots.setdefault(eq, [0, 0.0, 0.0]); q[0] += 1; q[1] += pour; q[2] += contre
                gs[0] += sot[t][0]; gs[1] += sot[t][1]; gs[2] += 1
        i = j
    return X

def elo_pred_gd(matchs, K):
    """Prediction de difference de buts de l'Elo (pour choisir K sur le passe) : (N,) NaN avant donnees."""
    X = extras(matchs, K); return X[:, 0]

def ajuster(X, y, lam, it=30):
    mu, sd = X.mean(0), X.std(0); sd[sd < 1e-9] = 1.0
    Z = np.hstack([np.ones((len(X), 1)), (X - mu) / sd]); w = np.zeros(Z.shape[1]); R = np.eye(Z.shape[1]) * lam; R[0, 0] = 0
    for _ in range(it):
        p = 1 / (1 + np.exp(-np.clip(Z @ w, -30, 30))); g = Z.T @ (p - y) + R @ w
        H = (Z * (p * (1 - p))[:, None]).T @ Z + R + 1e-8 * np.eye(len(w))
        step = np.linalg.solve(H, g); w -= step
        if np.abs(step).max() < 1e-7: break
    return mu, sd, w

def predire_logit(modele, X):
    mu, sd, w = modele; Z = np.hstack([np.ones((len(X), 1)), (X - mu) / sd]); return np.clip(1 / (1 + np.exp(-np.clip(Z @ w, -30, 30))), EPS, 1 - EPS)

def lb(p, y): return -(y * np.log(p) + (1 - y) * np.log(1 - p))

class Comp:
    def __init__(self, code):
        self.code = code; self.M = pp.charger(code); self.N = len(self.M)
        self.ok = self.N >= 50
        if not self.ok: return
        self.S = np.array([SAISONS.index(m[1]) for m in self.M]); self.D = np.array([m[0] for m in self.M]); self.Y = pp.issues(self.M)
        self.ref = pp.reference(self.M); self.valide = ~np.isnan(self.ref[:, 0])
        self.sot = charger_sot(code)
        if self.sot is not None: assert len(self.sot) == self.N
        self.base = {}; self.mu = {}
        for f in pp.FAMILLES:
            for k in pp.K_GRILLE:
                for hl in pp.HL_GRILLE:
                    r = pp.predire(self.M, f, k, hl, ret_mu=(f == "P1"))
                    if f == "P1": P, mu = r; self.mu[(k, hl)] = mu
                    else: P = r
                    self.base[(f, k, hl)] = P
        self.elo = {K: elo_pred_gd(self.M, K) for K in K_ELO}
        self.gd = np.array([m[4] - m[5] for m in self.M], float)
        self.start = {s: self.D[self.S == s].min() for s in range(5) if (self.S == s).any()}
    def cfg(self, f, e, s):
        """configuration de la famille f choisie pour l'evenement e sur les saisons < s (perte binaire)"""
        tr = self.valide & (self.S < s)
        return min(((f, k, hl) for k in pp.K_GRILLE for hl in pp.HL_GRILLE), key=lambda c: lb(np.nan_to_num(self.base[c][tr, e], nan=.5).clip(EPS, 1 - EPS), self.Y[tr, e]).mean())
    def features(self, e, s):
        """(X_basique (N,12), X_sot (N,14) ou None, preds des familles) pour l'evenement e et la saison test s: tout choisi avec les saisons < s"""
        tr = self.valide & (self.S < s)
        c = {f: self.cfg(f, e, s) for f in pp.FAMILLES}
        K = min(K_ELO, key=lambda K: np.nanmean((self.elo[K][tr] - self.gd[tr]) ** 2) if tr.any() else 0)
        k1 = c["P1"][1]; mu = self.mu[(c["P1"][1], c["P1"][2])]
        pr = {f: np.nan_to_num(self.base[c[f]][:, e], nan=.5) for f in pp.FAMILLES}
        ex = extras(self.M, K, self.sot, k_sot=k1)
        hist = np.log1p(np.arange(self.N))
        lg = lambda p: np.log(p / (1 - p))
        mu = np.nan_to_num(mu, nan=1.2)
        Xb = np.column_stack([lg(pr["P1"]), lg(pr["P2"]), lg(pr["F"]), lg(np.nan_to_num(self.ref[:, e], nan=.5).clip(EPS, 1 - EPS)), ex[:, :5],
                              np.log(np.maximum(mu[:, 0], 1e-3)), np.log(np.maximum(mu[:, 1], 1e-3)), np.log(np.maximum(mu.sum(1), 1e-3))])
        Xs = None
        if self.sot is not None: Xs = np.column_stack([Xb, np.nan_to_num(ex[:, 5:], nan=0.0)])
        return Xb, Xs, pr

def analyser_tout(codes, verbeux=True):
    C = {c: Comp(c) for c in codes}; C = {c: x for c, x in C.items() if x.ok}
    # pred[code][variante][s] -> (N,7) probabilites pour les matchs de la saison s (NaN ailleurs)
    pred = {c: {} for c in C}; info = {c: {} for c in C}
    for s in TESTS:
        gstart = min(x.start[s] for x in C.values() if s in x.start); gstart_val = min(x.start[s - 1] for x in C.values() if (s - 1) in x.start)
        for e in range(7):
            F = {c: C[c].features(e, s) for c in C}
            # POOL: modeles entraines sur toutes les competitions, strictement avant le 1er match de la saison s (final) ou s-1 (validation)
            def pool(cut, lam):
                Xs, ys = [], []
                for c, x in C.items():
                    m = x.valide & (x.D < cut)
                    if m.any(): Xs.append(F[c][0][m]); ys.append(x.Y[m, e])
                return ajuster(np.vstack(Xs), np.concatenate(ys), lam)
            pool_val = {lam: pool(gstart_val, lam) for lam in LAM_GRILLE}; pool_fin = {lam: pool(gstart, lam) for lam in LAM_GRILLE}
            for c, x in C.items():
                if s not in x.start or (s - 1) not in x.start: continue
                Xb, Xs, pr = F[c]
                te = x.valide & (x.S == s); va = x.valide & (x.S == s - 1)
                tr_val = x.valide & (x.D < x.start[s - 1]); tr_fin = x.valide & (x.D < x.start[s])
                cands = {}                     # nom -> (perte validation, probas test)
                for f in pp.FAMILLES: cands[f] = (lb(pr[f][va], x.Y[va, e]).mean(), pr[f][te])
                if tr_val.sum() > 30 and va.any():
                    for nom, X in (("LOC", Xb), ("SOT", Xs)):
                        if X is None: continue
                        for lam in LAM_GRILLE:
                            mv = ajuster(X[tr_val], x.Y[tr_val, e], lam); mf = ajuster(X[tr_fin], x.Y[tr_fin, e], lam)
                            cands[f"{nom}@{lam}"] = (lb(predire_logit(mv, X[va]), x.Y[va, e]).mean(), predire_logit(mf, X[te]))
                    for lam in LAM_GRILLE:
                        cands[f"POOL@{lam}"] = (lb(predire_logit(pool_val[lam], Xb[va]), x.Y[va, e]).mean(), predire_logit(pool_fin[lam], Xb[te]))
                def meilleur(prefixe):
                    ks = [k for k in cands if k == prefixe or k.startswith(prefixe + "@")]
                    return min(ks, key=lambda k: cands[k][0]) if ks else None
                choix = {"P1": "P1", "P2": "P2", "F": "F"}
                for v in ("LOC", "POOL", "SOT"):
                    b = meilleur(v)
                    if b: choix[v] = b
                choix["SEL"] = min(cands, key=lambda k: cands[k][0])
                for v, k in choix.items():
                    arr = pred[c].setdefault(v, {}).setdefault(s, np.full((x.N, 7), np.nan)); arr[te, e] = cands[k][1]
                info[c].setdefault(s, {})[EVT[e]] = {"SEL": choix["SEL"], "val_loss": {k: round(float(cands[k][0]), 5) for k in ("P1", "P2", "F")}}
        if verbeux: print("saison test", SAISONS[s], "ok", flush=True)
    return C, pred, info

def evaluer(C, pred, info):
    sortie = {}; variantes = ["P1", "P2", "F", "LOC", "POOL", "SOT", "SEL"]
    for c, x in C.items():
        res = {}
        masque = x.valide & np.isin(x.S, TESTS)
        if not masque.any(): continue
        Yt = x.Y[masque]; refP = x.ref[masque]; Lr, Br = pp.pertes(refP, Yt); Hr = pp.succes(refP, Yt)
        for v in variantes:
            if v not in pred[c]: continue
            P = np.full((x.N, 7), np.nan)
            for s in TESTS:
                if s in pred[c][v]: P[x.S == s] = pred[c][v][s][x.S == s]
            P = P[masque]
            if np.isnan(P).any(): continue
            P3 = P.copy(); P3[:, :3] = P3[:, :3] / P3[:, :3].sum(axis=1, keepdims=True)           # 1X2 renormalise
            L, B = pp.pertes(np.clip(P3, EPS, 1 - EPS), Yt); H = pp.succes(P3, Yt)
            for mi, mk in enumerate(MARCHES):
                d = Lr[:, mi] - L[:, mi]; n = len(d); m = float(d.mean()); se = float(d.std(ddof=1) / math.sqrt(n))
                par = {SAISONS[s]: round(float(d[x.S[masque] == s].mean()), 5) for s in TESTS if (x.S[masque] == s).any()}
                res[f"{v}|{mk}"] = {"methode": v, "marche": mk, "n": n, "gain_logloss": round(m, 5), "z": round(m / se, 2) if se > 0 else None,
                                    "gain_brier": round(float((Br[:, mi] - B[:, mi]).mean()), 5), "reussite": round(float(H[:, mi].mean()), 4), "reussite_ref": round(float(Hr[:, mi].mean()), 4),
                                    "gain_par_saison": par, "saisons_gagnantes": f"{sum(1 for q in par.values() if q > 0)}/{len(par)}"}
        sortie[c] = {"n_test": int(masque.sum()), "resultats": res, "choix_SEL": {SAISONS[s]: info[c].get(s, {}) for s in TESTS}}
    return sortie

def main(codes=None):
    cl = json.load(open(os.path.join(RACINE, "data", "inventaire", "classement_descriptif.json"), encoding="utf-8"))["competitions"]
    codes = codes or sorted(cl)
    C, pred, info = analyser_tout(codes); S = evaluer(C, pred, info)
    n = sum(len(v["resultats"]) for v in S.values()); zb = NormalDist().inv_cdf(1 - 0.05 / n)
    for v in S.values():
        for r in v["resultats"].values():
            gagn = sum(1 for q in r["gain_par_saison"].values() if q > 0); tot = len(r["gain_par_saison"])
            r["verdict"] = "aucun_avantage" if (r["z"] is None or r["gain_logloss"] <= 0) else ("avantage_robuste" if r["z"] > zb and gagn == tot else ("avantage" if r["z"] > 1.96 and gagn == tot else "indetermine"))
    doc = {"description": "Etape 2b: methodes combinees (voir en-tete de pouvoir_predictif_v2.py). Gain = perte log (reference - methode) par match sur 2324-2526; >0 = bat la frequence historique.", "tests_total": n, "z_bonferroni": round(zb, 2), "competitions": S}
    json.dump(doc, open(os.path.join(RACINE, "data", "inventaire", "pouvoir_predictif_v2.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return doc

if __name__ == "__main__":
    main(sys.argv[1:] or None)
