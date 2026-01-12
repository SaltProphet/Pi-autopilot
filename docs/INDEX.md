# Pi-Autopilot Documentation Index

## 🎯 Start Here

**New to Pi-Autopilot?** → Read [QUICK_START.md](QUICK_START.md) (5 min)

**Deploying to Raspberry Pi?** → Follow [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) (30 min)

**Want to understand the system?** → Review [ARCHITECTURE.md](../ARCHITECTURE.md) (20 min)

---

## 📚 Documentation by Purpose

### For First-Time Users

| Document | Time | Purpose |
|----------|------|---------|
| [QUICK_START.md](QUICK_START.md) | 5 min | Quick reference card with cheat sheet |
| [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) | 30 min | Step-by-step setup & troubleshooting |

### For Operators

| Document | Time | Purpose |
|----------|------|---------|
| [MONITORING.md](MONITORING.md) | 10 min | Using dashboard, checking timers, logs |
| [COMMANDS.md](COMMANDS.md) | 5 min | All systemd commands reference |

### For Developers

| Document | Time | Purpose |
|----------|------|---------|
| [ARCHITECTURE.md](../ARCHITECTURE.md) | 20 min | System design, data flow, cost limits |
| [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) | 15 min | What was built (technical overview) |
| [../SECURITY.md](../SECURITY.md) | 10 min | Security features, file permissions, backups |

### For Project Management

| Document | Time | Purpose |
|----------|------|---------|
| [../IMPLEMENTATION_COMPLETE.md](../IMPLEMENTATION_COMPLETE.md) | 10 min | Deliverables & status |
| [ROADMAP.md](ROADMAP.md) | 5 min | Future enhancements |
| [CHANGELOG.md](CHANGELOG.md) | 5 min | Version history |

---

## 🎮 Quick Command Reference

```bash
# Check timer status
systemctl list-timers pi-autopilot.timer

# View next scheduled run
systemctl status pi-autopilot.timer

# Run pipeline manually (right now)
sudo systemctl start pi-autopilot.service

# Watch pipeline logs
journalctl -fu pi-autopilot.service

# Access dashboard
http://<your-pi-ip>:8000

# View dashboard logs
journalctl -fu pi-autopilot-dashboard.service

# Edit timer schedule
sudo systemctl edit pi-autopilot.timer

# Check costs in database
sqlite3 data/pipeline.db \
  "SELECT ROUND(SUM(usd_cost), 2) FROM cost_tracking;"
```

See [COMMANDS.md](COMMANDS.md) for complete reference.

---

## 🚀 Common Scenarios

### "I want to set up on my Pi for the first time"
1. Read: [QUICK_START.md](QUICK_START.md)
2. Follow: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) → Installation section
3. Execute: `sudo bash installer/setup_pi.sh`

### "The system is running, how do I monitor it?"
1. Check: Dashboard at `http://your-pi-ip:8000`
2. Verify: Timer status with `systemctl list-timers`
3. Review: [MONITORING.md](MONITORING.md) for detailed checks

### "Something went wrong, I need to debug"
1. Check: Recent logs with `journalctl -u pi-autopilot.service`
2. Review: Relevant section in [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
3. Check database: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) → Database queries

### "I want to change how often it runs"
1. Edit: `sudo systemctl edit pi-autopilot.timer`
2. Examples: See [QUICK_START.md](QUICK_START.md) → Configuration
3. Reload: `sudo systemctl daemon-reload`

### "I'm concerned about API costs"
1. Check: Dashboard cost display (real-time)
2. Review: `.env` cost limits (MAX_USD_*)
3. Understand: [ARCHITECTURE.md](../ARCHITECTURE.md) → Cost limit enforcement

### "I need to understand the system architecture"
1. Read: [ARCHITECTURE.md](../ARCHITECTURE.md)
2. Focus: System Architecture diagram
3. Deep dive: Data flow → Cost controls → Performance

---

## 📊 File Structure

