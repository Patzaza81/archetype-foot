"""parse_combines_betpawa.py -- marchés COMBINÉS de Betpawa (page en anglais, texte du navigateur automatisé), jamais lus avant le 19/10/2026.

Titres lus (fin de match seulement) :
  « Double Chance and Over/Under | Full Time »            -> groupe dc_total_<ligne>   , sélection « 1N|plus »
  « 1X2 and Over/Under | Full Time »                      -> groupe 1x2_total_<ligne>  , sélection « 1|moins »
  « Double Chance and Both Teams To Score | Full Time »   -> groupe dc_btts            , sélection « 1N|Oui »
  « 1X2 and Both Teams To Score | Full Time »             -> groupe 1x2_btts           , sélection « 1|Non »
Deux dispositions sont comprises, parce que la page a été vue sous les deux : tableau (colonnes 1X/12/X2, une ligne par « Over 1.5 »)
ou lignes « 1X & Yes » suivies de leur cote. Un bloc illisible est ignoré : un combiné dont la cote n'est pas trouvée n'existe pas
(règle de Patrick : marché suspendu). Ajoute uniquement des groupes NOUVEAUX : aucun marché existant n'est modifié.
"""
import re

TITRES = {
    "Double Chance and Over/Under | Full Time": ("dc_total", "dc"),
    "1X2 and Over/Under | Full Time": ("1x2_total", "1x2"),
    "Double Chance and Both Teams To Score | Full Time": ("dc_btts", "dc"),
    "1X2 and Both Teams To Score | Full Time": ("1x2_btts", "1x2"),
}
DC = {"1X": "1N", "X2": "N2", "12": "12"}
R1X2 = {"1": "1", "X": "N", "2": "2"}
BTTS = {"Yes": "Oui", "No": "Non"}


def _nombre(x):
    if "." not in x and "," not in x:          # une cote s'affiche toujours avec ses décimales ; « 1 », « 2 » sont des étiquettes d'issue
        return None
    try:
        v = float(x.replace(",", "."))
        return v if v > 1 else None
    except ValueError:
        return None


def _issue(lab, genre):
    return (DC if genre == "dc" else R1X2).get(lab.strip("- ").strip())


def _total(lab):
    m = re.fullmatch(r"(Over|Under)\s+(\d+\.5)", lab.strip("- ").strip())
    return (("plus" if m.group(1) == "Over" else "moins"), m.group(2)) if m else None


def _bloc(lignes, i):
    j = i + 1
    while j < len(lignes) and " | " not in lignes[j]:
        j += 1
    return lignes[i + 1:j], j


def _lit_total(bloc, genre, famille, out):
    """Tableau : en-têtes d'issues, puis « Over 1.5 » suivi d'une cote par colonne (ou d'étiquette/cote en alternance)."""
    k = 0
    entetes = []
    while k < len(bloc) and _nombre(bloc[k]) is None and _total(bloc[k]) is None:
        if _issue(bloc[k], genre):
            entetes.append(_issue(bloc[k], genre))
        k += 1
    while k < len(bloc):
        t = _total(bloc[k])
        if not t:
            k += 1
            continue
        k += 1
        vals = []
        while k < len(bloc) and _total(bloc[k]) is None:
            if _nombre(bloc[k]) is not None:
                vals.append((None, _nombre(bloc[k])))
            elif _issue(bloc[k], genre) and k + 1 < len(bloc) and _nombre(bloc[k + 1]) is not None:
                vals.append((_issue(bloc[k], genre), _nombre(bloc[k + 1])))
                k += 1
            k += 1
        for idx, (iss, v) in enumerate(vals):
            iss = iss or (entetes[idx] if idx < len(entetes) and len(vals) == len(entetes) else None)
            if iss:
                out.setdefault(f"{famille}_{t[1]}", {})[f"{iss}|{t[0]}"] = v


def _lit_btts(bloc, genre, famille, out):
    """Lignes « 1X & Yes » + cote, ou tableau (en-têtes Yes/No, ligne « 1X » suivie d'une cote par colonne)."""
    k, entetes = 0, []
    while k < len(bloc):
        m = re.fullmatch(r"(\S+)\s*&\s*(Yes|No)", bloc[k].strip("- ").strip())
        if m and _issue(m.group(1), genre) and k + 1 < len(bloc) and _nombre(bloc[k + 1]) is not None:
            out.setdefault(famille, {})[f"{_issue(m.group(1), genre)}|{BTTS[m.group(2)]}"] = _nombre(bloc[k + 1])
            k += 2
            continue
        if bloc[k].strip("- ").strip() in BTTS and _nombre(bloc[k]) is None:
            entetes.append(BTTS[bloc[k].strip("- ").strip()])
        elif _issue(bloc[k], genre) and entetes:
            vals = []
            k += 1
            while k < len(bloc) and _nombre(bloc[k]) is not None and len(vals) < len(entetes):
                vals.append(_nombre(bloc[k])); k += 1
            if len(vals) == len(entetes):
                for e, v in zip(entetes, vals):
                    out.setdefault(famille, {})[f"{_issue(bloc[k - len(vals) - 1], genre)}|{e}"] = v
            continue
        k += 1


def parse_combines(texte):
    lignes = [l.strip() for l in texte.splitlines() if l.strip()]
    out, i = {}, 0
    while i < len(lignes):
        if lignes[i] in TITRES:
            famille, genre = TITRES[lignes[i]]
            bloc, i = _bloc(lignes, i)
            (_lit_total if famille.endswith("total") else _lit_btts)(bloc, genre, famille, out)
            continue
        i += 1
    return out
