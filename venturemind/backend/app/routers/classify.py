"""Router for the Industry Detection Engine (Feature 2).

Deliberately self-contained: it imports only the Pydantic schemas and the
pure-logic classifier service — never the database or RAG layers. That keeps the
/classify-industry endpoint importable, deployable, and testable in isolation,
with no PostgreSQL or vector-store dependency. A startup's industry can be
classified even if the database or the competitor-search stack is unavailable.
"""
from fastapi import APIRouter

from app import schemas
from app.services.industry_classifier import classify_industry

router = APIRouter(tags=["industry"])


@router.post("/classify-industry", response_model=schemas.ClassifyResponse)
def classify_industry_endpoint(payload: schemas.ClassifyRequest) -> schemas.ClassifyResponse:
    """Predict the industry of a startup from its title and description."""
    result = classify_industry(title=payload.title, description=payload.description)
    return schemas.ClassifyResponse(industry=result.industry, confidence=result.confidence)
