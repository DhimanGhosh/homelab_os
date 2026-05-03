from __future__ import annotations
import calendar
from datetime import date, timedelta
from collections import defaultdict
from typing import Optional
from sqlalchemy.orm import Session
from app.models import Expense


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
        self.db.commit()
        self.db.refresh(expense)
        return expense

    def update(self, expense_id: int, data: dict) -> Optional[Expense]:
        expense = self.get(expense_id)
        if not expense:
            return None
        for k, v in data.items():
            setattr(expense, k, v)
        self.db.commit()
        self.db.refresh(expense)
        return expense

    def delete(self, expense_id: int) -> bool:
        expense = self.get(expense_id)
        if not expense:
            return False
        self.db.delete(expense)
        self.db.commit()
        return True

    # ── Analytics helpers (Python does the maths) ─────────────────────────────

    def monthly_totals(self, months: int = 6) -> list[dict]:
        """Return {month, total_expenses, total_income} for last N months."""
        from datetime import date as d
        today = d.today()
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
            result.append({"month": label, "expenses": round(expenses, 2), "income": round(income, 2)})
        return result

    def category_breakdown(self, month: str) -> list[dict]:
        """Return [{category, total}] sorted descending for a month."""
        rows = self.list(month=month)
        totals: dict[str, float] = defaultdict(float)
        for r in rows:
            if r.amount < 0:
                totals[r.category] += abs(r.amount)
        return [
            {"category": cat, "total": round(amt, 2)}
            for cat, amt in sorted(totals.items(), key=lambda x: -x[1])
        ]

    def predict_category(self, description: str) -> str:
        """Simple keyword-based category prediction (no heavy ML on Pi)."""
        desc = description.lower()
        rules = {
            "Grocery":         ["grocery", "supermarket", "vegetables", "milk", "blinkit", "zepto", "swiggy instamart"],
            "Restaurant":      ["restaurant", "cafe", "coffee", "zomato", "swiggy", "food", "pizza", "burger"],
            "Office Travel":   ["uber", "ola", "cab", "auto", "metro", "office"],
            "Subscription":    ["netflix", "spotify", "amazon prime", "hotstar", "youtube", "subscription"],
            "Medicine":        ["pharmacy", "chemist", "medicine", "doctor", "hospital", "clinic"],
            "Online Shopping": ["amazon", "flipkart", "myntra", "ajio", "meesho"],
            "Mobile Recharge": ["recharge", "airtel", "jio", "vi", "bsnl"],
            "Utilities":       ["electricity", "water", "gas", "bill", "broadband", "wifi"],
            "Flat/Rent":       ["rent", "flat", "maintenance", "society"],
            "Movies":          ["movie", "cinema", "pvr", "inox", "bookmyshow"],
            "ATM Cash":        ["atm", "cash withdrawal"],
        }
        for category, keywords in rules.items():
            if any(kw in desc for kw in keywords):
                return category
        return "Other"
