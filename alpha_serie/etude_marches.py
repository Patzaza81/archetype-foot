"""Étude marché par marché des indices de réussite (26/10/2026). LECTURE SEULE : ne gèle rien, n'est appelée par aucun pipeline.

Reprend la rigueur de l'étude des victoires : rejeu du moteur alpha sur chaque match (matchs strictement antérieurs), séparation chronologique
stricte, sources jamais mélangées, effectifs exacts, borne basse de Wilson 95 %, comparaison à une référence propre à chaque marché.

Jeux de données DISJOINTS (aucun match compté deux fois) :
  - R  : Football-Data, avant le 01/04/2026            -> seul jeu qui sert à CHOISIR une règle ;
  - V  : Football-Data, du 01/04 au 27/09/2026         -> validation chronologique, jamais lue pendant le choix ;
  - B  : archive ARCHETYPE (cotes BetPawa d'avant match), 28/09 -> 25/10/2026 -> test à part, cotes et rendement réels.
Les matchs Football-Data du 28/09 au 16/10 sont écartés de V : ils figurent aussi dans l'archive (même match, deux sources).

Commande : python -m alpha_serie.etude_marches --ecrire   (ou sans option : affiche le résumé)
"""
from __future__ import annotations

import json
import math
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from . import coeur, parametres as P, robustesse as RB
from .marches import test_du_marche

RACINE = Path(__file__).resolve().parent.parent
SORTIE_JSON = RACINE / "data" / "etudes" / "marches_2026-10-26.json"
FIN_R = "2026-04-01"            # R : jour < FIN_R ; V : FIN_R <= jour < DEBUT_B
DEBUT_B = "2026-09-28"          # début de l'archive BetPawa ; Football-Data n'est lu qu'AVANT cette date
COTE_MIN = P.COTE_MIN           # 1,25 : cote minimale jouable du moteur (inchangée)
N_MIN_R, N_MIN_V, N_MIN_B = 200, 150, 30
Z_UNILATERAL = 1.645


# --- statistiques --------------------------------------------------------------------------------------------------------------------------------
def wilson(g: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    p = g / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - r) / d, (c + r) / d


def stats(lst: list[bool], jours: int | None = None) -> dict[str, Any]:
    n, g = len(lst), sum(lst)
    bas, haut = wilson(g, n)
    return {"matchs": n, "gagnes": g, "perdus": n - g, "taux": round(g / n, 4) if n else None, "wilson_bas_95": round(bas, 4) if n else None,
            "wilson_haut_95": round(haut, 4) if n else None, "par_jour": round(n / jours, 2) if jours else None}


def baisse_significative(g1: int, n1: int, g2: int, n2: int) -> bool:
    """Le taux du 2e jeu est-il significativement plus bas que celui du 1er ? (deux proportions, unilatéral 5 %)."""
    if n1 == 0 or n2 == 0:
        return False
    p1, p2, p = g1 / n1, g2 / n2, (g1 + g2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return se > 0 and (p1 - p2) / se > Z_UNILATERAL


def rendement(paris: list[tuple[bool, float]]) -> dict[str, Any]:
    """Mise unitaire. Gains = somme des (cote − 1) des paris gagnés ; pertes = nombre de paris perdus. IC 95 % normal sur le profit moyen."""
    n = len(paris)
    if n == 0:
        return {"paris": 0}
    profits = [(c - 1) if w else -1.0 for w, c in paris]
    m = sum(profits) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in profits) / (n - 1)) if n > 1 else 0.0
    h = 1.96 * sd / math.sqrt(n)
    return {"paris": n, "gagnes": sum(1 for w, _ in paris if w), "gains": round(sum(x for x in profits if x > 0), 2), "pertes": round(-sum(x for x in profits if x < 0), 2),
            "net": round(sum(profits), 2), "rendement": round(m, 4), "ic95": [round(m - h, 4), round(m + h, 4)], "cote_moyenne": round(sum(c for _, c in paris) / n, 3),
            "taux_equilibre": round(1 / (sum(c for _, c in paris) / n), 4)}


# --- table de rejeu ------------------------------------------------------------------------------------------------------------------------------
def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode())


def _gagne(cle: str, h: int, a: int) -> bool:
    g, s = cle.split("|")
    if g == "multigoals":
        lo, hi = map(int, s.split("-"))
        return lo <= h + a <= hi
    return bool(test_du_marche(g, s)(h, a))


