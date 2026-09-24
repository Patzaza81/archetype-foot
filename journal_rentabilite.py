# -*- coding: utf-8 -*-
"""Journal de rentabilité — attaque des points faibles de BetPawa (AJOUT 24/09/2026).

Chaque nuit, par le workflow séparé .github/workflows/journal.yml (lancé juste après le pipeline quotidien,
et à 05:30 UTC en secours) :

1. CARTE BETPAWA : pour chaque match terminé coté BetPawa, on règle TOUTES les cotes relevées
   (pas seulement celles choisies par un moteur) sur le score final. Sources :
     - data/echantillon_betpawa_501.json (base figée, 501 matchs du 09 au 20/09/2026) ;
     - historique_pronostics.json (matchs à source_cotes == "manuel" = cotes BetPawa), qui grossit chaque nuit.
   On mesure par segment (championnat, marché, championnat x famille, championnat x marché, tranche de cote)
   ce que BetPawa fait réellement payer : ROI à mise fixe, intervalle de confiance à 95 % (rééchantillonnage
   des MATCHS, les cotes d'un même match étant liées), stabilité entre la 1re et la 2e moitié chronologique.

2. MOTEURS : ROI réel des sélections P1/P2/P3 de moteur_v2_6_9 (archive/) et de shrink_v1 (archive_shrink/),
   uniquement sur les matchs cotés BetPawa, par championnat et par famille de marché.

3. CONSEILS : pour les matchs à venir cotés BetPawa (precalcul_leger.json / precalcul_shrink_leger.json), les
   marchés qui tombent dans un segment « A_JOUER » ou « A_SURVEILLER », jamais dans un segment « A_EVITER »,
   et les sélections de chaque moteur annotées du statut de leur segment.

Statuts d'un segment (règles fixes, publiées sur la page) :
  A_JOUER      : borne basse de l'IC 95 % > 0, ROI > 0 sur CHAQUE moitié, >= 40 matchs ;
  A_SURVEILLER : ROI > 0, ROI > 0 sur chaque moitié, >= 25 matchs (mise symbolique : pas encore prouvé) ;
  A_EVITER     : borne haute de l'IC 95 % < 0, >= 25 matchs ;
  NEUTRE       : le reste.

Bibliothèque standard uniquement (exigence du test d'intégrité du dépôt). Aucune écriture hors journal.json.
Usage : python journal_rentabilite.py
"""
import datetime
import glob
import json
import os
import random
import re
from collections import defaultdict

RACINE = os.path.dirname(os.path.abspath(__file__))
FICHIER_ECHANTILLON = os.path.join(RACINE, "data", "echantillon_betpawa_501.json")
FICHIER_HISTORIQUE = os.path.join(RACINE, "historique_pronostics.json")
FICHIERS_PRECALCUL = {"moteur_v2_6_9": os.path.join(RACINE, "precalcul_leger.json"),
                      "shrink_v1": os.path.join(RACINE, "precalcul_shrink_leger.json")}
REPERTOIRES_ARCHIVE = {"moteur_v2_6_9": os.path.join(RACINE, "archive"),
                       "shrink_v1": os.path.join(RACINE, "archive_shrink")}
FICHIER_SORTIE = os.path.join(RACINE, "journal.json")

VERSION = "1.0.0"
MIN_MATCHS_JOUER = 40
MIN_MATCHS_SURVEILLER = 25
MIN_MATCHS_EVITER = 25
TIRAGES_BOOTSTRAP = 800
GRAINE = 20260924
SOURCES_BETPAWA = {"manuel", "betpawa"}
FUSEAU_DOUALA = datetime.timezone(datetime.timedelta(hours=1))

# =============================================================================
# 1. Libellés de marchés -> règlement sur le score
# =============================================================================

_COTE = {"Domicile": "dom", "Extérieur": "ext", "Exterieur": "ext"}


def _res(v):
    return 1 if v else -1


