from __future__ import annotations

from dataclasses import dataclass


ODDS_MIN = 1.26
ODDS_MAX = 1.74


@dataclass(frozen=True)
class Value:
    market: str
    probability_raw: float
    probability: float
    odds: float
    implied_probability: float
    edge: float
    edv: float
    ev: float
    eligible: bool
    reasons: tuple[str, ...]


def edv_threshold(p: float) -> float | None:
    if p < 0.60:
        return None
    if p < 0.63:
        return 12.0
    if p < 0.67:
        return 10.0
    if p < 0.71:
        return 7.0
    return 5.0


def evaluate(market: str, probability: float, odds: float, *,
             calibrated_probability: float | None = None,
             dispersion: float | None = None) -> Value:
    # CORRECTIF 27/09 : une probabilité exactement 0 (λ nul) est un état dégénéré à REJETER (raison
    # PROBABILITE_DEGENEREE ci-dessous), pas une exception qui faisait planter tout le match.
    # Arrondi flottant des sommes de la matrice (ex. 1,0000000000000002) : ramené dans [0 ; 1], rien de plus.
    if -1e-9 <= probability < 0 or 1 < probability <= 1 + 1e-9:
        probability = min(max(probability, 0.0), 1.0)
    if not 0 <= probability <= 1:
        raise ValueError("PROBABILITE_INVALIDE")
    if odds <= 1:
        raise ValueError("COTE_INVALIDE")

    p = probability if calibrated_probability is None else calibrated_probability
    if not 0 <= p <= 1:
        raise ValueError("PROBABILITE_CALIBREE_INVALIDE")

    reasons: list[str] = []
    threshold = edv_threshold(p)
    implied = 1.0 / odds
    edge = p - implied
    ev = odds * edge
    edv = 100.0 * ev

    if not ODDS_MIN <= odds <= ODDS_MAX:
        reasons.append("COTE_HORS_FENETRE")
    if threshold is None:
        reasons.append("PROBABILITE_INF_60")
    elif edv < threshold:
        reasons.append("EDV_INSUFFISANTE")

    if dispersion is not None:
        if dispersion > 8.0:
            reasons.append("DISPERSION_SUP_8")
        elif dispersion > 5.0 and p < 0.67:
            reasons.append("DISPERSION_5_8_ET_P_INF_67")

    # Une probabilité exactement 0/1 issue d'une distribution dégénérée n'est
    # jamais une preuve de certitude; elle est traitée comme un défaut du
    # régime de données, pas corrigée artificiellement ici.
    if p <= 0.0 or p >= 1.0:
        reasons.append("PROBABILITE_DEGENEREE")

    return Value(
        market, probability, p, float(odds), implied, edge, edv,
        ev, not reasons, tuple(reasons)
    )
