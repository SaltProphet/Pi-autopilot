# Pi-Autopilot

Fully automated, verifier-first digital product engine for Raspberry Pi.

**Now with systemd automation + real-time dashboard** (hourly scheduling, cost tracking, activity monitoring).

## 🎯 Key Features

✅ **Automated Scheduling** - Systemd timer runs pipeline hourly (configurable)  
✅ **Real-time Dashboard** - Web UI for cost, activity, and status monitoring  
✅ **Cost Controls** - Hard limits prevent runaway API bills  
✅ **Daily Backups** - Automated database backups with retention policies  
✅ **Audit Trail** - Complete operation history for debugging  
✅ **Input Sanitization** - XSS prevention for all external content  

## System Architecture

```
Reddit → Problem Extraction → Spec Generation → Content Generation → Verification → Gumroad Upload
         ↓
    [Systemd Timer: Hourly]
         ↓
    [Real-time Dashboard: Monitoring]
```

Cost governor enforces hard limits at every LLM call.

## 🚀 Quick Start

### Prerequisites

- **Python 3.8+** - Required for running the pipeline
- **Git** - For cloning the repository
- **SSH keys configured with GitHub** (for Pi installation) - Required for automated installation

### Setting up SSH Keys (Required for Pi Installation)

**IMPORTANT**: Before running the automated installer on Raspberry Pi, you MUST configure SSH keys for GitHub authentication.

#### Step 1: Check if you already have SSH keys

```bash
ls -la ~/.ssh/id_*.pub
```

If you see files like `id_rsa.pub` or `id_ed25519.pub`, you already have SSH keys. Skip to Step 3.

#### Step 2: Generate SSH keys (if you don't have them)

```bash
# Generate a new SSH key (use your GitHub email)
ssh-keygen -t ed25519 -C "your_email@example.com"

# When prompted:
# - Press Enter to accept the default file location
# - Enter a passphrase (optional but recommended)
```

#### Step 3: Add your SSH key to GitHub

```bash
# Display your public key
cat ~/.ssh/id_ed25519.pub
# (or cat ~/.ssh/id_rsa.pub if you have an RSA key)

# Copy the entire output
```

Then:
1. Go to GitHub → Settings → SSH and GPG keys: https://github.com/settings/keys
2. Click "New SSH key"
3. Give it a title (e.g., "Raspberry Pi")
4. Paste your public key
5. Click "Add SSH key"

#### Step 4: Test your SSH connection

```bash
ssh -T git@github.com
```

You should see:
```
Hi YourUsername! You've successfully authenticated, but GitHub does not provide shell access.
```

If you see this message, you're ready to run the installer!

### Installation Options

#### Option 1: Automated Installation with SSH (Raspberry Pi - Recommended)

**Best for**: Production deployment on Raspberry Pi with SSH keys already configured

**Prerequisites**: SSH keys must be configured (see above)

```bash
# Clone the repository
git clone git@github.com:SaltProphet/Pi-autopilot.git
cd Pi-autopilot

# Run the automated installer (requires sudo)
sudo bash installer/setup_pi.sh
```

#### Option 1b: Automated Installation with HTTPS (Raspberry Pi - Alternative)

**Best for**: Users who prefer Personal Access Token (PAT) over SSH keys

**Prerequisites**: GitHub Personal Access Token with 'repo' scope

