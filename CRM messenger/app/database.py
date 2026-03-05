import os
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text,
    create_engine
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data/bot.db")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Member(Base):
    __tablename__ = "members"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100), unique=True, nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    display_name = Column(String(200), nullable=True)  # how they appear in transcripts
    is_chairman = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    tasks = relationship("Task", back_populates="assignee")
    comments = relationship("TaskComment", back_populates="author")

    @property
    def name(self):
        return self.display_name or self.first_name or self.username or f"User {self.telegram_id}"


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True)
    date = Column(DateTime, nullable=False)
    title = Column(String(500), nullable=True)
    raw_transcript = Column(Text, nullable=False)  # original text from Plaud
    summary = Column(Text, nullable=True)  # AI-generated structured summary
    participants = Column(Text, nullable=True)  # comma-separated names
    decisions = Column(Text, nullable=True)  # AI-extracted decisions (JSON)
    open_questions = Column(Text, nullable=True)  # AI-extracted open questions (JSON)
    agenda_items_next = Column(Text, nullable=True)  # items for next meeting agenda (JSON)
    is_confirmed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    tasks = relationship("Task", back_populates="meeting")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=True)
    assignee_id = Column(Integer, ForeignKey("members.id"), nullable=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    context_quote = Column(Text, nullable=True)  # quote from transcript
    priority = Column(String(20), default="medium")  # high, medium, low
    status = Column(String(20), default="new")  # new, in_progress, done, overdue
    deadline = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="tasks")
    assignee = relationship("Member", back_populates="tasks")
    comments = relationship("TaskComment", back_populates="task")


class TaskComment(Base):
    __tablename__ = "task_comments"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="comments")
    author = relationship("Member", back_populates="comments")


class MeetingEmbedding(Base):
    """Stores text chunks and their embeddings for RAG search."""
    __tablename__ = "meeting_embeddings"

    id = Column(Integer, primary_key=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    # Store embedding as JSON string for SQLite v1
    embedding = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
