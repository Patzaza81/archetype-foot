"""
archetype_model/data/validation.py — Fenêtre statistique (ARCHETYPE_FOOT
v3, §4.2), verrouillée :

    N < 5        -> INSUFFISANT (calcul non fiable, pas de sélection)
    5 <= N <= 12 -> UTILISABLE
    N > 12       -> UTILISABLE, tronqué aux 12 PLUS RÉCENTS matchs

Entrée attendue : une liste de matchs dans l'ordre CROISSANT (plus
ancien en premier) -- c'est le format produit par
`data.loader.separe_domicile_exterieur` (voir loader.py pour la
justification de cet ordre, vérifiée sur captures d'écran réelles le
08/09/2026). "12 plus récents" = les 12 DERNIERS éléments de la liste,
JAMAIS les 12 premiers -- inversion volontaire par rapport à
`scraper_details.recupere_gf_ga_avec_repli` (bug distinct de l'ancien
moteur, non corrigé ici, hors périmètre).

"Un match incomplet ou invalide n'augmente pas N" (§4.2) est déjà
garanti EN AMONT par `_extrait_historique_competition`, qui n'ajoute à
l'historique que les lignes où un score a été reconnu par regex -- cette
fonction ne refiltre donc rien, elle classe et tronque seulement.

DÉCISION ANNULÉE (08/09/2026, décision explicite de Patrick) : une
fonction `classifie_fenetre_globale` (sans troncature à 12, pour une
liste "toutes compétitions confondues") a existé brièvement ici.
Annulée en même temps que `data.loader.recupere_historique_toutes_competitions`
-- λ_global utilise maintenant `classifie_fenetre` normalement, sur la
seule compétition du match. Ne pas réintroduire sans en reparler
d'abord avec Patrick.
"""

N_MIN_UTILISABLE = 5
N_MAX_FENETRE = 12

STATUT_INSUFFISANT = "INSUFFISANT"
STATUT_UTILISABLE = "UTILISABLE"


def classifie_fenetre(matchs_ordre_croissant):
    """
    Retourne {"statut": STATUT_INSUFFISANT | STATUT_UTILISABLE,
    "n_brut": int, "matchs_retenus": [...]}.

    - n_brut : nombre de matchs REÇUS en entrée, avant toute troncature.
      C'est CETTE valeur que la règle N<5 / N>12 évalue -- jamais le
      nombre après troncature (qui plafonnerait toujours à 12 et
      rendrait la règle inutile).
    - matchs_retenus : liste effective à utiliser pour calculer GF/GA
      en aval. Vide si INSUFFISANT -- ne jamais lire matchs_retenus
      sans vérifier le statut d'abord.
    """
    n_brut = len(matchs_ordre_croissant)

    if n_brut < N_MIN_UTILISABLE:
        return {"statut": STATUT_INSUFFISANT, "n_brut": n_brut, "matchs_retenus": []}

    if n_brut > N_MAX_FENETRE:
        matchs_retenus = matchs_ordre_croissant[-N_MAX_FENETRE:]
    else:
        matchs_retenus = list(matchs_ordre_croissant)

    return {"statut": STATUT_UTILISABLE, "n_brut": n_brut, "matchs_retenus": matchs_retenus}
