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
