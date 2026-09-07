"""
brancher_moteur_v0.py — Adaptateur MINCE entre les données réelles déjà
scrapées par le pipeline existant et moteur_v0.py (décision Patrick,
07/09/2026 : "le branchement ne doit introduire aucune nouvelle règle de
calcul ou décision").

Ce fichier ne fait QUE de la plomberie :
    1. lire les mêmes matchs que le pipeline principal (mêmes fichiers,
       même fonction de normalisation) ;
    2. appeler les mêmes fonctions de scraping déjà testées, TELLES QUELLES
       (aucune réimplémentation) ;
    3. reformater leur sortie dans la forme exacte attendue par
       moteur_v0.evalue_match_v0() -- pur renommage/réarrangement de clés,
       aucune transformation de valeur, aucun nouveau seuil ;
    4. journaliser via moteur_v0.enregistre_evaluation_v0().

MODE OBSERVATION UNIQUEMENT :
    - Ne modifie JAMAIS precalcul.json / precalcul_leger.json / panier.json
      ni aucun fichier de DÉCISION du pipeline existant.
    - N'influence AUCUNE décision réelle, AUCUN pari réel.
    - Écrit dans historique_v0.jsonl (résultats V0) ET dans
      cache_equipes.json (PARTAGÉ avec le pipeline principal, via
      cache_equipes.recupere_gf_ga_avec_cache -- voir doctrine ci-dessous.
      C'est un cache additif de données déjà publiques (GF/GA d'une
      équipe), jamais un champ de décision -- le partager est le but
      recherché : réutiliser ce que le pipeline principal a déjà récupéré
      plutôt que de re-scraper).
    - Tourne EN PLUS du pipeline existant (run_pipeline.py), jamais à sa
      place.

Fonctions réutilisées TELLES QUELLES (aucune modification) :
    run_pipeline.charge_json_ou_vide / normalise_panier
        -- exactement la même liste de matchs que le pipeline principal.
    run_pipeline.recupere_cotes_marches
        -- cotes réelles (matchendirect/Bet365), même source que le
           moteur existant. Pas de cache pour cette fonction (ni ici ni
           dans le pipeline principal -- les cotes évoluent trop vite pour
           qu'un TTL ait un sens) : un vrai appel réseau à chaque run,
           identique au comportement du pipeline principal.
    cache_equipes.recupere_gf_ga_avec_cache
        -- CORRECTIF 07/09/2026 (remarque de Patrick : "les données sont
           censées exister et être stockées") -- la première version de ce
           fichier appelait scraper_details.recupere_gf_ga_avec_repli
           directement, en contournant le cache que precalcul.py branche
           sur run_pipeline.py par monkey-patch (précalcul.py réassigne
           run_pipeline.recupere_gf_ga_avec_repli à une version cachée --
           un import direct depuis scraper_details, comme le faisait cette
           première version, contourne ce monkey-patch et re-scrape à
           chaque run). Corrigé pour appeler cache_equipes.
           recupere_gf_ga_avec_cache directement, sur le MÊME fichier
           cache_equipes.json que le pipeline principal -- un cache hit si
           l'équipe/compétition a déjà été récupérée dans le TTL (4 jours
           sans historique, 20h avec -- voir cache_equipes.py), un vrai
           scraping sinon.
    run_pipeline.MAX_MATCHS_HISTORIQUE / FICHIER_MATCHS_DU_JOUR /
    FICHIER_MATCHS_DEMAIN / FICHIER_PANIER
        -- mêmes constantes, pas de nouvelle valeur.
    scraper_details.recupere_details_match
        -- pas de cache (ni ici ni dans le pipeline principal -- page de
           match légère, jamais mise en cache nulle part dans ce dépôt) :
           un vrai appel réseau à chaque run, identique au pipeline
           principal.

Extraction pays/competition depuis le libellé matchendirect : copie EXACTE
de la logique déjà en place dans run_pipeline.py (split(":")[0]/[1]) --
même règle, pas une nouvelle.
"""

import run_pipeline as rp
import precalcul
from scraper_details import recupere_details_match, recupere_gf_ga_avec_repli
from cache_equipes import recupere_gf_ga_avec_cache
import moteur_v0 as mv0

HISTORIQUE_V0_CHEMIN = "historique_v0.jsonl"


