# Pi-Autopilot: Systemd Timer & Dashboard Setup

## Overview

This guide sets up:
1. **Systemd Timer** - Automatically runs the pipeline on a schedule (hourly by default)
2. **Real-time Dashboard** - Web UI for monitoring costs, activity, and status

## Installation on Raspberry Pi

### Quick Setup (Recommended)

```bash
cd /opt/pi-autopilot
sudo bash installer/setup_pi.sh
```

This will:
- Install the pipeline service
- Install the timer
- Install the dashboard service
- Enable all services to start on boot

### Manual Setup

#### Step 1: Install Timer

```bash
sudo cp saltprophet.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pi-autopilot.timer
sudo systemctl start pi-autopilot.timer
```

Check timer status:
```bash
systemctl list-timers pi-autopilot.timer
```

View next scheduled run:
```bash
systemctl status pi-autopilot.timer
```

#### Step 2: Install Dashboard

```bash
sudo cp pi-autopilot-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pi-autopilot-dashboard.service
sudo systemctl start pi-autopilot-dashboard.service
```

Check dashboard status:
```bash
sudo systemctl status pi-autopilot-dashboard.service
```

View dashboard logs:
```bash
journalctl -fu pi-autopilot-dashboard
```

## Using the Dashboard

### Access the Web UI

After starting the dashboard service:

```
http://<your-pi-ip>:8000
```

Example: `http://192.168.1.100:8000`

### Dashboard Features

**Cost Tracking:**
- Lifetime cost (with progress bar toward `MAX_USD_LIFETIME`)
- Last 24h cost
- Cost status warning at 80% threshold

**Pipeline Stats (Last 24h):**
- ✅ Completed products
- ⏭️ Discarded posts (not monetizable)
- ❌ Rejected posts (failed quality gates)
- ⚠️ Failed posts (errors)

**Active Posts:**
- Real-time list of posts being processed
- Current stage (problem extraction, spec, content, etc.)
- Post score and subreddit
- Last activity timestamp

**Recent Activity Feed:**
- Chronological log of all pipeline actions
- Error indicators
- Timestamps

The dashboard **auto-refreshes every 3 seconds** with the latest data.

## Scheduling

### Timer Configuration

The default timer (`saltprophet.timer`) runs:
- 5 minutes after system boot
- Every 1 hour thereafter
- Persists missed runs (if system was offline)

### Custom Schedule

Edit the timer to change frequency:

```bash
sudo systemctl edit pi-autopilot.timer
```

Common intervals:
```ini
# Every 30 minutes
OnUnitActiveSec=30min

# Every 6 hours
OnUnitActiveSec=6h

# Every day at 2 AM
OnCalendar=*-*-* 02:00:00
```

After editing:
```bash
sudo systemctl daemon-reload
sudo systemctl restart pi-autopilot.timer
```

### Manual Trigger

Run the pipeline immediately (without waiting for timer):

```bash
sudo systemctl start pi-autopilot.service
```

View current run:
```bash
journalctl -fu pi-autopilot
```

## Monitoring

### Check Pipeline Logs

```bash
# Last 50 lines
journalctl -n 50 -fu pi-autopilot

# Last 24 hours
journalctl --since "24 hours ago" -u pi-autopilot

# With timestamps and full messages
journalctl -o short-full -u pi-autopilot
```

### Check Dashboard Logs

```bash
journalctl -fu pi-autopilot-dashboard
```

### View Timer Status

```bash
# Next scheduled run
systemctl list-timers pi-autopilot.timer

# Detailed timer info
systemctl status pi-autopilot.timer

# Timer logs
journalctl -u pi-autopilot.timer -f
```

### Query Database Directly

```bash
# Total posts processed
sqlite3 data/pipeline.db "SELECT COUNT(*) FROM reddit_posts;"

# Cost summary
sqlite3 data/pipeline.db "SELECT SUM(usd_cost) FROM cost_tracking;"

# Recent activity
sqlite3 data/pipeline.db "SELECT timestamp, action, post_id FROM audit_log ORDER BY timestamp DESC LIMIT 10;"
```

## Troubleshooting

### Dashboard Won't Start

```bash
# Check service status
sudo systemctl status pi-autopilot-dashboard.service

# Check logs
journalctl -u pi-autopilot-dashboard.service -n 50

# Try starting manually
sudo /opt/pi-autopilot/venv/bin/python /opt/pi-autopilot/dashboard.py

# Check if port 8000 is in use
sudo lsof -i :8000
```

