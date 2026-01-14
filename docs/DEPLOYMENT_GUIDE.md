# Pi-Autopilot: Complete Deployment & Testing Guide

## ✅ Implementation Summary

All components have been successfully implemented:

- ✅ **Systemd Timer** - Automatically runs pipeline on schedule (hourly)
- ✅ **Real-time Dashboard** - Web UI with live cost tracking & activity feed
- ✅ **Cost Monitoring** - Visual alerts at 50%/80% lifetime spend thresholds
- ✅ **Auto-recovery** - Systemd auto-restart on service failure
- ✅ **Database Logging** - Full audit trail in SQLite

---

## 🚀 Quick Start

### Local Development Testing

```bash
# 1. Set up Python environment
cd /workspaces/Pi-autopilot
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment (copy and edit)
cp .env.example .env
# Edit .env with your API keys

# 4. Initialize database (run main.py once to create tables)
python main.py

# 5. Start dashboard locally
python dashboard.py
# Access at: http://localhost:8000
```

### On Raspberry Pi (Automated)

#### Prerequisites

Ensure SSH keys are configured for GitHub:

```bash
# Generate SSH key (if needed) - replace with your GitHub email
ssh-keygen -t ed25519 -C "<your_email@example.com>"

# View your public key
cat ~/.ssh/id_ed25519.pub

# Add this key to GitHub: https://github.com/settings/keys

# Test SSH connection
ssh -T git@github.com
```

#### Installation

```bash
# Clone the repository with SSH
git clone git@github.com:SaltProphet/Pi-autopilot.git
cd Pi-autopilot

# Run the all-in-one installer
sudo bash installer/setup_pi.sh

# Edit configuration
sudo nano /opt/pi-autopilot/.env

# Verify installation
sudo systemctl status pi-autopilot.timer
sudo systemctl status pi-autopilot-dashboard.service
```

---

## 📊 Dashboard Features

### Real-Time Metrics (Auto-refresh every 3 seconds)

| Metric | Purpose | Alert Threshold |
|--------|---------|-----------------|
| **Lifetime Cost** | Total $ spent on API calls | 🔴 80% of `MAX_USD_LIFETIME` |
| **Last 24h Cost** | Daily spending | 📊 Informational only |
| **Completed** | Successfully uploaded products | ✅ Tracked only |
| **Discarded** | Not monetizable (filtered) | 📊 Tracked only |
| **Rejected** | Failed quality gates | ❌ Confidence <70% or <3 deliverables |
| **Failed** | Errors during processing | ⚠️ Check artifact logs |
| **Active Posts** | Currently processing | 📍 Real-time status |
| **Recent Activity** | Audit trail | 🔍 Last 20 actions |

### Cost Warning System

```
0% ─────────────────────── 50% ─────────────────────── 80% ───── 100%
     🟢 Green (Safe)     🟡 Yellow (Caution)    🔴 Red (Danger!)
```

At **80% lifetime spend**, a red warning badge appears and you should review spending before next pipeline run.

---

## 🔧 Configuration

All settings are in `.env`:

```env
# Cost Controls (CRITICAL)
MAX_TOKENS_PER_RUN=50000          # Abort if single run exceeds this
MAX_USD_PER_RUN=5.0               # Abort if single run costs more
MAX_USD_LIFETIME=100.0            # Hard limit across all runs

# Timer Schedule (in saltprophet.timer)
OnUnitActiveSec=1h                # Run every 1 hour (edit to change)
OnBootSec=5min                    # First run 5 min after boot
Persistent=true                   # Catch-up if system was off

# Dashboard
# Default: http://0.0.0.0:8000
# Change port: edit dashboard.py line 516: uvicorn.run(..., port=8001)
```

---

## 🎮 Common Operations

### Check if Everything is Running

```bash
# Timer status
sudo systemctl status pi-autopilot.timer

# Pipeline service
sudo systemctl status pi-autopilot.service

# Dashboard service
sudo systemctl status pi-autopilot-dashboard.service

# Next scheduled run
systemctl list-timers pi-autopilot.timer

# All system timers
systemctl list-timers
```

