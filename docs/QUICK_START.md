# Pi-Autopilot: Quick Reference Card

## 🎯 System Overview

**What it does:** Automatically monitors Reddit → extracts problems → creates products → uploads to Gumroad

**When it runs:** Every hour (configurable via timer)

**Cost controls:** 3 limits enforced: per-run tokens, per-run USD, lifetime USD

**Where to check:** http://your-pi-ip:8000 (dashboard)

---

## 🚀 Getting Started

### On Your Raspberry Pi

```bash
# 1. One-command setup
sudo bash /opt/pi-autopilot/installer/setup_pi.sh

# 2. Add API keys
sudo nano /opt/pi-autopilot/.env

# 3. Start everything
sudo systemctl start pi-autopilot.timer
sudo systemctl start pi-autopilot-dashboard.service

# 4. Check it works
systemctl list-timers pi-autopilot.timer
```

### Access Dashboard

```
🌐 http://<your-pi-ip>:8000

Shows:
  💰 Lifetime cost (with % bar)
  📊 Last 24h statistics  
  🟢 Pipeline status (completed/rejected/failed)
  📍 Active posts being processed
  🔔 Real-time activity feed
```

---

## 🎮 Command Cheat Sheet

| Goal | Command |
|------|---------|
| Check if running | `systemctl status pi-autopilot.timer` |
| Run now (don't wait) | `sudo systemctl start pi-autopilot.service` |
| View live logs | `journalctl -fu pi-autopilot.service` |
| See next run time | `systemctl list-timers pi-autopilot.timer` |
| Change run frequency | `sudo systemctl edit pi-autopilot.timer` |
| Stop pipeline | `sudo systemctl stop pi-autopilot.timer` |
| Restart dashboard | `sudo systemctl restart pi-autopilot-dashboard` |
| Check dashboard logs | `journalctl -fu pi-autopilot-dashboard` |

---

## 💰 Cost Monitoring

### Dashboard Cost Display

```
┌─────────────────────────────────────────┐
│ Lifetime Cost: $15.42 of $100.00       │
│ ████████░░░░░░░░░░░░░░░░░ 15% used    │
│ Status: 🟢 Safe                         │
└─────────────────────────────────────────┘

At 50% → 🟡 Yellow warning
At 80% → 🔴 Red alert
```

### View Cost Breakdown

```bash
# Total spent
sqlite3 data/pipeline.db \
  "SELECT ROUND(SUM(usd_cost), 2) FROM cost_tracking;"

# Last 5 runs
sqlite3 data/pipeline.db \
  "SELECT timestamp, ROUND(usd_cost, 4) FROM cost_tracking \
   ORDER BY timestamp DESC LIMIT 5;"

# By model
sqlite3 data/pipeline.db \
  "SELECT model, COUNT(*), ROUND(SUM(usd_cost), 2) \
   FROM cost_tracking GROUP BY model;"
```

---

## 📈 Pipeline Stages

1. **Reddit Ingest** → Fetch posts from subreddits
2. **Problem Extract** → Classify if monetizable → ✅/❌ discard
3. **Spec Gen** → Decide product type & price → ✅/❌ reject if confidence <70%
4. **Content Gen** → Write sales copy
5. **Verify** → Quality check → ✅/❌ regenerate if needed
6. **Gumroad Upload** → Publish with Reddit link

**Possible outcomes:**
- ✅ **Completed** → Product uploaded
- ⏭️ **Discarded** → Not a viable problem (stage 2)
- ❌ **Rejected** → Doesn't meet quality thresholds (stage 3)
- ⚠️ **Failed** → Error during processing

---

## ⚙️ Configuration (.env)

```env
# Cost limits (CRITICAL - system halts if exceeded)
MAX_TOKENS_PER_RUN=50000        # Tokens per single run
MAX_USD_PER_RUN=5.0             # USD per single run
MAX_USD_LIFETIME=100.0          # Total USD budget

# Timer schedule (edit with: systemctl edit pi-autopilot.timer)
OnUnitActiveSec=1h              # Every 1 hour
OnBootSec=5min                  # 5 min after boot
Persistent=true                 # Catch up if offline

# API Keys (keep these secret!)
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
OPENAI_API_KEY=...
GUMROAD_ACCESS_TOKEN=...

# Model pricing
OPENAI_INPUT_TOKEN_PRICE=0.00003   # gpt-4
OPENAI_OUTPUT_TOKEN_PRICE=0.00006
```

---

## 🚨 Emergency Actions

### Stop Everything (Kill Switch)

```bash
# Edit .env
sudo nano /opt/pi-autopilot/.env

# Add line:
KILL_SWITCH=true

# Reload
sudo systemctl daemon-reload
```

### Pause Timer (Don't Run)

```bash
sudo systemctl stop pi-autopilot.timer
sudo systemctl disable pi-autopilot.timer
```

### Reset Cost Tracking

```bash
# ⚠️ WARNING: This deletes cost history!
sqlite3 data/pipeline.db "DELETE FROM cost_tracking;"
```

---

## 🔍 Troubleshooting

### "Dashboard shows no posts"
→ Normal if no Reddit posts scored high enough. Wait for next timer run or:
```bash
sudo systemctl start pi-autopilot.service
```

### "Timer not running"
→ Enable it:
```bash
sudo systemctl enable pi-autopilot.timer
sudo systemctl start pi-autopilot.timer
```

### "Dashboard gives error"
→ Check database:
```bash
sqlite3 data/pipeline.db "PRAGMA integrity_check;"
```

### "High cost suddenly"
→ Check token prices in `.env` and recent LLM calls:
```bash
sqlite3 data/pipeline.db "SELECT * FROM cost_tracking ORDER BY timestamp DESC LIMIT 3;"
```

---

## 📊 Sample Dashboard Views

### During a Pipeline Run (every 3 sec refresh)

```
💰 Lifetime Cost: $2.34 (2.3%)
📊 Last 24h: $0.45
✅ Completed: 3
⏭️ Discarded: 7  
❌ Rejected: 1
⚠️ Failed: 0

📍 Active Posts:
  [Post 1] → Spec Generation (stage 3/6)
  [Post 2] → Content Generation (stage 4/6)

🔔 Recent Activity:
  15:32 - problem_extracted
  15:31 - spec_generated
  15:30 - content_generated
```

### Idle (No Active Posts)

```
💰 Lifetime Cost: $15.42 (15.4%) 🟡 Caution
📊 Last 24h: $0.00
✅ Completed: 47
⏭️ Discarded: 312
❌ Rejected: 28
⚠️ Failed: 3

📍 Active Posts: None

🔔 Recent Activity:
  10:00 - gumroad_upload_completed (post_abc123)
  10:00 - verified_successfully
  ...
```

---

## 📞 Useful Links

- Dashboard: `http://<pi-ip>:8000`
- Full Deployment Guide: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- Monitoring Details: [MONITORING.md](MONITORING.md)
- All Commands: [COMMANDS.md](COMMANDS.md)
- Security: [../SECURITY.md](../SECURITY.md)

---

## ✅ Checklist: First Time Setup

- [ ] `.env` filled with API keys
- [ ] `sudo systemctl start pi-autopilot.timer` running
- [ ] `sudo systemctl start pi-autopilot-dashboard.service` running
- [ ] Can access `http://pi-ip:8000` in browser
- [ ] Dashboard shows 0 cost (or previous runs)
- [ ] `systemctl list-timers` shows next scheduled run
- [ ] Manually run: `sudo systemctl start pi-autopilot.service`
- [ ] Check logs: `journalctl -u pi-autopilot.service | head -20`
- [ ] Dashboard updates after run

Done! System is live 🎉
