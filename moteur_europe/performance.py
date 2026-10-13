"""Indice de performance du marché pour le moteur Europe : même logique que moteur_v3.performance (version 4).

Seule différence : le profil « moyen » d'une équipe est la moyenne pondérée 70 % Europe / 30 % championnat ; le profil
« pire » est cherché dans TOUS les matchs utilisés (européens et championnat), pour que le pire scénario reste le plus dur
possible. Information seulement."""
from __future__ import annotations

from .socle.performance import _depend, _indice_deux_equipes, _indice_une_equipe, _moyen, marge

from .model import POIDS_CHAMPIONNAT, POIDS_EUROPE, derniers


def profil_moyen(europe, championnat) -> tuple[float, float]:
    e, c = _moyen(europe), _moyen(championnat)
    return (POIDS_EUROPE * e[0] + POIDS_CHAMPIONNAT * c[0], POIDS_EUROPE * e[1] + POIDS_CHAMPIONNAT * c[1])


def indice_performance_europe(marche, europe_dom, ligue_dom, europe_ext, ligue_ext):
    eu_d, eu_e = derniers(europe_dom, True), derniers(europe_ext, False)
    lg_d, lg_e = derniers(ligue_dom, True), derniers(ligue_ext, False)
    if not (eu_d and eu_e and lg_d and lg_e) or marge(marche, 0, 0) is None:
        return None
    dd, de = _depend(marche, True), _depend(marche, False)
    if not (dd or de):
        return None
    md, me = profil_moyen(eu_d, lg_d), profil_moyen(eu_e, lg_e)
    tous_d, tous_e = eu_d + lg_d, eu_e + lg_e
    if dd and de:
        return _indice_deux_equipes(marche, tous_d, tous_e, md, me)
    return _indice_une_equipe(marche, tous_d, tous_e, md, me, dd)
