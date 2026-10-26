"""Recherche d'indices marché par marché (26/10/2026, demande de Patrick) : UN protocole commun, sans seuil de réussite imposé d'avance.

Protocole (le même pour tous les marchés ; rien n'est décidé parce qu'il « donne un beau pourcentage »)
1. Données : un match analysé par alpha = une ligne (variables calculées AVANT le match à partir des séries appariées publiées ; résultat réel ; cotes si elles
   existent, chacune dans sa propre source : moyenne du marché de Football-Data « moy », BetPawa de l'archive ARCHETYPE).
2. Recherche : conditions « variable >= t » ou « variable <= t » (t = quantiles de la période d'APPRENTISSAGE), seules ou à deux. Rien n'est présumé.
3. Séparation chronologique : apprentissage A (avant 2026-01-01) -> sélection B (2026-01-01 à 2026-03-31) -> vérification C (depuis 2026-04-01).
   La règle est choisie sur A puis B ; C n'est calculée QUE pour la règle déjà gelée (une seule par marché et par famille de variables).
4. Référence propre au marché : le taux de réussite de TOUS les matchs sur la même période (taux de base), la borne basse de Wilson à 95 %, la fréquence par jour,
   les pertes, et, quand la cote existe, le rendement réel.
5. Seuil propre au marché : une règle n'est retenue (« en validation ») que si sa borne basse de Wilson sur C dépasse le taux de base de C. Sinon « en étude »
   (le taux observé dépasse la base mais l'incertitude ne le prouve pas) ou « aucun indice ». Jamais « validé » ici : seule la mesure prospective gelée peut le dire.
6. Suivi sans triche : voir `suivi.py` (gel avant le coup d'envoi, défaites comprises, sans doublon) ; les résultats de C ne servent jamais à « valider » rétroactivement.
7. Format commun : une configuration = {marche, variables, conditions, source de cote} ; un nouveau marché s'ajoute au catalogue `MARCHES` sans changer le protocole.
Ne calcule aucun pronostic et ne modifie ni le moteur ni les tickets.
"""
from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parent.parent
FIN_A, FIN_B = "2026-01-01", "2026-04-01"      # A < FIN_A <= B < FIN_B <= C
COTE_MIN_JOUABLE = 1.25                        # minimum de cote BetPawa d'un pari jouable dans alpha (parametres.json, cote_min)
N_TECHNIQUE = 30                               # minimum de matchs pour qu'une règle soit même considérée (pas un seuil de réussite)
VARIABLES = ["gfh", "gah", "gfa", "gaa", "xh", "xa", "tot", "sup", "D", "T", "mn", "mx", "ph", "pe", "sh_o25", "sh_btts", "nfaibles"]
NIVEAUX_Q = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]


LIBELLES = {"gfh": "buts marqués par le domicile (moyenne à domicile)", "gah": "buts encaissés par le domicile", "gfa": "buts marqués par l'extérieur (moyenne à l'extérieur)",
            "gaa": "buts encaissés par l'extérieur", "xh": "buts attendus du domicile", "xa": "buts attendus de l'extérieur", "tot": "total de buts attendu",
            "sup": "supériorité offensive attendue (domicile − extérieur)", "D": "écart de niveau D", "T": "total attendu du niveau", "mn": "plus faible niveau des deux équipes",
            "mx": "plus fort niveau des deux équipes", "ph": "part des paires favorables au domicile", "pe": "part des paires favorables à l'extérieur",
            "sh_o25": "part des paires à 2,5 buts attendus ou plus", "sh_btts": "part des paires où les deux équipes marquent", "nfaibles": "matchs passés à 0 ou 1 but"}


def texte_conditions(conds: list[dict[str, Any]]) -> str:
    return " ET ".join("%s %s %s" % (LIBELLES.get(c["var"], c["var"]), c["op"], str(c["val"]).replace(".", ",")) for c in conds)


# --- catalogue des marchés : résultat réel, cote BetPawa, cote moyenne du marché (Football-Data) -----------------------------------------------

