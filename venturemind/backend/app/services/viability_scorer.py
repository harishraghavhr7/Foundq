"""Startup Viability Scoring Engine (Feature 3).

Turns five analyst sub-scores — Demand, Competition, Scalability, Innovation and
Risk, each in [0, 100] — into a single **Startup Viability Score** in [0, 100],
plus a fully itemized breakdown explaining how every input moved the result.

Model
-----
The score is *not* a flat average of the five inputs. It is built in two stages
that mirror how a VC actually underwrites a deal: first size the upside, then
discount it for risk.

1. Normalize direction. Three inputs are "more is better" (Demand, Scalability,
   Innovation). Competition is supplied as market *intensity / saturation* (more
   rivals = harder), so we flip it into *competitive favorability*:
       favorability = 100 - competition
   These four are the **upside factors**, all now on a higher-is-better scale.

2. Weighted upside. Combine the four upside factors with weights that sum to 1:
       upside = Σ wᵢ · adjustedᵢ                         (∈ [0, 100])
   The weights encode how much each lever drives venture-scale returns (below).

3. Risk discount. Risk is supplied as overall risk (more = worse) and is applied
   as a *multiplicative* discount rather than another additive term:
       risk_multiplier = 1 - λ · (risk / 100)            (λ = risk severity)
       final = upside · risk_multiplier                  (∈ [0, 100])

Why multiply risk instead of adding it? If risk were just a sixth weighted term,
a venture with flawless fundamentals could only ever shed ~w_risk·100 points to
risk — so a near-fatal venture (risk = 100) would still score ~80. Investors do
not think that way. Multiplication makes risk a *gate*: it scales the entire
upside, so at λ = 0.5 maximum risk halves an otherwise perfect venture instead
of merely nicking it. Demand sets the ceiling; risk decides how much survives.

Weightage (defaults, sum = 1.0 over the upside factors)
-------------------------------------------------------
  Demand        0.35  — the single largest predictor. No market, no company:
                        a great team in a tiny market still loses.
  Scalability   0.25  — VC needs power-law outcomes; non-scalable models cap return.
  Innovation    0.20  — differentiation / moat; defensibility of the upside.
  Competition   0.20  — favorability of the landscape; a crowded market taxes CAC,
                        margins and growth even when demand is strong.
  (Risk is not in this sum — it acts as the λ = 0.5 multiplier described above.)

The model is intentionally conservative: because risk *discounts* the upside,
mediocre-everything ventures screen out, which is the point of a VC filter. All
weights and λ are configurable via ``ScoringConfig`` and validated so the output
is always a well-formed score in [0, 100].
"""
from __future__ import annotations

from dataclasses import dataclass, field

# --- Directionality --------------------------------------------------------
# "positive": higher raw input is better, used as-is.
# "inverse" : higher raw input is worse, adjusted = 100 - raw.
_POSITIVE = "positive"
_INVERSE = "inverse"

# The four upside factors and how each maps onto a higher-is-better scale.
UPSIDE_DIRECTIONS: dict[str, str] = {
    "demand": _POSITIVE,
    "scalability": _POSITIVE,
    "innovation": _POSITIVE,
    "competition": _INVERSE,
}

# House-view default weights over the upside factors (must sum to 1.0).
DEFAULT_WEIGHTS: dict[str, float] = {
    "demand": 0.35,
    "scalability": 0.25,
    "innovation": 0.20,
    "competition": 0.20,
}

# λ: fraction of the upside removed when risk = 100. 0.5 => max risk halves it.
DEFAULT_RISK_SEVERITY = 0.5

# Display labels for the five inputs.
FACTOR_LABELS: dict[str, str] = {
    "demand": "Demand",
    "scalability": "Scalability",
    "innovation": "Innovation",
    "competition": "Competition",
    "risk": "Risk",
}

# Rating bands: (inclusive lower bound, label), evaluated high -> low.
RATING_BANDS: tuple[tuple[float, str], ...] = (
    (80.0, "Highly Viable"),
    (65.0, "Viable"),
    (50.0, "Moderate"),
    (35.0, "Weak"),
    (0.0, "Not Viable"),
)

# Every input must be present and live in this closed range.
_INPUT_KEYS: tuple[str, ...] = ("demand", "competition", "scalability", "innovation", "risk")


@dataclass(frozen=True)
class ScoringConfig:
    """Tunable model parameters. Defaults are the house view.

    Validated on construction so a misconfigured model can never silently emit
    an out-of-range score.
    """

    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    risk_severity: float = DEFAULT_RISK_SEVERITY

    def __post_init__(self) -> None:
        if set(self.weights) != set(UPSIDE_DIRECTIONS):
            raise ValueError(
                f"weights must cover exactly {sorted(UPSIDE_DIRECTIONS)}, "
                f"got {sorted(self.weights)}"
            )
        if any(w < 0 for w in self.weights.values()):
            raise ValueError("weights must be non-negative")
        total = sum(self.weights.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"upside weights must sum to 1.0, got {total:.4f}")
        if not 0.0 <= self.risk_severity <= 1.0:
            raise ValueError(f"risk_severity (λ) must be in [0, 1], got {self.risk_severity}")


