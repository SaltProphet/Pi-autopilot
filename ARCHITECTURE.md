# System Architecture & Data Flow

## 🏗️ Complete System Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        Pi-Autopilot: Full System                             │
└──────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ SCHEDULER TIER (Systemd)                                                    │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │ pi-autopilot.timer                                               │      │
│  │ ────────────────────────────────────────────────────────────     │      │
│  │ Triggers every hour (configurable)                              │      │
│  │ OnBootSec=5min                                                  │      │
│  │ OnUnitActiveSec=1h                                              │      │
│  │ Persistent=true (catches up if offline)                         │      │
│  └────────────────────┬─────────────────────────────────────────────┘      │
│                       │                                                     │
│                       │ (triggers at scheduled time)                        │
│                       ↓                                                     │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │ pi-autopilot.service (Type=oneshot)                              │      │
│  │ ────────────────────────────────────────────────────────────     │      │
│  │ ExecStart=/venv/bin/python /opt/pi-autopilot/main.py            │      │
│  │ Runs once, finishes, returns to idle                            │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│ PIPELINE TIER (Batch Processing)                                            │
│                                                                             │
│  main.py Execution Flow:                                                   │
│  ─────────────────────────────────────────────────────────────────          │
│                                                                             │
│  1️⃣  REDDIT_INGEST                                                          │
│      └─→ Fetch posts from configured subreddits                            │
│         └─→ Filter by REDDIT_MIN_SCORE (default: 10)                       │
│            └─→ Store raw JSON to reddit_posts table                        │
│               └─→ Save to: data/artifacts/{post_id}/                       │
│                                                                             │
│  2️⃣  PROBLEM_EXTRACTION                                                     │
│      └─→ For each unprocessed post:                                        │
│         └─→ Call LLM: "Is this monetizable?"                               │
│            └─→ Classify: discard? urgency score?                           │
│               ├─→ If discard=true: Skip remaining stages ⏭️               │
│               └─→ Save: data/artifacts/{post_id}/problem_{ts}.json         │
│                                                                             │
│  3️⃣  SPEC_GENERATION                                                        │
│      └─→ For each accepted problem:                                        │
│         └─→ Call LLM: Decide product type (guide/template/pack)           │
│            └─→ Compute: price + confidence score                           │
│               ├─→ If build=false OR confidence<70: Reject ❌              │
│               ├─→ If len(deliverables)<3: Reject ❌                        │
│               └─→ Save: data/artifacts/{post_id}/spec_{ts}.json            │
│                                                                             │
│  4️⃣  CONTENT_GENERATION                                                     │
│      └─→ For each approved spec:                                           │
│         └─→ Call LLM: Write structured sales copy                          │
│            └─→ Route through InputSanitizer (XSS prevention)              │
│               └─→ Save: data/artifacts/{post_id}/content_{ts}.md           │
│                                                                             │
│  5️⃣  VERIFICATION                                                           │
│      └─→ For each generated content:                                       │
│         └─→ Call LLM: "Is this ready to sell?"                            │
│            ├─→ If regeneration_needed=true:                               │
│            │   └─→ Call Content Gen again (max: MAX_REGENERATION_ATTEMPTS) │
│            ├─→ Save: data/artifacts/{post_id}/verdict_{attempt}.json      │
│            └─→ If pass=true: Proceed to upload                            │
│                                                                             │
│  6️⃣  GUMROAD_UPLOAD                                                         │
│      └─→ For each verified product:                                        │
│         └─→ Format listing (title, description, deliverables)              │
│            └─→ Add Reddit source link (transparency)                       │
│               └─→ Call Gumroad API: Create product                         │
│                  └─→ Log success in audit_log                              │
│                                                                             │
│  💰 COST CONTROL (Every LLM Call):                                          │
│      ────────────────────────────────────                                   │
│      Before calling LLM:                                                    │
│        1. Estimate tokens: input + output                                   │
│        2. Check: tokens < MAX_TOKENS_PER_RUN?                              │
│        3. Check: cost < MAX_USD_PER_RUN?                                   │
│        4. Check: cost < MAX_USD_LIFETIME (persisted)?                      │
│        └─→ If any limit exceeded: Abort run, log to audit_log              │
│                                                                             │
│  📊 LOGGING (Every Stage):                                                  │
│      ─────────────────────                                                  │
│        • Save to: data/artifacts/{post_id}/{stage}_{ts}.json                │
│        • Log to: pipeline_runs (stage, status, artifact_path)               │
│        • Log to: cost_tracking (tokens_sent, tokens_received, usd_cost)    │
│        • Log to: audit_log (action, post_id, details, error_occurred)      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│ DATA TIER (Persistent Storage)                                              │
│                                                                             │
│  data/pipeline.db (SQLite):                                                │
│  ─────────────────────────────────────────────────────────────────          │
│                                                                             │
│  ┌─ reddit_posts ──────────────────────────────────────────┐               │
│  │ • id (PK)                                              │               │
│  │ • title, body, author, subreddit, score, url           │               │
│  │ • raw_json, timestamp                                  │               │
│  └────────────────────────────────────────────────────────┘               │
│           │                                                                │
│           │ (one post to many pipeline runs)                              │
│           ↓                                                                │
│  ┌─ pipeline_runs ─────────────────────────────────────────┐               │
│  │ • id (PK)                                              │               │
│  │ • post_id (FK), stage, status (completed/rejected)     │               │
│  │ • artifact_path, error_message, created_at             │               │
│  └────────────────────────────────────────────────────────┘               │
│                                                                             │
│  ┌─ cost_tracking ──────────────────────────────────────────┐              │
│  │ • id (PK)                                              │               │
│  │ • run_id, tokens_sent, tokens_received, usd_cost       │               │
│  │ • model, timestamp                                     │               │
│  │ (Dashboard queries this for cost display)              │               │
│  └────────────────────────────────────────────────────────┘               │
│                                                                             │
│  ┌─ audit_log ──────────────────────────────────────────────┐              │
│  │ • id (PK)                                              │               │
│  │ • action, post_id, run_id, details (JSON)              │               │
│  │ • error_occurred (bool), cost_limit_exceeded (bool)     │               │
│  │ • timestamp                                            │               │
│  │ (Dashboard queries this for activity feed)             │               │
│  └────────────────────────────────────────────────────────┘               │
│                                                                             │
│  data/artifacts/{post_id}/ (JSON/Markdown):                               │
│  ─────────────────────────────────────────────────────────────             │
│  problem_{ts}.json                  (from stage 2)                         │
│  spec_{ts}.json                     (from stage 3)                         │
│  content_{ts}.md                    (from stage 4)                         │
│  verdict_attempt_{n}.json           (from stage 5)                         │
│  error_logs/{stage}_{ts}.json        (error contexts)                      │
│                                                                             │
│  Purpose: Enable recovery without re-running prior stages                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│ DASHBOARD TIER (Monitoring & Visualization)                                 │
│                                                                             │
│  pi-autopilot-dashboard.service (Always Running):                          │
│  ─────────────────────────────────────────────────────────────────          │
│                                                                             │
│  ExecStart=/venv/bin/python dashboard.py                                   │
│  Type=simple                                                               │
│  Restart=on-failure                                                        │
│  RestartSec=10 (if crashes, restart in 10 sec)                             │
│                                                                             │
│                                                                             │
│  Dashboard Web Server (FastAPI):                                           │
│  ───────────────────────────────────────────────────                       │
│                                                                             │
│  GET / → Returns HTML5 page with:                                          │
│         • Inline CSS (responsive design)                                   │
│         • Inline JavaScript (WebSocket-optional)                           │
│         • Auto-refresh every 3 seconds                                     │
│                                                                             │
│  GET /api/stats → JSON                                                    │
│      └─→ cost_tracking: lifetime, last 24h, remaining                      │
│         └─→ SELECT SUM(usd_cost), SUM(tokens_*) FROM cost_tracking         │
│         └─→ Returns: {cost, tokens, pipeline stats}                        │
│                                                                             │
│  GET /api/activity → JSON (Last 20 entries)                                │
│      └─→ SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 20          │
│         └─→ Returns: [{timestamp, action, post_id, error}]                 │
│                                                                             │
│  GET /api/posts → JSON (Active posts)                                      │
│      └─→ SELECT ... FROM reddit_posts JOIN pipeline_runs                   │
│         └─→ Filter: WHERE status NOT IN (completed, discarded, rejected)   │
│         └─→ Returns: [{post_id, title, stage, status}]                     │
│                                                                             │
│  Port: 8000 (default)                                                      │
│  Access: http://<your-pi-ip>:8000                                          │
│                                                                             │
│  Dashboard UI Features:                                                    │
│  ──────────────────────────                                                │
│  • Cost tracking with progress bar                                        │
│  • Pipeline statistics (6 metric cards)                                    │
│  • Active posts table (real-time)                                          │
│  • Recent activity feed (error highlighting)                               │
│  • Color-coded status badges                                               │
│  • Mobile-responsive layout                                                │
│  • Zero-dependency design (no external CDN)                                │
│                                                                             │
│  Dashboard Data Flow:                                                      │
│  ────────────────────                                                      │
│  Browser (every 3 sec):                                                    │
│    ├─→ fetch(/api/stats) ──→ Query cost_tracking                           │
│    ├─→ fetch(/api/activity) ──→ Query audit_log                            │
│    └─→ fetch(/api/posts) ──→ Query pipeline_runs                           │
│                                                                             │
│       Render HTML ──→ Display metrics                                      │
│       ↓                                                                     │
│  Repeat in 3 seconds                                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│ SYSTEM STARTUP SEQUENCE                                                     │
│                                                                             │
│ 1. System Boot                                                              │
│    ↓                                                                        │
│ 2. Systemd loads pi-autopilot.timer                                        │
│    └─→ Schedules first run: OnBootSec=5min                                 │
│    └─→ Schedules recurring: OnUnitActiveSec=1h                             │
│    ↓                                                                        │
│ 3. Systemd loads pi-autopilot-dashboard.service                            │
│    └─→ Starts python dashboard.py                                          │
│    └─→ Binds to http://0.0.0.0:8000                                        │
│    ↓                                                                        │
│ 4. 5 minutes pass → Timer triggers                                         │
│    ↓                                                                        │
│ 5. pi-autopilot.service starts                                             │
│    └─→ Runs main.py (entire 6-stage pipeline)                              │
│    └─→ Logs go to journalctl                                               │
│    └─→ Data written to database                                            │
│    ↓                                                                        │
│ 6. Service completes (oneshot = finishes)                                  │
│    ↓                                                                        │
│ 7. Dashboard continuously queries database                                  │
│    └─→ Every 3 seconds: refresh metrics                                    │
│    ↓                                                                        │
│ 8. Timer waits 1 hour, triggers again → Go to step 5                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│ COST LIMIT ENFORCEMENT                                                      │
│                                                                             │
│ Three layers (all checked BEFORE API call):                                │
│                                                                             │
│ Layer 1: Per-Run Token Limit                                               │
│ ─────────────────────────────────                                           │
│ if estimated_tokens > MAX_TOKENS_PER_RUN:                                  │
│    └─→ Raise CostLimitExceeded                                             │
│        └─→ Log to audit_log                                                │
│        └─→ Skip remaining posts in this run                                │
│        └─→ Try again next hour                                             │
│                                                                             │
│ Layer 2: Per-Run USD Limit                                                 │
│ ────────────────────────────                                                │
│ if estimated_cost > MAX_USD_PER_RUN:                                       │
│    └─→ Raise CostLimitExceeded                                             │
│        └─→ Log to audit_log                                                │
│        └─→ Same behavior as Layer 1                                        │
│                                                                             │
│ Layer 3: Lifetime USD Limit (Persisted)                                    │
│ ───────────────────────────────────────                                     │
│ SELECT SUM(usd_cost) FROM cost_tracking                                    │
│ if lifetime_spent > MAX_USD_LIFETIME:                                      │
│    └─→ Raise CostLimitExceeded                                             │
│        └─→ Log to audit_log                                                │
│        └─→ ABORT ENTIRE PIPELINE                                           │
│        └─→ User must manually investigate                                   │
│                                                                             │
│ Example Flow:                                                              │
│ ──────────────                                                              │
│ 1. LLMClient.call_structured() called                                      │
│ 2. Estimate tokens: input + output_max                                     │
│ 3. Calculate cost: (input * INPUT_PRICE) + (output * OUTPUT_PRICE)         │
│ 4. Check all 3 limits ← CostGovernor                                       │
│ 5. If OK: Make API call                                                    │
│ 6. Record actual usage from response                                       │
│ 7. If OK: Continue to next post                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Dashboard Screenshot (Text Representation)

