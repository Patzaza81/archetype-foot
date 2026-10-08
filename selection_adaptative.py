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


def extract_journal_candidates(journal: dict[str, Any], full: dict[str, Any]) -> list[dict[str, Any]]:
    segs = journal_segment_map(journal)
    if not segs:
        return []
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
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
            key = (norm(signal.get("match_id")), market_key(market))
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
        c["marge_succes"] = round(lower - q, 6) if lower is not None and q is not None else c.get("journal_success_margin")
        tier, rank = confidence_tier(n, c.get("marge_succes"), roi if roi is not None else c.get("journal_roi"))
        if c.get("source") == "journal":
            if c.get("niveau") == "A_JOUER" and c.get("journal_success_margin") is not None and c["journal_success_margin"] > 0:
                tier, rank = "PROUVE", 4
            elif c.get("niveau") == "A_SURVEILLER":
                tier, rank = "SURVEILLER", 2
        c["niveau_confiance"] = tier
        c["rang_confiance"] = rank

        # Valeur estimée du choix, indépendante de l'historique : les moteurs font déjà
        # le tri, l'historique n'est conservé qu'à titre d'information.
        p_est = p
        jm = c.get("journal_success_margin")
        if p_est is None and c.get("source") == "journal" and q is not None and jm is not None:
            p_est = min(0.99, max(0.01, q + jm))
        c["probabilite_estimee"] = round(p_est, 6) if p_est is not None else None
        c["ev_estime"] = round(p_est * odds - 1.0, 6) if p_est is not None and odds else None
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

        # Classement déterministe : rang choisi par le moteur (P1 > P2 > P3), puis valeur
        # estimée (probabilité × cote − 1), puis avantage propre au modèle, probabilité et EDV.
        # Aucun coefficient arbitraire ne mélange ces grandeurs ; l'historique ne bloque rien.
        c["_ordre"] = (
            c.get("calibrage_rang", 0),
            c.get("calibrage_marge") if c.get("calibrage_marge") is not None else -999.0,
            c.get("calibrage_lift") if c.get("calibrage_lift") is not None else -999.0,
            rang_p,
            ev if ev is not None else -999.0,
            c.get("marge_modele") if c.get("marge_modele") is not None else -999.0,
            c.get("probabilite") if c.get("probabilite") is not None else -999.0,
            c.get("edv") if c.get("edv") is not None else -999.0,
            n,
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
            "priorite": "rang du moteur (P1 > P2 > P3) > valeur estimée (probabilité × cote − 1) > avantage modèle > probabilité > EDV ; l'historique ne sert plus qu'à départager",
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
    sources = top_by_source(rows)

    result = {
        "version": 1,
        "genere_le": dt.datetime.now(dt.timezone.utc).isoformat(),
        "regle": "Les deux moteurs restent autonomes. Le deuxième calibrage intervient uniquement après leurs filtres et trie les candidats selon des configurations historiques découvertes automatiquement. Il ne modifie jamais les probabilités, coefficients ou décisions internes des moteurs.",
        "sources": {
            source: {"disponibles": len([x for x in rows if x.get("source") == source]), "top": items}
            for source, items in sources.items()
        },
        "evolution": evolution(history),
        "calibrage_externe": summarize_calibrage(intelligence),
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
