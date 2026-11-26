import pandas as pd, math
EH, EA = 1.3808616267615823, 1.5668783441905885
def w(k, n, z=1.96):
    p = k/n; d = 1+z*z/n; c = p+z*z/(2*n); r = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)); return (c-r)/d
def bloc(nom, t):
    t = t[(t.EH < EH) & (t.EA < EA) & (t.nL >= 10)]
    ok = (t.bd + t.be) < 4; nv = t.SM <= 3.1
    n0, k0 = len(t), int(ok.sum()); n1, k1 = int(nv.sum()), int(ok[nv].sum()); n2, k2 = n0-n1, k0-k1
    print(f"{nom:28} | ancienne {k0/n0:.1%} ({n0}) | nouvelle {k1/n1:.1%} ({n1}) | écart {100*(k1/n1-k0/n0):+.1f} pt | écartés {n2} : {k2/n2:.1%} gagnants" if n2 else f"{nom}: rien d'écarté")
g = pd.read_csv("etude_n/t_grand.csv"); g["an"] = g.date.str[:4].astype(int)
bloc("2000-2016 (recherche)", g[g.an <= 2016])
bloc("2017-2020 (jamais vus)", g[(g.an >= 2017) & (g.an <= 2020)])
bloc("2021 (jamais vus)", g[g.an >= 2021])
bloc("Bloc 2025-26 (jamais vus)", pd.read_csv("etude_n/t_bloc.csv"))
bloc("Matchs Betpawa du système", pd.read_csv("etude_n/t_flux.csv"))
bloc("TOUT", pd.concat([g, pd.read_csv("etude_n/t_bloc.csv"), pd.read_csv("etude_n/t_flux.csv")]))