def construire_table() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Rejeu reproductible. Retourne (lignes, audit). Les lignes Football-Data postérieures au début de l'archive sont écartées (doublons de source)."""
    params = P.charger()
    lignes, audit = [], {"lus": {"FD": 0, "ARCH": 0}, "analyses": {"FD": 0, "ARCH": 0}, "ecartes_doublon_de_source": 0, "ids_en_double": 0, "matchs_en_double_meme_source": 0,
                         "resultats_manquants": 0, "cotes_prises_apres_le_coup_d_envoi": 0, "cotes_sans_horodatage": 0}
    vus: set = set()
    for src, charger in (("FD", RB.charger_bloc), ("ARCH", RB.charger_archive_archetype)):
        for m in charger():
            audit["lus"][src] += 1
            if src == "FD" and m["jour"] >= DEBUT_B:
                audit["ecartes_doublon_de_source"] += 1
                continue
            if not isinstance(m.get("h"), int) or not isinstance(m.get("a"), int):
                audit["resultats_manquants"] += 1
                continue
            if m["id"] in vus:
                audit["ids_en_double"] += 1
                continue
            vus.add(m["id"])
            try:
                r = coeur.analyser_match(m["dom"], m["ext"], m["jour"], params)
            except Exception:
                continue
            if r.get("statut") != "analyse":
                continue
            if src == "ARCH":
                pris, ko = m.get("cotes_prises_le"), m.get("coup_d_envoi_utc")
                if not pris or not ko:
                    audit["cotes_sans_horodatage"] += 1
                elif pris >= ko:
                    audit["cotes_prises_apres_le_coup_d_envoi"] += 1
            propose = {tuple(f["cle"]) for lst in r["onglets"].values() for f in lst if f["onglet"] != "multiscores"}
            mk: dict[str, list] = {}
            for f in [x for lst in r["onglets"].values() for x in lst] + r["rejetes"]:
                if f.get("onglet") == "multiscores" or "offensive" not in f:
                    continue
                cle = tuple(f["cle"])
                cote = coeur.cote_de(m.get("cotes"), cle) if src == "ARCH" else None
                mk["|".join(cle)] = [f["valeur"], f["offensive"], f["defensive"], 1 if cle in propose else 0, cote]
            moy: dict[str, float] = {}
            if src == "FD":
                fd = m.get("cotes_fd") or {}
                x = (fd.get("1x2_cloture") or {}).get("moy")
                if isinstance(x, list) and len(x) == 3 and all(isinstance(v, (int, float)) and v > 1 for v in x):
                    moy.update({"1x2|1": x[0], "1x2|N": x[1], "1x2|2": x[2]})
                y = (fd.get("plus_moins_2_5_cloture") or {}).get("moy")
                if isinstance(y, list) and len(y) == 2 and all(isinstance(v, (int, float)) and v > 1 for v in y):
                    moy.update({"over_under_2.5|plus": y[0], "over_under_2.5|moins": y[1]})
            noms = (_norm(str(m.get("domicile") or m["id"].split("|")[-2])), _norm(str(m.get("exterieur") or m["id"].split("|")[-1])))
            cle_match = (src, m["jour"], noms)
            if cle_match in vus:
                audit["matchs_en_double_meme_source"] += 1
                continue
            vus.add(cle_match)
            niv = r["niveaux"]
            audit["analyses"][src] += 1
            lignes.append({"id": m["id"], "jour": m["jour"], "src": src, "h": m["h"], "a": m["a"],
                           "v": {"total": niv["total"], "d": niv["d"], "absd": abs(niv["d"]), "dom": niv["dom"], "ext": niv["ext"], "mn": min(niv["dom"], niv["ext"])},
                           "mk": mk, "moy": moy})
    lignes.sort(key=lambda r: (r["jour"], r["id"]))
    return lignes, audit


def jeu(r: dict[str, Any]) -> str:
    if r["src"] == "ARCH":
        return "B"
    return "R" if r["jour"] < FIN_R else "V"


# --- configurations (annoncées à l'avance, une famille par marché) ------------------------------------------------------------------------------
def _grille(a: float, b: float, pas: float = 0.2) -> list[float]:
    n = int(round((b - a) / pas))
    return [round(a + i * pas, 2) for i in range(n + 1)]


GRILLES = {"total": _grille(1.0, 4.6), "d": _grille(-2.0, 2.0), "absd": _grille(0.0, 2.0), "dom": _grille(0.4, 3.0), "ext": _grille(0.4, 3.0), "mn": _grille(0.2, 2.4),
           "valeur": _grille(0.5, 1.0, 0.05)}


