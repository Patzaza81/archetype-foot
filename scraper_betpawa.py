"""
scraper_betpawa.py -- récupère automatiquement les pages de match Betpawa
listées dans betpawa_urls.txt (une URL par ligne) et les ajoute à
panier.json, sans intervention manuelle.

Nécessite un navigateur automatisé (Playwright/Chromium) car le contenu
est chargé par JavaScript après le chargement initial -- confirmé par
test_scraping_betpawa.py (26/08) : une requête HTTP classique ne renvoie
que le squelette vide de l'application, aucune cote.

CE SCRIPT N'A JAMAIS ÉTÉ TESTÉ EN CONDITIONS RÉELLES au moment où il est
écrit -- l'environnement d'édition n'a pas accès à betpawa.cm. Le format
exact du texte qu'un vrai navigateur automatisé va extraire de la page est
une inconnue : c'est pour ça que les DEUX parseurs déjà construits et
validés (parse_betpawa.py pour le format "copier-coller", parse_betpawa_url.py
pour le format "concaténé" vu par l'outil de récupération de Claude) sont
essayés, et celui qui reconnaît le plus de marchés est gardé. Le premier
run réel en dira plus -- lire attentivement le journal de ce run avant de
lui faire confiance.
"""
import json
import re
import sys
import unicodedata

from parse_betpawa import parse_betpawa
from parse_betpawa_url import parse_betpawa_url, extrait_meta

FICHIER_URLS = "betpawa_urls.txt"
FICHIER_PANIER = "panier.json"


def slug(s):
    # Normalise "Étoile" -> "etoile", pas "toile" (le "É" ne doit pas
    # disparaître comme si c'était un séparateur).
    s = unicodedata.normalize("NFD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def genere_match_id(domicile, exterieur):
    return f"betpawa_{slug(domicile)}_{slug(exterieur)}"


def lit_urls():
    try:
        with open(FICHIER_URLS, "r", encoding="utf-8") as f:
            return [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]
    except FileNotFoundError:
        return []


def lit_panier():
    try:
        with open(FICHIER_PANIER, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def ecrit_panier(panier):
    with open(FICHIER_PANIER, "w", encoding="utf-8") as f:
        json.dump(panier, f, ensure_ascii=False, indent=2)


def recupere_page(page, url):
    """Charge la page et renvoie (texte_complet, titre). Attend explicitement
    qu'un marché connu apparaisse plutôt qu'un délai fixe -- plus robuste si
    le réseau est lent, échoue proprement sinon (texte quand même renvoyé,
    peut juste être incomplet)."""
    page.goto(url, timeout=30000, wait_until="domcontentloaded")
    try:
        page.wait_for_selector("text=/1X2/i", timeout=15000)
        print("  Attente du marché 1X2 : trouvé.")
    except Exception as e:
        print(f"  Attente du marché 1X2 : JAMAIS TROUVÉ ({e}) -- "
              f"page probablement incomplète (JS non chargé, ou bloqué).")
    texte = page.inner_text("body")
    titre = page.title()
    return texte, titre


def meilleur_parsing(texte, domicile, exterieur):
    """Essaie les deux parseurs connus, garde celui qui reconnaît le plus de
    marchés -- le format réel produit par le navigateur automatisé n'était
    pas connu au moment d'écrire ce script (voir docstring en tête)."""
    try:
        resultat_a = parse_betpawa(texte, domicile, exterieur)
    except Exception as e:
        print(f"  parse_betpawa (format copier-coller) a échoué : {e}")
        resultat_a = {}
    try:
        resultat_b = parse_betpawa_url(texte, domicile, exterieur)
    except Exception as e:
        print(f"  parse_betpawa_url (format concaténé) a échoué : {e}")
        resultat_b = {}

    if len(resultat_a) >= len(resultat_b):
        print(f"  Format retenu : copier-coller ({len(resultat_a)} marchés "
              f"contre {len(resultat_b)})")
        return resultat_a
    print(f"  Format retenu : concaténé ({len(resultat_b)} marchés contre "
          f"{len(resultat_a)})")
    return resultat_b


def traite_url(page, url):
    print(f"\n=== {url} ===")
    try:
        texte, titre = recupere_page(page, url)
    except Exception as e:
        print(f"  ÉCHEC de récupération : {e}")
        return None

    meta = extrait_meta(titre)
    if not meta:
        print(f"  ÉCHEC : impossible d'extraire domicile/extérieur/compétition "
              f"depuis le titre de la page : '{titre}'")
        return None

    print(f"  Match : {meta['domicile']} - {meta['exterieur']} "
          f"({meta['competition']})")

    cotes = meilleur_parsing(texte, meta["domicile"], meta["exterieur"])
    if not cotes:
        print("  AVERTISSEMENT : aucun marché reconnu du tout -- entrée "
              "quand même créée (utile pour voir la raison dans data.json), "
              "mais à vérifier à la main.")
        print(f"  --- Longueur du texte capturé : {len(texte)} caractères ---")
        print(f"  --- Extrait des 1500 premiers caractères capturés ---")
        print(texte[:1500])
        print(f"  --- Fin de l'extrait ---")

    return {
        "domicile": meta["domicile"],
        "exterieur": meta["exterieur"],
        "competition": meta["competition"],
        "url_match": None,
        "match_id": genere_match_id(meta["domicile"], meta["exterieur"]),
        "source": "betpawa",
        "cotes_manuelles": cotes,
    }


def main():
    urls = lit_urls()
    if not urls:
        print(f"{FICHIER_URLS} absent ou vide -- rien à faire, sortie propre.")
        return

    print(f"{len(urls)} URL(s) à traiter depuis {FICHIER_URLS}")

    # Import différé : si Playwright n'est pas installé sur cette machine,
    # on le sait tout de suite avec un message clair plutôt qu'une trace
    # d'erreur cryptique.
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ÉCHEC : Playwright n'est pas installé. Voir l'étape "
              "d'installation dans pipeline.yml (pip install playwright + "
              "playwright install --with-deps chromium).")
        sys.exit(1)

    panier = lit_panier()
    ids_existants = {item.get("match_id") for item in panier if isinstance(item, dict)}
    nouvelles_entrees = []

    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        page = navigateur.new_page()
        for url in urls:
            entree = traite_url(page, url)
            if entree is None:
                continue
            if entree["match_id"] in ids_existants:
                print(f"  Déjà présent dans {FICHIER_PANIER} -- ignoré (pas de doublon).")
                continue
            nouvelles_entrees.append(entree)
            ids_existants.add(entree["match_id"])
        navigateur.close()

    if nouvelles_entrees:
        panier.extend(nouvelles_entrees)
        ecrit_panier(panier)
        print(f"\n{len(nouvelles_entrees)} match(s) Betpawa ajouté(s) à {FICHIER_PANIER}.")
    else:
        print("\nAucune nouvelle entrée à ajouter.")


if __name__ == "__main__":
    main()
