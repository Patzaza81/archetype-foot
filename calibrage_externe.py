"""Deuxième calibrage externe d'Archetype Foot.

Cette couche ne calcule aucun pronostic et ne modifie jamais les moteurs.
Elle apprend uniquement à partir des sélections historiques déjà produites
par les moteurs, découvre des configurations observables, puis classe les
candidats actuels selon la robustesse historique de leur configuration.

Principe:
    moteur -> candidats déjà filtrés -> découverte/validation externe -> tickets

Les règles sont temporaires et adaptatives: une configuration reste ACTIVE
tant que son historique récent confirme son avantage. Elle devient DECLINANTE
puis INACTIVE lorsqu'elle cesse de le confirmer. Aucune règle n'est inscrite
manuellement dans le moteur.
"""

from __future__ import annotations

import datetime as dt
import itertools
import math
import re
from collections import defaultdict
from typing import Any, Iterable

MIN_OBS = 40
MIN_RECENT_OBS = 20
RECENT_DAYS = 90
MAX_FEATURES = 3
MIN_RULE_MARGIN = 0.02
PROMISING_MARGIN = 0.01
MIN_LIFT = 0.01
MAX_RULES = 500
ODDS_WIDTH = 0.10
PROB_WIDTH = 0.05
EDGE_WIDTH = 0.05
EDV_WIDTH = 0.05

# Variables de base disponibles dans les archives des moteurs.
BASE_FEATURES = (
    "engine",
    "market",
    "market_family",
    "odds_band",
    "probability_band",
    "edge_band",
    "edv_band",
    "rank",
    "favorite_side",
    "competition",
    "home_team",
    "away_team",
    "robustness",
)

_NUMERIC_CONTEXT_KEYS = {
    "corners", "corners_home", "corners_away", "corners_concedes",
    "cartons", "cartons_jaunes", "cartons_rouges",
    "tirs", "tirs_cadres", "xg", "xg_concede",
}


def _s(x: Any) -> str:
    return " ".join(str(x or "").split()).strip()


def _num(x: Any) -> float | None:
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _wilson_lower(wins: int, n: int, z: float = 1.959963984540054) -> float:
    if n <= 0:
        return 0.0
    p = wins / n
    den = 1.0 + z * z / n
    centre = p + z * z / (2.0 * n)
    spread = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * n)) / n)
    return (centre - spread) / den


def _band(value: float | None, width: float, minimum: float = 0.0) -> str | None:
    if value is None or not math.isfinite(value):
        return None
    lo = math.floor((value - minimum) / width + 1e-9) * width + minimum
    hi = lo + width
    return f"{lo:.2f}-{hi:.2f}"


def _market_family(market: Any) -> str:
    s = _s(market).lower()
    if s.startswith("1x2"):
        return "RESULT"
    if "double chance" in s:
        return "DOUBLE_CHANCE"
    if "btts" in s:
        return "BTTS"
    if "buts" in s or "over_" in s or "under_" in s or "plus de" in s or "moins de" in s:
        return "GOALS"
    if "handicap" in s:
        return "HANDICAP"
    if "corner" in s:
        return "CORNERS"
    if "carton" in s:
        return "CARDS"
    return "AUTRE"


def _rank(record: dict[str, Any]) -> str | None:
    r = _s(record.get("rang")).upper()
    return r if r in {"P1", "P2", "P3"} else None


def _favorite_side(record: dict[str, Any]) -> str:
    """Déduit uniquement un rôle observable; aucune probabilité n'est inventée."""
    market = _s(record.get("marche")).lower()
    if "domicile" in market or market.endswith(" - 1"):
        return "DOMICILE"
    if "exterieur" in market or market.endswith(" - 2"):
        return "EXTERIEUR"
    signal = _s(record.get("signal_direction")).lower()
    if "dom" in signal:
        return "DOMICILE"
    if "ext" in signal:
        return "EXTERIEUR"
    return "INCONNU"


