# Usage : python3 etudes/moins35_2026_11/test_echantillons.py depuis /home/claude (tables etude_n/t_*.csv construites par etudes/categories_2026_11/build.py)
import pandas as pd
F = {"Grand échantillon 2000-2021": "etude_n/t_grand.csv", "Bloc Football-Data 2025-26": "etude_n/t_bloc.csv", "Matchs Betpawa du système": "etude_n/t_flux.csv"}
M = {"Moins de 3,5": lambda h, a: h + a < 4, "1 & -3,5": lambda h, a: (h > a) & (h + a < 4), "2 & -3,5": lambda h, a: (h < a) & (h + a < 4),
     "1N & -3,5": lambda h, a: (h >= a) & (h + a < 4), "N2 & -3,5": lambda h, a: (h <= a) & (h + a < 4), "12 & -3,5": lambda h, a: (h != a) & (h + a < 4)}
def ligne(t, nom):
    out = []
    for lab, f in M.items():
        ok = f(t.bd, t.be); s = []
        for q, msk in (("tous", t.SM == t.SM), ("SM <= 3,1", t.SM <= 3.1), ("SM > 3,1", t.SM > 3.1)):
            n = int(msk.sum()); s.append(f"{q}: {ok[msk].mean():.1%} ({n})" if n else f"{q}: - (0)")
        out.append(f"  {lab:12} | " + " | ".join(s))
    print(nom); print("\n".join(out))
for nom, p in F.items():
    t = pd.read_csv(p); ligne(t, f"== {nom} ({len(t)} matchs, 4 matchs mini au même lieu)")
    if "EH" in t:
        c = t[(t.EH < 1.3808616267615823) & (t.EA < 1.5668783441905885)]; ligne(c[["bd","be","SM"]], f"   -> dans l'intervalle Catégories du -3,5 ({len(c)} matchs)")
    if "bp_moins_3_5" in t: pass
