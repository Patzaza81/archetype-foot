"""
resolution_betpawa.py -- Module de production, extrait tel quel de
test_scraping_betpawa_liste.py V30 (31/08/2026), validé sur un
échantillon de 100 matchs réels : 37 trouvés / 3 ambigus / 60 non
trouvés, ZÉRO faux positif détecté.

RÈGLE STRICTE (demande explicite de Patrick) : la logique des trois
tamis ci-dessous ne doit plus être modifiée sans repasser par un test
complet sur échantillon, exactement comme celle de calculs.py pour le
moteur de pronostics. Toute amélioration future (cache, alias
d'équipes, parallélisation) doit venir EN COMPLÉMENT, dans d'autres
fichiers, jamais en modifiant les fonctions ci-dessous.

TAMIS 1 -- correspondance forte et unique (domicile ET extérieur,
           score >= 0.80 chacun) : accepté automatiquement.
TAMIS 2 -- si ambigu : on ouvre chaque candidat restant, on lit sa
           vraie date affichée sur Betpawa, on la compare à la date
           connue depuis matchendirect.
TAMIS 3 -- si toujours ambigu après la date : jamais de choix au
           hasard, renvoyé comme "AMBIGU".

Fonction d'entrée : resoudre_match(page, nom_domicile, nom_exterieur,
date_iso, etapes) -> URL Betpawa (str), "AMBIGU", ou None.
"""
import re
import unicodedata
from difflib import SequenceMatcher

from scraper_betpawa import TOKENS_CLUB_IGNORES

URL_EVENTS = "https://www.betpawa.cm/events?categoryId=2&marketId=1X2"

TOKENS_IGNORES_ETENDUS = TOKENS_CLUB_IGNORES | {"el", "al"}
SEUIL_HAUTE_CONFIANCE = 0.80
SEUIL_CANDIDAT = 0.50

SIGLES_CONNUS = {
    "psg": "Paris Saint-Germain",
    "om": "Olympique Marseille",
    "ol": "Olympique Lyonnais",
}


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
    try:
        annee, mois, jour = date_iso.split("-")
        return f"{jour}/{mois}"
    except Exception:
        return None


def ouvre_recherche_et_tape(page, variante):
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


def resoudre_match(page, nom_domicile, nom_exterieur, date_iso, etapes):
    """Point d'entrée du module -- inchangé depuis V30 (renommée
    traite_un_match -> resoudre_match pour la production, logique
    identique)."""
    date_attendue = date_ddmm_attendue(date_iso)

    for variante in variantes_du_nom(nom_domicile):
        candidats = collecte_candidats(page, variante, nom_domicile, nom_exterieur)
        if not candidats:
            continue

        candidats_confiants = [c for c in candidats if c[0] >= SEUIL_HAUTE_CONFIANCE]

        if len(candidats_confiants) == 1:
            score, texte = candidats_confiants[0]
            url, _ = verifie_date_candidat(page, variante, texte, date_attendue)
            if url:
                etapes.append(f"TROUVÉ (tamis 1) [{nom_domicile} - {nom_exterieur}] "
                              f"score {score:.2f} -> {url}")
                return url
            continue

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