```
╔════════════════════════════════════════════════════════════════════════════╗
║                     🚀 Pi-Autopilot Dashboard                             ║
║                     Real-time pipeline monitoring                          ║
╚════════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────────────┐
│                          💰 Lifetime Cost                                  │
│                           $15.42 of $100.00                                │
│ ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 15% used  🟢 Safe         │
└─────────────────────────────────────────────────────────────────────────────┘

┌────────────────┬────────────────┬────────────────┬────────────────┐
│  📊 Last 24h   │  ✅ Completed  │  ⏭️ Discarded  │  ❌ Rejected   │
│  Cost: $0.45   │  Count: 12     │  Count: 47     │  Count: 8      │
└────────────────┴────────────────┴────────────────┴────────────────┘

┌────────────────┬────────────────┐
│  ⚠️ Failed     │  🔴 Max Run    │
│  Count: 2      │  $5.00/run     │
└────────────────┴────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 📍 Active Posts                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│ Title                              Score  Stage              Status        │
├─────────────────────────────────────────────────────────────────────────────┤
│ How to build a profitable SaaS...  287    Problem Extract   in_progress    │
│ Best framework for React apps       156    Content Gen        in_progress   │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 🔔 Recent Activity                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ 15:45  gumroad_upload_completed     (post_xyz123)                           │
│ 15:44  verified_successfully        (post_xyz123)                           │
│ 15:43  content_generated            (post_xyz123)                           │
│ 15:42  spec_generated               (post_xyz123) - confidence: 89%         │
│ 15:41  problem_extracted            (post_xyz123) - urgency: 92             │
│ 15:40  post_ingested                (from SideProject subreddit)            │
│ 14:45  post_discarded               ⚠️ not_monetizable                      │
└─────────────────────────────────────────────────────────────────────────────┘

Auto-refreshes every 3 seconds
```