def cotes_vers_plat_v0(cotes_marches: dict) -> dict:
    """Reformate le dict imbriqué cotes_marches (sortie de
    run_pipeline.recupere_cotes_marches, même structure que celle consommée
    par run_pipeline.construit_candidats/cote_marche) vers le dict PLAT
    {libellé exact marché -> cote} attendu par moteur_v0.evalue_match_v0.

    PUR RENOMMAGE -- mêmes clés de sélection, mêmes valeurs de cote que
    celles déjà lues par cote_marche() dans le moteur existant, aucune
    transformation de valeur, aucun filtre. Ne couvre que les marchés que
    moteur_v0.probabilites_marches_v0 sait évaluer (buts, 1X2, double
    chance, BTTS, pair/impair, cage inviolée, handicap) -- Score exact et
    Nombre exact de buts ne sont pas construits par moteur_v0, donc pas
    mappés ici (rien à décider : moteur_v0 ne les évaluera de toute façon
    jamais, ce n'est pas un choix de cet adaptateur)."""

    def lire(cle_marche, cle_cote):
        panel = cotes_marches.get(cle_marche)
        return panel.get(cle_cote) if panel else None

    plat = {
        "1X2 - 1": lire("1x2", "1"),
        "1X2 - X": lire("1x2", "N"),
        "1X2 - 2": lire("1x2", "2"),
        "Double chance - 1X": lire("double_chance", "1N"),
        "Double chance - 12": lire("double_chance", "12"),
        "Double chance - X2": lire("double_chance", "N2"),
        "BTTS - oui": lire("btts", "Oui"),
        "BTTS - non": lire("btts", "Non"),
        "Total buts - pair": lire("pair_impair", "pair"),
        "Total buts - impair": lire("pair_impair", "impair"),
        "Cage inviolée - Domicile": lire("cages_inviolees_domicile", "oui"),
        "Encaisse au moins 1 but - Domicile": lire("cages_inviolees_domicile", "non"),
        "Cage inviolée - Extérieur": lire("cages_inviolees_exterieur", "oui"),
        "Encaisse au moins 1 but - Extérieur": lire("cages_inviolees_exterieur", "non"),
    }

    for ligne in mv0.LIGNES_OU:
        ligne_str = str(ligne)
        plat[f"Plus de {ligne} buts"] = lire(f"over_under_{ligne_str}", "plus")
        plat[f"Moins de {ligne} buts"] = lire(f"over_under_{ligne_str}", "moins")
        plat[f"Plus de {ligne} buts - Domicile"] = lire(f"over_under_domicile_{ligne_str}", "plus")
        plat[f"Moins de {ligne} buts - Domicile"] = lire(f"over_under_domicile_{ligne_str}", "moins")
        plat[f"Plus de {ligne} buts - Extérieur"] = lire(f"over_under_exterieur_{ligne_str}", "plus")
        plat[f"Moins de {ligne} buts - Extérieur"] = lire(f"over_under_exterieur_{ligne_str}", "moins")

    for ligne in mv0.LIGNES_HANDICAP:
        ligne_str = str(ligne)
        plat[f"Handicap {ligne} - Domicile"] = lire(f"handicap_{ligne_str}", "domicile")
        plat[f"Handicap {ligne} - Extérieur"] = lire(f"handicap_{ligne_str}", "exterieur")

    return {k: v for k, v in plat.items() if v is not None}


def _pays_et_competition(competition: str):
    """Copie EXACTE de la logique déjà en place dans run_pipeline.py
    (lignes ~551-556) -- même règle d'extraction, pas une nouvelle."""
    pays_match = competition.split(":")[0].strip() if competition else None
    competition_partie = competition.split(":", 1)[1].strip() if competition and ":" in competition else None
    return pays_match, competition_partie


