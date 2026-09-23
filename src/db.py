from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    engine: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    plan_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)


def _resolve_url(database_url: str | None) -> str:
    url = (database_url or os.getenv("DATABASE_URL", "")).strip()
    if url:
        # Some hosted PostgreSQL services provide postgres:// URLs.
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://") :]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://") :]
        return url

    data_dir = Path(__file__).resolve().parents[1] / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{data_dir / 'planner.sqlite3'}"


def init_db(database_url: str | None = None):
    url = _resolve_url(database_url)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return engine


def create_project(db_engine, name: str, source_name: str, plan: dict, engine_name: str = "") -> int:
    actual_engine = engine_name
    from datetime import datetime, timezone

    with Session(db_engine) as session:
        project = Project(
            name=name,
            source_name=source_name,
            engine=actual_engine,
            plan_json=plan,
            created_at=datetime.now(timezone.utc),
        )
        session.add(project)
        session.commit()
        session.refresh(project)
        return int(project.id)


def list_projects(db_engine):
    with Session(db_engine) as session:
        rows = session.execute(select(Project).order_by(Project.created_at.desc())).scalars().all()
        return [
            {
                "id": row.id,
                "name": row.name,
                "label": f"{row.name} — {row.created_at:%Y-%m-%d %H:%M}",
                "source_name": row.source_name,
                "engine": row.engine,
            }
            for row in rows
        ]


def load_project(db_engine, project_id: int):
    with Session(db_engine) as session:
        row = session.get(Project, int(project_id))
        if row is None:
            return None
        return {
            "id": row.id,
            "name": row.name,
            "source_name": row.source_name,
            "engine": row.engine,
            "plan": row.plan_json,
            "created_at": row.created_at,
        }
