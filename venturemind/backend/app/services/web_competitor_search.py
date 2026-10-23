"""Live Web Search Competitor Discovery Service.

Replaces static/RAG vector lookups with live web search intelligence (Tavily Search + LLM Synthesis).
Given a startup title, description, and industry, this service searches the live web for actual
direct competitors, alternatives, and market players, extracting structured competitor profiles.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.schemas import CompetitorOut
from app.services.llm_client import FallbackLLMClient, extract_json_payload

logger = logging.getLogger("venturemind.web_competitors")


def _clean_url(raw_url: str | None) -> str:
    """Ensure a valid, absolute URL."""
    if not raw_url:
        return ""
    url = raw_url.strip()
    if not url or url == "#":
        return ""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    try:
        parsed = urlparse(url)
        if parsed.netloc:
            return url
    except Exception:
        pass
    return url


def _clean_company_name(raw_name: str) -> str:
    """Clean company names from common web search prefixes or suffixes."""
    name = raw_name.strip()
    # Strip leading numbering like "1. Plaid"
    name = re.sub(r"^\d+[\.\)]\s*", "", name).strip()
    # Strip suffixes like " - 2026 Company Profile", " | Official Site", ": Overview"
    name = re.sub(r"\s*[-|–—:]\s*(?:\d{4}\s+)?(?:Company Profile|Official Site|Overview|Reviews|Competitors|Alternatives|Pricing|Crunchbase|Tracxn|G2|Product Hunt).*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+(?:Pricing|Alternatives|Reviews|Competitors|Overview)\b.*", "", name, flags=re.IGNORECASE)
    # Strip leading bullets or punctuation
    name = re.sub(r"^[\d\.\-\•\*\s]+", "", name).strip()
    return name.strip() or raw_name.strip()


async def query_live_web(query: str, max_results: int = 6) -> list[dict[str, Any]]:
    """Query live web search using Tavily API, with fallback handling."""
    tavily_key = (settings.tavily_api_key or "").strip()
    if not tavily_key:
        logger.warning("Tavily API key not configured; skipping live web query.")
        return []

    try:
        headers = {
            "Authorization": f"Bearer {tavily_key}",
            "User-Agent": "VentureMind/1.0 (Live Competitor Discovery)",
            "Content-Type": "application/json",
        }
        payload = {
            "api_key": tavily_key,
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_answer": True,
            "topic": "general",
        }
        async with httpx.AsyncClient(timeout=12.0, headers=headers) as client:
            res = await client.post("https://api.tavily.com/search", json=payload)
            if res.status_code == 200:
                data = res.json()
                results = data.get("results", [])
                logger.info("Tavily search retrieved %d live results for '%s'", len(results), query)
                return results
            logger.warning("Tavily search API returned HTTP %d: %s", res.status_code, res.text[:200])
    except Exception as exc:
        logger.warning("Tavily search API request failed for '%s': %s", query, exc)

    return []


def _extract_from_snippets_heuristic(
    results: list[dict[str, Any]], industry: str, top_k: int
) -> list[CompetitorOut]:
    """Fallback extraction directly from web search snippets without LLM."""
    competitors: list[CompetitorOut] = []
    seen_names = set()

    for r in results:
        raw_title = str(r.get("title") or "").strip()
        url = _clean_url(r.get("url"))
        raw_content = str(r.get("content") or "").strip()
        cleaned_name = _clean_company_name(raw_title)

        if not cleaned_name or cleaned_name.lower() in seen_names:
            continue
        # Skip generic aggregator titles
        if any(agg in cleaned_name.lower() for agg in ["best", "top 10", "top 20", "alternatives to", "competitors"]):
            # If domain can give a name:
            if url:
                domain_parts = urlparse(url).netloc.split(".")
                domain_name = domain_parts[0] if domain_parts[0] != "www" else (domain_parts[1] if len(domain_parts) > 1 else "")
                if domain_name and domain_name.lower() not in ["g2", "capterra", "tracxn", "crunchbase", "reddit", "youtube"]:
                    cleaned_name = domain_name.capitalize()
                else:
                    continue
            else:
                continue

        seen_names.add(cleaned_name.lower())
        desc = raw_content[:240] + ("..." if len(raw_content) > 240 else "")
        score = float(r.get("score") or 0.85)
        competitors.append(
            CompetitorOut(
                startup_name=cleaned_name,
                name=cleaned_name,
                industry=industry,
                description=desc,
                website=url or "https://www.google.com",
                country="Global",
                similarity=round(min(1.0, max(0.0, score)), 2),
            )
        )
        if len(competitors) >= top_k:
            break

    return competitors


async def find_web_competitors(
    title: str,
    description: str,
    industry: str | None = None,
    top_k: int = 4,
) -> list[CompetitorOut]:
    """Find direct competitors using live web search and structured LLM extraction.

    Args:
        title: Idea / startup title.
        description: Problem / product summary.
        industry: Optional industry or category.
        top_k: Target number of competitor profiles to return (default: 4).

    Returns:
        list[CompetitorOut]: Structured competitor records with name, industry,
        description, website, and country.
    """
    clean_title = (title or "").strip()
    clean_desc = (description or "").strip()
    sector = (industry or "Technology").strip()

    # Formulate targeted competitor discovery query
    search_query = f"{clean_title} {sector} competitors alternatives startups companies products"

    # Step 1: Query live web
    search_results = await query_live_web(search_query, max_results=max(top_k * 2, 6))

    # If initial specific search was sparse, run broader keyword search
    if len(search_results) < 2 and clean_desc:
        short_desc = clean_desc[:100]
        broader_query = f"top competitors and alternatives for {short_desc}"
        supp_results = await query_live_web(broader_query, max_results=5)
        search_results.extend(supp_results)

    # Step 2: Use LLM to extract and synthesize structured competitor entities
    if search_results:
        snippets = "\n".join(
            [
                f"- Title: {r.get('title')}\n  URL: {r.get('url')}\n  Snippet: {r.get('content')}"
                for r in search_results
            ]
        )
        prompt = (
            f"Startup Idea: \"{clean_title}\"\n"
            f"Industry / Category: {sector}\n"
            f"Description: {clean_desc}\n\n"
            f"Live Web Search Results:\n{snippets}\n\n"
            f"From the live web search findings above, identify {top_k} distinct real competitors, "
            f"established companies, or market alternatives in this space.\n"
            f"For each competitor, provide:\n"
            f"- name: Exact company / startup / product name\n"
            f"- industry: Sector / category\n"
            f"- description: 1-2 sentence description of what they do and their core value proposition\n"
            f"- website: Official website URL (use verified URL from search results if possible)\n"
            f"- country: Headquarters country (or 'United States', 'Global', etc.)\n"
            f"- similarity: Relevance score from 0.70 to 0.99\n\n"
            f"Output strictly a JSON array of objects conforming to the fields above. Do not include markdown codeblocks."
        )

        try:
            llm = FallbackLLMClient()
            if llm.is_available():
                raw_text = await llm.generate_text(
                    system_instruction="You are an expert venture capital market intelligence analyst. Output strictly a JSON array without markdown formatting.",
                    user_prompt=prompt,
                    temperature=0.2,
                )
                clean_json = extract_json_payload(raw_text)
                parsed = json.loads(clean_json)

                if isinstance(parsed, list) and len(parsed) > 0:
                    competitors: list[CompetitorOut] = []
                    for item in parsed[:top_k]:
                        name = str(item.get("name") or item.get("startup_name") or "Competitor").strip()
                        comp_ind = str(item.get("industry") or sector).strip()
                        comp_desc = str(item.get("description") or "").strip()
                        comp_web = _clean_url(item.get("website"))
                        comp_country = str(item.get("country") or "Global").strip()
                        try:
                            sim = float(item.get("similarity", 0.88))
                            sim = round(min(1.0, max(0.0, sim)), 2)
                        except (ValueError, TypeError):
                            sim = 0.88

                        competitors.append(
                            CompetitorOut(
                                startup_name=name,
                                name=name,
                                industry=comp_ind,
                                description=comp_desc,
                                website=comp_web or "https://www.google.com",
                                country=comp_country,
                                similarity=sim,
                            )
                        )

                    if len(competitors) >= 2:
                        logger.info("Successfully synthesized %d competitors from web search", len(competitors))
                        return competitors
        except Exception as exc:
            logger.warning("LLM competitor extraction failed, falling back to heuristic extraction: %s", exc)

        # Fallback to direct snippet heuristic extraction
        heuristic_comps = _extract_from_snippets_heuristic(search_results, industry=sector, top_k=top_k)
        if heuristic_comps:
            return heuristic_comps

    # Step 3: Resilient offline / zero-result fallback generator
    logger.info("Using curated market intel fallback for sector '%s'", sector)
    return _generate_fallback_competitors(clean_title, sector, top_k)


def _generate_fallback_competitors(title: str, industry: str, top_k: int) -> list[CompetitorOut]:
    """Deterministic, high-quality sector comps when search returns empty or unconfigured."""
    ind_lower = industry.lower()
    if any(k in ind_lower for k in ["fintech", "finance", "payment", "bank", "credit", "lending"]):
        comps = [
            CompetitorOut(startup_name="Stripe", name="Stripe", industry="FinTech", description="Global financial infrastructure and payment processing platform powering online businesses.", website="https://stripe.com", country="United States", similarity=0.92),
            CompetitorOut(startup_name="Plaid", name="Plaid", industry="FinTech", description="Data network connecting consumer bank accounts to financial applications and fintech services.", website="https://plaid.com", country="United States", similarity=0.88),
            CompetitorOut(startup_name="Brex", name="Brex", industry="FinTech", description="AI-powered corporate cards, spend management, and corporate banking solutions for modern enterprises.", website="https://brex.com", country="United States", similarity=0.85),
            CompetitorOut(startup_name="Wise", name="Wise", industry="FinTech", description="Cross-border payment infrastructure and multi-currency accounts offering real-time low-fee FX.", website="https://wise.com", country="United Kingdom", similarity=0.84),
        ]
    elif any(k in ind_lower for k in ["edtech", "education", "tutor", "learn", "course"]):
        comps = [
            CompetitorOut(startup_name="Duolingo", name="Duolingo", industry="EdTech", description="Gamified language and subject learning platform using adaptive AI personalization.", website="https://duolingo.com", country="United States", similarity=0.91),
            CompetitorOut(startup_name="Coursera", name="Coursera", industry="EdTech", description="Global online learning platform partnering with universities to offer degrees and certifications.", website="https://coursera.org", country="United States", similarity=0.87),
            CompetitorOut(startup_name="Quizlet", name="Quizlet", industry="EdTech", description="AI-assisted study tools, digital flashcards, and practice tests used by millions of students.", website="https://quizlet.com", country="United States", similarity=0.86),
            CompetitorOut(startup_name="Speak", name="Speak", industry="EdTech", description="Voice-first AI conversational tutor helping learners practice speaking in real-time.", website="https://speak.com", country="United States", similarity=0.84),
        ]
    elif any(k in ind_lower for k in ["health", "medical", "clinic", "patient", "telemedicine"]):
        comps = [
            CompetitorOut(startup_name="Teladoc Health", name="Teladoc Health", industry="HealthTech", description="Virtual care and telemedicine platform offering on-demand medical and mental health consults.", website="https://teladoc.com", country="United States", similarity=0.90),
            CompetitorOut(startup_name="Hims & Hers", name="Hims & Hers", industry="HealthTech", description="Direct-to-consumer telehealth and personalized wellness brand with digital consultations.", website="https://forhims.com", country="United States", similarity=0.86),
            CompetitorOut(startup_name="Ro", name="Ro", industry="HealthTech", description="Direct-to-patient healthcare technology platform providing diagnosis, telehealth, and pharmacy delivery.", website="https://ro.co", country="United States", similarity=0.85),
            CompetitorOut(startup_name="Abridge", name="Abridge", industry="HealthTech", description="Generative AI clinical conversation documentation platform for healthcare systems.", website="https://abridge.com", country="United States", similarity=0.84),
        ]
    elif any(k in ind_lower for k in ["agri", "farm", "crop", "soil"]):
        comps = [
            CompetitorOut(startup_name="Farmers Business Network", name="Farmers Business Network", industry="AgriTech", description="Farmer-to-farmer analytics, input purchasing, and agricultural data intelligence network.", website="https://fbn.com", country="United States", similarity=0.89),
            CompetitorOut(startup_name="Indigo Agriculture", name="Indigo Agriculture", industry="AgriTech", description="Biological seed treatments and digital carbon credit verification for sustainable farming.", website="https://indigoag.com", country="United States", similarity=0.86),
            CompetitorOut(startup_name="Prospera", name="Prospera", industry="AgriTech", description="Machine learning and computer vision systems for precision crop management and greenhouse monitoring.", website="https://prospera.ag", country="Israel", similarity=0.85),
            CompetitorOut(startup_name="Taranis", name="Taranis", industry="AgriTech", description="High-resolution sub-millimeter aerial crop scouting intelligence platform powered by AI.", website="https://taranis.com", country="United States", similarity=0.83),
        ]
    elif any(k in ind_lower for k in ["ecommerce", "e-commerce", "retail", "shop", "store"]):
        comps = [
            CompetitorOut(startup_name="Shopify", name="Shopify", industry="E-commerce", description="Leading global commerce platform enabling merchants to build and operate online storefronts.", website="https://shopify.com", country="Canada", similarity=0.93),
            CompetitorOut(startup_name="BigCommerce", name="BigCommerce", industry="E-commerce", description="Open SaaS ecommerce platform providing headless and enterprise online retail infrastructure.", website="https://bigcommerce.com", country="United States", similarity=0.87),
            CompetitorOut(startup_name="Klaviyo", name="Klaviyo", industry="E-commerce", description="Intelligent marketing automation and customer data platform built for modern ecommerce brands.", website="https://klaviyo.com", country="United States", similarity=0.86),
            CompetitorOut(startup_name="Gorgias", name="Gorgias", industry="E-commerce", description="Ecommerce customer service and support platform centralizing tickets across channels.", website="https://gorgias.com", country="United States", similarity=0.84),
        ]
    else:
        comps = [
            CompetitorOut(startup_name="Notion", name="Notion", industry="SaaS", description="Connected workspace for docs, wikis, and project management with built-in AI capabilities.", website="https://notion.so", country="United States", similarity=0.88),
            CompetitorOut(startup_name="Zapier", name="Zapier", industry="SaaS", description="Workflow automation platform connecting thousands of business apps without code.", website="https://zapier.com", country="United States", similarity=0.86),
            CompetitorOut(startup_name="Airtable", name="Airtable", industry="SaaS", description="Low-code platform for building collaborative databases and customized workflow apps.", website="https://airtable.com", country="United States", similarity=0.85),
            CompetitorOut(startup_name="Linear", name="Linear", industry="SaaS", description="Purpose-built project management and issue tracking system for high-velocity software teams.", website="https://linear.app", country="United States", similarity=0.84),
        ]

    return comps[:top_k]


def find_web_competitors_sync(
    title: str,
    description: str,
    industry: str | None = None,
    top_k: int = 4,
) -> list[CompetitorOut]:
    """Synchronous wrapper for find_web_competitors."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, find_web_competitors(title, description, industry, top_k)).result()
    return loop.run_until_complete(find_web_competitors(title, description, industry, top_k))