def evalue_et_journalise(m: dict, chemin_historique: str = HISTORIQUE_V0_CHEMIN):
    """m : entrée de match normalisée (voir run_pipeline.normalise_panier)
    -- mêmes clés que celles consommées par run_pipeline.construit_signaux
    (url_match, domicile, exterieur, competition, cotes_manuelles)."""
    url_match = m.get("url_match")
    nom_domicile = m.get("domicile")
    nom_exterieur = m.get("exterieur")
    competition = m.get("competition")

    match_info = {
        "url_match": url_match, "equipe_domicile": nom_domicile,
        "equipe_exterieur": nom_exterieur, "competition": competition,
        "match_id": m.get("match_id"),
    }

    def echec(motif):
        mv0.enregistre_evaluation_v0(match_info, {"verdict": "NO_BET", "motif": motif}, chemin=chemin_historique)

    if not url_match:
        # Même cas que run_pipeline.py : sans URL matchendirect, ni
        # historique ni classement ne peuvent être récupérés -- non traité,
        # jamais une donnée devinée (identique à la doctrine du pipeline
        # existant pour ce cas).
        echec("url_match_absente")
        return

    try:
        details = recupere_details_match(url_match)
    except Exception as e:
        echec(f"erreur_technique_details_match: {e}")
        return

    url_eq_domicile = details.get("url_equipe_domicile")
    url_eq_exterieur = details.get("url_equipe_exterieur")
    if not url_eq_domicile or not url_eq_exterieur:
        echec("url_equipe_introuvable_sur_page_match")
        return

    try:
        # CORRECTIF (07/09/2026, remarque de Patrick) -- appel direct à
        # recupere_gf_ga_avec_repli() sans passer par le cache existant :
        # la version précédente re-scrapait matchendirect à CHAQUE run,
        # même juste après le pipeline principal, alors que cache_equipes.py
        # avait déjà mémorisé le résultat. Corrigé pour appeler le même
        # wrapper de cache que precalcul.py (recupere_gf_ga_avec_cache),
        # sur le MÊME fichier cache_equipes.json -- un hit si le pipeline
        # principal (ou un run précédent de cet adaptateur) a déjà
        # récupéré cette équipe/compétition dans le TTL, un vrai scraping
        # sinon (jamais bloquant, juste plus lent la première fois).
        stats_domicile = recupere_gf_ga_avec_cache(
            recupere_gf_ga_avec_repli, url_eq_domicile, nom_domicile, competition,
            max_matchs=rp.MAX_MATCHS_HISTORIQUE,
        )
        stats_exterieur = recupere_gf_ga_avec_cache(
            recupere_gf_ga_avec_repli, url_eq_exterieur, nom_exterieur, competition,
            max_matchs=rp.MAX_MATCHS_HISTORIQUE,
        )
    except Exception as e:
        echec(f"erreur_technique_historique: {e}")
        return

    if "raison_non_traite" in stats_domicile:
        echec(f"domicile: {stats_domicile['raison_non_traite']}")
        return
    if "raison_non_traite" in stats_exterieur:
        echec(f"exterieur: {stats_exterieur['raison_non_traite']}")
        return

    gf_home = stats_domicile.get("gf_domicile")
    ga_home = stats_domicile.get("ga_domicile")
    gf_away = stats_exterieur.get("gf_exterieur")
    ga_away = stats_exterieur.get("ga_exterieur")
    if None in (gf_home, ga_home, gf_away, ga_away):
        echec("historique_domicile_ou_exterieur_vide")
        return

    cotes_manuelles = m.get("cotes_manuelles")
    if cotes_manuelles:
        cotes_marches = cotes_manuelles
    else:
        try:
            cotes_marches = rp.recupere_cotes_marches(url_match + "?p=face-a-face")
        except Exception as e:
            echec(f"erreur_technique_cotes: {e}")
            return

    cotes_plates = cotes_vers_plat_v0(cotes_marches)
    pays_match, competition_partie = _pays_et_competition(competition)

    resultat = mv0.evalue_match_v0(
        gf_home, ga_home, gf_away, ga_away,
        nb_matchs_domicile_utilises=stats_domicile["nb_domicile"],
        nb_matchs_exterieur_utilises=stats_exterieur["nb_exterieur"],
        cotes_marches=cotes_plates,
        matchs_domicile_bruts=stats_domicile.get("matchs_domicile_bruts", []),
        matchs_exterieur_bruts=stats_exterieur.get("matchs_exterieur_bruts", []),
        pays=pays_match, competition=competition_partie,
    )
    mv0.enregistre_evaluation_v0(match_info, resultat, chemin=chemin_historique)


def main():
    # CORRECTIF 07/09/2026 (remarque de Patrick : le run GitHub Actions ne
    # faisait tourner que precalcul.py, jamais ce script) -- la version
    # précédente lisait panier.json via run_pipeline.normalise_panier(),
    # qui n'a de sens que pour le canal Supabase (dispatch_pipeline.py) --
    # sur un run planifié normal, panier.json est vide ou périmé, ce script
    # aurait donc évalué presque aucun match. La vraie liste "tous les
    # matchs du jour/demain/J+2/J+3, après tous les filtres (jeunes,
    # réserves, divisions, zones autorisées...)" est construite par
    # precalcul.charge_matchs_fenetre() -- réutilisée ici TELLE QUELLE
    # (même fonction, mêmes filtres déjà tous testés), pas réimplémentée.
    fenetre, *_ = precalcul.charge_matchs_fenetre()

    print(f"[moteur_v0] {len(fenetre)} match(s) à évaluer en observation "
          f"(aucun pari réel, journal : {HISTORIQUE_V0_CHEMIN}).")
    for m in fenetre:
        evalue_et_journalise(m)
    print("[moteur_v0] terminé.")


if __name__ == "__main__":
    main()
