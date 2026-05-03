# Expense Tracker Plugin for Homelab OS

An intelligent, cross-device expense tracking system for your homelab. Track expenses from anywhere with OCR receipt scanning, voice entry, auto-categorization, and recurring expense detection.

## Features

### Phase 1 - MVP (Core Tracking)
- ✅ **Expense Tracking**: Add, edit, delete expenses with category, amount, date, and description
- ✅ **Budget Management**: Set category or total budgets with configurable alerts (80%, 100%)
- ✅ **Analytics Dashboard**: Real-time spending overview with charts and trends
- ✅ **Cross-Device Sync**: Central NAS database ensures all devices stay in sync
- ✅ **Mobile-Responsive UI**: Works perfectly on phone, tablet, and desktop

### Phase 2 - Intelligent Features
- 🚀 **Receipt OCR Scanning**: Upload receipt images, auto-extract merchant, amount, and date
- 🚀 **Auto-Categorization**: AI suggests category based on merchant name and description
- 🚀 **Recurring Detection**: Automatically detects and creates recurring expenses
- 🚀 **Advanced Analytics**: Spending trends, anomaly detection, and budget projections

### Phase 3 - Enhancement
- 🔄 **Voice Entry**: Speak your expenses in natural language
- 📊 **Export**: CSV/PDF reports for analysis
- 📱 **Full Mobile Optimization**: Native-like mobile experience

## Architecture

```
expense-tracker/
├── plugin.json                          # Plugin manifest
└── docker/
    ├── Dockerfile                       # Python 3.11 + dependencies
    ├── docker-compose.yml               # Container configuration
    ├── app.py                          # FastAPI entry point
    ├── app/
    │   ├── __init__.py
    │   ├── config.py                   # Configuration
    │   ├── database.py                 # SQLAlchemy setup
    │   ├── models.py                   # Data models (Pydantic + SQLAlchemy)
    │   ├── routes/
    │   │   ├── expenses.py             # CRUD endpoints
    │   │   ├── budgets.py              # Budget endpoints
    │   │   ├── analytics.py            # Analytics endpoints
    │   │   ├── receipts.py             # Receipt OCR endpoints
    │   │   ├── recurring.py            # Recurring expense endpoints
    │   │   └── voice.py                # Voice entry endpoints
    │   └── services/
    │       ├── ocr_service.py          # Receipt scanning
    │       ├── categorization.py       # Auto-categorization
    │       ├── recurring_detector.py   # Pattern detection
    │       ├── voice_processor.py      # Voice transcription
    │       └── analytics_engine.py     # Advanced analytics
    ├── templates/
    │   └── index.html                  # Vue.js SPA template
    └── static/
        ├── css/styles.css              # Responsive styling
        └── js/main.js                  # Vue.js application

Data Storage:
├── /mnt/nas/homelab/runtime/expense-tracker/data/
│   ├── expenses.db                     # SQLite database
│   └── receipts/                       # Receipt images
```

## Technology Stack

### Backend
- **Framework**: FastAPI (async, high-performance)
- **Database**: SQLite (file-based, NAS-mounted)
- **ORM**: SQLAlchemy
- **AI/ML**:
  - OCR: Pytesseract + Tesseract
  - NLP: spaCy (entity extraction)
  - ML: scikit-learn (categorization)
  - Voice: OpenAI Whisper or Ollama (local)
- **Task Scheduling**: APScheduler (recurring expenses)

### Frontend
- **Framework**: Vue.js 3 (lightweight, reactive)
- **Styling**: CSS3 (responsive, mobile-first)
- **Charts**: Chart.js (analytics visualizations)

### Deployment
- **Container**: Docker
- **Orchestration**: docker-compose
- **Network**: Caddy reverse proxy (HTTPS, global access)
- **Storage**: NAS volume mount (`/mnt/nas/homelab/runtime/expense-tracker/data/`)

## Installation

### 1. Build the Plugin
```bash
cd homelab_os
homelabctl build-plugin plugins/expense-tracker --env-file .env
```

This creates: `build/expense-tracker.v1.0.1.tgz`

### 2. Install the Plugin
```bash
homelabctl install-plugin build/expense-tracker.v1.0.1.tgz --env-file .env
```

This:
- Extracts the archive to `/mnt/nas/homelab/runtime/installed_plugins/expense-tracker/`
- Creates a data directory at `/mnt/nas/homelab/runtime/expense-tracker/data/`
- Registers the plugin in `manifests/installed_plugins.json`
- Starts the Docker container automatically

### 3. Access the Plugin
Navigate to: `https://<your-homelab-fqdn>:8461/`

Example: `https://pi-nas.taild4713b.ts.net:8461/`

## Configuration

### Environment Variables (docker-compose.yml)
```yaml
environment:
  APP_NAME: "Expense Tracker"
  APP_VERSION: "1.0.1"
  APP_DATA_DIR: "/mnt/nas/homelab/runtime/expense-tracker/data"
  LOG_LEVEL: "INFO"
```

### Database
- Location: `/mnt/nas/homelab/runtime/expense-tracker/data/expenses.db`
- Type: SQLite
- Auto-migrated on startup (SQLAlchemy handles schema creation)

## API Endpoints

### Expenses
- `GET /api/expenses/` - List expenses (with filtering)
- `POST /api/expenses/` - Create expense
- `GET /api/expenses/{id}` - Get expense
- `PUT /api/expenses/{id}` - Update expense
- `DELETE /api/expenses/{id}` - Delete expense
- `GET /api/expenses/summary/monthly` - Monthly summary

