# -*- coding: utf-8 -*-
"""Collecte des données du moteur Europe (LdC, Europa League, Conférence League) — 13/10/2026.

Aucune modification des scrapers existants : ce module les réutilise (scraper_details) et lit l'archive de test, qui
contient déjà les matchs européens à venir et leurs cotes BetPawa (résolues par resolution_betpawa_precalcul).

Ce qu'il ajoute :
  1. repérer les matchs européens (liste Matchendirect, « Europe : Ligue des Champions / Europa / Conférence ») ;
  2. lire, sur la page de chaque club, TOUTES ses rubriques européennes (saison courante + saison précédente) et sa
     rubrique de championnat national ;
  3. assembler l'entrée de moteur_europe.evaluate_match_europe (historiques + cotes BetPawa), sans jamais utiliser un
     match daté du jour du match ou après (anti-fuite).
Règles : NO DATA -> NO GO (jamais de date inventée, jamais de championnat deviné si ambigu) ; saison précédente
acceptée seulement si le site l'a vraiment servie (page différente de la saison courante).

Utilisation :  python collecte_europe.py [--archive data/archive_test] [--sortie data/europe/entrees_europe.json] [--inclure-joues]
"""
from __future__ import annotations

import argparse
import datetime
import glob
import gzip
import json
import os
import re
import sys
import time

from bs4 import BeautifulSoup

import scraper_details as sd

CODES = (("ldc", "ligue des champions"), ("el", "ligue europa"), ("ecl", "ligue conference"))
# Compétitions de clubs seulement : jeunes, féminines et qualifications sont refusées (adversaires d'un autre niveau).
MARQUEURS_REFUSES = {"jeunes", "femmes", "feminine", "feminin", "women", "u17", "u18", "u19", "u20", "u21", "u23",
                     "qualification", "qualifications", "preliminaire", "preliminaires", "amicaux"}
ZONES_NON_NATIONALES = {"europe", "monde", "asie", "afrique", "amerique du nord", "amerique du sud",
                        "amerique centrale", "oceanie"}
SAISON_PRECEDENTE_FIN = (6, 30)


def _titre(h):
    texte = " ".join(h.get_text(" ", strip=True).split())
    if ":" not in texte:
        return None, None
    pays, partie = (x.strip() for x in texte.split(":", 1))
    return pays, partie


def competition_europeenne(nom):
    """'ldc' | 'el' | 'ecl' pour une compétition de CLUBS européenne (préfixe « Europe : »), sinon None."""
    texte = " ".join(str(nom or "").split())
    if ":" not in texte:
        return None
    pays, partie = (x.strip() for x in texte.split(":", 1))
    if sd._sans_accents(pays).strip() != "europe":
        return None
    mots = sd._mots_sans_accents(partie)
    if mots & MARQUEURS_REFUSES:
        return None
    norm = sd._sans_accents(partie)
    for code, debut in CODES:
        if norm.startswith(debut):
            return code
    return None


def _propre(rows, saison, competition):
    out, sans_date = [], 0
    for m in rows or []:
        if not m.get("date"):
            sans_date += 1          # jamais de date devinée : le match est écarté et compté
            continue
        out.append({"date": m["date"], "domicile": bool(m["domicile"]), "buts_marques": int(m["buts_marques"]),
                    "buts_encaisses": int(m["buts_encaisses"]), "adversaire": str(m.get("adversaire") or "").replace("▲", "").strip(),
                    "url_match": m.get("url_match"), "source": "matchendirect", "competition": competition,
                    "saison": saison})
    return out, sans_date


def _dedoublonne(rows):
    vus, out = set(), []
    for m in sorted(rows, key=lambda m: (m["date"], m["adversaire"])):
        cle = (m["date"], m["adversaire"], m["domicile"])
        if cle not in vus:
            vus.add(cle)
            out.append(m)
    return out


