from __future__ import annotations
import math
from datetime import date
from typing import Optional
from sqlalchemy.orm import Session
from app.models import Budget


class BudgetService:
    def __init__(self, db: Session):
        self.db = db

    def get(self, month: Optional[str] = None) -> Optional[Budget]:
        if not month:
            month = date.today().strftime("%Y-%m")
        return self.db.query(Budget).filter(Budget.month == month).first()

    def upsert(self, month: str, data: dict) -> Budget:
        budget = self.get(month)
        if budget:
            for k, v in data.items():
                setattr(budget, k, v)
        else:
            budget = Budget(month=month, **data)
            self.db.add(budget)
        self.db.commit()
        self.db.refresh(budget)
        return budget

    def compute_status(self, budget: Optional[Budget], total_expenses: float) -> dict:
        """All budget calculations done in Python, returned as a dict for the frontend."""
        if not budget:
            return {
                "income": 0, "expense_limit": 0, "emergency_fund": 0,
                "investment_goal": 0,
                "total_expenses": round(total_expenses, 2),
                "remaining": 0, "savings": 0,
                "budget_pct": 0, "alert": False,
                "months_to_goal": 0,
            }
        remaining = max(budget.expense_limit - total_expenses, 0)
        savings   = max(budget.income - total_expenses - budget.emergency_fund, 0)
        pct       = min((total_expenses / budget.expense_limit * 100) if budget.expense_limit else 0, 100)
        # investment_goal = product_cost (product_goal column retired from UI)
        months_to_goal = 0
        if budget.product_cost > 0 and savings > 0:
            months_to_goal = math.ceil(budget.product_cost / savings)

        return {
            "income":           round(budget.income, 2),
            "expense_limit":    round(budget.expense_limit, 2),
            "emergency_fund":   round(budget.emergency_fund, 2),
            "investment_goal":  round(budget.product_cost, 2),
            "total_expenses":   round(total_expenses, 2),
            "remaining":        round(remaining, 2),
            "savings":          round(savings, 2),
            "budget_pct":       round(pct, 1),
            "alert":            pct >= 80,
            "months_to_goal":   months_to_goal,
        }
