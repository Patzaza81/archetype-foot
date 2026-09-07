"""
scraper_betpawa.py -- bibliothèque de correspondance de noms d'équipes et
de parsing des cotes Betpawa, utilisée par resolution_betpawa_precalcul.py
(moteur automatique actif).

CORRECTIF 06/09/2026 (bug #36/#37) -- ce fichier contenait à l'origine
tout un flux manuel (lit_urls/traite_url/main lisant betpawa_urls.txt,
écrivant panier.json) qui a été le premier mécanisme de récupération des
cotes Betpawa. Ce flux est devenu du code mort le 06/09/2026 quand la
saisie manuelle a été supprimée (panier.html/panier.js, Groupe 1) --
aucun appelant actif ne restait (vérifié par recherche exhaustive dans le
dépôt avant suppression). Supprimé ici avec genere_match_id, slug,
cherche_url_matchendirect_auto (repris par le moteur à 3 tamis de
resolution_betpawa.py, protégé, jamais modifié) et les 5 constantes de
fichiers qui n'étaient utilisées que par ce flux. betpawa_urls.txt
(fichier de données, pas du code) reste sur le disque, orphelin -- à
supprimer à la main si tu n'en as plus besoin.

SYSTÈME HYBRIDE (décision du 26/08) : Betpawa fournit les cotes et
marchés, matchendirect reste l'UNIQUE source de forme/classement/H2H --
volontairement, pas par manque d'essai (une tentative d'extraire ces
stats depuis Betpawa via navigateur automatisé a échoué, données absentes
du texte capturé même après clic sur les onglets).

Nécessite un navigateur automatisé (Playwright/Chromium) car le contenu
des cotes est chargé par JavaScript après le chargement initial (confirmé
par test_scraping_betpawa.py, 26/08 : une requête HTTP classique ne
renvoie que le squelette vide de l'application).
"""
import re

from parse_betpawa import parse_betpawa
from parse_betpawa_url import parse_betpawa_url
from parse_betpawa_playwright import parse_betpawa_playwright

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

# CORRECTIF 05/09/2026 -- voir _noms_correspondent ci-dessous.
MARQUEURS_RESERVE_EQUIPE = {"b", "ii", "iii", "castilla", "atletic", "reserve",
                            "reservas", "u23", "u21", "u20", "u19", "juvenil"}


def _normalise_nom_equipe(nom):
    mots = re.sub(r"[^a-z0-9\s]", " ", nom.lower()).split()
    mots_utiles = [m for m in mots if m not in TOKENS_CLUB_IGNORES]
    return " ".join(mots_utiles) or nom.lower()


def _correspond_via_initiale(nom_abrege, nom_complet):
    """Cas ciblé : matchendirect réduit parfois le premier mot d'un nom
    composé à une seule initiale ('S. Bratislava' pour 'Slovan
    Bratislava', 'D. Zagreb' pour 'Dinamo Zagreb'). Ne matche QUE ce
    pattern précis -- un premier mot d'une seule lettre, suivi du reste
    du nom identique -- jamais une simple ressemblance de dernier mot."""
    mots_abr = _normalise_nom_equipe(nom_abrege).split()
    mots_complet = _normalise_nom_equipe(nom_complet).split()
    if len(mots_abr) < 2 or len(mots_abr[0]) != 1:
        return False
    reste = mots_abr[1:]
    for i, mot in enumerate(mots_complet[:-len(reste)] if len(reste) else []):
        if mot[:1] == mots_abr[0] and mots_complet[i + 1:] == reste:
            return True
    return False


def _noms_correspondent(nom_a, nom_b):
    a, b = _normalise_nom_equipe(nom_a), _normalise_nom_equipe(nom_b)
    if a and b and (a in b or b in a):
        # CORRECTIF 05/09/2026 -- même bug trouvé et corrigé dans
        # resolution_betpawa.py/scraper_details.py/calculs.py : le
        # substring seul confond une équipe et sa réserve/jeunes (ex.
        # 'Real Madrid' vs 'Real Madrid Castilla', 'PSG' vs 'PSG U19').
        # Un faux positif fait pointer vers la mauvaise page matchendirect,
        # donc de mauvaises stats de forme pour tout le calcul de lambda.
        mots_a, mots_b = set(a.split()), set(b.split())
        mots_en_trop = (mots_a - mots_b) | (mots_b - mots_a)
        if mots_en_trop & MARQUEURS_RESERVE_EQUIPE:
            return False
        return True
    # REJETÉ (26/08) : un repli par simple "dernier mot identique" avait
    # été testé, mais un test à grande échelle (2876 matchs réels) a
    # trouvé un faux positif dangereux -- "CSKA Sofia" et "Slavia Sofia"
    # (deux clubs différents, même ville) auraient matché, exactement le
    # type d'incident déjà évité pour Manchester City/United. Remplacé par
    # le repli ci-dessous, qui ne cible QUE le cas réel observé (initiale).
    return _correspond_via_initiale(nom_a, nom_b) or _correspond_via_initiale(nom_b, nom_a)


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


def _marches_plausibles(resultat):
    """AJOUT 06/09/2026 (bug #20) -- garde-fou structurel avant de compter
    les marchés d'un parseur. Une cote décimale <= 1.0 est mathématiquement
    impossible (le pari le plus sûr rapporte toujours plus que la mise) --
    un marché contenant une telle valeur est le signe que le parseur a
    dérapé sur la mauvaise ligne du texte capturé, pas un vrai marché.
    Écarte le marché ENTIER dans ce cas (jamais une valeur isolée gardée à
    côté d'une valeur fausse dans le même marché). None reste toléré
    (valeur explicitement absente, ex. `paires.get(...)` qui ne trouve
    rien) -- ce n'est pas une preuve d'erreur, contrairement à une valeur
    numérique invalide."""
    marches_valides = {}
    for marche, valeurs in resultat.items():
        if not isinstance(valeurs, dict):
            marches_valides[marche] = valeurs
            continue
        valide = all(
            v is None or (isinstance(v, (int, float)) and not isinstance(v, bool) and v > 1.0)
            for v in valeurs.values()
        )
        if valide:
            marches_valides[marche] = valeurs
    return marches_valides


def meilleur_parsing(texte, domicile, exterieur):
    """Essaie les trois parseurs connus, garde celui qui reconnaît le plus de
    marchés PLAUSIBLES (voir _marches_plausibles -- correctif #20, 06/09 :
    avant, le choix se faisait sur le nombre BRUT de marchés retournés, sans
    aucune vérification que ces marchés contiennent des cotes réalistes --
    un parseur qui dérape sur le mauvais texte pouvait gagner face au bon
    parseur simplement en produisant plus d'entrées, même fausses). Un seul
    format de capture réel en production à ce jour (Playwright), donc
    impact contextuel aujourd'hui, mais ce garde-fou protège aussi le jour
    où un autre format réapparaîtra. Trois formats réellement observés à ce
    jour, tous différents :
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
        resultat = _marches_plausibles(resultat)
        print(f"  {nom} : {len(resultat)} marché(s) plausible(s)")
        if len(resultat) > len(meilleur_resultat):
            meilleur_nom, meilleur_resultat = nom, resultat

    print(f"  Format retenu : {meilleur_nom or 'aucun'} ({len(meilleur_resultat)} marché(s))")
    return meilleur_resultat
