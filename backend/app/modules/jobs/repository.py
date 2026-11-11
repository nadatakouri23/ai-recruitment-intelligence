"""Accès aux données des offres (toujours filtrées par propriétaire)."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.jobs.models import Job


class JobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, owner_id: int, job_id: int) -> Job | None:
        return self._session.scalar(select(Job).where(Job.id == job_id, Job.owner_id == owner_id))

    def list(self, owner_id: int, *, limit: int, offset: int) -> tuple[list[Job], int]:
        total = self._session.scalar(
            select(func.count()).select_from(Job).where(Job.owner_id == owner_id)
        )
        page = self._session.scalars(
            select(Job)
            .where(Job.owner_id == owner_id)
            .order_by(Job.created_at.desc(), Job.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(page), total or 0

    def add(self, job: Job) -> Job:
        try:
            self._session.add(job)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return job

    def save(self, job: Job) -> Job:
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return job

    def delete(self, job: Job) -> None:
        self._session.delete(job)
        self._session.commit()
