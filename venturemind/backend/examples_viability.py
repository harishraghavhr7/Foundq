"""Runnable examples for the Startup Viability Scoring Engine (Feature 3).

Run from the backend directory (no server or database needed):

    cd venturemind/backend
    python examples_viability.py

It scores three archetypal startups directly through the pure-logic engine and
prints the full breakdown for each.
"""
from app.services.viability_scorer import ViabilityResult, score_startup

# (label, inputs) for three deliberately different ventures.
EXAMPLES = [
    (
        "A) Hot market, strong product, low risk",
        dict(demand=92, competition=20, scalability=88, innovation=85, risk=12),
    ),
    (
        "B) Real demand but crowded and risky",
        dict(demand=70, competition=85, scalability=60, innovation=40, risk=75),
    ),
    (
        "C) Middling on everything",
        dict(demand=65, competition=55, scalability=60, innovation=55, risk=50),
    ),
]


def render(label: str, inputs: dict[str, float], result: ViabilityResult) -> str:
    lines = [
        "=" * 68,
        label,
        "-" * 68,
        "inputs: " + ", ".join(f"{k}={v}" for k, v in inputs.items()),
        "",
        f"{'factor':<13}{'raw':>6}{'dir':>10}{'adj':>7}{'weight':>8}{'contrib':>9}{'lost':>7}",
    ]
    for f in result.breakdown:
        lines.append(
            f"{f.factor:<13}{f.raw:>6.0f}{f.direction:>10}{f.adjusted:>7.0f}"
            f"{f.weight:>8.2f}{f.contribution:>9.2f}{f.points_lost:>7.2f}"
        )
    lines += [
        "-" * 68,
        f"{'UPSIDE (pre-risk)':<46}{result.upside_score:>9.1f}",
        f"risk={result.risk:.0f}  ->  multiplier ="
        f" 1 - {result.risk_severity}*{result.risk:.0f}/100 = {result.risk_multiplier:.3f}"
        f"   (-{result.risk_discount_points:.1f} pts)",
        "",
        f">>> FINAL SCORE: {result.final_score:.1f}/100   [{result.rating}]",
        f"    {result.summary}",
    ]
    return "\n".join(lines)


def main() -> None:
    for label, inputs in EXAMPLES:
        print(render(label, inputs, score_startup(**inputs)))
    print("=" * 68)


if __name__ == "__main__":
    main()
