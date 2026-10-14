"""ATTENTION (14/10/2026) : ce module évalue l'ANCIEN modèle (calibration + Poisson), PAS le moteur v2r à cellules.
Pour tester v2r : python -m moteur_v2r.backtest AAAA-MM-JJ [...] (moteur_v2r/backtest.py). Ici ne servent plus que
les outils de règlement (lignes, roi, bootstrap).

Évaluation chronologique (walk-forward) : à chaque bloc, calibration + seuil appris UNIQUEMENT sur le passé.
Sortie : ROI hors échantillon, intervalle bootstrap par match, comparaison au hasard (tout parier)."""
import random

import journal_rentabilite as J
from . import calibration as C, modele as M, selection as S

GRILLE_SEUIL = (0.0, 0.03, 0.06, 0.10)
GRILLE_BANDES = ((1.01, 999.0), (1.3, 3.0), (1.3, 2.0), (1.8, 3.5))


def lignes(matchs, pri, P=M.PARAMS):
    L = []
    for m in matchs:
        ld, le = M.lambdas(m["hd"], m["he"], pri, P)
        pr = M.probas(M.grille(ld, le), m["cotes"].keys())
        for lib, (pw, pp) in pr.items():
            an = J.analyse_libelle(lib)
            r = an[1](m["h"], m["a"])
            if r is None:
                continue
            o = m["cotes"][lib]
            L.append(dict(mid=m["id"], date=m["date"], lib=lib, o=o, pw=pw, pp=pp, r=r,
                          y=1 if r == 1 else 0, profit=(o - 1) if r == 1 else (0.0 if r == 0 else -1.0)))
    return L


def roi(S_):
    return sum(l["profit"] for l in S_) / len(S_) if S_ else None


def bootstrap(S_, n=2000, graine=1):
    """IC 95 % de l'ROI, rééchantillonnage PAR MATCH (les paris d'un même match sont corrélés)."""
    if not S_:
        return None
    par = {}
    for l in S_:
        par.setdefault(l["mid"], []).append(l["profit"])
    ids = sorted(par)
    rnd = random.Random(graine)
    v = []
    for _ in range(n):
        tot = k = 0
        for _ in ids:
            p = par[rnd.choice(ids)]
            tot += sum(p); k += len(p)
        v.append(tot / k)
    v.sort()
    return v[int(0.025 * n)], v[int(0.975 * n)]


def _calibre(L, w):
    for l in L:
        l["pc"] = C.proba_calibree(w, l["pw"], l["o"])
        l["ev"] = S.ev(l["pc"], l["o"])
    return L


def apprend(matchs_passe):
    pri = M.prior_ligue([m["hd"] + m["he"] for m in matchs_passe])
    L = lignes(matchs_passe, pri)
    w = C.ajuste([C.features(l["pw"], l["o"]) for l in L], [l["y"] for l in L])
    _calibre(L, w)
    # meilleur couple (seuil, bande) sur le passé, minimum 80 paris ; sinon None = ne rien proposer
    meilleur = None
    for tau in GRILLE_SEUIL:
        for lo, hi in GRILLE_BANDES:
            sel = S.choisir(L, tau, lo, hi)
            if len(sel) >= 80:
                r = roi(sel)
                if r > 0 and (meilleur is None or r > meilleur[0]):
                    meilleur = (r, tau, lo, hi)
    return dict(pri=pri, w=w, regle=meilleur)


def walk_forward(matchs, part_depart=0.4, blocs=6):
    dates = sorted({m["date"] for m in matchs})
    debut = dates[int(len(dates) * part_depart)]
    futur = [d for d in dates if d >= debut]
    taille = max(1, len(futur) // blocs)
    coupes = [futur[i] for i in range(0, len(futur), taille)][:blocs]
    sel_tot, hasard_tot, journal = [], [], []
    for i, c in enumerate(coupes):
        fin = coupes[i + 1] if i + 1 < len(coupes) else "9999"
        passe = [m for m in matchs if m["date"] < c]
        test = [m for m in matchs if c <= m["date"] < fin]
        if not passe or not test:
            continue
        mod = apprend(passe)
        Lt = _calibre(lignes(test, mod["pri"]), mod["w"])
        hasard_tot += Lt
        if mod["regle"]:
            _, tau, lo, hi = mod["regle"]
            sel = S.choisir(Lt, tau, lo, hi)
        else:
            sel = []
        sel_tot += sel
        journal.append(dict(bloc=i, debut=c, regle=mod["regle"], paris=len(sel), roi=roi(sel)))
    return dict(selection=sel_tot, hasard=hasard_tot, journal=journal,
                roi=roi(sel_tot), ic=bootstrap(sel_tot), roi_hasard=roi(hasard_tot))


def main():
    from .donnees import charge
    r = walk_forward(charge())
    for j in r["journal"]:
        print(j)
    print("paris:", len(r["selection"]), "ROI:", r["roi"], "IC95:", r["ic"], "| hasard:", r["roi_hasard"])


if __name__ == "__main__":
    main()
