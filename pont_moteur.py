#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pont_moteur.py -- pont entre le moteur de scraping (archetype-foot) et
moteur_v2_6_9.py (moteur de value bets, Poisson à un couple de λ par match).

Ne scrape rien, ne modifie aucun fichier existant, n'importe rien du dépôt :
il traduit ce que le scraping produit déjà vers le format d'entrée du moteur
(Partie 2 de la spec V2.6.2).

CE QUI EST TRADUIT
    signal du pipeline (precalcul.py)      ->  match du moteur
    ---------------------------------          ------------------------------
    match_id                                   id
    domicile / exterieur                       nom_dom / nom_ext, equipe_*.nom
    stats équipe domicile, à DOMICILE          equipe_dom.buts_marques_moy / buts_encaisses_moy
    stats équipe extérieure, à L'EXTÉRIEUR     equipe_ext.buts_marques_moy / buts_encaisses_moy
    nb_domicile / nb_exterieur                 equipe_*.matchs_joues  (V4 / R4)
    cotes_manuelles (BetPawa, imbriquées)      cotes (clés plates du moteur)
    date                                       date_match (V11)
    heure == "REP"                             statut = "reporte" (V11)
    heure "TER", "MT", "83'"                   match écarté (pas d'avant-match)
    heure d'export                             cotes_prises_le (V8)

DÉCISIONS (à contester si elles ne conviennent pas)
    1. Seules les cotes BetPawa sont exportées. Les cotes Bet365 de repli ne sont
       pas conservées sous forme exploitable dans le signal, et une value bet
       calculée sur Bet365 n'est pas jouable sur BetPawa.
    2. Domicile = stats à domicile, extérieur = stats à l'extérieur : c'est le
       couple que l'ancien moteur donnait à calcule_lambda(). Le moteur v2.6.9
       ne distingue pas le lieu, il reçoit donc déjà la bonne moyenne.
    3. meta.fiabilite n'est JAMAIS posé : le moteur interdit de l'inférer, et rien
       dans le scraping ne prouve un « classement uniquement ».
    4. Un fichier par date de match (le moteur SKIP tout match dont date_match
       diffère de --date, V11) : lancer le moteur une fois par fichier.

Sortie : export_moteur/matchs_moteur_<AAAA-MM-JJ>.json + diagnostic_pont.json
    python moteur_v2_6_9.py export_moteur/matchs_moteur_2026-09-22.json --date 2026-09-22

    python pont_moteur.py --autotest
"""
from __future__ import annotations

import collections
import datetime
import glob
import json
import os
import re
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple

VERSION_MOTEUR_CIBLE = "2.6.9"
DOSSIER_EXPORT = "export_moteur"
PREFIXE_FICHIER = "matchs_moteur_"
FICHIER_DIAGNOSTIC = "diagnostic_pont.json"

# Périmètre de lecture du moteur (moteur_v2_6_9.py, PARTIE 2). Hors périmètre :
# ignoré ici et compté dans le diagnostic, plutôt que déversé dans « non_reconnues ».
OU_X_MAX = 5              # over_X_5 / under_X_5, X = 0..5
BUTS_EQUIPE_X_MAX = 1     # buts_dom_over_X_5 ..., X = 0..1
HANDICAP_ABS_MAX = 3.0    # le moteur filtre ensuite selon LIGNES_ACTIVES (±2, ou ±3 avec --lignes-etendues)

_RE_HEURE = re.compile(r"^\d{1,2}:\d{2}$")
_RE_OU = re.compile(r"^over_under_(\d+)\.5$")
_RE_OU_EQUIPE = re.compile(r"^over_under_(domicile|exterieur)_(\d+)\.5$")
_RE_HANDICAP_2 = re.compile(r"^handicap_([+-]?\d+\.5)$")
_RE_HANDICAP_3 = re.compile(r"^handicap_3choix_(\d+)$")


# ══════════════════════════════════════════════════════════════════════════
# COTES : format imbriqué du scraping -> clés plates du moteur
# ══════════════════════════════════════════════════════════════════════════
def _num(v: Any) -> Optional[float]:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v)


def _cle_handicap(cote_side: str, ligne: float) -> str:
    """('dom', -1.5) -> 'handicap_dom_-1_5' ; ('ext', 1.0) -> 'handicap_ext_+1_0' ; 0 -> '..._0_0'."""
    signe = "+" if ligne > 0 else "-" if ligne < 0 else ""
    a = abs(ligne)
    entier = int(a)
    return f"handicap_{cote_side}_{signe}{entier}_{int(round((a - entier) * 10))}"


def cotes_vers_moteur(cotes: Any) -> Tuple[Dict[str, float], List[str]]:
    """Retourne (cotes_moteur, ignores). `ignores` liste des étiquettes courtes (une par
    élément écarté), destinées à être comptées, pas lues une à une.

    Sémantique des handicaps -- `handicap_L` du scraping = ligne L appliquée à l'équipe
    DOMICILE (« domicile » = domicile à L, « exterieur » = extérieur à −L) :
        handicap_-1.5 {domicile: a, exterieur: b}  ->  handicap_dom_-1_5 = a, handicap_ext_+1_5 = b
        handicap_3choix_1 {domicile, nul, exterieur} -> handicap_dom_-1_0, handicap_ext_+1_0
    Le « nul » du handicap à 3 choix n'a pas de clé moteur (handicap_nul_X supprimé en 2.6.2).
    """
    out: Dict[str, float] = {}
    ignores: List[str] = []
    if not isinstance(cotes, dict):
        return out, ignores

    def pose(cle: str, v: Any) -> None:
        x = _num(v)
        if x is not None:
            out[cle] = x

    for cle, val in cotes.items():
        if not isinstance(val, dict):
            ignores.append(f"{cle} (format inattendu)")
            continue

        if cle == "1x2":
            pose("victoire", val.get("1")); pose("nul", val.get("N")); pose("defaite", val.get("2"))
        elif cle == "double_chance":
            pose("dc_1X", val.get("1N")); pose("dc_X2", val.get("N2")); pose("dc_12", val.get("12"))
        elif cle == "btts":
            pose("btts_oui", val.get("Oui")); pose("btts_non", val.get("Non"))
        elif cle in ("cages_inviolees_domicile", "cages_inviolees_exterieur"):
            # « Clean Sheet | équipe = Oui » : cette équipe n'encaisse pas -> clean_sheet_dom / _ext.
            pose("clean_sheet_dom" if cle.endswith("domicile") else "clean_sheet_ext", val.get("oui"))
            if val.get("non") is not None:
                ignores.append(f"{cle}.non (pas d'équivalent moteur)")
        else:
            m = _RE_OU.match(cle)
            if m:
                x = int(m.group(1))
                if x <= OU_X_MAX:
                    pose(f"over_{x}_5", val.get("plus")); pose(f"under_{x}_5", val.get("moins"))
                else:
                    ignores.append(f"over_under_{x}.5 (hors périmètre moteur)")
                continue
            m = _RE_OU_EQUIPE.match(cle)
            if m:
                cote_side = "dom" if m.group(1) == "domicile" else "ext"
                x = int(m.group(2))
                if x <= BUTS_EQUIPE_X_MAX:
                    pose(f"buts_{cote_side}_over_{x}_5", val.get("plus"))
                    pose(f"buts_{cote_side}_under_{x}_5", val.get("moins"))
                else:
                    ignores.append(f"over_under_{m.group(1)}_{x}.5 (hors périmètre moteur)")
                continue
            m = _RE_HANDICAP_2.match(cle)
            if m:
                ligne = float(m.group(1))
                if abs(ligne) > HANDICAP_ABS_MAX:
                    ignores.append(f"{cle} (hors périmètre moteur)")
                    continue
                pose(_cle_handicap("dom", ligne), val.get("domicile"))
                pose(_cle_handicap("ext", -ligne), val.get("exterieur"))
                continue
            m = _RE_HANDICAP_3.match(cle)
            if m:
                n = float(m.group(1))
                if n == 0 or n > HANDICAP_ABS_MAX:
                    ignores.append(f"{cle} (ligne 0 = 1X2, ou hors périmètre moteur)")
                    continue
                pose(_cle_handicap("dom", -n), val.get("domicile"))
                pose(_cle_handicap("ext", n), val.get("exterieur"))
                if val.get("nul") is not None:
                    ignores.append("handicap_3choix.nul (pas d'équivalent moteur)")
                continue
            ignores.append(cle)   # pair_impair, score_exact, nombre_exact_buts, marché inconnu...
    return out, ignores


# ══════════════════════════════════════════════════════════════════════════
# ÉQUIPES : stats du scraping -> equipe_dom / equipe_ext
# ══════════════════════════════════════════════════════════════════════════
def equipe_vers_moteur(nom: str, stats: Any, role: str) -> Dict[str, Any]:
    """role = 'dom' (stats à domicile) ou 'ext' (stats à l'extérieur).
    `stats` = dict renvoyé par scraper_details.recupere_gf_ga_avec_repli. Lève ValueError."""
    lieu = "domicile" if role == "dom" else "exterieur"
    if not isinstance(stats, dict):
        raise ValueError(f"{lieu}: historique jamais récupéré pour ce match")
    if "raison_non_traite" in stats:
        raise ValueError(f"{lieu}: {stats['raison_non_traite']}")
    gf, ga, n = stats.get(f"gf_{lieu}"), stats.get(f"ga_{lieu}"), stats.get(f"nb_{lieu}")
    if _num(gf) is None or _num(ga) is None:
        raise ValueError(f"{lieu}: aucun match {'à domicile' if role == 'dom' else 'à l’extérieur'} dans l'historique")
    eq: Dict[str, Any] = {"nom": nom, "buts_marques_moy": float(gf), "buts_encaisses_moy": float(ga)}
    if isinstance(n, int) and not isinstance(n, bool) and n >= 1:
        eq["matchs_joues"] = n
    return eq


# ══════════════════════════════════════════════════════════════════════════
# MATCH
# ══════════════════════════════════════════════════════════════════════════
def match_vers_moteur(signal: Dict[str, Any], stats_equipes: Dict[Tuple[str, str], Any],
                      cotes_prises_le: Optional[str] = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Retourne (match_moteur, None) ou (None, raison). `stats_equipes` est indexé par
    (nom_equipe, competition), exactement les deux premiers arguments utiles de
    recupere_gf_ga_avec_repli."""
    mid, dom, ext, comp = (signal.get(k) for k in ("match_id", "domicile", "exterieur", "competition"))
    if not (mid and dom and ext and comp):
        return None, "donnees_de_base_manquantes"
    if not signal.get("date"):
        return None, "date_manquante"

    statut = None
    heure = signal.get("heure")
    if isinstance(heure, str) and heure.strip():
        h = heure.strip()
        if h.upper() == "REP":
            statut = "reporte"
        elif not _RE_HEURE.match(h):
            return None, "match_deja_commence_ou_termine"

    if not signal.get("cotes_manuelles"):
        return None, "pas_de_cotes_betpawa"
    cotes, ignores = cotes_vers_moteur(signal["cotes_manuelles"])
    if not cotes:
        return None, "cotes_betpawa_inexploitables"

    try:
        eq_dom = equipe_vers_moteur(dom, stats_equipes.get((dom, comp)), "dom")
        eq_ext = equipe_vers_moteur(ext, stats_equipes.get((ext, comp)), "ext")
    except ValueError as e:
        return None, f"historique_indisponible: {e}"

    match: Dict[str, Any] = {
        "id": mid, "nom_dom": dom, "nom_ext": ext,
        "equipe_dom": eq_dom, "equipe_ext": eq_ext,
        "cotes": cotes,
        "date_match": signal["date"],
        # Champs informatifs : le moteur les ignore, ils servent à relire le rapport.
        "competition": comp, "heure": heure,
        "meta": {"source_cotes": "betpawa", "betpawa_url": signal.get("betpawa_url")},
    }
    if cotes_prises_le:
        match["cotes_prises_le"] = cotes_prises_le
    if statut:
        match["statut"] = statut
    match["_ignores"] = ignores   # retiré à l'export ; sert au diagnostic
    return match, None


# ══════════════════════════════════════════════════════════════════════════
# EXPORT
# ══════════════════════════════════════════════════════════════════════════
def exporte_matchs_moteur(signaux: List[Dict[str, Any]], stats_equipes: Dict[Tuple[str, str], Any],
                          dossier: str = DOSSIER_EXPORT,
                          maintenant: Optional[datetime.datetime] = None) -> Dict[str, Any]:
    """Écrit un fichier par date de match. Les fichiers matchs_moteur_*.json d'un export
    précédent sont supprimés d'abord : le dossier ne garde que la fenêtre courante.

    cotes_prises_le = heure de l'export, appelé en fin de precalcul.py : les cotes BetPawa
    ont été lues pendant ce même run (jamais mises en cache), donc au plus quelques heures
    plus tôt. V8 n'avertit qu'au-delà de 24 h."""
    maintenant = maintenant or datetime.datetime.now(datetime.timezone.utc)
    horodatage = maintenant.strftime("%Y-%m-%dT%H:%M:%SZ")

    par_date: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
    rejets: collections.Counter = collections.Counter()
    detail_rejets: List[Dict[str, Any]] = []
    ignores_total: collections.Counter = collections.Counter()

    for s in signaux:
        match, raison = match_vers_moteur(s, stats_equipes, horodatage)
        if match is None:
            rejets[raison.split(":")[0]] += 1
            detail_rejets.append({"match_id": s.get("match_id"), "match": f"{s.get('domicile')} - {s.get('exterieur')}",
                                  "competition": s.get("competition"), "date": s.get("date"), "raison": raison})
            continue
        ignores_total.update(match.pop("_ignores"))
        par_date[match["date_match"]].append(match)

    os.makedirs(dossier, exist_ok=True)
    for ancien in glob.glob(os.path.join(dossier, f"{PREFIXE_FICHIER}*.json")):
        os.remove(ancien)

    fichiers: Dict[str, str] = {}
    for d, matchs in sorted(par_date.items()):
        matchs.sort(key=lambda m: (str(m.get("heure") or ""), str(m["id"])))
        chemin = os.path.join(dossier, f"{PREFIXE_FICHIER}{d}.json")
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump({"genere_le": horodatage, "date": d, "version_moteur_cible": VERSION_MOTEUR_CIBLE,
                       "matchs": matchs}, f, ensure_ascii=False, indent=2)
        fichiers[d] = chemin

    resume = {
        "genere_le": horodatage,
        "nb_signaux": len(signaux),
        "nb_exportes": sum(len(v) for v in par_date.values()),
        "par_date": {d: len(v) for d, v in sorted(par_date.items())},
        "rejets": dict(rejets),
        "marches_ignores": dict(ignores_total.most_common(15)),
        "fichiers": fichiers,
    }
    with open(os.path.join(dossier, FICHIER_DIAGNOSTIC), "w", encoding="utf-8") as f:
        json.dump({**resume, "detail_rejets": detail_rejets}, f, ensure_ascii=False, indent=2)
    return resume


# ══════════════════════════════════════════════════════════════════════════
# AUTOTEST -- vérifie la traduction contre la vraie sortie des parseurs du dépôt
# et contre le vrai moteur (moteur_v2_6_9.py, dans le même dossier).
# ══════════════════════════════════════════════════════════════════════════
def autotest() -> int:
    ok = True

    def check(cond: bool, msg: str) -> None:
        nonlocal ok
        print(("  OK   " if cond else "  ÉCHEC ") + msg)
        ok = ok and bool(cond)

    print("Autotests pont_moteur -> moteur", VERSION_MOTEUR_CIBLE)
    ici = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, ici)
    import moteur_v2_6_9 as moteur
    from parse_betpawa import parse_betpawa
    from parse_betpawa_playwright import parse_betpawa_playwright

    texte_en = """1X2 | Full Time
1
2.10
X
3.40
2
3.60
Double Chance | Full Time
1X
1.30
X2
1.75
12
1.28
Both Teams To Score | Full Time
Yes
1.85
No
1.95
Over/Under | Full Time
Over 2.5
1.90
Under 2.5
1.90
Over 6.5
9.00
Under 6.5
1.05
2-Way Handicap | Full Time
1
2
-1.5
3.60
+1.5
1.30
+0.5
1.45
-0.5
2.60
Clean Sheet | Alpha FC | Full Time
Yes
2.40
No
1.55
Clean Sheet | Beta FC | Full Time
Yes
3.10
No
1.35
Over/Under | Alpha FC | Full Time
Over 0.5
1.25
Under 0.5
3.80
Over 2.5
5.00
Under 2.5
1.15
Odd/Even | Full Time
Even
1.90
Odd
1.90
"""
    texte_fr = """1X2 | Fin de Match
1
2.10
X
3.40
2
3.60
Handicap À 3 Choix | Fin de Match
1
X
2
Domicile -1
2.90
Nul -1
3.80
Extérieur +1
1.40
Domicile -2
5.50
Nul -2
4.60
Extérieur +2
1.22
"""
    en = parse_betpawa_playwright(texte_en, "Alpha FC", "Beta FC")
    fr = parse_betpawa(texte_fr, "Alpha FC", "Beta FC")

    # --- cotes, à partir de la vraie sortie des parseurs -------------------
    c, ign = cotes_vers_moteur(en)
    check(c["victoire"] == 2.10 and c["nul"] == 3.40 and c["defaite"] == 3.60, "1x2 -> victoire / nul / defaite")
    check(c["dc_1X"] == 1.30 and c["dc_X2"] == 1.75 and c["dc_12"] == 1.28, "double chance : 1N->dc_1X, N2->dc_X2, 12->dc_12")
    check(c["btts_oui"] == 1.85 and c["btts_non"] == 1.95, "btts")
    check(c["over_2_5"] == 1.90 and c["under_2_5"] == 1.90 and not any("6_5" in k for k in c), "O/U 2.5 gardé, 6.5 écarté")
    check(c["handicap_dom_-1_5"] == 3.60 and c["handicap_ext_+1_5"] == 1.30,
          "handicap_-1.5 : domicile -1.5 = 3.60, extérieur +1.5 = 1.30")
    check(c["handicap_dom_+0_5"] == 1.45 and c["handicap_ext_-0_5"] == 2.60,
          "handicap_0.5 (domicile +0.5) : côtés dom/ext et signes corrects")
    check(c["clean_sheet_dom"] == 2.40 and c["clean_sheet_ext"] == 3.10, "cages inviolées Oui -> clean_sheet_dom / _ext")
    check(c["buts_dom_over_0_5"] == 1.25 and c["buts_dom_under_0_5"] == 3.80 and "buts_dom_over_2_5" not in c,
          "total de buts d'équipe : 0.5 gardé, 2.5 écarté")
    check("pair_impair" in ign and not any("pair" in k for k in c), "pair/impair ignoré")
    c3, ign3 = cotes_vers_moteur(fr)
    check(c3["handicap_dom_-1_0"] == 2.90 and c3["handicap_ext_+1_0"] == 1.40
          and c3["handicap_dom_-2_0"] == 5.50 and c3["handicap_ext_+2_0"] == 1.22,
          "handicap 3 choix : Domicile -N -> handicap_dom_-N_0, Extérieur +N -> handicap_ext_+N_0")
    check(not any(k.startswith("handicap_nul") for k in c3) and "handicap_3choix.nul (pas d'équivalent moteur)" in ign3,
          "« Nul -N » du handicap 3 choix : aucune clé moteur")
    check(cotes_vers_moteur({"1x2": {"1": None, "N": 3.4, "2": 3.6}})[0] == {"nul": 3.4, "defaite": 3.6},
          "cote absente (None) : marché non émis, jamais inventé")
    check(cotes_vers_moteur(None) == ({}, []), "cotes absentes -> vide")

    # --- le moteur lit tout ce que le pont produit -------------------------
    tous = {**c, **c3}
    stats_d = {"nb_domicile": 8, "gf_domicile": 1.8, "ga_domicile": 1.0, "nb_exterieur": 7, "gf_exterieur": 1.5, "ga_exterieur": 1.2}
    stats_e = {"nb_domicile": 6, "gf_domicile": 1.0, "ga_domicile": 1.6, "nb_exterieur": 9, "gf_exterieur": 1.2, "ga_exterieur": 1.4}
    r = moteur.analyser_match({"id": "t1", "nom_dom": "Alpha FC", "nom_ext": "Beta FC",
                               "equipe_dom": equipe_vers_moteur("Alpha FC", stats_d, "dom"),
                               "equipe_ext": equipe_vers_moteur("Beta FC", stats_e, "ext"),
                               "cotes": tous})
    marches = {l["marche"]: l for l in r["inventaire"]}
    check(r["statut_global"] != "SKIP" and r["non_reconnues"] == [],
          f"moteur : aucune clé non reconnue ({r['non_reconnues']})")
    check(all(k in marches or any(e["marche"] == k for e in r["marches_exclus"]) for k in tous),
          "moteur : chaque cote du pont finit dans l'inventaire (ou dans marches_exclus, avec raison)")
    check(r["n_matchs_dom"] == 8 and r["n_matchs_ext"] == 9, "matchs_joues : 8 à domicile (dom), 9 à l'extérieur (ext)")
    check(abs(r["lambda_dom"] - (1.8 + 1.4) / 2) < 1e-9 and abs(r["lambda_ext"] - (1.2 + 1.0) / 2) < 1e-9,
          "λ : dom = (att dom-à-domicile + déf ext-à-l'extérieur)/2 ; ext = (att ext-à-l'extérieur + déf dom-à-domicile)/2")
    li = marches["handicap_dom_-1_0"]
    check(abs(li["ev"] - (li["proba_modele"] * 2.90 - 1.0)) < 1e-12, "moteur : ligne entière -> égalité perdante (2.6.9)")

    # --- équipes ------------------------------------------------------------
    def leve(f, *a) -> str:
        try:
            f(*a)
        except ValueError as e:
            return str(e)
        return ""
    check("aucun_match_joue" in leve(equipe_vers_moteur, "X", {"raison_non_traite": "aucun_match_joue_saison_actuelle_ou_precedente"}, "dom"),
          "équipe sans historique : raison du scraper reprise")
    check("aucun match à domicile" in leve(equipe_vers_moteur, "X", {"nb_exterieur": 5, "gf_exterieur": 1.0, "ga_exterieur": 1.0}, "dom"),
          "équipe sans match à domicile : refusée")
    check("jamais récupéré" in leve(equipe_vers_moteur, "X", None, "ext"), "stats absentes : refusées")

    # --- match --------------------------------------------------------------
    stats = {("Alpha FC", "Pays : Ligue"): stats_d, ("Beta FC", "Pays : Ligue"): stats_e}
    base = {"match_id": "m1", "domicile": "Alpha FC", "exterieur": "Beta FC", "competition": "Pays : Ligue",
            "date": "2026-09-22", "heure": "20:45", "cotes_manuelles": en, "betpawa_url": "https://www.betpawa.cm/events/1"}
    m, raison = match_vers_moteur(base, stats, "2026-09-21T21:00:00Z")
    check(m is not None and m["id"] == "m1" and m["date_match"] == "2026-09-22" and "fiabilite" not in m["meta"],
          "match valide traduit, meta.fiabilite jamais posé")
    check(match_vers_moteur({**base, "heure": "TER"}, stats)[1] == "match_deja_commence_ou_termine", "heure « TER » : écarté")
    check(match_vers_moteur({**base, "heure": "83'"}, stats)[1] == "match_deja_commence_ou_termine", "match en cours : écarté")
    check(match_vers_moteur({**base, "heure": "REP"}, stats)[0]["statut"] == "reporte", "heure « REP » -> statut reporte (V11)")
    check(match_vers_moteur({k: v for k, v in base.items() if k != "cotes_manuelles"}, stats)[1] == "pas_de_cotes_betpawa",
          "sans cotes BetPawa : écarté")
    check(match_vers_moteur(base, {})[1].startswith("historique_indisponible"), "sans historique : écarté avec raison")
    check(match_vers_moteur({**base, "date": None}, stats)[1] == "date_manquante", "sans date : écarté (V11 serait aveugle)")

    # --- export bout en bout, relu par le vrai chargeur du moteur -----------
    with tempfile.TemporaryDirectory() as tmp:
        sigs = [base, {**base, "match_id": "m2", "date": "2026-09-23"}, {**base, "match_id": "m3", "heure": "TER"},
                {**base, "match_id": "m4", "domicile": "Inconnu FC"}]
        ancien = os.path.join(tmp, f"{PREFIXE_FICHIER}2026-01-01.json")
        os.makedirs(tmp, exist_ok=True)
        open(ancien, "w").write("{}")
        res = exporte_matchs_moteur(sigs, stats, dossier=tmp,
                                    maintenant=datetime.datetime(2026, 9, 21, 21, 0, tzinfo=datetime.timezone.utc))
        check(res["nb_exportes"] == 2 and set(res["par_date"]) == {"2026-09-22", "2026-09-23"}, "export : un fichier par date de match")
        check(not os.path.exists(ancien), "export : fichiers d'une fenêtre précédente supprimés")
        check(res["rejets"] == {"match_deja_commence_ou_termine": 1, "historique_indisponible": 1}, f"export : rejets comptés ({res['rejets']})")
        lus = moteur.charger_matchs(res["fichiers"]["2026-09-22"])
        rr = moteur.analyser_match(lus[0], "2026-09-22", datetime.datetime(2026, 9, 21, 22, 0, tzinfo=datetime.timezone.utc))
        check(rr["statut_global"] != "SKIP" and not any("V11" in str(a) or "V8" in str(a) for a in rr["avertissements_cotes"] + rr["avertissements_match"]),
              "moteur relit le fichier exporté : pas de SKIP, pas d'alerte V8/V11")
        rd = moteur.analyser_match(lus[0], "2026-09-23")
        check(rd["statut_global"] == "SKIP" and "V11" in (rd["raison_skip"] or ""), "moteur lancé avec la mauvaise --date : SKIP V11 (d'où un fichier par date)")

    print("\nRésultat :", "TOUS LES TESTS PASSENT" if ok else "AU MOINS UN TEST ÉCHOUE")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--autotest" in sys.argv:
        sys.exit(autotest())
    print(__doc__)