def ligne_propre(ligne_affichee, equipe):
    """Convention de historique_pronostics.json (vérifiée le 24/09/2026 sur 733 matchs : « Handicap -0.5 - Extérieur »
    a la même cote que la double chance X2 dans 99 % des cas) : la ligne affichée est celle de l'équipe À DOMICILE.
    « Handicap -0.5 - Extérieur » = l'extérieur reçoit +0.5. Renvoie la ligne de l'équipe réellement jouée."""
    return ligne_affichee if equipe == "dom" else -ligne_affichee


def analyse_libelle(libelle):
    """Libellé BetPawa/pipeline -> (famille, fonction(buts_dom, buts_ext) -> 1 gagné / 0 remboursé / -1 perdu).
    Renvoie None si le libellé n'est pas reconnu (il est alors compté dans 'libelles_non_reconnus')."""
    if not isinstance(libelle, str):
        return None
    l = " ".join(libelle.split())
    m = re.fullmatch(r"1X2 - (1|X|2)", l)
    if m:
        c = m[1]
        return "1X2", (lambda h, a: _res(h > a)) if c == "1" else (lambda h, a: _res(h == a)) if c == "X" else (lambda h, a: _res(h < a))
    m = re.fullmatch(r"Double chance - (1X|X2|12)", l)
    if m:
        c = m[1]
        return "Double chance", (lambda h, a: _res(h >= a)) if c == "1X" else (lambda h, a: _res(h <= a)) if c == "X2" else (lambda h, a: _res(h != a))
    m = re.fullmatch(r"BTTS - (oui|non)", l, re.I)
    if m:
        oui = m[1].lower() == "oui"
        return "BTTS", (lambda h, a, o=oui: _res((h > 0 and a > 0) == o))
    m = re.fullmatch(r"(Plus|Moins) de (\d+(?:\.\d+)?) buts", l)
    if m:
        plus, L = m[1] == "Plus", float(m[2])
        if float(L).is_integer():
            return None  # ligne entière (remboursement possible) non produite par le pipeline : refus explicite
        return "Total buts", (lambda h, a, p=plus, L=L: _res((h + a > L) if p else (h + a < L)))
    m = re.fullmatch(r"(Plus|Moins) de (\d+(?:\.\d+)?) buts - (Domicile|Extérieur|Exterieur)", l)
    if m:
        plus, L, eq = m[1] == "Plus", float(m[2]), _COTE[m[3]]
        if float(L).is_integer():
            return None
        return "Buts équipe", (lambda h, a, p=plus, L=L, e=eq: _res(((h if e == "dom" else a) > L) if p else ((h if e == "dom" else a) < L)))
    m = re.fullmatch(r"Cage inviolée - (Domicile|Extérieur|Exterieur)", l)
    if m:
        eq = _COTE[m[1]]
        return "Cage inviolée", (lambda h, a, e=eq: _res((a if e == "dom" else h) == 0))
    m = re.fullmatch(r"Encaisse au moins 1 but - (Domicile|Extérieur|Exterieur)", l)
    if m:
        eq = _COTE[m[1]]
        return "Cage inviolée", (lambda h, a, e=eq: _res((a if e == "dom" else h) >= 1))
    m = re.fullmatch(r"Handicap (-?\d+(?:\.\d+)?) - (Domicile|Extérieur|Exterieur)", l)
    if m:
        ligne, eq = ligne_propre(float(m[1]), _COTE[m[2]]), _COTE[m[2]]

        def f(h, a, ligne=ligne, e=eq):
            d = (h - a if e == "dom" else a - h) + ligne
            return 1 if d > 0 else (0 if d == 0 else -1)
        return "Handicap", f
    m = re.fullmatch(r"Total buts - (pair|impair)", l, re.I)
    if m:
        pair = m[1].lower() == "pair"
        return "Pair / impair", (lambda h, a, p=pair: _res(((h + a) % 2 == 0) == p))
    return None


