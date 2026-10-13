"""V2 calibré SUR L'ÉCHANTILLON CONNU (résultats vus). Le ROI affiché est un ROI sur échantillon : il n'est PAS
une preuve prédictive. Règle : on garde les cellules (libellé, tranche de cote) rentables sur l'échantillon,
avec un minimum de paris par cellule, et au plus 1 pari par match (meilleur ROI de cellule)."""
import re

PAS_COTE = 0.25


def tranche(cote):
    return int((cote - 1.0) / PAS_COTE)


def cle(lib, cote):
    return (re.sub(r"\s+", " ", lib), tranche(cote))


def ajuste_cellules(lignes, min_paris=10, roi_min=0.30):
    """lignes: dicts lib, o, profit. Retourne {cellule: roi} des cellules retenues."""
    acc = {}
    for l in lignes:
        a = acc.setdefault(cle(l["lib"], l["o"]), [0.0, 0])
        a[0] += l["profit"]; a[1] += 1
    return {k: s / n for k, (s, n) in acc.items() if n >= min_paris and s / n >= roi_min}


def choisir(lignes, cellules, max_par_match=1):
    par = {}
    for l in lignes:
        k = cle(l["lib"], l["o"])
        if k in cellules:
            par.setdefault(l["mid"], []).append((cellules[k], l))
    out = []
    for mid in sorted(par):
        B = sorted(par[mid], key=lambda t: (-t[0], t[1]["lib"]))
        out += [l for _, l in B[:max_par_match]]
    return out


def main():
    from . import evaluation as E, modele as M
    from .donnees import charge
    Ms = charge()
    L = E.lignes(Ms, M.prior_ligue([m["hd"] + m["he"] for m in Ms]))
    c = ajuste_cellules(L)
    S = choisir(L, c)
    print("ROI SUR ECHANTILLON (non predictif) | cellules:", len(c), "paris:", len(S),
          "reussite:", round(sum(1 for l in S if l["r"] == 1) / max(1, len(S)), 3),
          "ROI:", round(E.roi(S), 3), "IC95 (echantillon):", E.bootstrap(S, 500))


if __name__ == "__main__":
    main()