DEFAULT_CONFIG = ScoringConfig()


@dataclass(frozen=True)
class FactorScore:
    """One upside factor's contribution to the score."""

    factor: str             # display label, e.g. "Demand"
    raw: float              # the analyst input in [0, 100]
    direction: str          # "positive" | "inverse"
    adjusted: float         # higher-is-better value (raw, or 100 - raw if inverse)
    weight: float           # share of the upside
    contribution: float     # weight * adjusted  -> points of upside earned
    max_contribution: float # weight * 100        -> best this factor could add
    points_lost: float      # max_contribution - contribution -> headroom left


@dataclass(frozen=True)
class ViabilityResult:
    """Full, explainable result of one scoring run."""

    final_score: float            # the 0-100 Startup Viability Score
    rating: str                   # band label, e.g. "Viable"
    upside_score: float           # weighted upside before the risk discount
    risk: float                   # raw risk input
    risk_severity: float          # λ used
    risk_multiplier: float        # 1 - λ * risk/100
    risk_discount_points: float   # upside_score - final_score (points risk removed)
    breakdown: tuple[FactorScore, ...]
    summary: str                  # one-line human-readable takeaway


def rating_for(score: float) -> str:
    """Map a 0-100 score to its band label."""
    for lower, label in RATING_BANDS:
        if score >= lower:
            return label
    return RATING_BANDS[-1][1]  # 0.0 bound makes this unreachable, kept for safety


def _validate_inputs(values: dict[str, float]) -> None:
    missing = [k for k in _INPUT_KEYS if k not in values]
    if missing:
        raise ValueError(f"missing required scores: {missing}")
    for key in _INPUT_KEYS:
        value = values[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{key} must be a number, got {type(value).__name__}")
        if not 0.0 <= float(value) <= 100.0:
            raise ValueError(f"{key} must be in [0, 100], got {value}")


def _summarize(
    factors: list[FactorScore],
    upside: float,
    final: float,
    rating: str,
) -> str:
    """Build a one-line VC takeaway: strongest lever and biggest drag."""
    driver = max(factors, key=lambda f: f.contribution)
    risk_loss = upside - final
    upside_drag = max(factors, key=lambda f: f.points_lost)
    if risk_loss >= upside_drag.points_lost:
        drag = f"risk (-{risk_loss:.1f} pts)"
    else:
        drag = f"{upside_drag.factor.lower()} (-{upside_drag.points_lost:.1f} pts)"
    return (
        f"{rating}: {final:.1f}/100. "
        f"Strongest lever: {driver.factor.lower()} (+{driver.contribution:.1f}). "
        f"Biggest drag: {drag}."
    )


def score_startup(
    demand: float,
    competition: float,
    scalability: float,
    innovation: float,
    risk: float,
    config: ScoringConfig = DEFAULT_CONFIG,
) -> ViabilityResult:
    """Compute the Startup Viability Score and a full breakdown.

    Args:
        demand: market pull / demand strength, [0, 100], higher is better.
        competition: market intensity / saturation, [0, 100], higher is worse.
        scalability: ability to scale efficiently, [0, 100], higher is better.
        innovation: differentiation / moat, [0, 100], higher is better.
        risk: overall venture risk, [0, 100], higher is worse.
        config: weights and risk severity (defaults to the house view).

    Returns:
        A ``ViabilityResult`` with the final 0-100 score, rating band, the
        pre-risk upside, the risk discount, and a per-factor breakdown.
    """
    raw: dict[str, float] = {
        "demand": float(demand),
        "competition": float(competition),
        "scalability": float(scalability),
        "innovation": float(innovation),
        "risk": float(risk),
    }
    _validate_inputs(raw)

    factors: list[FactorScore] = []
    upside = 0.0
    # Order the breakdown by weight (most influential first) for readability.
    for key in sorted(UPSIDE_DIRECTIONS, key=lambda k: config.weights[k], reverse=True):
        direction = UPSIDE_DIRECTIONS[key]
        value = raw[key]
        adjusted = value if direction == _POSITIVE else 100.0 - value
        weight = config.weights[key]
        contribution = weight * adjusted
        upside += contribution
        factors.append(
            FactorScore(
                factor=FACTOR_LABELS[key],
                raw=round(value, 2),
                direction=direction,
                adjusted=round(adjusted, 2),
                weight=round(weight, 4),
                contribution=round(contribution, 2),
                max_contribution=round(weight * 100.0, 2),
                points_lost=round(weight * (100.0 - adjusted), 2),
            )
        )

    risk_multiplier = 1.0 - config.risk_severity * (raw["risk"] / 100.0)
    final = upside * risk_multiplier
    rating = rating_for(final)

    return ViabilityResult(
        final_score=round(final, 1),
        rating=rating,
        upside_score=round(upside, 1),
        risk=round(raw["risk"], 2),
        risk_severity=config.risk_severity,
        risk_multiplier=round(risk_multiplier, 4),
        risk_discount_points=round(upside - final, 1),
        breakdown=tuple(factors),
        summary=_summarize(factors, upside, final, rating),
    )