def lit_page_equipe(html, nom_equipe, date_reference=None, saison="courante"):
    """Matchs européens (toutes rubriques LdC/EL/ECL) et de championnat national d'UNE page équipe."""
    soup = BeautifulSoup(html, "html.parser")
    europe, sans_date, titres_europe = [], 0, []
    nationaux = []
    for h in soup.find_all(["h2", "h3", "h4"]):
        pays, partie = _titre(h)
        if pays is None:
            continue
        code = competition_europeenne(f"{pays} : {partie}")
        if code:
            rows = sd._extrait_historique_competition(soup, partie, nom_equipe, date_reference=date_reference)
            if rows:
                propres, sd_ = _propre(rows, saison, code)
                europe += propres
                sans_date += sd_
                titres_europe.append(partie)
        elif (sd._sans_accents(pays).strip() not in ZONES_NON_NATIONALES
              and not (sd._mots_sans_accents(partie) & sd._MARQUEURS_AUTRE_COMPETITION)):
            nationaux.append(partie)
    # Championnat : parmi les rubriques nationales sans coupe/amical/femmes/jeunes, celle qui a le plus de matchs ;
    # égalité en tête -> ambigu -> aucune donnée (NO DATA -> NO GO).
    candidats = {}
    for partie in nationaux:
        rows = sd._extrait_historique_competition(soup, partie, nom_equipe, date_reference=date_reference)
        if rows:
            candidats[partie] = rows
    championnat, titre_champ, raison = [], None, None
    if candidats:
        tri = sorted(candidats.items(), key=lambda kv: len(kv[1]), reverse=True)
        if len(tri) > 1 and len(tri[0][1]) == len(tri[1][1]):
            raison = "CHAMPIONNAT_AMBIGU"
        else:
            titre_champ = tri[0][0]
            championnat, sd_ = _propre(tri[0][1], saison, "championnat")
            sans_date += sd_
    else:
        raison = "CHAMPIONNAT_INTROUVABLE"
    return {"europe": _dedoublonne(europe), "championnat": _dedoublonne(championnat), "championnat_titre": titre_champ,
            "europe_titres": titres_europe, "sans_date": sans_date, "raison_championnat": raison}


def _signature(page):
    sig = lambda rows: [(m["adversaire"], m["domicile"], m["buts_marques"], m["buts_encaisses"], m["url_match"]) for m in rows]
    return sig(page["europe"]), sig(page["championnat"])


def charge_club(url_equipe, nom_equipe, fetch=sd.fetch_html, avec_saison_precedente=True, aujourdhui=None):
    """Historique d'un club : saison courante + saison précédente (si le site l'a réellement servie)."""
    aujourdhui = aujourdhui or datetime.date.today()
    actuelle, precedente = sd._saison_actuelle_et_precedente()
    cur = lit_page_equipe(fetch(url_equipe), nom_equipe, date_reference=aujourdhui, saison=actuelle)
    meta = {"saison_precedente": "non_demandee", "sans_date": cur["sans_date"],
            "championnat_titre": cur["championnat_titre"], "raison_championnat": cur["raison_championnat"],
            "europe_titres": cur["europe_titres"]}
    europe, champ = list(cur["europe"]), list(cur["championnat"])
    if avec_saison_precedente:
        fin = datetime.date(int(precedente[-4:]), *SAISON_PRECEDENTE_FIN)   # les « JJ/MM » sont lus avant cette date
        url_p = f"{url_equipe}?season={precedente.replace('/', '%2F')}"
        try:
            prev = lit_page_equipe(fetch(url_p), nom_equipe, date_reference=fin, saison=precedente)
        except RuntimeError as e:
            meta["saison_precedente"] = f"echec_fetch: {e}"[:200]
        else:
            if _signature(prev) == _signature(cur):
                meta["saison_precedente"] = "ignoree_par_le_site"      # page identique : on ne compte jamais deux fois
            else:
                meta["saison_precedente"] = "utilisee"
                meta["sans_date"] += prev["sans_date"]
                europe += prev["europe"]
                champ += prev["championnat"]
                if cur["championnat_titre"] is None and prev["championnat_titre"]:
                    meta["championnat_titre"] = prev["championnat_titre"]
    return {"europe": _dedoublonne(europe), "championnat": _dedoublonne(champ), "meta": meta}


def avant(rows, date_match):
    """Anti-fuite : jamais un match daté du jour du match ou après."""
    return [m for m in rows if str(m["date"]) < str(date_match)]


def compte_lieu(rows, domicile):
    return sum(1 for m in rows if m["domicile"] is domicile)


