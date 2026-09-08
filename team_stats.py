"""
archetype_model/statistics/team_stats.py — Statistiques descriptives
d'équipe (v3 §5) : production offensive, production défensive,
résultats.

AGNOSTIQUE DE LA SOURCE : ces fonctions prennent une liste de matchs
{"domicile": bool, "buts_marques": int, "buts_encaisses": int} (format
produit par data.loader) et ne savent pas si cette liste représente le
domicile, l'extérieur, ou (futur) toutes compétitions confondues pour
le λ global (v3 §6) -- c'est à l'appelant de constituer la bonne liste
et de l'étiqueter. NOTE OUVERTE : `data.loader` ne sait aujourd'hui
récupérer qu'UNE compétition nommée ; la variante "global" (toutes
compétitions confondues) nécessitera une extension de loader.py, pas
de ce module -- non fait ici, hors périmètre de ce chantier.

Toutes les fonctions attendent une liste déjà passée par
`data.validation.classifie_fenetre` (matchs_retenus) -- elles ne
refiltrent ni ne re-tronquent rien, elles décrivent la liste reçue
telle quelle.
"""

from .distributions import moyenne, mediane, variance, ecart_type, minimum, maximum, distribution_paliers


def stats_offensives(matchs):
    """Production offensive (v3 §5) : buts marqués."""
    buts = [m["buts_marques"] for m in matchs]
    return {
        "n": len(buts),
        "moyenne": moyenne(buts),
        "mediane": mediane(buts),
        "min": minimum(buts),
        "max": maximum(buts),
        "variance": variance(buts),
        "ecart_type": ecart_type(buts),
        "distribution": distribution_paliers(buts),
    }


def stats_defensives(matchs):
    """Production défensive (v3 §5) : buts encaissés, clean sheets,
    fréquence d'encaissement (= 1 - fréquence de clean sheet, mais
    calculée directement pour ne jamais dépendre d'un arrondi
    complémentaire)."""
    buts = [m["buts_encaisses"] for m in matchs]
    n = len(buts)
    clean_sheets = sum(1 for b in buts if b == 0)
    return {
        "n": n,
        "moyenne": moyenne(buts),
        "mediane": mediane(buts),
        "min": minimum(buts),
        "max": maximum(buts),
        "variance": variance(buts),
        "ecart_type": ecart_type(buts),
        "distribution": distribution_paliers(buts),
        "clean_sheets": clean_sheets,
        "frequence_clean_sheets": (clean_sheets / n) if n else None,
        "frequence_encaissement": ((n - clean_sheets) / n) if n else None,
    }


def resultats(matchs):
    """Résultats (v3 §5) : victoires/nuls/défaites, déduits de
    buts_marques vs buts_encaisses -- aucune donnée supplémentaire
    requise, le résultat est entièrement contenu dans le score."""
    n = len(matchs)
    victoires = sum(1 for m in matchs if m["buts_marques"] > m["buts_encaisses"])
    defaites = sum(1 for m in matchs if m["buts_marques"] < m["buts_encaisses"])
    nuls = n - victoires - defaites
    return {
        "n": n,
        "victoires": victoires,
        "nuls": nuls,
        "defaites": defaites,
        "frequence_victoires": (victoires / n) if n else None,
        "frequence_nuls": (nuls / n) if n else None,
        "frequence_defaites": (defaites / n) if n else None,
    }