---

## 🔄 Deployment Flow

```
Raspberry Pi Setup:
─────────────────

1. User runs installer
   └─→ sudo bash installer/setup_pi.sh

2. Installer steps:
   ├─→ Update apt packages
   ├─→ Install Python 3 + venv
   ├─→ Clone/update repo
   ├─→ Create venv
   ├─→ pip install -r requirements.txt
   ├─→ Copy saltprophet.timer → /etc/systemd/system/
   ├─→ Copy pi-autopilot-dashboard.service → /etc/systemd/system/
   ├─→ systemctl daemon-reload
   ├─→ systemctl enable both services
   └─→ systemctl start both services

3. Systemd takes over:
   ├─→ Dashboard starts listening on :8000
   ├─→ Timer starts scheduling runs
   └─→ Both auto-restart on failure

4. User sets up config:
   └─→ Edit /opt/pi-autopilot/.env
       (add API keys)

5. System runs automatically:
   └─→ Every hour: timer triggers pipeline
       ├─→ Pipeline runs all 6 stages
       ├─→ Results saved to database
       ├─→ Dashboard displays results
       └─→ Repeat next hour

6. User monitors:
   └─→ Open browser
       └─→ http://your-pi-ip:8000
          └─→ See live metrics
             └─→ Check costs
                └─→ Review activity feed
```

