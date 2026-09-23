# -*- coding: utf-8 -*-
"""Branche un DEUXIÈME moteur sur le pipeline, au même point exact que branchement_moteur.applique_moteur (voir
precalcul.applique_moteur_pipeline), SANS second scraping : réutilise les mêmes `signaux` (cotes déjà résolues) et le
même dict `stats_equipes` déjà chargé par charge_stats_saison() lors du premier appel.

Pourquoi aucun scraping supplémentaire n'est nécessaire : stats_saison_en_cours.recupere_gf_ga_avec_cache() vérifie
le cache AVANT tout accès réseau. Le premier appel (moteur_v2_6_9) a déjà rempli ce cache pour toutes les équipes de
la fenêtre. Rappeler applique_moteur_shrink(signaux, STATS_EQUIPES_VUES, ...) juste après, avec les MÊMES stats_equipes,
ne déclenche donc aucune requête réseau supplémentaire — seulement un second calcul, local, sur les données déjà en
mémoire. Cette fonction n'appelle jamais charge_stats_saison() elle-même : c'est délibéré, pour rendre l'absence de
second scraping visible dans le code, pas seulement vraie par effet de cache.

Usage dans precalcul.main(), juste après `signaux = applique_moteur_pipeline(signaux)` :

    from moteur_shrink_pipeline import applique_moteur_shrink
    resume_shrink = applique_moteur_shrink(signaux, STATS_EQUIPES_VUES, h2h_fetcher=_h2h_pour_signal,
                                            archiver=archiver_shrink)

Écrit sur chaque signal un bloc `shrink_v1` de MÊME FORME que le bloc `moteur_v2_6_9` (statut, verdict, sélection
P1/P2/P3, inventaire) — voir CLE_BLOC dans branchement_moteur.py, la nomenclature est réutilisée à l'identique côté
site (une page dédiée lit `s["shrink_v1"]` au lieu de `s[bm.CLE_BLOC]`)."""
import contextlib
import copy
from typing import Any, Callable, Dict, List, Optional, Tuple

import branchement_moteur as bm
import moteur_v2_6_9 as moteur
import pont_moteur
import evaluation.modeles.shrink_v1 as shrink

CLE_BLOC_SHRINK = "shrink_v1"
CONFIG_VERSION_SHRINK = "shrink_v1-K4"     # à incrémenter si K ou mu sont un jour reréglés


def archiver_shrink(archive_module):
    """Construit l'archiveur à passer à applique_moteur_shrink(archiver=...). Écrit dans archive_shrink/AAAA-MM.json
    (JAMAIS archive/AAAA-MM.json : ce dossier appartient à moteur_v2_6_9 et alimente roi_dashboard.json — le mélanger
    y ferait passer les choix de shrink_v1 pour ceux du moteur principal). model_version="shrink_v1", jamais
    NOM_MOTEUR (bm.archive_bloc écrit NOM_MOTEUR en dur, donc il n'est PAS réutilisé ici)."""
    def archiver(signal, bloc, non_selectionnes):
        match = {"match_id": signal.get("match_id"), "date_match": signal.get("date"), "heure_match": signal.get("heure"),
                 "equipe_dom": signal.get("domicile"), "equipe_ext": signal.get("exterieur"), "competition": signal.get("competition")}
        selections = [bloc["selection"][r] for r in bm.RANGS if bloc["selection"].get(r)]
        if not selections and not non_selectionnes:
            return 0
        return archive_module.enregistrer_selection_et_contrefactuels(
            match=match, selections=selections, contrefactuels=non_selectionnes,
            model_version=CLE_BLOC_SHRINK, config_version=CONFIG_VERSION_SHRINK,
            chemin=archive_module.chemin_archive_mensuelle(match["date_match"], repertoire="archive_shrink"))
    return archiver


