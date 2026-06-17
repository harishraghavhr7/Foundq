"""Market Demand Score engine.

Given four market signals — industry, competitor count, search trend and market
growth — produce a single **Demand Score in [0, 100]** that estimates how
attractive *unmet* demand is for entering or investing in a market.

The model in one line
---------------------
    demand = clamp( (w_trend·T + w_growth·G + w_comp·C) · m_industry , 0, 100 )

where T, G, C are three component sub-scores (each on its own 0–100 scale), the
weights ``w_*`` sum to 1, and ``m_industry`` is a small structural tailwind /
headwind multiplier for the sector. Each piece is deliberately simple and
separately inspectable — the breakdown is returned so a score is never a black
box.

The three component sub-scores
------------------------------
1. **Search trend → T (`trend_score`)**
   ``search_trend`` is read as *momentum*: the percentage change in search
   interest over the trailing window (e.g. +40 = searches up 40%). A logistic
   (sigmoid) transform bounds any input and makes "flat" (0%) read as a neutral
   50, decisive momentum saturate toward 100, and collapse toward 0:
       T = 100 · σ(k_t · (search_trend − mid_t))
   Sigmoid (not linear) so that outliers (a viral +500% spike) can't dominate
   the blend and a steady +30% still scores strongly.

2. **Market growth → G (`growth_score`)**
   ``market_growth`` is read as projected **CAGR (%)**. Same logistic shape, but
   centered on a baseline CAGR so that *average* growth reads ~50 and only
   above-trend growth pushes the score up:
       G = 100 · σ(k_g · (market_growth − mid_g))

3. **Competitor count → C (`competition_score`)**
   Competition is **not monotonic**, so a plain "fewer is better" inverse is
   wrong. We use an inverted-U:
     - *Zero* competitors is not a perfect score — an empty market is often an
       *unproven* one, so C starts at a floor (`UNPROVEN_FLOOR`).
     - C ramps linearly up to 100 at the industry **sweet spot** ``c*`` — enough
       rivals to validate real demand, not enough to crowd it.
     - Past ``c*`` C decays exponentially toward 0, passing through
       `SATURATION_SCORE` exactly at the industry **saturation** count ``S``.

How `industry` is used
----------------------
``industry`` is categorical, so it is a *context modifier*, never an additive
term (adding a category code to a score is meaningless). It selects an
``IndustryProfile`` that supplies: (a) the blend **weights** — which signals
matter most for that sector; (b) the competition **sweet spot / saturation**
reference — "many rivals" means different things in SaaS vs AgriTech; and
(c) the structural **multiplier** — a secular tailwind for sectors with strong
underlying demand. Unknown / free-text industries fall back to a neutral
``_DEFAULT_PROFILE`` so the endpoint never fails on an unrecognized sector.

Every constant below (midpoints, steepness, sweet spots, weights, multipliers)
is a calibration knob, set to a defensible default rather than fitted — tune
against observed outcomes as data accrues.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

# --- Component normalization constants -------------------------------------

# Search-trend logistic: input is % change in search interest.
#   mid_t = 0   -> flat search reads as a neutral 50
#   k_t   = 0.04 -> +25% ≈ 73, +50% ≈ 88, −25% ≈ 27 (a usable spread)
_TREND_MIDPOINT = 0.0
_TREND_STEEPNESS = 0.04

# Market-growth logistic: input is projected CAGR (%).
#   mid_g = 8   -> ~broad-economy CAGR reads as a neutral 50
#   k_g   = 0.08 -> 20% ≈ 72, 30% ≈ 85, 0% ≈ 35, −10% ≈ 19
_GROWTH_MIDPOINT = 8.0
_GROWTH_STEEPNESS = 0.08

# Competition inverted-U anchors (shared across industries).
UNPROVEN_FLOOR = 45.0     # C at 0 competitors: an empty market is unproven, not ideal
SATURATION_SCORE = 25.0   # C exactly at the industry saturation count S

# Input sanity clamps (a market can't lose >100% of search/size).
_MIN_PCT = -100.0
_MAX_PCT = 1000.0

# Score band labels, ascending. Boundaries are inclusive lower bounds.
_BANDS = (
    (0.0, "Very Low"),
    (25.0, "Low"),
    (45.0, "Moderate"),
    (65.0, "High"),
    (85.0, "Very High"),
)


@dataclass(frozen=True)
class IndustryProfile:
    """Per-industry calibration. Weights must sum to 1.0."""

    w_trend: float
    w_growth: float
    w_competition: float
    sweet_spot: float       # competitor count c* scoring the maximum 100
    saturation: float       # competitor count S scoring SATURATION_SCORE
    multiplier: float       # structural demand tailwind/headwind, ~[0.85, 1.15]

    def __post_init__(self) -> None:
        total = self.w_trend + self.w_growth + self.w_competition
        if not math.isclose(total, 1.0, abs_tol=1e-6):
            raise ValueError(f"profile weights must sum to 1.0, got {total}")
        if not self.saturation > self.sweet_spot > 0:
            raise ValueError("require saturation > sweet_spot > 0")


# Industry profiles. Weights reflect which signal dominates demand in each
# sector; sweet_spot/saturation reflect how crowded a market gets before it
# saturates; multiplier reflects secular tailwinds. Keys are matched
# case-insensitively (see _resolve_profile).
_PROFILES: dict[str, IndustryProfile] = {
    #                   trend growth comp  c*    S    mult
    "edtech":     IndustryProfile(0.35, 0.35, 0.30,  8.0, 40.0, 1.00),
    "fintech":    IndustryProfile(0.25, 0.40, 0.35,  6.0, 30.0, 1.08),
    "healthtech": IndustryProfile(0.25, 0.45, 0.30,  6.0, 30.0, 1.10),
    "agritech":   IndustryProfile(0.20, 0.50, 0.30,  4.0, 20.0, 1.05),
    "saas":       IndustryProfile(0.35, 0.30, 0.35, 12.0, 60.0, 1.05),
    "e-commerce": IndustryProfile(0.40, 0.25, 0.35, 10.0, 50.0, 0.98),
}

# Neutral fallback for unknown / free-text industries.
_DEFAULT_PROFILE = IndustryProfile(0.30, 0.40, 0.30, 8.0, 40.0, 1.00)

# Common spellings normalized to the canonical profile keys above.
_INDUSTRY_ALIASES: dict[str, str] = {
    "ecommerce": "e-commerce",
    "e commerce": "e-commerce",
    "health tech": "healthtech",
    "fin tech": "fintech",
    "ed tech": "edtech",
    "agri tech": "agritech",
    "agtech": "agritech",
    "software": "saas",
    "saas platform": "saas",
}


@dataclass(frozen=True)
class DemandScoreResult:
    """Full, inspectable output of the demand model."""

    demand_score: float          # final 0–100 score
    band: str                    # qualitative label (Very Low … Very High)
    industry_matched: str        # canonical profile key used ("e-commerce", "default", …)
    trend_score: float           # component T (0–100)
    growth_score: float          # component G (0–100)
    competition_score: float     # component C (0–100)
    weighted_base: float         # blend before the industry multiplier
    multiplier: float            # industry structural multiplier applied
    weights: dict[str, float] = field(default_factory=dict)


def _sigmoid(x: float) -> float:
    """Numerically stable logistic, returns (0, 1)."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    z = math.exp(x)
    return z / (1.0 + z)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _resolve_profile(industry: str) -> tuple[str, IndustryProfile]:
    """Map a free-text industry to (canonical_key, profile), case-insensitively."""
    key = " ".join((industry or "").lower().split())
    key = _INDUSTRY_ALIASES.get(key, key)
    if key in _PROFILES:
        return key, _PROFILES[key]
    return "default", _DEFAULT_PROFILE


