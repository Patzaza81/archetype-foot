"""
parse_betpawa.py -- convertit un copier-coller BRUT de la page marchés
Betpawa (tel quel, sans tri manuel) en cotes_manuelles pour panier.json.

Ignore volontairement et silencieusement tout ce que le modèle ne sait pas
exploiter : corners, cartons, joueurs, mi-temps, 1UP/2UP, prochain but,
multiscores, etc. Aucun message d'erreur pour ces sections -- absence de
correspondance = non pertinent, pas un problème.

Usage :
    python3 parse_betpawa.py brut.txt "Crystal Palace" "Manchester City" > cotes.json
"""
import json
import re
import sys


def _lignes_non_vides(texte):
    return [l.strip() for l in texte.splitlines() if l.strip()]


def _paires(lignes, i, n):
    """Lit n paires (label, valeur_float) à partir de l'index i. Retourne
    (dict label->valeur, index après la dernière paire lue)."""
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
    """Lit des paires (label, valeur) tant que label correspond à motif_label
    (regex). S'arrête à la première ligne qui ne correspond pas -- c'est ce
    qui délimite naturellement la fin d'une section sur une page Betpawa."""
    resultat = {}
    while i + 1 < len(lignes) and re.match(motif_label, lignes[i]):
        label, valeur = lignes[i], lignes[i + 1]
        try:
            resultat[label] = float(valeur.replace(",", "."))
        except ValueError:
            break
        i += 2
    return resultat, i


def parse_betpawa(texte, nom_domicile, nom_exterieur):
    lignes = _lignes_non_vides(texte)
    cotes = {}
    i = 0
    while i < len(lignes):
        titre = lignes[i]

        if titre == "1X2 | Fin de Match":
            paires, i = _paires(lignes, i + 1, 3)
            if len(paires) == 3:
                cotes["1x2"] = {"1": paires.get("1"), "N": paires.get("X"), "2": paires.get("2")}
            continue

        if titre == "Double Chance | Fin de Match":
            paires, i = _paires(lignes, i + 1, 3)
            if len(paires) == 3:
                cotes["double_chance"] = {
                    "1N": paires.get("1X"), "N2": paires.get("X2"), "12": paires.get("12"),
                }
            continue

        if titre == "Les Deux Équipes Marquent | Fin de Match":
            paires, i = _paires(lignes, i + 1, 2)
            if len(paires) == 2:
                cotes["btts"] = {"Oui": paires.get("Oui"), "Non": paires.get("Non")}
            continue

        if titre == "Plus de/Moins de | Fin de Match":
            paires, i = _paires_jusqua_rupture(lignes, i + 1, r"^(Plus|Moins) de \d+\.5$")
            for label, valeur in paires.items():
                m = re.match(r"^(Plus|Moins) de (\d+\.5)$", label)
                cle_sel = "plus" if m.group(1) == "Plus" else "moins"
                cle_marche = f"over_under_{m.group(2)}"
                cotes.setdefault(cle_marche, {})[cle_sel] = valeur
            continue

        m_equipe = re.match(r"^Plus de/Moins de \| (.+) \| Fin de [Mm]atch$", titre)
        if m_equipe:
            nom = m_equipe.group(1)
            if nom == nom_domicile:
                prefixe = "over_under_domicile"
            elif nom == nom_exterieur:
                prefixe = "over_under_exterieur"
            else:
                prefixe = None
            paires, i = _paires_jusqua_rupture(lignes, i + 1, r"^(Plus|Moins) de \d+\.5$")
            if prefixe:
                for label, valeur in paires.items():
                    m = re.match(r"^(Plus|Moins) de (\d+\.5)$", label)
                    cle_sel = "plus" if m.group(1) == "Plus" else "moins"
                    cle_marche = f"{prefixe}_{m.group(2)}"
                    cotes.setdefault(cle_marche, {})[cle_sel] = valeur
            continue

        if titre == "Handicap À 2 Choix | Fin de Match":
            i += 1
            # deux lignes d'en-tête de colonnes ("1", "2") à sauter
            if i < len(lignes) and lignes[i] == "1":
                i += 1
            if i < len(lignes) and lignes[i] == "2":
                i += 1
            while i + 3 < len(lignes) and re.match(r"^[+-]\d+\.5$", lignes[i]):
                label_dom, val_dom, label_ext, val_ext = lignes[i:i + 4]
                if re.match(r"^[+-]\d+\.5$", label_ext):
                    # normalise "+0.5" -> "0.5" pour matcher str(float) côté
                    # calculs.py/run_pipeline.py (Python n'affiche jamais le
                    # signe "+" d'un float positif)
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

        if titre == "Impair/Pair | Fin de Match":
            paires, i = _paires(lignes, i + 1, 2)
            if len(paires) == 2:
                cotes["pair_impair"] = {"pair": paires.get("Pair"), "impair": paires.get("Impair")}
            continue

        m_cages = re.match(r"^Cages Inviolées \| (.+) \| Fin de Match$", titre)
        if m_cages:
            nom = m_cages.group(1)
            paires, i = _paires(lignes, i + 1, 2)
            if len(paires) == 2:
                if nom == nom_domicile:
                    cotes["cages_inviolees_domicile"] = {"oui": paires.get("Oui"), "non": paires.get("Non")}
                elif nom == nom_exterieur:
                    cotes["cages_inviolees_exterieur"] = {"oui": paires.get("Oui"), "non": paires.get("Non")}
            continue

        if titre == "Score Exact | Fin de Match":
            paires, i = _paires_jusqua_rupture(lignes, i + 1, r"^(\d+-\d+|Other|Autre)$")
            scores = {k: v for k, v in paires.items() if re.match(r"^\d+-\d+$", k)}
            if scores:
                cotes["score_exact"] = scores
            continue

        if titre == "Nombre Exact de Buts | Fin de Match":
            paires, i = _paires_jusqua_rupture(lignes, i + 1, r"^(\d+|\d+\+)$")
            if paires:
                cotes["nombre_exact_buts"] = paires
            continue

        i += 1  # section non reconnue -- ignorée sans message, c'est voulu

    return cotes


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage : python3 parse_betpawa.py fichier_brut.txt \"Nom Domicile\" \"Nom Exterieur\"",
              file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        texte = f.read()
    resultat = parse_betpawa(texte, sys.argv[2], sys.argv[3])
    print(json.dumps(resultat, indent=2, ensure_ascii=False))
