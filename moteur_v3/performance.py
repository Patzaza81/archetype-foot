"""Indice de performance d'un marché V3 : croisement des scénarios « moyen » et « pire » des deux équipes.

Décision de Patrick (10/10/2026), PRÉCISÉE LE 12/10/2026 : le pire scénario regarde le SCORE ENTIER qui met le plus en mal
le marché choisi, sans distinguer domicile et extérieur ; le scénario moyen est la moyenne de tous les résultats.
Chaque équipe a deux profils, calculés sur ses matchs au même lieu (ceux de la justification), chacun étant un score
(buts marqués, buts encaissés) :
- moyen : moyenne des buts marqués et moyenne des buts encaissés sur tous ses matchs (moyennes simples) ;
- pire : le match dont le score met le plus le marché en difficulté ; pour (pire, pire) on teste toutes les paires de
  matchs et on garde la plus dure (aucun scénario ne peut être pire).

Les 2 × 2 profils donnent 4 scénarios de match. Score d'un scénario (version 4, 12/10/2026) :
    buts du domicile    = (ce que marque le domicile dans son profil + ce que l'extérieur encaisse dans le sien) ÷ 2
    buts de l'extérieur = (ce que marque l'extérieur dans son profil + ce que le domicile encaisse dans le sien) ÷ 2
Pour un total de buts, cela revient à la moyenne des totaux des deux matchs. Exemple de référence (12/10, Al Khaleej –
Al Fayha, moins de 3,5) : pire Al Khaleej 1-5 (6 buts) et pire Al Fayha 2-1 (3 buts) → 4,5 buts : non validé. (Versions 1 à 3 :
seuls les buts marqués comptaient, ce qui laissait le 1-5 invisible.)
Un scénario valide le marché si sa marge (en buts, contre la ligne du marché) est strictement positive ; à égalité exacte
avec la ligne il ne valide pas. L'indice est le nombre de scénarios qui valident : 4/4 Sûr, 3/4 Recommandé,
2/4 Attention, 1/4 Risqué (0/4 : Très risqué, niveau ajouté, non défini par Patrick).

Marché d'une seule équipe (domicile plus de 1,5 buts, clean sheet...) : 2 scénarios, moyen et pire de cette équipe ; ses
propres buts sont le score du marché, l'autre équipe n'entre pas (inchangé).

Information seulement : cet indice ne change ni la probabilité, ni la sélection, ni la calibration V3.
Un marché dont le résultat n'est pas continu (score exact, nombre exact de buts, pair/impair, issue « X » d'un handicap
à 3 choix) n'a pas d'indice (None) : ces marchés ne sont pas sélectionnables par la V3.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

EPS = 1e-9
VERSION = 4        # 4 = score entier (12/10/2026) ; 3 = buts marqués seulement (10/10/2026)
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


def croise(dom: tuple[float, float], ext: tuple[float, float]) -> tuple[float, float]:
    """Score (domicile, extérieur) d'un scénario à partir des deux profils (marqués, encaissés) : chaque côté est la
    moyenne de ce que son équipe marque et de ce que l'adversaire encaisse (règle de Patrick du 12/10/2026)."""
    return (dom[0] + ext[1]) / 2.0, (ext[0] + dom[1]) / 2.0


def _pire_croise(matchs, marche: str, domicile: bool, autre: tuple[float, float]):
    """Match d'une équipe dont le score met le plus le marché en difficulté, croisé avec le profil `autre` de
    l'adversaire : celui de marge minimale. À égalité, le plus récent. Retourne (marge, (marqués, encaissés)) ou None."""
    pire = None
    for m in matchs:
        prof = _buts(m)
        h, a = croise(prof, autre) if domicile else croise(autre, prof)
        mg = marge(marche, h, a)
        if mg is None:
            return None
        if pire is None or mg <= pire[0]:
            pire = (mg, prof)
    return pire


def profils(matchs: Sequence[Mapping[str, Any]], marche: str, domicile: bool,
            autre: tuple[float, float] | None = None) -> dict[str, Any] | None:
    """Profils moyen et pire d'une équipe pour ce marché (règle de Patrick du 12/10 : score entier).
    - moyen : (moyenne des buts marqués, moyenne des buts encaissés) ;
    - pire : le match dont le score met le plus le marché en difficulté. `autre` = profil (marqués, encaissés) de
      l'adversaire avec lequel on le croise ; sans `autre`, le score du match est pris tel quel (domicile, extérieur)."""
    if not matchs or marge(marche, 0, 0) is None:
        return None
    moyen = _moyen(matchs)
    pire = None
    for m in matchs:
        gf, ga = _buts(m)
        h, a = croise((gf, ga), autre) if (autre is not None and domicile) else \
            croise(autre, (gf, ga)) if autre is not None else ((gf, ga) if domicile else (ga, gf))
        mg = marge(marche, h, a)
        if mg is None:
            return None
        if pire is None or mg <= pire[0]:
            pire = (mg, (gf, ga))
    return {"moyen": moyen, "pire": pire[1]}


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


