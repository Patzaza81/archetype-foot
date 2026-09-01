"""
test_scraping_betpawa_liste.py -- V20. La V19 a révélé deux vrais bugs
(pas des absences réelles de match) :
1. Le sélecteur de champ de recherche ("input:not(#bookingCode)") était
   trop large -- il comptait aussi les ~267 cases à cocher cachées du
   panneau Leagues, et finissait par cliquer sur un interrupteur "Show
   1UP & 2UP" au lieu du champ de recherche. Corrigé en excluant
   explicitement les checkbox/radio et en ciblant un vrai champ texte.
2. Le nettoyage des noms remplaçait les lettres accentuées (ó, ø, ł)
   par des espaces au lieu de les translittérer -- "Sokół Ostróda"
   devenait "sok ostr da" au lieu de "sokol ostroda". Corrigé avec une
   translittération basique des caractères les plus courants en
   football européen.

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

MATCHS_A_TESTER = [
    ("Bocholt", "Bonn"),
    ("Talaea Gaish", "ZED"),
    ("Sokół Ostróda", "Sokół Kleczew"),
    ("Brøndby", "Spartak"),
    ("West Bromwich", "Charlton"),
]


def translitere(nom):
    """Remplace les lettres accentuées par leur équivalent latin simple
    (ó -> o, ø -> o, ł -> l, etc.) au lieu de les supprimer -- correctif
    du bug observé sur "Sokół Ostróda" -> "sok ostr da"."""
    nom = nom.replace("ø", "o").replace("Ø", "O").replace("ł", "l").replace("Ł", "L")
    nfkd = unicodedata.normalize("NFKD", nom)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalise(nom):
    nom = translitere(nom)
    mots = re.sub(r"[^a-z0-9\s]", " ", nom.lower()).split()
    return [m for m in mots if m not in TOKENS_IGNORES_ETENDUS]


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
    """CORRECTIF V20 : cible uniquement un vrai champ de saisie texte,
    jamais une case à cocher (les ~267 checkbox cachées du panneau
    Leagues faisaient planter la V19)."""
    champs = page.locator("input[type='text'], input[type='search'], input:not([type])")
    for i in range(champs.count()):
        c = champs.nth(i)
        if c.is_visible() and c.get_attribute("id") != "bookingCode":
            return c
    return None


def cherche_avec_variantes(page, nom_domicile, nom_exterieur, etapes):
    for variante in variantes_du_nom(nom_domicile):
        try:
            # CORRECTIF V21 : revenir sur la page de base avant CHAQUE
            # variante, pas juste une fois par match -- la loupe est un
            # bouton bascule (ouvre/ferme), donc la recliquer sans
            # recharger la page la refermait au lieu de la rouvrir.
            page.goto(URL_EVENTS, timeout=30000, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass

            page.locator("[aria-label*='earch' i]").first.click(timeout=5000)
            page.wait_for_timeout(800)

            champ = trouve_champ_recherche(page)
            if champ is None:
                etapes.append(f"[{nom_domicile} - {nom_exterieur}] variante '{variante}' -- "
                              f"champ de recherche introuvable")
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
