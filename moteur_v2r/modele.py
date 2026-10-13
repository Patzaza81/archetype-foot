"""Modèle de buts (Poisson contracté vers la moyenne de ligue) + probabilités par libellé."""
import math
import journal_rentabilite as J

MAXG = 10
PARAMS = dict(k0=1.0, wsame=0.3, s=0.7, d=0.0)


def poisson_row(lam, n=MAXG + 1):
    p = [math.exp(-lam)]
    for k in range(1, n):
        p.append(p[-1] * lam / k)
    s = sum(p)
    return [x / s for x in p]


def _somme(hist, lieu_dom, cle):
    L = [x for x in hist if x["domicile"] == lieu_dom]
    return sum(x[cle] for x in L), len(L)


def _tous(hist, cle):
    return sum(x[cle] for x in hist), len(hist)


def _contracte(sn, prior, k0):
    s, n = sn
    return (s + k0 * prior) / (n + k0)


def prior_ligue(historiques):
    """Moyennes de buts marqués à domicile / à l'extérieur / globale sur un ensemble d'historiques."""
    h = nh = a = na = 0
    for hist in historiques:
        for x in hist:
            if x["domicile"]:
                h += x["buts_marques"]; nh += 1
            else:
                a += x["buts_marques"]; na += 1
    ph = h / nh if nh else 1.5
    pa = a / na if na else 1.2
    n = nh + na
    return dict(h=ph, a=pa, all=(h + a) / n if n else 1.35)


def lambdas(hd, he, pri, P=PARAMS):
    k0, w = P["k0"], P["wsame"]
    def mix(same, alls, p_same):
        return w * _contracte(same, p_same, k0) + (1 - w) * _contracte(alls, pri["all"], k0)
    att_d = mix(_somme(hd, True, "buts_marques"), _tous(hd, "buts_marques"), pri["h"])
    def_d = mix(_somme(hd, True, "buts_encaisses"), _tous(hd, "buts_encaisses"), pri["a"])
    att_e = mix(_somme(he, False, "buts_marques"), _tous(he, "buts_marques"), pri["a"])
    def_e = mix(_somme(he, False, "buts_encaisses"), _tous(he, "buts_encaisses"), pri["h"])
    ld = pri["h"] + P["s"] * ((att_d + def_e) / 2 - pri["h"])
    le = pri["a"] + P["s"] * ((att_e + def_d) / 2 - pri["a"])
    return max(ld, 0.15), max(le, 0.15)


def grille(ld, le):
    pd, pe = poisson_row(ld), poisson_row(le)
    return [[pd[i] * pe[j] for j in range(MAXG + 1)] for i in range(MAXG + 1)]


def probas(G, libelles):
    """{libellé: (p_gagne, p_rembourse)} ; libellés non reconnus ignorés."""
    out = {}
    for lib in libelles:
        an = J.analyse_libelle(lib)
        if an is None:
            continue
        f = an[1]
        pw = pp = 0.0
        for i in range(MAXG + 1):
            for j in range(MAXG + 1):
                r = f(i, j)
                if r == 1:
                    pw += G[i][j]
                elif r == 0:
                    pp += G[i][j]
        out[lib] = (pw, pp)
    return out
