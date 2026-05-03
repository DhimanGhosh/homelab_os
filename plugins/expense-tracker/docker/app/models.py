from __future__ import annotations
from datetime import date, datetime
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, ForeignKey
from app.database import Base


class Expense(Base):
    __tablename__ = "expenses"

    id          = Column(Integer, primary_key=True, index=True)
    date        = Column(Date, nullable=False, index=True)
    amount      = Column(Float, nullable=False)          # negative = expense, positive = income
    category    = Column(String, nullable=False, index=True)
    description = Column(String, nullable=True)
    cardholder  = Column(String, nullable=True)          # "Dhiman Ghosh" | "Anushree Mitra"
    created_at  = Column(DateTime, default=datetime.utcnow)


class Budget(Base):
    __tablename__ = "budgets"

    id             = Column(Integer, primary_key=True, index=True)
    month          = Column(String, nullable=False, index=True, unique=True)  # "YYYY-MM"
    income         = Column(Float, default=0.0)
    expense_limit  = Column(Float, default=0.0)
    emergency_fund = Column(Float, default=0.0)
    product_goal   = Column(Float, default=0.0)
    product_cost   = Column(Float, default=0.0)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RecurringTemplate(Base):
    __tablename__ = "recurring_templates"

    id          = Column(Integer, primary_key=True, index=True)
    description = Column(String, nullable=False)
    amount      = Column(Float, nullable=False)
    category    = Column(String, nullable=False)
    cardholder  = Column(String, nullable=True)
    frequency   = Column(String, nullable=False)   # daily|weekly|monthly|yearly
    next_due    = Column(Date, nullable=False)
    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime, default=datetime.utcnow)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key        = Column(String, primary_key=True, index=True)
    value      = Column(String, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