def _tot(h, a): return h + a


MARCHES: dict[str, dict[str, Any]] = {
    "vic_dom": {"nom": "Victoire à domicile", "gagne": lambda h, a: h > a, "bp": ("1x2", "1"), "moy": ("1x2", 0)},
    "vic_ext": {"nom": "Victoire à l'extérieur", "gagne": lambda h, a: a > h, "bp": ("1x2", "2"), "moy": ("1x2", 2)},
    "nul": {"nom": "Match nul", "gagne": lambda h, a: h == a, "bp": ("1x2", "N"), "moy": ("1x2", 1)},
    "dc_1n": {"nom": "Double chance 1N", "gagne": lambda h, a: h >= a, "bp": ("double_chance", "1N"), "moy": None},
    "dc_n2": {"nom": "Double chance N2", "gagne": lambda h, a: a >= h, "bp": ("double_chance", "N2"), "moy": None},
    "dc_12": {"nom": "Double chance 12 (pas de nul)", "gagne": lambda h, a: h != a, "bp": ("double_chance", "12"), "moy": None},
    "plus_1_5": {"nom": "Plus de 1,5 buts", "gagne": lambda h, a: _tot(h, a) >= 2, "bp": ("over_under_1.5", "plus"), "moy": None},
    "moins_1_5": {"nom": "Moins de 1,5 buts", "gagne": lambda h, a: _tot(h, a) <= 1, "bp": ("over_under_1.5", "moins"), "moy": None},
    "plus_2_5": {"nom": "Plus de 2,5 buts", "gagne": lambda h, a: _tot(h, a) >= 3, "bp": ("over_under_2.5", "plus"), "moy": ("ou25", 0)},
    "moins_2_5": {"nom": "Moins de 2,5 buts", "gagne": lambda h, a: _tot(h, a) <= 2, "bp": ("over_under_2.5", "moins"), "moy": ("ou25", 1)},
    "plus_3_5": {"nom": "Plus de 3,5 buts", "gagne": lambda h, a: _tot(h, a) >= 4, "bp": ("over_under_3.5", "plus"), "moy": None},
    "moins_3_5": {"nom": "Moins de 3,5 buts", "gagne": lambda h, a: _tot(h, a) <= 3, "bp": ("over_under_3.5", "moins"), "moy": None},
    "btts_oui": {"nom": "Les deux équipes marquent", "gagne": lambda h, a: h >= 1 and a >= 1, "bp": ("btts", "Oui"), "moy": None},
    "btts_non": {"nom": "Les deux équipes ne marquent pas", "gagne": lambda h, a: h == 0 or a == 0, "bp": ("btts", "Non"), "moy": None},
    "dom_plus_0_5": {"nom": "Le domicile marque", "gagne": lambda h, a: h >= 1, "bp": ("over_under_domicile_0.5", "plus"), "moy": None},
    "dom_plus_1_5": {"nom": "Le domicile marque 2 buts ou plus", "gagne": lambda h, a: h >= 2, "bp": ("over_under_domicile_1.5", "plus"), "moy": None},
    "ext_plus_0_5": {"nom": "L'extérieur marque", "gagne": lambda h, a: a >= 1, "bp": ("over_under_exterieur_0.5", "plus"), "moy": None},
    "ext_plus_1_5": {"nom": "L'extérieur marque 2 buts ou plus", "gagne": lambda h, a: a >= 2, "bp": ("over_under_exterieur_1.5", "plus"), "moy": None},
    "hcp_dom_m1_5": {"nom": "Handicap -1,5 domicile (gagne par 2 buts ou plus)", "gagne": lambda h, a: h - a >= 2, "bp": ("handicap_-1.5", "domicile"), "moy": None},
    "hcp_ext_m1_5": {"nom": "Handicap -1,5 extérieur (gagne par 2 buts ou plus)", "gagne": lambda h, a: a - h >= 2, "bp": ("handicap_1.5", "exterieur"), "moy": None},
    "hcp_dom_p1_5": {"nom": "Handicap +1,5 domicile (ne perd pas par 2 buts ou plus)", "gagne": lambda h, a: a - h <= 1, "bp": ("handicap_1.5", "domicile"), "moy": None},
    "hcp_ext_p1_5": {"nom": "Handicap +1,5 extérieur (ne perd pas par 2 buts ou plus)", "gagne": lambda h, a: h - a <= 1, "bp": ("handicap_-1.5", "exterieur"), "moy": None},
}


