"""Tests for the Industry Detection Engine (Feature 2) and its endpoint.

The endpoint tests mount the feature's own router on a minimal FastAPI app
instead of importing ``app.main``. This keeps the suite hermetic: it exercises
the *real* route, schemas, and classifier with no PostgreSQL or RAG/vector-store
dependency, so Feature 2 can be verified independently of the rest of the app.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.classify import router
from app.services.industry_classifier import SUPPORTED_INDUSTRIES, classify_industry

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_clear_edtech_signal():
    result = classify_industry(
        title="LearnLoop",
        description="An online tutoring platform that builds an adaptive curriculum for students.",
    )
    assert result.industry == "EdTech"
    assert result.confidence > 0.7


def test_clear_fintech_signal():
    result = classify_industry(
        title="PayFlow",
        description="A digital wallet for instant UPI payments and lending.",
    )
    assert result.industry == "FinTech"


def test_title_outweighs_description():
    # 'farm' in the title should beat a single weak ecommerce term in the body.
    result = classify_industry(
        title="FarmConnect for farmers",
        description="Order products easily.",
    )
    assert result.industry == "AgriTech"


def test_no_keywords_is_low_confidence():
    result = classify_industry(title="Zorp", description="A thing that does stuff.")
    # Uniform distribution => confidence near 1/N.
    assert result.confidence < 0.3
    assert result.industry in SUPPORTED_INDUSTRIES


def test_endpoint_returns_contract():
    res = client.post(
        "/classify-industry",
        json={
            "title": "MediBook",
            "description": "Telemedicine app to book a doctor appointment at any hospital.",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["industry"] == "HealthTech"
    assert 0.0 <= body["confidence"] <= 1.0
    assert set(body.keys()) == {"industry", "confidence"}


def test_endpoint_validation_error():
    res = client.post("/classify-industry", json={"title": "", "description": ""})
    assert res.status_code == 422