def _trend_score(search_trend: float) -> float:
    pct = _clamp(search_trend, _MIN_PCT, _MAX_PCT)
    return 100.0 * _sigmoid(_TREND_STEEPNESS * (pct - _TREND_MIDPOINT))


def _growth_score(market_growth: float) -> float:
    pct = _clamp(market_growth, _MIN_PCT, _MAX_PCT)
    return 100.0 * _sigmoid(_GROWTH_STEEPNESS * (pct - _GROWTH_MIDPOINT))


def _competition_score(competitor_count: int, profile: IndustryProfile) -> float:
    """Inverted-U: ramp up to 100 at the sweet spot, then decay past it.

    Below c*: linear from UNPROVEN_FLOOR (0 rivals) to 100 (c* rivals).
    Above c*: exponential decay hitting SATURATION_SCORE at S, continuing toward 0.
    """
    c = max(0, competitor_count)
    c_star = profile.sweet_spot
    if c <= c_star:
        return UNPROVEN_FLOOR + (100.0 - UNPROVEN_FLOOR) * (c / c_star)
    # Decay rate λ chosen so score(S) == SATURATION_SCORE exactly.
    lam = math.log(100.0 / SATURATION_SCORE) / (profile.saturation - c_star)
    return _clamp(100.0 * math.exp(-lam * (c - c_star)), 0.0, 100.0)


def _band(score: float) -> str:
    label = _BANDS[0][1]
    for lower, name in _BANDS:
        if score >= lower:
            label = name
    return label


def score_market_demand(
    industry: str,
    competitor_count: int,
    search_trend: float,
    market_growth: float,
) -> DemandScoreResult:
    """Compute the Market Demand Score (0–100) for a market.

    Args:
        industry: sector name (free text; matched case-insensitively, unknown
            sectors use a neutral profile).
        competitor_count: number of known competitors in the market (>= 0).
        search_trend: % change in search interest over the trailing window
            (e.g. 40 = +40%). Negative = declining interest.
        market_growth: projected market CAGR in % (e.g. 18 = 18% per year).

    Returns:
        A DemandScoreResult with the final score, qualitative band, and the
        full component breakdown for transparency.
    """
    matched, profile = _resolve_profile(industry)

    t = _trend_score(search_trend)
    g = _growth_score(market_growth)
    c = _competition_score(competitor_count, profile)

    base = profile.w_trend * t + profile.w_growth * g + profile.w_competition * c
    score = _clamp(base * profile.multiplier, 0.0, 100.0)

    return DemandScoreResult(
        demand_score=round(score, 1),
        band=_band(score),
        industry_matched=matched,
        trend_score=round(t, 1),
        growth_score=round(g, 1),
        competition_score=round(c, 1),
        weighted_base=round(base, 1),
        multiplier=profile.multiplier,
        weights={
            "trend": profile.w_trend,
            "growth": profile.w_growth,
            "competition": profile.w_competition,
        },
    )
