# Quick Commands Reference

## Dashboard

```bash
# Start dashboard
sudo systemctl start pi-autopilot-dashboard.service

# Stop dashboard
sudo systemctl stop pi-autopilot-dashboard.service

# Check dashboard status
sudo systemctl status pi-autopilot-dashboard.service

# View dashboard logs (live)
journalctl -fu pi-autopilot-dashboard.service

# Access dashboard
http://<pi-ip>:8000
```

## Pipeline & Timer

```bash
# Manually trigger pipeline run (right now)
sudo systemctl start pi-autopilot.service

# Check pipeline status
sudo systemctl status pi-autopilot.service

# View pipeline logs (live)
journalctl -fu pi-autopilot.service

# View last 50 lines of logs
journalctl -n 50 -u pi-autopilot.service

# Check timer status
sudo systemctl status pi-autopilot.timer

# View next scheduled run
systemctl list-timers pi-autopilot.timer

# Edit timer schedule
sudo systemctl edit pi-autopilot.timer

# View timer logs
journalctl -fu pi-autopilot.timer
```

## Database Queries

```bash
# Total posts processed
sqlite3 data/pipeline.db "SELECT COUNT(*) FROM reddit_posts;"

# Total cost (lifetime)
sqlite3 data/pipeline.db "SELECT SUM(usd_cost) as total_cost FROM cost_tracking;"

# Cost breakdown by stage
sqlite3 data/pipeline.db "SELECT action, COUNT(*) FROM audit_log GROUP BY action;"

# Recent errors
sqlite3 data/pipeline.db "SELECT timestamp, action, details FROM audit_log WHERE error_occurred=1 ORDER BY timestamp DESC LIMIT 10;"

# Active posts
sqlite3 data/pipeline.db "SELECT p.id, p.title, pr.stage FROM reddit_posts p LEFT JOIN pipeline_runs pr ON p.id = pr.post_id WHERE pr.status NOT IN ('completed', 'discarded', 'rejected');"

# Cost per run
sqlite3 data/pipeline.db "SELECT run_id, SUM(usd_cost) as run_cost FROM cost_tracking GROUP BY run_id ORDER BY timestamp DESC LIMIT 10;"
```

## Troubleshooting

```bash
# Check service status
sudo systemctl status pi-autopilot.service pi-autopilot-dashboard.service pi-autopilot.timer

# See all Pi-Autopilot services
systemctl list-units --type=service | grep pi-autopilot

# Check if port 8000 is in use
sudo lsof -i :8000

# Restart dashboard
sudo systemctl restart pi-autopilot-dashboard.service

# View all timers
systemctl list-timers --all

# Check Pi-Autopilot service health
sudo systemctl is-active pi-autopilot.service
sudo systemctl is-active pi-autopilot-dashboard.service
sudo systemctl is-active pi-autopilot.timer
```

## Configuration

```bash
# Edit environment variables
sudo nano /opt/pi-autopilot/.env

# Edit timer schedule
sudo systemctl edit pi-autopilot.timer

# Edit dashboard service
sudo systemctl edit pi-autopilot-dashboard.service

# Reload after editing config files
sudo systemctl daemon-reload
```

## Service Management

```bash
# Enable services to start on boot
sudo systemctl enable pi-autopilot.service
sudo systemctl enable pi-autopilot-dashboard.service
sudo systemctl enable pi-autopilot.timer

# Disable services from starting on boot
sudo systemctl disable pi-autopilot.service
sudo systemctl disable pi-autopilot-dashboard.service
sudo systemctl disable pi-autopilot.timer

# Check what's enabled
systemctl is-enabled pi-autopilot.service
systemctl is-enabled pi-autopilot-dashboard.service
systemctl is-enabled pi-autopilot.timer
```

## File Locations

```
/opt/pi-autopilot/                 # Main installation directory
├── main.py                        # Pipeline entry point
├── dashboard.py                   # Web dashboard
├── saltprophet.service            # Pipeline service definition
├── saltprophet.timer              # Timer definition
├── pi-autopilot-dashboard.service # Dashboard service definition
├── .env                           # Configuration (edit this!)
├── data/
│   ├── pipeline.db                # SQLite database
│   └── artifacts/                 # JSON outputs & logs
├── agents/                        # LLM agents (pipeline stages)
├── services/                      # Core services (DB, API, etc)
├── prompts/                       # LLM prompts
├── docs/
│   └── MONITORING.md              # Full monitoring guide
└── installer/
    ├── setup_pi.sh                # Install on Raspberry Pi
    └── setup_dashboard.sh         # Install dashboard only
```

## Log Locations

```bash
# Pipeline logs (systemd journal)
journalctl -u pi-autopilot.service

# Dashboard logs (systemd journal)
journalctl -u pi-autopilot-dashboard.service

# Timer logs (systemd journal)
journalctl -u pi-autopilot.timer

# Error artifacts (on disk)
ls data/artifacts/*/error_logs/

# Full artifact history
ls -la data/artifacts/
```

## System Health Check

```bash
#!/bin/bash
# Quick health check

echo "=== Pi-Autopilot Health Check ==="
echo ""

# Service status
echo "Services:"
sudo systemctl status pi-autopilot.service --no-pager | grep Active
sudo systemctl status pi-autopilot-dashboard.service --no-pager | grep Active
sudo systemctl status pi-autopilot.timer --no-pager | grep Active

# Database check
echo ""
echo "Database:"
sqlite3 data/pipeline.db "SELECT SUM(usd_cost) as total_cost, COUNT(*) as total_runs FROM cost_tracking;"

# Recent errors
echo ""
echo "Recent errors:"
sqlite3 data/pipeline.db "SELECT COUNT(*) FROM audit_log WHERE error_occurred=1 AND timestamp > datetime('now', '-24 hours');"

# Disk space
echo ""
echo "Disk usage:"
du -sh data/

# Port check
echo ""
echo "Dashboard port (8000):"
curl -s http://localhost:8000 > /dev/null && echo "✅ Online" || echo "❌ Offline"
```

Save as `health_check.sh` and run: `bash health_check.sh`

## Advanced: Manual Backup

```bash
# Create backup now
cd /opt/pi-autopilot && python3 -c "from services.backup_manager import BackupManager; print(BackupManager('data/pipeline.db').backup_database())"

# List all backups
ls -lah data/artifacts/backups/

# Restore from backup (CAREFUL!)
cp data/artifacts/backups/pipeline_YYYY-MM-DD_HH-MM-SS.db data/pipeline.db
```

## See Also

- Full monitoring guide: [MONITORING.md](docs/MONITORING.md)
- Security documentation: [SECURITY.md](SECURITY.md)
- Implementation details: [IMPLEMENTATION_SUMMARY.md](docs/IMPLEMENTATION_SUMMARY.md)
