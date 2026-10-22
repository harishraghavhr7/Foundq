# VentureMind AI — Project Scope & Architecture Blueprint

## 1. Executive Summary & Vision

**VentureMind AI** is an institutional-grade venture intelligence and startup pressure-testing platform. Founders, angel investors, and venture teams frequently assess early-stage concepts using subjective instincts or generic, ungrounded LLM prompts that hallucinate market sizes and competitive dynamics. 

VentureMind solves this by establishing a **dual-engine evaluation architecture**:
1. **Deterministic Analytics**: Algorithmic NLP classification, mathematical 5-factor viability scoring, and quantitative market demand models.
2. **Autonomous Multi-Agent Deliberation (LangGraph)**: An automated Investment Committee featuring adversarial agents (**Bull**, **Bear**, **Moat**) operating with live tools (Tavily Search, SEC EDGAR filings, Product Hunt traction) followed by cyclic cross-examination and Lead Partner consensus synthesis.

---

## 2. Core Functional Modules (Features 1–8)

### Feature 1: Idea Ingestion & Persistent Storage
* **Purpose**: Capture core startup premise (`title`, `description`, `industry`) and maintain audit history.
* **Storage**: PostgreSQL / SQLite via SQLAlchemy ORM with automatic schema initialization.
* **Status**: Complete & Verified.

### Feature 2: High-Velocity Industry Classifier
* **Purpose**: Determine the operational vertical with zero external network or model latency.
* **Mechanism**: Statistical token analysis, term frequency, and n-gram keyword weighting across 6 primary verticals (`EdTech`, `FinTech`, `HealthTech`, `AgriTech`, `SaaS`, `E-commerce`).
* **Status**: Complete & Verified.

### Feature 3: Startup Viability Scoring Engine
* **Purpose**: Provide a transparent, explainable 0–100 viability benchmark with full factor breakdown.
* **Mathematical Weights**:
  * Demand Contribution: 30%
  * Competition Penalty (Inverted): 20%
  * Scalability Contribution: 25%
  * Innovation Contribution: 15%
  * Risk Discount: $-0.3\%$ per risk unit against raw upside score.
* **Status**: Complete & Verified.

### Feature 4: Market Demand Scoring Engine
* **Purpose**: Measure market appetite and category expansion potential.
* **Variables**: Baseline industry TAM multipliers, competitor saturation penalty/validation curves, search trend momentum, and annual CAGR.
* **Status**: Complete & Verified.

### Feature 5: Semantic Competitor Retrieval (RAG)
* **Purpose**: Identify direct and indirect competitors without keyword mismatch limitations.
* **Technology**: ChromaDB vector store paired with `sentence-transformers/all-MiniLM-L6-v2` dense embeddings, indexed over curated startup datasets.
* **Status**: Complete & Verified.

### Feature 6: Grounded Market Analysis (Gemini RAG)
* **Purpose**: Generate executive market summaries and competitive positioning memos.
* **Constraint**: LLM generation is strictly grounded in retrieved ChromaDB documents, preventing factual hallucinations.
* **Status**: Complete & Verified.

### Feature 7: 4-Quadrant SWOT Matrix
* **Purpose**: Synthesize internal strengths/weaknesses and external opportunities/threats with item-by-item rationale.
* **Input Gate**: Evaluates context sufficiency to flag underdeveloped concept pitches.
* **Status**: Complete & Verified.

### Feature 8: LangGraph Multi-Agent Investment Committee
* **Purpose**: Emulate the rigor of Tier-1 venture capital partner meetings.
* **Autonomous Committee Members**:
  * **Bull Agent 🐂**: Explores market size tailwinds, viral distribution loops, TAM expansion, and optimistic growth multiples.
  * **Bear Agent 🐻**: Stress-tests margin erosion, regulatory hurdles, customer churn, CAC escalation, and unit-economic fragility.
  * **Moat Agent 🏰**: Assesses defensibility, proprietary dataset flywheels, enterprise switching costs, and IP positioning.
* **Live Tool Augmentation**:
  * Tavily Search API: Live venture rounds, founder news, and market disclosures.
  * Traction Scraper: Product Hunt community sentiment, upvotes, and pricing models.
  * SEC EDGAR: S-1 and 10-K public company benchmarks (Rule of 40, median SaaS gross margins).
* **Cyclic Multi-Agent Debate**:
  * Coordinated through a compiled LangGraph `StateGraph`, iterating through cross-critique rounds where agents challenge each other's assumptions.
* **Lead Partner Synthesis & Caching**:
  * Synthesizes an executive Investment Memo with overall score, verdict, strengths, risks, and strategic conditions.
  * Caches results in SQL database (`investment_memos`) for instant recall.
* **Unified Model Fallback Middleware**:
  * Gracefully fails over across Google Gemini, Groq Cloud, and local Ollama (`llama3.2`).
* **Status**: Complete & Verified.

---

## 3. Data & Technology Blueprint

* **Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0, Pydantic v2, ChromaDB, LangChain, LangGraph.
* **Frontend**: React 18, Vite, TypeScript, Tailwind CSS, Heroicons / Emoji indicators.
* **Datasets**: Curated 100+ multi-sector startup knowledge base (`startup_knowledge_base.csv`, `startups.csv`).

---

## 4. Completed Milestones

- [x] Full-stack idea persistence and REST API scaffolding.
- [x] Pure-logic industry classification and mathematical viability scoring.
- [x] ChromaDB semantic competitor retrieval and RAG pipeline.
- [x] Grounded Gemini market analysis and 4-quadrant SWOT matrix.
- [x] Multi-agent investment committee architecture (Bull, Bear, Moat).
- [x] Live web search and financial filing tools with execution telemetry.
- [x] LangGraph cyclic cross-examination debate graph.
- [x] Model fallback middleware (Gemini -> Groq -> Ollama).
- [x] Interactive web dashboard with Investment Memo, debate logs, and tool execution inspectors.
- [x] Clean repository governance, documentation, and production gitignore.
