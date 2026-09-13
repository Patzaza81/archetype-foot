"""
observe_tickets_archetype_model.py -- (13/09/2026) orchestrateur nocturne
du mode observation des tickets (Option A, décision de Patrick).

Pourquoi ce script existe : brancher tickets/observation.py dans le
pipeline nocturne, dès le prochain run. Chaque nuit :
1. résout les tickets fictifs PENDING des nuits précédentes dont toutes
   les jambes ont désormais un résultat réel connu -- doit tourner
   APRÈS verifie_resultats_archetype_model.py, sinon les scores tout
   juste trouvés ne seraient pas encore là pour cette résolution ;
2. construit, si possible, UN nouveau ticket fictif à partir des
   sélections encore PENDING de l'archive (matchs pas encore joués) --
   jamais à partir de matchs déjà résolus ;
3. affiche un rapport de calibration à jour (probabilité annoncée vs
   taux de réussite réel sur tous les tickets fictifs résolus à ce jour).

N'écrit jamais dans archive/ ni dans un chemin lu par le site public --
uniquement dans tickets_observes/. Ne modifie jamais
tickets/builder.py ni son seuil réel (100 observations).

Usage : python observe_tickets_archetype_model.py
"""

from __future__ import annotations

import datetime
from typing import Any

from archetype_model.learning import archive, observations
from tickets import builder, observation, rapport_calibration


def _candidats_pending_du_jour(repertoire_archive: str = "archive") -> list[dict[str, Any]]:
    """Toutes les sélections SELECTED encore PENDING (matchs pas encore
    joués) -- le pool dans lequel construire un nouveau ticket fictif.
    Ne considère jamais les COUNTERFACTUAL (jamais de vrais paris) ni les
    RESOLVED/NON_RESOLU_DEFINITIF (matchs déjà tranchés, sans intérêt
    pour un NOUVEAU ticket à suivre)."""
    tous = observations.charge_toutes_les_archives(repertoire_archive)
    return [
        r for r in tous
        if r.get("categorie") == archive.CATEGORIE_SELECTED
        and r.get("resultat_statut") == archive.STATUT_PENDING
    ]


def executer_cycle_observation(
    date_cycle: str | None = None,
    repertoire_archive: str = "archive",
    taille: int = builder.TAILLE_TICKET,
) -> dict[str, Any]:
    """Exécute un cycle complet du mode observation. Retourne toujours un
    résumé, même si aucun ticket n'a pu être construit (0 candidat
    compatible est un résultat honnête, jamais une erreur)."""
    date_cycle = date_cycle or datetime.date.today().isoformat()

    tous = observations.charge_toutes_les_archives(repertoire_archive)
    selections_resolues = [
        r for r in tous
        if r.get("categorie") == archive.CATEGORIE_SELECTED
        and r.get("resultat_statut") == archive.STATUT_RESOLVED
    ]

    # 1. Résoudre les tickets fictifs déjà enregistrés dont les jambes
    #    ont désormais un résultat connu (peu importe le mois où ils ont
    #    été construits -- on ne résout ici que le fichier du mois
    #    courant, les mois précédents ont déjà été résolus lors de leurs
    #    propres cycles ; un ticket qui traînerait plus d'un mois sans
    #    résolution serait de toute façon visible dans le rapport comme
    #    PENDING).
    chemin_mois = observation.chemin_tickets_observes(date_cycle)
    observation.resoudre_tickets_observes(chemin_mois, selections_resolues)

    # 2. Construire un nouveau ticket fictif à partir des candidats
    #    encore PENDING.
    candidats_du_jour = _candidats_pending_du_jour(repertoire_archive)
    marginal, matrice = builder.construire_marginal_et_matrice(selections_resolues)
    nouveau_ticket = observation.construire_ticket_observation(
        candidats_du_jour, marginal, matrice, taille=taille
    )

    if nouveau_ticket is not None:
        observation.enregistrer_ticket_observe(nouveau_ticket, date_cycle)

    # 3. Rapport de calibration à jour, sur l'ensemble des tickets
    #    fictifs déjà résolus (tous mois confondus).
    tous_tickets_observes = rapport_calibration.charge_tous_les_tickets_observes()
    rapport = rapport_calibration.construit_rapport(tous_tickets_observes)

    return {
        "date_cycle": date_cycle,
        "nb_candidats_pending": len(candidats_du_jour),
        "ticket_construit": nouveau_ticket is not None,
        "rapport": rapport,
    }


def main():
    resume = executer_cycle_observation()
    ticket_txt = (
        "1 ticket fictif construit"
        if resume["ticket_construit"]
        else "aucun ticket fictif construit (pas assez de jambes compatibles à ce jour)"
    )
    rapport = resume["rapport"]
    if rapport["nb_tickets_resolus"] > 0:
        rapport_txt = (
            f"{rapport['nb_tickets_resolus']} ticket(s) fictif(s) résolu(s) au total -- "
            f"probabilité annoncée moyenne {rapport['probabilite_annoncee_moyenne']:.3f}, "
            f"taux de réussite réel {rapport['taux_reussite_reel']:.3f} "
            f"(écart {rapport['ecart']:+.3f})"
        )
    else:
        rapport_txt = "aucun ticket fictif résolu pour l'instant"
    print(
        f"[tickets observation] {resume['date_cycle']} -- "
        f"{resume['nb_candidats_pending']} candidat(s) PENDING disponible(s) -- "
        f"{ticket_txt}. {rapport_txt}"
    )


if __name__ == "__main__":
    main()