# --- variables (calculées à partir des seules séries appariées publiées : mêmes valeurs au rejeu et en direct) -----------------------------------

def features(niveaux: dict[str, float], off: list, de: list) -> dict[str, float] | None:
    """off[i] = (A, B) : buts marqués par le domicile / l'extérieur dans leur match i ; de[i] = (C, D) : buts encaissés par l'extérieur / le domicile."""
    n = min(len(off), len(de))
    if n == 0:
        return None
    A, B = [o[0] for o in off[:n]], [o[1] for o in off[:n]]
    C, Dd = [d[0] for d in de[:n]], [d[1] for d in de[:n]]
    m = lambda l: sum(l) / len(l)
    gfh, gfa, gaa, gah = m(A), m(B), m(C), m(Dd)
    xh, xa = (gfh + gaa) / 2, (gfa + gah) / 2
    xhi = [(a + c) / 2 for a, c in zip(A, C)]
    xai = [(b + d) / 2 for b, d in zip(B, Dd)]
    return {"gfh": gfh, "gah": gah, "gfa": gfa, "gaa": gaa, "xh": xh, "xa": xa, "tot": xh + xa, "sup": xh - xa, "D": (gfh - gah) - (gfa - gaa),
            "T": float(niveaux["total"]), "mn": float(min(niveaux["dom"], niveaux["ext"])), "mx": float(max(niveaux["dom"], niveaux["ext"])),
            "ph": sum(a > b for a, b in zip(xhi, xai)) / n, "pe": sum(b > a for a, b in zip(xhi, xai)) / n,
            "sh_o25": sum(a + b >= 2.5 for a, b in zip(xhi, xai)) / n, "sh_btts": sum(a >= 1 and b >= 1 for a, b in zip(A, B)) / n,
            "nfaibles": float(sum((a + d <= 1) + (b + c <= 1) for a, b, c, d in zip(A, B, C, Dd)))}


# --- statistiques ------------------------------------------------------------------------------------------------------------------------------

def wilson_bas(g: float, n: float, z: float = 1.96) -> float:
    if n <= 0:
        return 0.0
    p = g / n
    return (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)


def _jours(rows: list[dict]) -> int:
    ds = sorted({r["jour"] for r in rows})
    return (date.fromisoformat(ds[-1]) - date.fromisoformat(ds[0])).days + 1 if ds else 0


def periode(r: dict) -> str:
    return "A" if r["jour"] < FIN_A else "B" if r["jour"] < FIN_B else "C"


