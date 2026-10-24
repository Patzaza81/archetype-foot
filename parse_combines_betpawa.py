"""parse_combines_betpawa.py -- marchés COMBINÉS de Betpawa (texte du navigateur automatisé), jamais lus avant le 19/10/2026.

CORRECTIF 24/10/2026 : la page Betpawa Cameroun est en FRANÇAIS (le lecteur principal lit « Double Chance | Fin de Match »,
« Plus de 1.5 », « Oui / Non »), alors que ce lecteur ne connaissait que les titres anglais : aucune cote de combiné n'a jamais été lue
(0 sur 625 matchs). Les titres et étiquettes français sont maintenant compris en plus des anglais : « Double Chance & Plus de/Moins de |
Fin de Match » (séparateur « & », « et », « and » ou « + »), « Plus de 1.5 » / « Moins de 2.5 », « Oui » / « Non », lignes « 1X & Oui ».
La forme exacte de la page française n'a pas encore été vue : `diagnostic_combines` en garde un relevé brut pour vérification.

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
BTTS = {"Yes": "Oui", "No": "Non", "Oui": "Oui", "Non": "Non"}
_TITRE = re.compile(r"^(Double Chance|1X2)\s*(?:&|et|and|\+)\s*(Over/Under|Plus de/Moins de|Plus/Moins|Total(?: de buts)?|Both Teams To Score|"
                    r"Les Deux [ÉE]quipes Marquent)\s*\|\s*(Full Time|Fin de [Mm]atch)$", re.I)


def titre_combine(ligne):
    """(famille, genre) d'un titre de marché combiné, anglais ou français ; None sinon (mi-temps, autre marché)."""
    if ligne in TITRES:
        return TITRES[ligne]
    m = _TITRE.match(ligne.strip())
    if not m:
        return None
    genre = "dc" if m.group(1).lower().startswith("double") else "1x2"
    btts = m.group(2).lower().startswith(("both", "les deux"))
    return (f"{genre}_btts" if btts else f"{genre}_total"), genre


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
    m = re.fullmatch(r"(Over|Under|Plus de|Moins de)\s+(\d+)[.,]5", lab.strip("- ").strip(), re.I)
    return (("plus" if m.group(1).lower() in ("over", "plus de") else "moins"), f"{m.group(2)}.5") if m else None


def _paire_total(lab):
    """« 1X & Plus de 1.5 » -> (« 1X », (« plus », « 1.5 »)) ; None sinon."""
    m = re.fullmatch(r"(\S+)\s*(?:&|et|\+)\s*((?:Over|Under|Plus de|Moins de)\s+\d+[.,]5)", lab.strip("- ").strip(), re.I)
    return (m.group(1), _total(m.group(2))) if m else None


def _bloc(lignes, i):
    j = i + 1
    while j < len(lignes) and " | " not in lignes[j]:
        j += 1
    return lignes[i + 1:j], j


def _lit_total(bloc, genre, famille, out):
    """Tableau : en-têtes d'issues, puis « Over 1.5 » suivi d'une cote par colonne (ou d'étiquette/cote en alternance)."""
    k = 0
    entetes = []
    while k < len(bloc) and _nombre(bloc[k]) is None and _total(bloc[k]) is None and _paire_total(bloc[k]) is None:
        if _issue(bloc[k], genre):
            entetes.append(_issue(bloc[k], genre))
        k += 1
    while k < len(bloc):
        pt = _paire_total(bloc[k])
        if pt and _issue(pt[0], genre) and k + 1 < len(bloc) and _nombre(bloc[k + 1]) is not None:
            out.setdefault(f"{famille}_{pt[1][1]}", {})[f"{_issue(pt[0], genre)}|{pt[1][0]}"] = _nombre(bloc[k + 1])
            k += 2
            continue
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
        m = re.fullmatch(r"(\S+)\s*(?:&|et|\+)\s*(Yes|No|Oui|Non)", bloc[k].strip("- ").strip(), re.I)
        if m and _issue(m.group(1), genre) and k + 1 < len(bloc) and _nombre(bloc[k + 1]) is not None:
            out.setdefault(famille, {})[f"{_issue(m.group(1), genre)}|{BTTS[m.group(2).capitalize()]}"] = _nombre(bloc[k + 1])
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
        tc = titre_combine(lignes[i])
        if tc:
            famille, genre = tc
            bloc, i = _bloc(lignes, i)
            (_lit_total if famille.endswith("total") else _lit_btts)(bloc, genre, famille, out)
            continue
        i += 1
    return out


def diagnostic_combines(texte, max_lignes=40):
    """Relevé BRUT (lecture seule) des blocs dont le titre parle de « Double Chance » ou de « 1X2 » combiné, pour vérifier la forme
    réelle de la page française. Ne produit aucune cote."""
    lignes = [l.strip() for l in texte.splitlines() if l.strip()]
    blocs = []
    for i, l in enumerate(lignes):
        if " | " in l and re.search(r"double chance|1x2", l, re.I) and l not in ("1X2 | Fin de Match", "Double Chance | Fin de Match") \
                and re.search(r"&| et |and|\+|plus|moins|over|under|marquent|both", l, re.I):
            blocs.append(lignes[i:i + max_lignes])
    return blocs
