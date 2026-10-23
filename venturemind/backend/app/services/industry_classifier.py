"""Keyword-based industry detection engine.

Given a startup title + description, predict one of the supported industries and
attach a confidence score in [0, 1].

Approach
--------
1. Normalize the text (lowercase, collapse whitespace).
2. For each industry, scan a curated keyword lexicon. Each keyword carries a
   weight: domain-defining terms ("tuition", "telemedicine") weigh more than
   weak/ambiguous ones ("platform", "online"). Keywords are matched on word
   boundaries so "ai" doesn't fire inside "email".
3. Sum the matched weights into a raw score per industry. The argmax is the
   predicted industry.
4. Derive confidence from two independent factors, so it stays honest:
     - margin   = (top - runner_up) / top : how decisively the winner beats the
                  next-best industry. Mixed signals -> low margin.
     - evidence = 1 - exp(-top / k)       : how much absolute keyword evidence we
                  actually found. One weak hit -> low evidence even if unrivaled.
   confidence = FLOOR + (1 - FLOOR) * margin * evidence.

Why not softmax? Softmax compares the winner only against the *other* industries,
so a single unambiguous keyword (rivals all zero) saturates to 1.0 — overconfident.
The margin x evidence form separately punishes "barely any evidence" and "close
call", giving calibrated mid-range scores (~0.9 for a clean match, low for noise).
When nothing matches, top == 0 and confidence is 0.0 — a clear "unsure" signal.
"""
from __future__ import annotations

import asyncio
import math
import re
from dataclasses import dataclass

# Supported industries. Order is the deterministic tie-breaker (first wins).
SUPPORTED_INDUSTRIES = (
    "EdTech",
    "FinTech",
    "HealthTech",
    "AgriTech",
    "SaaS",
    "E-commerce",
)

# Confidence shaping constants.
_CONFIDENCE_FLOOR = 0.15   # a confident, single-industry match never reads as 0
_EVIDENCE_K = 4.0          # raw score at which "evidence" is ~63% saturated

# Weighted keyword lexicon per industry.
#   weight 3 : strong, near-unambiguous signal
#   weight 2 : solid signal
#   weight 1 : weak / supporting signal
_LEXICON: dict[str, dict[str, int]] = {
    "EdTech": {
        "education": 3, "edtech": 3, "learning": 2, "student": 2, "students": 2,
        "tutor": 3, "tutoring": 3, "tuition": 3, "course": 2, "courses": 2,
        "classroom": 2, "curriculum": 3, "teacher": 2, "school": 2, "exam": 2,
        "lms": 3, "e-learning": 3, "skill": 1, "quiz": 2,
    },
    "FinTech": {
        "fintech": 3, "payment": 3, "payments": 3, "banking": 3, "loan": 3,
        "loans": 3, "credit": 2, "investment": 2, "trading": 2, "wallet": 3,
        "lending": 3, "insurance": 2, "finance": 2, "financial": 2, "upi": 3,
        "remittance": 3, "transaction": 2, "crypto": 2, "neobank": 3,
    },
    "HealthTech": {
        "health": 3, "healthtech": 3, "medical": 3, "patient": 3, "patients": 3,
        "doctor": 3, "doctors": 2, "hospital": 3, "clinic": 2, "telemedicine": 3,
        "diagnosis": 3, "therapy": 2, "wellness": 2, "pharmacy": 3, "fitness": 1,
        "healthcare": 3, "appointment": 1, "prescription": 3,
    },
    "AgriTech": {
        "agriculture": 3, "agritech": 3, "farm": 3, "farmer": 3, "farmers": 3,
        "farming": 3, "crop": 3, "crops": 3, "soil": 3, "irrigation": 3,
        "harvest": 2, "livestock": 3, "agronomy": 3, "yield": 1, "pesticide": 3,
        "fertilizer": 3, "cultivation": 2,
    },
    "SaaS": {
        "saas": 3, "subscription": 2, "dashboard": 2, "workflow": 2, "api": 2,
        "automation": 2, "crm": 3, "b2b": 2, "analytics": 2, "integration": 1,
        "cloud": 2, "collaboration": 2, "productivity": 2, "no-code": 2,
        "onboarding": 1, "saas platform": 3,
    },
    "E-commerce": {
        "ecommerce": 3, "e-commerce": 3, "shop": 2, "shopping": 3, "store": 2,
        "cart": 3, "checkout": 3, "marketplace": 3, "retail": 2, "product": 1,
        "products": 1, "order": 1, "orders": 1, "seller": 2, "buyer": 2,
        "delivery": 1, "inventory": 1, "dropshipping": 3,
    },
}


@dataclass(frozen=True)
class ClassificationResult:
    industry: str
    confidence: float
    scores: dict[str, float]  # raw weighted scores per industry (for debugging)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _keyword_pattern(keyword: str) -> re.Pattern[str]:
    # Word-boundary match; supports multi-word and hyphenated keywords.
    return re.compile(rf"(?<!\w){re.escape(keyword)}(?!\w)")