def construire_table(sortie: Path | None = None) -> list[dict[str, Any]]:
    """Rejeu reproductible : analyse alpha de chaque match du bloc Football-Data et de l'archive ARCHETYPE (matchs strictement antérieurs, sans fuite)."""
    from . import coeur, parametres as P, robustesse as RB
    params, rows = P.charger(), []
    for src, charger in (("FD", RB.charger_bloc), ("ARCH", RB.charger_archive_archetype)):
        for m in charger():
            try:
                r = coeur.analyser_match(m["dom"], m["ext"], m["jour"], params)
            except Exception:
                continue
            if r.get("statut") != "analyse":
                continue
            f = features(r["niveaux"], r["scenarios_offensifs"], r["scenarios_defensifs"])
            if f is None:
                continue
            moy: dict[str, float] = {}
            fd = m.get("cotes_fd") or {}
            x = (fd.get("1x2_cloture") or {}).get("moy")
            if isinstance(x, list) and len(x) == 3 and all(isinstance(v, (int, float)) and v > 1 for v in x):
                moy.update({"vic_dom": x[0], "nul": x[1], "vic_ext": x[2]})
            y = (fd.get("plus_moins_2_5_cloture") or {}).get("moy")
            if isinstance(y, list) and len(y) == 2 and all(isinstance(v, (int, float)) and v > 1 for v in y):
                moy.update({"plus_2_5": y[0], "moins_2_5": y[1]})
            bp: dict[str, float] = {}
            for mid, d in MARCHES.items():
                v = ((m.get("cotes") or {}).get(d["bp"][0]) or {}).get(d["bp"][1])
                if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 1:
                    bp[mid] = float(v)
            rows.append({"id": m["id"], "jour": m["jour"], "src": src, "h": m["h"], "a": m["a"], "f": f, "moy": moy, "bp": bp})
    rows.sort(key=lambda r: (r["jour"], r["id"]))
    if sortie:
        sortie.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return rows


# --- recherche ----------------------------------------------------------------------------------------------------------------------------------

def _atomes(X: Any, noms: list[str], base: Any) -> tuple[list[tuple], Any]:
    import numpy as np
    """Atomes « variable >= t » / « variable <= t », t = quantiles de la période d'apprentissage ; matrice booléenne sur TOUTES les lignes."""
    atomes, cols = [], []
    for j, nom in enumerate(noms):
        v = X[:, j]
        qs = sorted({round(float(q), 4) for q in np.nanquantile(base[:, j], NIVEAUX_Q)})
        for t in qs:
            for op in (">=", "<="):
                atomes.append((nom, op, t))
                cols.append((v >= t) if op == ">=" else (v <= t))
    return atomes, np.array(cols).T.astype(np.float32)


def _stats(mask: Any, y: Any, jours: int) -> dict[str, Any]:
    n = int(mask.sum())
    g = int((y & mask).sum())
    return {"matchs": n, "gagnes": g, "perdus": n - g, "taux": round(g / n, 4) if n else None, "wilson_bas_95": round(wilson_bas(g, n), 4) if n else None,
            "par_jour": round(n / jours, 2) if jours else None}


def _verdict(c: dict[str, Any], base_c: float, ab: dict[str, Any]) -> tuple[str, str]:
    """Verdict propre au marché, déduit des données (aucun seuil de réussite posé à la main).
    - informative : borne basse de Wilson sur C > taux de base de C ;
    - stable : le taux sur C n'est pas significativement plus bas que celui de A+B (test unilatéral à 5 % sur la différence de deux proportions).
    « en_validation » = les deux ; « en_etude » = taux observé au-dessus de la base mais une des deux preuves manque ; sinon « aucun_indice »."""
    if c["matchs"] == 0 or c["taux"] is None:
        return "aucun_indice", "aucun match en vérification"
    informative = c["wilson_bas_95"] > base_c
    p1, n1, p2, n2 = ab["taux"], ab["matchs"], c["taux"], c["matchs"]
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2) if n1 and n2 else 0.0
    stable = (p1 - p2) <= 1.645 * se
    if informative and stable:
        return "en_validation", "borne basse sur C au-dessus du taux de base et taux sans baisse significative par rapport à A+B"
    if c["taux"] > base_c:
        return "en_etude", ("incertitude trop grande : borne basse sur C sous le taux de base" if not informative else "dégradation : le taux sur C est significativement plus bas que sur A+B")
    return "aucun_indice", "le taux sur C ne dépasse pas le taux de base"


