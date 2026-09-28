"""
parse_betpawa.py -- convertit un copier-coller BRUT de la page marchés
Betpawa en cotes_manuelles.

Le périmètre handicap retenu ici est exclusivement :
« Handicap À 3 Choix | Fin de Match ».
Les autres formes de handicap sont ignorées.
"""
import json
import re
import sys


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
                cotes["double_chance"] = {"1N": paires.get("1X"), "N2": paires.get("X2"), "12": paires.get("12")}
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
                cotes.setdefault(f"over_under_{m.group(2)}", {})[cle_sel] = valeur
            continue

        m_equipe = re.match(r"^Plus de/Moins de \| (.+) \| Fin de [Mm]atch$", titre)
        if m_equipe:
            nom = m_equipe.group(1)
            prefixe = "over_under_domicile" if nom == nom_domicile else ("over_under_exterieur" if nom == nom_exterieur else None)
            paires, i = _paires_jusqua_rupture(lignes, i + 1, r"^(Plus|Moins) de \d+\.5$")
            if prefixe:
                for label, valeur in paires.items():
                    m = re.match(r"^(Plus|Moins) de (\d+\.5)$", label)
                    cotes.setdefault(f"{prefixe}_{m.group(2)}", {})["plus" if m.group(1) == "Plus" else "moins"] = valeur
            continue

        if titre == "Handicap À 3 Choix | Fin de Match":
            i += 1
            # En-têtes Betpawa : 1 / X / 2.
            while i < len(lignes) and lignes[i] in {"1", "X", "2"}:
                i += 1
            # Une ligne de tableau = 3 étiquettes + 3 cotes (issues 1, X, 2). La ligne est lue sur la 1re étiquette
            # « Domicile ±N » (handicap du domicile, signe conservé). Les 2e et 3e étiquettes varient selon l'affichage
            # (« Nul -2 » ou « Domicile -2 », « Extérieur +2 » ou « Extérieur -1 ») : seule leur forme est contrôlée.
            # CORRECTIF 28/09/2026 : l'ancienne lecture (« Domicile -N / Nul -N / Extérieur +N » seulement) s'arrêtait
            # à la première ligne « Domicile +1 » : les lignes +1 et +2 n'étaient jamais lues.
            while i + 5 < len(lignes):
                labels = lignes[i], lignes[i + 2], lignes[i + 4]
                m1 = re.match(r"^Domicile\s+([+-]\d+)$", labels[0], re.I)
                if not (m1 and all(re.match(r"^(Domicile|Nul|Extérieur)\s+[+-]\d+$", x, re.I) for x in labels[1:])):
                    break
                try:
                    v1, vx, v2 = (float(lignes[i + k].replace(",", ".")) for k in (1, 3, 5))
                except ValueError:
                    break
                ligne = int(m1.group(1))
                if ligne in (-2, -1, 1, 2):
                    cotes[f"handicap_3issues_{ligne}"] = {"1": v1, "X": vx, "2": v2}
                # V2 INCHANGÉE : le pont V2 (pont_moteur.py) lit « handicap_3choix_N ». On la produit exactement dans
                # le seul cas où l'ancienne lecture la produisait (Domicile -N / Nul -N / Extérieur +N).
                if (re.match(r"^Domicile\s+-\d+$", labels[0], re.I) and re.match(r"^Nul\s+-\d+$", labels[1], re.I)
                        and re.match(r"^Extérieur\s+\+\d+$", labels[2], re.I)):
                    cotes[f"handicap_3choix_{-ligne}"] = {"domicile": v1, "nul": vx, "exterieur": v2}
                i += 6
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

        i += 1

    return cotes


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage : python3 parse_betpawa.py fichier_brut.txt \"Nom Domicile\" \"Nom Exterieur\"", file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        texte = f.read()
    print(json.dumps(parse_betpawa(texte, sys.argv[2], sys.argv[3]), indent=2, ensure_ascii=False))
