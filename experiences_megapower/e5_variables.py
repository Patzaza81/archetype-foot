"""E5 : variables structurelles (xG vs buts, référentiel de ligue, classement, petites valeurs de tendance), chronologique A/B/C."""
import pickle, time
import numpy as np
import commun as C
from commun import *
matchs, sc, lig0 = C.charger()
def perte_periodes(w, meq, mlig, beta, ecart, sp=None):
    C.W, C.MEQ, C.MLIG = w, meq, mlig
    lig = {k: M.Ligue(v) for k, v in M.index_ligues(matchs).items()}
    R = []
    for m in matchs:
        if m["id"] in sc:
            F = C.features(m, lig)
            if F is not None:
                F["y"] = sc[m["id"]]; R.append(F)
    js = sorted(r["jour"] for r in R); dA, dB = js[len(js) // 2], js[3 * len(js) // 4]
    out = {}
    for nom, S in (("A", [r for r in R if r["jour"] < dA]), ("B", [r for r in R if dA <= r["jour"] < dB]), ("C", [r for r in R if r["jour"] >= dB])):
        la, lb = zip(*(C.lambdas(r, sp, beta, ecart) for r in S)); h, a = zip(*(r["y"] for r in S))
        out[nom] = C.perte_scores(la, lb, h, a)
    return out, len(R)
t0 = time.time()
ref, n = perte_periodes(1.0, 16.0, 10000.0, BETA_GD, "gd"); print("référence megapower v2", n, {k: round(v, 5) for k, v in ref.items()})
def aff(nom, o): print(f"{nom:48s}", {k: round(v, 5) for k, v in o.items()}, "Δ vs réf B/C:", round(o["B"] - ref["B"], 5), round(o["C"] - ref["C"], 5), flush=True)
print("\n-- attaque/défense : xG vs buts")
for w in (0.0, 0.5, 1.0):
    aff(f"poids du xG = {w}", perte_periodes(w, 16.0, 10000.0, BETA_GD, "gd")[0])
print("\n-- référentiel du championnat (rapprochement de la ligue vers la moyenne générale : 0 = moyenne propre à la ligue)")
for ml in (0.0, 20.0, 100.0, 500.0, 2342.0, 10000.0):
    aff(f"pseudo-matchs de ligue = {ml}", perte_periodes(1.0, 16.0, ml, BETA_GD, "gd")[0])
print("\n-- rapprochement des équipes (pseudo-matchs neutres)")
for me in (4.0, 8.0, 16.0, 32.0, 64.0):
    aff(f"pseudo-matchs d'équipe = {me}", perte_periodes(1.0, me, 10000.0, BETA_GD, "gd")[0])
print("\n-- situation compétitive (coefficient ajusté sur A, évalué sur B et C)")
from scipy.optimize import minimize_scalar
C.W, C.MEQ, C.MLIG = 1.0, 16.0, 10000.0
lig = {k: M.Ligue(v) for k, v in M.index_ligues(matchs).items()}
R = [r for r in (C.features(m, lig) for m in matchs if m["id"] in sc) if r is not None]
for r, m in zip(R, [m for m in matchs if m["id"] in sc and C.features(m, lig) is not None]):
    r["y"] = sc[m["id"]]
js = sorted(r["jour"] for r in R); dA, dB = js[len(js) // 2], js[3 * len(js) // 4]
PA = [r for r in R if r["jour"] < dA]; PB = [r for r in R if dA <= r["jour"] < dB]; PC = [r for r in R if r["jour"] >= dB]
def L(S, beta, ecart, sp=None):
    la, lb = zip(*(C.lambdas(r, sp, beta, ecart) for r in S)); h, a = zip(*(r["y"] for r in S)); return C.perte_scores(la, lb, h, a)
print(f"{'sans classement':48s} A={L(PA,0,'gd'):.5f} B={L(PB,0,'gd'):.5f} C={L(PC,0,'gd'):.5f}")
for ec in ("ppm", "gd", "xgd", "xpts", "surperf"):
    b = float(minimize_scalar(lambda x: L(PA, x, ec), bounds=(-1.5, 1.5), method="bounded").x)
    print(f"{'écart '+ec:48s} β={b:+.3f} A={L(PA,b,ec):.5f} B={L(PB,b,ec):.5f} C={L(PC,b,ec):.5f}")
print("\n-- tendance : valeurs de θ plus petites que celles du premier balayage (arith/géo, normalisée, fenêtre 6)")
for tp in ("arith", "geo", "ewma"):
    for th in (0.0, 0.02, 0.05, 0.1):
        sp = dict(type=tp, theta=th, win=6, norm=True, decay=0.85)
        print(f"{tp:6s} θ={th:<5} A={L(PA,BETA_GD,'gd',sp):.5f} B={L(PB,BETA_GD,'gd',sp):.5f} C={L(PC,BETA_GD,'gd',sp):.5f}")
print(round(time.time() - t0), "s")
