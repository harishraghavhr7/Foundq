"""API tests using an in-memory SQLite DB so no PostgreSQL is required to run them."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

# Single shared in-memory connection for the whole test session.
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_submit_idea_success():
    payload = {
        "title": "AI Resume Builder",
        "description": "Generates tailored resumes from a LinkedIn profile.",
        "industry": "HR Tech",
    }
    res = client.post("/ideas", json=payload)
    assert res.status_code == 201
    body = res.json()
    assert body["id"] > 0
    assert body["title"] == payload["title"]
    assert body["created_at"] is not None


def test_submit_idea_validation_error():
    res = client.post("/ideas", json={"title": "", "description": "x", "industry": "y"})
    assert res.status_code == 422
