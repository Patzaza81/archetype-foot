"""
test_scraping_betpawa_liste.py -- V27. Test à grande échelle (100 vrais
matchs de precalcul.json, tirage honnête comme les échantillons
précédents) de la recette validée en V26 : recherche par nom d'équipe +
comparaison par ressemblance (SequenceMatcher) au lieu d'une liste
d'abréviations. Ajout d'une petite table de sigles connus (PSG -> Paris
Saint-Germain) convertis avant la recherche, suite à la confirmation
que Betpawa ne reconnaît pas les sigles à 3 lettres.

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
SEUIL_RESSEMBLANCE = 0.55

SIGLES_CONNUS = {
    "psg": "Paris Saint-Germain",
    "om": "Olympique Marseille",
    "ol": "Olympique Lyonnais",
}

MATCHS_A_TESTER = [
    ("Lernayin Artsakh", "Urartu II"),
    ("Caracas", "Portuguesa"),
    ("Cosmos", "Sarasota"),
    ("Real Sociedad", "Celta Vigo"),
    ("TWL Elektra", "LAC-IC"),
    ("ES Sétif", "ES Ben Aknoun"),
    ("Jedinstvo K", "Trayal"),
    ("Ingolstadt", "A. Aachen"),
    ("Atl. Mineiro", "Cruzeiro MG"),
    ("Bayern Munich II", "Eichstätt"),
    ("Young Star", "Vision"),
    ("PSG", "AS Monaco"),
    ("Wattenscheid", "Rödinghausen"),
    ("Khelang United", "Kamphaeng"),
    ("Tychy", "LKS Lódz"),
    ("Binh Phuoc", "CLB Viettel"),
    ("Ulfarnir", "Alafoss"),
    ("Slovan", "SFK 2000"),
    ("Zrinjski", "Siroki Brije"),
    ("Stockport U21", "Stoke City U21"),
    ("Altach", "Bischofshofen"),
    ("Lusail City", "Al Wakrah"),
    ("Hoffenheim", "Leverkusen"),
    ("Konoplev U19", "Ural U19"),
    ("Național", "Congaz"),
    ("Vitesse", "TOP Oss"),
    ("Turkmenistan U20", "Thaïlande U20"),
    ("Pyunik II", "Sardarapat"),
    ("Cibalia", "Orijent"),
    ("Celtic Glasgow", "Aberdeen"),
    ("Juventus", "Spratzern"),
    ("Sportivo Amel.", "Trinidense Res."),
    ("Baltika", "Krylya Sovetov"),
    ("Krušik", "Stepojevac"),
    ("Waalwijk", "NAC"),
    ("Unia Swarzędz", "Lech Poznan II"),
    ("Rakow C.", "Górnik Zabrze"),
    ("River Plate", "Nacional"),
    ("Ipswich Town", "Liverpool"),
    ("Baglan Dragons", "Afan Lido"),
    ("Paloma", "Fužinar"),
    ("Biar", "Olympique Akbou"),
    ("CFR Cluj", "Farul"),
    ("JEF Utd", "Fagiano"),
    ("M. Hollyhock", "Kashima"),
    ("Macará", "Manta"),
    ("Al Shorta", "Arbil"),
    ("V. Sarsfield", "Boca Juniors"),
    ("Preston U21", "Wolves U21"),
    ("Hallescher", "Tasmania Berlin"),
    ("Lopburi City", "Kasem Bundit"),
    ("Managua", "Diriangén"),
    ("Winterthur", "Xamax"),
    ("Choloma", "Olancho"),
    ("Slovenj Gradec", "Maribor"),
    ("Ovoshtnik", "Rozova dolina"),
    ("Santo Domingo", "Cumbayá"),
    ("Iskra", "Țarigrad"),
    ("Spartaan'20", "UDI"),
    ("US Boulogne", "Dijon FCO"),
    ("Gainare Tottori", "Omiya"),
    ("Genoa", "Côme"),
    ("JS Kabylie", "Rouisset"),
    ("Cardiff MU", "Cambrian"),
    ("Queens Park R.", "Cardiff"),
    ("Kheybar", "Foolad"),
    ("Toulouse", "Lille"),
    ("Vejle-Kolding", "Hjørring"),
    ("Hanovre", "Karlsruher"),
    ("Nasaf", "Neftchi"),
    ("Altrincham", "Eastleigh"),
    ("SOSA", "Central Coast"),
    ("Petrovac", "Sutjeska"),
    ("America Cali", "Alianza Valledupar"),
    ("EIF II", "LePa"),
    ("Politehnica T.", "FC Rapid Bucarest"),
    ("Pragersko", "Grajena"),
    ("Nacional", "Libertad"),
    ("Estudiantes M.", "UCV"),
    ("Bizertin", "Olympique Béja"),
    ("Inde U20", "Ouzbékistan U20"),
    ("Lyon", "AJ Auxerre"),
    ("Vinotinto", "San Antonio"),
    ("Kriens", "Lausanne-Ouchy"),
    ("Espérance ST", "Marsa"),
    ("Tafic FC", "Gaborone"),
    ("Kapfenberg", "Hertha Wels"),
    ("Yala City", "Jalor City"),
    ("Atlas", "Guadalajara"),
    ("Hifk", "HPS"),
    ("Sivasspor", "Mardin 1969"),
    ("Burnley", "Middlesbrough"),
    ("15 de Agosto", "Fomboni"),
    ("Tanta", "Masar"),
    ("Coquimbo", "U. Concepción"),
    ("Flora T.", "Tammeka"),
    ("Bohemians P.", "Jablonec"),
    ("Pelikan", "Swit Nowy Dwór"),
    ("Vålerenga", "Radomlje"),
    ("Real Native", "Midlands Wand."),
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
    return " ".join(normalise(texte))


def ratio_ressemblance(nom_a, nom_b):
    a, b = normalise_pour_comparaison(nom_a), normalise_pour_comparaison(nom_b)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def developpe_sigle(nom):
    """Convertit un sigle connu (PSG, OM...) vers le nom complet du club
    -- Betpawa ne reconnaît pas les sigles à 3 lettres (confirmé sur
    PSG en V26)."""
    cle = nom.strip().lower()
    return SIGLES_CONNUS.get(cle, nom)


def variantes_du_nom(nom):
    nom = developpe_sigle(nom)
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
            page.wait_for_timeout(500)

            champ = trouve_champ_recherche(page)
            if champ is None:
                continue

            champ.click(timeout=3000)
            page.keyboard.type(variante, delay=40)
            page.wait_for_timeout(1200)

            liste_suggestions = page.locator("[data-test-id='search-suggestions']")
            options = liste_suggestions.locator("li, [role='option']")

            textes_vus = []
            meilleure_option = None
            meilleur_ratio = 0.0
            for i in range(min(options.count(), 15)):
                try:
                    texte = options.nth(i).inner_text(timeout=700)
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
                page.wait_for_timeout(1200)
                url = page.url
                etapes.append(f"TROUVÉ [{nom_domicile} - {nom_exterieur}] (variante '{variante}', "
                              f"ressemblance {meilleur_ratio:.2f}) -> {url}")
                return url
            else:
                etapes.append(f"pas de correspondance [{nom_domicile} - {nom_exterieur}] variante '{variante}' "
                              f"(meilleure ressemblance : {meilleur_ratio:.2f})")
        except Exception as e:
            etapes.append(f"échec technique [{nom_domicile} - {nom_exterieur}] variante '{variante}' : "
                          f"{str(e)[:100]}")

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