def variables_du_marche(cle: str) -> list[tuple[str, str]]:
    """(variable, sens) du marché : la quantité de niveau que le moteur lit pour ce marché, + la valeur du moteur. Sens annoncé à l'avance."""
    g, s = cle.split("|")
    v: list[tuple[str, str]]
    m = re.fullmatch(r"over_under_(?:(domicile|exterieur)_)?\d+\.\d+", g)
    if g == "multigoals":
        v = [("total", ">="), ("total", "<=")]
    elif m and m.group(1) is None:
        v = [("total", ">=" if s == "plus" else "<=")]
    elif m:
        v = [("dom" if m.group(1) == "domicile" else "ext", ">=" if s == "plus" else "<=")]
    elif g == "btts":
        v = [("mn", ">=" if s == "Oui" else "<=")]
    elif g == "1x2" and s == "1" or (g == "double_chance" and s == "1N") or (g.startswith("handicap_") and s == "domicile"):
        v = [("d", ">=")]
    elif g == "1x2" and s == "2" or (g == "double_chance" and s == "N2") or (g.startswith("handicap_") and s == "exterieur"):
        v = [("d", "<=")]
    elif g == "1x2":
        v = [("absd", "<=")]
    elif g == "double_chance":                        # « 12 » : le moteur n'a aucune norme de niveau ; écart absolu et total, deux sens annoncés
        v = [("absd", ">="), ("total", ">=")]
    elif g.startswith("cages_inviolees_"):
        adverse = "ext" if g.endswith("domicile") else "dom"
        v = [(adverse, "<=" if s == "oui" else ">=")]
    else:
        v = []
    return v + [("valeur", ">=")]


def valeur_de(r: dict[str, Any], cle: str, var: str) -> float | None:
    if var == "valeur":
        f = r["mk"].get(cle)
        return f[0] if f else None
    return r["v"][var]


def configs(cle: str) -> list[tuple[str, str, float]]:
    out = []
    for var, op in variables_du_marche(cle):
        for t in GRILLES[var]:
            out.append((var, op, t))
    return out


def vrai(r: dict[str, Any], cle: str, c: tuple[str, str, float]) -> bool:
    x = valeur_de(r, cle, c[0])
    return x is not None and (x >= c[2] - 1e-9 if c[1] == ">=" else x <= c[2] + 1e-9)


def jours_du_jeu(j: str) -> int:
    d = {"R": ("2025-02-28", "2026-03-31"), "V": ("2026-04-01", "2026-09-27"), "B": ("2026-09-28", "2026-10-25")}[j]
    return (date.fromisoformat(d[1]) - date.fromisoformat(d[0])).days + 1


# --- étude -----------------------------------------------------------------------------------------------------------------------------------------
def objectif_du_marche(lignes: list[dict[str, Any]], cle: str) -> dict[str, Any]:
    """Taux d'équilibre propre au marché = 1 / cote moyenne des paris proposés ET jouables (cote BetPawa >= 1,25) de l'archive.
    N'utilise QUE des cotes (prix), jamais un résultat. Indéfini si moins de N_MIN_B paris jouables."""
    cotes = [r["mk"][cle][4] for r in lignes if jeu(r) == "B" and cle in r["mk"] and r["mk"][cle][3] and r["mk"][cle][4] and r["mk"][cle][4] >= COTE_MIN]
    if len(cotes) < N_MIN_B:
        return {"taux_equilibre": None, "paris_jouables_pour_le_calcul": len(cotes)}
    return {"taux_equilibre": round(1 / (sum(cotes) / len(cotes)), 4), "cote_moyenne": round(sum(cotes) / len(cotes), 3), "paris_jouables_pour_le_calcul": len(cotes)}


MODES = ("couverture", "wilson_max")


def choisir(lignes_R: list[dict[str, Any]], cle: str, objectif: float | None, mode: str = "couverture") -> dict[str, Any] | None:
    """Deux règles de choix, annoncées à l'avance et reportées ensemble (ajout du 2e mode après lecture d'un premier jeu de résultats : à signaler).
    Parmi les configurations ayant >= N_MIN_R matchs sur R et dont la borne basse de Wilson sur R atteint max(taux du marché sur R, taux d'équilibre) :
      - « couverture »  : celle de plus grand effectif (se place au bord de la barre) ;
      - « wilson_max »  : celle dont la borne basse de Wilson sur R est la plus haute (compromis taux / effectif).
    N'accède qu'à R (testé : modifier V ou B ne change pas le choix)."""
    pool = [r for r in lignes_R if cle in r["mk"] and r["mk"][cle][3]]
    if len(pool) < N_MIN_R:
        return None
    base = sum(_gagne(cle, r["h"], r["a"]) for r in pool) / len(pool)
    barre = max(base, objectif or 0.0)
    meilleur, cle_tri = None, None
    for c in configs(cle):
        sel = [r for r in pool if vrai(r, cle, c)]
        if len(sel) < N_MIN_R:
            continue
        g = sum(_gagne(cle, r["h"], r["a"]) for r in sel)
        w = wilson(g, len(sel))[0]
        if w < barre:
            continue
        k = len(sel) if mode == "couverture" else w
        if cle_tri is None or k > cle_tri:
            meilleur, cle_tri = {"config": c, "n": len(sel), "barre_R": round(barre, 4), "wilson_bas_R": round(w, 4)}, k
    return meilleur