# Pre-compile every keyword pattern once at import time.
_COMPILED: dict[str, list[tuple[re.Pattern[str], int]]] = {
    industry: [(_keyword_pattern(kw), weight) for kw, weight in kws.items()]
    for industry, kws in _LEXICON.items()
}


def classify_industry(title: str, description: str) -> ClassificationResult:
    """Predict the industry for a startup from its title and description.

    Title terms are weighted 2x because a word in the title is a stronger signal
    of intent than the same word buried in the description.
    """
    title_text = _normalize(title)
    body_text = _normalize(description)

    raw_scores: dict[str, float] = {}
    for industry in SUPPORTED_INDUSTRIES:
        score = 0.0
        for pattern, weight in _COMPILED[industry]:
            score += weight * 2 * len(pattern.findall(title_text))  # title boost
            score += weight * len(pattern.findall(body_text))
        raw_scores[industry] = score

    ordered = [raw_scores[i] for i in SUPPORTED_INDUSTRIES]
    # argmax with first-listed industry winning ties (deterministic).
    best_idx = max(range(len(ordered)), key=lambda i: (ordered[i], -i))
    top = ordered[best_idx]
    runner_up = max((s for i, s in enumerate(ordered) if i != best_idx), default=0.0)

    if top == 0.0:
        confidence = 0.0  # no keyword evidence at all -> we are not sure
    else:
        margin = (top - runner_up) / top
        evidence = 1.0 - math.exp(-top / _EVIDENCE_K)
        confidence = _CONFIDENCE_FLOOR + (1.0 - _CONFIDENCE_FLOOR) * margin * evidence

    return ClassificationResult(
        industry=SUPPORTED_INDUSTRIES[best_idx],
        confidence=round(confidence, 2),
        scores=raw_scores,
    )


_CANONICAL_MAP: dict[str, str] = {
    "edtech": "EdTech",
    "education": "EdTech",
    "e-learning": "EdTech",
    "fintech": "FinTech",
    "finance": "FinTech",
    "banking": "FinTech",
    "financial technology": "FinTech",
    "healthtech": "HealthTech",
    "healthcare": "HealthTech",
    "health": "HealthTech",
    "medtech": "HealthTech",
    "agritech": "AgriTech",
    "agriculture": "AgriTech",
    "farming": "AgriTech",
    "saas": "SaaS",
    "b2b saas": "SaaS",
    "software": "SaaS",
    "enterprise software": "SaaS",
    "ecommerce": "E-commerce",
    "e-commerce": "E-commerce",
    "retail": "E-commerce",
    "cleantech": "CleanTech",
    "clean tech": "CleanTech",
    "climate tech": "CleanTech",
    "cybersecurity": "Cybersecurity",
    "cyber security": "Cybersecurity",
    "proptech": "PropTech",
    "real estate": "PropTech",
    "biotech": "BioTech",
    "ai": "AI / ML",
    "ai / ml": "AI / ML",
    "artificial intelligence": "AI / ML",
}


async def detect_industry_with_model_async(title: str, description: str) -> str:
    """Predict the industry for a startup idea using the AI model (LLM with fallback).

    Prompts the configured LLM client to infer the category from the startup title and description.
    Falls back reliably to the rule-based keyword classifier if the LLM is unavailable or fails.
    """
    try:
        from app.services.llm_client import get_llm_client
        llm = get_llm_client()
        if llm and llm.is_available():
            prompt = (
                f"Startup Title: {title}\n"
                f"Startup Description: {description}\n\n"
                f"Identify the primary industry or sector for this startup. "
                f"Standard categories include: EdTech, FinTech, HealthTech, AgriTech, SaaS, E-commerce, CleanTech, AI / ML, Cybersecurity, PropTech, BioTech. "
                f"Respond with ONLY the single industry name (1-2 words). Do not include any explanations or punctuation."
            )
            raw = await llm.generate_text(
                system_instruction="You are an expert venture capital classification model. Return only the concise industry name.",
                user_prompt=prompt,
                temperature=0.1,
            )
            clean = raw.strip().strip("'\"`.,;:").strip()
            clean = re.sub(r"^(?:Industry|Sector|Category)\s*:\s*", "", clean, flags=re.IGNORECASE).strip()
            if clean and len(clean) <= 50:
                low = clean.lower()
                if low in _CANONICAL_MAP:
                    return _CANONICAL_MAP[low]
                return clean.title() if clean.islower() else clean
    except Exception:
        pass

    # Deterministic fallback to keyword classifier
    return classify_industry(title=title, description=description).industry


def detect_industry_with_model(title: str, description: str) -> str:
    """Synchronous helper for model-based industry detection."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, detect_industry_with_model_async(title, description)).result()
    return loop.run_until_complete(detect_industry_with_model_async(title, description))

