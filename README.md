# Pi-Autopilot

Fully automated, verifier-first digital product engine for Raspberry Pi.

**Now with enterprise-grade security hardening** (backup, audit logging, API resilience, input sanitization).

## System Architecture

```
Reddit → Problem Extraction → Spec Generation → Content Generation → Verification → Gumroad Upload
```

Cost governor enforces hard limits at every LLM call.

## 🔒 Security Features

✅ **Configuration Validation** - Validates all required settings on startup  
✅ **Daily Backups** - Automated database backups with 7-day/4-week/12-month retention  
✅ **Error Logging** - Full exception context logged to immutable artifacts  
✅ **Input Sanitization** - XSS prevention for Gumroad listings  
✅ **API Resilience** - Exponential backoff retry logic for transient failures  
✅ **Audit Trail** - Complete operation history for compliance & debugging  
✅ **File Permissions** - 0600 on secrets, 0700 on directories  

→ See [SECURITY.md](SECURITY.md) for detailed security documentation

## Installation

### On Raspberry Pi

```bash
sudo bash installer/setup_pi.sh
```

Edit `/opt/pi-autopilot/.env` with your API credentials.

### Manual Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your credentials

mkdir -p data/artifacts
```

## Configuration

Edit `.env`:

```env
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=Pi-Autopilot/2.0

OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4

GUMROAD_ACCESS_TOKEN=your_gumroad_access_token

DATABASE_PATH=./data/pipeline.db
ARTIFACTS_PATH=./data/artifacts

REDDIT_SUBREDDITS=SideProject,Entrepreneur,startups
REDDIT_MIN_SCORE=10
REDDIT_POST_LIMIT=20

MAX_REGENERATION_ATTEMPTS=1

MAX_TOKENS_PER_RUN=50000
MAX_USD_PER_RUN=5.0
MAX_USD_LIFETIME=100.0

KILL_SWITCH=false

OPENAI_INPUT_TOKEN_PRICE=0.00003
OPENAI_OUTPUT_TOKEN_PRICE=0.00006
```

## Cost Controls

### Hard Limits

Three levels of protection:

1. **Per-Run Token Limit** (`MAX_TOKENS_PER_RUN`)
   - Default: 50,000 tokens
   - Includes input + output tokens
   - Pipeline aborts when exceeded

2. **Per-Run USD Limit** (`MAX_USD_PER_RUN`)
   - Default: $5.00
   - Estimated cost based on token usage
   - Pipeline aborts when exceeded

3. **Lifetime USD Limit** (`MAX_USD_LIFETIME`)
   - Default: $100.00
   - Cumulative across all runs
   - Persists in SQLite database
   - Pipeline aborts when exceeded

### Cost Tracking

All LLM calls tracked in `cost_tracking` table:
- Input/output tokens
- USD cost
- Timestamp
- Model used
- Abort reasons

View lifetime cost:
```sql
sqlite3 data/pipeline.db "SELECT SUM(usd_cost) FROM cost_tracking;"
```

### Abort Behavior

When any limit is exceeded:
1. Pipeline stops immediately
2. No regeneration attempts
3. Failure written to `data/artifacts/abort_{run_id}.json`
4. Database records abort reason
5. Current post marked as `cost_limit_exceeded`

Abort file format:
```json
{
  "run_id": 1234567890,
  "abort_reason": "MAX_USD_PER_RUN exceeded: 5.12 > 5.0",
  "run_tokens_sent": 25000,
  "run_tokens_received": 18000,
  "run_cost": 5.12,
  "timestamp": 1234567890
}
```

### Kill Switch

Emergency stop without deleting data:

```bash
# In .env
KILL_SWITCH=true
```

When enabled:
- Pipeline exits immediately
- No Reddit ingestion
- No LLM calls
- No Gumroad uploads
- Database and artifacts preserved

### Token Pricing

Configure per-token costs:

```env
OPENAI_INPUT_TOKEN_PRICE=0.00003
OPENAI_OUTPUT_TOKEN_PRICE=0.00006
```

Defaults are for GPT-4. Adjust for other models.

### Cost Estimation

Before each LLM call:
1. Estimate input tokens (text length / 3.5)
2. Use max_tokens for output estimate
3. Calculate estimated USD cost
4. Check against all limits
5. Refuse call if any limit would be exceeded

After each LLM call:
1. Record actual token usage from response
2. Calculate actual USD cost
3. Update run totals
4. Write to cost_tracking table

### Resetting Lifetime Cost

To reset cumulative cost tracking:

```bash
sqlite3 data/pipeline.db "DELETE FROM cost_tracking;"
```

Or delete specific runs:

```bash
sqlite3 data/pipeline.db "DELETE FROM cost_tracking WHERE run_id = 1234567890;"
```

## Usage

Run the complete pipeline:

```bash
python main.py
```

The pipeline executes sequentially:

1. Ingest Reddit posts from configured subreddits
2. Extract problems from posts (discard if not monetizable)
3. Generate product specifications (reject if confidence < 70)
4. Generate product content
5. Verify content quality (max 1 regeneration attempt)
6. Generate Gumroad listing
7. Upload to Gumroad

## Pipeline Rules

- Verifier-first: Content must pass verification or get discarded
- One regeneration: If content fails verification, regenerate once
- Hard discard: If second attempt fails, permanently discard
- Cost limits: Any LLM call that would exceed limits is refused
- Sequential execution: No parallel processing
- Disk-based state: All artifacts saved to disk
- JSON between modules: All inter-agent communication uses JSON

## File Structure

```
/
├─ main.py                    # Pipeline orchestrator
├─ config.py                  # Configuration management
├─ requirements.txt           # Python dependencies
├─ .env.example              # Environment template
├─ installer/
│  ├─ setup_pi.sh            # Raspberry Pi setup script
│  └─ run.sh                 # Manual run script
├─ prompts/
│  ├─ problem_extraction.txt
│  ├─ product_spec.txt
│  ├─ verifier.txt
│  ├─ product_content.txt
│  └─ gumroad_listing.txt
├─ agents/
│  ├─ reddit_ingest.py       # Reddit ingestion
│  ├─ problem_agent.py       # Problem extraction
│  ├─ spec_agent.py          # Spec generation
│  ├─ verifier_agent.py      # Quality verification
│  ├─ content_agent.py       # Content generation
│  └─ gumroad_agent.py       # Gumroad upload
├─ services/
│  ├─ llm_client.py          # OpenAI API client
│  ├─ reddit_client.py       # Reddit API client
│  ├─ gumroad_client.py      # Gumroad API client
│  ├─ storage.py             # SQLite storage
│  ├─ cost_governor.py       # Cost control & limits
│  ├─ config_validator.py    # Config validation (NEW)
│  ├─ backup_manager.py      # Database backups (NEW)
│  ├─ error_handler.py       # Error logging (NEW)
│  ├─ sanitizer.py           # Input sanitization (NEW)
│  ├─ retry_handler.py       # API retry logic (NEW)
│  └─ audit_logger.py        # Audit trail (NEW)
└─ models/
   ├─ problem.py             # Problem model
   ├─ product_spec.py        # Product spec model
   └─ verdict.py             # Verification verdict model
