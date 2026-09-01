"""
test_scraping_betpawa_liste.py -- V23. La V22 a validé la méthode sur un
petit échantillon (2/5, échecs tous légitimes -- matchs absents de
Betpawa, pas des bugs). Patrick demande un échantillon plus large avant
de considérer la méthode fiable. Ce test reprend la recette validée
(V20-V22 : bon champ de recherche, bon menu de suggestions, variantes de
nom) sur 30 vrais matchs pris dans precalcul.json du 01/09/2026 (8 de
grands championnats connus + 22 tirés au hasard dans tout le reste, sans
tri favorable) -- un échantillon honnête pour mesurer le vrai taux de
réussite.

Ce script ne fait partie d'AUCUN pipeline -- rien ne l'appelle
automatiquement.
"""
import re
import sys
import unicodedata

from playwright.sync_api import sync_playwright

sys.path.insert(0, ".")
from scraper_betpawa import TOKENS_CLUB_IGNORES

URL_EVENTS = "https://www.betpawa.cm/events?categoryId=2&marketId=1X2"
FICHIER_SORTIE = "diagnostic_liste_betpawa.txt"

TOKENS_IGNORES_ETENDUS = TOKENS_CLUB_IGNORES | {"el", "al"}

# Échantillon réel, pris dans precalcul.json (01/09/2026, 774 matchs) --
# 8 de grands championnats + 22 au hasard dans le reste, mélangés.
MATCHS_A_TESTER = [
    ("Beskid", "Śląsk II"),
    ("PSG", "AS Monaco"),
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
    """Normalisation tolérante pour COMPARER un nom à une suggestion --
    gère les abréviations les plus courantes révélées par la V24
    (Saint/St, United/Utd, Moscow/Moskva, Olympiacos/Olympiakos...),
    en plus des accents déjà traités par translitere()."""
    texte = translitere(texte).lower()
    texte = re.sub(r"[^a-z0-9\s]", " ", texte)
    remplacements = {
        "saint": "st", "united": "utd", "moscow": "moskva",
        "olympiacos": "olympiakos",
    }
    mots = texte.split()
    mots = [remplacements.get(m, m) for m in mots]
    mots = [m for m in mots if m not in TOKENS_IGNORES_ETENDUS]
    return " ".join(mots)


def se_ressemblent(nom_a, nom_b):
    a, b = normalise_pour_comparaison(nom_a), normalise_pour_comparaison(nom_b)
    if not a or not b:
        return False
    return a in b or b in a


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
                # CORRECTIF V24 : la V23 continuait silencieusement ici,
                # donnant des "NON TROUVÉ" sans aucune preuve -- suspect
                # sur des matchs connus comme PSG-Monaco. On capture
                # maintenant le titre de la page et un extrait du texte
                # visible, pour voir si Betpawa a réagi anormalement
                # (page d'erreur, ralentissement, etc.).
                titre = page.title()
                extrait = page.inner_text("body")[:150].replace("\n", " ")
                etapes.append(f"échec [{nom_domicile} - {nom_exterieur}] variante '{variante}' : "
                              f"champ introuvable -- titre page: '{titre}' -- début texte: '{extrait}'")
                page.wait_for_timeout(1500)  # pause avant de réessayer, au cas où c'est un ralentissement
                continue

            champ.click(timeout=3000)
            page.keyboard.type(variante, delay=50)
            page.wait_for_timeout(1300)

            liste_suggestions = page.locator("[data-test-id='search-suggestions']")
            options = liste_suggestions.locator("li, [role='option']")

            textes_vus = []
            bonne_suggestion = None
            for i in range(min(options.count(), 15)):
                try:
                    texte = options.nth(i).inner_text(timeout=800)
                except Exception:
                    continue
                if texte and texte not in textes_vus:
                    textes_vus.append(texte)
                    # CORRECTIF V25 : comparaison tolérante (accents +
                    # abréviations Saint/St, United/Utd, etc.) au lieu
                    # d'une recherche de sous-chaîne stricte -- la V24 a
                    # montré que Kilmarnock/Motherwell/Larissa/Zbrojovka/
                    # Spartak Moscou étaient TOUS trouvés dans les
                    # suggestions mais ratés par une comparaison trop
                    # stricte (St vs Saint, Utd vs United, etc.).
                    if len(texte.split(" - ")) == 2:
                        _, nom_ext_suggestion = texte.split(" - ", 1)
                    else:
                        nom_ext_suggestion = texte
                    if se_ressemblent(nom_exterieur, nom_ext_suggestion):
                        bonne_suggestion = options.nth(i)
                        break

            if bonne_suggestion is not None:
                bonne_suggestion.click(timeout=5000, force=True)
                page.wait_for_timeout(1500)
                url = page.url
                etapes.append(f"TROUVÉ [{nom_domicile} - {nom_exterieur}] (variante '{variante}') -> {url}")
                return url
            else:
                etapes.append(f"pas de correspondance [{nom_domicile} - {nom_exterieur}] variante '{variante}' -- "
                              f"suggestions vues : {textes_vus[:5]}")
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
