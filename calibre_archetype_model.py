"""
calibre_archetype_model.py -- (13/09/2026) orchestrateur nocturne de la
calibration adaptative.

Pourquoi ce script existe : calibration.py, garde_fous.py, validation.py
et contrefactuel.py existent depuis cette même session, mais aucun script
ne les appelait automatiquement -- ce fichier est le point d'entrée que
pipeline.yml exécute chaque nuit, après le bilan comportemental
(calcule_matrice_archetype_model.py).

Pour chaque paramètre calibrable TESTABLE (les 7 sur 8 que
contrefactuel.py sait simuler -- ROBUSTNESS_STD_THRESHOLD est
explicitement exclu, voir contrefactuel.py) :
    1. compte les observations résolues dans le bracket concerné ;
    2. propose deux variations symétriques (-pas et +pas, où le pas est
       une fraction du plafond d'amplitude de garde_fous.py -- jamais le
       plafond lui-même, marge de sécurité) ;
    3. fait passer chaque proposition par
       calibration.evaluer_proposition() (garde-fous PUIS validation hors
       échantillon) ;
    4. promeut la PREMIÈRE proposition qui obtient un verdict PROMU (au
       plus une par paramètre et par cycle -- arrête immédiatement l'essai
       de la direction opposée pour ne jamais tester une seconde
       proposition contre une valeur actuelle devenue obsolète) ; sinon
       journalise un rejet pour chaque direction testée.

Toujours termine par un enregistrement de cycle
(journal.enregistrer_cycle), même quand rien n'est promu -- répond à
"le système a-t-il seulement tourné cette nuit ?".

Ne modifie jamais selector.py/convergence.py/deduplication.py -- lit
uniquement l'archive et écrit uniquement dans config/ et le journal.
"""

from __future__ import annotations

import datetime
from typing import Any

from archetype_model.learning import archive, calibration, contrefactuel, garde_fous, journal, observations

FICHIER_JOURNAL_CYCLE = "config/journal_cycle.jsonl"
FICHIER_JOURNAL_PROMOTION = "config/journal_promotion.jsonl"
FACTEUR_PAS_ESSAI = 0.8  # 80% du plafond d'amplitude -- marge de sécurité, jamais le plafond exact

PARAMETRES_TESTABLES = sorted(contrefactuel.PARAMETRES_EDV_MIN | contrefactuel.PARAMETRES_COTE)


def _pas_essai(parametre: str) -> float:
    plafond = (
        garde_fous.AMPLITUDE_MAX_RENFORCEE
        if parametre in garde_fous.PARAMETRES_A_GARDE_FOUS_RENFORCES
        else garde_fous.AMPLITUDE_MAX_STANDARD
    )
    return plafond * FACTEUR_PAS_ESSAI


def _compte_observations_parametre(
    parametre: str,
    selections: list[dict[str, Any]],
    contrefactuels: list[dict[str, Any]],
) -> int:
    if parametre in contrefactuel.PARAMETRES_EDV_MIN:
        return sum(
            1 for r in selections + contrefactuels
            if contrefactuel.bracket_edv_min(r.get("probabilite")) == parametre
        )
    if parametre in contrefactuel.PARAMETRES_COTE:
        return len(selections) + sum(
            1 for r in contrefactuels if r.get("motif_rejet") == "COTE_HORS_INTERVALLE"
        )
    return 0


def executer_cycle(date_cycle: str | None = None) -> dict[str, Any]:
    """Exécute un cycle complet de calibration sur l'archive actuelle.
    Retourne toujours le résumé de cycle, même si aucune donnée n'était
    disponible (0 observation -> 0 proposition, cycle quand même
    journalisé)."""
    date_cycle = date_cycle or datetime.date.today().isoformat()

    tous_records = observations.charge_toutes_les_archives()
    selections_resolues = [
        r for r in tous_records
        if r.get("categorie") == archive.CATEGORIE_SELECTED
        and r.get("resultat_statut") == archive.STATUT_RESOLVED
    ]
    contrefactuels_resolus = [
        r for r in tous_records
        if r.get("categorie") == archive.CATEGORIE_COUNTERFACTUAL
        and r.get("resultat_statut") == archive.STATUT_RESOLVED
    ]

    parametres_actifs = calibration.charger_parametres()["parametres"]

    nb_propositions = nb_promotions = nb_rejets = 0

    for parametre in PARAMETRES_TESTABLES:
        bloc = parametres_actifs.get(parametre)
        if bloc is None:
            continue  # paramètre absent de la configuration active -- rien à calibrer ici
        valeur_actuelle = bloc["valeur"]
        valeur_origine = bloc.get("valeur_origine", valeur_actuelle)
        nb_observations = _compte_observations_parametre(parametre, selections_resolues, contrefactuels_resolus)
        pas = _pas_essai(parametre)

        for signe in (-1, 1):
            valeur_proposee = valeur_actuelle * (1 + signe * pas)
            nb_propositions += 1
            verdict = calibration.evaluer_proposition(
                parametre, valeur_actuelle, valeur_origine, valeur_proposee,
                nb_observations, selections_resolues, contrefactuels_resolus,
            )
            if verdict["decision"] == "PROMU":
                calibration.promouvoir(
                    parametre, valeur_proposee, date_cycle,
                    evidence={"etape": verdict["etape"], "nb_observations": nb_observations},
                    chemin_journal_promotion=FICHIER_JOURNAL_PROMOTION,
                )
                nb_promotions += 1
                break  # jamais tester la direction opposée contre une valeur devenue obsolète
            calibration.rejeter(
                parametre, valeur_actuelle, valeur_proposee, date_cycle,
                verdict["motif"], chemin_journal_promotion=FICHIER_JOURNAL_PROMOTION,
            )
            nb_rejets += 1

    resume_cycle = {
        "date_cycle": date_cycle,
        "observations": len(selections_resolues) + len(contrefactuels_resolus),
        "parametres_analyses": len(PARAMETRES_TESTABLES),
        "propositions": nb_propositions,
        "promotions": nb_promotions,
        "rejets": nb_rejets,
        "rollback": 0,
        "constat_majeur": False,
    }
    journal.enregistrer_cycle(FICHIER_JOURNAL_CYCLE, resume_cycle)
    return resume_cycle


def main():
    resume = executer_cycle()
    print(
        f"[calibration] cycle {resume['date_cycle']} -- "
        f"{resume['observations']} observation(s) résolue(s) -- "
        f"{resume['parametres_analyses']} paramètre(s) analysé(s) -- "
        f"{resume['propositions']} proposition(s), "
        f"{resume['promotions']} promue(s), {resume['rejets']} rejetée(s)."
    )


if __name__ == "__main__":
    main()
