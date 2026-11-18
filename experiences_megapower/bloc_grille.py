"""Bloc de saisons (16 558 matchs, buts seulement) : réglages du modèle de buts sur 3 périodes (A choix / B validation / C test)."""
import time, sys
import numpy as np
import commun as C
from commun import *
t0 = time.time()
matchs, sc, _ = C.charger_bloc()
print(len(matchs), "matchs", round(time.time() - t0))
def run(meq, mlig, beta, ecart, sp=None):
    C.MEQ, C.MLIG = meq, mlig
    lig = {k: M.Ligue(v) for k, v in M.index_ligues(matchs).items()}
    R = []
    for m in matchs:
        F = C.features(m, lig)
        if F is not None:
            F["y"] = sc[m["id"]]; R.append(F)
    js = [r["jour"] for r in R]; n = len(R)
    dA, dB = js[n // 2], js[(3 * n) // 4]
    P = {"A": [r for r in R if r["jour"] < dA], "B": [r for r in R if dA <= r["jour"] < dB], "C": [r for r in R if r["jour"] >= dB]}
    out = {}
    for k, S in P.items():
        la, lb = zip(*(C.lambdas(r, sp, beta, ecart) for r in S)); h, a = zip(*(r["y"] for r in S)); out[k] = C.perte_scores(la, lb, h, a)
    return out, {k: len(v) for k, v in P.items()}, (dA, dB)
o, n, cut = run(16.0, 10000.0, 0.0, "gd"); print("référence sans classement", n, cut, {k: round(v, 5) for k, v in o.items()})
for me in (8.0, 16.0, 32.0, 64.0, 128.0):
    o, *_ = run(me, 10000.0, 0.0, "gd"); print("m_equipe", me, {k: round(v, 5) for k, v in o.items()}, flush=True)
for ml in (0.0, 50.0, 200.0, 1000.0, 10000.0):
    o, *_ = run(32.0, ml, 0.0, "gd"); print("m_ligue", ml, {k: round(v, 5) for k, v in o.items()}, flush=True)
for ec in ("gd", "ppm"):
    for b in (0.1, 0.2, 0.3, 0.4, 0.6):
        o, *_ = run(32.0, 10000.0, b, ec); print("classement", ec, b, {k: round(v, 5) for k, v in o.items()}, flush=True)
print(round(time.time() - t0), "s")
