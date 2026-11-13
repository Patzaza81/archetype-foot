"""Quelles compétitions de Matchendirect sont des matchs OFFICIELS de sélections
nationales A (hommes), tous tournois confondus.

Règle (consigne de Patrick 13/11) : tout tournoi officiel de sélections, pas
seulement les qualifications Coupe du monde. Amicaux exclus (non officiels),
jeunes (U17..U23), féminines et compétitions de clubs exclus.

Libellés au format Matchendirect : "Zone : Nom de compétition".
VÉRIFIÉ sur le PDF du 15/11/2026 : seuls ces deux tournois de sélections
officiels y figurent. Les autres (Coupe du monde, qualifications, Euro, CAN,
Copa América, Gold Cup, Coupe d'Asie...) n'ont PAS encore été vus : leurs
libellés exacts restent à ajouter dès qu'ils apparaissent (liste blanche,
jamais un mot-clé générique).
"""
LIBELLES_OFFICIELS = (
    "Ligue des Nations de l'UEFA",
    "Ligue des Nations de la CONCACAF",
)
MARQUEURS_EXCLUS = ("u15", "u16", "u17", "u18", "u19", "u20", "u21", "u23",
                    "féminin", "feminin", "femme", "amical")


def est_selection_officielle(competition):
    c = " ".join((competition or "").replace("\n", " ").split())
    bas = c.lower()
    if any(m in bas.replace("(", " ").split() or m in bas for m in MARQUEURS_EXCLUS):
        return False
    return any(l in c for l in LIBELLES_OFFICIELS)