def _context_values(record: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for source_name in ("contexte", "context", "features", "statistiques", "stats"):
        obj = record.get(source_name)
        if isinstance(obj, dict):
            for key, value in obj.items():
                if _s(key).lower() in _NUMERIC_CONTEXT_KEYS:
                    v = _num(value)
                    if v is not None:
                        out[_s(key).lower()] = v
    for key in _NUMERIC_CONTEXT_KEYS:
        if key in record:
            v = _num(record.get(key))
            if v is not None:
                out[key] = v
    return out


def feature_values(record: dict[str, Any]) -> dict[str, str]:
    """Construit les variables discrètes utilisables par la découverte."""
    odds = _num(record.get("cote"))
    p = _num(record.get("probabilite"))
    edge = _num(record.get("edge"))
    edv = _num(record.get("edv"))
    values: dict[str, str] = {
        "engine": _s(record.get("model_version") or record.get("moteur")),
        "market": _s(record.get("marche")).lower(),
        "market_family": _market_family(record.get("marche")),
        "rank": _rank(record) or "INCONNU",
        "favorite_side": _favorite_side(record),
        "competition": _s(record.get("competition") or record.get("championnat") or record.get("ligue") or record.get("league")).lower() or "INCONNUE",
        "home_team": _s(record.get("equipe_dom") or record.get("domicile")).lower() or "INCONNUE",
        "away_team": _s(record.get("equipe_ext") or record.get("exterieur")).lower() or "INCONNUE",
        "robustness": _s(record.get("robustesse") or record.get("niveau")).upper() or "INCONNUE",
    }
    b = _band(odds, ODDS_WIDTH, 1.20)
    if b:
        values["odds_band"] = b
    b = _band(p, PROB_WIDTH)
    if b:
        values["probability_band"] = b
    b = _band(edge, EDGE_WIDTH, -0.10)
    if b:
        values["edge_band"] = b
    b = _band(edv, EDV_WIDTH, 0.0)
    if b:
        values["edv_band"] = b
    for key, value in _context_values(record).items():
        b = _band(value, 1.0)
        if b:
            values[key + "_band"] = b
    return values


def _date(record: dict[str, Any]) -> dt.date | None:
    raw = _s(record.get("date_match") or record.get("date"))[:10]
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        return None


def _resolved_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in records:
        if not isinstance(r, dict):
            continue
        if _s(r.get("categorie")) != "SELECTED":
            continue
        if _s(r.get("resultat_statut")) != "RESOLVED":
            continue
        if _s(r.get("resultat_marche")) not in {"WIN", "LOSS"}:
            continue
        if _num(r.get("cote")) is None:
            continue
        if _date(r) is None:
            continue
        out.append(r)
    return out


def _rule_id(items: tuple[tuple[str, str], ...]) -> str:
    return " + ".join(f"{k}={v}" for k, v in items)


def _rule_matches(rule: dict[str, Any], features: dict[str, str]) -> bool:
    return all(features.get(k) == v for k, v in rule.get("conditions", {}).items())


def _stats(records: list[dict[str, Any]], reference_date: dt.date | None = None) -> dict[str, Any]:
    n = len(records)
    wins = sum(_s(r.get("resultat_marche")) == "WIN" for r in records)
    profit = 0.0
    odds_sum = 0.0
    for r in records:
        o = _num(r.get("cote"))
        if o and o > 1:
            odds_sum += o
            profit += o - 1.0 if _s(r.get("resultat_marche")) == "WIN" else -1.0
    hit = wins / n if n else 0.0
    return {
        "observations": n,
        "gagnes": wins,
        "perdus": n - wins,
        "taux_reussite": round(hit, 6) if n else None,
        "borne_basse_95": round(_wilson_lower(wins, n), 6) if n else None,
        "roi": round(profit / n, 6) if n else None,
        "cote_moyenne": round(odds_sum / n, 4) if n and odds_sum else None,
    }


def _baseline(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        f = feature_values(r)
        groups[(f["engine"], f["market"])] .append(r)
    return {_key: _stats(rows) for _key, rows in groups.items()}


def _recent(records: list[dict[str, Any]], end: dt.date) -> list[dict[str, Any]]:
    start = end - dt.timedelta(days=RECENT_DAYS)
    return [r for r in records if (d := _date(r)) is not None and start <= d <= end]


def _candidate_features(candidate: dict[str, Any]) -> dict[str, str]:
    # Les candidats portent les mêmes noms métier que l'archive, avec quelques
    # alias de sortie des moteurs.
    record = dict(candidate)
    record.setdefault("model_version", candidate.get("moteur"))
    record.setdefault("equipe_dom", candidate.get("domicile"))
    record.setdefault("equipe_ext", candidate.get("exterieur"))
    return feature_values(record)


def discover_rules(records: Iterable[dict[str, Any]], historical_rows: Iterable[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Découvre et valide des règles de 1 à 3 dimensions.

    La recherche est bornée pour éviter l'extraction de coïncidences:
    minimum d'observations, borne Wilson, comparaison au marché/moteur parent,
    puis validation sur les 90 derniers jours.
    """
    hist = _resolved_records(records)
    if not hist:
        return {"version": 2, "statut": "AUCUNE_DONNEE", "rules": [], "compteurs": {}}

    feature_names = [x for x in BASE_FEATURES if x not in {"home_team", "away_team"}]
    # Les équipes exactes sont autorisées seulement en dimension simple ou avec
    # le marché/cote; elles ne peuvent pas former des triples équipe+équipe+...
    rule_specs: list[tuple[str, ...]] = []
    for size in range(1, MAX_FEATURES + 1):
        rule_specs.extend(itertools.combinations(feature_names, size))
    rule_specs.extend([
        # Le championnat est une dimension de contexte prioritaire : une règle
        # championnat+marché+cote doit battre le même marché au niveau global.
        ("competition", "market"),
        ("competition", "market", "odds_band"),
        ("competition", "market", "probability_band"),
        ("competition", "market", "favorite_side"),
        ("market", "odds_band", "home_team"),
        ("market", "odds_band", "away_team"),
        ("market", "odds_band", "favorite_side"),
        ("market", "probability_band", "favorite_side"),
        ("market", "odds_band", "competition"),
    ])

    today = max((_date(r) for r in hist if _date(r)), default=dt.date.today())
    baselines = _baseline(hist)
    discovered: list[dict[str, Any]] = []

    for spec in rule_specs:
        buckets: dict[tuple[tuple[str, str], ...], list[dict[str, Any]]] = defaultdict(list)
        for r in hist:
            f = feature_values(r)
            if any(not f.get(k) for k in spec):
                continue
            conditions = tuple(sorted((k, f[k]) for k in spec))
            buckets[conditions].append(r)
        for conditions, rows in buckets.items():
            if len(rows) < MIN_OBS:
                continue
            key = dict(conditions)
            engine = key.get("engine")
            market = key.get("market")
            parent = baselines.get((engine, market)) if engine and market else None
            st = _stats(rows)
            # Une règle spécifique à un championnat doit démontrer un avantage
            # réel sur son parent global (même moteur + même marché). Sans parent
            # exploitable, elle reste surveillée et ne peut pas être utilisée.
            is_competition_rule = "competition" in key
            if is_competition_rule and parent is None:
                continue
            parent_lower = _num(parent.get("borne_basse_95")) if parent else None
            lift = (st["taux_reussite"] - parent["taux_reussite"]) if parent and parent.get("taux_reussite") is not None else None
            if lift is not None and lift < MIN_LIFT:
                continue
            # Une règle doit avoir une marge réelle au-dessus de l'implicite
            # moyen de ses propres observations, pas seulement une belle moyenne.
            avg_odds = st.get("cote_moyenne")
            implied_rate = 1.0 / avg_odds if avg_odds and avg_odds > 1 else None
            margin = (st["borne_basse_95"] - implied_rate) if implied_rate is not None else None
            if margin is None or margin < MIN_RULE_MARGIN or (st.get("roi") or 0.0) <= 0:
                continue

            recent_rows = _recent(rows, today)
            recent = _stats(recent_rows) if recent_rows else {"observations": 0}
            recent_implied = 1.0 / recent["cote_moyenne"] if recent.get("cote_moyenne") and recent["cote_moyenne"] > 1 else None
            recent_margin = (
                recent.get("borne_basse_95", 0.0) - recent_implied
                if recent.get("observations", 0) and recent_implied is not None else None
            )
            recent_lift = None
            if recent.get("observations", 0) >= MIN_RECENT_OBS and parent:
                # Le contrôle récent doit également rester supérieur au parent.
                recent_lift = recent.get("taux_reussite") - parent.get("taux_reussite") if parent.get("taux_reussite") is not None and recent.get("taux_reussite") is not None else None
            if recent.get("observations", 0) >= MIN_RECENT_OBS and recent_margin is not None and recent_margin >= MIN_RULE_MARGIN and (recent_lift is None or recent_lift >= MIN_LIFT):
                status = "ACTIVE"
            elif recent.get("observations", 0) >= MIN_RECENT_OBS:
                status = "DECLINANTE"
            else:
                status = "SURVEILLER"

            historical = None
            if historical_rows is not None and key.get("market") and key.get("competition"):
                historical = historical_support({"date": today.isoformat(), "marche": key["market"], "competition": key["competition"]}, historical_rows)

            discovered.append({
                "id": _rule_id(conditions),
                "conditions": key,
                "observations": st["observations"],
                "gagnes": st["gagnes"],
                "taux_reussite": st["taux_reussite"],
                "borne_basse_95": st["borne_basse_95"],
                "roi": st["roi"],
                "cote_moyenne": st["cote_moyenne"],
                "marge_vs_implicite": round(margin, 6),
                "lift_vs_parent": round(lift, 6) if lift is not None else None,
                "observations_recentes": recent.get("observations", 0),
                "taux_reussite_recent": recent.get("taux_reussite"),
                "marge_recente_vs_implicite": round(recent_margin, 6) if recent_margin is not None else None,
                "lift_recent_vs_parent": round(recent_lift, 6) if recent_lift is not None else None,
                "statut": status,
                "specificite": len(conditions),
                "historique_saison_precedente": historical,
            })

    # Déduplication par identifiant et priorité: active > surveiller > déclinante.
    priority = {"ACTIVE": 3, "SURVEILLER": 2, "DECLINANTE": 1}
    unique: dict[str, dict[str, Any]] = {}
    for r in discovered:
        old = unique.get(r["id"])
        if old is None or (priority[r["statut"]], r["borne_basse_95"], r["observations"]) > (
            priority[old["statut"]], old["borne_basse_95"], old["observations"]
        ):
            unique[r["id"]] = r
    rules = sorted(
        unique.values(),
        key=lambda r: (
            priority[r["statut"]],
            r["marge_vs_implicite"],
            r.get("lift_vs_parent") if r.get("lift_vs_parent") is not None else -1.0,
            r["borne_basse_95"],
            r["observations"],
        ),
        reverse=True,
    )[:MAX_RULES]

    return {
        "version": 2,
        "statut": "OK",
        "parametres": {
            "observations_min": MIN_OBS,
            "observations_recentes_min": MIN_RECENT_OBS,
            "fenetre_recente_jours": RECENT_DAYS,
            "dimensions_max": MAX_FEATURES,
            "marge_minimale": MIN_RULE_MARGIN,
            "lift_minimal": MIN_LIFT,
        },
        "compteurs": {
            "observations_resolues": len(hist),
            "regles_decouvertes": len(discovered),
            "regles_retenues": len(rules),
            "actives": sum(r["statut"] == "ACTIVE" for r in rules),
            "declinantes": sum(r["statut"] == "DECLINANTE" for r in rules),
            "regles_championnat": sum("competition" in (r.get("conditions") or {}) for r in rules),
            "regles_championnat_actives": sum(r["statut"] == "ACTIVE" and "competition" in (r.get("conditions") or {}) for r in rules),
        },
        "rules": rules,
    }


def _season_code_for_date(value: dt.date | None) -> str | None:
    if value is None:
        return None
    start = value.year if value.month >= 7 else value.year - 1
    return f"{start % 100:02d}{(start + 1) % 100:02d}"


def _previous_season_code(value: dt.date | None) -> str | None:
    current = _season_code_for_date(value)
    if not current:
        return None
    start = 2000 + int(current[:2])
    return f"{(start - 1) % 100:02d}{start % 100:02d}"


def historical_support(candidate: dict[str, Any], rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Mesure un appui de la saison précédente sans créer de fausses sélections.

    Les snapshots Football-Data ne sont jamais considérés comme des sélections
    du moteur : ils servent uniquement de validation historique du championnat
    et du marché. Un historique seul ne peut donc pas activer un candidat.
    """
    target_date = _date(candidate)
    previous = _previous_season_code(target_date)
    market = _s(candidate.get("marche")).lower()
    competition = _s(candidate.get("competition") or candidate.get("championnat") or candidate.get("ligue")).lower()
    if not previous or not market or not competition:
        return {"statut": "INDISPONIBLE", "saison": previous, "observations": 0}

    try:
        from journal.journal_n1 import _norm, _num
        from journal.journal_memoire import evaluer_marche
    except Exception:
        return {"statut": "INDISPONIBLE", "saison": previous, "observations": 0}

    comp_norm = _norm(competition)
    aliases = {comp_norm}
    try:
        from archive_football_data import COMPETITIONS
        for code, pair in COMPETITIONS.items():
            if isinstance(pair, (tuple, list)) and len(pair) > 1:
                if comp_norm in {_norm(pair[0]), _norm(pair[1])}:
                    aliases.add(_norm(code))
    except Exception:
        pass
    values: list[bool] = []
    for row in rows:
        if not isinstance(row, dict) or _s(row.get("saison")) != previous:
            continue
        row_comp = _norm(row.get("competition"))
        # Les snapshots N1 utilisent principalement le code CSV (E0, D1...).
        # On accepte aussi un nom de championnat si un fournisseur l'a déjà normalisé.
        if row_comp and not ({row_comp, _norm(row.get("competition_nom"))} & aliases):
            # Une absence de nom exploitable ne doit jamais être transformée en correspondance.
            continue
        if not row.get("home") or not row.get("away"):
            continue
        result = evaluer_marche(market, row.get("hg"), row.get("ag"))
        if result is not None:
            values.append(bool(result))

    out = {
        "statut": "HISTORIQUE_SEUL" if values else "INDISPONIBLE",
        "saison": previous,
        "observations": len(values),
        "taux_reussite": round(sum(values) / len(values), 6) if values else None,
    }
    # Pour une correspondance équipe/championnat, fournir une seconde mesure
    # utile sans la confondre avec la performance du moteur.
    if values and len(values) >= 20:
        out["niveau"] = "FORT" if out["taux_reussite"] >= 0.65 else "FAIBLE" if out["taux_reussite"] < 0.50 else "NEUTRE"
    else:
        out["niveau"] = "INDICATIF" if values else None
    return out


def apply_rules(candidate: dict[str, Any], intelligence: dict[str, Any]) -> dict[str, Any]:
    """Évalue un candidat sans toucher à sa probabilité moteur."""
    features = _candidate_features(candidate)
    matches = [
        r for r in intelligence.get("rules", [])
        if r.get("statut") == "ACTIVE" and _rule_matches(r, features)
    ]
    if not matches:
        candidate["calibrage_externe"] = {
            "statut": "AUCUN_PATTERN",
            "regles": [],
            "rang": 0,
            "marge": None,
        }
        candidate["calibrage_rang"] = 0
        return candidate

    best = max(
        matches,
        key=lambda r: (
            1 if r.get("statut") == "ACTIVE" else 0,
            r.get("marge_vs_implicite") or -1.0,
            r.get("lift_vs_parent") if r.get("lift_vs_parent") is not None else -1.0,
            r.get("borne_basse_95") or 0.0,
            r.get("observations") or 0,
        ),
    )
    margin = _num(best.get("marge_vs_implicite"))
    lift = _num(best.get("lift_vs_parent"))
    historique = best.get("historique_saison_precedente") or {}
    rank = 3 if historique.get("niveau") == "FORT" else 2
    candidate["calibrage_externe"] = {
        "statut": best.get("statut"),
        "regle": best.get("id"),
        "conditions": best.get("conditions"),
        "observations": best.get("observations"),
        "taux_reussite": best.get("taux_reussite"),
        "borne_basse_95": best.get("borne_basse_95"),
        "roi": best.get("roi"),
        "lift_vs_parent": lift,
        "marge_vs_implicite": margin,
        "regles_compatibles": len(matches),
    }
    candidate["calibrage_rang"] = rank
    candidate["calibrage_marge"] = margin
    candidate["calibrage_lift"] = lift
    candidate["calibrage_historique_niveau"] = (historique or {}).get("niveau")
    candidate["calibrage_historique_taux"] = (historique or {}).get("taux_reussite")
    return candidate


def summarize(intelligence: dict[str, Any]) -> dict[str, Any]:
    rules = intelligence.get("rules") or []
    return {
        "version": intelligence.get("version", 2),
        "statut": intelligence.get("statut"),
        "compteurs": intelligence.get("compteurs", {}),
        "actives": [
            {
                "id": r.get("id"),
                "statut": r.get("statut"),
                "observations": r.get("observations"),
                "taux_reussite": r.get("taux_reussite"),
                "marge_vs_implicite": r.get("marge_vs_implicite"),
                "lift_vs_parent": r.get("lift_vs_parent"),
                "lift_recent_vs_parent": r.get("lift_recent_vs_parent"),
                "conditions": r.get("conditions"),
                "historique_saison_precedente": r.get("historique_saison_precedente"),
            }
            for r in rules if r.get("statut") == "ACTIVE"
        ][:50],
    }