@contextlib.contextmanager
def _moteur_avec_shrink(entree: Dict[str, Any]):
    """Substitue construire_matrice/calcul_lambdas_trace le temps d'un match, restaure toujours ensuite -- même
    mécanisme que evaluation/rejoue_moteur.py, déjà utilisé pour valider shrink_v1 sur les 501 matchs.

    `entree` doit être le dict construit par pont_moteur.match_vers_moteur() pour CE match (equipe_dom/equipe_ext
    avec matchs_joues) -- shrink.lambdas() en a besoin pour calculer le poids du tirage vers la référence commune.
    Un dict vide {} désactive silencieusement tout le shrinkage (voir _shrink() dans evaluation/modeles/shrink_v1.py :
    n=None -> valeur brute renvoyée telle quelle) -- BUG corrigé le 23/09/2026, shrink_v1 tournait comme une copie
    exacte de moteur_v2_6_9 depuis son branchement, sans qu'aucune erreur ne le signale (voir ROADMAP)."""
    orig_matrice, orig_trace = moteur.construire_matrice, moteur.calcul_lambdas_trace

    def trace(att_d, def_d, att_e, def_e):
        ld_brut, le_brut = shrink.lambdas(att_d, def_d, att_e, def_e, entree)
        ld = max(moteur.LAMBDA_MIN, min(moteur.LAMBDA_MAX, ld_brut))
        le = max(moteur.LAMBDA_MIN, min(moteur.LAMBDA_MAX, le_brut))
        return ld, le, {"dom": {"brut": ld_brut, "clampe": ld, "clamp_applique": ld != ld_brut},
                        "ext": {"brut": le_brut, "clampe": le, "clamp_applique": le != le_brut}}

    moteur.construire_matrice = lambda ld, le: shrink.matrice(ld, le, entree)
    moteur.calcul_lambdas_trace = trace
    try:
        yield
    finally:
        moteur.construire_matrice, moteur.calcul_lambdas_trace = orig_matrice, orig_trace


def applique_moteur_shrink(signaux: List[Dict[str, Any]], stats_equipes: Dict[Tuple[str, str], Any], *,
                           maintenant=None, h2h_fetcher: Optional[Callable] = None,
                           archiver: Optional[Callable] = None) -> Dict[str, Any]:
    """Même contrat de retour que branchement_moteur.applique_moteur. N'appelle jamais analyse_signal() sans la
    substitution active : shrink_v1 ne doit jamais, même par accident, être évalué avec les lambdas de v2.6.9.

    Reconstruit le dict `entree` (equipe_dom/equipe_ext, matchs_joues) via pont_moteur.match_vers_moteur() -- la
    MÊME fonction, pure, que analyse_signal() appelle en interne pour le même signal -- afin de le transmettre à
    shrink.lambdas(). Un signal non exportable (NON_EXPORTABLE) donne entree={} : shrink_v1 tombera alors sur le
    même statut NON_EXPORTABLE qu'affiche déjà moteur_v2_6_9 pour ce signal, sans jamais planter."""
    import datetime
    maintenant = maintenant or datetime.datetime.now(datetime.timezone.utc)
    horodatage = maintenant.strftime("%Y-%m-%dT%H:%M:%SZ")
    statuts: Dict[str, int] = {}
    nb_selectionnes = nb_avec_choix = nb_archives = nb_erreurs_archive = 0
    for s in signaux:
        try:
            entree, _raison = pont_moteur.match_vers_moteur(s, stats_equipes, horodatage)
            with _moteur_avec_shrink(entree or {}):
                bloc, non_selectionnes = bm.analyse_signal(s, stats_equipes, maintenant, h2h_fetcher)
        except Exception as e:
            bloc, non_selectionnes = bm.bloc_non_analyse("ERREUR_TECHNIQUE", f"{type(e).__name__}: {e}"), []
        s["shrink_v1_utilise"] = "shrink_v1"
        s[CLE_BLOC_SHRINK] = bloc
        statuts[bloc["statut"]] = statuts.get(bloc["statut"], 0) + 1
        if bloc["statut"] != "OK":
            continue
        n = sum(1 for r in bm.RANGS if bloc["selection"].get(r))
        nb_selectionnes += n
        nb_avec_choix += 1 if n else 0
        if archiver is not None and (n or non_selectionnes):
            try:
                nb_archives += archiver(s, bloc, non_selectionnes) or 0
            except Exception as e:
                nb_erreurs_archive += 1
    return {"nb_signaux": len(signaux), "statuts": statuts, "nb_matchs_avec_choix": nb_avec_choix,
            "nb_choix_retenus": nb_selectionnes, "nb_archives": nb_archives, "nb_erreurs_archive": nb_erreurs_archive}
