"""V2 calibré sur l'échantillon AVEC historiques de buts : chaque pari reçoit le profil de buts du championnat
(moyenne de buts/match de la compétition d'après les historiques) et celui du match (buts attendus du modèle).
Cellule = (libellé, tranche de cote, classe de championnat, classe de match). ROI = ROI sur échantillon."""
from . import echantillon as X, evaluation as E, modele as M

COUPURES_LIGUE = (2.5, 2.9)     # buts/match : bas < 2.5 <= moyen < 2.9 <= haut
COUPURES_MATCH = (2.4, 3.0)     # buts attendus du modèle


def classe(v, coupures):
    return sum(1 for c in coupures if v >= c)


def moyenne_buts_ligue(matchs):
    acc = {}
    for m in matchs:
        for x in m["hd"] + m["he"]:
            a = acc.setdefault(m["ligue"], [0, 0])
            a[0] += x["buts_marques"] + x["buts_encaisses"]; a[1] += 1
    return {k: s / n for k, (s, n) in acc.items() if n}


def lignes_profil(matchs, P=M.PARAMS):
    pri = M.prior_ligue([m["hd"] + m["he"] for m in matchs])
    ml = moyenne_buts_ligue(matchs)
    L = []
    for m in matchs:
        ld, le = M.lambdas(m["hd"], m["he"], pri, P)
        cl = classe(ml.get(m["ligue"], pri["all"] * 2), COUPURES_LIGUE)
        cm = classe(ld + le, COUPURES_MATCH)
        for l in E.lignes([m], pri, P):
            l["profil"] = (cl, cm)
            L.append(l)
    return L


def cle(l):
    lib, tr = X.cle(l["lib"], l["o"])
    return (lib, tr) + tuple(l["profil"])


def ajuste(lignes, min_paris=10, roi_min=0.30):
    acc = {}
    for l in lignes:
        a = acc.setdefault(cle(l), [0.0, 0])
        a[0] += l["profit"]; a[1] += 1
    return {k: s / n for k, (s, n) in acc.items() if n >= min_paris and s / n >= roi_min}


def choisir(lignes, cellules, max_par_match=1):
    par = {}
    for l in lignes:
        k = cle(l)
        if k in cellules:
            par.setdefault(l["mid"], []).append((cellules[k], l))
    out = []
    for mid in sorted(par):
        B = sorted(par[mid], key=lambda t: (-t[0], t[1]["lib"]))
        out += [l for _, l in B[:max_par_match]]
    return out


def main():
    from .donnees import charge
    L = lignes_profil(charge())
    for mp, rm in ((10, 0.30), (10, 0.50), (8, 0.60), (6, 0.60)):
        c = ajuste(L, mp, rm); S = choisir(L, c)
        print(mp, rm, "cellules:", len(c), "paris:", len(S),
              "reussite:", round(sum(1 for l in S if l["r"] == 1) / max(1, len(S)), 3),
              "ROI:", round(E.roi(S) or 0, 3))


if __name__ == "__main__":
    main()