# =============================================================================
# 1 bis. Contrôle de cohérence des cotes (erreurs de scraping)
# =============================================================================
# Constat du 24/09/2026 : dans historique_pronostics.json, une partie des handicaps BetPawa porte le mauvais signe
# (ex. « Handicap 2.5 - Extérieur » à 9.74 alors que l'extérieur est favori à 2.14 : c'est en réalité le -2.5).
# Sans ce contrôle, ces cotes fabriquent de faux segments « rentables » (Handicap 2.5 - Extérieur : ROI +22 %).
TOLERANCE_HANDICAP = 0.15


def controle_coherence(cotes):
    """Retire les cotes de handicap incompatibles avec le 1X2 / la double chance du même match.
    Règles (handicap à 2 issues, lignes x.5) :
      - équipe +L (L > 0)  : au moins aussi probable que « ne perd pas » -> cote <= cote double chance x 1.15 ;
      - équipe -0.5        : même événement que la victoire sèche      -> cote entre 0.85 et 1.15 x cote victoire ;
      - équipe -L (L >= 1.5): moins probable que la victoire sèche     -> cote >= cote victoire x 0.85.
    Renvoie (cotes_propres, rejets[libellé])."""
    ref = {"dom": (cotes.get("1X2 - 1"), cotes.get("Double chance - 1X")),
           "ext": (cotes.get("1X2 - 2"), cotes.get("Double chance - X2"))}
    propres, rejets = {}, []
    for lib, o in cotes.items():
        m = re.fullmatch(r"Handicap (-?\d+(?:\.\d+)?) - (Domicile|Extérieur|Exterieur)", " ".join(lib.split()))
        if not m:
            propres[lib] = o
            continue
        eq = _COTE[m[2]]
        ligne = ligne_propre(float(m[1]), eq)
        victoire, double = ref[eq]
        ok = True
        if ligne > 0 and double:
            ok = o <= double * (1 + TOLERANCE_HANDICAP)
        elif ligne == -0.5 and victoire:
            ok = victoire * (1 - TOLERANCE_HANDICAP) <= o <= victoire * (1 + TOLERANCE_HANDICAP)
        elif ligne <= -1.5 and victoire:
            ok = o >= victoire * (1 - TOLERANCE_HANDICAP)
        if ok:
            propres[lib] = o
        else:
            rejets.append(lib)
    return propres, rejets


def libelle_depuis_moteur(marche):
    """Nom de marché des moteurs (archive/, sélections P1-P3) -> libellé BetPawa/pipeline. None si inconnu."""
    if not isinstance(marche, str):
        return None
    m = marche.strip()
    fixes = {"1x2_domicile": "1X2 - 1", "1x2_nul": "1X2 - X", "1x2_exterieur": "1X2 - 2",
             "double_chance_1X": "Double chance - 1X", "double_chance_X2": "Double chance - X2",
             "double_chance_12": "Double chance - 12", "btts_oui": "BTTS - oui", "btts_non": "BTTS - non",
             "clean_sheet_domicile": "Cage inviolée - Domicile", "clean_sheet_exterieur": "Cage inviolée - Extérieur"}
    if m in fixes:
        return fixes[m]
    r = re.fullmatch(r"over_under_total_(\d+(?:\.\d+)?)_(over|under)", m)
    if r:
        return f"{'Plus' if r[2] == 'over' else 'Moins'} de {r[1]} buts"
    r = re.fullmatch(r"buts_equipe_(domicile|exterieur)_(\d+(?:\.\d+)?)_(over|under)", m)
    if r:
        return f"{'Plus' if r[3] == 'over' else 'Moins'} de {r[2]} buts - {'Domicile' if r[1] == 'domicile' else 'Extérieur'}"
    r = re.fullmatch(r"handicap_(domicile|exterieur)_(-?\d+(?:\.\d+)?)", m)
    if r:
        # moteurs : ligne de l'équipe jouée ; libellés : ligne vue du domicile (voir ligne_propre)
        ligne = float(r[2]) if r[1] == "domicile" else -float(r[2])
        return f"Handicap {ligne:g} - {'Domicile' if r[1] == 'domicile' else 'Extérieur'}"
    return None


