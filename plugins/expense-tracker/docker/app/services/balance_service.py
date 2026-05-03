from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import AppSetting


BALANCE_KEY = "current_bank_balance"


class BalanceService:
    def __init__(self, db: Session):
        self.db = db

    def get_balance(self) -> float:
        row = self.db.query(AppSetting).filter(AppSetting.key == BALANCE_KEY).first()
        if not row:
            return 0.0
        try:
            return round(float(row.value), 2)
        except (TypeError, ValueError):
            return 0.0

    def set_balance(self, amount: float, commit: bool = True) -> float:
        row = self.db.query(AppSetting).filter(AppSetting.key == BALANCE_KEY).first()
        if not row:
            row = AppSetting(key=BALANCE_KEY, value="0")
            self.db.add(row)
        row.value = f"{round(float(amount), 2):.2f}"
        row.updated_at = datetime.utcnow()
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return self.get_balance()

    def apply_delta(self, delta: float) -> float:
        return self.set_balance(self.get_balance() + float(delta), commit=False)
