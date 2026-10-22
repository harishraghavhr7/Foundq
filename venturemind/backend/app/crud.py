"""Database operations (kept separate from the HTTP layer)."""
from sqlalchemy.orm import Session

from app import models, schemas


def create_idea(db: Session, idea: schemas.IdeaCreate) -> models.Idea:
    db_idea = models.Idea(
        title=idea.title,
        description=idea.description,
        industry=idea.industry,
    )
    db.add(db_idea)
    db.commit()
    db.refresh(db_idea)  # populate server-generated fields (id, created_at)
    return db_idea


def get_idea(db: Session, idea_id: int) -> models.Idea | None:
    """Fetch an idea / startup by its primary key ID."""
    return db.query(models.Idea).filter(models.Idea.id == idea_id).first()


# Alias for startup ID consistency
get_startup = get_idea


def get_memo_by_startup_id(db: Session, startup_id: int) -> models.InvestmentMemo | None:
    """Fetch the latest investment memo for a startup if one exists."""
    return (
        db.query(models.InvestmentMemo)
        .filter(models.InvestmentMemo.startup_id == startup_id)
        .order_by(models.InvestmentMemo.created_at.desc())
        .first()
    )


def save_memo(db: Session, startup_id: int, memo: schemas.InvestmentMemo) -> models.InvestmentMemo:
    """Persist an investment memo to the database."""
    db_memo = models.InvestmentMemo(
        startup_id=startup_id,
        verdict=memo.verdict,
        score=memo.overall_score,
        full_memo_json=memo.model_dump_json(),
    )
    db.add(db_memo)
    db.commit()
    db.refresh(db_memo)
    return db_memo

