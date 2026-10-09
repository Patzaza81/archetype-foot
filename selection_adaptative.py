from __future__ import annotations

import datetime as dt
import gzip
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from calibrage_externe import apply_rules, discover_rules, summarize as summarize_calibrage
from journal.journal_n1 import charger_n1
import journal_classement as jcl
import journal_regularites as jrg

V2 = "moteur_v2_6_10"
V3 = "moteur_v3"
ENGINES = (V2, V3)

INPUTS = {
    V2: Path("precalcul_leger.json"),
    V3: Path("data/v3/pronostics_v3.json"),
}
FULL_PRECALC = Path("precalcul.json")
JOURNAL = Path("journal.json")
ARCHIVE = Path("archive")
OUT = Path("data/selection_intelligence.json")
CALIBRAGE_OUT = Path("data/calibrage_externe.json")
V3_HISTORY = Path("data/v3/historique_selection.json")
HISTORIQUE = Path("historique_pronostics.json")

ODDS_MIN = 1.26
ODDS_MAX = 3.01
MAX_PER_SOURCE = 10


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists() or not path.stat().st_size:
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def norm(x: Any) -> str:
    return " ".join(str(x or "").split()).strip()


def num(x: Any) -> float | None:
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def implied(odds: float | None) -> float | None:
    return 1.0 / odds if odds and odds > 1 else None


def wilson_lower(wins: int, n: int, z: float = 1.959963984540054) -> float | None:
    if n <= 0:
        return None
    p = wins / n
    den = 1.0 + z * z / n
    centre = p + z * z / (2 * n)
    spread = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return (centre - spread) / den


# Décision de Patrick du 08/10/2026 (test sans cotes sur 48 224 observations équipe×marché, walk-forward) : la borne
# basse de Wilson sous-estimait le Journal (75 % annoncé pour 81 % réel). La probabilité du Journal est désormais la
# fréquence de l'équipe lissée vers la fréquence générale du marché, avec 20 matchs fictifs :
#   p = (réussites + 20 × fréquence_générale) / (matchs + 20)
# Test hors échantillon : à p >= 70 %, 76,6 % annoncé pour 76,9 % réel. Wilson reste calculé (information, classement).
JOURNAL_MATCHS_FICTIFS = 20

# INTERRUPTEUR (exigence non négociable de Patrick, 08/10/2026) : le calibrage du Journal doit pouvoir revenir à sa
# condition initiale (borne de Wilson) sans toucher au code. Fichier config/journal_calibrage.json : {"mode": "lisse"}
# ou {"mode": "wilson"}. Fichier absent, illisible ou mode inconnu : "wilson" (l'état initial, le plus prudent).
JOURNAL_CONFIG = Path("config/journal_calibrage.json")
MODES_JOURNAL = ("lisse", "wilson", "preuves", "regularites")
# Mode « regularites » (journal_regularites.py) : formule simple sans cote ni ROI ; chiffre = taux x réalisme du marché x
# (1 - marge d'erreur) ; indice de constance dès 6 matchs ; probabilité des tickets = taux x réalisme.


def journal_mode(path: Path = JOURNAL_CONFIG) -> str:
    try:
        mode = str(json.loads(path.read_text(encoding="utf-8")).get("mode", "")).strip().lower()
    except (OSError, ValueError, AttributeError):
        return "wilson"
    return mode if mode in MODES_JOURNAL else "wilson"


def journal_probabilite_lissee(wins: int, n: int, base: float | None, m: int = JOURNAL_MATCHS_FICTIFS) -> float | None:
    if n <= 0 or base is None or not 0.0 <= base <= 1.0 or wins < 0 or wins > n:
        return None
    return (wins + m * base) / (n + m)


def market_family(market: str) -> str:
    s = norm(market).lower()
    if s.startswith("1x2"):
        return "RESULT"
    if s.startswith("double chance"):
        return "DOUBLE_CHANCE"
    if "btts" in s:
        return "BTTS"
    if "buts" in s or "plus de" in s or "moins de" in s:
        return "GOALS"
    if "handicap" in s:
        return "HANDICAP"
    if "cage" in s or "encaisse" in s:
        return "DEFENSE"
    return "AUTRE"


def market_key(market: str) -> str:
    return norm(market).lower()


def confidence_tier(n: int, margin: float | None, roi: float | None) -> tuple[str, int]:
    if margin is not None and margin > 0 and roi is not None and roi > 0:
        if n >= 40:
            return "PROUVE", 4
        if n >= 25:
            return "ETABLI", 3
        if n >= 10:
            return "PROMETTEUR", 2
    if n >= 10:
        return "OBSERVE", 1
    return "MODELE_SEUL", 0


def iter_archive_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not ARCHIVE.exists():
        return records
    for path in sorted(ARCHIVE.glob("*.json")):
        raw = load_json(path, [])
        if isinstance(raw, list):
            records.extend(x for x in raw if isinstance(x, dict))
        elif isinstance(raw, dict) and isinstance(raw.get("records"), list):
            records.extend(x for x in raw["records"] if isinstance(x, dict))
    for path in sorted(ARCHIVE.glob("*.json.gz")):
        try:
            with gzip.open(path, "rt", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, list):
                records.extend(x for x in raw if isinstance(x, dict))
        except (OSError, gzip.BadGzipFile, json.JSONDecodeError):
            continue
    return records



