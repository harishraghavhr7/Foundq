"""FastAPI application entrypoint and route definitions."""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.config import settings
from app.database import Base, engine, get_db
from app.routers import analyze, classify, market_demand, score, swot


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup if they don't exist.
    # (In production prefer Alembic migrations; this is convenient for now.)
    #
    # This runs on app *startup*, not at module import. Keeping it out of import
    # means importing `app` has no side effects — the pure-logic
    # /classify-industry engine and its tests need no live database.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="VentureMind AI", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ideas", response_model=schemas.IdeaResponse, status_code=status.HTTP_201_CREATED)
def submit_idea(idea: schemas.IdeaCreate, db: Session = Depends(get_db)) -> models.Idea:
    """Persist a startup idea and return the created record."""
    return crud.create_idea(db=db, idea=idea)


# Industry Detection Engine (Feature 2) — self-contained, DB/RAG-free router.
app.include_router(classify.router)

# Startup Viability Scoring Engine (Feature 3) — self-contained, DB/RAG-free router.
app.include_router(score.router)

# Market Demand Score engine (Feature 4) — self-contained, DB/RAG-free router.
app.include_router(market_demand.router)

# Grounded market analysis (Gemini RAG generation) — retrieves competitors, then
# generates a market summary, competitor analysis, strengths and weaknesses.
app.include_router(analyze.router)

# SWOT Analysis Engine (Gemini generation) — takes the idea plus caller-supplied
# competitors and market context, generates strengths/weaknesses/opportunities/
# threats. Self-contained: no DB or RAG dependency.
app.include_router(swot.router)


@app.post("/competitors", response_model=schemas.CompetitorSearchResponse)
def competitors_endpoint(payload: schemas.CompetitorQuery) -> schemas.CompetitorSearchResponse:
    """Return the top-K most semantically similar startups (competitors)."""
    try:
        from app.rag.retrieval import find_competitors
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Competitor search unavailable: chromadb / sentence-transformers not installed.",
        )
    results = find_competitors(
        title=payload.title,
        description=payload.description,
        industry=payload.industry,
        top_k=payload.top_k,
    )
    return schemas.CompetitorSearchResponse(
        query_title=payload.title,
        competitors=[
            schemas.CompetitorOut(
                startup_name=c.startup_name,
                industry=c.industry,
                description=c.description,
                similarity=c.similarity,
            )
            for c in results
        ],
    )
