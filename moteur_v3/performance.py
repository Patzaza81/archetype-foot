"""Indice de performance d'un marché V3 : croisement des scénarios « moyen » et « pire » des deux équipes.

Décision de Patrick (10/10/2026). Pour un marché donné, chaque équipe a deux profils, calculés sur ses matchs au même
lieu (ceux de la justification) :
- moyen : somme des buts marqués ÷ nombre de matchs, somme des buts encaissés ÷ nombre de matchs (moyennes simples) ;
- pire : le match qui éprouve le plus CE marché ; pour (pire, pire) on teste toutes les paires de matchs et on garde la plus dure (aucun scénario ne peut être pire).

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


def _moyen(matchs: Sequence[Mapping[str, Any]]) -> tuple[float, float]:
    n = len(matchs)
    return sum(_buts(m)[0] for m in matchs) / n, sum(_buts(m)[1] for m in matchs) / n


def _pire(matchs, marche: str, domicile: bool, autre_buts: float):
    """Match d'une équipe qui met le plus le marché à l'épreuve, face à `autre_buts` buts de l'adversaire : celui dont
    la marge est la plus basse (seuls les buts marqués comptent). À égalité, le plus récent. None si non calculable."""
    pire = None
    for m in matchs:
        gf, ga = _buts(m)
        mg = marge(marche, *((gf, autre_buts) if domicile else (autre_buts, gf)))
        if mg is None:
            return None
        if pire is None or mg <= pire[0]:
            pire = (mg, gf, ga)
    return pire


def profils(matchs: Sequence[Mapping[str, Any]], marche: str, domicile: bool, autre_buts: float | None = None) -> dict[str, Any] | None:
    """Profils moyen et pire d'une équipe pour ce marché (règle de Patrick : seuls les buts MARQUÉS comptent).
    - moyen : somme des buts marqués ÷ nombre de matchs ;
    - pire : le match qui éprouve le plus le marché, face à `autre_buts` buts de l'adversaire (par défaut sa moyenne)."""
    if not matchs or marge(marche, 0, 0) is None:
        return None
    moyen = _moyen(matchs)
    ref = moyen[0] if autre_buts is None else autre_buts      # pas utilisé quand l'adversaire est lui aussi « moyen »
    pire = _pire(matchs, marche, domicile, ref)
    return None if pire is None else {"moyen": moyen, "pire": (pire[1], pire[2])}


def croise(dom: tuple[float, float], ext: tuple[float, float]) -> tuple[float, float]:
    """Buts du domicile et de l'extérieur dans un scénario : ce que chacun MARQUE dans son profil (règle de Patrick)."""
    return dom[0], ext[0]


def _depend(marche: str, domicile: bool) -> bool:
    """Le résultat du marché dépend-il des buts de cette équipe ? (ex. « domicile plus de 1,5 » ne dépend pas de l'extérieur)"""
    for autre in range(0, 7):
        for g in range(0, 6):
            f = (lambda x: marge(marche, x, autre)) if domicile else (lambda x: marge(marche, autre, x))
            if abs(f(g + 1) - f(g)) > EPS:
                return True
    return False


def niveau_pour(indice: int, sur: int) -> tuple[str, str]:
    """Niveau selon la part de scénarios validés : 100 % Sûr, ≥ 75 % Recommandé, ≥ 50 % Attention, > 0 Risqué, 0 Très risqué.
    Sur 4 : 4/4 Sûr, 3/4 Recommandé, 2/4 Attention, 1/4 Risqué (échelle de Patrick). Sur 2 : 2/2 Sûr, 1/2 Attention."""
    if indice >= sur:
        return NIVEAUX[4]
    part = indice / sur
    return NIVEAUX[3] if part >= 0.75 else NIVEAUX[2] if part >= 0.5 else NIVEAUX[1] if indice > 0 else NIVEAUX[0]


def indice_performance(marche: str, matchs_dom: Sequence[Mapping[str, Any]],
                       matchs_ext: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    """Indice de performance du marché (scénarios validés sur scénarios distincts) et détail. None si non calculable.

    Marché qui dépend des deux équipes : 4 scénarios (moyen/pire de chacune). Marché qui ne dépend que d'UNE équipe
    (ex. domicile plus de 1,5 buts, clean sheet) : 2 scénarios seulement, moyen et pire de cette équipe, l'autre n'entre pas.

    Le pire scénario est le plus dur possible : pour (pire, pire) on teste TOUTES les paires (match du domicile, match de
    l'extérieur) et on garde celle de marge minimale, donc aucun autre scénario ne peut être pire (même pour les marchés
    où le pire d'une équipe dépend de l'autre, comme la double chance 12). Pour (pire, moyen) et (moyen, pire), le pire
    match de l'équipe est celui de marge minimale face à la moyenne de l'adversaire."""
    if not matchs_dom or not matchs_ext or marge(marche, 0, 0) is None:
        return None
    dd, de = _depend(marche, True), _depend(marche, False)
    if not (dd or de):
        return None
    md, me = _moyen(matchs_dom), _moyen(matchs_ext)
    pp = None
    for x in matchs_dom:
        for y in matchs_ext:
            mg = marge(marche, _buts(x)[0], _buts(y)[0])
            if pp is None or mg <= pp[0]:
                pp = (mg, _buts(x), _buts(y))
    pm = _pire(matchs_dom, marche, True, me[0])
    mp = _pire(matchs_ext, marche, False, md[0])
    buts = {("moyen", "moyen"): (md[0], me[0]), ("pire", "moyen"): (pm[1], me[0]),
            ("moyen", "pire"): (md[0], mp[1]), ("pire", "pire"): (pp[1][0], pp[2][0])}
    if dd and not de:
        liste = (("moyen", None), ("pire", None))
    elif de and not dd:
        liste = ((None, "moyen"), (None, "pire"))
    else:
        liste = SCENARIOS
    scenarios = []
    for sd, se in liste:
        hd, ae = buts[(sd or "moyen", se or "moyen")]
        if sd is None:
            hd = None
        if se is None:
            ae = None
        # marché d'une seule équipe : l'autre n'intervient pas dans la marge (0 neutre)
        mg = marge(marche, 0 if hd is None else hd, 0 if ae is None else ae)
        scenarios.append({"domicile": sd, "exterieur": se,
                          "buts_domicile": None if hd is None else round(hd, 3),
                          "buts_exterieur": None if ae is None else round(ae, 3),
                          "marge": round(mg, 3), "valide": mg > EPS})
    indice = sum(1 for s in scenarios if s["valide"])
    sur = len(scenarios)
    niveau, libelle = niveau_pour(indice, sur)
    return {"version": 3, "indice": indice, "sur": sur, "niveau": niveau, "libelle": libelle,
            "moyenne_domicile": {"marque": round(md[0], 3), "encaisse": round(md[1], 3)},
            "moyenne_exterieur": {"marque": round(me[0], 3), "encaisse": round(me[1], 3)},
            "pire_domicile": None if not dd else {"marque": (pp[1][0] if de else pm[1]), "encaisse": (pp[1][1] if de else pm[2])},
            "pire_exterieur": None if not de else {"marque": (pp[2][0] if dd else mp[1]), "encaisse": (pp[2][1] if dd else mp[2])},
            "scenarios": scenarios}