def evaluer_config(lignes: list[dict[str, Any]], cle: str, c: tuple[str, str, float] | None) -> dict[str, Any]:
    """Statistiques d'une configuration (c=None : tous les paris proposés du marché) sur R, V et B, séparément."""
    res: dict[str, Any] = {}
    for j in ("R", "V", "B"):
        pool = [r for r in lignes if jeu(r) == j and cle in r["mk"] and r["mk"][cle][3]]
        sel = [r for r in pool if c is None or vrai(r, cle, c)]
        w = [_gagne(cle, r["h"], r["a"]) for r in sel]
        e = {**stats(w, jours_du_jeu(j)), "reference_tous_les_paris_du_marche": stats([_gagne(cle, r["h"], r["a"]) for r in pool])}
        if j == "B":
            pr = [(_gagne(cle, r["h"], r["a"]), r["mk"][cle][4]) for r in sel if r["mk"][cle][4]]
            ja = [x for x in pr if x[1] >= COTE_MIN]
            ref_ja = [(_gagne(cle, r["h"], r["a"]), r["mk"][cle][4]) for r in pool if r["mk"][cle][4] and r["mk"][cle][4] >= COTE_MIN]
            e.update({"avec_cote_betpawa": len(pr), "jouables_cote_min": len(ja), "part_jouable": round(len(ja) / len(pr), 3) if pr else None,
                      "taux_des_jouables": stats([w_ for w_, _ in ja]), "rendement_jouables": rendement(ja), "reference_jouables_sans_seuil": {**stats([w_ for w_, _ in ref_ja]), "rendement": rendement(ref_ja)}})
            sem: dict[str, list[bool]] = defaultdict(list)
            for r, ok in zip(sel, w):
                sem[f"{date.fromisoformat(r['jour']).isocalendar()[0]}-S{date.fromisoformat(r['jour']).isocalendar()[1]:02d}"].append(ok)
            e["par_semaine"] = {k: [sum(v), len(v)] for k, v in sorted(sem.items())}
        else:
            mois: dict[str, list[bool]] = defaultdict(list)
            for r, ok in zip(sel, w):
                mois[r["jour"][:7]].append(ok)
            e["par_mois"] = {k: [sum(v), len(v)] for k, v in sorted(mois.items())}
            cm = [(ok, r["moy"][cle]) for r, ok in zip(sel, w) if cle in r["moy"]]
            if cm:
                e["rendement_cotes_moyennes_cloture_football_data"] = rendement(cm)
        res[j] = e
    return res


BANDES_COTES = [(1.25, 1.35), (1.35, 1.50), (1.50, 1.70), (1.70, 2.00), (2.00, 99.0)]       # annoncées à l'avance, bornes basses incluses


def bandes_de_cotes(lignes: list[dict[str, Any]], cle: str) -> dict[str, Any]:
    """Étape EXPLORATOIRE (comme les bandes de cotes de l'étude des victoires) : réussite et rendement par bande de cote, tous les paris proposés du marché.
    B : cotes BetPawa d'avant match (28 jours). R et V : cotes moyennes de CLÔTURE de Football-Data, seulement pour 1X2 et plus/moins 2,5 (autre type de cote : jamais mélangée).
    Aucune règle n'en est tirée : 28 jours et des dizaines de cellules ne permettent pas de sélectionner."""
    def par_bande(paires: list[tuple[bool, float]]) -> list[dict[str, Any]]:
        out = []
        for lo, hi in BANDES_COTES:
            pb = [(w, c) for w, c in paires if lo <= c < hi]
            out.append({"bande": f"{lo:g}-{hi:g}" if hi < 99 else f">={lo:g}", **stats([w for w, _ in pb]), "rendement": rendement(pb)})
        return out
    res: dict[str, Any] = {"B_betpawa": par_bande([(_gagne(cle, r["h"], r["a"]), r["mk"][cle][4]) for r in lignes if jeu(r) == "B" and cle in r["mk"] and r["mk"][cle][3] and r["mk"][cle][4]])}
    if any(cle in r["moy"] for r in lignes if r["src"] == "FD"):
        for j in ("R", "V"):
            res[f"{j}_cotes_moyennes_cloture_fd"] = par_bande([(_gagne(cle, r["h"], r["a"]), r["moy"][cle]) for r in lignes if jeu(r) == j and cle in r["mk"] and r["mk"][cle][3] and cle in r["moy"]])
    return res


