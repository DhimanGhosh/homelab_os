from __future__ import annotations
import os
from pathlib import Path

APP_NAME    = os.getenv("APP_NAME", "Expense Tracker")
APP_VERSION = os.getenv("APP_VERSION", "1.1.0")
PORT        = int(os.getenv("PORT", "8161"))

DATA_DIR = Path(os.getenv("APP_DATA_DIR", "/mnt/nas/homelab/runtime/expense-tracker/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR}/expenses.db"

CATEGORIES = [
    "Office Travel", "Grocery", "Restaurant", "Cigarette", "Subscription",
    "Other Travels", "Games", "Medicine", "CC Bill", "Maid Cash",
    "Bank Savings", "Pocket Money", "Bank GST", "Online Shopping", "Movies",
    "ATM Cash", "Mobile Recharge", "Offline Shopping", "Parcel",
    "Flat/Rent", "Utilities", "Outside Food", "Other",
]

CARDHOLDERS = ["Dhiman Ghosh", "Anushree Mitra"]
