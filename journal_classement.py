"""Classement du Journal fondé sur des preuves (mode « preuves »).

Problème corrigé : le Journal proposait des paris dont la probabilité annoncée (fréquence de l'équipe, lissée ou
bornée par Wilson) n'avait jamais été confrontée à ce qui arrive réellement ensuite, et le filtre « probabilité >=
1/cote » choisissait les plus gros désaccords avec le bookmaker, c'est-à-dire les plus probables erreurs.

Principe (aucun coefficient arbitraire) :
  1. CALIBRAGE WALK-FORWARD. Pour chaque jour passé, on reconstruit les candidats du Journal avec les seuls matchs
     STRICTEMENT antérieurs (règle du Journal : >= 5 matchs, fréquence >= 70 %, marché non banal), puis on regarde
     ce qui s'est réellement produit. Probabilité réelle = a + b * p_lissée + c * probabilité implicite de la cote
     (moindres carrés, pentes >= 0) : le marché est le point de départ, la fréquence du Journal ne compte que si elle
     apporte quelque chose de mesurable en plus. Moins de MIN_CALIBRAGE observations : rien n'est publiable.
  2. ADMISSIBILITÉ. Un pari n'est publiable que si la BORNE BASSE (95 %) de sa probabilité calibrée couvre la
     probabilité implicite de la cote : l'espérance positive doit être démontrée, pas seulement observée.
  3. CLASSEMENT lexicographique, dans l'ordre de priorité demandé : fiabilité démontrée (borne basse calibrée),
     probabilité calibrée, espérance de gain calibrée, stabilité historique (min des deux moitiés), nombre de matchs.
  4. UN SEUL PARI PAR MATCH (marchés d'un même match fortement liés) et 15 au maximum. Si 6 passent, on publie 6.

Le module est indépendant des moteurs V2 et V3 : il ne lit que les résultats et les cotes du Journal.
Bibliothèque standard uniquement. Fonctions pures et déterministes, sauf `charge_calibrage` qui lit les fichiers.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

Z = 1.959963984540054
MAX_RETENUS = 15
MIN_CALIBRAGE = 30
PREMIER_JOUR = "2026-09-01"
COTE_MIN = 1.26
COTE_MAX = 3.01
MATCHS_FICTIFS = 20


def borne_basse_wilson(gagnes: int, joues: int, z: float = Z) -> float | None:
    if joues <= 0:
        return None
    p = gagnes / joues
    den = 1.0 + z * z / joues
    centre = p + z * z / (2 * joues)
    ecart = z * math.sqrt((p * (1 - p) + z * z / (4 * joues)) / joues)
    return (centre - ecart) / den


def lissee(gagnes: int, joues: int, base: float | None, m: int = MATCHS_FICTIFS) -> float | None:
    """Même formule que `selection_adaptative.journal_probabilite_lissee` (un test garantit l'égalité)."""
    if joues <= 0 or base is None or not 0.0 <= base <= 1.0 or gagnes < 0 or gagnes > joues:
        return None
    return (gagnes + m * base) / (joues + m)


def _gagne(resultat: Any) -> float:
    return 1.0 if resultat == 1 else 0.0


# ---------------------------------------------------------------------------
# 1. Calibrage walk-forward
# ---------------------------------------------------------------------------

def _mco(x: list[list[float]], y: list[float]) -> list[float] | None:
    """Moindres carrés ordinaires par les équations normales (pivot de Gauss). None si le système est dégénéré."""
    k = len(x[0])
    a = [[sum(r[i] * r[j] for r in x) + (1e-9 if i == j else 0.0) for j in range(k)] for i in range(k)]
    v = [sum(r[i] * yy for r, yy in zip(x, y)) for i in range(k)]
    for i in range(k):
        piv = max(range(i, k), key=lambda r: abs(a[r][i]))
        if abs(a[piv][i]) < 1e-12:
            return None
        a[i], a[piv], v[i], v[piv] = a[piv], a[i], v[piv], v[i]
        for r in range(i + 1, k):
            f = a[r][i] / a[i][i]
            for c in range(i, k):
                a[r][c] -= f * a[i][c]
            v[r] -= f * v[i]
    sol = [0.0] * k
    for i in reversed(range(k)):
        sol[i] = (v[i] - sum(a[i][c] * sol[c] for c in range(i + 1, k))) / a[i][i]
    return sol


def ajuste_calibrage(passes: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Probabilité réelle estimée = a + b * p_lissée + c * p_implicite(cote), ajustée sur des candidats dont le résultat
    est CONNU (jours passés, cote connue). Le marché est le point de départ : la fréquence du Journal n'entre que si les
    données montrent qu'elle apporte quelque chose en plus (pente b >= 0), sinon elle est écartée.
      - moins de MIN_CALIBRAGE observations : None (données insuffisantes, rien n'est publiable) ;
      - modèle complet avec b >= 0 et c >= 0 : retenu ;
      - sinon modèle « marché seul » (a + c * implicite) avec c >= 0 ;
      - sinon repli sur le marché lui-même (p = implicite) : aucun avantage démontrable, donc rien d'admissible."""
    lignes = [r for r in passes if r.get("cote") and r["cote"] > 1 and r.get("lissee") is not None]
    n = len(lignes)
    if n < MIN_CALIBRAGE:
        return None
    y = [_gagne(r.get("resultat")) for r in lignes]
    q = [1.0 / r["cote"] for r in lignes]
    li = [float(r["lissee"]) for r in lignes]
    for noms, x in ((("a", "b", "c"), [[1.0, li[i], q[i]] for i in range(n)]), (("a", "c"), [[1.0, q[i]] for i in range(n)])):
        w = _mco(x, y)
        if w is None:
            continue
        coef = dict(zip(noms, w))
        if coef.get("b", 0.0) < -1e-6 or coef.get("c", 0.0) < -1e-6:
            continue
        return {"n": n, "a": coef["a"], "b": coef.get("b", 0.0), "c": coef.get("c", 0.0), "modele": "+".join(noms)}
    return {"n": n, "a": 0.0, "b": 0.0, "c": 1.0, "modele": "marche"}


def proba_calibree(cal: dict[str, Any], p_lissee: float, p_implicite: float = 0.0) -> float:
    return min(0.99, max(0.01, cal["a"] + cal["b"] * p_lissee + cal.get("c", 0.0) * p_implicite))


def borne_basse_calibree(p: float, n: int, z: float = Z) -> float:
    """Borne basse 95 % de la probabilité calibrée : l'incertitude vient du nombre d'observations passées du calibrage."""
    return p - z * math.sqrt(max(p * (1 - p), 1e-9) / max(n, 1))


# ---------------------------------------------------------------------------
# 2. Admissibilité et 3. classement
# ---------------------------------------------------------------------------

def evalue(cand: dict[str, Any], cal: dict[str, float] | None) -> dict[str, Any]:
    """Évalue un candidat : probabilité calibrée, borne basse, espérance et motifs de rejet éventuels.
    Entrées utilisées : cote, lissee (probabilité lissée du Journal), joues, stabilite (facultative)."""
    motifs: list[str] = []
    cote = cand.get("cote")
    p_lissee = cand.get("lissee")
    if cal is None:
        motifs.append("CALIBRAGE_ABSENT")
    if p_lissee is None:
        motifs.append("PROBABILITE_NON_VERIFIABLE")
    if not cote or cote <= 1:
        motifs.append("COTE_ABSENTE")
    elif cote < COTE_MIN or cote > COTE_MAX:
        motifs.append("COTE_HORS_FENETRE")
    if motifs:
        return {"admissible": False, "motifs": motifs, "p_cal": None, "borne_basse": None, "ev": None}
    p = proba_calibree(cal, p_lissee, 1.0 / cote)
    bas = borne_basse_calibree(p, int(cal["n"]))
    if bas < 1.0 / cote:
        motifs.append("BORNE_BASSE_INF_IMPLICITE")
    return {"admissible": not motifs, "motifs": motifs, "p_cal": p, "borne_basse": bas, "ev": p * cote - 1.0}


def cle_classement(cand: dict[str, Any], ev: dict[str, Any]) -> tuple:
    """Ordre de priorité (plus grand = meilleur) : fiabilité démontrée, probabilité calibrée, espérance, stabilité,
    nombre de matchs. Les deux derniers éléments ne servent qu'à rendre l'ordre déterministe."""
    stab = cand.get("stabilite")
    return (ev["borne_basse"], ev["p_cal"], ev["ev"], stab if stab is not None else -1.0,
            int(cand.get("joues") or 0), str(cand.get("match_id") or cand.get("cle_match") or ""), str(cand.get("marche") or ""))


def cle_match(cand: dict[str, Any]) -> tuple:
    """Même match, quelle que soit la source : date + équipes ; à défaut d'équipes, l'identifiant."""
    dom, ext = str(cand.get("domicile") or "").lower(), str(cand.get("exterieur") or "").lower()
    if dom and ext:
        return (str(cand.get("date") or ""), dom, ext)
    return ("id", str(cand.get("match_id") or ""))


def selectionne(candidats: list[dict[str, Any]], cal: dict[str, float] | None,
                maximum: int = MAX_RETENUS) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Renvoie (retenus, rejetés). Retenus : admissibles, un seul par match (le mieux classé), `maximum` au plus,
    jamais complétés. Rejetés : tout le reste, avec le motif. Même entrée = même sortie, quel que soit l'ordre d'entrée."""
    evalues = [(c, evalue(c, cal)) for c in candidats]
    rejetes = [{**c, "motifs": e["motifs"]} for c, e in evalues if not e["admissible"]]
    bons = sorted([(c, e) for c, e in evalues if e["admissible"]], key=lambda t: cle_classement(*t), reverse=True)
    retenus, vus = [], set()
    for c, e in bons:
        k = cle_match(c)
        if k in vus:
            rejetes.append({**c, "motifs": ["MEME_MATCH_MIEUX_CLASSE"]})
            continue
        if len(retenus) >= maximum:
            rejetes.append({**c, "motifs": ["AU_DELA_DU_MAXIMUM"]})
            continue
        vus.add(k)
        retenus.append({**c, "p_cal": e["p_cal"], "borne_basse": e["borne_basse"], "ev": e["ev"]})
    return retenus, rejetes


# ---------------------------------------------------------------------------
# Reconstruction chronologique des candidats (même règle que journal_rentabilite.construit_equipes_a_suivre)
# ---------------------------------------------------------------------------

def _resultat(jr, libelle: str, buts: tuple[int, int]):
    analyse = jr.analyse_libelle(libelle)
    return analyse[1](*buts) if analyse else None


def marches_du_match_entier(jr) -> set[str]:
    """Marchés dont les deux équipes ont le même libellé : le même pari vu des deux côtés (ex. moins de 2,5 buts)."""
    return {nom for nom, (ld, le) in jr.MARCHES_EQUIPE.items() if ld == le}


def stats_equipes(jr, historique: list[dict[str, Any]]) -> dict[tuple, dict[str, Any]]:
    """Statistiques (équipe, ligue, marché) calculées UNIQUEMENT sur `historique` (matchs terminés)."""
    generale: dict[str, float | None] = {}
    for nom, (ld, le) in jr.MARCHES_EQUIPE.items():
        res = []
        for m in historique:
            for lib in (ld, le):
                r = _resultat(jr, lib, m["buts"])
                if r is not None:
                    res.append(r == 1)
        generale[nom] = sum(res) / len(res) if res else None
    par_equipe: dict[tuple, list] = defaultdict(list)
    for m in historique:
        par_equipe[(m["domicile"], m["ligue"])].append((m, "dom"))
        par_equipe[(m["exterieur"], m["ligue"])].append((m, "ext"))
    stats: dict[tuple, dict[str, Any]] = {}
    for (equipe, ligue), liste in par_equipe.items():
        if len(liste) < jr.MIN_MATCHS_EQUIPE:
            continue
        liste = sorted(liste, key=lambda t: (t[0]["date"], t[0]["match_id"]))
        for nom, (ld, le) in jr.MARCHES_EQUIPE.items():
            g = generale[nom]
            if g is None or g >= jr.SEUIL_FREQUENCE_EQUIPE:
                continue
            issues = []
            for m, cote_equipe in liste:
                issues.append(_resultat(jr, ld if cote_equipe == "dom" else le, m["buts"]) == 1)
            gagnes = sum(issues)
            if gagnes / len(liste) < jr.SEUIL_FREQUENCE_EQUIPE:
                continue
            moitie = len(liste) // 2
            h1, h2 = issues[:moitie], issues[moitie:]
            stats[(equipe, ligue, nom)] = {
                "gagnes": gagnes, "joues": len(liste), "generale": g,
                "stabilite": min(sum(h1) / len(h1), sum(h2) / len(h2)) if h1 and h2 else None,
            }
    return stats


def candidats_walk_forward(jr, matchs: list[dict[str, Any]], jusqu_a: str | None = None,
                           premier_jour: str = PREMIER_JOUR) -> list[dict[str, Any]]:
    """Candidats de chaque jour D reconstruits avec les matchs de date < D. `jusqu_a` : dernier jour exclu.
    Résultat et profit sont lus APRÈS coup, uniquement pour le calibrage et le backtest (jamais pour choisir)."""
    matchs = sorted(matchs, key=lambda m: (m["date"], m["match_id"]))
    jours = sorted({m["date"] for m in matchs if m["date"] >= premier_jour and (jusqu_a is None or m["date"] < jusqu_a)})
    entier = marches_du_match_entier(jr)
    lignes = []
    for jour in jours:
        historique = [m for m in matchs if m["date"] < jour]
        stats = stats_equipes(jr, historique)
        if not stats:
            continue
        for m in (x for x in matchs if x["date"] == jour):
            du_match: dict[Any, dict[str, Any]] = {}
            for equipe, cote_equipe in ((m["domicile"], "dom"), (m["exterieur"], "ext")):
                for nom, (ld, le) in jr.MARCHES_EQUIPE.items():
                    s = stats.get((equipe, m["ligue"], nom))
                    if not s:
                        continue
                    lib = ld if cote_equipe == "dom" else le
                    r = _resultat(jr, lib, m["buts"])
                    if r is None:
                        continue
                    cote = m["cotes"].get(lib) or None
                    ligne = {
                        "date": jour, "match_id": m["match_id"], "ligue": m["ligue"], "equipe": equipe,
                        "domicile": m["domicile"], "exterieur": m["exterieur"], "marche": nom, "libelle": lib,
                        "cote": cote, "gagnes": s["gagnes"], "joues": s["joues"], "frequence": s["gagnes"] / s["joues"],
                        "generale": s["generale"], "wilson": borne_basse_wilson(s["gagnes"], s["joues"]),
                        "lissee": lissee(s["gagnes"], s["joues"], s["generale"]), "stabilite": s["stabilite"],
                        "resultat": r, "profit": (cote - 1.0 if r == 1 else (0.0 if r == 0 else -1.0)) if cote else None,
                    }
                    # Marché du match entier : le même pari vu des deux équipes, on garde celle au plus grand échantillon.
                    cle = nom if nom in entier else (nom, equipe)
                    if cle not in du_match or ligne["joues"] > du_match[cle]["joues"]:
                        du_match[cle] = ligne
            lignes.extend(du_match.values())
    return lignes


def charge_calibrage(aujourdhui: str, matchs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Calibrage valable pour les paris de `aujourdhui` ou après : appris sur les candidats des jours < aujourdhui.
    Toute erreur est renvoyée dans `erreur` (jamais masquée) et rend alors le Journal non publiable (calibrage None)."""
    try:
        import journal_rentabilite as jr
        if matchs is None:
            matchs = jr.charge_tous_resultats()
        passes = candidats_walk_forward(jr, matchs, jusqu_a=aujourdhui)
        cal = ajuste_calibrage(passes)
        historique = [m for m in matchs if m["date"] < aujourdhui]
        stab = {k: v["stabilite"] for k, v in stats_equipes(jr, historique).items()}
        return {"calibrage": cal, "stabilite": stab, "observations": len(passes), "pour_le": aujourdhui, "erreur": None}
    except Exception as e:  # noqa: BLE001 - l'erreur est remontée telle quelle dans le diagnostic
        return {"calibrage": None, "stabilite": {}, "observations": 0, "pour_le": aujourdhui,
                "erreur": f"{type(e).__name__}: {e}"}
