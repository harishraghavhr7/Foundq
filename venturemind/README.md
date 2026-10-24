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
│   │   ├── database.py             # Database engine, connection normalizer & session dependency
│   │   ├── models.py               # SQLAlchemy models (Idea, InvestmentMemo)
│   │   ├── schemas.py              # Pydantic v2 schemas
│   │   ├── crud.py                 # Database CRUD operations
│   │   ├── routers/                # API routers
│   │   │   ├── classify.py         # Industry detection
│   │   │   ├── score.py            # Viability scoring
│   │   │   ├── market_demand.py    # Market demand score
│   │   │   ├── analyze.py          # Multi-Agent Investment Committee
│   │   │   └── swot.py             # SWOT generation
│   │   ├── services/
│   │   │   ├── web_competitor_search.py # Live web competitor intelligence (Tavily + LLM)
│   │   │   ├── industry_classifier.py   # Pure-logic NLP classifier
│   │   │   ├── viability_scorer.py      # 5-factor mathematical model
│   │   │   ├── market_demand.py         # Market demand score engine
│   │   │   ├── swot_analyzer.py         # SWOT generation service
│   │   │   ├── llm_client.py            # Multi-provider LLM adapter (OpenRouter/Gemini/Groq/Ollama)
│   │   │   ├── debate.py                # LangGraph cyclic multi-agent debate
│   │   │   ├── memo_writer.py           # Lead partner memo synthesis
│   │   │   └── agents/                  # Bull, Bear, Moat, Orchestrator & Tools
│   │   └── prompts/                     # Committee system prompts
│   ├── tests/                      # Pytest unit & integration test suite
│   ├── requirements.txt            # Python dependencies (streamlined for cloud deployment)
│   ├── Procfile                    # Cloud process runner
│   ├── runtime.txt                 # Pinned Python version
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
│   ├── vercel.json                 # Vercel SPA routing rewrites
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
