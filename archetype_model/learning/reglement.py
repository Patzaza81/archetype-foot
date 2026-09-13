"""
archetype_model/learning/reglement.py — Règlement mécanique des marchés.

Pourquoi ce module existe : resultats.py (et plus tard contrefactuel.py)
doivent tous deux répondre à la même question -- un marché a-t-il gagné ou
perdu, une fois le score réel connu -- avec exactement la même règle.
Isoler cette règle ici, sans aucune I/O ni accès réseau, garantit qu'elle ne
peut jamais être appliquée différemment à deux endroits du système (c'est
exactement le trou que le bureau d'étude avait laissé passer avec son
"etc." -- corrigé le 12/09/2026, verrouillé ici).

Convention non négociable (vérifiée avec Patrick le 13/09/2026) :
buts_dom / buts_ext désignent TOUJOURS les buts de l'équipe DOMICILE et
EXTÉRIEURE du match réel -- jamais les buts d'une "équipe analysée" selon
une convention qui varierait d'un marché à l'autre.

AUCUNE ellipse : les 19 motifs de l'Annexe A du cahier des charges sont
couverts explicitement ci-dessous, plus les combos DC+Total. Un marché non
reconnu retourne MARCHE_NON_RECONNU -- jamais une perte par défaut, jamais
une exception qui interromprait le pipeline nocturne.

Les motifs et leurs formats de chaîne reprennent exactement ceux déjà en
production dans justification.py (mêmes regex, même nomenclature) -- pas
une nouvelle convention inventée ici.
"""

from __future__ import annotations

import re
from typing import NamedTuple

WIN = "WIN"
LOSS = "LOSS"
MARCHE_NON_RECONNU = "MARCHE_NON_RECONNU"

STATUTS_VALIDES = frozenset({WIN, LOSS, MARCHE_NON_RECONNU})


class ResultatMarche(NamedTuple):
    """statut : WIN | LOSS | MARCHE_NON_RECONNU."""
    statut: str


_RE_OVER_UNDER_TOTAL = re.compile(r"^over_under_total_(-?\d+(?:\.\d+)?)_(over|under)$")
_RE_BUTS_EQUIPE = re.compile(r"^buts_equipe_(domicile|exterieur)_(-?\d+(?:\.\d+)?)_(over|under)$")
_RE_HANDICAP = re.compile(r"^handicap_(domicile|exterieur)_(-?\d+(?:\.\d+)?)$")
_RE_COMBO = re.compile(r"^combo_(1X|X2|12)_(over|under)_(-?\d+(?:\.\d+)?)$")


def _win(condition: bool) -> ResultatMarche:
    return ResultatMarche(WIN if condition else LOSS)


def evaluer_marche(marche: str, buts_dom: int, buts_ext: int) -> ResultatMarche:
    """Retourne WIN ou LOSS pour `marche`, compte tenu du score réel
    (buts_dom, buts_ext) -- ou MARCHE_NON_RECONNU si `marche` ne correspond
    à aucun des motifs de l'Annexe A. Ne lève jamais d'exception pour un
    motif inconnu : c'est à l'appelant de décider quoi faire d'un
    MARCHE_NON_RECONNU (voir resultats.py -- jamais une résolution
    silencieuse en LOSS par défaut).
    """
    if not isinstance(buts_dom, int) or not isinstance(buts_ext, int):
        raise ValueError("buts_dom et buts_ext doivent être des entiers")
    if buts_dom < 0 or buts_ext < 0:
        raise ValueError("buts_dom et buts_ext doivent être >= 0")

    marche = (marche or "").strip()
    total = buts_dom + buts_ext

    # 1-2. Over/Under total (+ alias historique over_2_5)
    m = _RE_OVER_UNDER_TOTAL.match(marche)
    if m:
        ligne, sens = float(m.group(1)), m.group(2)
        return _win(total > ligne if sens == "over" else total < ligne)
    if marche == "over_2_5":
        return _win(total > 2.5)

    # 3-4. Handicap
    m = _RE_HANDICAP.match(marche)
    if m:
        role, ligne = m.group(1), float(m.group(2))
        if role == "domicile":
            return _win(buts_dom + ligne > buts_ext)
        return _win(buts_ext + ligne > buts_dom)

    # 5-7. Double chance (+ alias historiques 1x2_domicile/exterieur)
    if marche in ("double_chance_1X", "1x2_domicile"):
        return _win(buts_dom >= buts_ext)
    if marche in ("double_chance_X2", "1x2_exterieur"):
        return _win(buts_ext >= buts_dom)
    if marche == "double_chance_12":
        return _win(buts_dom != buts_ext)

    # 8-9. BTTS
    if marche == "btts_oui":
        return _win(buts_dom > 0 and buts_ext > 0)
    if marche == "btts_non":
        return _win(buts_dom == 0 or buts_ext == 0)

    # 10-13. Buts par équipe
    m = _RE_BUTS_EQUIPE.match(marche)
    if m:
        role, ligne, sens = m.group(1), float(m.group(2)), m.group(3)
        buts = buts_dom if role == "domicile" else buts_ext
        return _win(buts > ligne if sens == "over" else buts < ligne)

    # 14-15. Cage inviolée
    if marche == "cage_inviolee_domicile":
        return _win(buts_ext == 0)
    if marche == "cage_inviolee_exterieur":
        return _win(buts_dom == 0)

    # 16-17. Encaisse
    if marche == "encaisse_domicile":
        return _win(buts_ext > 0)
    if marche == "encaisse_exterieur":
        return _win(buts_dom > 0)

    # 18-19. Parité
    if marche == "parite_pair":
        return _win(total % 2 == 0)
    if marche == "parite_impair":
        return _win(total % 2 == 1)

    # 20. Combo Double Chance + Total (conjonction des deux conditions)
    m = _RE_COMBO.match(marche)
    if m:
        dc, sens, ligne = m.group(1), m.group(2), float(m.group(3))
        if dc == "1X":
            cond_dc = buts_dom >= buts_ext
        elif dc == "X2":
            cond_dc = buts_ext >= buts_dom
        else:  # "12"
            cond_dc = buts_dom != buts_ext
        cond_total = total > ligne if sens == "over" else total < ligne
        return _win(cond_dc and cond_total)

    return ResultatMarche(MARCHE_NON_RECONNU)
