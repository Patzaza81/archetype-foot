import pickle, itertools, statistics
rows = pickle.load(open("rows.pkl", "rb"))
FAMS = {"Toutes": None, "Total buts": {"Total buts"}, "Double chance": {"Double chance"}, "Buts d'une équipe": {"Buts d'une équipe"},
        "Handicap": {"Handicap"}, "Cage/encaisse": {"Cage / encaisse"}, "Totaux+DC": {"Total buts", "Double chance"}}
BANDS = [(1.26, 1.37), (1.26, 1.5), (1.37, 1.6), (1.26, 1.74), (1.5, 2.0)]
TS = [0.6, 0.7, 0.8, 0.9, 1.0]; MS = [0.0, 0.05, 0.10]
def play(R, fam, band, t, m):
    fs = FAMS[fam]; by = {}
    for r in R:
        if fs and r["fam"] not in fs: continue
        if not (band[0] <= r["cote"] <= band[1]): continue
        if r["final"] < t - 1e-9 or r["final"] - 1 / r["cote"] < m - 1e-9: continue
        k = (r["final"], r["cote"])
        if r["match"] not in by or k > by[r["match"]][0]: by[r["match"]] = (k, r)
    b = [r for _, r in by.values()]; n = len(b)
    if not n: return (0, 0, 0)
    return (n, sum(r["gagne"] for r in b) / n, sum((r["cote"] - 1) if r["gagne"] else -1 for r in b) / n)
RULES = list(itertools.product(FAMS, BANDS, TS, MS))
print("règles testées :", len(RULES))
def run(dm, nmin=25):
    tr = [r for r in rows if r["date"] <= dm]; te = [r for r in rows if r["date"] > dm]
    out = []
    for rule in RULES:
        a = play(tr, *rule)
        if a[0] >= nmin:
            b = play(te, *rule); out.append((a[2], rule, a, b))
    out.sort(key=lambda x: -x[0])
    return out
for dm in ("2026-10-09", "2026-10-10"):
    out = run(dm)
    print(f"\n== réglage <= {dm} : {len(out)} règles avec >= 25 paris ==")
    pos = [o for o in out if o[0] > 0]
    print("règles à ROI positif en réglage :", len(pos), "| parmi elles ROI positif en test :", sum(1 for o in pos if o[3][2] > 0 and o[3][0] >= 15), "/", sum(1 for o in pos if o[3][0] >= 15))
    for roi, rule, a, b in out[:6]:
        print(f"  {rule[0]:<16} cote {rule[1]} t>={rule[2]} marge>={rule[3]}: réglage {a[0]} paris {a[1]:.0%} ROI {a[2]:+.1%} | test {b[0]} paris {b[1]:.0%} ROI {b[2]:+.1%}")
    top = [o for o in out[:10] if o[3][0] >= 15]
    if top: print("  médiane ROI test des 10 meilleures règles de réglage : %+.1f%%" % (100 * statistics.median(o[3][2] for o in top)))
# réglage sur TOUT (en trichant)
alld = []
for rule in RULES:
    a = play(rows, *rule)
    if a[0] >= 40: alld.append((a[2], rule, a))
alld.sort(key=lambda x: -x[0])
print("\n== MEILLEURES RÈGLES SUR LES 440 (en trichant, >= 40 paris) ==")
for roi, rule, a in alld[:8]:
    print(f"  {rule[0]:<16} cote {rule[1]} t>={rule[2]} marge>={rule[3]}: {a[0]} paris {a[1]:.1%} ROI {roi:+.1%}")
