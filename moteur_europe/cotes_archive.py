"""Lecture des cotes de l'archive (BetPawa puis cotes observées) en noms de marchés. Copie autonome du moteur Europe."""


def _cote_ok(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v > 1



# Cotes BetPawa brutes (cotes_manuelles) -> noms de MARCHES. Handicaps volontairement absents.
_BETPAWA = {("1x2", "1"): "victoire", ("1x2", "N"): "nul", ("1x2", "2"): "defaite",
            ("double_chance", "1N"): "dc_1X", ("double_chance", "N2"): "dc_X2", ("double_chance", "12"): "dc_12",
            ("btts", "Oui"): "btts_oui", ("btts", "Non"): "btts_non",
            ("cages_inviolees_domicile", "oui"): "clean_sheet_dom",
            ("cages_inviolees_domicile", "non"): "clean_sheet_dom_non",
            ("cages_inviolees_exterieur", "oui"): "clean_sheet_ext",
            ("cages_inviolees_exterieur", "non"): "clean_sheet_ext_non"}
_OBSERVEES = {"1X2 - 1": "victoire", "1X2 - X": "nul", "1X2 - 2": "defaite", "Double chance - 1X": "dc_1X",
              "Double chance - X2": "dc_X2", "Double chance - 12": "dc_12", "BTTS - oui": "btts_oui",
              "BTTS - non": "btts_non", "Cage inviolée - Domicile": "clean_sheet_dom",
              "Encaisse au moins 1 but - Domicile": "clean_sheet_dom_non",   # complément de « Cage inviolée - Domicile »
              "Cage inviolée - Extérieur": "clean_sheet_ext",
              "Encaisse au moins 1 but - Extérieur": "clean_sheet_ext_non"}
for _x in range(6):
    _BETPAWA[(f"over_under_{_x}.5", "plus")] = f"over_{_x}_5"
    _BETPAWA[(f"over_under_{_x}.5", "moins")] = f"under_{_x}_5"
    _OBSERVEES[f"Plus de {_x}.5 buts"] = f"over_{_x}_5"
    _OBSERVEES[f"Moins de {_x}.5 buts"] = f"under_{_x}_5"
for _x in range(2):
    for _cote, _nom, _libelle in (("dom", "domicile", "Domicile"), ("ext", "exterieur", "Extérieur")):
        _BETPAWA[(f"over_under_{_nom}_{_x}.5", "plus")] = f"buts_{_cote}_over_{_x}_5"
        _BETPAWA[(f"over_under_{_nom}_{_x}.5", "moins")] = f"buts_{_cote}_under_{_x}_5"
        _OBSERVEES[f"Plus de {_x}.5 buts - {_libelle}"] = f"buts_{_cote}_over_{_x}_5"
        _OBSERVEES[f"Moins de {_x}.5 buts - {_libelle}"] = f"buts_{_cote}_under_{_x}_5"
for _n in range(6):
    _BETPAWA[("nombre_exact_buts", str(_n))] = f"exact_goals_{_n}"
_BETPAWA[("nombre_exact_buts", "6+")] = "exact_goals_6_plus"


def cotes_archive(e):
    """Cotes d'un enregistrement de l'archive, en noms de MARCHES : BetPawa d'abord, cotes observées en complément."""
    cotes = {}
    for (groupe, issue), marche in _BETPAWA.items():
        v = ((e.get("cotes_betpawa") or {}).get(groupe) or {}).get(issue)
        if _cote_ok(v):
            cotes[marche] = v
    for nom, marche in _OBSERVEES.items():
        v = (e.get("cotes_observees") or {}).get(nom)
        if marche not in cotes and _cote_ok(v):
            cotes[marche] = v
    return cotes
