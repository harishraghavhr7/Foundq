# VentureMind AI — Quickstart & Module Guide

This folder contains the complete full-stack implementation of the **VentureMind AI** platform.

For the comprehensive architectural breakdown, LangGraph state diagrams, and API documentation, please refer to the primary project [README.md](../../README.md) in the repository root.

---

## Folder Structure

```
venturemind/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI application factory & routes
│   │   ├── config.py               # Pydantic Settings configuration
│   │   ├── database.py             # Database engine & session dependency
│   │   ├── models.py               # SQLAlchemy models (Idea, InvestmentMemo)
│   │   ├── schemas.py              # Pydantic v2 schemas
│   │   ├── crud.py                 # Database CRUD operations
│   │   ├── routers/                # API routers
│   │   │   ├── classify.py         # Industry detection
│   │   │   ├── score.py            # Viability scoring
│   │   │   ├── market_demand.py    # Market demand score
│   │   │   ├── analyze.py          # Grounded Gemini analysis & Committee
│   │   │   └── swot.py             # SWOT generation
│   │   ├── services/
│   │   │   ├── industry_classifier.py
│   │   │   ├── viability_scorer.py
│   │   │   ├── market_demand.py
│   │   │   ├── market_analyzer.py
│   │   │   ├── swot_analyzer.py
│   │   │   ├── llm_client.py       # Gemini, Groq, Ollama adapter
│   │   │   ├── debate.py           # LangGraph multi-agent debate
│   │   │   ├── memo_writer.py      # Lead partner memo synthesis
│   │   │   └── agents/             # Bull, Bear, Moat, Orchestrator & Tools
│   │   ├── prompts/                # Committee system prompts
│   │   └── rag/                    # ChromaDB embeddings, ingestion & retrieval
│   ├── tests/                      # Pytest unit & integration test suite
│   ├── requirements.txt            # Python dependencies
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/                    # API client bindings
│   │   ├── components/             # Dashboard, IdeaForm, InvestmentMemoSection, SWOT, etc.
│   │   ├── hooks/                  # Custom React hooks
│   │   ├── types.ts                # TypeScript types mirroring API schemas
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── vite.config.ts
│   └── .env.example
└── db/
    └── schema.sql                  # PostgreSQL & SQLite DDL
```

---

## Local Development Instructions

### 1. Database (SQLite or PostgreSQL)
* **SQLite (Default)**: Preconfigured out-of-the-box (`sqlite:///./venturemind.db`). No extra service required.
* **PostgreSQL (Optional)**:
  ```bash
  createdb venturemind
  psql -d venturemind -f db/schema.sql
  ```

### 2. Backend
```bash
cd backend
python -m venv .venv
# Activate virtual environment:
# Windows: .venv\Scripts\activate | macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```
Open [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive Swagger API docs.

### 3. Frontend
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

### 4. Tests
```bash
cd backend
pytest
```
