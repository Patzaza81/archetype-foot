"""Test de sensibilité des paramètres de v2r (ajout 14/10/2026). OUTIL D'ÉTUDE : ne modifie ni le moteur ni ses fichiers.
Rejoue le vrai moteur jour par jour (règles apprises uniquement sur les jours précédents, comme backtest.py) en changeant
un paramètre à la fois, puis restaure la configuration. Usage : python -m moteur_v2r.sensibilite
Limites : réentraînement quotidien (la production le fait le lundi) ; premiers jours testés avec très peu de matchs
d'entraînement ; les tests ne sont pas indépendants entre eux (mêmes matchs)."""
import collections
import copy

from . import backtest as B, echantillon as X, integration as I, regles as R
from .donnees import charge

PREMIER_JOUR_TESTE = "2026-10-06"


def decrit(ms):
    """Description de l'échantillon : taille, dates, matchs par jour, championnats, marchés par match."""
    par_jour = collections.Counter(m["date"] for m in ms)
    return dict(matchs=len(ms), du=min(par_jour), au=max(par_jour), par_jour=sorted(par_jour.items()),
                championnats=len({m["ligue"] for m in ms}),
                marches_par_match=round(sum(len(m["cotes"]) for m in ms) / len(ms), 1))


def rejoue_avec(ms, jours, min_paris=None, roi_min=None, pas=None, coupures_ligue=None, coupures_match=None):
    """Rejoue le moteur officiel ('v2r') avec UN paramètre modifié, puis restaure tout. Retourne le résumé."""
    ancien = (copy.deepcopy(R.CONFIG), X.PAS_COTE, I.COUPURES_LIGUE, I.COUPURES_MATCH)
    try:
        if min_paris is not None:
            R.CONFIG["min_paris"] = min_paris
        if roi_min is not None:
            R.CONFIG["roi_min"] = roi_min
        if pas is not None:
            X.PAS_COTE = pas
        if coupures_ligue is not None:
            I.COUPURES_LIGUE = coupures_ligue
        if coupures_match is not None:
            I.COUPURES_MATCH = coupures_match
        return B.resume(B.rejoue(ms, jours)["v2r"])
    finally:
        R.CONFIG.clear()
        R.CONFIG.update(ancien[0])
        X.PAS_COTE, I.COUPURES_LIGUE, I.COUPURES_MATCH = ancien[1:]


def main():
    ms = [m for m in charge() if m["h"] is not None]
    print(decrit(ms))
    jours = [j for j in sorted({m["date"] for m in ms}) if j >= PREMIER_JOUR_TESTE]
    print("jours testés :", jours)
    essais = [("base", {})] + [(f"min_paris={v}", dict(min_paris=v)) for v in (5, 10, 20)] \
        + [(f"roi_min={v}", dict(roi_min=v)) for v in (0.0, 0.15, 0.30, 0.45)] \
        + [(f"pas_cote={v}", dict(pas=v)) for v in (0.2, 0.25, 0.5)]
    for nom, kw in essais:
        s = rejoue_avec(ms, jours, **kw)
        ic = None if not s["ic95"] else [round(x, 2) for x in s["ic95"]]
        roi = None if s["roi"] is None else round(s["roi"], 3)
        print(f"{nom:16s} paris {s['paris']:4d}  ROI {roi}  IC95 {ic}")


if __name__ == "__main__":
    main()