def lit_score(score):
    if isinstance(score, str):
        r = re.fullmatch(r"\s*(\d+)\s*[-:]\s*(\d+)\s*", score)
        if r:
            return int(r[1]), int(r[2])
    return None


def tranche_cote(o):
    if o < 1.30:
        return "1.01 – 1.29"
    if o < 1.70:
        return "1.30 – 1.69"
    if o < 2.50:
        return "1.70 – 2.49"
    if o < 5.0:
        return "2.50 – 4.99"
    return "5.00 et plus"


def nom_ligue(competition):
    return " ".join(str(competition or "").split()) or "Inconnue"

# =============================================================================
# 2. Chargement des matchs terminés cotés BetPawa
# =============================================================================


def _lire_json(chemin, defaut):
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def charge_matchs_betpawa(fichier_echantillon=FICHIER_ECHANTILLON, fichier_historique=FICHIER_HISTORIQUE):
    """Renvoie (matchs, diagnostic). Un match = {match_id, date, ligue, domicile, exterieur, buts, cotes{libelle: cote}}.
    Dédoublonnage par match_id : l'échantillon figé est prioritaire, puis la PREMIÈRE capture de l'historique
    (la plus ancienne, donc la plus proche d'un pari réellement pris avant le match)."""
    matchs, diag = {}, {"echantillon": 0, "historique": 0, "historique_ignores_non_betpawa": 0}
    for m in (_lire_json(fichier_echantillon, {}) or {}).get("matchs", []):
        buts = lit_score(m.get("score"))
        if buts and m.get("cotes"):
            matchs[m["match_id"]] = {"match_id": m["match_id"], "date": m["date"], "ligue": nom_ligue(m.get("competition")),
                                     "domicile": m.get("domicile"), "exterieur": m.get("exterieur"), "buts": buts,
                                     "cotes": {k: float(v) for k, v in m["cotes"].items() if v and float(v) > 1.0}}
            diag["echantillon"] += 1
    historique = _lire_json(fichier_historique, [])
    jours = sorted(historique, key=lambda j: str(j.get("date", ""))) if isinstance(historique, list) else []
    for jour in jours:
        for m in jour.get("matchs", []) or []:
            mid = m.get("match_id")
            if not mid or mid in matchs:
                continue
            if m.get("source_cotes") not in SOURCES_BETPAWA:
                diag["historique_ignores_non_betpawa"] += 1
                continue
            buts = lit_score(m.get("score"))
            cotes = {}
            for x in m.get("TOUS_MARCHES_EVALUES") or []:
                o = x.get("cote_observee")
                try:
                    o = float(o)
                except (TypeError, ValueError):
                    continue
                if o > 1.0 and x.get("marche"):
                    cotes[x["marche"]] = o
            if not buts or not cotes:
                continue
            matchs[mid] = {"match_id": mid, "date": str(m.get("date") or jour.get("date")), "ligue": nom_ligue(m.get("competition")),
                           "domicile": m.get("domicile"), "exterieur": m.get("exterieur"), "buts": buts, "cotes": cotes}
            diag["historique"] += 1
    return list(matchs.values()), diag


def ids_betpawa(fichier_echantillon=FICHIER_ECHANTILLON, fichier_historique=FICHIER_HISTORIQUE):
    """Identifiants de tous les matchs cotés BetPawa (terminés ou non) : sert à filtrer les archives des moteurs."""
    ids = {m.get("match_id") for m in (_lire_json(fichier_echantillon, {}) or {}).get("matchs", [])}
    for jour in _lire_json(fichier_historique, []) or []:
        for m in jour.get("matchs", []) or []:
            if m.get("source_cotes") in SOURCES_BETPAWA:
                ids.add(m.get("match_id"))
    ids.discard(None)
    return ids

