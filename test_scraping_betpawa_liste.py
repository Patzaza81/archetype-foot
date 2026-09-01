"""
test_scraping_betpawa_liste.py -- V31. Test du cache_betpawa.py branché
sur resolution_betpawa.py (le moteur V30, promu module de production,
INCHANGÉ). Règle stricte respectée : seuls les TROUVÉ (tamis 1 ou 2)
sont enregistrés dans le cache -- jamais les AMBIGU ni les NON TROUVÉ.

Ordre de vérification demandé par Patrick :
1. Vider le cache, lancer sur les 100 matchs -- doit reproduire
   exactement 37 trouvés / 3 ambigus / 60 non trouvés (le moteur n'a
   pas changé).
2. Relancer immédiatement une deuxième fois SANS vider le cache -- les
   37 trouvés doivent être retrouvés directement (cache hit), sans
   repasser par Playwright, et le résultat doit être identique (pas de
   AMBIGU/NON TROUVÉ transformé en TROUVÉ artificiellement).
3. Mesurer le temps du 1er run vs le 2e run.

Ce script ne fait partie d'AUCUN pipeline -- rien ne l'appelle
automatiquement.
"""
import os
import time

from playwright.sync_api import sync_playwright

from resolution_betpawa import resoudre_match
from cache_betpawa import cherche_dans_cache, enregistre_correspondance

FICHIER_SORTIE = "diagnostic_liste_betpawa.txt"
FICHIER_CACHE = "cache_betpawa.json"

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


def traite_avec_cache(page, nom_domicile, nom_exterieur, date_iso, etapes):
    """Vérifie le cache AVANT toute recherche Betpawa. Si absent,
    délègue entièrement à resolution_betpawa.resoudre_match() -- logique
    de correspondance INCHANGÉE. N'enregistre dans le cache que les
    vrais TROUVÉ (jamais AMBIGU ni NON TROUVÉ)."""
    hit = cherche_dans_cache(nom_domicile, nom_exterieur, date_iso)
    if hit is not None:
        etapes.append(f"CACHE HIT [{nom_domicile} - {nom_exterieur}] -> {hit['event_id']}")
        return hit["event_id"], True  # True = venu du cache, pas de Playwright utilisé

    resultat = resoudre_match(page, nom_domicile, nom_exterieur, date_iso, etapes)

    if resultat and resultat != "AMBIGU":
        enregistre_correspondance(
            nom_domicile, nom_exterieur, date_iso,
            event_id_url=resultat, tamis="V30",
        )
    return resultat, False


def lance_une_serie(page, etapes, resultats, cache_utilise_compteur):
    for i, (nom_domicile, nom_exterieur, date_iso) in enumerate(MATCHS_A_TESTER, 1):
        print(f"[{i}/{len(MATCHS_A_TESTER)}] {nom_domicile} - {nom_exterieur}")
        url, venu_du_cache = traite_avec_cache(page, nom_domicile, nom_exterieur, date_iso, etapes)
        resultats[f"{nom_domicile} - {nom_exterieur}"] = url
        if venu_du_cache:
            cache_utilise_compteur[0] += 1


def main():
    etapes = []

    # Repart d'un cache vide pour ce test, comme demandé (étape 1).
    if os.path.exists(FICHIER_CACHE):
        os.remove(FICHIER_CACHE)

    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        appareil = p.devices["iPhone 13"]
        contexte = navigateur.new_context(**appareil)
        page = contexte.new_page()

        etapes.append("=== RUN 1 (cache vide) ===")
        resultats_run1 = {}
        compteur_cache_1 = [0]
        debut_1 = time.time()
        lance_une_serie(page, etapes, resultats_run1, compteur_cache_1)
        duree_1 = time.time() - debut_1

        etapes.append(f"\n=== RUN 2 (cache rempli par le run 1) ===")
        resultats_run2 = {}
        compteur_cache_2 = [0]
        debut_2 = time.time()
        lance_une_serie(page, etapes, resultats_run2, compteur_cache_2)
        duree_2 = time.time() - debut_2

        navigateur.close()

    nb_trouves_1 = sum(1 for v in resultats_run1.values() if v and v != "AMBIGU")
    nb_ambigus_1 = sum(1 for v in resultats_run1.values() if v == "AMBIGU")
    nb_trouves_2 = sum(1 for v in resultats_run2.values() if v and v != "AMBIGU")
    nb_ambigus_2 = sum(1 for v in resultats_run2.values() if v == "AMBIGU")

    resultats_identiques = resultats_run1 == resultats_run2

    rapport = [
        f"RUN 1 (cache vide) : {nb_trouves_1} trouvés / {nb_ambigus_1} ambigus, "
        f"{compteur_cache_1[0]} venus du cache (doit être 0), durée : {duree_1:.0f}s",
        f"RUN 2 (cache rempli) : {nb_trouves_2} trouvés / {nb_ambigus_2} ambigus, "
        f"{compteur_cache_2[0]} venus du cache (doit être {nb_trouves_1}), durée : {duree_2:.0f}s",
        f"Résultats run1 == run2 (aucune dérive) : {resultats_identiques}",
        f"Gain de temps run2 vs run1 : {round(100 * (1 - duree_2 / duree_1))}%" if duree_1 else "N/A",
    ]

    with open(FICHIER_SORTIE, "w", encoding="utf-8") as f:
        f.write("--- Étapes ---\n" + "\n".join(rapport) + "\n\n--- Détail ---\n" + "\n".join(etapes))

    print("\n".join(rapport))
    print(f"\nRapport écrit dans {FICHIER_SORTIE} (committé par le workflow).")


if __name__ == "__main__":
    main()
