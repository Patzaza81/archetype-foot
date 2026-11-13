"""Collecte du moteur sélections : relit les fichiers déjà scrapés sur Matchendirect
(matchs_du_jour.json, matchs_demain.json, matchs_semaine.json) SANS les modifier,
garde les matchs officiels de sélections (competitions.py) et écrit
data/selections/a_venir.json. Aucun appel réseau, aucun autre fichier touché.

    python -m moteur_selections.collecte
"""
import json
import os

from moteur_selections.competitions import est_selection_officielle

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = ("matchs_du_jour.json", "matchs_demain.json", "matchs_semaine.json")
SORTIE = os.path.join(RACINE, "data", "selections", "a_venir.json")


def _lire(chemin):
    try:
        with open(chemin, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return []
    return d if isinstance(d, list) else []


def collecte(racine=RACINE):
    vus, sortie = set(), []
    for nom in SOURCES:
        for m in _lire(os.path.join(racine, nom)):
            if not est_selection_officielle(m.get("competition")):
                continue
            cle = m.get("match_id") or m.get("url_match")
            if cle in vus:
                continue
            vus.add(cle)
            sortie.append({**m, "competition": " ".join((m.get("competition") or "").split())})
    sortie.sort(key=lambda m: (m.get("date") or "", m.get("heure") or ""))
    return sortie


def main():
    matchs = collecte()
    os.makedirs(os.path.dirname(SORTIE), exist_ok=True)
    with open(SORTIE, "w", encoding="utf-8") as f:
        json.dump(matchs, f, ensure_ascii=False, indent=1)
    print(f"selections: {len(matchs)} matchs officiels de sélections -> {os.path.relpath(SORTIE, RACINE)}")


if __name__ == "__main__":
    main()