```

## Documentation

- [SECURITY.md](SECURITY.md) - Security features and hardening
- [docs/CHANGELOG.md](docs/CHANGELOG.md) - Version history
- [docs/ROADMAP.md](docs/ROADMAP.md) - Feature roadmap (Q1-Q4 2026)
- [docs/IMPLEMENTATION_OUTLINE.md](docs/IMPLEMENTATION_OUTLINE.md) - Technical architecture
- [docs/IMPLEMENTATION_SUMMARY.md](docs/IMPLEMENTATION_SUMMARY.md) - Implementation details

## Artifacts

All pipeline artifacts are saved to `./data/artifacts/{post_id}/`:

- `problem_*.json` - Extracted problems
- `spec_*.json` - Product specifications
- `content_*.md` - Generated product content
- `verdict_attempt_*.json` - Verification results
- `gumroad_upload_*.json` - Upload results
- `error_*.json` - Exception logs with full context

Backups and cost tracking:

- `backups/pipeline_db_*.sqlite.gz` - Daily database backups
- `abort_{run_id}.json` - Cost limit failures

## Systemd Timer

After running `setup_pi.sh`, the pipeline runs every 6 hours automatically.

Check status:
```bash
systemctl status pi-autopilot.timer
```

View logs:
```bash
journalctl -u pi-autopilot.service -f
```

Manual trigger:
```bash
systemctl start pi-autopilot.service
```

## API Keys

### Reddit
1. Go to https://www.reddit.com/prefs/apps
2. Create app (script type)
3. Copy client ID and secret

### OpenAI
1. Visit https://platform.openai.com/api-keys
2. Create new key
3. Copy key

### Gumroad
1. Go to Settings → Advanced → Applications
2. Create application
3. Generate access token
4. Copy token

## Verification Logic

Content must pass all checks:

- `example_quality_score >= 7`
- `generic_language_detected == false`
- `missing_elements == []`

If any check fails, content is regenerated once. If second attempt fails, the post is permanently discarded.

## Rejection Criteria

Posts are rejected at various stages:

**Problem Extraction:**
- `discard == true` (not monetizable)
- No economic consequence
- Generic complaints

**Spec Generation:**
- `build == false`
- `confidence < 70`
- `deliverables.length < 3`
- Generic target audience

**Verification:**
- Poor example quality
- Generic language detected
- Missing required sections
- Two failed attempts

**Cost Limits:**
- Token limit exceeded
- Per-run USD limit exceeded
- Lifetime USD limit exceeded

## Database Schema

**reddit_posts:**
- id, title, body, timestamp, subreddit, author, score, url, raw_json

**pipeline_runs:**
- id, post_id, stage, status, artifact_path, error_message, created_at

**cost_tracking:**
- id, run_id, tokens_sent, tokens_received, usd_cost, timestamp, model, abort_reason

## Troubleshooting

**No posts ingested:**
- Check Reddit credentials in `.env`
- Lower `REDDIT_MIN_SCORE` threshold
- Verify subreddit names are correct

**All posts discarded:**
- Check OpenAI API key
- Review `problem_*.json` artifacts
- Adjust subreddit targets to more entrepreneurial communities

**Verification always fails:**
- Check `verdict_*.json` for specific reasons
- Review `content_*.md` for quality issues
- Consider adjusting prompts in `/prompts`

**Gumroad upload fails:**
- Verify `GUMROAD_ACCESS_TOKEN` is correct
- Check Gumroad account status
- Review `gumroad_upload_*.json` for error details

**Pipeline aborts with cost limit:**
- Check `abort_{run_id}.json` for exact reason
- Review `cost_tracking` table in database
- Adjust limits in `.env` if needed
- Consider reducing `REDDIT_POST_LIMIT`

**Kill switch not working:**
- Ensure `KILL_SWITCH=true` (not "True" or "1")
- Restart service after changing `.env`
- Check logs for "KILL SWITCH ACTIVE" message

## Production Notes

- Run on Raspberry Pi 3B+ or newer
- Requires stable internet connection
- Runs headless and unattended
- All decisions logged to SQLite
- All artifacts preserved on disk
- No manual intervention required
- Cost limits prevent runaway spending
- Kill switch allows emergency stop

## License

See LICENSE file.