```
pi-autopilot/
├── main.py                           ← Main pipeline executor
├── dashboard.py                      ← Web UI (FastAPI)
├── config.py                         ← Settings loader
├── saltprophet.timer                ← Systemd timer config
├── pi-autopilot-dashboard.service   ← Dashboard service config
│
├── agents/                           ← 6-stage pipeline
│   ├── reddit_ingest.py
│   ├── problem_agent.py
│   ├── spec_agent.py
│   ├── content_agent.py
│   ├── verifier_agent.py
│   └── gumroad_agent.py
│
├── services/                         ← Supporting services
│   ├── llm_client.py                ← OpenAI wrapper
│   ├── cost_governor.py             ← Cost tracking & limits
│   ├── storage.py                   ← Database interface
│   ├── audit_logger.py              ← Audit trail
│   └── ...
│
├── models/                           ← Data classes
│   ├── problem.py
│   ├── product_spec.py
│   └── verdict.py
│
├── installer/
│   ├── setup_pi.sh                  ← Full Pi setup
│   ├── setup_dashboard.sh           ← Dashboard setup
│   ├── setup_monitoring.sh          ← Timer setup
│   └── run.sh                        ← Quick start
│
├── docs/
│   ├── INDEX.md                     ← This file
│   ├── QUICK_START.md               ← Quick reference
│   ├── DEPLOYMENT_GUIDE.md          ← Full setup guide
│   ├── MONITORING.md                ← Monitoring guide
│   ├── COMMANDS.md                  ← Command reference
│   ├── ARCHITECTURE.md              ← System design
│   └── ...
│
├── data/
│   ├── pipeline.db                  ← SQLite database
│   └── artifacts/{post_id}/        ← Stage outputs
│
└── requirements.txt                 ← Python dependencies
```

---

## 🔗 Key Pages Quick Links

**Setup & Deployment:**
- [QUICK_START.md](QUICK_START.md) - 5-minute start
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Full setup guide
- installer/setup_pi.sh - Automated installation

**Daily Operations:**
- [COMMANDS.md](COMMANDS.md) - All commands
- [MONITORING.md](MONITORING.md) - How to monitor
- Dashboard: http://your-pi-ip:8000

**Understanding the System:**
- [ARCHITECTURE.md](../ARCHITECTURE.md) - Complete architecture
- [../SECURITY.md](../SECURITY.md) - Security features
- [../SECURITY.md](../SECURITY.md) - Data flow diagrams

**Troubleshooting:**
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md#-troubleshooting) - Troubleshooting section
- [MONITORING.md](MONITORING.md) - Database queries for debugging

---

## ❓ FAQ

**Q: How often does the pipeline run?**  
A: Every hour (configurable via systemd timer). Change with `sudo systemctl edit pi-autopilot.timer`

**Q: How much does it cost?**  
A: Depends on post length. Typical: $0.02-0.05 per run. Hard limit: $5/run, $100 lifetime.

**Q: Can I monitor it remotely?**  
A: Yes! Dashboard at http://your-pi-ip:8000 works from any device on your network.

**Q: What if something crashes?**  
A: Systemd auto-restarts both services. Check logs: `journalctl -u pi-autopilot.service`

**Q: Can I pause the pipeline?**  
A: Yes. `sudo systemctl stop pi-autopilot.timer` stops scheduling.

**Q: How do I change the timer schedule?**  
A: `sudo systemctl edit pi-autopilot.timer` then `sudo systemctl daemon-reload`

**Q: Where are API costs tracked?**  
A: Dashboard shows real-time costs. Database stores details: `sqlite3 data/pipeline.db "SELECT * FROM cost_tracking"`

**Q: Can I run multiple instances?**  
A: Not recommended. Single instance per Pi. For scale, use multiple Pis with separate databases.

---

## 📞 Support

1. **Check logs:** `journalctl -u pi-autopilot.service`
2. **Review docs:** Start with [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
3. **Database queries:** See DEPLOYMENT_GUIDE.md → Database section
4. **Cost issues:** Check `.env` limits and recent costs

---

## ✅ Verify Installation

After setup, run these checks:

```bash
# 1. Timer is enabled
systemctl is-enabled pi-autopilot.timer
→ Should print: enabled

# 2. Dashboard is running
systemctl is-active pi-autopilot-dashboard.service
→ Should print: active

# 3. Dashboard accessible
curl http://localhost:8000 | head -5
→ Should print: <!DOCTYPE html>

# 4. Database exists
ls -la data/pipeline.db
→ Should show file size > 0

# 5. Next scheduled run
systemctl list-timers pi-autopilot.timer
→ Should show future timestamp
```

All passing? ✅ You're ready to go!

---

**Last updated:** 2026-01-12  
**Version:** 2.0 (Timer + Dashboard)