def phrase_indice(scenarios: Sequence[Mapping[str, Any]]) -> str:
    """Phrase qui dit ce que l'indice signifie. Marché d'une seule équipe (2 scénarios) : on dit si le marché tient en
    moyenne et dans le pire match, plutôt qu'une note sur 2. Marché des deux équipes : nombre de scénarios sur 4."""
    v = [bool(x["valide"]) for x in scenarios]
    if len(v) == 2:
        moyen, pire = v
        if moyen and pire:
            return "Tient en moyenne et dans le pire match."
        if moyen:
            return "Tient en moyenne, mais pas dans le pire match."
        if pire:
            return "Ne tient pas en moyenne, mais tient dans le pire match."
        return "Ne tient ni en moyenne ni dans le pire match."
    n = sum(v)
    return f"Validé dans {n} scénario{'s' if n > 1 else ''} sur {len(v)}."


def indice_performance(marche: str, matchs_dom: Sequence[Mapping[str, Any]],
                       matchs_ext: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    """Indice de performance du marché (scénarios validés sur scénarios distincts) et détail. None si non calculable.

    Marché qui dépend des deux équipes : 4 scénarios (moyen/pire de chacune), chaque profil étant un SCORE ENTIER
    (marqués, encaissés), croisés par `croise`. Marché qui ne dépend que d'UNE équipe (ex. domicile plus de 1,5 buts,
    clean sheet) : 2 scénarios seulement, moyen et pire de cette équipe, l'autre n'entre pas.

    Le pire scénario est le plus dur possible : pour (pire, pire) on teste TOUTES les paires (match du domicile, match de
    l'extérieur) et on garde celle de marge minimale, donc aucun autre scénario ne peut être pire. Pour (pire, moyen) et
    (moyen, pire), le pire match de l'équipe est celui de marge minimale face au profil moyen de l'adversaire."""
    if not matchs_dom or not matchs_ext or marge(marche, 0, 0) is None:
        return None
    dd, de = _depend(marche, True), _depend(marche, False)
    if not (dd or de):
        return None
    md, me = _moyen(matchs_dom), _moyen(matchs_ext)
    if dd and de:
        return _indice_deux_equipes(marche, matchs_dom, matchs_ext, md, me)
    return _indice_une_equipe(marche, matchs_dom, matchs_ext, md, me, dd)


def _resultat(scenarios, md, me, pire_d, pire_e):
    indice = sum(1 for s in scenarios if s["valide"])
    sur = len(scenarios)
    niveau, libelle = niveau_pour(indice, sur)
    return {"version": VERSION, "indice": indice, "sur": sur, "niveau": niveau, "libelle": libelle,
            "phrase": phrase_indice(scenarios),
            "moyenne_domicile": {"marque": round(md[0], 3), "encaisse": round(md[1], 3)},
            "moyenne_exterieur": {"marque": round(me[0], 3), "encaisse": round(me[1], 3)},
            "pire_domicile": None if pire_d is None else {"marque": pire_d[0], "encaisse": pire_d[1]},
            "pire_exterieur": None if pire_e is None else {"marque": pire_e[0], "encaisse": pire_e[1]},
            "scenarios": scenarios}


def _indice_deux_equipes(marche, matchs_dom, matchs_ext, md, me):
    pp = None
    for x in matchs_dom:
        for y in matchs_ext:
            h, a = croise(_buts(x), _buts(y))
            mg = marge(marche, h, a)
            if pp is None or mg <= pp[0]:
                pp = (mg, _buts(x), _buts(y))
    pm = _pire_croise(matchs_dom, marche, True, me)
    mp = _pire_croise(matchs_ext, marche, False, md)
    profils_ = {("moyen", "moyen"): (md, me), ("pire", "moyen"): (pm[1], me),
                ("moyen", "pire"): (md, mp[1]), ("pire", "pire"): (pp[1], pp[2])}
    scenarios = []
    for sd, se in SCENARIOS:
        d, e = profils_[(sd, se)]
        h, a = croise(d, e)
        mg = marge(marche, h, a)
        scenarios.append({"domicile": sd, "exterieur": se, "buts_domicile": round(h, 3), "buts_exterieur": round(a, 3),
                          "marge": round(mg, 3), "valide": mg > EPS})
    return _resultat(scenarios, md, me, pp[1], pp[2])


def _indice_une_equipe(marche, matchs_dom, matchs_ext, md, me, dom_seul):
    """Marché d'une seule équipe : ses propres buts font le score du marché (comportement inchangé depuis le 10/10)."""
    scenarios = []
    pire = _pire(matchs_dom if dom_seul else matchs_ext, marche, dom_seul, (me if dom_seul else md)[0])
    for niveau in ("moyen", "pire"):
        if dom_seul:
            hd, ae = (md[0] if niveau == "moyen" else pire[1]), None
            mg = marge(marche, hd, 0)
        else:
            hd, ae = None, (me[0] if niveau == "moyen" else pire[1])
            mg = marge(marche, 0, ae)
        scenarios.append({"domicile": niveau if dom_seul else None, "exterieur": None if dom_seul else niveau,
                          "buts_domicile": None if hd is None else round(hd, 3),
                          "buts_exterieur": None if ae is None else round(ae, 3),
                          "marge": round(mg, 3), "valide": mg > EPS})
    return _resultat(scenarios, md, me, (pire[1], pire[2]) if dom_seul else None, None if dom_seul else (pire[1], pire[2]))
