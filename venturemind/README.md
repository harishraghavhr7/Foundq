# VentureMind AI — Feature 1: Startup Idea Submission

A full-stack slice: React + TypeScript form → FastAPI `POST /ideas` → PostgreSQL `ideas` table.

## Folder structure

```
venturemind/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py        # env-driven settings (DB URL, CORS)
│   │   ├── database.py      # engine, session, get_db dependency
│   │   ├── models.py        # SQLAlchemy ORM model (Idea)
│   │   ├── schemas.py       # Pydantic request/response models
│   │   ├── crud.py          # DB operations
│   │   └── main.py          # FastAPI app + routes
│   ├── tests/
│   │   └── test_ideas.py    # API tests (in-memory SQLite)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/ideas.ts     # fetch client
│   │   ├── components/IdeaForm.tsx
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── types.ts         # shared TS types mirroring the API
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── .env.example
└── db/
    └── schema.sql           # raw PostgreSQL DDL
```

## Run it

### 1. Database
```bash
createdb venturemind
psql -d venturemind -f db/schema.sql      # optional: app also auto-creates tables
```

### 2. Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # edit DATABASE_URL
uvicorn app.main:app --reload                        # http://localhost:8000/docs
```

### 3. Frontend
```bash
cd frontend
npm install
cp .env.example .env
npm run dev                                          # http://localhost:5173
```

### 4. Tests
```bash
cd backend
pytest
```
