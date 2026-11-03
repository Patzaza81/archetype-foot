"""Données du moteur Europe-Gamma : les trois échantillons de Patrick (03/11/2026), lus dans data/europe/entrees_europe.json (bloc de collecte commun).

Autonome : aucun import d'un autre moteur.

Trois échantillons par équipe, TOUJOURS au même lieu (domicile pour A, extérieur pour B) et strictement avant le jour du match :
- « prec »  : saison européenne PRÉCÉDENTE, les 5 derniers matchs au même lieu ................ poids de base 20 %
- « champ » : championnat de la saison EN COURS, tous les matchs de la saison au même lieu ....... poids de base 30 %
- « eu »    : matchs européens de la saison EN COURS, tous au même lieu ........................ poids de base 50 %

Un échantillon n'entre dans le calcul que si LES DEUX équipes ont au moins N_MIN matchs dedans (« NO DATA -> NO GO », jamais de zéro de remplacement).
Un échantillon absent est retiré et les poids restants sont renormalisés (20/30/50 gardent leurs proportions) ; la fiche dit toujours lesquels ont servi.

Forces en présence : chaque observation est pesée par la force de l'adversaire affronté (points par match de l'adversaire dans le classement de la MÊME compétition ÷ moyenne
du classement). Adversaire introuvable dans le classement = poids neutre 1, compté et affiché (jamais deviné). Aucun coefficient posé à la main.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from . import marches as M

ROOT = Path(__file__).resolve().parent.parent
ENTREES = ROOT / "data" / "europe" / "entrees_europe.json"
CLASSEMENTS = ROOT / "cache_classement.json"

SOURCES = ("prec", "champ", "eu")
N_PREC_MAX = 5                       # décision de Patrick : « les 5 derniers dans le même lieu » de la saison européenne passée
N_MIN = 3                            # minimum par équipe et par échantillon : celui que Patrick avait fixé pour l'Europe (13/10/2026)
CLE_CLASSEMENT_EUROPE = {"ldc": "europe : ligue des champions phase de ligue", "el": "europe : ligue europa phase de ligue",
                         "ecl": "europe : ligue conférence phase de ligue"}


def norm(s: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", str(s or "").lower()).encode("ascii", "ignore").decode())


def saisons(jour: str) -> tuple[str, str]:
    """(saison en cours, saison précédente) à la date du match : une saison court de juillet à juin."""
    y, mth = int(jour[:4]), int(jour[5:7])
    d = y if mth >= 7 else y - 1
    return f"{d}/{d + 1}", f"{d - 1}/{d}"


def _valide(x: dict[str, Any]) -> bool:
    return bool(x.get("date")) and isinstance(x.get("buts_marques"), int) and isinstance(x.get("buts_encaisses"), int) \
        and not isinstance(x["buts_marques"], bool) and not isinstance(x["buts_encaisses"], bool) and x["buts_marques"] >= 0 and x["buts_encaisses"] >= 0


# --- Forces en présence -------------------------------------------------------------------------------------------
def table_force(classement: list[dict[str, Any]] | None) -> dict[str, float]:
    """nom normalisé -> force = points par match ÷ moyenne des points par match du classement (équipes ayant joué). {} si pas de classement exploitable."""
    ppm = {norm(r.get("equipe")): r["pts"] / r["j"] for r in classement or [] if isinstance(r.get("j"), int) and r["j"] > 0 and isinstance(r.get("pts"), int)}
    moy = sum(ppm.values()) / len(ppm) if ppm else 0.0
    return {n: v / moy for n, v in ppm.items()} if moy > 0 else {}


def cle_championnat(classements: dict[str, Any], titre: str | None, equipe: str | None = None) -> str | None:
    """Clé du classement national dont le titre (après « pays : ») est EXACTEMENT celui de la rubrique. Plusieurs candidats (ex. « Bundesliga » allemande et autrichienne) :
    on garde celui dont le classement contient l'équipe elle-même ; ambiguïté persistante ou absence = None (jamais deviné)."""
    if not titre:
        return None
    ok = [k for k in classements if not k.startswith("europe") and norm(k.split(":")[-1]) == norm(titre)]
    if len(ok) > 1 and equipe:
        ok = [k for k in ok if any(norm(r.get("equipe")) == norm(equipe) for r in (classements[k].get("resultat") or []))]
    return ok[0] if len(ok) == 1 else None


def poids_adversaire(obs: dict[str, Any], forces: dict[str, float]) -> tuple[float, bool]:
    """(poids, résolu). Adversaire absent du classement de sa compétition : (1.0, False)."""
    f = forces.get(norm(obs.get("adversaire")))
    return (f, True) if f is not None else (1.0, False)


# --- Échantillons -------------------------------------------------------------------------------------------------
def _prend(rows: list[dict[str, Any]], domicile: bool, jour: str, saison: str | None) -> list[dict[str, Any]]:
    out: dict[tuple, dict[str, Any]] = {}
    for x in rows:
        if not _valide(x) or bool(x.get("domicile")) is not domicile or x["date"][:10] >= jour or (saison is not None and x.get("saison") != saison):
            continue
        out.setdefault((x["date"][:10], norm(x.get("adversaire"))), x)          # même match vu par deux sources = une seule observation
    return sorted(out.values(), key=lambda x: (x["date"], norm(x.get("adversaire"))))


