"""Indice de performance d'un marché V3 : croisement des scénarios « moyen » et « pire » des deux équipes.

Décision de Patrick (10/10/2026). Pour un marché donné, chaque équipe a deux profils, calculés sur ses matchs au même
lieu (ceux de la justification) :
- moyen : somme des buts marqués ÷ nombre de matchs, somme des buts encaissés ÷ nombre de matchs (moyennes simples) ;
- pire : le match où l'équipe marque le moins favorablement pour CE marché (à égalité, le plus récent).

Les 2 × 2 profils donnent 4 scénarios de match. Dans chacun, seuls les buts MARQUÉS comptent : buts du domicile = ce
que marque le domicile dans son profil, buts de l'extérieur = ce que marque l'extérieur dans le sien (correction de
Patrick du 10/10 : pire Virton 3-0 + Hasselt 2-1 = 3 + 2 = 5 buts).
Un scénario valide le marché si sa marge (en buts, contre la ligne du marché) est strictement positive ; à égalité exacte
avec la ligne il ne valide pas. L'indice est le nombre de scénarios qui valident : 4/4 Sûr, 3/4 Recommandé,
2/4 Attention, 1/4 Risqué (0/4 : Très risqué, niveau ajouté, non défini par Patrick).

Information seulement : cet indice ne change ni la probabilité, ni la sélection, ni la calibration V3.
Un marché dont le résultat n'est pas continu (score exact, nombre exact de buts, pair/impair, issue « X » d'un handicap
à 3 choix) n'a pas d'indice (None) : ces marchés ne sont pas sélectionnables par la V3.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

EPS = 1e-9
SCENARIOS = (("moyen", "moyen"), ("pire", "moyen"), ("moyen", "pire"), ("pire", "pire"))
NIVEAUX = {4: ("SUR", "Sûr"), 3: ("RECOMMANDE", "Recommandé"), 2: ("ATTENTION", "Attention"),
           1: ("RISQUE", "Risqué"), 0: ("TRES_RISQUE", "Très risqué")}


def _ligne(jeton: str) -> float:
    return float(jeton.replace("_", "."))


def marge(marche: str, h: float, a: float) -> float | None:
    """Marge en buts du marché V3 pour un score h-a, éventuellement fractionnaire. > 0 : le marché est gagné.

    Les seuils sont ceux du règlement entier (moteur_v3.markets.gagne) placés à mi-chemin entre deux entiers : pour un
    score entier la marge n'est jamais nulle et son signe donne exactement le résultat du marché. None si le marché
    n'a pas de marge continue."""
    d = h - a
    if marche == "1x2_1":
        return d - 0.5
    if marche == "1x2_2":
        return -d - 0.5
    if marche == "dc_1X":
        return d + 0.5
    if marche == "dc_X2":
        return -d + 0.5
    if marche == "dc_12":
        return abs(d) - 0.5
    if marche == "btts_yes":
        return min(h, a) - 0.5
    if marche == "btts_no":
        return 0.5 - min(h, a)
    if marche == "clean_home":       # le domicile n'encaisse pas : l'extérieur ne marque pas
        return 0.5 - a
    if marche == "clean_away":
        return 0.5 - h
    if marche == "clean_home_no":    # le domicile encaisse au moins un but : l'extérieur marque
        return a - 0.5
    if marche == "clean_away_no":
        return h - 0.5
    if marche.startswith(("over_", "under_")):
        sens, jeton = marche.split("_", 1)
        ligne = _ligne(jeton)
        return (h + a - ligne) if sens == "over" else (ligne - h - a)
    if marche.startswith(("home_over_", "home_under_", "away_over_", "away_under_")):
        cote, sens, jeton = marche.split("_", 2)
        buts, ligne = (h if cote == "home" else a), _ligne(jeton)
        return (buts - ligne) if sens == "over" else (ligne - buts)
    if marche.startswith("handicap_"):
        try:
            _, jeton, issue = marche.split("_")
            ligne = float(jeton)
        except ValueError:
            return None
        pas = 0.5 if ligne == int(ligne) else 0.0   # ligne entière (3 choix) : il faut au moins 1 but d'écart
        if issue == "1":
            return d - ligne - pas
        if issue == "2":
            return ligne - d - pas
    return None


