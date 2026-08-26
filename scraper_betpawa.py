"""
scraper_betpawa.py -- récupère automatiquement les cotes des pages de match
Betpawa listées dans betpawa_urls.txt et les ajoute à panier.json, sans
intervention manuelle.

SYSTÈME HYBRIDE (décision du 26/08) : Betpawa fournit les cotes et
marchés, matchendirect reste l'UNIQUE source de forme/classement/H2H --
volontairement, pas par manque d'essai (une tentative d'extraire ces
stats depuis Betpawa via navigateur automatisé a échoué, données absentes
du texte capturé même après clic sur les onglets). Chaque ligne de
betpawa_urls.txt peut donc contenir une deuxième URL matchendirect
optionnelle (séparateur '|') pour que le match ait un vrai calcul
GO/NO_GO ; sans elle, le match reste "non traité" (cotes affichées seules).

Nécessite un navigateur automatisé (Playwright/Chromium) car le contenu
des cotes est chargé par JavaScript après le chargement initial (confirmé
par test_scraping_betpawa.py, 26/08 : une requête HTTP classique ne
renvoie que le squelette vide de l'application).
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
FICHIER_MATCHS_DU_JOUR = "matchs_du_jour.json"
FICHIER_MATCHS_DEMAIN = "matchs_demain.json"
FICHIER_MATCHS_SEMAINE = "matchs_semaine.json"

# Tokens de type de club sans valeur distinctive pour l'appariement de noms
# -- "AC Horsens" et "Horsens" doivent se reconnaître comme la même équipe.
# CORRECTIF : liste volontairement réduite au strict minimum -- "United",
# "City", "Real", "Athletic", "Town", "Sporting" etc. sont RETIRÉS de cette
# liste après un faux positif dangereux confirmé ("Manchester City" et
# "Manchester United" se faisaient reconnaître comme la même équipe, ces
# mots étant précisément ce qui distingue deux clubs rivaux d'une même
# ville). Mieux vaut rater un appariement légitime (repli sur l'URL
# manuelle) que fusionner deux équipes différentes.
TOKENS_CLUB_IGNORES = {"fc", "ac", "cf", "sc", "afc", "cfc", "club"}


def _normalise_nom_equipe(nom):
    mots = re.sub(r"[^a-z0-9\s]", " ", nom.lower()).split()
    mots_utiles = [m for m in mots if m not in TOKENS_CLUB_IGNORES]
    return " ".join(mots_utiles) or nom.lower()


def _noms_correspondent(nom_a, nom_b):
    a, b = _normalise_nom_equipe(nom_a), _normalise_nom_equipe(nom_b)
    return a and b and (a in b or b in a)


def cherche_url_matchendirect_auto(domicile, exterieur):
    """Cherche le match dans matchs_du_jour.json/matchs_demain.json par nom
    d'équipe (Betpawa et matchendirect n'utilisent pas toujours exactement
    la même orthographe -- "AC Horsens" vs "Horsens"). Retourne l'URL trouvée
    ou None -- ne devine jamais si la correspondance est ambiguë : mieux
    vaut aucune URL automatique qu'une mauvaise (mauvaises stats de forme
    utilisées pour calculer lambda, silencieusement)."""
    candidats = []
    for fichier in (FICHIER_MATCHS_DU_JOUR, FICHIER_MATCHS_DEMAIN, FICHIER_MATCHS_SEMAINE):
        try:
            with open(fichier, "r", encoding="utf-8") as f:
                candidats.extend(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            continue

    correspondances = [
        m for m in candidats
        if m.get("domicile") and m.get("exterieur")
        and _noms_correspondent(domicile, m["domicile"])
        and _noms_correspondent(exterieur, m["exterieur"])
    ]

    if len(correspondances) == 1:
        return correspondances[0].get("url_match")
    if len(correspondances) > 1:
        print(f"  Recherche auto matchendirect : {len(correspondances)} "
              f"correspondances AMBIGUËS pour '{domicile} - {exterieur}' -- "
              f"aucune retenue, pas de devinette.")
    return None


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
    """Une ligne = une URL Betpawa (cotes), avec en option une deuxième URL
    matchendirect séparée par '|' (forme/classement/H2H -- SEULE source
    utilisée pour ça, jamais Betpawa, décision du 26/08 : les deux sources
    sont complémentaires par force, pas redondantes). Format :
        https://www.betpawa.cm/event/XXXX?filter=all
        https://www.betpawa.cm/event/YYYY?filter=all | https://www.matchendirect.fr/live-score/zzz_id.html
    Retourne une liste de (url_betpawa, url_matchendirect_ou_None)."""
    try:
        with open(FICHIER_URLS, "r", encoding="utf-8") as f:
            lignes = [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]
    except FileNotFoundError:
        return []

    resultat = []
    for ligne in lignes:
        if "|" in ligne:
            url_bp, url_md = (p.strip() for p in ligne.split("|", 1))
            resultat.append((url_bp, url_md or None))
        else:
            resultat.append((ligne, None))
    return resultat


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


def traite_url(page, url_betpawa, url_matchendirect):
    print(f"\n=== {url_betpawa} ===")
    if url_matchendirect:
        print(f"  (forme/classement/H2H depuis matchendirect : {url_matchendirect})")
    try:
        texte, titre = recupere_page(page, url_betpawa)
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

    # CORRECTIF (26/08duodecies) : recherche automatique d'abord -- si le
    # match est déjà dans les listes du jour/demain (scraper.py, exécuté
    # juste avant cette étape dans pipeline.yml), l'URL matchendirect est
    # trouvée sans rien demander. Sinon, repli sur l'URL fournie à la main
    # dans betpawa_urls.txt (utile pour un match trop loin dans le temps
    # pour être déjà dans ces listes).
    url_match_auto = cherche_url_matchendirect_auto(meta["domicile"], meta["exterieur"])
    if url_match_auto:
        print(f"  URL matchendirect trouvée automatiquement : {url_match_auto}")
        url_match_finale = url_match_auto
    elif url_matchendirect:
        print(f"  Pas trouvé automatiquement -- URL fournie à la main utilisée.")
        url_match_finale = url_matchendirect
    else:
        print(f"  Pas trouvé automatiquement, aucune URL fournie à la main -- "
              f"match affiché sans calcul (forme/classement/H2H indisponibles).")
        url_match_finale = None

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
        # CORRECTIF (26/08undecies) : url_match = la source matchendirect si
        # fournie -- c'est elle, et UNIQUEMENT elle, qui alimente
        # forme/classement/H2H dans construit_signaux(). Betpawa ne fournit
        # jamais ces données (décision du 26/08 : pas de statistiques
        # Betpawa, matchendirect reste seul pour ça -- les deux sources
        # sont complémentaires, pas redondantes). Sans URL matchendirect,
        # comportement inchangé : "non traité", cotes affichées seules.
        "url_match": url_match_finale,
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
        for url_betpawa, url_matchendirect in urls:
            entree = traite_url(page, url_betpawa, url_matchendirect)
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