# =============================================================================
# 3. Statistiques par segment
# =============================================================================


def paris_depuis_matchs(matchs):
    """Règle chaque cote de chaque match. Renvoie (paris, libelles_non_reconnus, cotes_incoherentes_retirees)."""
    paris, inconnus, incoherentes = [], defaultdict(int), defaultdict(int)
    for m in matchs:
        h, a = m["buts"]
        cotes, rejets = controle_coherence(m["cotes"])
        for lib in rejets:
            incoherentes[lib] += 1
        for lib, o in cotes.items():
            an = analyse_libelle(lib)
            if an is None:
                inconnus[lib] += 1
                continue
            famille, fn = an
            r = fn(h, a)
            paris.append({"match_id": m["match_id"], "date": m["date"], "ligue": m["ligue"], "marche": " ".join(lib.split()),
                          "famille": famille, "cote": o, "profit": (o - 1.0) if r == 1 else (0.0 if r == 0 else -1.0),
                          "resultat": r})
    return paris, dict(inconnus), dict(incoherentes)


def _ic_cluster(paris, tirages=TIRAGES_BOOTSTRAP, graine=GRAINE):
    par_match = defaultdict(lambda: [0.0, 0])
    for p in paris:
        par_match[p["match_id"]][0] += p["profit"]
        par_match[p["match_id"]][1] += 1
    blocs = list(par_match.values())
    if len(blocs) < 2:
        return None, None
    rnd = random.Random(graine)
    rois = []
    for _ in range(tirages):
        tot = n = 0
        for _ in range(len(blocs)):
            b = blocs[rnd.randrange(len(blocs))]
            tot += b[0]
            n += b[1]
        rois.append(tot / n)
    rois.sort()
    return rois[int(0.025 * tirages)], rois[int(0.975 * tirages) - 1]


def statut_segment(n_matchs, roi, bas, haut, roi_m1, roi_m2):
    if n_matchs >= MIN_MATCHS_JOUER and bas is not None and bas > 0 and roi_m1 is not None and roi_m1 > 0 and roi_m2 is not None and roi_m2 > 0:
        return "A_JOUER"
    if n_matchs >= MIN_MATCHS_EVITER and haut is not None and haut < 0:
        return "A_EVITER"
    if n_matchs >= MIN_MATCHS_SURVEILLER and roi > 0 and roi_m1 is not None and roi_m1 > 0 and roi_m2 is not None and roi_m2 > 0:
        return "A_SURVEILLER"
    return "NEUTRE"