def construit_entree_europe(enreg, hist_dom, hist_ext):
    """Entrée de moteur_europe.evaluate_match_europe : historiques (avant le match) + cotes BetPawa de l'archive."""
    from moteur_v3_pipeline import cotes_v3, lignes_handicap
    d = enreg["date"]
    cotes = cotes_v3(enreg)
    entree = {"europe_dom": avant(hist_dom["europe"], d), "europe_ext": avant(hist_ext["europe"], d),
              "ligue_dom": avant(hist_dom["championnat"], d), "ligue_ext": avant(hist_ext["championnat"], d),
              "odds": cotes, "handicap_lines": lignes_handicap(cotes)}
    n = {"europe_dom_domicile": compte_lieu(entree["europe_dom"], True), "europe_ext_exterieur": compte_lieu(entree["europe_ext"], False),
         "ligue_dom_domicile": compte_lieu(entree["ligue_dom"], True), "ligue_ext_exterieur": compte_lieu(entree["ligue_ext"], False)}
    n["evaluable"] = min(n.values()) >= 3 and bool(cotes)
    return entree, n


def lit_archive(dossier):
    enregs = []
    for chemin in sorted(glob.glob(os.path.join(dossier, "*.json.gz"))):
        with gzip.open(chemin, "rt", encoding="utf-8") as f:
            enregs.extend(json.load(f).values())
    return enregs


def _non_joue(e):
    sc = e.get("score")
    if not sc:
        return True
    if isinstance(sc, dict):
        return sc.get("buts_dom") is None and sc.get("buts_ext") is None
    return False


def matchs_europeens_a_venir(enregs):
    return [e for e in enregs if competition_europeenne(e.get("competition")) and _non_joue(e)]


def matchs_europeens(enregs, inclure_joues=False):
    """À venir seulement, ou aussi les matchs joués (nécessaires à l'entraînement du calibrateur)."""
    if not inclure_joues:
        return matchs_europeens_a_venir(enregs)
    return [e for e in enregs if competition_europeenne(e.get("competition"))]


def execution(archive="data/archive_test", sortie="data/europe/entrees_europe.json", cache="data/europe/cache_clubs.json",
              fetch=sd.fetch_html, pause=1.0, aujourdhui=None, inclure_joues=False):
    aujourdhui = aujourdhui or datetime.date.today()
    jour = aujourdhui.isoformat()
    cache_donnees = {}
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            cache_donnees = json.load(f)

    def club(url, nom):
        if not url:
            return {"europe": [], "championnat": [], "meta": {"erreur": "URL_EQUIPE_ABSENTE"}}
        c = cache_donnees.get(url)
        if c and c.get("charge_le") == jour:
            return c["donnees"]
        try:
            donnees = charge_club(url, nom, fetch=fetch, aujourdhui=aujourdhui)
            time.sleep(pause)
        except Exception as e:                    # un club en échec ne bloque jamais les autres
            donnees = {"europe": [], "championnat": [], "meta": {"erreur": f"{type(e).__name__}: {e}"[:200]}}
        cache_donnees[url] = {"charge_le": jour, "donnees": donnees}
        return donnees

    sorties = []
    for e in matchs_europeens(lit_archive(archive), inclure_joues):
        dom, ext = e.get("equipe_dom") or {}, e.get("equipe_ext") or {}
        hd, he = club(dom.get("url_equipe"), e.get("domicile")), club(ext.get("url_equipe"), e.get("exterieur"))
        entree, n = construit_entree_europe(e, hd, he)
        sorties.append({"match_id": e.get("match_id"), "date": e.get("date"), "competition_code": competition_europeenne(e.get("competition")),
                        "domicile": e.get("domicile"), "exterieur": e.get("exterieur"), "couverture": n, "score": e.get("score"),
                        "coup_d_envoi_utc": e.get("coup_d_envoi_utc"),
                        "heure": e.get("heure_cameroun"), "competition": e.get("competition"),
                        "meta_dom": hd["meta"], "meta_ext": he["meta"], "entree": entree})
    bilan = {"genere_le": jour, "matchs": len(sorties), "evaluables": sum(1 for s in sorties if s["couverture"]["evaluable"])}
    for chemin, contenu in ((sortie, {"bilan": bilan, "matchs": sorties}), (cache, cache_donnees)):
        os.makedirs(os.path.dirname(chemin) or ".", exist_ok=True)
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(contenu, f, ensure_ascii=False)
    return bilan


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--archive", default="data/archive_test")
    p.add_argument("--sortie", default="data/europe/entrees_europe.json")
    p.add_argument("--cache", default="data/europe/cache_clubs.json")
    p.add_argument("--inclure-joues", action="store_true")
    a = p.parse_args()
    print(json.dumps(execution(a.archive, a.sortie, a.cache, inclure_joues=a.inclure_joues), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