def score_history() -> dict[str, tuple[int, int]]:
    out: dict[str, tuple[int, int]] = {}
    hist = load_json(HISTORIQUE, [])
    if not isinstance(hist, list):
        return out
    for day in hist:
        for m in (day.get("matchs") or []) if isinstance(day, dict) else []:
            mid = norm(m.get("match_id"))
            score = norm(m.get("score"))
            if not mid or not score:
                continue
            parts = score.replace(":", "-").split("-")
            if len(parts) != 2:
                continue
            try:
                out[mid] = (int(parts[0]), int(parts[1]))
            except ValueError:
                continue
    return out


def sync_v3_history() -> list[dict[str, Any]]:
    current = load_json(INPUTS[V3], {}) or {}
    existing = load_json(V3_HISTORY, []) or []
    if not isinstance(existing, list):
        existing = []
    index = {norm(x.get("record_id")): x for x in existing if isinstance(x, dict) and norm(x.get("record_id"))}
    scores = score_history()

    try:
        from branchement_moteur import nom_canonique
        from archetype_model.learning.reglement import evaluer_marche
    except Exception:
        nom_canonique = lambda x: x
        evaluer_marche = None

    for signal in current.get("signaux", []) or []:
        if not isinstance(signal, dict):
            continue
        mid = norm(signal.get("match_id"))
        if not mid:
            continue
        block = signal.get(V3) or {}
        for rank in ("P1", "P2", "P3"):
            c = (block.get("selection") or {}).get(rank)
            if not isinstance(c, dict):
                continue
            market = norm(c.get("marche"))
            rid = mid + "|" + market
            rec = index.setdefault(rid, {
                "record_id": rid,
                "match_id": mid,
                "date": norm(signal.get("date")),
                "domicile": norm(signal.get("domicile")),
                "exterieur": norm(signal.get("exterieur")),
                "competition": norm(signal.get("competition")),
                "marche": market,
                "rang": rank,
                "cote": num(c.get("cote")),
                "probabilite": num(c.get("probabilite")),
                "edge": num(c.get("edge")),
                "edv": num(c.get("edv")),
                "resultat_statut": "PENDING",
            })
            if rec.get("resultat_statut") == "RESOLVED":
                continue
            sc = scores.get(mid)
            if not sc:
                continue
            canon = nom_canonique(market)
            result = None
            if evaluer_marche and canon:
                try:
                    result = evaluer_marche(canon, sc[0], sc[1]).statut
                except Exception:
                    result = None
            if result in ("WIN", "LOSS"):
                rec.update({
                    "resultat_statut": "RESOLVED",
                    "resultat_marche": result,
                    "buts_dom": sc[0],
                    "buts_ext": sc[1],
                })
    ordered = sorted(index.values(), key=lambda x: (str(x.get("date")), str(x.get("match_id")), str(x.get("marche"))))
    V3_HISTORY.parent.mkdir(parents=True, exist_ok=True)
    V3_HISTORY.write_text(json.dumps(ordered, ensure_ascii=False, indent=2), encoding="utf-8")
    return ordered

