"""Calibration par régression logistique sur [1, logit(p_modèle), logit(1/cote)] : le poids du modèle
est APPRIS contre la cote du bookmaker (jamais supposé)."""
import math


def logit(p):
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def sig(x):
    return 1 / (1 + math.exp(-x))


def features(pw, cote):
    return [1.0, logit(pw), logit(1 / cote)]


def ajuste(X, y, iters=25, l2=1e-3):
    """Newton-Raphson ridge. Retourne les poids."""
    d = len(X[0])
    w = [0.0] * d
    for _ in range(iters):
        g = [0.0] * d
        H = [[l2 if i == j else 0.0 for j in range(d)] for i in range(d)]
        for xi, yi in zip(X, y):
            p = sig(sum(a * b for a, b in zip(w, xi)))
            q = p * (1 - p)
            for i in range(d):
                g[i] += (p - yi) * xi[i]
                for j in range(d):
                    H[i][j] += q * xi[i] * xi[j]
        A = [H[i][:] + [g[i]] for i in range(d)]
        for i in range(d):
            piv = A[i][i]
            for j in range(i, d + 1):
                A[i][j] /= piv
            for k in range(d):
                if k != i:
                    f = A[k][i]
                    for j in range(i, d + 1):
                        A[k][j] -= f * A[i][j]
        w = [w[i] - A[i][d] for i in range(d)]
    return w


def proba_calibree(w, pw, cote):
    return sig(sum(a * b for a, b in zip(w, features(pw, cote))))
