"""Suivi nocturne de l'onglet « Meilleures sélections » : recalibrage hebdomadaire automatique, classement du jour, bilan.

    python -m meilleures_selections.suivi [pipeline|calibrer|rejeu]

Sorties (data/meilleures_selections/) :
  historique_calibrations.json  instantanés successifs (ajout seul) : permet de mesurer le résultat HORS échantillon ;
  classement.json               sélections du jour retenues, avec leur groupe, et le bilan affiché sur les pages.
Ne bloque jamais le pipeline : toute erreur est écrite et le fichier précédent reste en place."""
from __future__ import annotations

import datetime
import json
import os
import sys
from typing import Any

from . import donnees, regles

DOSSIER = "data/meilleures_selections"
HISTORIQUE = os.path.join(DOSSIER, "historique_calibrations.json")
CLASSEMENT = os.path.join(DOSSIER, "classement.json")


def _lit(chemin: str, defaut):
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return defaut


def _ecrit(chemin: str, objet) -> None:
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(objet, f, ensure_ascii=False, indent=1)


def jour_du_systeme() -> str:
    return (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)).date().isoformat()   # heure du Cameroun


def construire(jour: str, paris: list[dict[str, Any]], selections: list[dict[str, Any]], historique: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Cœur testable : retourne (historique mis à jour, contenu de classement.json). Aucun accès fichier."""
    historique = list(historique)
    recalibre = regles.recalibrage_du(historique, jour)
    if recalibre:
        historique.append(regles.photographie(paris, jour))
    actuel = max(historique, key=lambda h: h["calibre_le"])
    classees = regles.classer(selections, actuel["groupes"])
    r = regles.rejeu(paris)
    prochain = (datetime.date.fromisoformat(actuel["calibre_le"]) + datetime.timedelta(days=regles.PERIODE_JOURS)).isoformat()
    sortie = {"genere_le": jour, "calibre_le": actuel["calibre_le"], "prochain_recalibrage": prochain, "recalibre_aujourdhui": recalibre,
              "nb_paris_calibrage": actuel["nb_paris"], "m_tests": actuel["m_tests"],
              "seuil_confirme": actuel["seuil_confirme"], "seuil_observation": actuel["seuil_observation"],
              "groupes": actuel["groupes"],
              "bilan_historique": regles.bilan_historique(paris, actuel["groupes"]),
              "hors_echantillon": regles.bilan_hors_echantillon(paris, historique),
              "rejeu": {"nb_recalibrages": len(r["instantanes"]), "bilan": r["bilan"]},
              "selections": classees}
    return historique, sortie


def pipeline() -> int:
    jour = jour_du_systeme()
    paris = donnees.paris_resolus()
    selections = donnees.selections_du_jour(jour)
    historique, sortie = construire(jour, paris, selections, _lit(HISTORIQUE, []))
    _ecrit(HISTORIQUE, historique)
    _ecrit(CLASSEMENT, sortie)
    print(f"[meilleures sélections] {len(paris)} paris résolus ; calibré le {sortie['calibre_le']} "
          f"({'recalibré aujourd’hui' if sortie['recalibre_aujourdhui'] else 'prochain le ' + sortie['prochain_recalibrage']}) ; "
          f"{len(sortie['groupes'])} groupe(s) admis ; {len(sortie['selections'])} sélection(s) retenue(s) sur {len(selections)}.")
    return 0


def rejeu_cmd() -> int:
    r = regles.rejeu(donnees.paris_resolus())
    print(json.dumps({"instantanes": [{k: h[k] for k in ("calibre_le", "nb_paris", "m_tests")} | {"groupes": [(g["moteur"], g["famille"], g["palier"], g["statut"], g["n"]) for g in h["groupes"]]} for h in r["instantanes"]],
                      "hors_echantillon": r["bilan"]}, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    commande = sys.argv[1] if len(sys.argv) > 1 else "pipeline"
    try:
        sys.exit({"pipeline": pipeline, "rejeu": rejeu_cmd}[commande]())
    except Exception as e:  # ne bloque jamais le pipeline
        print(f"[meilleures sélections] ERREUR : {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
