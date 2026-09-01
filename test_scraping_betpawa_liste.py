"""
test_scraping_betpawa_liste.py -- V26. Deux changements :
1. Vérification de l'hypothèse PSG : chercher "Paris Saint-Germain" au
   lieu de "PSG", pour confirmer si le sigle est le problème.
2. Remplacement de la comparaison par dictionnaire d'abréviations
   (Saint/St, United/Utd...) -- approche qui ne finira jamais de couvrir
   tous les cas -- par un calcul de RESSEMBLANCE (SequenceMatcher, dans
   la bibliothèque standard Python) : au lieu de chercher une liste
   fermée de cas particuliers, on mesure à quel point deux noms se
   ressemblent en pourcentage, et on accepte au-delà d'un seuil. Ça
   couvre naturellement Saint/St, Utd/United, Moskva/Moscow, et bien
   d'autres variantes qu'on n'a pas encore rencontrées, sans avoir à
   les lister à l'avance.

Ce script ne fait partie d'AUCUN pipeline -- rien ne l'appelle
automatiquement.
"""
import re
import sys
import unicodedata
from difflib import SequenceMatcher

from playwright.sync_api import sync_playwright

sys.path.insert(0, ".")
from scraper_betpawa import TOKENS_CLUB_IGNORES

URL_EVENTS = "https://www.betpawa.cm/events?categoryId=2&marketId=1X2"
FICHIER_SORTIE = "diagnostic_liste_betpawa.txt"

TOKENS_IGNORES_ETENDUS = TOKENS_CLUB_IGNORES | {"el", "al"}
SEUIL_RESSEMBLANCE = 0.55  # à ajuster selon les résultats réels

# Échantillon identique aux tests précédents (comparaison directe
# possible), + un test ciblé pour l'hypothèse PSG.
MATCHS_A_TESTER = [
    ("Bocholt", "Bonn"),
    ("Paris Saint-Germain", "AS Monaco"),  # test de l'hypothèse PSG (nom complet au lieu du sigle)
    ("Puerto Montt", "Curicó Unido"),
    ("Bunyodkor", "Surkhon Termez"),
    ("Hoffenheim", "Leverkusen"),
    ("Progrès SE", "Hammam-Lif"),
    ("Larne", "Glentoran"),
    ("St. Lavallois", "Red Star"),
    ("Mornar", "Bokelj"),
    ("Blacks Power", "Uganda Police"),
    ("Oriental", "R. Montevideo"),
    ("Asswehly", "KVZ"),
    ("Kilmarnock FC", "Saint Mirren FC"),
    ("Lernayin Artsakh", "Urartu II"),
    ("Larissa", "Olympiakos"),
    ("Assyriska", "IFK Stocksund"),
    ("Zénith", "Dynamo Makh."),
    ("Motherwell FC", "Dundee Utd."),
    ("Muangnont", "Hua Hin"),
    ("Zbrojovka", "H. Kralove"),
    ("Treaty Utd", "Wexford"),
    ("Brøndby", "Spartak"),
    ("Pattani", "BG Pathum Utd"),
    ("Spartak Moscou", "Rodina Moskva"),
    ("Resovia", "Arka Gdynia"),
    ("Hienghène", "Lössi"),
    ("Westchester SC", "C. Red Wolves"),
    ("Fort Wayne", "Richmond"),
    ("Bombers", "Harlem Utd"),
    ("Santa Cruz", "Pelotas"),
]


def translitere(nom):
    nom = nom.replace("ø", "o").replace("Ø", "O").replace("ł", "l").replace("Ł", "L")
    nfkd = unicodedata.normalize("NFKD", nom)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalise(nom):
    nom = translitere(nom)
    mots = re.sub(r"[^a-z0-9\s]", " ", nom.lower()).split()
    return [m for m in mots if m not in TOKENS_IGNORES_ETENDUS]


def normalise_pour_comparaison(texte):
    mots = normalise(texte)
    return " ".join(mots)


def ratio_ressemblance(nom_a, nom_b):
    a, b = normalise_pour_comparaison(nom_a), normalise_pour_comparaison(nom_b)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0  # inclusion directe (après nettoyage) = ressemblance maximale
    return SequenceMatcher(None, a, b).ratio()