def _buts(m: Mapping[str, Any]) -> tuple[float, float]:
    return float(m["buts_marques"]), float(m["buts_encaisses"])


def _sens(marche: str, domicile: bool) -> int | None:
    """+1 : plus l'équipe marque, plus le marché est favorable ; -1 : l'inverse ; None : pas monotone (ex. 12)."""
    signes = set()
    for autre in range(0, 7):
        for g in range(0, 7):
            f = (lambda x: marge(marche, x, autre)) if domicile else (lambda x: marge(marche, autre, x))
            v = f(g + 1) - f(g)
            if abs(v) > EPS:
                signes.add(1 if v > 0 else -1)
    return signes.pop() if len(signes) == 1 else None


def profils(matchs: Sequence[Mapping[str, Any]], marche: str, domicile: bool) -> dict[str, Any] | None:
    """Profils moyen et pire d'une équipe pour ce marché (règle de Patrick : seuls les buts MARQUÉS comptent dans un
    scénario). `matchs` : ses matchs au même lieu, du plus ancien au plus récent.
    - moyen : somme des buts marqués ÷ nombre de matchs ;
    - pire : le match où elle marque le moins favorablement pour le marché (le moins de buts si plus de buts aide le
      marché, le plus de buts sinon). À égalité de buts marqués, le plus récent. Marché non monotone (double chance
      12) : le match dont le score est le moins favorable au marché."""
    if not matchs or marge(marche, 0, 0) is None:
        return None
    sens = _sens(marche, domicile)
    pire: tuple[float, float, float] | None = None
    for m in matchs:
        gf, ga = _buts(m)
        if sens is None:
            cle = marge(marche, *((gf, ga) if domicile else (ga, gf)))
            if cle is None:
                return None
        else:
            if marge(marche, *((gf, ga) if domicile else (ga, gf))) is None:
                return None
            cle = sens * gf
        if pire is None or cle <= pire[0]:
            pire = (cle, gf, ga)
    n = len(matchs)
    moyen = (sum(_buts(m)[0] for m in matchs) / n, sum(_buts(m)[1] for m in matchs) / n)
    return {"moyen": moyen, "pire": (pire[1], pire[2])}


def croise(dom: tuple[float, float], ext: tuple[float, float]) -> tuple[float, float]:
    """Buts du domicile et de l'extérieur dans un scénario : ce que chacun MARQUE dans son profil (règle de Patrick)."""
    return dom[0], ext[0]


def indice_performance(marche: str, matchs_dom: Sequence[Mapping[str, Any]],
                       matchs_ext: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    """Indice de performance du marché (0 à 4 scénarios sur 4) et détail des scénarios. None si non calculable."""
    pd, pe = profils(matchs_dom, marche, True), profils(matchs_ext, marche, False)
    if pd is None or pe is None:
        return None
    scenarios = []
    for sd, se in SCENARIOS:
        hd, ae = croise(pd[sd], pe[se])
        mg = marge(marche, hd, ae)
        scenarios.append({"domicile": sd, "exterieur": se, "buts_domicile": round(hd, 3), "buts_exterieur": round(ae, 3),
                          "marge": round(mg, 3), "valide": mg > EPS})
    indice = sum(1 for s in scenarios if s["valide"])
    niveau, libelle = NIVEAUX[indice]
    return {"version": 1, "indice": indice, "sur": len(SCENARIOS), "niveau": niveau, "libelle": libelle,
            "moyenne_domicile": {"marque": round(pd["moyen"][0], 3), "encaisse": round(pd["moyen"][1], 3)},
            "moyenne_exterieur": {"marque": round(pe["moyen"][0], 3), "encaisse": round(pe["moyen"][1], 3)},
            "pire_domicile": {"marque": pd["pire"][0], "encaisse": pd["pire"][1]},
            "pire_exterieur": {"marque": pe["pire"][0], "encaisse": pe["pire"][1]},
            "scenarios": scenarios}
