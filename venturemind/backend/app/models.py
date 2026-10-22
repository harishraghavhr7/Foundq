"""SQLAlchemy ORM models."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Idea(Base):
    __tablename__ = "ideas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    industry: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class InvestmentMemo(Base):
    __tablename__ = "investment_memos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    startup_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    verdict: Mapped[str] = mapped_column(String(50), nullable=False)
    score: Mapped[float] = mapped_column(nullable=False)
    full_memo_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