def rechercher(rows: list[dict], marche: str, cote_source: str | None = None, variables: list[str] | None = None, top_a: int = 50) -> dict[str, Any]:
    """Un marché, une famille de variables. cote_source = None (structurelles seules) ou « moy » (+ la cote moyenne du marché comme variable, lignes cotées seulement)."""
    import numpy as np
    d = MARCHES[marche]
    noms = list(variables or VARIABLES) + (["cote"] if cote_source else [])
    sel = [r for r in rows if r["src"] == "FD" or r["src"] == "ARCH"]
    if cote_source:
        sel = [r for r in sel if marche in r["moy"]]
    if len(sel) < 3 * N_TECHNIQUE:
        return {"marche": marche, "verdict": "aucun_indice", "raison": "trop peu de lignes", "lignes": len(sel)}
    X = np.array([[r["f"][v] for v in (variables or VARIABLES)] + ([r["moy"][marche]] if cote_source else []) for r in sel], dtype=float)
    y = np.array([bool(d["gagne"](r["h"], r["a"])) for r in sel])
    per = np.array([periode(r) for r in sel])
    ia, ib, ic = per == "A", per == "B", per == "C"
    jours = {k: _jours([r for r, p in zip(sel, per) if p == k]) for k in "ABC"}
    base = {k: float(y[m].mean()) for k, m in (("A", ia), ("B", ib), ("C", ic))}
    atomes, Z = _atomes(X, noms, X[ia])
    ZA = Z[ia]
    ya = y[ia].astype(np.float32)
    nA = ZA.T @ ZA
    wA = (ZA * ya[:, None]).T @ ZA
    # règles : atomes seuls (diagonale) et paires d'atomes de variables différentes
    nom_atome = [a[0] for a in atomes]
    cand: list[tuple[float, tuple[int, ...]]] = []
    for i in range(len(atomes)):
        if nA[i, i] >= N_TECHNIQUE:
            cand.append((wilson_bas(wA[i, i], nA[i, i]), (i,)))
        for j in range(i + 1, len(atomes)):
            if nom_atome[i] != nom_atome[j] and nA[i, j] >= N_TECHNIQUE:
                cand.append((wilson_bas(wA[i, j], nA[i, j]), (i, j)))
    total_testees = len(cand)
    cand.sort(key=lambda t: -t[0])
    garde = []
    for wl, idx in cand[:top_a]:
        m = np.ones(len(sel), dtype=bool)
        for i in idx:
            m &= Z[:, i].astype(bool)
        sb = _stats(m & ib, y, jours["B"])
        if sb["matchs"] >= N_TECHNIQUE and sb["wilson_bas_95"] is not None and sb["wilson_bas_95"] > base["B"]:
            ab = _stats(m & (ia | ib), y, jours["A"] + jours["B"])
            garde.append((ab["wilson_bas_95"], idx, m, sb))
    out: dict[str, Any] = {"marche": marche, "nom": d["nom"], "cote_source": cote_source, "lignes": len(sel), "taux_de_base": {k: round(v, 4) for k, v in base.items()},
                           "regles_testees_sur_A": total_testees, "retenues_apres_B": len(garde),
                           "periodes": {"A": f"< {FIN_A}", "B": f"{FIN_A} à {FIN_B}", "C": f">= {FIN_B}"}}
    if not garde:
        out.update({"verdict": "aucun_indice", "raison": "aucune règle apprise sur A ne tient sur B"})
        return out
    garde.sort(key=lambda t: -t[0])
    _, idx, m, sb = garde[0]                                   # règle GELÉE avant de regarder C
    conds = [{"var": atomes[i][0], "op": atomes[i][1], "val": atomes[i][2]} for i in idx]
    sa, sc, sab = _stats(m & ia, y, jours["A"]), _stats(m & ic, y, jours["C"]), _stats(m & (ia | ib), y, jours["A"] + jours["B"])
    verdict, raison = _verdict(sc, base["C"], sab)
    out.update({"regle": conds, "regle_texte": texte_conditions(conds), "apprentissage_A": sa, "selection_B": sb, "apprentissage_et_selection_AB": sab, "verification_C": sc,
                "verdict": verdict, "raison": raison, "taux_de_base_C": round(base["C"], 4)})
    # cote et rendement sur C quand elles existent (sources séparées, jamais mélangées)
    for src in ("moy", "bp"):
        lignes = [(r, mm) for r, mm, p in zip(sel, m, per) if p == "C" and mm and marche in r[src]]
        if lignes:
            gs = [bool(d["gagne"](r["h"], r["a"])) for r, _ in lignes]
            cs = [r[src][marche] for r, _ in lignes]
            jou = [(c, g) for c, g in zip(cs, gs) if c >= COTE_MIN_JOUABLE]
            out["cotes_" + ("moyenne_marche" if src == "moy" else "betpawa")] = {
                "matchs": len(lignes), "gagnes": sum(gs), "taux": round(sum(gs) / len(gs), 4), "cote_moyenne": round(sum(cs) / len(cs), 3),
                "rendement": round(sum((c - 1) if g else -1 for c, g in zip(cs, gs)) / len(gs), 4),
                "jouables": {"cote_min": COTE_MIN_JOUABLE, "matchs": len(jou), "gagnes": sum(g for _, g in jou), "part": round(len(jou) / len(lignes), 3),
                             "taux": round(sum(g for _, g in jou) / len(jou), 4) if jou else None}}
    return out