def verdict(ev: dict[str, Any], objectif: float | None, choisie_sur_R: bool) -> tuple[str, list[str]]:
    """Jamais « validé » : une étude rétrospective ne peut pas valider. Au mieux « sous observation » (à suivre en gel prospectif, décision de Patrick)."""
    R, V, B = ev["R"], ev["V"], ev["B"]
    raisons = []
    if V["matchs"] < N_MIN_V:
        raisons.append(f"effectif insuffisant sur V ({V['matchs']} < {N_MIN_V})")
    else:
        barre = max(V["reference_tous_les_paris_du_marche"]["taux"] or 0, objectif or 0)
        if V["wilson_bas_95"] < barre:
            raisons.append(f"borne basse de Wilson sur V ({V['wilson_bas_95']:.1%}) sous la barre du marché ({barre:.1%})")
        if baisse_significative(R["gagnes"], R["matchs"], V["gagnes"], V["matchs"]):
            raisons.append("baisse significative de R à V")
    if B["matchs"] >= N_MIN_B and B["taux"] is not None and baisse_significative(V["gagnes"], V["matchs"], B["gagnes"], B["matchs"]):
        raisons.append("baisse significative de V à l'archive BetPawa")
    if B["jouables_cote_min"] < N_MIN_B:
        raisons.append(f"jouabilité non démontrée : {B['jouables_cote_min']} paris jouables (cote BetPawa >= {COTE_MIN}) dans l'archive, minimum {N_MIN_B}")
    elif B["rendement_jouables"]["rendement"] < 0:
        r_ = B["rendement_jouables"]
        raisons.append(f"taux des paris jouables ({B['taux_des_jouables']['taux']:.1%}) sous leur propre taux d'équilibre ({r_['taux_equilibre']:.1%}) : rendement net {r_['rendement']:+.1%}, IC95 [{r_['ic95'][0]:+.1%} ; {r_['ic95'][1]:+.1%}]")
    if not choisie_sur_R:
        raisons.append("règle imposée après observation des résultats (non choisie sur R) : aucune preuve indépendante")
    if any(r.startswith(("effectif", "borne", "baisse", "jouabilité", "taux des paris")) for r in raisons):
        return "non_valide", raisons
    return "sous_observation", raisons


CANDIDATS_IMPOSES = {"over_under_3.5|moins": ("total", "<=", 2.8), "double_chance|12": ("absd", ">=", 0.6)}


def etudier(lignes: list[dict[str, Any]]) -> dict[str, Any]:
    cles = sorted({k for r in lignes for k, f in r["mk"].items() if f[3]})
    R = [r for r in lignes if jeu(r) == "R"]
    marches = {}
    for cle in cles:
        nR = sum(1 for r in R if cle in r["mk"] and r["mk"][cle][3])
        if nR < N_MIN_R:
            marches[cle] = {"etudie": False, "raison": f"{nR} paris proposés sur R (< {N_MIN_R})"}
            continue
        obj = objectif_du_marche(lignes, cle)
        entree: dict[str, Any] = {"etudie": True, "objectif": obj, "configurations_testees": len(configs(cle)), "reference": evaluer_config(lignes, cle, None), "bandes_de_cotes": bandes_de_cotes(lignes, cle), "regles": {}}
        verdicts = []
        for mode in MODES:
            choix = choisir(R, cle, obj["taux_equilibre"], mode)
            if choix is None:
                entree["regles"][mode] = {"config": None, "verdict": "non_valide", "raisons": ["aucune configuration ne passe la barre sur R"]}
            else:
                ev = evaluer_config(lignes, cle, choix["config"])
                v, rs = verdict(ev, obj["taux_equilibre"], True)
                entree["regles"][mode] = {"config": list(choix["config"]), "barre_R": choix["barre_R"], "wilson_bas_R": choix["wilson_bas_R"], "evaluation": ev, "verdict": v, "raisons": rs,
                                          "verdict_si_seule_la_hausse_sur_le_marche_compte": verdict(ev, None, True)[0]}
            verdicts.append(entree["regles"][mode]["verdict"])
        entree["verdict"] = "sous_observation" if all(v == "sous_observation" for v in verdicts) else "non_valide"
        if cle in CANDIDATS_IMPOSES:
            c = CANDIDATS_IMPOSES[cle]
            ev = evaluer_config(lignes, cle, c)
            v, rs = verdict(ev, obj["taux_equilibre"], False)
            entree["candidat_impose"] = {"config": list(c), "evaluation": ev, "verdict": v, "raisons": rs,
                                         "verdict_si_on_ignore_le_defaut_de_methode": verdict(ev, obj["taux_equilibre"], True)[0],
                                         "verdict_si_seule_la_hausse_sur_le_marche_compte": verdict(ev, None, True)[0]}
        marches[cle] = entree
    return marches


