from __future__ import annotations
import calendar
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
        day = min(current.day, calendar.monthrange(y, m)[1])
        return current.replace(year=y, month=m, day=day)
    if frequency == "yearly":
        y = current.year + 1
        day = min(current.day, calendar.monthrange(y, current.month)[1])
        return current.replace(year=y, day=day)
    return current + timedelta(days=30)


def _month_bounds(month: str) -> tuple[date, date]:
    y, m = int(month.split("-")[0]), int(month.split("-")[1])
    return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])


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
        today = date.today()
        cutoff_month = today.month + months
        cutoff_year = today.year + (cutoff_month - 1) // 12
        cutoff_month = ((cutoff_month - 1) % 12) + 1
        cutoff_day = min(today.day, calendar.monthrange(cutoff_year, cutoff_month)[1])
        cutoff = date(cutoff_year, cutoff_month, cutoff_day)
        while d <= cutoff and len(upcoming) < 20:
            upcoming.append({"date": str(d), "amount": tmpl.amount, "description": tmpl.description})
            d = _next_due(d, tmpl.frequency)
        return upcoming

    def projected_for_month(self, month: str) -> list[dict]:
        start, end = _month_bounds(month)
        templates = self.db.query(RecurringTemplate).filter(RecurringTemplate.is_active == True).all()
        generated = self._generated_keys(start, end)
        projected = []
        for tmpl in templates:
            due = tmpl.next_due
            while due < start:
                due = _next_due(due, tmpl.frequency)
            while due <= end:
                amount = -abs(tmpl.amount)
                key = (due, round(amount, 2), tmpl.category, f"[Auto] {tmpl.description}")
                if key not in generated:
                    projected.append({
                        "date": due,
                        "amount": amount,
                        "category": tmpl.category,
                        "description": f"[Recurring] {tmpl.description}",
                        "cardholder": tmpl.cardholder or "",
                        "template_id": tmpl.id,
                    })
                due = _next_due(due, tmpl.frequency)
        return projected

    def projected_total_for_month(self, month: str) -> float:
        return round(sum(abs(item["amount"]) for item in self.projected_for_month(month)), 2)

    def _generated_keys(self, start: date, end: date) -> set[tuple]:
        rows = self.db.query(Expense).filter(Expense.date >= start, Expense.date <= end).all()
        return {
            (row.date, round(row.amount, 2), row.category, row.description or "")
            for row in rows
            if (row.description or "").startswith("[Auto] ")
        }
