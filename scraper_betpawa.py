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
from parse_betpawa_playwright import parse_betpawa_playwright

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
    """Essaie les trois parseurs connus, garde celui qui reconnaît le plus de
    marchés. Trois formats réellement observés à ce jour, tous différents :
    (1) copier-coller téléphone -- français, étiquette/valeur séparées ;
    (2) outil de récupération de Claude -- anglais, étiquette/valeur collées ;
    (3) navigateur automatisé (Playwright) -- anglais, étiquette/valeur
    séparées -- confirmé le 26/08 sur le journal réel d'un run GitHub Actions,
    aucun des deux premiers ne le couvrait."""
    strategies = [
        ("copier-coller (FR, séparé)", parse_betpawa),
        ("récupération Claude (EN, collé)", parse_betpawa_url),
        ("navigateur automatisé (EN, séparé)", parse_betpawa_playwright),
    ]
    meilleur_nom, meilleur_resultat = None, {}
    for nom, fonction in strategies:
        try:
            resultat = fonction(texte, domicile, exterieur)
        except Exception as e:
            print(f"  {nom} a échoué : {e}")
            resultat = {}
        print(f"  {nom} : {len(resultat)} marché(s)")
        if len(resultat) > len(meilleur_resultat):
            meilleur_nom, meilleur_resultat = nom, resultat

    print(f"  Format retenu : {meilleur_nom or 'aucun'} ({len(meilleur_resultat)} marché(s))")
    return meilleur_resultat


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
    index_existant = {item.get("match_id"): idx for idx, item in enumerate(panier) if isinstance(item, dict)}
    nb_ajoutes, nb_mis_a_jour = 0, 0

    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        page = navigateur.new_page()
        for url in urls:
            entree = traite_url(page, url)
            if entree is None:
                continue
            if entree["match_id"] in index_existant:
                # CORRECTIF : remplacer, pas ignorer -- sinon une entrée
                # ratée lors d'un run précédent (0 marché) bloque
                # définitivement la mise à jour, même quand ce run-ci
                # obtient les vraies cotes.
                panier[index_existant[entree["match_id"]]] = entree
                nb_mis_a_jour += 1
                print(f"  Déjà présent dans {FICHIER_PANIER} -- cotes remplacées.")
            else:
                panier.append(entree)
                index_existant[entree["match_id"]] = len(panier) - 1
                nb_ajoutes += 1
        navigateur.close()

    if nb_ajoutes or nb_mis_a_jour:
        ecrit_panier(panier)
        print(f"\n{nb_ajoutes} match(s) ajouté(s), {nb_mis_a_jour} mis à jour dans {FICHIER_PANIER}.")
    else:
        print("\nAucune nouvelle entrée à ajouter.")


if __name__ == "__main__":
    main()