def variantes_du_nom(nom):
    mots_nettoyes = normalise(nom)
    variantes = [nom]
    nettoye = " ".join(mots_nettoyes)
    if nettoye and nettoye.lower() != nom.lower():
        variantes.append(nettoye)
    if mots_nettoyes:
        mot_distinctif = max(mots_nettoyes, key=len)
        if mot_distinctif not in [v.lower() for v in variantes]:
            variantes.append(mot_distinctif)
    return variantes


def trouve_champ_recherche(page):
    champs = page.locator("input[type='text'], input[type='search'], input:not([type])")
    for i in range(champs.count()):
        c = champs.nth(i)
        if c.is_visible() and c.get_attribute("id") != "bookingCode":
            return c
    return None


def cherche_avec_variantes(page, nom_domicile, nom_exterieur, etapes):
    for variante in variantes_du_nom(nom_domicile):
        try:
            page.goto(URL_EVENTS, timeout=30000, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=6000)
            except Exception:
                pass

            page.locator("[aria-label*='earch' i]").first.click(timeout=5000)
            page.wait_for_timeout(600)

            champ = trouve_champ_recherche(page)
            if champ is None:
                continue

            champ.click(timeout=3000)
            page.keyboard.type(variante, delay=50)
            page.wait_for_timeout(1300)

            liste_suggestions = page.locator("[data-test-id='search-suggestions']")
            options = liste_suggestions.locator("li, [role='option']")

            textes_vus = []
            meilleure_option = None
            meilleur_ratio = 0.0
            for i in range(min(options.count(), 15)):
                try:
                    texte = options.nth(i).inner_text(timeout=800)
                except Exception:
                    continue
                if not texte or texte in textes_vus:
                    continue
                textes_vus.append(texte)
                if " - " in texte:
                    _, nom_ext_suggestion = texte.split(" - ", 1)
                else:
                    nom_ext_suggestion = texte
                r = ratio_ressemblance(nom_exterieur, nom_ext_suggestion)
                if r > meilleur_ratio:
                    meilleur_ratio = r
                    meilleure_option = options.nth(i)

            if meilleure_option is not None and meilleur_ratio >= SEUIL_RESSEMBLANCE:
                meilleure_option.click(timeout=5000, force=True)
                page.wait_for_timeout(1500)
                url = page.url
                etapes.append(f"TROUVÉ [{nom_domicile} - {nom_exterieur}] (variante '{variante}', "
                              f"ressemblance {meilleur_ratio:.2f}) -> {url}")
                return url
            else:
                etapes.append(f"pas de correspondance [{nom_domicile} - {nom_exterieur}] variante '{variante}' "
                              f"(meilleure ressemblance : {meilleur_ratio:.2f}) -- suggestions vues : {textes_vus[:5]}")
        except Exception as e:
            etapes.append(f"échec technique [{nom_domicile} - {nom_exterieur}] variante '{variante}' : "
                          f"{str(e)[:120]}")

    etapes.append(f"NON TROUVÉ [{nom_domicile} - {nom_exterieur}]")
    return None


def main():
    etapes = []
    resultats = {}

    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        appareil = p.devices["iPhone 13"]
        contexte = navigateur.new_context(**appareil)
        page = contexte.new_page()

        for i, (nom_domicile, nom_exterieur) in enumerate(MATCHS_A_TESTER, 1):
            print(f"[{i}/{len(MATCHS_A_TESTER)}] {nom_domicile} - {nom_exterieur}")
            url = cherche_avec_variantes(page, nom_domicile, nom_exterieur, etapes)
            resultats[f"{nom_domicile} - {nom_exterieur}"] = url

        navigateur.close()

    nb_trouves = sum(1 for v in resultats.values() if v)
    etapes.insert(0, f"Résultat global : {nb_trouves}/{len(MATCHS_A_TESTER)} matchs trouvés "
                     f"({round(100 * nb_trouves / len(MATCHS_A_TESTER))}%)")

    with open(FICHIER_SORTIE, "w", encoding="utf-8") as f:
        f.write("--- Étapes ---\n" + "\n".join(etapes))

    print("\n".join(etapes))
    print(f"\nRapport écrit dans {FICHIER_SORTIE} (committé par le workflow).")


if __name__ == "__main__":
    main()