---

## 🎯 Key Design Decisions

### Why Separate Processes?

| Component | Type | Why Separate |
|-----------|------|-------------|
| Timer | Systemd | Reliable, built-in, no external deps |
| Pipeline | Oneshot service | Runs when triggered, finishes cleanly |
| Dashboard | Long-running service | Needs to stay online 24/7 |

**Benefit:** Each can fail independently without breaking others.

### Why FastAPI?

- ✅ Lightweight (no heavy framework overhead)
- ✅ Built-in JSON serialization
- ✅ Async-ready (future WebSocket support)
- ✅ Single-file deployment (dashboard.py)
- ✅ No database ORM needed (direct SQLite queries)

### Why Auto-Refresh Every 3 Seconds?

- ✅ Fast enough to see real-time activity
- ✅ Slow enough to not hammer database
- ✅ Works on slow Pi network (no lag)

### Why Database Queries in Dashboard?

- ✅ Pipeline never blocked by dashboard
- ✅ Dashboard can crash without affecting pipeline
- ✅ Multiple dashboards can view same database
- ✅ Historical data available for queries

---

## 📈 Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| Pipeline run time | ~5-10 min | Depends on LLM response time |
| Dashboard startup | <1 sec | FastAPI is fast |
| Dashboard memory | ~50 MB | Python + FastAPI + SQLite |
| Database query time | <100 ms | SQLite on local disk |
| Dashboard refresh latency | <500 ms | Auto-refresh every 3 sec |
| Cost per run (typical) | $0.02-0.05 | Depends on post length |

---

## 🛡️ Reliability Features

✅ **Auto-restart on failure**
- If pipeline crashes: Timer will trigger again in 1 hour
- If dashboard crashes: Systemd restarts it in 10 seconds

✅ **Persistent storage**
- All data saved to SQLite (survives reboots)
- Cost tracking persists (lifetime limit still enforced)

✅ **Audit trail**
- Every action logged with timestamps
- Error tracking for debugging
- No silent failures

✅ **Error recovery**
- Artifacts saved at each stage
- Can resume from any stage
- No need to re-run prior stages

✅ **Cost controls**
- 3-layer enforcement prevents bill shock
- Automatic abort if limits exceeded
- Detailed logging of all costs
