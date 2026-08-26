"""
parse_betpawa_playwright.py -- troisième variante de parseur, pour le
format RÉELLEMENT produit par le navigateur automatisé (confirmé sur
capture d'écran du journal GitHub Actions, 26/08) : titres de marché en
ANGLAIS ("1X2 | Full Time"), mais étiquette et valeur SÉPARÉES sur deux
lignes ("1" puis "4.43") -- ni le format copier-coller (français, séparé)
ni le format de l'outil de récupération de Claude (anglais, collé) ne
correspondaient. Structure de lecture identique à parse_betpawa.py
(paires de lignes), mais titres et libellés de sélection en anglais comme
parse_betpawa_url.py.
"""
import re


def _lignes_non_vides(texte):
    return [l.strip() for l in texte.splitlines() if l.strip()]


def _paires(lignes, i, n):
    resultat = {}
    for _ in range(n):
        if i + 1 >= len(lignes):
            break
        label, valeur = lignes[i], lignes[i + 1]
        try:
            resultat[label] = float(valeur.replace(",", "."))
        except ValueError:
            break
        i += 2
    return resultat, i


def _paires_jusqua_rupture(lignes, i, motif_label):
    resultat = {}
    while i + 1 < len(lignes) and re.match(motif_label, lignes[i]):
        label, valeur = lignes[i], lignes[i + 1]
        try:
            resultat[label] = float(valeur.replace(",", "."))
        except ValueError:
            break
        i += 2
    return resultat, i


def parse_betpawa_playwright(texte, nom_domicile, nom_exterieur):
    lignes = _lignes_non_vides(texte)
    cotes = {}
    i = 0

    while i < len(lignes):
        titre = lignes[i]

        if titre == "1X2 | Full Time":
            paires, i = _paires(lignes, i + 1, 3)
            if len(paires) == 3:
                cotes["1x2"] = {"1": paires.get("1"), "N": paires.get("X"), "2": paires.get("2")}
            continue

        if titre == "Double Chance | Full Time":
            paires, i = _paires(lignes, i + 1, 3)
            if len(paires) == 3:
                cotes["double_chance"] = {
                    "1N": paires.get("1X"), "N2": paires.get("X2"), "12": paires.get("12"),
                }
            continue

        if titre == "Both Teams To Score | Full Time":
            paires, i = _paires(lignes, i + 1, 2)
            if len(paires) == 2:
                cotes["btts"] = {"Oui": paires.get("Yes"), "Non": paires.get("No")}
            continue

        if titre == "Over/Under | Full Time":
            paires, i = _paires_jusqua_rupture(lignes, i + 1, r"^(Over|Under) \d+\.5$")
            for label, valeur in paires.items():
                m = re.match(r"^(Over|Under) (\d+\.5)$", label)
                cle_sel = "plus" if m.group(1) == "Over" else "moins"
                cotes.setdefault(f"over_under_{m.group(2)}", {})[cle_sel] = valeur
            continue

        m_equipe = re.match(r"^Over/Under \| (.+) \| Full Time$", titre)
        if m_equipe:
            nom = m_equipe.group(1)
            prefixe = ("over_under_domicile" if nom == nom_domicile
                       else "over_under_exterieur" if nom == nom_exterieur else None)
            paires, i = _paires_jusqua_rupture(lignes, i + 1, r"^(Over|Under) \d+\.5$")
            if prefixe:
                for label, valeur in paires.items():
                    m = re.match(r"^(Over|Under) (\d+\.5)$", label)
                    cle_sel = "plus" if m.group(1) == "Over" else "moins"
                    cotes.setdefault(f"{prefixe}_{m.group(2)}", {})[cle_sel] = valeur
            continue

        if titre == "2-Way Handicap | Full Time":
            i += 1
            if i < len(lignes) and lignes[i] == "1":
                i += 1
            if i < len(lignes) and lignes[i] == "2":
                i += 1
            while i + 3 < len(lignes) and re.match(r"^[+-]\d+\.5$", lignes[i]):
                label_dom, val_dom, label_ext, val_ext = lignes[i:i + 4]
                if re.match(r"^[+-]\d+\.5$", label_ext):
                    cle_ligne = label_dom[1:] if label_dom.startswith("+") else label_dom
                    try:
                        cotes[f"handicap_{cle_ligne}"] = {
                            "domicile": float(val_dom.replace(",", ".")),
                            "exterieur": float(val_ext.replace(",", ".")),
                        }
                    except ValueError:
                        pass
                    i += 4
                else:
                    break
            continue

        if titre == "Odd/Even | Full Time":
            paires, i = _paires(lignes, i + 1, 2)
            if len(paires) == 2:
                cotes["pair_impair"] = {"pair": paires.get("Even"), "impair": paires.get("Odd")}
            continue

        m_cages = re.match(r"^Clean Sheet \| (.+) \| Full Time$", titre)
        if m_cages:
            nom = m_cages.group(1)
            paires, i = _paires(lignes, i + 1, 2)
            if len(paires) == 2:
                if nom == nom_domicile:
                    cotes["cages_inviolees_domicile"] = {"oui": paires.get("Yes"), "non": paires.get("No")}
                elif nom == nom_exterieur:
                    cotes["cages_inviolees_exterieur"] = {"oui": paires.get("Yes"), "non": paires.get("No")}
            continue

        if titre == "Correct Score | Full Time":
            paires, i = _paires_jusqua_rupture(lignes, i + 1, r"^(\d+-\d+|Other)$")
            scores = {k: v for k, v in paires.items() if re.match(r"^\d+-\d+$", k)}
            if scores:
                cotes["score_exact"] = scores
            continue

        if titre == "Total Goals Exact | Full Time":
            paires, i = _paires_jusqua_rupture(lignes, i + 1, r"^(\d+|\d+\+)$")
            if paires:
                cotes["nombre_exact_buts"] = paires
            continue

        i += 1  # section non reconnue -- ignorée sans message, c'est voulu

    return cotes
