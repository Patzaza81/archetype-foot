"""
test_scraping_betpawa.py -- teste UNE question précise : une requête HTTP
classique (bibliothèque `requests`, comme le fait déjà `scraper.py` pour
matchendirect) obtient-elle le même contenu que l'outil de récupération de
Claude sur une page de match Betpawa ?

Ce script ne fait PARTIE d'aucun pipeline -- il n'est appelé par rien
d'automatique. Il sert uniquement à répondre à cette question avant de
décider si ça vaut la peine de construire une automatisation complète.
Résultat à lire dans le journal du run GitHub Actions (onglet Actions).
"""
import sys

import requests

URL_TEST = "https://www.betpawa.cm/event/36982608?filter=all"

# Indices attendus si le contenu réel de la page est bien récupéré (mêmes
# équipes et marché que dans le test fait via le chat, 26/08).
INDICES_SUCCES = ["AC Horsens", "Viborg FF", "1X2", "Full Time"]

# Indices d'un blocage anti-robot classique (Cloudflare, captcha, page
# d'attente) -- s'ils apparaissent, la requête a été détectée et bloquée.
INDICES_BLOCAGE = ["Just a moment", "cf-chl", "captcha", "Attention Required",
                   "Access denied", "cf-browser-verification"]

EN_TETES = {
    # User-Agent d'un navigateur classique -- sans ça, beaucoup de sites
    # rejettent la requête immédiatement (identifiée comme un script).
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


def main():
    print(f"Requête vers : {URL_TEST}")
    try:
        reponse = requests.get(URL_TEST, headers=EN_TETES, timeout=20)
    except requests.exceptions.RequestException as e:
        print(f"ÉCHEC -- la requête elle-même a échoué : {e}")
        sys.exit(1)

    print(f"Code HTTP : {reponse.status_code}")
    print(f"Taille du contenu reçu : {len(reponse.text)} caractères")
    print()

    blocages_trouves = [b for b in INDICES_BLOCAGE if b.lower() in reponse.text.lower()]
    if blocages_trouves:
        print(f"BLOCAGE DÉTECTÉ -- indices trouvés : {blocages_trouves}")
        print("La requête a probablement été identifiée comme un robot et bloquée.")

    succes_trouves = [s for s in INDICES_SUCCES if s.lower() in reponse.text.lower()]
    print(f"Indices de contenu réel trouvés : {succes_trouves} (sur {len(INDICES_SUCCES)} attendus)")
    print()

    print("--- Extrait des 2000 premiers caractères reçus ---")
    print(reponse.text[:2000])
    print("--- Fin de l'extrait ---")
    print()

    if len(succes_trouves) == len(INDICES_SUCCES):
        print("RÉSULTAT : SUCCÈS -- le contenu réel est bien accessible par requête HTTP classique.")
    elif blocages_trouves:
        print("RÉSULTAT : ÉCHEC -- requête bloquée, ne pas construire l'automatisation sur cette base.")
    else:
        print("RÉSULTAT : INCERTAIN -- ni succès net ni blocage net, lire l'extrait ci-dessus à la main.")


if __name__ == "__main__":
    main()
