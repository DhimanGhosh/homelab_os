# Expense Tracker Plugin - Quick Start Guide

## 🚀 5-Minute Setup

### Step 1: Build the Plugin
```bash
cd homelab_os
homelabctl build-plugin plugins/expense-tracker --env-file .env
```
✅ Creates: `build/expense-tracker.v1.0.1.tgz`

### Step 2: Install the Plugin
```bash
homelabctl install-plugin build/expense-tracker.v1.0.1.tgz --env-file .env
```
✅ Installs to: `/mnt/nas/homelab/runtime/installed_plugins/expense-tracker/`

### Step 3: Access the Plugin
Navigate to your homelab URL (replace with your actual FQDN):
```
https://<your-homelab-fqdn>:8461/
```

Example: `https://pi-nas.taild4713b.ts.net:8461/`

✅ **Your Expense Tracker is live!**

---

## 💡 First Steps After Installation

### 1. Add Your First Expense (30 seconds)
1. Click **"Expenses"** tab
2. Click **"Quick Entry"** button
3. Enter amount: `15.50`
4. Enter description: `coffee`
5. Click **"Save"**
6. See expense appear in table

### 2. View Your Dashboard
1. Click **"Dashboard"** tab
2. See spending summary:
   - **This Month**: $15.50
   - **Stat Cards**: Monthly, yearly, all-time totals
   - **Charts**: (empty for now, will populate with more expenses)

### 3. Set a Budget
1. Click **"Budgets"** tab
2. Click **"Add Budget"**
3. Category: `Food`
4. Amount: `500`
5. Month: Select current month
6. Click **"Create Budget"**
7. You'll see a progress bar showing: `3% used` (15.50/500)

### 4. Create a Recurring Expense
1. Click **"Recurring"** tab
2. Click **"Add Recurring"**
3. Description: `Netflix`
4. Amount: `12.99`
5. Category: `Entertainment`
6. Frequency: `Monthly`
7. Click **"Create"**
8. System will auto-fill next month

### 5. Get Insights
1. Click **"Insights"** tab
2. View AI-generated insights about your spending
3. Add more expenses to see trends

---

## 📊 Using Key Features

### Quick Entry (Fastest Method)
**Use this for rapid expense logging:**
```
15.50 coffee
45.00 groceries
12.99 netflix subscription
100 electric bill
```

Format: `[amount] [description]`

The system will:
- ✅ Automatically detect the amount
- ✅ Suggest a category based on description
- ✅ Create the expense with today's date

**Time: ~5 seconds per expense**

### Receipt Upload (OCR coming in Phase 2)
**Planned feature** - Will allow:
```
1. Take receipt photo
2. App extracts amount, merchant, date
3. Auto-categorizes based on merchant
4. One-click confirm
```

Currently supports upload UI (awaiting Tesseract setup).

### Voice Entry (Phase 3)
**Planned feature** - Say things like:
```
"Spent 15 dollars on coffee at Starbucks"
"Netflix subscription 12.99"
"Groceries 45 dollars"
```

The app will:
- ✅ Transcribe your speech
- ✅ Parse amount, merchant, description
- ✅ Suggest category
- ✅ Save with one tap

### Budget Alerts
**How it works:**
1. Set a budget (e.g., Food = $500/month)
2. Add expenses in that category
3. At **80% of budget**: ⚠️ Yellow warning
4. At **100% of budget**: 🔴 Red alert
5. System prevents overspending visually

### Recurring Expense Auto-Creation
**Manual setup (now):**
1. Go to Recurring tab
2. Add: Netflix $12.99, monthly, on day 5
3. System auto-creates on the 5th each month

**Auto-detection (Phase 2):**
1. App analyzes spending history
2. Suggests patterns: "Netflix appears every month"
3. One-click: Convert to recurring

---

## 🎯 Common Workflows

### Workflow 1: Daily Expense Logging (10 expenses)
```
1. Open app
2. Quick Entry × 10 times
3. Takes ~1 minute total
4. Dashboard updates in real-time
```

### Workflow 2: Weekly Review
```
1. Dashboard tab
2. Check "This Week" spending
3. View top categories
4. See budget status
5. Note any unusual spending
Takes ~2 minutes
```

### Workflow 3: Budget Planning
```
1. Budgets tab
2. Review last month's spending by category
3. Set budgets for next month (with 10% buffer)
4. Get recommendations from insights
Takes ~5 minutes
```

### Workflow 4: Monthly Analysis
```
1. Insights tab
2. Review trends
3. Check anomalies (unusual expenses)
4. Analyze category spending
5. Plan adjustments for next month
Takes ~10 minutes
```

---

## 📱 Mobile Tips

### Phone Access
The app is fully responsive on phones:

**Landscape**:
- Tabs at top
- Content flows horizontally
- Charts visible