### Manually Trigger Pipeline

```bash
# Run immediately (don't wait for timer)
sudo systemctl start pi-autopilot.service

# Watch it run (live logs)
journalctl -fu pi-autopilot.service
```

### View Pipeline Logs

```bash
# Last 20 lines
journalctl -n 20 -u pi-autopilot.service

# Last hour of logs
journalctl -u pi-autopilot.service --since "1 hour ago"

# Follow logs in real-time
journalctl -fu pi-autopilot.service
```

### View Dashboard Logs

```bash
# Live logs
journalctl -fu pi-autopilot-dashboard.service

# Last 50 lines
journalctl -n 50 -u pi-autopilot-dashboard.service
```

### Modify Timer Schedule

```bash
# Interactive editor (don't edit /etc/systemd/system/ directly!)
sudo systemctl edit pi-autopilot.timer

# Example changes:
# Every 30 minutes: OnUnitActiveSec=30min
# Every 4 hours: OnUnitActiveSec=4h
# Daily at 2 AM: OnCalendar=*-*-* 02:00:00

# Reload after changes
sudo systemctl daemon-reload
sudo systemctl restart pi-autopilot.timer
```

### Stop/Pause the Pipeline

```bash
# Disable timer (won't run again until re-enabled)
sudo systemctl disable pi-autopilot.timer
sudo systemctl stop pi-autopilot.timer

# Stop running pipeline immediately
sudo systemctl stop pi-autopilot.service

# Pause just the dashboard
sudo systemctl stop pi-autopilot-dashboard.service
```

### Emergency Brake

If something is wrong and you want to freeze everything immediately:

```bash
# Set KILL_SWITCH=true in .env
sudo nano /opt/pi-autopilot/.env

# Or temporarily
sudo systemctl mask pi-autopilot.service
sudo systemctl mask pi-autopilot.timer
```

---

## 📈 Monitoring Database Directly

### Check Cost Tracking

```bash
sqlite3 data/pipeline.db

# Total lifetime cost
SELECT ROUND(SUM(usd_cost), 2) as total_cost FROM cost_tracking;

# Cost breakdown by model
SELECT model, ROUND(SUM(usd_cost), 2) as cost, COUNT(*) as calls 
FROM cost_tracking GROUP BY model;

# Last 10 API calls with costs
SELECT timestamp, model, tokens_sent, tokens_received, usd_cost 
FROM cost_tracking ORDER BY timestamp DESC LIMIT 10;
```

### Check Pipeline Status

```bash
# Recently processed posts
SELECT post_id, stage, status, created_at FROM pipeline_runs 
ORDER BY created_at DESC LIMIT 20;

# Posts stuck in a stage
SELECT post_id, stage, COUNT(*) FROM pipeline_runs 
GROUP BY post_id, stage HAVING COUNT(*) > 1;

# Success rate (last 24h)
SELECT 
  status,
  COUNT(*) as count,
  ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM pipeline_runs WHERE created_at > datetime('now', '-1 day')), 1) as percent
FROM pipeline_runs 
WHERE created_at > datetime('now', '-1 day')
GROUP BY status;
```

### Check Audit Trail

```bash
# Recent errors
SELECT timestamp, action, post_id, error_occurred, details 
FROM audit_log WHERE error_occurred = 1 
ORDER BY timestamp DESC LIMIT 10;

# Actions in last hour
SELECT action, COUNT(*) as count FROM audit_log 
WHERE timestamp > datetime('now', '-1 hour') 
GROUP BY action;
```

---

## 🐛 Troubleshooting

### Dashboard Shows "No Active Posts"

✅ **Normal** - Pipeline runs once per hour and finishes in minutes. You'll only see active posts during that window.

Check if posts exist:
```bash
sqlite3 data/pipeline.db "SELECT COUNT(*) FROM reddit_posts;"
```

If 0, run pipeline manually:
```bash
sudo systemctl start pi-autopilot.service
```