def build_history() -> dict[str, Any]:
    v3_history = sync_v3_history()
    buckets: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"n": 0, "wins": 0, "losses": 0, "profit": 0.0, "odds_sum": 0.0}
    )
    by_engine: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"n": 0, "wins": 0, "losses": 0, "profit": 0.0}
    )

    seen: set[str] = set()
    for r in iter_archive_records():
        if r.get("resultat_statut") != "RESOLVED":
            continue
        if r.get("categorie") != "SELECTED":
            continue
        engine = norm(r.get("model_version"))
        if engine not in ENGINES:
            continue
        rid = norm(r.get("record_id"))
        if rid and rid in seen:
            continue
        if rid:
            seen.add(rid)
        market = norm(r.get("marche"))
        if not market:
            continue
        result = r.get("resultat_marche")
        if result not in ("WIN", "LOSS"):
            continue
        odds = num(r.get("cote"))
        b = buckets[(engine, market_key(market))]
        b["n"] += 1
        b["wins"] += int(result == "WIN")
        b["losses"] += int(result == "LOSS")
        if odds and odds > 1:
            b["odds_sum"] += odds
            b["profit"] += odds - 1 if result == "WIN" else -1.0
        g = by_engine[engine]
        g["n"] += 1
        g["wins"] += int(result == "WIN")
        g["losses"] += int(result == "LOSS")
        if odds and odds > 1:
            g["profit"] += odds - 1 if result == "WIN" else -1.0


    for r in v3_history:
        if r.get("resultat_statut") != "RESOLVED":
            continue
        result = r.get("resultat_marche")
        if result not in ("WIN", "LOSS"):
            continue
        market = norm(r.get("marche"))
        if not market:
            continue
        b = buckets[(V3, market_key(market))]
        b["n"] += 1
        b["wins"] += int(result == "WIN")
        b["losses"] += int(result == "LOSS")
        odds = num(r.get("cote"))
        if odds and odds > 1:
            b["odds_sum"] += odds
            b["profit"] += odds - 1 if result == "WIN" else -1.0
        g = by_engine[V3]
        g["n"] += 1
        g["wins"] += int(result == "WIN")
        g["losses"] += int(result == "LOSS")
        if odds and odds > 1:
            g["profit"] += odds - 1 if result == "WIN" else -1.0

    out: dict[str, Any] = {"par_moteur": {}, "par_marche": {}}
    for engine in ENGINES:
        g = by_engine[engine]
        n = g["n"]
        wins = g["wins"]
        out["par_moteur"][engine] = {
            "observations": n,
            "gagnes": wins,
            "perdus": g["losses"],
            "taux_reussite": round(wins / n, 6) if n else None,
            "borne_basse_95": round(wilson_lower(wins, n), 6) if n else None,
            "roi": round(g["profit"] / n, 6) if n else None,
        }

    for (engine, key), b in sorted(buckets.items()):
        n = b["n"]
        wins = b["wins"]
        roi = b["profit"] / n if n else None
        hit = wins / n if n else None
        out["par_marche"][engine + "|" + key] = {
            "moteur": engine,
            "marche": key,
            "observations": n,
            "gagnes": wins,
            "perdus": b["losses"],
            "taux_reussite": round(hit, 6) if hit is not None else None,
            "borne_basse_95": round(wilson_lower(wins, n), 6) if n else None,
            "roi": round(roi, 6) if roi is not None else None,
            "cote_moyenne": round(b["odds_sum"] / n, 4) if n and b["odds_sum"] else None,
        }
    return out


