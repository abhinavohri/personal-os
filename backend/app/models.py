import uuid
from datetime import date, datetime
from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

def uuid_str() -> str:
    return str(uuid.uuid4())

class Learner(Base):
    __tablename__ = "learners"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(80), default="Explorer")
    xp: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    daily_goal: Mapped[int] = mapped_column(Integer, default=30)
    last_active_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now().astimezone())

class LessonProgress(Base):
    __tablename__ = "lesson_progress"
    __table_args__ = (UniqueConstraint("learner_id", "lesson_slug"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id"), index=True)
    lesson_slug: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(20), default="available")
    best_score: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class LessonSession(Base):
    __tablename__ = "lesson_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id"), index=True)
    lesson_slug: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    position: Mapped[int] = mapped_column(Integer, default=0)
    hearts: Mapped[int] = mapped_column(Integer, default=5)
    xp_earned: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    mistakes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now().astimezone())

class ExerciseAttempt(Base):
    __tablename__ = "exercise_attempts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    session_id: Mapped[str] = mapped_column(ForeignKey("lesson_sessions.id"), index=True)
    exercise_id: Mapped[str] = mapped_column(String(100))
    answer: Mapped[dict] = mapped_column(JSON)
    correct: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now().astimezone())
