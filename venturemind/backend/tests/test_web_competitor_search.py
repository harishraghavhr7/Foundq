import asyncio
from unittest.mock import AsyncMock, patch

from app.schemas import CompetitorOut
from app.services.web_competitor_search import (
    _clean_company_name,
    _clean_url,
    find_web_competitors,
    find_web_competitors_sync,
)


def test_clean_url():
    assert _clean_url("stripe.com") == "https://stripe.com"
    assert _clean_url("https://plaid.com/about") == "https://plaid.com/about"
    assert _clean_url("") == ""
    assert _clean_url("#") == ""


def test_clean_company_name():
    assert _clean_company_name("Stripe - 2026 Company Profile") == "Stripe"
    assert _clean_company_name("1. Plaid: Overview") == "Plaid"
    assert _clean_company_name("Brex | Official Site") == "Brex"
    assert _clean_company_name("Wise Pricing & Alternatives") == "Wise"


def test_find_web_competitors_fallback_when_empty():
    async def _run():
        with patch("app.services.web_competitor_search.query_live_web", new=AsyncMock(return_value=[])):
            results = await find_web_competitors(
                title="CryptoWallet",
                description="A digital wallet for instant crypto payments and yield generation.",
                industry="FinTech",
                top_k=3,
            )
            assert len(results) == 3
            assert all(isinstance(c, CompetitorOut) for c in results)
            assert any(c.name in ("Stripe", "Plaid", "Brex", "Wise") for c in results)

    asyncio.run(_run())


def test_find_web_competitors_with_mocked_search():
    mock_results = [
        {
            "title": "Jobscan - Resume Optimization Platform",
            "url": "https://www.jobscan.co",
            "content": "Jobscan helps job seekers optimize resumes and cover letters for applicant tracking systems.",
            "score": 0.94,
        },
        {
            "title": "Teal - Career Growth & AI Resume Builder",
            "url": "https://www.tealhq.com",
            "content": "Teal provides an all-in-one job search tracker and AI-driven resume builder.",
            "score": 0.91,
        },
    ]

    async def _run():
        with patch("app.services.web_competitor_search.query_live_web", new=AsyncMock(return_value=mock_results)):
            results = await find_web_competitors(
                title="AI Resume Builder",
                description="An AI resume builder that crafts ATS-optimized resumes.",
                industry="HRTech",
                top_k=2,
            )
            assert len(results) >= 2
            names = [c.name.lower() for c in results]
            assert any("jobscan" in n or "teal" in n for n in names)

    asyncio.run(_run())