def tout(rows: list[dict]) -> list[dict[str, Any]]:
    res = []
    for mid, d in MARCHES.items():
        res.append(rechercher(rows, mid))
        if d["moy"]:
            res.append(rechercher(rows, mid, cote_source="moy"))
    return res


# --- règles gelées, évaluation en direct, résultats publiés -------------------------------------------------------------------------------------

DOSSIER = ROOT / "data" / "alpha_serie"
RESULTATS = DOSSIER / "decouverte_resultats.json"
GELEES = DOSSIER / "indices_decouverts.json"


def regle_vraie(conditions: list[dict[str, Any]], f: dict[str, float]) -> bool:
    """Évalue une configuration sur les variables d'un match (même fonction au rejeu et en direct)."""
    return all((f[c["var"]] >= c["val"]) if c["op"] == ">=" else (f[c["var"]] <= c["val"]) for c in conditions)


def cote_betpawa(marche: str, cotes_betpawa: dict[str, Any] | None) -> float | None:
    v = (((cotes_betpawa or {}).get(MARCHES[marche]["bp"][0])) or {}).get(MARCHES[marche]["bp"][1])
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 1 else None


def ecrire(resultats: list[dict[str, Any]], nb_lignes: int, jour: str, sortie: Path = RESULTATS, gelees: Path = GELEES) -> None:
    """Publie tous les résultats de la recherche, et fige (indices_decouverts.json) les règles structurelles « en_validation » à suivre en direct."""
    sortie.write_text(json.dumps({"genere_le": jour, "lignes_analysees": nb_lignes, "periodes": {"A": f"< {FIN_A}", "B": f"{FIN_A} à {FIN_B}", "C": f">= {FIN_B}"},
                                  "protocole": __doc__.split("Protocole")[1].split("Ne calcule")[0].strip(), "resultats": resultats}, ensure_ascii=False, indent=1), encoding="utf-8")
    fig = {}
    for r in resultats:
        if r.get("verdict") == "en_validation" and not r.get("cote_source") and "regle" in r:
            fig[r["marche"]] = {"nom": r["nom"], "gele_le": jour, "regle": r["regle"], "taux_de_base_C": r["taux_de_base_C"], "apprentissage_A": r["apprentissage_A"],
                                "selection_B": r["selection_B"], "verification_C": r["verification_C"], "taux_de_base": r["taux_de_base"]}
    gelees.write_text(json.dumps({"note": "Règles trouvées sur A, retenues sur B, vérifiées sur C, puis GELÉES ici. Leur suivi réel (gel avant match) est indépendant de ces chiffres.",
                                  "regles": fig}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    import sys
    from datetime import datetime, timezone
    lignes = construire_table()
    res = tout(lignes)
    if "--ecrire" in sys.argv:
        ecrire(res, len(lignes), datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    for r in res:
        print(r["marche"], "moy" if r.get("cote_source") else "-", r["verdict"], r.get("raison", ""))