def echantillons(m: dict[str, Any], classements: dict[str, Any] | None = None) -> dict[str, Any]:
    """Pour un match de entrees_europe.json : les trois échantillons des deux équipes, avec poids de force des adversaires.
    Retourne {"sources": {nom: {"A": [...], "B": [...], "valide": bool}}, "forces": {...}}. Ne lève rien : la validité est dans le résultat."""
    classements = classements if classements is not None else {}
    jour = str(m["date"])[:10]
    cur, prev = saisons(jour)
    e = m["entree"]
    code = m.get("competition_code")
    f_eu = table_force((classements.get(CLE_CLASSEMENT_EUROPE.get(code, "")) or {}).get("resultat"))
    cote = {}
    for cote_cle, meta, nom in (("dom", m.get("meta_dom") or {}, m.get("domicile")), ("ext", m.get("meta_ext") or {}, m.get("exterieur"))):
        k = cle_championnat(classements, meta.get("championnat_titre"), nom)
        cote[cote_cle] = table_force(((classements.get(k) or {}).get("resultat"))) if k else {}
    brut = {"prec": (_prend(e["europe_dom"], True, jour, prev)[-N_PREC_MAX:], _prend(e["europe_ext"], False, jour, prev)[-N_PREC_MAX:]),
            "champ": (_prend(e["ligue_dom"], True, jour, cur), _prend(e["ligue_ext"], False, jour, cur)),
            "eu": (_prend(e["europe_dom"], True, jour, cur), _prend(e["europe_ext"], False, jour, cur))}
    res: dict[str, Any] = {}
    stats = {"resolus": 0, "neutres": 0}
    for nom, (a, b) in brut.items():
        def pese(rows: list[dict[str, Any]], equipe: str) -> list[dict[str, Any]]:
            out = []
            for x in rows:
                if nom == "champ":
                    forces = cote[equipe]
                elif nom == "eu":
                    forces = f_eu
                else:
                    forces = {}                                             # saison passée : aucun classement conservé, force neutre (affichée)
                w, ok = poids_adversaire(x, forces)
                stats["resolus" if ok else "neutres"] += 1
                out.append({"date": x["date"][:10], "adversaire": x.get("adversaire"), "marques": x["buts_marques"], "encaisses": x["buts_encaisses"],
                            "competition": x.get("competition"), "poids": round(w, 4), "force_resolue": ok})
            return out
        A, B = pese(a, "dom"), pese(b, "ext")
        res[nom] = {"A": A, "B": B, "valide": len(A) >= N_MIN and len(B) >= N_MIN}
    return {"sources": res, "forces": stats}


# --- Cotes ---------------------------------------------------------------------------------------------------------
def _ligne(t: str) -> str:
    return t.replace("_", ".")


def cotes_gamma(odds: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Cotes BetPawa de la collecte Europe (clés plates) -> {groupe: {sélection: cote}} aux noms de marches.CLES. Une clé sans équivalent exact est ignorée, jamais devinée."""
    out: dict[str, dict[str, float]] = {}
    ok = set(M.CLES)

    def put(g: str, s: str, v: Any) -> None:
        if (g, s) in ok and isinstance(v, (int, float)) and not isinstance(v, bool) and v > 1:
            out.setdefault(g, {})[s] = float(v)

    for k, v in (odds or {}).items():
        p = k.split("_")
        if k.startswith("1x2_") and len(p) == 2:
            put("1x2", {"1": "1", "X": "N", "2": "2"}.get(p[1], "?"), v)
        elif k.startswith("dc_") and len(p) == 2:
            put("double_chance", {"1X": "1N", "X2": "N2", "12": "12"}.get(p[1], "?"), v)
        elif k in ("btts_yes", "btts_no"):
            put("btts", "Oui" if k.endswith("yes") else "Non", v)
        elif k in ("clean_home", "clean_away", "clean_home_no", "clean_away_no"):
            put("cages_inviolees_" + ("domicile" if "home" in k else "exterieur"), "non" if k.endswith("_no") else "oui", v)
        elif p[0] in ("over", "under") and len(p) == 3:
            put("over_under_" + p[1] + "." + p[2], "plus" if p[0] == "over" else "moins", v)
        elif p[0] in ("home", "away") and p[1] in ("over", "under") and len(p) == 4:
            put("over_under_" + ("domicile" if p[0] == "home" else "exterieur") + "_" + p[2] + "." + p[3], "plus" if p[1] == "over" else "moins", v)
        elif p[0] == "handicap" and len(p) >= 3:
            ligne, sel = "_".join(p[1:-1]), p[-1]
            if "_" in ligne:
                ligne = ligne.replace("_", ".")
            if "." in ligne:
                put("handicap_" + ligne, {"1": "domicile", "2": "exterieur"}.get(sel, "?"), v)
            else:
                put("handicap_3issues_" + ligne, {"1": "1", "X": "X", "2": "2"}.get(sel, "?"), v)
    return out
