"""
test_scraping_betpawa_liste.py -- V30. Procédure à trois tamis, demandée
par Patrick après la découverte d'un faux positif (Tanta-Masar confondu
avec Macará-Manta) :

TAMIS 1 -- correspondance forte et unique (domicile ET extérieur, score
           >= 0.80 chacun) : accepté automatiquement.
TAMIS 2 -- si ambigu (0 candidat en tamis 1, mais 1+ candidats au-dessus
           d'un seuil minimal) : on ouvre CHAQUE candidat restant, on lit
           sa vraie date affichée sur Betpawa, et on la compare à la
           date déjà connue depuis matchendirect. Un seul candidat à la
           bonne date -> confirmé par la date, pas par le nom.
TAMIS 3 -- si toujours ambigu après la date (plusieurs à la même date,
           ou aucun) : laissé de côté, jamais de choix au hasard.

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
SEUIL_HAUTE_CONFIANCE = 0.80
SEUIL_CANDIDAT = 0.50

SIGLES_CONNUS = {
    "psg": "Paris Saint-Germain",
    "om": "Olympique Marseille",
    "ol": "Olympique Lyonnais",
}

# Échantillon identique aux tests précédents (100 matchs), avec en plus
# la date connue depuis matchendirect (format AAAA-MM-JJ), nécessaire
# pour le tamis 2.
MATCHS_A_TESTER = [
    ("Lernayin Artsakh", "Urartu II", "2026-09-02"),
    ("Caracas", "Portuguesa", "2026-09-02"),
    ("Cosmos", "Sarasota", "2026-09-02"),
    ("Real Sociedad", "Celta Vigo", "2026-09-03"),
    ("TWL Elektra", "LAC-IC", "2026-09-04"),
    ("ES Sétif", "ES Ben Aknoun", "2026-09-03"),
    ("Jedinstvo K", "Trayal", "2026-09-02"),
    ("Ingolstadt", "A. Aachen", "2026-09-04"),
    ("Atl. Mineiro", "Cruzeiro MG", "2026-09-02"),
    ("Bayern Munich II", "Eichstätt", "2026-09-04"),
    ("Young Star", "Vision", "2026-09-04"),
    ("PSG", "AS Monaco", "2026-09-04"),
    ("Wattenscheid", "Rödinghausen", "2026-09-02"),
    ("Khelang United", "Kamphaeng", "2026-09-04"),
    ("Tychy", "LKS Lódz", "2026-09-03"),
    ("Binh Phuoc", "CLB Viettel", "2026-09-04"),
    ("Ulfarnir", "Alafoss", "2026-09-03"),
    ("Slovan", "SFK 2000", "2026-09-02"),
    ("Zrinjski", "Siroki Brije", "2026-09-04"),
    ("Stockport U21", "Stoke City U21", "2026-09-04"),
    ("Altach", "Bischofshofen", "2026-09-04"),
    ("Lusail City", "Al Wakrah", "2026-09-04"),
    ("Hoffenheim", "Leverkusen", "2026-09-04"),
    ("Konoplev U19", "Ural U19", "2026-09-04"),
    ("Național", "Congaz", "2026-09-02"),
    ("Vitesse", "TOP Oss", "2026-09-04"),
    ("Turkmenistan U20", "Thaïlande U20", "2026-09-03"),
    ("Pyunik II", "Sardarapat", "2026-09-02"),
    ("Cibalia", "Orijent", "2026-09-02"),
    ("Celtic Glasgow", "Aberdeen", "2026-09-02"),
    ("Juventus", "Spratzern", "2026-09-02"),
    ("Sportivo Amel.", "Trinidense Res.", "2026-09-02"),
    ("Baltika", "Krylya Sovetov", "2026-09-02"),
    ("Krušik", "Stepojevac", "2026-09-02"),
    ("Waalwijk", "NAC", "2026-09-04"),
    ("Unia Swarzędz", "Lech Poznan II", "2026-09-04"),
    ("Rakow C.", "Górnik Zabrze", "2026-09-03"),
    ("River Plate", "Nacional", "2026-09-03"),
    ("Ipswich Town", "Liverpool", "2026-09-04"),
    ("Baglan Dragons", "Afan Lido", "2026-09-04"),
    ("Paloma", "Fužinar", "2026-09-02"),
    ("Biar", "Olympique Akbou", "2026-09-03"),
    ("CFR Cluj", "Farul", "2026-09-04"),
    ("JEF Utd", "Fagiano", "2026-09-02"),
    ("M. Hollyhock", "Kashima", "2026-09-02"),
    ("Macará", "Manta", "2026-09-02"),
    ("Al Shorta", "Arbil", "2026-09-04"),
    ("V. Sarsfield", "Boca Juniors", "2026-09-02"),
    ("Preston U21", "Wolves U21", "2026-09-02"),
    ("Hallescher", "Tasmania Berlin", "2026-09-02"),
    ("Lopburi City", "Kasem Bundit", "2026-09-04"),
    ("Managua", "Diriangén", "2026-09-03"),
    ("Winterthur", "Xamax", "2026-09-04"),
    ("Choloma", "Olancho", "2026-09-04"),
    ("Slovenj Gradec", "Maribor", "2026-09-02"),
    ("Ovoshtnik", "Rozova dolina", "2026-09-02"),
    ("Santo Domingo", "Cumbayá", "2026-09-03"),
    ("Iskra", "Țarigrad", "2026-09-02"),
    ("Spartaan'20", "UDI", "2026-09-02"),
    ("US Boulogne", "Dijon FCO", "2026-09-04"),
    ("Gainare Tottori", "Omiya", "2026-09-02"),
    ("Genoa", "Côme", "2026-09-04"),
    ("JS Kabylie", "Rouisset", "2026-09-04"),
    ("Cardiff MU", "Cambrian", "2026-09-04"),
    ("Queens Park R.", "Cardiff", "2026-09-02"),
    ("Kheybar", "Foolad", "2026-09-02"),
    ("Toulouse", "Lille", "2026-09-03"),
    ("Vejle-Kolding", "Hjørring", "2026-09-04"),
    ("Hanovre", "Karlsruher", "2026-09-04"),
    ("Nasaf", "Neftchi", "2026-09-04"),
    ("Altrincham", "Eastleigh", "2026-09-04"),
    ("SOSA", "Central Coast", "2026-09-02"),
    ("Petrovac", "Sutjeska", "2026-09-04"),
    ("America Cali", "Alianza Valledupar", "2026-09-03"),
    ("EIF II", "LePa", "2026-09-03"),
    ("Politehnica T.", "FC Rapid Bucarest", "2026-09-03"),
    ("Pragersko", "Grajena", "2026-09-02"),
    ("Nacional", "Libertad", "2026-09-02"),
    ("Estudiantes M.", "UCV", "2026-09-03"),
    ("Bizertin", "Olympique Béja", "2026-09-03"),
    ("Inde U20", "Ouzbékistan U20", "2026-09-03"),
    ("Lyon", "AJ Auxerre", "2026-09-04"),
    ("Vinotinto", "San Antonio", "2026-09-03"),
    ("Kriens", "Lausanne-Ouchy", "2026-09-04"),
    ("Espérance ST", "Marsa", "2026-09-03"),
    ("Tafic FC", "Gaborone", "2026-09-02"),
    ("Kapfenberg", "Hertha Wels", "2026-09-04"),
    ("Yala City", "Jalor City", "2026-09-04"),
    ("Atlas", "Guadalajara", "2026-09-04"),
    ("Hifk", "HPS", "2026-09-03"),
    ("Sivasspor", "Mardin 1969", "2026-09-02"),
    ("Burnley", "Middlesbrough", "2026-09-02"),
    ("15 de Agosto", "Fomboni", "2026-09-03"),
    ("Tanta", "Masar", "2026-09-04"),
    ("Coquimbo", "U. Concepción", "2026-09-02"),
    ("Flora T.", "Tammeka", "2026-09-02"),
    ("Bohemians P.", "Jablonec", "2026-09-02"),
    ("Pelikan", "Swit Nowy Dwór", "2026-09-04"),
    ("Vålerenga", "Radomlje", "2026-09-02"),
    ("Real Native", "Midlands Wand.", "2026-09-04"),
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


def date_ddmm_attendue(date_iso):
    """Convertit 'AAAA-MM-JJ' (matchendirect) en 'JJ/MM' (format affiché
    sur Betpawa, ex. '04/09')."""
    try:
        annee, mois, jour = date_iso.split("-")
        return f"{jour}/{mois}"
    except Exception:
        return None


def ouvre_recherche_et_tape(page, variante):
    """Recette de base validée (V20-V22) : ouvrir la recherche, taper un
    texte, retourne la liste des options de suggestion visibles."""
    page.goto(URL_EVENTS, timeout=30000, wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=6000)
    except Exception:
        pass
    page.locator("[aria-label*='earch' i]").first.click(timeout=5000)
    page.wait_for_timeout(500)
    champ = trouve_champ_recherche(page)
    if champ is None:
        return None
    champ.click(timeout=3000)
    page.keyboard.type(variante, delay=40)
    page.wait_for_timeout(1200)
    liste_suggestions = page.locator("[data-test-id='search-suggestions']")
    return liste_suggestions.locator("li, [role='option']")


def collecte_candidats(page, variante, nom_domicile, nom_exterieur):
    """TAMIS 1 (implicite ici) : calcule le score de chaque suggestion
    visible, retourne la liste triée (score, texte) -- ne clique sur
    rien encore."""
    options = ouvre_recherche_et_tape(page, variante)
    if options is None:
        return []
    candidats = []
    textes_vus = []
    for i in range(min(options.count(), 15)):
        try:
            texte = options.nth(i).inner_text(timeout=700)
        except Exception:
            continue
        if not texte or texte in textes_vus or " - " not in texte:
            continue
        textes_vus.append(texte)
        nom_dom_suggestion, nom_ext_suggestion = texte.split(" - ", 1)
        r_dom = ratio_ressemblance(nom_domicile, nom_dom_suggestion)
        r_ext = ratio_ressemblance(nom_exterieur, nom_ext_suggestion)
        score = min(r_dom, r_ext)
        if score >= SEUIL_CANDIDAT:
            candidats.append((score, texte))
    candidats.sort(key=lambda c: c[0], reverse=True)
    return candidats


def verifie_date_candidat(page, variante, texte_candidat, date_attendue_ddmm):
    """TAMIS 2 : rouvre la recherche, clique précisément sur le
    candidat désigné (par son texte), lit sa vraie date sur la page du
    match, compare à la date attendue."""
    options = ouvre_recherche_et_tape(page, variante)
    if options is None:
        return None, None
    for i in range(min(options.count(), 15)):
        try:
            texte = options.nth(i).inner_text(timeout=700)
        except Exception:
            continue
        if texte == texte_candidat:
            options.nth(i).click(timeout=5000, force=True)
            page.wait_for_timeout(1200)
            url = page.url
            texte_page = page.inner_text("body")[:300]
            m = re.search(r"\b(\d{2}/\d{2})\b", texte_page)
            date_trouvee = m.group(1) if m else None
            return url, date_trouvee
    return None, None


def traite_un_match(page, nom_domicile, nom_exterieur, date_iso, etapes):
    date_attendue = date_ddmm_attendue(date_iso)

    for variante in variantes_du_nom(nom_domicile):
        candidats = collecte_candidats(page, variante, nom_domicile, nom_exterieur)
        if not candidats:
            continue

        candidats_confiants = [c for c in candidats if c[0] >= SEUIL_HAUTE_CONFIANCE]

        # TAMIS 1
        if len(candidats_confiants) == 1:
            score, texte = candidats_confiants[0]
            url, _ = verifie_date_candidat(page, variante, texte, date_attendue)
            if url:
                etapes.append(f"TROUVÉ (tamis 1) [{nom_domicile} - {nom_exterieur}] "
                              f"score {score:.2f} -> {url}")
                return url
            continue

        # TAMIS 2 : ambigu -- vérifier la date de chaque candidat restant
        if candidats and date_attendue:
            candidats_a_verifier = candidats_confiants if candidats_confiants else candidats[:4]
            candidats_a_bonne_date = []
            for score, texte in candidats_a_verifier:
                url, date_trouvee = verifie_date_candidat(page, variante, texte, date_attendue)
                if url and date_trouvee == date_attendue:
                    candidats_a_bonne_date.append((score, texte, url))

            if len(candidats_a_bonne_date) == 1:
                score, texte, url = candidats_a_bonne_date[0]
                etapes.append(f"TROUVÉ (tamis 2, date confirmée {date_attendue}) "
                              f"[{nom_domicile} - {nom_exterieur}] -> {url}")
                return url
            elif len(candidats_a_bonne_date) > 1:
                etapes.append(f"AMBIGU (tamis 3, {len(candidats_a_bonne_date)} candidats à la même date "
                              f"{date_attendue}) [{nom_domicile} - {nom_exterieur}] : "
                              f"{[t for _, t, _ in candidats_a_bonne_date]}")
                return "AMBIGU"

        if candidats:
            etapes.append(f"AMBIGU (tamis 3, aucune date ne correspond) "
                          f"[{nom_domicile} - {nom_exterieur}] variante '{variante}' -- "
                          f"candidats vus : {[t for _, t in candidats[:4]]}")
            return "AMBIGU"

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

        for i, (nom_domicile, nom_exterieur, date_iso) in enumerate(MATCHS_A_TESTER, 1):
            print(f"[{i}/{len(MATCHS_A_TESTER)}] {nom_domicile} - {nom_exterieur}")
            url = traite_un_match(page, nom_domicile, nom_exterieur, date_iso, etapes)
            resultats[f"{nom_domicile} - {nom_exterieur}"] = url

        navigateur.close()

    nb_trouves = sum(1 for v in resultats.values() if v and v != "AMBIGU")
    nb_ambigus = sum(1 for v in resultats.values() if v == "AMBIGU")
    nb_non_trouves = len(resultats) - nb_trouves - nb_ambigus

    # Vérification finale : aucune URL ne doit apparaître deux fois
    # (la preuve qu'il n'y a plus de faux positif comme Tanta/Macará).
    from collections import Counter
    urls_utilisees = Counter(v for v in resultats.values() if v and v != "AMBIGU")
    doublons = {u: c for u, c in urls_utilisees.items() if c > 1}

    etapes.insert(0, f"Résultat global : {nb_trouves} trouvés / {nb_ambigus} ambigus / "
                     f"{nb_non_trouves} non trouvés -- sur {len(MATCHS_A_TESTER)} matchs. "
                     f"Doublons d'URL détectés : {doublons if doublons else 'AUCUN'}")

    with open(FICHIER_SORTIE, "w", encoding="utf-8") as f:
        f.write("--- Étapes ---\n" + "\n".join(etapes))

    print("\n".join(etapes))
    print(f"\nRapport écrit dans {FICHIER_SORTIE} (committé par le workflow).")


if __name__ == "__main__":
    main()
