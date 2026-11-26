# Analyse Verdict « moins de 3,5 » (seul + combos) : verdict de base (des deux côtés, pari passé plus souvent que raté, même lieu, saison en cours, avant le match, 4 matchs mini)
# ancienne = verdict TIENT / TIENT AVEC RÉSERVE ; nouvelle = idem + (buts marqués domicile à domicile + extérieur dehors) <= 3,1
import pandas as pd, collections
M = {"Moins de 3,5": lambda h, a: h + a < 4, "1 & -3,5": lambda h, a: h > a and h + a < 4, "N & -3,5": lambda h, a: h == a and h + a < 4, "2 & -3,5": lambda h, a: h < a and h + a < 4,
     "1N & -3,5": lambda h, a: h >= a and h + a < 4, "N2 & -3,5": lambda h, a: h <= a and h + a < 4, "12 & -3,5": lambda h, a: h != a and h + a < 4}
def etude(df, cle):
    df = df.sort_values("date"); H = collections.defaultdict(list); A = collections.defaultdict(list); R = collections.defaultdict(lambda: [[0, 0], [0, 0], [0, 0]])
    for r in df.itertuples():
        kh, ka = (r.ligue_, r.saison, r.domicile), (r.ligue_, r.saison, r.exterieur)
        h, a = H[kh], A[ka]
        if len(h) >= 4 and len(a) >= 4:
            sm = sum(x[0] for x in h) / len(h) + sum(x[1] for x in a) / len(a)
            for nom, f in M.items():
                pa = sum(f(*x) for x in h) / len(h) > .5; pb = sum(f(*x) for x in a) / len(a) > .5
                if not (pa or pb): continue
                st = "TIENT" if pa and pb else "RÉSERVE"; ok = f(r.buts_dom, r.buts_ext)
                for g in ("tous", st):
                    d = R[(nom, g)]; d[0][0] += 1; d[0][1] += ok
                    d[1 if sm <= 3.1 else 2][0] += 1; d[1 if sm <= 3.1 else 2][1] += ok
        H[kh].append((r.buts_dom, r.buts_ext)); A[ka].append((r.buts_dom, r.buts_ext))   # (buts du domicile, buts de l'extérieur)
    return R
def show(nom, R):
    print(f"== {nom}")
    for (m, g), d in sorted(R.items(), key=lambda kv: (list(M).index(kv[0][0]), kv[0][1] != "tous", kv[0][1])):
        (n0, k0), (n1, k1), (n2, k2) = d
        if g != "tous" and m != "Moins de 3,5": continue
        print(f"  {m:12} {g:8} ancienne {k0/n0:.1%} ({n0}) | nouvelle {k1/n1 if n1 else 0:.1%} ({n1}) | écart {100*((k1/n1 if n1 else 0)-k0/n0):+.1f} pt | écartés {n2} : {(k2/n2 if n2 else 0):.1%}")
g = pd.read_csv("neutre/grand_echantillon_2000_2021.csv"); g["ligue_"] = g.ligue; g["an"] = g.date.str[:4].astype(int)
b = pd.read_csv("neutre/bloc_matchs_footballdata.csv"); b["ligue_"] = b.division
show("2000-2010", etude(g[g.an <= 2010], 0)); show("2011-2020", etude(g[g.an >= 2011], 0)); show("Saison 2025-26 (Football-Data)", etude(b, 0))
