"""
test_scraping_betpawa_liste.py -- V19. La V18 a confirmé que le vrai
problème n'est pas la méthode de recherche elle-même, mais les
différences d'orthographe entre matchendirect et Betpawa (ex. "Talaea
Gaish" vs "Talaea El Gaish", confirmé manuellement par Patrick). Ce
test essaie PLUSIEURS variantes du nom, de la plus complète à la plus
simplifiée, avant d'abandonner :
1. Le nom tel quel
2. Le nom nettoyé (sans FC/SC/AC/CF, et sans "El"/"Al" -- absents de
   la liste existante dans scraper_betpawa.py, ajoutés ici pour ce test)
3. Le mot le plus distinctif du nom nettoyé (souvent le dernier mot,
   plus rare donc plus susceptible de matcher dans la recherche de
   Betpawa)

Ce script ne fait partie d'AUCUN pipeline -- rien ne l'appelle
automatiquement.
"""
import re
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, ".")
from scraper_betpawa import TOKENS_CLUB_IGNORES

URL_EVENTS = "https://www.betpawa.cm/events?categoryId=2&marketId=1X2"
FICHIER_SORTIE = "diagnostic_liste_betpawa.txt"

# Ajout local (pas dans scraper_betpawa.py) : "el"/"al" absents de la
# liste existante, cause probable de l'échec observé sur Talaea Gaish.
TOKENS_IGNORES_ETENDUS = TOKENS_CLUB_IGNORES | {"el", "al"}

MATCHS_A_TESTER = [
    ("Bocholt", "Bonn"),
    ("Talaea Gaish", "ZED"),
    ("Sokół Ostróda", "Sokół Kleczew"),
    ("Brøndby", "Spartak"),
    ("West Bromwich", "Charlton"),
]


def normalise(nom):
    mots = re.sub(r"[^a-z0-9\s]", " ", nom.lower()).split()
    return [m for m in mots if m not in TOKENS_IGNORES_ETENDUS]


def variantes_du_nom(nom):
    mots_nettoyes = normalise(nom)
    variantes = [nom]  # 1. tel quel
    nettoye = " ".join(mots_nettoyes)
    if nettoye and nettoye.lower() != nom.lower():
        variantes.append(nettoye)  # 2. nettoyé
    if mots_nettoyes:
        mot_distinctif = max(mots_nettoyes, key=len)  # 3. mot le plus long/distinctif
        if mot_distinctif not in [v.lower() for v in variantes]:
            variantes.append(mot_distinctif)
    return variantes


def cherche_avec_variantes(page, nom_domicile, nom_exterieur, etapes):
    for variante in variantes_du_nom(nom_domicile):
        try:
            page.locator("[aria-label*='earch' i]").first.click(timeout=5000)
            page.wait_for_timeout(800)

            champs = page.locator("input:not(#bookingCode)")
            champ = None
            for i in range(champs.count()):
                if champs.nth(i).is_visible():
                    champ = champs.nth(i)
                    break
            if champ is None:
                continue

            champ.click(timeout=3000)
            page.keyboard.type(variante, delay=60)
            page.wait_for_timeout(1500)

            suggestions = page.locator("div, span").filter(has_text=re.compile(re.escape(variante), re.IGNORECASE))
            textes_vus = []
            bonne_suggestion = None
            for i in range(min(suggestions.count(), 15)):
                try:
                    texte = suggestions.nth(i).inner_text(timeout=1000)
                except Exception:
                    continue
                if texte and texte not in textes_vus and len(texte) < 100:
                    textes_vus.append(texte)
                    if nom_exterieur.lower() in texte.lower():
                        bonne_suggestion = suggestions.nth(i)

            if bonne_suggestion is not None:
                bonne_suggestion.click(timeout=5000)
                page.wait_for_timeout(2000)
                url = page.url
                etapes.append(f"[{nom_domicile} - {nom_exterieur}] TROUVÉ avec la variante '{variante}' -> {url}")
                return url
            else:
                etapes.append(f"[{nom_domicile} - {nom_exterieur}] variante '{variante}' -- pas de correspondance "
                              f"(suggestions vues : {textes_vus[:5]})")
        except Exception as e:
            etapes.append(f"[{nom_domicile} - {nom_exterieur}] variante '{variante}' -- échec technique : {e}")

    etapes.append(f"[{nom_domicile} - {nom_exterieur}] ÉCHEC après toutes les variantes")
    return None


def main():
    etapes = []
    resultats = {}

    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        appareil = p.devices["iPhone 13"]
        contexte = navigateur.new_context(**appareil)
        page = contexte.new_page()

        for nom_domicile, nom_exterieur in MATCHS_A_TESTER:
            page.goto(URL_EVENTS, timeout=30000, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            url = cherche_avec_variantes(page, nom_domicile, nom_exterieur, etapes)
            resultats[f"{nom_domicile} - {nom_exterieur}"] = url

        navigateur.close()

    nb_trouves = sum(1 for v in resultats.values() if v)
    etapes.insert(0, f"Résultat global : {nb_trouves}/{len(MATCHS_A_TESTER)} matchs trouvés")

    with open(FICHIER_SORTIE, "w", encoding="utf-8") as f:
        f.write("--- Étapes ---\n" + "\n".join(etapes))

    print("\n".join(etapes))
    print(f"\nRapport écrit dans {FICHIER_SORTIE} (committé par le workflow).")


if __name__ == "__main__":
    main()
