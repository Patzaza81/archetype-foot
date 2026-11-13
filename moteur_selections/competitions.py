"""Quelles compétitions de Matchendirect sont des matchs OFFICIELS de sélections
nationales A (hommes), tous tournois confondus.

Le PDF du jour n'est pas un standard : les tournois changent chaque jour. Pas de
liste de libellés figée. Règle structurelle (libellé "Zone : Compétition") :
  - la zone est supranationale (Europe, Afrique, Asie, Océanie, Amérique..., Monde),
    donc pas un championnat de pays ;
  - pas d'amical, pas de jeunes (U15..U23), pas de féminin ;
  - pas de compétition de clubs (Ligue des Champions, Libertadores, ...).
Reste : Coupe du monde, qualifications, Euro, CAN, Copa América, Gold Cup,
Coupe d'Asie, Ligues des Nations, etc.
"""
ZONES = ("europe", "afrique", "asie", "océanie", "oceanie", "monde", "amérique", "amerique")
CLUBS = ("ligue des champions", "ligue europa", "ligue conférence", "ligue conference",
         "libertadores", "sudamericana", "sud-américaine", "coupe de la confédération",
         "coupe de la confederation", "coupe de la caf", "super coupe", "supercoupe",
         "coupe du monde des clubs", "intercontinentale", "champions cup", "coupe arabe des clubs")
EXCLUS = ("amic", "féminin", "feminin", "femme", "women")
JEUNES = ("u15", "u16", "u17", "u18", "u19", "u20", "u21", "u22", "u23")


def est_selection_officielle(competition):
    c = " ".join((competition or "").replace("\n", " ").split())
    if ":" not in c:
        return False
    zone, nom = (p.strip().lower() for p in c.split(":", 1))
    if not zone.startswith(ZONES):
        return False
    mots = nom.replace("-", " ").split()
    if any(j in mots for j in JEUNES):
        return False
    if any(e in nom for e in EXCLUS) or any(k in nom for k in CLUBS):
        return False
    return True
