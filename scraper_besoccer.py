"""
scraper_besoccer.py — Récupération GF/GA domicile/extérieur et historique
récent, depuis BeSoccer.

CHOIX TECHNIQUE : pandas.read_html() plutôt que BeautifulSoup + sélecteurs
CSS. Raison explicite : je n'ai jamais pu observer le HTML brut de ce site
(mon outil de récupération web pré-extrait toujours le contenu, même en
changeant de méthode d'extraction) — donc je ne peux vérifier aucun nom de
classe CSS. pandas.read_html() lit les balises <table> par leur structure,
pas par leur style, ce qui rend ce code robuste à cette limite au lieu de
deviner des sélecteurs invérifiables.

STATUT DE VÉRIFICATION, sans détour : la structure ci-dessous (colonnes
Pts/MP/W/D/L/GK/GA/GD, onglets Total/Home/Away) a été observée trois fois de
suite via une extraction de contenu (pas le HTML source lui-même). Ce
script n'a JAMAIS tourné contre le HTML réel — ni ici (accès réseau
bloqué), ni ailleurs. La première vérification réelle aura lieu dans le
run de diagnostic GitHub Actions (voir pipeline.yml). Si la structure a
changé ou si pandas ne trouve pas les tableaux attendus, ce script échouera
proprement (exception explicite), pas silencieusement.
"""

import re
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ArchetypeFootBot/1.0; +https://github.com/)"
}

COLONNES_ATTENDUES = ["Pts", "MP", "W", "D", "L", "GK", "GA", "GD"]


def fetch_html(url, retries=3, delay=2):
    last_err = None
    for _ in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            last_err = e
            time.sleep(delay)
    raise RuntimeError(f"Échec de récupération de {url} après {retries} tentatives: {last_err}")


def _trouve_tables_classement(html):
    """
    Retourne la liste des DataFrames trouvés dans la page qui ressemblent à
    un tableau de classement (colonnes GK/GA présentes). BeSoccer affiche
    généralement 3 versions (Total/Home/Away) à la suite — on les distingue
    par leur ORDRE D'APPARITION, pas par un attribut identifiant (non
    observable). Si ça casse, ce sera parce que l'ordre a changé — à corriger
    à ce moment-là, pas à deviner maintenant.
    """
    try:
        tables = pd.read_html(html)
    except ValueError as e:
        raise RuntimeError("Aucun tableau HTML trouvé sur la page — structure probablement changée.") from e

    candidates = [t for t in tables if all(c in t.columns for c in COLONNES_ATTENDUES)]
    if not candidates:
        raise RuntimeError(
            f"Aucun tableau avec les colonnes {COLONNES_ATTENDUES} trouvé. "
            f"Colonnes disponibles dans les tableaux de la page : "
            f"{[list(t.columns) for t in tables]}"
        )
    return candidates


def recupere_gf_ga_dom_ext(nom_equipe_slug):
    """
    nom_equipe_slug : identifiant BeSoccer dans l'URL, ex. 'paris-saint-germain-fc'.
    Retourne {'domicile': {'gf':.., 'ga':.., 'mp':..}, 'exterieur': {...}}
    à partir des tableaux Total/Home/Away de la page /team/table/{slug}.
    """
    url = f"https://www.besoccer.com/team/table/{nom_equipe_slug}"
    html = fetch_html(url)
    tables = _trouve_tables_classement(html)

    if len(tables) < 3:
        raise RuntimeError(
            f"3 tableaux attendus (Total/Home/Away), {len(tables)} trouvé(s) pour {nom_equipe_slug}. "
            "Vérification manuelle nécessaire avant de faire confiance à ces chiffres."
        )

    # Ordre observé : [0]=Total, [1]=Home, [2]=Away
    table_home, table_away = tables[1], tables[2]

    def extrait_ligne_equipe(table, slug):
        # La colonne du nom d'équipe n'a pas de nom de colonne fiable observé
        # (souvent une colonne sans en-tête contenant le lien) — on cherche la
        # ligne dont une cellule contient le slug ou un nom approchant.
        for _, ligne in table.iterrows():
            texte_ligne = " ".join(str(v) for v in ligne.values)
            if slug.replace("-", " ") in texte_ligne.lower():
                return ligne
        return None

    ligne_home = extrait_ligne_equipe(table_home, nom_equipe_slug)
    ligne_away = extrait_ligne_equipe(table_away, nom_equipe_slug)

    if ligne_home is None or ligne_away is None:
        raise RuntimeError(
            f"Équipe '{nom_equipe_slug}' non trouvée dans le(s) tableau(x) Home/Away. "
            "Le slug ne correspond peut-être pas au texte affiché — vérification manuelle requise."
        )

    return {
        "domicile": {"gf": int(ligne_home["GK"]), "ga": int(ligne_home["GA"]), "mp": int(ligne_home["MP"])},
        "exterieur": {"gf": int(ligne_away["GK"]), "ga": int(ligne_away["GA"]), "mp": int(ligne_away["MP"])},
    }


def recupere_historique_matchs(nom_equipe_slug, max_matchs=10):
    """
    Retourne les `max_matchs` derniers matchs TERMINÉS (le plus récent
    d'abord), avec domicile/extérieur explicite et score, depuis la page
    /team/matches/{slug}.

    CORRECTION IMPORTANTE (25/08/2026) : la première version de cette fonction
    ancrait l'extraction sur le motif texte "**FT**" — un artefact de mise en
    forme Markdown produit par MON outil de récupération web, pas quelque
    chose qui existe dans le vrai HTML brut que ce script recevra en
    production. Ça aurait échoué silencieusement (aucune correspondance,
    liste vide) sans jamais toucher au vrai site. Corrigé : on ancre
    maintenant sur l'attribut href des liens vers /match/, qui est un
    attribut HTML réel, pas un artefact d'un outil d'extraction.
    """
    url = f"https://www.besoccer.com/team/matches/{nom_equipe_slug}"
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    resultats = []
    for a in soup.select("a[href*='/match/']"):
        if len(resultats) >= max_matchs:
            break
        texte = a.get_text(" ", strip=True)
        # Format observé (via extraction, à confirmer sur le vrai HTML) :
        # "Nantes Nantes 0-1 PSGPSG 17 AUG 2025" -- domicile dupliqué,
        # score au milieu, extérieur dupliqué, date à la fin.
        m = re.search(r"(\d+)\s*-\s*(\d+)", texte)
        if not m:
            continue  # match à venir (pas encore de score), pas une erreur

        avant_score = texte[:m.start()].strip()
        apres_score = texte[m.end():].strip()
        if not avant_score or not apres_score:
            continue

        resultats.append({
            "domicile_brut": avant_score,
            "exterieur_brut": apres_score,
            "buts_domicile": int(m.group(1)),
            "buts_exterieur": int(m.group(2)),
            "url_match": a.get("href"),
        })

    if not resultats:
        raise RuntimeError(
            f"Aucun match terminé trouvé pour {nom_equipe_slug} via les liens /match/ — "
            "structure probablement différente de celle observée, à vérifier avec le HTML réel en main "
            "(voir logs de diagnostic GitHub Actions)."
        )
    return resultats
