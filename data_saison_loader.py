"""
archetype_model/data/loader.py — Récupération de l'historique brut d'une
équipe pour la SAISON EN COURS UNIQUEMENT (ARCHETYPE_FOOT v3, §4.1).

Invariant non négociable (v3 §4.1) : jamais de repli sur la saison
précédente en cas d'insuffisance. Contrairement à
`scraper_details.recupere_gf_ga_avec_repli` (utilisé par l'ancien
moteur), ce module effectue UN SEUL fetch, sans jamais construire d'URL
`?season=`.

Pourquoi `recupere_gf_ga_avec_repli` n'est PAS réutilisée ici (décision
du 08/09/2026, à ne pas rouvrir sans en parler à Patrick d'abord) :
1. Elle mélange saison actuelle et saison précédente en cas de repli, et
   les matchs fusionnés ne portent plus de tag de saison -- impossible
   de les distinguer après coup. Violerait §4.1 silencieusement.
2. Elle tronque aux N PREMIERS matchs rencontrés sur la page. Or,
   vérifié sur deux captures d'écran réelles le 08/09/2026 (page équipe
   Al Ettifaq / Arabie Saoudite, page équipe Kalmar / Suède Allsvenskan) :
   le tableau d'une compétition sur matchendirect.fr liste les matchs du
   PLUS ANCIEN au PLUS RÉCENT. Prendre les N premiers = prendre les N
   PLUS ANCIENS, l'inverse de ce qu'un signal de forme récente doit
   capturer. C'est un bug réel de l'ancien moteur, non corrigé ici (hors
   périmètre de ce chantier, décision explicite de Patrick).

   ATTENTION -- cette hypothèse d'ordre croissant n'est vérifiée que sur
   2 échantillons, tous deux du même gabarit de page. Si un run réel sur
   `archetype_model` produit un signal de forme qui semble inversé pour
   une compétition donnée, ne pas supposer que c'est un cas isolé à
   ignorer : vérifier `ASSUME_ORDRE_CROISSANT` ci-dessous en priorité.

Ce module importe, en LECTURE SEULE, deux primitives déjà existantes et
déjà testées ailleurs dans le dépôt -- aucune n'est modifiée :
- scraper_details.fetch_html
- scraper_details._extrait_historique_competition
Aucune écriture, aucun cache, aucun état partagé avec l'ancien moteur.

DÉCISION ANNULÉE (08/09/2026, décision explicite de Patrick) : une
version antérieure de ce fichier ajoutait une agrégation "toutes
compétitions confondues" (`recupere_historique_toutes_competitions`)
pour alimenter λ_global (v3 §6). Annulée : λ_global reste calculé sur
la SEULE compétition du match (comme les 3 autres scénarios), pas sur
plusieurs compétitions fusionnées -- voir `main._stats_globales` pour
le calcul actuel. Ne pas réintroduire cette fonction sans en reparler
d'abord avec Patrick.
"""

from bs4 import BeautifulSoup

from scraper_details import fetch_html, _extrait_historique_competition

# Documente l'hypothèse d'ordre exploitée par validation.py (les 12 plus
# récents = les 12 DERNIERS éléments de la liste retournée ici). Change
# ce commentaire, pas la valeur, si l'hypothèse est un jour infirmée --
# la correction doit se faire dans validation.py (slice [-N:] -> [:N]),
# jamais ici.
ASSUME_ORDRE_CROISSANT = True  # plus ancien en premier, confirmé 08/09/2026


def recupere_historique_saison_courante(url_equipe, nom_competition, nom_equipe):
    """
    Récupère l'historique COMPLET (non tronqué) d'une équipe dans une
    compétition donnée, pour la saison en cours uniquement.

    Retourne une liste de dicts {"domicile": bool, "buts_marques": int,
    "buts_encaisses": int}, dans l'ordre de la page (croissant, voir
    ASSUME_ORDRE_CROISSANT). Ne retourne JAMAIS None : si la compétition
    est introuvable sur la page ou si aucun match n'a de score
    exploitable, retourne une liste vide (normalisation du None que
    peut renvoyer `_extrait_historique_competition` en cas d'ancre
    introuvable).

    Un seul fetch réseau. Aucun paramètre `?season=` n'est jamais
    construit ici.
    """
    html = fetch_html(url_equipe)
    soup = BeautifulSoup(html, "html.parser")
    historique = _extrait_historique_competition(soup, nom_competition, nom_equipe)
    return historique if historique else []


def separe_domicile_exterieur(historique):
    """
    Sépare une liste chronologique en deux sous-listes qui PRÉSERVENT
    l'ordre d'origine : matchs à domicile, matchs à l'extérieur. Ne
    trie pas, ne tronque pas -- la fenêtre statistique (§4.2) est du
    ressort de validation.classifie_fenetre, appelée séparément sur
    chacune des deux listes retournées ici.
    """
    matchs_domicile = [m for m in historique if m["domicile"]]
    matchs_exterieur = [m for m in historique if not m["domicile"]]
    return matchs_domicile, matchs_exterieur