### Budgets
- `GET /api/budgets/` - List budgets
- `POST /api/budgets/` - Create budget
- `GET /api/budgets/{id}` - Get budget
- `PUT /api/budgets/{id}` - Update budget
- `DELETE /api/budgets/{id}` - Delete budget
- `GET /api/budgets/{id}/status` - Budget usage status

### Analytics
- `GET /api/analytics/dashboard` - Dashboard data
- `GET /api/analytics/category/{category}` - Category analytics
- `GET /api/analytics/period?period=week|month|year` - Period analytics
- `GET /api/analytics/insights` - Spending insights

### Recurring Expenses
- `GET /api/recurring/` - List recurring
- `POST /api/recurring/` - Create recurring
- `GET /api/recurring/{id}` - Get recurring
- `PUT /api/recurring/{id}` - Update recurring
- `DELETE /api/recurring/{id}` - Delete recurring
- `POST /api/recurring/{id}/pause` - Pause recurring
- `POST /api/recurring/{id}/resume` - Resume recurring

### Receipts
- `POST /api/receipts/upload` - Upload and scan receipt
- `GET /api/receipts/{expense_id}` - Get receipt

### Voice/Quick Entry
- `POST /api/voice/transcribe` - Transcribe audio to expense
- `POST /api/voice/quick-entry` - Parse quick text entry

## Usage Guide

### Adding an Expense (3 ways)

**Method 1: Quick Entry**
1. Click "Quick Entry"
2. Enter amount (e.g., "15.50")
3. Add description (optional)
4. Click "Save"

**Method 2: Voice (Future)**
1. Click "Voice Entry"
2. Say "Spent 15 dollars on coffee at Starbucks"
3. Verify and save

**Method 3: Manual Entry**
1. Click "Add Expense"
2. Fill in all fields
3. Click "Add Expense"

### Setting a Budget
1. Go to "Budgets" tab
2. Click "Add Budget"
3. Select category (or leave empty for total budget)
4. Enter budget amount
5. Select month
6. Click "Create Budget"

The system will warn you when you reach 80% of budget and alert at 100%.

### Viewing Analytics
1. Go to "Dashboard" tab
2. View spending overview:
   - Total spending (this month, year, all-time)
   - Daily average
   - Top spending categories
   - Monthly spending trend

### Managing Recurring Expenses
1. Go to "Recurring" tab
2. Click "Add Recurring"
3. Enter description (e.g., "Netflix")
4. Set amount, category, frequency
5. System auto-fills on due date

Or let the system detect recurring patterns automatically:
1. System analyzes history
2. Suggests recurring patterns
3. One-click setup

### Getting Insights
1. Go to "Insights" tab
2. View:
   - Unusual spending patterns
   - Monthly spending trends
   - Budget recommendations
   - Category insights

## Database Schema

### Expenses Table
```sql
CREATE TABLE expenses (
  id INTEGER PRIMARY KEY,
  user_id TEXT,
  amount FLOAT,
  category TEXT,
  date DATE,
  time TIME,
  description TEXT,
  tags TEXT,
  receipt_url TEXT,
  recurring_expense_id INTEGER,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
```

### Budgets Table
```sql
CREATE TABLE budgets (
  id INTEGER PRIMARY KEY,
  user_id TEXT,
  category TEXT,  -- NULL for total budget
  amount FLOAT,
  month DATE,
  alert_threshold FLOAT,  -- default 80.0
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
```

### Recurring Expenses Table
```sql
CREATE TABLE recurring_expenses (
  id INTEGER PRIMARY KEY,
  user_id TEXT,
  description TEXT,
  amount FLOAT,
  category TEXT,
  frequency TEXT,  -- 'weekly', 'bi-weekly', 'monthly', 'yearly'
  day_of_period INTEGER,
  last_created DATE,
  next_due DATE,
  is_active BOOLEAN,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
```

## Troubleshooting

### Plugin won't start
```bash
# Check Docker logs
docker logs expense-tracker

# Verify NAS mount
df /mnt/nas

# Rebuild and reinstall
homelabctl uninstall-plugin expense-tracker
homelabctl build-plugin plugins/expense-tracker --env-file .env
homelabctl install-plugin build/expense-tracker.v1.0.1.tgz --env-file .env
```

### Database locked
The SQLite database might be locked if the container crashed. The watchdog service should auto-recover within seconds.

### OCR not working
Ensure Tesseract is properly installed in the Docker image. Check logs: `docker logs expense-tracker | grep -i ocr`

## Development

### Local Development
```bash
cd docker

# Install dependencies
pip install -r requirements.txt

# Run FastAPI
python -m uvicorn app:app --host 0.0.0.0 --port 8150 --reload

# Frontend available at: http://localhost:8150
```

### Running Tests (Phase 2+)
```bash
pytest tests/
```

### Building New Container
```bash
docker build -t expense-tracker:latest .
docker run -p 8150:8150 -v /mnt/nas/homelab/runtime/expense-tracker/data:/mnt/nas/homelab/runtime/expense-tracker/data expense-tracker:latest
```

## Roadmap

- **v1.0** ✅ Core expense tracking, budgets, analytics, cross-device sync
- **v1.1** 🚀 Receipt OCR, auto-categorization, recurring detection
- **v2.0** 🔄 Voice entry, advanced analytics, export (CSV/PDF)
- **v2.1** 👥 Multi-user support with per-user permissions
- **v3.0** 📱 Native mobile app (React Native)

## License

Same as homelab-os

## Support

Issues? Check the logs:
```bash
docker logs expense-tracker

# Or from homelab-os CLI
homelabctl logs expense-tracker
```

For bugs or features, create an issue in the homelab-os repository.
