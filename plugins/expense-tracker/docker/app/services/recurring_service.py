from __future__ import annotations
from datetime import date, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from app.models import RecurringTemplate, Expense
from app.database import SessionLocal

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    _scheduler = BackgroundScheduler()
except ImportError:
    _scheduler = None


def _next_due(current: date, frequency: str) -> date:
    if frequency == "daily":
        return current + timedelta(days=1)
    if frequency == "weekly":
        return current + timedelta(weeks=1)
    if frequency == "monthly":
        m = current.month + 1
        y = current.year + (m - 1) // 12
        m = ((m - 1) % 12) + 1
        return current.replace(year=y, month=m)
    if frequency == "yearly":
        return current.replace(year=current.year + 1)
    return current + timedelta(days=30)


def generate_due_expenses() -> None:
    """Called daily at 2 AM: create expenses for templates that are due today."""
    db = SessionLocal()
    try:
        today = date.today()
        templates = db.query(RecurringTemplate).filter(
            RecurringTemplate.is_active == True,
            RecurringTemplate.next_due <= today,
        ).all()
        for tmpl in templates:
            expense = Expense(
                date=tmpl.next_due,
                amount=-abs(tmpl.amount),
                category=tmpl.category,
                description=f"[Auto] {tmpl.description}",
                cardholder=tmpl.cardholder,
            )
            db.add(expense)
            tmpl.next_due = _next_due(tmpl.next_due, tmpl.frequency)
        db.commit()
    finally:
        db.close()


def start_scheduler() -> None:
    if _scheduler is None:
        return
    _scheduler.add_job(generate_due_expenses, "cron", hour=2, minute=0)
    _scheduler.start()


def stop_scheduler() -> None:
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()


class RecurringService:
    def __init__(self, db: Session):
        self.db = db

    def list(self) -> list[RecurringTemplate]:
        return (
            self.db.query(RecurringTemplate)
            .order_by(RecurringTemplate.next_due)
            .all()
        )

    def create(self, data: dict) -> RecurringTemplate:
        tmpl = RecurringTemplate(**data)
        self.db.add(tmpl)
        self.db.commit()
        self.db.refresh(tmpl)
        return tmpl

    def update(self, tmpl_id: int, data: dict) -> Optional[RecurringTemplate]:
        tmpl = self.db.query(RecurringTemplate).filter(RecurringTemplate.id == tmpl_id).first()
        if not tmpl:
            return None
        for k, v in data.items():
            setattr(tmpl, k, v)
        self.db.commit()
        self.db.refresh(tmpl)
        return tmpl

    def delete(self, tmpl_id: int) -> bool:
        tmpl = self.db.query(RecurringTemplate).filter(RecurringTemplate.id == tmpl_id).first()
        if not tmpl:
            return False
        self.db.delete(tmpl)
        self.db.commit()
        return True

    def preview(self, tmpl_id: int, months: int = 3) -> list[dict]:
        """Return a list of upcoming generated dates (Python logic, no DB writes)."""
        tmpl = self.db.query(RecurringTemplate).filter(RecurringTemplate.id == tmpl_id).first()
        if not tmpl:
            return []
        upcoming = []
        d = tmpl.next_due
        cutoff = date.today().replace(month=min(date.today().month + months, 12))
        while d <= cutoff and len(upcoming) < 20:
            upcoming.append({"date": str(d), "amount": tmpl.amount, "description": tmpl.description})
            d = _next_due(d, tmpl.frequency)
        return upcoming