def calendrier_des_marches(marches: dict[str, Any]) -> dict[str, Any]:
    ev = [m for m in marches.values() if m.get("etudie")]
    return {"marches_etudies": len(ev), "sous_observation": sum(1 for m in ev if m["verdict"] == "sous_observation"), "non_valides": sum(1 for m in ev if m["verdict"] == "non_valide"),
            "faux_positifs_attendus_si_aucun_effet": round(0.025 * len(ev), 2)}


def recouvrement_fd_archive() -> dict[str, Any]:
    """Contrôle des matchs mal identifiés / comptés deux fois : matchs Football-Data qui sont aussi dans l'archive (même jour, noms d'équipes proches, même score)."""
    arch: dict[str, list] = defaultdict(list)
    for m in RB.charger_archive_archetype():
        arch[m["jour"]].append((_norm(m["domicile"]), _norm(m["exterieur"]), m["h"], m["a"]))
    proche = lambda x, y: x == y or (len(x) >= 4 and len(y) >= 4 and (x in y or y in x))
    fd = [m for m in RB.charger_bloc() if m["jour"] >= DEBUT_B]
    app = sc = 0
    for m in fd:
        n = m["id"].split("|")
        d, e = _norm(n[3]), _norm(n[4])
        for d2, e2, h, a in arch.get(m["jour"], []):
            if proche(d, d2) and proche(e, e2):
                app += 1
                sc += (h, a) == (m["h"], m["a"])
                break
    return {"matchs_fd_apres_debut_archive": len(fd), "retrouves_dans_archive": app, "dont_meme_score": sc}