def extract_engine_candidates(doc: dict[str, Any], engine: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for signal in doc.get("signaux", []) or []:
        if not isinstance(signal, dict):
            continue
        block = signal.get(engine) or {}
        selections = block.get("selection") or {}
        for rank in ("P1", "P2", "P3"):
            c = selections.get(rank)
            if not isinstance(c, dict):
                continue
            odds = num(c.get("cote"))
            p = num(c.get("probabilite"))
            if not odds or odds < ODDS_MIN or odds > ODDS_MAX or not p or not (0 < p < 1):
                continue
            rows.append({
                "source": engine,
                "moteur": engine,
                "rang": rank,
                "match_id": norm(signal.get("match_id")),
                "date": norm(signal.get("date")),
                "heure": norm(signal.get("heure_cameroun") or signal.get("heure")),
                "competition": norm(signal.get("competition")),
                "domicile": norm(signal.get("domicile")),
                "exterieur": norm(signal.get("exterieur")),
                "marche": norm(c.get("marche")),
                "cote": odds,
                "probabilite": p,
                "edge": num(c.get("edge")),
                "edv": num(c.get("edv")),
                "niveau": norm(c.get("niveau")),
                "market_family": norm(c.get("market_family")) or market_family(c.get("marche")),
                "exposure_group": norm(c.get("exposure_group")),
                "justification": (c.get("justification") or {}).get("resume") if isinstance(c.get("justification"), dict) else None,
                "betpawa_url": signal.get("betpawa_url"),
            })
    return rows


def journal_segment_map(journal: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    segments = journal.get("segments") or {}
    for row in segments.get("ligue_marche", []) or []:
        if not isinstance(row, dict):
            continue
        league = norm(row.get("ligue") or row.get("championnat"))
        market = norm(row.get("marche"))
        if league and market:
            out[league.lower() + "|" + market_key(market)] = row
    return out


def _journal_team_market_candidate(row: dict[str, Any], mode: str | None = None,
                                   classement: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Transforme une observation équipe×marché du Journal en opportunité exploitable.

    Le Journal reste indépendant du moteur : sa fréquence est une preuve descriptive,
    jamais une probabilité moteur. Pour les calculs de tickets, la borne de Wilson
    constitue volontairement l'estimation prudente ; la fréquence brute sert au
    classement des opportunités.
    """
    pm = row.get("prochain_match") or {}
    odds = num(pm.get("cote_betpawa"))
    date = norm(pm.get("date"))
    if not date or date < dt.datetime.now().date().isoformat() or not odds or odds <= 1:
        return None
    if odds > ODDS_MAX:
        return None
    wins = int(row.get("gagnes") or 0)
    observations = int(row.get("joues") or 0)
    frequency = num(row.get("frequence"))
    if observations < 5 or frequency is None:
        return None
    lower = wilson_lower(wins, observations)
    base_marche = num(row.get("frequence_generale"))
    mode = mode or journal_mode()
    lissee = journal_probabilite_lissee(wins, observations, base_marche) if mode == "lisse" else None
    p_journal = lissee if lissee is not None else lower
    equipe = norm(row.get("equipe"))
    adversaire = norm(pm.get("adversaire"))
    lieu = norm(pm.get("lieu"))
    if not equipe or not adversaire:
        return None
    if lieu == "domicile":
        domicile, exterieur = equipe, adversaire
    else:
        domicile, exterieur = adversaire, equipe
    market = norm(row.get("marche"))
    q = implied(odds)
    candidat = {
        "source": "journal",
        "moteur": None,
        "rang": None,
        "match_id": None,
        "date": date,
        "heure": norm(pm.get("heure")),
        "competition": norm(row.get("ligue")),
        "domicile": domicile,
        "exterieur": exterieur,
        "marche": market,
        "cote": odds,
        "probabilite": None,
        "probabilite_estimee": round(p_journal, 6) if p_journal is not None else None,
        "probabilite_source": "JOURNAL_LISSE" if lissee is not None else "JOURNAL_WILSON",
        "journal_probabilite_lissee": round(lissee, 6) if lissee is not None else None,
        "journal_calibrage": mode,
        "journal_frequence_generale": base_marche,
        "probabilite_brute_journal": frequency,
        "edge": None,
        "edv": None,
        "niveau": f"FORME_{wins}_SUR_{observations}",
        "market_family": market_family(market),
        "exposure_group": market_family(market),
        "justification": (
            f"{equipe} a réussi ce marché {wins}/{observations} fois "
            f"({frequency:.1%}) ; probabilité estimée "
            + (f"{lissee:.1%} (fréquence lissée vers la fréquence générale du marché {base_marche:.1%})."
               if lissee is not None else f"{lower:.1%} (borne prudente Wilson 95 %, fréquence générale du marché absente).")
        ) if p_journal is not None else None,
        "journal_roi": num(row.get("roi_betpawa")),
        "journal_success_margin": round(p_journal - q, 6) if p_journal is not None and q is not None else None,
        "journal_observations": observations,
        "journal_frequency": frequency,
        "journal_wins": wins,
        "journal_lower_bound": lower,
        "journal_team": equipe,
        "journal_opportunity": True,
        "betpawa_url": pm.get("betpawa_url"),
    }
    if mode == "preuves":
        _applique_preuves(candidat, row, observations, wins, base_marche, classement)
    elif mode == "regularites":
        _applique_regularites(candidat, row, observations, wins, odds, classement)
    return candidat


def _applique_regularites(c: dict[str, Any], row: dict[str, Any], observations: int, wins: int, odds: float,
                          stats: dict[str, Any] | None) -> None:
    """Mode « regularites » : formule simple, sans cote ni ROI.
    chiffre = taux de l'équipe x réalisme du marché x (1 - marge d'erreur) ; probabilité de ticket = taux x réalisme.
    `stats` = journal_regularites.charge_realisme()."""
    marche = c.get("marche") or ""
    realisme, origine = jrg.realisme_pour(marche, stats)
    ok, motifs = jrg.evalue(wins, observations, row.get("gagnes_6"), row.get("joues_6"))
    taux = wins / observations if observations else 0.0
    proba = chif = None
    if realisme is None:
        ok = False
        motifs.append(jrg.MOTIF_REALISME)
    else:
        proba = jrg.probabilite_ticket(taux, realisme)
        chif = jrg.chiffre(taux, observations, realisme)
    c.update({
        "probabilite_source": "JOURNAL_REGULARITE",
        "probabilite_estimee": round(proba, 6) if proba is not None else None,
        "journal_realisme": round(realisme, 6) if realisme is not None else None,
        "journal_realisme_origine": origine,
        "journal_chiffre": round(chif, 6) if chif is not None else None,
        "journal_marge_erreur": round(jrg.marge_erreur(taux, observations), 6),
        "journal_admissible": ok,
        "journal_motifs_rejet": motifs,
        "journal_gagnes_6": row.get("gagnes_6"),
        "journal_joues_6": row.get("joues_6"),
        "journal_indice_constance": jrg.indice_constance(wins, observations, row.get("gagnes_6"), row.get("joues_6")),
        "journal_affichage": f"{wins} sur {observations}",
        "journal_roi": None,
        "journal_success_margin": None,
        "justification": jrg.texte_affichage(c.get("journal_team") or "", wins, observations, row.get("gagnes_6"),
                                             row.get("joues_6"), proba),
    })


def _applique_preuves(c: dict[str, Any], row: dict[str, Any], observations: int, wins: int,
                      base_marche: float | None, classement: dict[str, Any] | None) -> None:
    """Mode « preuves » (journal_classement.py) : la probabilité annoncée est la probabilité CALIBRÉE sur les résultats
    passés du Journal, et le pari n'est admissible que si sa borne basse couvre la probabilité implicite de la cote.
    Sans calibrage (données absentes ou erreur), rien n'est admissible : jamais de pari présenté comme fiable sans preuve."""
    classement = classement or {}
    cal = classement.get("calibrage")
    stab = (classement.get("stabilite") or {}).get((norm(row.get("equipe")), norm(row.get("ligue")), norm(row.get("marche"))))
    lis = jcl.lissee(wins, observations, base_marche)
    ev = jcl.evalue({"cote": c["cote"], "lissee": lis, "joues": observations, "stabilite": stab}, cal)
    q = implied(c["cote"])
    c["probabilite_source"] = "JOURNAL_CALIBRE"
    c["journal_calibrage"] = "preuves"
    c["journal_probabilite_lissee"] = round(lis, 6) if lis is not None else None
    c["journal_admissible"] = bool(ev["admissible"])
    c["journal_motifs_rejet"] = list(ev["motifs"])
    c["journal_stabilite"] = round(stab, 6) if stab is not None else None
    c["journal_borne_basse_calibree"] = round(ev["borne_basse"], 6) if ev["borne_basse"] is not None else None
    if ev["p_cal"] is not None:
        c["probabilite_estimee"] = round(ev["p_cal"], 6)
        c["journal_success_margin"] = round(ev["p_cal"] - q, 6) if q is not None else None
        c["justification"] = (
            f"{c['journal_team']} a réussi ce marché {wins}/{observations} fois ({c['journal_frequency']:.1%}) ; "
            f"probabilité calibrée sur les résultats passés du Journal : {ev['p_cal']:.1%} "
            f"(borne basse {ev['borne_basse']:.1%}) contre {q:.1%} impliquée par la cote."
            if q is not None else None
        )
    else:
        c["journal_success_margin"] = None


DIAGNOSTIC_CLASSEMENT: dict[str, Any] = {}


def resume_classement(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Diagnostic du mode « preuves » : combien de paris du Journal sont admissibles, pourquoi les autres sont rejetés, et
    les rejetés les plus proches du seuil (jamais publiés, seulement pour comprendre)."""
    cj = [x for x in rows if x.get("probabilite_source") == "JOURNAL_CALIBRE"]
    motifs: dict[str, int] = {}
    for x in cj:
        for m in x.get("journal_motifs_rejet") or []:
            motifs[m] = motifs.get(m, 0) + 1
    proches = sorted(
        [x for x in cj if not x.get("journal_admissible") and x.get("journal_borne_basse_calibree") is not None],
        key=lambda x: x["journal_borne_basse_calibree"] - 1.0 / x["cote"], reverse=True)[:5]
    return {
        "candidats": len(cj), "admissibles": sum(1 for x in cj if x.get("journal_admissible")), "motifs_de_rejet": motifs,
        "plus_proches_du_seuil": [
            {"match": f"{x['domicile']} - {x['exterieur']}", "marche": x["marche"], "cote": x["cote"],
             "probabilite_calibree": x.get("probabilite_estimee"), "borne_basse": x["journal_borne_basse_calibree"],
             "probabilite_implicite": round(1.0 / x["cote"], 6)} for x in proches],
    }


def extract_journal_candidates(journal: dict[str, Any], full: dict[str, Any], mode: str | None = None,
                               classement: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Récupère deux formes de valeur du Journal sans dépendre de TOUS_MARCHES_EVALUES.

    1. équipes à suivre : équipe×marché récurrent + prochain match + cote ;
    2. segments championnat×marché : conseil historique directement compatible avec la cote.

    Le premier flux est essentiel : il survit même lorsque precalcul.json est allégé.
    """
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    mode = mode or journal_mode()
    if mode == "regularites" and classement is None:
        classement = jrg.charge_realisme(dt.datetime.now().date().isoformat())
    if mode == "preuves" and classement is None:
        classement = jcl.charge_calibrage(dt.datetime.now().date().isoformat())
    DIAGNOSTIC_CLASSEMENT.clear()
    if mode == "preuves":
        cal = (classement or {}).get("calibrage") or {}
        DIAGNOSTIC_CLASSEMENT.update({
            "observations_calibrage": (classement or {}).get("observations", 0), "pour_le": (classement or {}).get("pour_le"),
            "a": cal.get("a"), "b": cal.get("b"), "c": cal.get("c"), "modele": cal.get("modele"), "n": cal.get("n"),
            "erreur": (classement or {}).get("erreur"),
        })

    if mode == "regularites":
        st = classement or {}
        DIAGNOSTIC_CLASSEMENT.update({
            "mode": "regularites", "cas_passes": (st.get("total") or (0, 0.0, 0))[0],
            "realisme_moyen": jrg.realisme_pour("", st)[0],
            "realisme_par_marche": {m: round(v[2] / v[1], 3) for m, v in (st.get("marches") or {}).items()
                                    if v[0] >= jrg.MIN_CAS_MARCHE and v[1] > 0},
            "erreur": st.get("erreur"),
        })

    for item in journal.get("equipes_a_suivre") or []:
        if not isinstance(item, dict):
            continue
        c = _journal_team_market_candidate(item, mode, classement)
        if not c:
            continue
        key = (
            c["date"],
            c["domicile"].lower() + "|" + c["exterieur"].lower(),
            market_key(c["marche"]),
        )
        if key in seen:
            continue
        seen.add(key)
        rows.append(c)

    if mode == "regularites":
        # Mode « regularites » : seuls les paris équipe×marché passent par les règles. Les segments championnat×marché
        # reposent sur un ROI de segment, exclu de ce mode.
        return rows

    segs = journal_segment_map(journal)
    if not segs:
        return rows

    for signal in full.get("signaux", []) or []:
        if not isinstance(signal, dict):
            continue
        if norm(signal.get("date")) < dt.datetime.now().date().isoformat():
            continue
        league = norm(signal.get("competition"))
        for item in signal.get("TOUS_MARCHES_EVALUES") or []:
            if not isinstance(item, dict):
                continue
            market = norm(item.get("marche"))
            odds = num(item.get("cote_observee"))
            if not market or not odds or odds < ODDS_MIN or odds > ODDS_MAX:
                continue
            seg = segs.get(league.lower() + "|" + market_key(market))
            if not seg or seg.get("statut") not in ("A_JOUER", "A_SURVEILLER"):
                continue
            if seg.get("cote_min") is not None and odds < float(seg["cote_min"]):
                continue
            if seg.get("cote_max") is not None and odds > float(seg["cote_max"]):
                continue
            key = (
                norm(signal.get("match_id")),
                market_key(market),
                "segment",
            )
            if key in seen:
                continue
            seen.add(key)
            roi = num(seg.get("roi"))
            success = num(seg.get("reussite"))
            required = num(seg.get("reussite_necessaire"))
            margin = (success - required) if success is not None and required is not None else None
            rows.append({
                "source": "journal",
                "moteur": None,
                "rang": None,
                "match_id": norm(signal.get("match_id")),
                "date": norm(signal.get("date")),
                "heure": norm(signal.get("heure_cameroun") or signal.get("heure")),
                "competition": league,
                "domicile": norm(signal.get("domicile")),
                "exterieur": norm(signal.get("exterieur")),
                "marche": market,
                "cote": odds,
                "probabilite": None,
                "edge": None,
                "edv": None,
                "niveau": seg.get("statut"),
                "market_family": market_family(market),
                "exposure_group": market_family(market),
                "justification": "Rentabilité historique du même marché dans le même championnat.",
                "journal_roi": roi,
                "journal_success_margin": margin,
                "journal_observations": seg.get("matchs"),
                "journal_segment": True,
                "betpawa_url": signal.get("betpawa_url"),
            })
    return rows

def enrich(candidates: list[dict[str, Any]], history: dict[str, Any], intelligence: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    for c in candidates:
        odds = c.get("cote")
        q = implied(odds)
        c["probabilite_implicite"] = round(q, 6) if q is not None else None
        p = c.get("probabilite")
        c["marge_modele"] = round(p - q, 6) if p is not None and q is not None else None

        key = c.get("moteur") + "|" + market_key(c.get("marche")) if c.get("moteur") else None
        h = history["par_marche"].get(key, {}) if key else {}
        n = int(h.get("observations") or 0)
        lower = num(h.get("borne_basse_95"))
        roi = num(h.get("roi"))
        c["historique_observations"] = n
        c["historique_taux"] = h.get("taux_reussite")
        c["historique_borne_basse_95"] = lower
        c["historique_roi"] = roi
        c["marge_succes"] = (
            round(lower - q, 6)
            if lower is not None and q is not None
            else c.get("journal_success_margin")
        )
        tier, rank = confidence_tier(n, c.get("marge_succes"), roi if roi is not None else c.get("journal_roi"))
        if c.get("source") == "journal":
            if c.get("journal_team"):
                # La fréquence équipe est une preuve descriptive, pas une garantie.
                # On garde le rang de confiance distinct pour ne pas appeler 5/5 « prouvé ».
                tier = f"FORME_{int(c.get('journal_wins') or 0)}_SUR_{int(c.get('journal_observations') or 0)}"
                rank = 3 if int(c.get("journal_observations") or 0) >= 8 else 2
            elif c.get("niveau") == "A_JOUER" and c.get("journal_success_margin") is not None and c["journal_success_margin"] > 0:
                tier, rank = "PROUVE", 4
            elif c.get("niveau") == "A_SURVEILLER":
                tier, rank = "SURVEILLER", 2
        c["niveau_confiance"] = tier
        c["rang_confiance"] = rank

        # Pour les tickets, on n'utilise jamais la fréquence brute comme probabilité.
        # Une équipe 5/5 est donc mise en avant comme preuve, mais son estimation
        # mathématique reste prudente (borne Wilson 95 %).
        p_est = p
        if c.get("probabilite_source") in ("JOURNAL_CALIBRE", "JOURNAL_REGULARITE"):
            p_est = c.get("probabilite_estimee")
        elif c.get("journal_probabilite_lissee") is not None:
            p_est = c["journal_probabilite_lissee"]
            c["probabilite_source"] = "JOURNAL_LISSE"
        elif c.get("journal_lower_bound") is not None:
            p_est = c["journal_lower_bound"]
            c["probabilite_source"] = "JOURNAL_WILSON"
        elif n >= 10 and lower is not None:
            p_est = lower
            c["probabilite_source"] = "HISTORIQUE_MOTEUR_WILSON"
        else:
            c["probabilite_source"] = "MODELE_NON_CALIBRE"
        jm = c.get("journal_success_margin")
        if p_est is None and c.get("source") == "journal" and q is not None and jm is not None:
            p_est = min(0.99, max(0.01, q + jm))
        c["probabilite_estimee"] = round(p_est, 6) if p_est is not None else None
        c["ev_estime"] = round(p_est * odds - 1.0, 6) if p_est is not None and odds else None
        if c.get("probabilite_source") == "JOURNAL_REGULARITE":
            c["ev_estime"] = None   # mode « regularites » : aucun gain espéré
        if intelligence:
            apply_rules(c, intelligence)
        else:
            c.setdefault("calibrage_rang", 0)
            c.setdefault("calibrage_marge", None)
            c.setdefault("calibrage_lift", None)
        rang_p = {"P1": 3, "P2": 2, "P3": 1}.get(norm(c.get("rang")), 0)
        if rang_p == 0 and c.get("source") == "journal":
            rang_p = 2 if c.get("niveau") == "A_JOUER" else 1
        ev = c["ev_estime"]

        # Classement multi-source : la preuve observée passe AVANT le rang P1/P2/P3.
        # Aucun coefficient arbitraire : chaque niveau est une comparaison lexicographique.
        # - Journal équipe : borne Wilson + fréquence + ROI + volume ;
        # - moteur avec historique suffisant : borne Wilson + taux + ROI + volume ;
        # - sinon seulement calibrage externe puis rang/valeur du moteur.
        empirical_lower = c.get("journal_lower_bound")
        empirical_rate = c.get("journal_frequency")
        empirical_roi = c.get("journal_roi")
        empirical_n = int(c.get("journal_observations") or 0)
        if c.get("probabilite_source") == "JOURNAL_CALIBRE":
            # Mode « preuves » : fiabilité démontrée = borne basse calibrée (seulement si admissible), puis probabilité
            # calibrée, puis espérance calibrée. Un pari non admissible n'a aucune preuve : il passe après tous les autres.
            empirical_lower = c.get("journal_borne_basse_calibree") if c.get("journal_admissible") else None
            empirical_rate = c.get("probabilite_estimee")
            empirical_roi = c.get("ev_estime")
        elif c.get("probabilite_source") == "JOURNAL_REGULARITE":
            # Mode « regularites » : aucun ROI dans le classement (borne Wilson, fréquence, volume seulement).
            empirical_roi = None
        elif empirical_lower is None and n >= 10:
            empirical_lower = lower
            empirical_rate = c.get("historique_taux")
            empirical_roi = roi
            empirical_n = n
        sample_rank = 0
        if c.get("source") == V3:
            niveau_v3 = norm(c.get("niveau"))
            sample_rank = {
                "V3_ECHANTILLON_TRES_SOLIDE": 2,
                "V3_ECHANTILLON_SOLIDE": 2,
                "V3_ECHANTILLON_UTILISABLE": 1,
                "V3_ECHANTILLON_FAIBLE": 0,
            }.get(niveau_v3, 0)
        empirical_rank = 3 if empirical_n >= 5 and empirical_lower is not None else sample_rank
        c["preuve_niveau"] = (
            "OBSERVEE"
            if empirical_rank == 3
            else "ECHANTILLON_V3"
            if empirical_rank > 0
            else "MODELE_NON_CALIBRE"
        )
        # Contrat de normalisation : le générateur ne connaît pas la source.
        # Toute différence V2/V3/Journal est résolue ici, avant l'entrée dans le générateur.
        c["selection_evidence_rank"] = empirical_rank
        c["selection_evidence_lower_bound"] = empirical_lower
        c["selection_evidence_rate"] = empirical_rate
        c["selection_evidence_roi"] = empirical_roi
        c["selection_evidence_observations"] = empirical_n
        c["selection_sample_rank"] = sample_rank
        c["selection_rank"] = rang_p
        c["_ordre"] = (
            empirical_rank,
            empirical_lower if empirical_lower is not None else -999.0,
            empirical_rate if empirical_rate is not None else -999.0,
            empirical_roi if empirical_roi is not None else -999.0,
            empirical_n,
            sample_rank,
            int(c.get("calibrage_rang") or 0),
            c.get("calibrage_marge") if c.get("calibrage_marge") is not None else -999.0,
            c.get("calibrage_lift") if c.get("calibrage_lift") is not None else -999.0,
            rang_p,
            ev if ev is not None else -999.0,
            c.get("marge_modele") if c.get("marge_modele") is not None else -999.0,
            c.get("probabilite") if c.get("probabilite") is not None else -999.0,
            c.get("edv") if c.get("edv") is not None else -999.0,
            -float(odds or 99),
            c.get("match_id") or "",
            c.get("marche") or "",
        )
    return candidates


def top_by_source(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {V2: [], V3: [], "journal": []}
    for source in grouped:
        pool = [x for x in rows if x.get("source") == source]
        pool.sort(key=lambda x: x["_ordre"], reverse=True)
        grouped[source] = pool[:MAX_PER_SOURCE]
    return grouped



def advantage_by_market(history: dict[str, Any]) -> dict[str, Any]:
    grouped: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for key, row in (history.get("par_marche") or {}).items():
        grouped[str(row.get("marche") or key)][str(row.get("moteur") or "")] = row
    out: dict[str, Any] = {}
    for market, engines in sorted(grouped.items()):
        a = engines.get(V2)
        b = engines.get(V3)
        if not a or not b or min(int(a.get("observations") or 0), int(b.get("observations") or 0)) < 10:
            out[market] = {"statut": "DONNEES_INSUFFISANTES"}
            continue
        av = (float(a.get("borne_basse_95") or -1), float(a.get("roi") or -1), float(a.get("taux_reussite") or -1))
        bv = (float(b.get("borne_basse_95") or -1), float(b.get("roi") or -1), float(b.get("taux_reussite") or -1))
        if av > bv:
            winner = V2
        elif bv > av:
            winner = V3
        else:
            winner = "EGALITE"
        out[market] = {
            "statut": "COMPARE",
            "meilleur": winner,
            "v2": a,
            "v3": b,
            "critere": "borne basse 95 % > ROI > taux de réussite, avec au moins 10 observations par moteur",
        }
    return out


def evolution(history: dict[str, Any]) -> dict[str, Any]:
    return {
        "moteurs": history.get("par_moteur", {}),
        "marches": history.get("par_marche", {}),
        "avantage_par_marche": advantage_by_market(history),
        "criteres": {
            "marge_succes": "borne basse Wilson 95 % du taux de réussite historique moins probabilité implicite 1/cote (informatif, ne bloque plus la sélection)",
            "marge_modele": "probabilité du moteur moins probabilité implicite 1/cote",
            "priorite": "preuve observée (Journal équipe ou historique moteur) > niveau d'échantillon V3 > calibrage externe > rang P1/P2/P3 > valeur modèle ; une probabilité moteur non calibrée ne peut plus dominer une preuve réelle",
            "odds": [ODDS_MIN, ODDS_MAX],
        },
    }


def main() -> int:
    v2 = load_json(INPUTS[V2], {}) or {}
    v3 = load_json(INPUTS[V3], {}) or {}
    journal = load_json(JOURNAL, {}) or {}
    full = load_json(FULL_PRECALC, {}) or {}
    history = build_history()
    # Deuxième calibrage: apprentissage uniquement sur les sélections déjà produites
    # et résolues par les moteurs. Il ne modifie aucune probabilité ni aucun seuil moteur.
    n1_rows = charger_n1("data/football_data/snapshots")
    intelligence = discover_rules(iter_archive_records(), historical_rows=n1_rows)
    CALIBRAGE_OUT.parent.mkdir(parents=True, exist_ok=True)
    CALIBRAGE_OUT.write_text(json.dumps(intelligence, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = extract_engine_candidates(v2, V2) + extract_engine_candidates(v3, V3)
    rows += extract_journal_candidates(journal, full)
    rows = enrich(rows, history, intelligence)
    if DIAGNOSTIC_CLASSEMENT:
        DIAGNOSTIC_CLASSEMENT.update(resume_classement(rows))
        if DIAGNOSTIC_CLASSEMENT.get("erreur"):
            print("ERREUR calibrage du Journal :", DIAGNOSTIC_CLASSEMENT["erreur"])      # visible dans les journaux du workflow
    sources = top_by_source(rows)

    result = {
        "version": 1,
        "genere_le": dt.datetime.now(dt.timezone.utc).isoformat(),
        "regle": "Les deux moteurs restent autonomes. Le deuxième calibrage intervient uniquement après leurs filtres et trie les candidats selon des configurations historiques découvertes automatiquement. Il ne modifie jamais les probabilités, coefficients ou décisions internes des moteurs.",
        "journal_calibrage": journal_mode(),
        "journal_classement": dict(DIAGNOSTIC_CLASSEMENT),
        "sources": {
            source: {
                "disponibles": len([x for x in rows if x.get("source") == source]),
                "top": items,
                # Tous les candidats de la source, classés : le générateur de tickets fait lui-même le tri final
                # (éligibilité, 10 par source, doublons). `top` reste pour les pages d'affichage.
                "candidats": sorted([x for x in rows if x.get("source") == source], key=lambda x: x["_ordre"], reverse=True),
            }
            for source, items in sources.items()
        },
        "evolution": evolution(history),
        "calibrage_externe": summarize_calibrage(intelligence),
        "opportunites": sorted(
            [
                x for x in rows
                if x.get("journal_opportunity")
                or int(x.get("historique_observations") or 0) >= 5
                or str(x.get("niveau") or "").startswith("V3_ECHANTILLON_")
                or x.get("calibrage_rang")
            ],
            key=lambda x: x["_ordre"],
            reverse=True,
        )[:20],
        "comptage_opportunites": {
            source: sum(1 for x in rows if x.get("source") == source)
            for source in (V2, V3, "journal")
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "v2": len(sources[V2]),
        "v3": len(sources[V3]),
        "journal": len(sources["journal"]),
        "historique_v2": history["par_moteur"].get(V2, {}).get("observations", 0),
        "historique_v3": history["par_moteur"].get(V3, {}).get("observations", 0),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
