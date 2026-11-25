from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from sprintpilot.config import settings


class Base(DeclarativeBase):
    pass


class ProjectRecord(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    brief_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    analysis_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    plan_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    approval_status: Mapped[str] = mapped_column(String(30), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


def _database_url() -> str:
    url = settings.database_url
    if url.startswith("sqlite:///"):
        database_path = url.removeprefix("sqlite:///")
        if database_path not in {":memory:", ""}:
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    return url


engine = create_engine(_database_url(), echo=False)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    return SessionLocal()


def save_project(
    name: str,
    brief: dict[str, Any],
    analysis: dict[str, Any] | None = None,
    plan: dict[str, Any] | None = None,
    approval_status: str = "pending",
    project_id: int | None = None,
) -> ProjectRecord:
    with SessionLocal() as session:
        if project_id is None:
            record = ProjectRecord(name=name)
        else:
            record = session.get(ProjectRecord, project_id)
            if record is None:
                raise ValueError(f"Project {project_id} does not exist.")

        record.name = name
        record.brief_json = brief
        record.analysis_json = analysis
        record.plan_json = plan
        record.approval_status = approval_status
        session.add(record)
        session.commit()
        session.refresh(record)
        return record


def get_project(project_id: int) -> ProjectRecord | None:
    with SessionLocal() as session:
        record = session.get(ProjectRecord, project_id)
        if record is None:
            return None
        session.expunge(record)
        return record


def list_projects() -> list[ProjectRecord]:
    with SessionLocal() as session:
        records = list(session.scalars(select(ProjectRecord).order_by(ProjectRecord.id)))
        for record in records:
            session.expunge(record)
        return records