def rapport(o: dict[str, Any]) -> str:
    p = lambda x: "-" if x is None else f"{x:.1%}"
    nom = lambda k: k.replace("|", " : ")
    a = o["audit_donnees"]
    L = [f"# Étude des marchés — audit et résultats reproductibles ({o['genere_le']})", "",
         "Statut : ÉTUDE EN LECTURE SEULE. Aucun gel, aucune modification du moteur ni de la production. Rien n'est « validé ».", "",
         "## Résultat en une ligne",
         f"- {o['synthese']['marches_etudies']} marchés étudiés ; **{o['synthese']['sous_observation']} sous observation, {o['synthese']['non_valides']} non validés**. "
         f"Sans aucun effet réel, on attendrait environ {o['synthese']['faux_positifs_attendus_si_aucun_effet']} faux positif.",
         "- Les deux candidats (Moins de 3,5 « total ≤ 2,8 » et Double chance 12 « écart ≥ 0,6 ») sont **rejetés**.", "",
         "## 1. Audit de l'étude précédente",
         f"- **Recouvrement de sources** : {o['recouvrement']['retrouves_dans_archive']} des {o['recouvrement']['matchs_fd_apres_debut_archive']} matchs Football-Data postérieurs au 28/09 sont aussi dans l'archive BetPawa "
         f"({o['recouvrement']['dont_meme_score']} avec le même score) : mes tableaux précédents les comptaient deux fois. Ici, Football-Data s'arrête au 27/09 ({a['ecartes_doublon_de_source']} lignes écartées).",
         "- **Choix après observation** : les deux candidats ont été retenus en lisant les taux de toute la période, contrôle compris. Ils ne sont pas des règles choisies sur le réglage : aucune preuve indépendante.",
         "- **Comparaison de populations différentes** : « tous les paris » (Football-Data + archive) était comparé aux « jouables » (archive seule). Ici la comparaison est faite dans la même archive (section 4).",
         "- **Fréquence par jour** fausse (division par une constante de 208) : remplacée par les jours calendaires de chaque jeu.",
         "- **Recherche en masse de la PR #117** (~40 000 règles par marché, 7 gels) : sélection optimiste, mauvaise méthode ; la PR ne doit pas être fusionnée.",
         "- **« Écart de niveau ≥ 0,6 » pour Double chance 12** : le moteur n'a aucune norme de niveau pour le « 12 » (`ecart_niveau` vide). J'ai utilisé l'écart attendu absolu |d| ; à confirmer.",
         "- **Paramètres du moteur appris sur l'archive BetPawa** (`parametres.json`, 940 matchs du 28/09 au 24/10) : le jeu B est « en échantillon » pour le moteur. La preuve principale est donc V (Football-Data), pas B.",
         "- **Second mode de choix de règle** ajouté après lecture d'un premier jeu de résultats sur V (le premier mode plaçait la règle au bord de la barre). Les deux modes sont reportés et les deux doivent passer.",
         f"- Contrôles passés : identifiants en double {a['ids_en_double']}, même match en double dans une source {a['matchs_en_double_meme_source']}, résultats manquants {a['resultats_manquants']}, "
         f"cotes BetPawa prises après le coup d'envoi {a['cotes_prises_apres_le_coup_d_envoi']}, cotes sans horodatage {a['cotes_sans_horodatage']}. Anti-fuite du moteur et choix de règle limité à R : testés (`tests/test_etude_marches.py`).", "",
         "## 2. Méthode (identique pour chaque marché ; barres et variables propres à chaque marché)",
         f"- Jeux disjoints : R = Football-Data avant le {FIN_R} ({o['lignes']['R']} matchs) ; V = Football-Data du {FIN_R} au 27/09 ({o['lignes']['V']}) ; B = archive BetPawa 28/09–25/10 ({o['lignes']['B']}). Jamais mélangés.",
         "- Population : les paris que le moteur propose réellement (même filtre que la production). Réglage uniquement sur R.",
         "- Configurations annoncées à l'avance : la variable de niveau que le moteur lit pour ce marché (total attendu, buts attendus de l'équipe, écart attendu, plus petit attendu pour « les deux marquent ») et la valeur du moteur ; pas fixes de 0,2 (0,05 pour la valeur).",
         f"- Barre propre au marché = max(taux du marché sur R, taux d'équilibre du marché). Taux d'équilibre = 1 / cote BetPawa moyenne des paris proposés jouables (cote ≥ {COTE_MIN:g}) de l'archive ; il n'utilise que des prix, jamais un résultat.",
         f"- Une règle doit avoir ≥ {N_MIN_R} matchs sur R, ≥ {N_MIN_V} sur V, borne basse de Wilson sur V ≥ barre, pas de baisse significative R→V ni V→B (test à 5 % unilatéral), ≥ {N_MIN_B} paris jouables dans l'archive et rendement net ≥ 0 sur ces paris.",
         "- « Sous observation » est le maximum possible : seul un gel prospectif peut valider. Les deux modes de choix (couverture, Wilson maximal) doivent passer.", "",
         "## 3. Résultats par marché (V = validation chronologique ; B jouables = archive, cote ≥ 1,25)",
         "| Marché | Taux marché V | Barre | Mode | Règle choisie sur R | V : gagnés/matchs | Wilson bas V | B jouables | Rend. net B | Verdict |", "|---|---|---|---|---|---|---|---|---|---|"]
    for k, m in o["marches"].items():
        if not m["etudie"]:
            continue
        for mode, r in m["regles"].items():
            if r["config"] is None:
                L.append(f"| {nom(k)} | {p(m['reference']['V']['taux'])} | {p(m['objectif']['taux_equilibre'])} | {mode} | aucune ne passe | - | - | - | - | non validé |")
                continue
            e = r["evaluation"]
            rj = e["B"]["rendement_jouables"]
            L.append(f"| {nom(k)} | {p(m['reference']['V']['taux'])} | {p(r['barre_R'])} | {mode} | {r['config'][0]} {r['config'][1]} {r['config'][2]} | {e['V']['gagnes']}/{e['V']['matchs']} ({p(e['V']['taux'])}) | {p(e['V']['wilson_bas_95'])} "
                     f"| {e['B']['jouables_cote_min']} | {('%+.1f%%' % (100 * rj['rendement'])) if rj.get('paris') else '-'} | {'sous observation' if r['verdict'] == 'sous_observation' else 'non validé'} |")
    L += ["", "Marchés non étudiés (moins de 200 paris proposés sur R) : " + ", ".join(nom(k) for k, m in o["marches"].items() if not m["etudie"]) + ".", "",
          "## 4. Le filtre « cote ≥ 1,25 » fait-il baisser la réussite ? (même archive, mêmes matchs)",
          "| Marché | Tous les paris proposés | Paris jouables | Part jouable |", "|---|---|---|---|"]
    for k, m in o["marches"].items():
        if m.get("etudie") and m["reference"]["B"]["avec_cote_betpawa"] >= 100:
            B = m["reference"]["B"]
            L.append(f"| {nom(k)} | {p(B['taux'])} ({B['matchs']}) | {p(B['taux_des_jouables']['taux'])} ({B['jouables_cote_min']}) | {p(B['part_jouable'])} |")
    L += ["", "## 5. Les deux candidats, traités par les mêmes fonctions que les autres règles"]
    for k, m in o["marches"].items():
        c = m.get("candidat_impose")
        if not c:
            continue
        e = c["evaluation"]
        rj = e["B"]["rendement_jouables"]
        L += [f"### {nom(k)} — {c['config'][0]} {c['config'][1]} {c['config'][2]} → **{c['verdict'].replace('_', ' ')}**",
              f"- R : {e['R']['gagnes']}/{e['R']['matchs']} ({p(e['R']['taux'])}), Wilson bas {p(e['R']['wilson_bas_95'])}, {e['R']['par_jour']}/jour",
              f"- V : {e['V']['gagnes']}/{e['V']['matchs']} ({p(e['V']['taux'])}), Wilson [{p(e['V']['wilson_bas_95'])} ; {p(e['V']['wilson_haut_95'])}], {e['V']['par_jour']}/jour ; tous les paris du marché sur V : {p(e['V']['reference_tous_les_paris_du_marche']['taux'])}",
              f"- B : {e['B']['gagnes']}/{e['B']['matchs']} ({p(e['B']['taux'])}) ; jouables {e['B']['jouables_cote_min']} ({p(e['B']['taux_des_jouables']['taux'])}), gains {rj.get('gains')}, pertes {rj.get('pertes')}, net {rj.get('net')}, rendement {('%+.1f%%' % (100 * rj['rendement'])) if rj.get('paris') else '-'}, IC95 {rj.get('ic95')}",
              "- Raisons : " + " ; ".join(c["raisons"]),
              f"- Hausse de réussite démontrée sur V (borne basse de Wilson {p(e['V']['wilson_bas_95'])} contre {p(e['V']['reference_tous_les_paris_du_marche']['taux'])} pour tous les paris du marché) : "
              f"{'oui' if e['V']['wilson_bas_95'] > e['V']['reference_tous_les_paris_du_marche']['taux'] else 'non'}. Rejet principal : {'rendement net négatif aux cotes jouables' if rj.get('rendement', 0) < 0 else 'voir raisons'}.", ""]
    cells = pos = ic = 0
    for m in o["marches"].values():
        for L2 in (m.get("bandes_de_cotes") or {}).values():
            for b in L2:
                if b["matchs"] >= 30:
                    cells += 1
                    pos += b["rendement"].get("rendement", 0) > 0
                    ic += bool(b["rendement"].get("ic95")) and b["rendement"]["ic95"][0] > 0
    L += ["## 6. Bandes de cotes (exploratoire, comme dans l'étude des victoires)",
          f"- {cells} cellules marché × bande × jeu avec ≥ 30 paris ; {pos} ont un rendement positif ; **{ic} ont une borne basse d'intervalle de confiance au-dessus de 0**. Aucune règle n'en est tirée.",
          "- Détail par bande et par période dans le fichier de résultats (`bandes_de_cotes`). Cotes de B = BetPawa d'avant match ; cotes de R et V = moyennes de clôture Football-Data (1X2 et plus/moins 2,5 seulement), jamais mélangées.", "",
          "## 7. Limites",
          "- Rétrospectif : aucune de ces règles n'est validée. Le seul test indépendant est le gel avant match, sur plusieurs semaines.",
          "- Archive BetPawa : 28 jours, effectifs de jouables souvent < 100 ; intervalles de rendement larges.",
          "- Multigoals : pas de cote BetPawa dans l'archive, donc jouabilité et rendement non évaluables.",
          "- Football-Data et archive couvrent des championnats différents : les taux de V et de B ne sont pas directement comparables ; ils sont présentés séparément.", "",
          "## 8. Reproduction",
          "- `python -m alpha_serie.etude_marches --ecrire` régénère `data/etudes/marches_2026-10-26.json` et ce rapport (≈ 30 s).",
          "- `python -m pytest tests/test_etude_marches.py -q` vérifie les calculs, la séparation des jeux, l'absence de fuite et la non-intégration à la production."]
    return "\n".join(L) + "\n"


RAPPORT_MD = RACINE / "docs" / "ETUDE_MARCHES_2026-10-26.md"


def ecrire() -> dict[str, Any]:
    lignes, audit = construire_table()
    marches = etudier(lignes)
    out = {"genere_le": "2026-10-26", "jeux": {"R": f"Football-Data < {FIN_R}", "V": f"Football-Data {FIN_R} -> veille de {DEBUT_B}", "B": f"archive BetPawa {DEBUT_B} -> 2026-10-25"},
           "lignes": {j: sum(1 for r in lignes if jeu(r) == j) for j in ("R", "V", "B")}, "audit_donnees": audit, "recouvrement": recouvrement_fd_archive(),
           "synthese": calendrier_des_marches(marches), "marches": marches}
    SORTIE_JSON.parent.mkdir(parents=True, exist_ok=True)
    SORTIE_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    RAPPORT_MD.write_text(rapport(out), encoding="utf-8")
    return out


if __name__ == "__main__":
    o = ecrire() if "--ecrire" in sys.argv else None
    if o:
        print(json.dumps({k: o[k] for k in ("lignes", "audit_donnees", "recouvrement", "synthese")}, ensure_ascii=False, indent=1))