**Portrait**:
- Tabs stack
- Single-column layout
- Touch-friendly buttons
- Modals expand full-screen

### Best Practices
1. **Use Quick Entry on phone** (faster than forms)
2. **View Dashboard on desktop** (better charts)
3. **Manage Budgets on desktop** (easier with mouse)
4. **Quick check status anywhere** (sync is instant)

---

## 🔄 Data Sync Across Devices

### How It Works
- **Central Database**: All data stored on NAS
- **Instant Sync**: Changes visible on all devices immediately
- **No Conflicts**: Server handles all writes
- **Always Safe**: NAS backups protect your data

### Testing Multi-Device Sync
1. **Open on Phone**: https://your-homelab.com:8460
2. **Open on PC**: Same URL
3. **Add expense on Phone**
4. **Check PC** - Expense appears instantly
5. **Add budget on PC**
6. **Check Phone** - Budget updates immediately

---

## ⚙️ Verification Checklist

### After Installation
- [ ] Plugin container is running: `docker ps | grep expense-tracker`
- [ ] Database created: `ls /mnt/nas/homelab/runtime/expense-tracker/data/expenses.db`
- [ ] API responding: `curl https://your-fqdn:8460/health`
- [ ] Web UI loads without errors
- [ ] Can add an expense
- [ ] Can view dashboard
- [ ] Can set a budget

### Command Reference
```bash
# Check if running
docker ps | grep expense-tracker

# View logs
docker logs expense-tracker

# Stop plugin
docker stop expense-tracker

# Restart plugin
docker restart expense-tracker

# View database
sqlite3 /mnt/nas/homelab/runtime/expense-tracker/data/expenses.db

# Check data size
du -sh /mnt/nas/homelab/runtime/expense-tracker/data/
```

---

## 🐛 Troubleshooting

### "Plugin won't start"
```bash
# Check logs
docker logs expense-tracker

# Verify NAS mount
mount | grep nas

# Rebuild and reinstall
homelabctl uninstall-plugin expense-tracker
homelabctl build-plugin plugins/expense-tracker --env-file .env
homelabctl install-plugin build/expense-tracker.v1.0.1.tgz --env-file .env
```

### "Cannot add expenses"
```bash
# Check database permissions
ls -la /mnt/nas/homelab/runtime/expense-tracker/data/

# Check container logs
docker logs expense-tracker

# Verify database is valid
sqlite3 /mnt/nas/homelab/runtime/expense-tracker/data/expenses.db ".tables"
```

### "Slow response / Dashboard stuck"
```bash
# Check container resources
docker stats expense-tracker

# Restart container
docker restart expense-tracker

# Clear browser cache (Chrome DevTools > Network > Disable cache)
```

---

## 📈 Next: Phase 2 Features (Coming Soon)

### Receipt OCR
```
1. Click "Expenses" → Upload receipt
2. App scans image with OCR
3. Extracts: amount $45.99, merchant "Target"
4. Suggests category: "Shopping"
5. One-click confirm
```

### Recurring Auto-Detection
```
1. Add 3+ similar expenses (Netflix $12.99)
2. App detects pattern
3. Suggests: "Create recurring Netflix?"
4. One-click setup
```

### Advanced Insights
```
- Spending trends over time
- Anomaly detection (unusual expenses)
- Category forecasts
- Budget recommendations
```

---

## 💬 Support

### View Logs
```bash
# Real-time logs
docker logs -f expense-tracker

# Last 50 lines
docker logs --tail 50 expense-tracker

# With timestamps
docker logs -t expense-tracker
```

### API Testing
```bash
# Health check
curl https://your-fqdn:8460/health

# List expenses
curl https://your-fqdn:8460/api/expenses/

# Create test expense
curl -X POST https://your-fqdn:8460/api/expenses/ \
  -H "Content-Type: application/json" \
  -d '{"amount": 15.50, "category": "Food", "date": "2024-05-03"}'
```

---

## ✨ Tips for Best Experience

1. **Use Quick Entry on mobile** - Fastest way to log expenses
2. **Review Dashboard weekly** - Stay aware of spending
3. **Set budgets by category** - More granular control
4. **Check Insights tab** - Learn spending patterns
5. **Access from anywhere** - Your data is always in sync
6. **Backup your NAS regularly** - Protects your financial data

---

## 🎉 You're Ready!

Your Expense Tracker is now:
- ✅ Running on your homelab
- ✅ Accessible from phone, PC, Mac
- ✅ Data stored securely on NAS
- ✅ Syncing in real-time across devices
- ✅ Ready for intelligent features (Phase 2+)

**Start tracking! Add your first 10 expenses today.** 💰

---

**Version**: 1.0.0  
**Status**: Production Ready  
**Last Updated**: May 3, 2026
