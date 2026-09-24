#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stats_saison_en_cours.py -- statistiques d'équipe du moteur v2.6.9 : SAISON EN COURS UNIQUEMENT, matchs les PLUS RÉCENTS.

Pourquoi ce module existe (21/09/2026). Le pont vers le moteur (pont_moteur.py) était alimenté par
`scraper_details.recupere_gf_ga_avec_repli`, que `archetype_model/data/loader.py` écarte explicitement
(décision de Patrick du 08/09/2026, « invariant non négociable v3 §4.1 », « à ne pas rouvrir sans lui en parler ») :
  1. elle COMPLÈTE avec la saison précédente quand la saison en cours est trop courte ; les matchs fusionnés ne portent
     plus de tag de saison, on ne peut plus les distinguer ;
  2. elle prend les N PREMIERS matchs de la page, or la page liste les matchs du plus ancien au plus récent : ce sont
     donc les N plus anciens, l'inverse d'une forme récente.
Mesuré sur le cache du 20/09 : 52 % des équipes avaient plus de matchs que la saison en cours ne le permet, et 82 %
des choix du moteur reposaient sur une telle équipe. Les « séries » de la bibliothèque de justification, comptées
depuis la FIN de la liste, décrivaient alors des matchs de la saison précédente.

Ce module réutilise le chargeur déjà éprouvé en production (`loader.recupere_historique_saison_courante` : un seul
fetch, aucun `?season=`, ordre chronologique croissant) et la fenêtre de `validation` (12 plus récents par lieu).
Sortie : même forme que `recupere_gf_ga_avec_repli`, pour que le pont et la bibliothèque n'aient rien à changer ; les
listes `matchs_*_bruts` sont en ordre CHRONOLOGIQUE CROISSANT (le plus récent en dernier, comme la bibliothèque
l'attend). Aucun repli : une équipe sans match cette saison est refusée avec une raison explicite.
"""
from __future__ import annotations

from typing import Any, Dict, List

from archetype_model.data import loader as _loader
from archetype_model.data.validation import N_MAX_FENETRE

FICHIER_CACHE_SAISON = "cache_equipes_saison.json"      # distinct de cache_equipes.json (données à repli, ancien format)
SOURCE = "saison_en_cours_seule"
RAISON_AUCUN_MATCH = "aucun_match_saison_en_cours"
RAISON_SAISON_INCOHERENTE = "saison_incoherente_avec_resultats_connus"

_RESULTATS_CONNUS = None


def _resultats_connus():
    """Scores réels connus par les pages de match (échantillon + historique), chargés une fois par exécution."""
    global _RESULTATS_CONNUS
    if _RESULTATS_CONNUS is None:
        import controle_saisons
        _RESULTATS_CONNUS = controle_saisons.resultats_connus()
    return _RESULTATS_CONNUS


def controle_coherence(url_equipe: str, nom_equipe: str, nom_competition: str,
                       historique: List[Dict[str, Any]]) -> Dict[str, Any]:
    """AJOUT 24/09/2026 -- garde-fou : la saison lue sur la page doit contenir chaque match déjà connu par les pages
    de match (même compétition, joué avant aujourd'hui, même lieu, mêmes buts). Voir controle_saisons.py.
    Renvoie la ligne de contrôle (statut COHERENTE / INCOHERENTE / NON_VERIFIABLE)."""
    import datetime
    import controle_saisons as cs
    connus = _resultats_connus()
    slug = cs.slug_equipe(url_equipe)
    vue = {slug: connus.get(slug) or connus.get(cs.normalise(nom_equipe), [])}
    entree = {"horodatage": datetime.datetime.now(datetime.timezone.utc).date().isoformat(),
              "resultat": {"matchs_domicile_bruts": [m for m in historique if m["domicile"]],
                           "matchs_exterieur_bruts": [m for m in historique if not m["domicile"]]}}
    return cs.controle_equipe(f"{url_equipe}||{nom_competition}", entree, vue)


def _moyenne(matchs: List[Dict[str, Any]], cle: str) -> float:
    return sum(m[cle] for m in matchs) / len(matchs)


def stats_saison_en_cours(url_equipe: str, nom_equipe: str, nom_competition: str,
                          max_matchs: int = N_MAX_FENETRE) -> Dict[str, Any]:
    """Statistiques d'une équipe : ses `max_matchs` matchs les plus récents À DOMICILE et ses `max_matchs` plus récents
    À L'EXTÉRIEUR, dans la compétition du match, saison en cours seulement. Peut lever (réseau) : l'appelant décide."""
    historique = _loader.recupere_historique_saison_courante(url_equipe, nom_competition, nom_equipe)
    # AJOUT 24/09/2026 -- une saison qui contredit un résultat réel connu n'est jamais donnée au moteur (NO DATA ->
    # NO GO) : c'était le cas de 23 % des équipes avant la correction de la lecture des pages (ex. The New Saints).
    if historique:
        verif = controle_coherence(url_equipe, nom_equipe, nom_competition, historique)
        if verif["statut"] == "INCOHERENTE":
            return {"raison_non_traite": RAISON_SAISON_INCOHERENTE, "manquants": verif["manquants"][:3]}
    domicile, exterieur = _loader.separe_domicile_exterieur(historique)
    domicile = domicile[-max_matchs:] if max_matchs else domicile        # les PLUS RÉCENTS (liste croissante)
    exterieur = exterieur[-max_matchs:] if max_matchs else exterieur
    if not domicile and not exterieur:
        return {"raison_non_traite": RAISON_AUCUN_MATCH}
    resultat: Dict[str, Any] = {
        "nb_domicile": len(domicile), "nb_exterieur": len(exterieur),
        "matchs_domicile_bruts": domicile, "matchs_exterieur_bruts": exterieur,
        "nb_matchs_saison_courante": len(historique), "source": SOURCE,
    }
    if domicile:
        resultat["gf_domicile"] = _moyenne(domicile, "buts_marques")
        resultat["ga_domicile"] = _moyenne(domicile, "buts_encaisses")
    if exterieur:
        resultat["gf_exterieur"] = _moyenne(exterieur, "buts_marques")
        resultat["ga_exterieur"] = _moyenne(exterieur, "buts_encaisses")
    return resultat