def stats_segment(paris):
    n = len(paris)
    ids = sorted({p["match_id"] for p in paris})
    dates = sorted({p["date"] for p in paris})
    roi = sum(p["profit"] for p in paris) / n
    gagnes = sum(1 for p in paris if p["resultat"] == 1)
    rembourses = sum(1 for p in paris if p["resultat"] == 0)
    milieu = dates[len(dates) // 2] if dates else None
    m1 = [p for p in paris if p["date"] < milieu] if milieu else []
    m2 = [p for p in paris if milieu and p["date"] >= milieu]
    roi_m1 = sum(p["profit"] for p in m1) / len(m1) if len(m1) >= 10 else None
    roi_m2 = sum(p["profit"] for p in m2) / len(m2) if len(m2) >= 10 else None
    bas, haut = _ic_cluster(paris) if len(ids) >= MIN_MATCHS_SURVEILLER else (None, None)
    return {"paris": n, "matchs": len(ids), "roi": round(roi, 4),
            "ic95": [round(bas, 4), round(haut, 4)] if bas is not None else None,
            "roi_moitie_1": round(roi_m1, 4) if roi_m1 is not None else None,
            "roi_moitie_2": round(roi_m2, 4) if roi_m2 is not None else None,
            "reussite": round(gagnes / (n - rembourses), 4) if n > rembourses else None,
            "cote_moyenne": round(sum(p["cote"] for p in paris) / n, 3),
            "statut": statut_segment(len(ids), roi, bas, haut, roi_m1, roi_m2)}


DIMENSIONS = {
    "ligues": lambda p: p["ligue"],
    "marches": lambda p: p["marche"],
    "familles": lambda p: p["famille"],
    "tranches_de_cote": lambda p: tranche_cote(p["cote"]),
    "ligue_famille": lambda p: p["ligue"] + " | " + p["famille"],
    "ligue_marche": lambda p: p["ligue"] + " | " + p["marche"],
}


def construit_segments(paris):
    out = {}
    for nom, cle in DIMENSIONS.items():
        groupes = defaultdict(list)
        for p in paris:
            groupes[cle(p)].append(p)
        lignes = []
        for k, v in groupes.items():
            if len({p["match_id"] for p in v}) < 10:
                continue
            s = stats_segment(v)
            s["segment"] = k
            lignes.append(s)
        ordre = {"A_JOUER": 0, "A_SURVEILLER": 1, "NEUTRE": 2, "A_EVITER": 3}
        lignes.sort(key=lambda s: (ordre[s["statut"]], -s["roi"]))
        out[nom] = lignes
    return out

# =============================================================================
# 4. Performance réelle des moteurs (sélections P1-P3, matchs BetPawa uniquement)
# =============================================================================


def charge_selections_resolues(repertoire, ids_bp):
    paris = []
    for chemin in sorted(glob.glob(os.path.join(repertoire, "*.json"))):
        for r in _lire_json(chemin, []) or []:
            if r.get("categorie") != "SELECTED" or r.get("resultat_statut") != "RESOLVED":
                continue
            if r.get("match_id") not in ids_bp:
                continue
            res = r.get("resultat_marche")
            try:
                o = float(r.get("cote"))
            except (TypeError, ValueError):
                continue
            if res == "WIN":
                profit, code = o - 1.0, 1
            elif res == "LOSS":
                profit, code = -1.0, -1
            elif res in ("PUSH", "VOID"):
                profit, code = 0.0, 0
            else:
                continue
            lib = libelle_depuis_moteur(r.get("marche"))
            an = analyse_libelle(lib) if lib else None
            paris.append({"match_id": r["match_id"], "date": str(r.get("date_match")), "ligue": nom_ligue(r.get("competition")),
                          "marche": lib or r.get("marche"), "famille": an[0] if an else (r.get("market_family") or "Autre"),
                          "cote": o, "profit": profit, "resultat": code})
    return paris


def construit_moteurs(ids_bp):
    out = {}
    for nom, rep in REPERTOIRES_ARCHIVE.items():
        paris = charge_selections_resolues(rep, ids_bp)
        if not paris:
            out[nom] = {"global": None, "ligues": [], "familles": [], "note": "Aucune sélection résolue sur un match coté BetPawa pour l'instant."}
            continue
        seg = {}
        for dim in ("ligues", "familles"):
            groupes = defaultdict(list)
            for p in paris:
                groupes[DIMENSIONS[dim](p)].append(p)
            lignes = []
            for k, v in groupes.items():
                s = stats_segment(v)
                s["segment"] = k
                lignes.append(s)
            lignes.sort(key=lambda s: -s["paris"])
            seg[dim] = lignes
        out[nom] = {"global": stats_segment(paris), "ligues": seg["ligues"], "familles": seg["familles"]}
    return out

# =============================================================================
# 5. Conseils pour les matchs à venir
# =============================================================================


def _index_statuts(segments):
    return {dim: {s["segment"]: s for s in lignes} for dim, lignes in segments.items()}


def verdict_marche(index, ligue, libelle, cote):
    """Statut d'un marché pour un match. Niveaux examinés du plus précis au plus général :
    championnat x marché, championnat x famille, marché (tous championnats). Le premier niveau dont le statut
    n'est pas NEUTRE décide : une preuve précise l'emporte sur une tendance générale. Les niveaux très larges
    (famille seule, tranche de cote, championnat seul) sont affichés à titre d'information mais ne décident pas :
    ils sont tous négatifs à cause de la marge et bloqueraient tout. Renvoie (statut, preuve_ou_None)."""
    an = analyse_libelle(libelle)
    if an is None or not cote:
        return "INCONNU", None
    famille = an[0]
    lib = " ".join(libelle.split())
    niveaux = [("ligue_marche", ligue + " | " + lib), ("ligue_famille", ligue + " | " + famille), ("marches", lib)]
    trouves = [(d, index.get(d, {}).get(cle)) for d, cle in niveaux]
    trouves = [(d, s) for d, s in trouves if s]
    for d, s in trouves:
        if s["statut"] != "NEUTRE":
            return s["statut"], dict(s, niveau=d)
    return "NEUTRE", (dict(trouves[0][1], niveau=trouves[0][0]) if trouves else None)


def _aujourdhui():
    return datetime.datetime.now(FUSEAU_DOUALA).date().isoformat()


def construit_conseils(segments, aujourdhui=None, fichiers=FICHIERS_PRECALCUL):
    aujourdhui = aujourdhui or _aujourdhui()
    index = _index_statuts(segments)
    conseils, pronostics = [], {}
    deja = set()
    for moteur, chemin in fichiers.items():
        doc = _lire_json(chemin, {}) or {}
        liste = []
        for s in doc.get("signaux", []) or []:
            if str(s.get("date", "")) < aujourdhui:
                continue
            betpawa = s.get("source_cotes") in SOURCES_BETPAWA
            ligue = nom_ligue(s.get("competition"))
            base = {"match_id": s.get("match_id"), "date": s.get("date"), "heure": s.get("heure_cameroun") or s.get("heure"),
                    "ligue": ligue, "domicile": s.get("domicile"), "exterieur": s.get("exterieur"),
                    "betpawa_url": s.get("betpawa_url"), "cotes_betpawa": betpawa}
            # Sélections du moteur (P1-P3), annotées
            bloc = s.get(moteur) or {}
            for rang in ("P1", "P2", "P3"):
                sel = (bloc.get("selection") or {}).get(rang)
                if not sel:
                    continue
                lib = libelle_depuis_moteur(sel.get("marche"))
                try:
                    cote = float(sel.get("cote"))
                except (TypeError, ValueError):
                    cote = None
                statut, preuve = verdict_marche(index, ligue, lib, cote) if (lib and cote) else ("INCONNU", None)
                if not betpawa:
                    statut = "COTE_NON_BETPAWA"
                resume = (sel.get("justification") or {}).get("resume")
                liste.append(dict(base, rang=rang, marche=lib or sel.get("marche"), cote=cote,
                                  probabilite=sel.get("probabilite"), statut_journal=statut, preuve=preuve, justification=resume))
            # Conseils du journal : tous les marchés cotés BetPawa du match (une seule fois par match)
            if betpawa and s.get("match_id") not in deja:
                deja.add(s.get("match_id"))
                cotes_match = {}
                for x in s.get("TOUS_MARCHES_EVALUES") or []:
                    try:
                        cotes_match[x.get("marche")] = float(x.get("cote_observee"))
                    except (TypeError, ValueError):
                        continue
                cotes_match, _ = controle_coherence({k: v for k, v in cotes_match.items() if k and v > 1.0})
                for lib, cote in cotes_match.items():
                    statut, preuve = verdict_marche(index, ligue, lib, cote)
                    if statut in ("A_JOUER", "A_SURVEILLER"):
                        conseils.append(dict(base, marche=" ".join(lib.split()), cote=cote, statut_journal=statut, preuve=preuve))
        ordre = {"A_JOUER": 0, "A_SURVEILLER": 1, "NEUTRE": 2, "INCONNU": 3, "COTE_NON_BETPAWA": 4, "A_EVITER": 5}
        liste.sort(key=lambda x: (ordre.get(x["statut_journal"], 9), str(x["date"]), str(x["heure"])))
        pronostics[moteur] = {"genere_le": doc.get("genere_le"), "selections": liste}
    conseils.sort(key=lambda x: (0 if x["statut_journal"] == "A_JOUER" else 1, str(x["date"]), str(x["heure"]), -(x["preuve"] or {}).get("roi", 0)))
    return conseils, pronostics

# =============================================================================
# 6. Assemblage
# =============================================================================


def construit_journal(aujourdhui=None):
    matchs, diag = charge_matchs_betpawa()
    paris, inconnus, incoherentes = paris_depuis_matchs(matchs)
    segments = construit_segments(paris) if paris else {k: [] for k in DIMENSIONS}
    conseils, pronostics = construit_conseils(segments, aujourdhui)
    moteurs = construit_moteurs(ids_betpawa())
    dates = sorted({m["date"] for m in matchs})
    compte = {dim: {st: sum(1 for s in lignes if s["statut"] == st) for st in ("A_JOUER", "A_SURVEILLER", "NEUTRE", "A_EVITER")}
              for dim, lignes in segments.items()}
    return {
        "version": VERSION,
        "genere_le": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "donnees": {"matchs": len(matchs), "cotes_reglees": len(paris), "periode": [dates[0], dates[-1]] if dates else None,
                    "sources": diag, "libelles_non_reconnus": inconnus, "cotes_incoherentes_retirees": incoherentes,
                    "cout_global_betpawa": stats_segment(paris) if paris else None},
        "regles": {"A_JOUER": f"IC 95 % entièrement positif, ROI positif sur chaque moitié de la période, au moins {MIN_MATCHS_JOUER} matchs",
                   "A_SURVEILLER": f"ROI positif sur toute la période et sur chaque moitié, au moins {MIN_MATCHS_SURVEILLER} matchs — pas encore prouvé : mise symbolique",
                   "A_EVITER": f"IC 95 % entièrement négatif, au moins {MIN_MATCHS_EVITER} matchs",
                   "NEUTRE": "ni prouvé, ni à éviter",
                   "avertissement": "Beaucoup de segments sont testés : quelques-uns sortent « à surveiller » par pur hasard. "
                                    "Seul « à jouer » repose sur une preuve statistique, et il est recalculé chaque nuit."},
        "comptage_statuts": compte,
        "conseils": conseils,
        "pronostics": pronostics,
        "moteurs": moteurs,
        "segments": segments,
    }


def main():
    journal = construit_journal()
    with open(FICHIER_SORTIE, "w", encoding="utf-8") as f:
        json.dump(journal, f, ensure_ascii=False, indent=1)
    d = journal["donnees"]
    cg = d["cout_global_betpawa"] or {}
    print(f"[journal] {d['matchs']} matchs BetPawa terminés, {d['cotes_reglees']} cotes réglées, coût global BetPawa "
          f"{cg.get('roi', 0):+.1%} -- {len(journal['conseils'])} conseil(s) pour les matchs à venir.")
    for dim, c in journal["comptage_statuts"].items():
        print(f"[journal] {dim}: {c}")
    if d["cotes_incoherentes_retirees"]:
        print(f"[journal] cotes incohérentes retirées (erreurs de relevé probables) : {sum(d['cotes_incoherentes_retirees'].values())}")
    if d["libelles_non_reconnus"]:
        print(f"[journal] libellés non reconnus (ignorés, à ajouter si fréquents) : {d['libelles_non_reconnus']}")


if __name__ == "__main__":
    main()
