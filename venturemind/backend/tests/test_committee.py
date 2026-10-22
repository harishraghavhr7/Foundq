import asyncio
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
import app.rag.retrieval as rag_retrieval
from app.services.agents import BullAgent, BearAgent, MoatAgent, LeadPartnerOrchestrator
from app.services.debate import run_debate
from app.services.memo_writer import write_memo
from app.schemas import AgentVerdict



@dataclass
class MockCompetitor:
    startup_name: str = "TutorAI"
    industry: str = "EdTech"
    description: str = "AI tutoring bot"
    similarity: float = 0.85


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


class TestInvestmentCommittee(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.rag_patch = patch.object(rag_retrieval, "find_competitors", return_value=[MockCompetitor()])
        self.rag_patch.start()

    def tearDown(self):
        self.rag_patch.stop()
        Base.metadata.drop_all(bind=engine)


    def test_committee_agents_mock_mode(self):
        async def _run():
            context = {
                "title": "Quantum Tutor",
                "description": "Personalized physics tutor powered by LLMs.",
                "industry": "EdTech",
            }
            bull = BullAgent(llm_client=False)
            bear = BearAgent(llm_client=False)
            moat = MoatAgent(llm_client=False)

            v_bull = await bull.analyze(context)
            v_bear = await bear.analyze(context)
            v_moat = await moat.analyze(context)

            self.assertEqual(v_bull.agent_name, "Bull Agent")
            self.assertTrue(1.0 <= v_bull.score <= 10.0)
            self.assertTrue(len(v_bull.key_points) > 0)

            self.assertEqual(v_bear.agent_name, "Bear Agent")
            self.assertTrue(1.0 <= v_bear.score <= 10.0)

            self.assertEqual(v_moat.agent_name, "Moat Agent")
            self.assertTrue(1.0 <= v_moat.score <= 10.0)

        asyncio.run(_run())

    def test_debate_round_and_memo(self):
        async def _run():
            committee = [BullAgent(False), BearAgent(False), MoatAgent(False)]
            verdicts = [
                AgentVerdict(agent_name="Bull Agent", score=8.5, summary="Huge market", key_points=["Growth"], recommendation="Invest"),
                AgentVerdict(agent_name="Bear Agent", score=6.0, summary="High CAC", key_points=["Churn"], recommendation="Caution"),
                AgentVerdict(agent_name="Moat Agent", score=7.0, summary="Data moat", key_points=["Switching costs"], recommendation="Defend"),
            ]

            debate = await run_debate(committee, verdicts, rounds=1)
            self.assertEqual(len(debate), 1)
            self.assertEqual(len(debate[0].critiques), 3)

            context = {"id": 1, "title": "Quantum Tutor", "description": "Physics tutor", "industry": "EdTech"}
            v_bull = await committee[0].analyze(context)
            v_bear = await committee[1].analyze(context)
            v_moat = await committee[2].analyze(context)
            analyzed_verdicts = [v_bull, v_bear, v_moat]

            memo = await write_memo(context, analyzed_verdicts, debate, llm_client=False)
            self.assertEqual(memo.startup_id, 1)
            self.assertTrue(memo.overall_score >= 1.0)
            self.assertIn(memo.verdict, ["STRONG INVEST", "INVEST WITH CONDITIONS", "CAUTION / PASS", "PASS"])
            self.assertTrue(len(memo.key_strengths) > 0)
            self.assertTrue(len(memo.key_risks) > 0)
            self.assertTrue(len(memo.tool_calls) >= 3)
            self.assertEqual(memo.tool_calls[0].status, "completed")
            self.assertIsNotNone(memo.tool_calls[0].retrieved_information)

        asyncio.run(_run())


    def test_analyze_endpoint_and_cache(self):
        # 1. Create startup idea
        create_res = client.post("/ideas", json={
            "title": "Quantum Tutor",
            "description": "Personalized physics tutor powered by LLMs.",
            "industry": "EdTech",
        })
        self.assertEqual(create_res.status_code, 201)
        startup_id = create_res.json()["id"]

        # 2. Run analysis
        res = client.post(f"/startups/{startup_id}/analyze")
        self.assertEqual(res.status_code, 200)
        memo = res.json()
        self.assertEqual(memo["startup_id"], startup_id)
        self.assertEqual(len(memo["agent_verdicts"]), 3)
        self.assertIn("verdict", memo)
        self.assertIn("overall_score", memo)
        self.assertIn("tool_calls", memo)
        self.assertTrue(len(memo["tool_calls"]) > 0)
        self.assertEqual(memo["tool_calls"][0]["status"], "completed")
        self.assertIn("retrieved_information", memo["tool_calls"][0])
        self.assertIn("tool_calls", memo["agent_verdicts"][0])

        # 3. Retrieve cached memo via GET
        get_res = client.get(f"/startups/{startup_id}/memo")
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["overall_score"], memo["overall_score"])

        # 4. 404 on invalid startup ID
        invalid_res = client.post("/startups/99999/analyze")
        self.assertEqual(invalid_res.status_code, 404)


if __name__ == "__main__":
    unittest.main()