### Dashboard Shows High Lifetime Cost

1. Check your `.env` settings:
   ```bash
   grep MAX_USD /opt/pi-autopilot/.env
   ```

2. Review cost per run:
   ```bash
   sqlite3 data/pipeline.db \
     "SELECT timestamp, ROUND(usd_cost, 4) FROM cost_tracking ORDER BY timestamp DESC LIMIT 5;"
   ```

3. If model price is wrong:
   ```bash
   # Edit .env
   OPENAI_INPUT_TOKEN_PRICE=0.00003   # gpt-4
   OPENAI_OUTPUT_TOKEN_PRICE=0.00006
   ```

### Timer Not Running

Check timer status:
```bash
sudo systemctl status pi-autopilot.timer
systemctl list-timers pi-autopilot.timer
```

If inactive, enable and start:
```bash
sudo systemctl enable pi-autopilot.timer
sudo systemctl start pi-autopilot.timer
```

### Dashboard Crashes on Startup

Check for database issues:
```bash
# Verify database exists and is readable
ls -la /opt/pi-autopilot/data/pipeline.db

# Check for corruption
sqlite3 /opt/pi-autopilot/data/pipeline.db "PRAGMA integrity_check;"

# Restore from backup if corrupted
sudo bash /opt/pi-autopilot/scripts/restore_backup.sh
```

### Pipeline Runs But Doesn't Upload to Gumroad

Check logs for API errors:
```bash
journalctl -u pi-autopilot.service | grep -i gumroad
```

Verify token is valid:
```bash
grep GUMROAD_ACCESS_TOKEN /opt/pi-autopilot/.env
```

---

## 📋 Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                   Pi-Autopilot System                   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Systemd Timer (hourly)                               │
│       ↓                                                │
│  ┌─────────────────────┐                              │
│  │  main.py (oneshot)  │ ← triggered by timer         │
│  │  · Reddit Ingest    │                              │
│  │  · Extract Problem  │                              │
│  │  · Gen Spec         │                              │
│  │  · Gen Content      │                              │
│  │  · Verify           │                              │
│  │  · Upload Gumroad   │                              │
│  └─────────────────────┘                              │
│       ↓                                                │
│  ┌─────────────────────┐                              │
│  │  SQLite Database    │  ← stores costs, audit log   │
│  │  · pipeline.db      │                              │
│  └─────────────────────┘                              │
│       ↓                                                │
│  ┌─────────────────────┐                              │
│  │  dashboard.py       │ ← web UI (always running)    │
│  │  (separate process) │                              │
│  │  · FastAPI server   │                              │
│  │  · http://pi:8000   │                              │
│  └─────────────────────┘                              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Key Design:**
- Timer runs pipeline on schedule
- Pipeline stores all results in database
- Dashboard reads database (no direct access to pipeline)
- Each component can restart independently
- Cost limits enforced before every LLM call

---

## 🎯 Success Criteria

After deployment, verify:

- [ ] Dashboard accessible at `http://<pi-ip>:8000`
- [ ] Dashboard shows 0 errors initially
- [ ] Timer is enabled: `systemctl is-enabled pi-autopilot.timer` → `enabled`
- [ ] Next run scheduled: `systemctl list-timers pi-autopilot.timer` shows future date
- [ ] At least one successful pipeline run completes
- [ ] Dashboard displays cost breakdown (even if $0.00)
- [ ] Can manually trigger: `sudo systemctl start pi-autopilot.service`
- [ ] Logs flow to journalctl: `journalctl -u pi-autopilot.service` shows recent entries

---

## 📞 Support

For issues, check:

1. **Logs:** `journalctl -fu pi-autopilot.service`
2. **Database:** `sqlite3 data/pipeline.db "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 1;"`
3. **Config:** `cat /opt/pi-autopilot/.env` (mask API keys!)
4. **Artifacts:** `ls -lh data/artifacts/*/` (check for error logs)

See [MONITORING.md](MONITORING.md) for detailed troubleshooting.
