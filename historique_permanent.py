# -*- coding: utf-8 -*-
"""Historique permanent des matchs des championnats absents de Football-Data (08/11/2026).

Probleme : data/assemblage/equipes.json est reconstruit chaque nuit pour les SEULES equipes qui ont un match a venir. Des qu'une equipe
a joue et n'a pas de match programme, son bloc disparait ; les matchs qu'elle partageait avec des equipes encore presentes restent,
mais ceux contre d'autres equipes sorties aussi sont perdus (ex. Septemvri - Dunav). L'historique d'un championnat s'appauvrit donc chaque nuit.

Regle : chaque nuit, le bloc de chaque equipe d'un championnat NON couvert par Football-Data est copie dans data/historique_permanent/equipes.json.
- une equipe presente dans l'assemblage du jour : son bloc du jour remplace l'ancien (le jour fait foi, il est reconstruit entierement) ;
- une equipe absente : son dernier bloc connu est conserve et rendu a la lecture (charger_ligues), marque « hors_fenetre ».
Football-Data n'est pas archive ici : ses archives sont deja completes."""
import json, os

RACINE = os.path.dirname(os.path.abspath(__file__))
FICHIER = os.path.join(RACINE, "data", "historique_permanent", "equipes.json")


def lire(fichier=FICHIER):
    try:
        with open(fichier, encoding="utf-8") as f: return json.load(f).get("equipes", {})
    except (OSError, ValueError):
        return {}


def archiver(doc, fichier=FICHIER):
    """Ajoute/remplace les blocs du jour (championnats hors Football-Data) dans l'archive. Retourne (equipes archivees, ajoutees)."""
    A = lire(fichier); avant = len(A)
    for x in doc.get("equipes", []):
        if x.get("couverte_par_football_data") or not x.get("matchs") or not x.get("cle_cache"): continue
        A[x["cle_cache"]] = {k: v for k, v in x.items() if k != "hors_fenetre"}
    os.makedirs(os.path.dirname(fichier), exist_ok=True)
    with open(fichier, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "regle": __doc__.split("Regle :")[1].strip(), "equipes": {k: A[k] for k in sorted(A)}}, f, ensure_ascii=False, separators=(",", ":"))
    return len(A), len(A) - avant


def completer(doc, fichier=FICHIER):
    """Copie de doc + blocs archives des equipes absentes du jour (marques hors_fenetre)."""
    presentes = {x.get("cle_cache") for x in doc.get("equipes", [])}
    en_plus = [{**b, "hors_fenetre": True} for k, b in lire(fichier).items() if k not in presentes]
    return {**doc, "equipes": list(doc.get("equipes", [])) + en_plus}