### Timer Not Running

```bash
# Check timer status
systemctl status pi-autopilot.timer

# Check if service exists
ls -la /etc/systemd/system/pi-autopilot.service

# Verify syntax
systemd-analyze verify /etc/systemd/system/pi-autopilot.timer

# Check timer state
systemctl list-timers --all pi-autopilot.timer
```

### High CPU/Memory Usage

The dashboard fetches data every 3 seconds. If this is too frequent:

Edit [dashboard.py](../dashboard.py), line with `REFRESH_INTERVAL`:
```python
REFRESH_INTERVAL = 5000  # 5 seconds instead of 3
```

Then restart:
```bash
sudo systemctl restart pi-autopilot-dashboard
```

### Database Locked Error

If you see "database is locked":
```bash
# The database is being used by another process
# Wait a moment and try again, or check active processes:
lsof data/pipeline.db
```

## Cost Control Integration

The dashboard displays costs in real-time:

| Limit | Default | Setting |
|-------|---------|---------|
| Per-run token limit | 50,000 | `MAX_TOKENS_PER_RUN` |
| Per-run USD limit | $5 | `MAX_USD_PER_RUN` |
| Lifetime USD limit | $100 | `MAX_USD_LIFETIME` |

**Dashboard warnings:**
- 🟡 Yellow when lifetime cost > 50% of limit
- 🔴 Red when lifetime cost > 80% of limit

Once lifetime cost exceeds `MAX_USD_LIFETIME`, the pipeline **automatically halts** to prevent further charges.

## Service Management

### Enable/Disable Timer

```bash
# Enable timer (runs on boot)
sudo systemctl enable pi-autopilot.timer

# Disable timer (don't run on boot)
sudo systemctl disable pi-autopilot.timer

# Start timer now
sudo systemctl start pi-autopilot.timer

# Stop timer
sudo systemctl stop pi-autopilot.timer
```

### Enable/Disable Dashboard

```bash
sudo systemctl enable pi-autopilot-dashboard.service
sudo systemctl disable pi-autopilot-dashboard.service
sudo systemctl start pi-autopilot-dashboard.service
sudo systemctl stop pi-autopilot-dashboard.service
```

### View All Services

```bash
systemctl list-units --type=service | grep pi-autopilot
systemctl list-timers | grep pi-autopilot
```

## Network Access (Remote Monitoring)

If accessing dashboard from another computer:

### Find Pi's IP Address

```bash
hostname -I
```

Then access dashboard at:
```
http://<pi-ip>:8000
```

### Restrict Access (Optional Security)

The dashboard currently serves on `0.0.0.0` (all interfaces). To restrict to localhost only:

Edit [dashboard.py](../dashboard.py):
```python
uvicorn.run(app, host="127.0.0.1", port=8000)  # localhost only
```

Then restart:
```bash
sudo systemctl restart pi-autopilot-dashboard
```

## Advanced: Custom Dashboard Port

Default port is 8000. To change it:

```bash
sudo systemctl edit pi-autopilot-dashboard.service
```

Add under `[Service]`:
```ini
Environment="DASHBOARD_PORT=9000"
```

Then in [dashboard.py](../dashboard.py), change port in `uvicorn.run()` call and restart.

## Integration Examples

### Slack Alerts (Optional Add-on)

Modify [dashboard.py](../dashboard.py) to send alerts:
```python
import requests

def send_slack_alert(message):
    webhook = os.getenv('SLACK_WEBHOOK_URL')
    if webhook:
        requests.post(webhook, json={'text': message})
```

### Email Alerts (Optional Add-on)

```python
import smtplib

def send_email_alert(subject, body):
    smtp_server = os.getenv('SMTP_SERVER')
    # ... email code ...
```

These can be triggered when `stats.cost.lifetime > MAX_USD_LIFETIME * 0.8`.

## Next Steps

1. ✅ Install timer: `sudo systemctl start pi-autopilot.timer`
2. ✅ Install dashboard: `sudo systemctl start pi-autopilot-dashboard.service`
3. ✅ Access dashboard: `http://<pi-ip>:8000`
4. ✅ Configure schedule: `systemctl edit pi-autopilot.timer`
5. ✅ Set cost alerts: See integration examples above

---

For issues or questions, check logs with `journalctl -fu pi-autopilot` or `journalctl -fu pi-autopilot-dashboard`.