To create a PAT:
1. Go to: https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Give it a name (e.g., "Pi-Autopilot")
4. Select scope: **repo** (Full control of private repositories)
5. Click "Generate token" and copy it (you won't see it again!)

```bash
# Clone the repository (you can use HTTPS here too with your PAT)
git clone https://github.com/SaltProphet/Pi-autopilot.git
cd Pi-autopilot

# Run the HTTPS installer (will prompt for PAT)
sudo bash installer/setup_with_https.sh
```

**What the automated installers do:**
- Install system dependencies (Python 3, pip, venv, git)
- Create installation at `/opt/pi-autopilot`
- Set up Python virtual environment
- Install all Python dependencies
- Create data directories with proper permissions
- Configure systemd services (pipeline + dashboard)
- Set up timer for hourly pipeline runs
- Configure daily database backups

**After installation:**
1. Edit `/opt/pi-autopilot/.env` with your API keys
2. Test the pipeline: `sudo systemctl start pi-autopilot.service`
3. Access dashboard: `http://<pi-ip>:8000`
4. Check timer status: `systemctl list-timers pi-autopilot.timer`

#### Option 2: Manual Installation (Development/Local)

**Recommended for development, testing, or non-Pi systems**

```bash
# 1. Clone the repository
git clone https://github.com/SaltProphet/Pi-autopilot.git
cd Pi-autopilot

# 2. Create a Python virtual environment
python3 -m venv venv

# 3. Activate the virtual environment
# On Linux/Mac:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# 4. Upgrade pip
pip install --upgrade pip

# 5. Install dependencies
pip install -r requirements.txt

# 6. Create data directories
mkdir -p data/artifacts

# 7. Configure environment
cp .env.example .env
# Edit .env with your API keys (see Configuration section)

# 8. Run the pipeline manually
python main.py

# 9. (Optional) Start the dashboard
python dashboard.py
# Access at http://localhost:8000
```

### Essential Commands

#### Pipeline Management

```bash
# Run pipeline once (manual)
python main.py

# Run with virtual environment (if not activated)
./venv/bin/python main.py

# Run in dry-run mode (no real Gumroad uploads)
# Set DRY_RUN=true in .env first
python main.py
```

#### Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate          # Linux/Mac
venv\Scripts\activate              # Windows

# Deactivate virtual environment
deactivate

# Install/update dependencies
pip install -r requirements.txt

# Upgrade specific package
pip install --upgrade openai
```

#### Dashboard

```bash
# Start dashboard (development)
python dashboard.py

# Start with specific host/port
python dashboard.py --host 0.0.0.0 --port 8000

# Access dashboard
# Local: http://localhost:8000
# Remote: http://<your-ip>:8000
```

#### Systemd Service Management (Pi Installation)

```bash
# View service status
systemctl status pi-autopilot.service
systemctl status pi-autopilot-dashboard.service

# Start/stop services
sudo systemctl start pi-autopilot.service
sudo systemctl stop pi-autopilot.service
sudo systemctl restart pi-autopilot-dashboard.service

# Enable/disable automatic startup
sudo systemctl enable pi-autopilot.timer
sudo systemctl disable pi-autopilot.timer

# View logs (follow mode)
journalctl -fu pi-autopilot.service
journalctl -fu pi-autopilot-dashboard.service

# View recent logs
journalctl -u pi-autopilot.service -n 100

# Check timer schedule
systemctl list-timers pi-autopilot.timer

# Manually trigger pipeline
sudo systemctl start pi-autopilot.service

# Reload systemd after config changes
sudo systemctl daemon-reload
```

#### Database Management

```bash
# View database
sqlite3 data/pipeline.db

# Check lifetime cost
sqlite3 data/pipeline.db "SELECT SUM(usd_cost) FROM cost_tracking;"

# List recent pipeline runs
sqlite3 data/pipeline.db "SELECT * FROM pipeline_runs ORDER BY created_at DESC LIMIT 10;"

# Count posts by status
sqlite3 data/pipeline.db "SELECT status, COUNT(*) FROM pipeline_runs GROUP BY status;"

# Reset cost tracking (use with caution)
sqlite3 data/pipeline.db "DELETE FROM cost_tracking;"
```

#### Testing

```bash
# Run all tests
SKIP_CONFIG_VALIDATION=1 pytest tests/

# Run specific test file
SKIP_CONFIG_VALIDATION=1 pytest tests/test_storage.py -v

# Run with coverage
SKIP_CONFIG_VALIDATION=1 pytest tests/ --cov=services --cov=agents

# Run only unit tests
SKIP_CONFIG_VALIDATION=1 pytest tests/ -m unit
```

#### Troubleshooting

```bash
# Check Python version
python3 --version

# Verify virtual environment is activated
which python        # Should show path to venv/bin/python

# List installed packages
pip list

# Check for missing dependencies
pip check

# View environment variables
cat .env

# Check file permissions
ls -la .env data/

# Test API connectivity
python -c "from services.reddit_client import RedditClient; print('Reddit OK')"
python -c "from openai import OpenAI; print('OpenAI OK')"
```

### Access Dashboard

After installation, the dashboard is live at:

```
http://<your-pi-ip>:8000
```

Real-time monitoring of:
- 💰 Cost tracking (lifetime + last 24h)
- ✅ Pipeline stats (completed/discarded/rejected)
- 📍 Active posts being processed
- 📋 Recent activity feed

## 🔐 Configuration Management

Pi-Autopilot includes a web-based configuration interface for managing API keys and settings.

### Accessing the Configuration UI

```bash
# Start the dashboard
python dashboard.py

# Navigate to:
http://localhost:8000/config
```

### Security Best Practices

1. **HTTPS or Localhost Only**: Only access the config UI over HTTPS or from localhost
2. **Password Protection** (optional): Set `DASHBOARD_PASSWORD` in `.env` to require authentication
3. **IP Whitelisting** (optional): Set `DASHBOARD_ALLOWED_IPS` to restrict access
4. **File Permissions**: The `.env` file is automatically secured with 0o600 permissions

### Features

- ✅ Secure API key input with masked display
- ✅ Test API keys before saving
- ✅ Toggle services on/off without deleting keys
- ✅ Automatic backups before every change
- ✅ Restore from previous backups
- ✅ Input validation and error handling
- ✅ Audit logging of all changes

### Configuration Backups

Backups are stored in `./config_backups/` with timestamps. The system keeps the last 7 backups automatically.

## Configuration

Edit `.env` or use the web interface at `http://localhost:8000/config`:

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

### Custom Timer Schedule

Edit timer to change frequency:

```bash
sudo systemctl edit pi-autopilot.timer
```

Options:
```ini
# Every 30 minutes
OnUnitActiveSec=30min

# Every 6 hours
OnUnitActiveSec=6h

# Daily at 2 AM
OnCalendar=*-*-* 02:00:00
```

Then reload:
```bash
sudo systemctl daemon-reload
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

### Dry Run Mode

Test the system safely without making real Gumroad uploads:

```bash
# In .env (enabled by default on installation)
DRY_RUN=true
```

When enabled:
- Pipeline runs normally through all stages
- Reddit posts are processed
- LLM calls generate content
- Gumroad uploads are **simulated** (no real products created)
- All artifacts and logs are created
- Console shows "[DRY RUN]" prefix for uploads

**To enable real uploads:** Set `DRY_RUN=false` in `.env`

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

- **[docs/SYSTEM_PIPELINE_OVERVIEW.md](docs/SYSTEM_PIPELINE_OVERVIEW.md)** - **Complete system pipeline, functions, and outcomes** (START HERE for comprehensive understanding)
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

### Installation Issues

**SSH Authentication Failed During Installation:**

If you see errors like:
```
remote: Invalid username or token. Password authentication is not supported for Git operations.
fatal: Authentication failed for 'https://github.com/SaltProphet/Pi-autopilot.git/'
```

Or:
```
ERROR: SSH authentication to GitHub failed
```

**Solution 1: Set up SSH keys properly**
1. Check if you have SSH keys:
   ```bash
   ls -la ~/.ssh/id_*.pub
   ```

2. If no keys exist, generate one:
   ```bash
   ssh-keygen -t ed25519 -C "your_email@example.com"
   ```

3. Add your public key to GitHub:
   ```bash
   cat ~/.ssh/id_ed25519.pub
   ```
   Copy the output and add it at: https://github.com/settings/keys

4. Test the connection:
   ```bash
   ssh -T git@github.com
   ```
   You should see: "Hi YourUsername! You've successfully authenticated..."

5. Re-run the installer:
   ```bash
   sudo bash installer/setup_pi.sh
   ```

**Solution 2: Use HTTPS installer with Personal Access Token**

If SSH is not working or you prefer using PAT:
1. Create a Personal Access Token at: https://github.com/settings/tokens
2. Select scope: **repo**
3. Run the HTTPS installer:
   ```bash
   sudo bash installer/setup_with_https.sh
   ```

**"Could not detect the actual user" error:**
- Don't run the script directly as root
- Always use: `sudo bash installer/setup_pi.sh` (not `sudo su` then run script)

**SSH keys exist but authentication still fails:**
- Verify the key is added to your GitHub account: https://github.com/settings/keys
- Check SSH agent is running:
  ```bash
  eval "$(ssh-agent -s)"
  ssh-add ~/.ssh/id_ed25519
  ```
- Test manually:
  ```bash
  ssh -Tv git@github.com
  ```

### Runtime Issues

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
