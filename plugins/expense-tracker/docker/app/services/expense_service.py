from __future__ import annotations
import calendar
from datetime import date
from collections import defaultdict
from typing import Optional
from sqlalchemy.orm import Session
from app.config import CATEGORIES
from app.models import Expense, RecurringTemplate
from app.services.balance_service import BalanceService
from app.services.ml_service import ml_prediction
from app.services.recurring_service import RecurringService


class ExpenseService:
    def __init__(self, db: Session):
        self.db = db

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def list(
        self,
        month: Optional[str] = None,
        category: Optional[str] = None,
        cardholder: Optional[str] = None,
    ) -> list[Expense]:
        q = self.db.query(Expense)
        if month:                          # "YYYY-MM"
            y, m = int(month.split("-")[0]), int(month.split("-")[1])
            last_day = calendar.monthrange(y, m)[1]
            q = q.filter(
                Expense.date >= date(y, m, 1),
                Expense.date <= date(y, m, last_day),
            )
        if category:
            q = q.filter(Expense.category == category)
        if cardholder:
            q = q.filter(Expense.cardholder == cardholder)
        return q.order_by(Expense.date.desc()).all()

    def get(self, expense_id: int) -> Optional[Expense]:
        return self.db.query(Expense).filter(Expense.id == expense_id).first()

    def create(self, data: dict) -> Expense:
        expense = Expense(**data)
        self.db.add(expense)
        BalanceService(self.db).apply_delta(expense.amount)
        self.db.commit()
        self.db.refresh(expense)
        return expense

    def update(self, expense_id: int, data: dict) -> Optional[Expense]:
        expense = self.get(expense_id)
        if not expense:
            return None
        old_amount = expense.amount
        for k, v in data.items():
            setattr(expense, k, v)
        BalanceService(self.db).apply_delta(expense.amount - old_amount)
        self.db.commit()
        self.db.refresh(expense)
        return expense

    def delete(self, expense_id: int) -> bool:
        expense = self.get(expense_id)
        if not expense:
            return False
        BalanceService(self.db).apply_delta(-expense.amount)
        self.db.delete(expense)
        self.db.commit()
        return True

    # ── Analytics helpers (Python does the maths) ─────────────────────────────

    def monthly_totals(self, months: int = 6, include_recurring: bool = False) -> list[dict]:
        """Return {month, total_expenses, total_income} for last N months."""
        from datetime import date as d
        today = d.today()
        rec_svc = RecurringService(self.db)
        result = []
        for i in range(months - 1, -1, -1):
            m = today.month - i
            y = today.year
            while m <= 0:
                m += 12
                y -= 1
            label = f"{y}-{m:02d}"
            rows = self.list(month=label)
            expenses = sum(abs(r.amount) for r in rows if r.amount < 0)
            income   = sum(r.amount for r in rows if r.amount >= 0)
            recurring = rec_svc.projected_total_for_month(label) if include_recurring else 0
            result.append({
                "month": label,
                "expenses": round(expenses + recurring, 2),
                "income": round(income, 2),
                "recurring": round(recurring, 2),
            })
        return result

    def category_breakdown(self, month: str, include_recurring: bool = False) -> list[dict]:
        """Return [{category, total}] sorted descending for a month."""
        rows = self.list(month=month)
        totals: dict[str, float] = defaultdict(float)
        for r in rows:
            if r.amount < 0:
                totals[r.category] += abs(r.amount)
        if include_recurring:
            for item in RecurringService(self.db).projected_for_month(month):
                totals[item["category"]] += abs(item["amount"])
        return [
            {"category": cat, "total": round(amt, 2)}
            for cat, amt in sorted(totals.items(), key=lambda x: -x[1])
        ]

    def all_categories(self) -> list[str]:
        expense_categories = [
            row[0] for row in self.db.query(Expense.category).distinct().all() if row[0]
        ]
        recurring_categories = [
            row[0] for row in self.db.query(RecurringTemplate.category).distinct().all() if row[0]
        ]
        return sorted(set(CATEGORIES + expense_categories + recurring_categories), key=str.lower)

    def predict_category(self, description: str) -> str:
        return self.predict_category_details(description)["category"]

    def predict_category_details(self, description: str) -> dict:
        prediction = ml_prediction(description, self.db.query(Expense).all())
        return {
            "category": prediction.category,
            "confidence": prediction.confidence,
            "source": prediction.source,
            "alternatives": prediction.alternatives,
        }

    def smart_insights(self, month: str, budget_status: dict, breakdown: list[dict], trends: list[dict]) -> dict:
        top = breakdown[0] if breakdown else None
        recurring_total = RecurringService(self.db).projected_total_for_month(month)
        previous = trends[-2]["expenses"] if len(trends) > 1 else 0
        current = trends[-1]["expenses"] if trends else 0
        trend_delta = round(current - previous, 2)
        descriptions = []
        if top:
            descriptions.append(f"{top['category']} is your highest spending category this month at ₹{top['total']:,.2f}.")
        if recurring_total:
            descriptions.append(f"Projected recurring expenses add ₹{recurring_total:,.2f} this month.")
        if trend_delta > 0:
            descriptions.append(f"Spending is up ₹{trend_delta:,.2f} compared with last month.")
        elif trend_delta < 0:
            descriptions.append(f"Spending is down ₹{abs(trend_delta):,.2f} compared with last month.")
        else:
            descriptions.append("Spending is steady compared with last month.")

        savings = budget_status.get("savings", 0) or 0
        suggestions = []
        if savings > 0:
            rd_amount = max(round(savings * 0.35, 2), 0)
            suggestions.append(f"Consider moving about ₹{rd_amount:,.2f} into a Recurring Deposit for predictable monthly saving.")
            suggestions.append("Keep LIC or Post Office options for lower-risk, longer-horizon goals after emergency savings are covered.")
        else:
            suggestions.append("Build a small monthly surplus first, then split it between RD and low-risk Post Office options.")
        if budget_status.get("emergency_fund", 0) > 0:
            suggestions.append("Protect the emergency fund before increasing discretionary investments.")
        if top:
            suggestions.append(f"Review {top['category']} expenses for avoidable repeat spends before adding new investments.")

        return {
            "top_category": top,
            "recurring_total": round(recurring_total, 2),
            "trend_delta": trend_delta,
            "descriptions": descriptions,
            "investment_suggestions": suggestions,
        }
