# Expense Tracker Plugin for Homelab OS

Version: 1.1.0

Expense Tracker is a local-first FastAPI and SQLite plugin for tracking debits, credits, budgets, recurring expenses, and spending analytics from Homelab OS.

## What's New in 1.1.0

- Native offline ML categorization using scikit-learn `TfidfVectorizer` and `MultinomialNB`.
- Typed custom categories are supported and learned from expenses and recurring templates.
- Current bank balance can be set once and is automatically updated by debits and credits.
- Dashboard and analytics include projected monthly/yearly recurring expenses.
- Dashboard Recent Expenses now shows debits only; credits remain in Transactions.
- Smart spending descriptions, category charts, recurring impact, and investment suggestions are generated locally.

## Architecture

```text
expense-tracker/
├── plugin.json
└── docker/
    ├── Dockerfile
    ├── docker-compose.yml
    ├── app.py
    ├── app/
    │   ├── config.py
    │   ├── database.py
    │   ├── models.py
    │   ├── routes.py
    │   └── services/
    │       ├── balance_service.py
    │       ├── budget_service.py
    │       ├── expense_service.py
    │       ├── ml_service.py
    │       └── recurring_service.py
    ├── templates/index.html
    └── static/
        ├── css/styles.css
        └── js/script.js
```

## Runtime

- Backend: FastAPI, SQLAlchemy, SQLite, APScheduler
- ML: scikit-learn, trained from local transaction descriptions
- Frontend: vanilla JavaScript and Chart.js
- Data: `/mnt/nas/homelab/runtime/expense-tracker/data/expenses.db`

## Key Endpoints

- `GET /api/health`
- `GET /api/dashboard`
- `GET /api/analytics?months=6`
- `GET /api/expenses`
- `POST /api/expenses`
- `PUT /api/expenses/{id}`
- `DELETE /api/expenses/{id}`
- `GET /api/balance`
- `POST /api/balance`
- `GET /api/categories`
- `POST /api/predict-category`
- `GET /api/budget`
- `POST /api/budget`
- `GET /api/recurring`
- `POST /api/recurring`
- `PUT /api/recurring/{id}`
- `DELETE /api/recurring/{id}`

## Notes

- The plugin folder and id remain `expense-tracker`.
- No `.tgz` package is required for source editing.
- Existing SQLite installs are migrated on startup by creating the `app_settings` table when missing.
