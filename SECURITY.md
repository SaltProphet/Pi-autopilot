# Security Features & Hardening

This document outlines the security features and hardening measures implemented in Pi-Autopilot.

## Table of Contents

1. [Configuration Validation](#configuration-validation)
2. [Database Backups](#database-backups)
3. [Error Handling & Logging](#error-handling--logging)
4. [Input Sanitization](#input-sanitization)
5. [API Resilience](#api-resilience)
6. [Audit Logging](#audit-logging)
7. [File Permissions](#file-permissions)
8. [Deployment Security](#deployment-security)

---

## Configuration Validation

**Module:** `services/config_validator.py`

Validates all required configuration on startup, preventing silent failures due to misconfiguration.

### Validations Performed

- **Required fields:** All API keys, credentials, and essential settings
- **API key formats:** Regex validation for OpenAI (48 hex chars), Reddit (client ID/secret), Gumroad token
- **Numeric ranges:** Cost limits (USD), token budgets must be positive integers within bounds
- **Path accessibility:** Database and artifacts directories must be writable
- **Subreddit names:** Comma-separated list format validation

### Error Handling

If validation fails, a detailed error message is displayed before the pipeline starts:

```
CONFIGURATION ERROR:
  - OPENAI_API_KEY: Invalid format (must be 48 hex characters)
  - REDDIT_CLIENT_ID: Missing required field
```

### Integration

Automatic validation on startup via `config.py`:

```python
validator = ConfigValidator(settings)
validator.validate_or_raise()
```

---

## Database Backups

**Module:** `services/backup_manager.py`

Automated daily backups with multi-tier retention policy for disaster recovery.

### Backup Schedule

| Frequency | Retention | Purpose |
|-----------|-----------|---------|
| Daily | 7 backups | Recent recovery |
| Weekly | 4 backups | Historical snapshots |
| Monthly | 12 backups | Long-term archival |

### Features

- **Compression:** Gzip compression reduces backup size
- **Permissions:** 0600 (owner read/write only) on all backups
- **Verification:** SQLite header integrity check on restore
- **Timestamped:** Filename includes ISO timestamp for easy identification
- **Auto-cleanup:** Enforces retention policy automatically

### Backup Location

```
data/artifacts/backups/
├── pipeline_db_2026-01-12T143022.sqlite.gz
├── pipeline_db_2026-01-11T143022.sqlite.gz
└── ...
```

### Disaster Recovery

```bash
# Restore from backup
./scripts/restore_backup.sh data/artifacts/backups/pipeline_db_2026-01-12T143022.sqlite.gz

# The script will:
# 1. Create a safety backup of current database
# 2. Restore from the specified backup
# 3. Verify integrity
# 4. Display recovery status
```

### Automatic Daily Backups

Cron job runs daily at 2 AM:

```bash
0 2 * * * /opt/pi-autopilot/venv/bin/python -c \
  "from services.backup_manager import BackupManager; \
   BackupManager('./data/pipeline.db').backup_database()"
```

---

## Error Handling & Logging

**Module:** `services/error_handler.py`

Captures all exceptions with full context for debugging and pattern detection.

### Error Categorization

**Transient Errors** (automatically retried with backoff):
- `TimeoutError` - Request timeout
- `ConnectionError` - Network connectivity issues
- `OSError` - System-level network errors
- API errors: 429 (rate limit), 500-503 (server errors)

**Fatal Errors** (logged and skipped):
- `ValueError` - Invalid input
- `TypeError` - Type mismatch
- `KeyError` - Missing data
- API errors: 400 (bad request), 401 (auth failure)

### Error Artifacts

All exceptions are logged to JSON artifacts:

```json
{
  "unix_timestamp": 1704969600.123,
  "error_type": "TimeoutError",
  "categorization": {
    "is_transient": true,
    "category": "api_timeout",
    "suggested_action": "retry_with_backoff"
  },
  "traceback": "Traceback (most recent call last):\n...",
  "python_version": "3.11.4",
  "context": {
    "post_id": "xyz123",
    "stage": "content_generation",
    "additional": {...}
  }
}
```

### Artifact Storage

```
data/artifacts/{post_id}/
├── error_1704969600.json
├── error_1704969700.json
└── ...
```

Artifacts have **0600 permissions** (owner read/write only).

---

## Input Sanitization

**Module:** `services/sanitizer.py`

Sanitizes user-generated content from Reddit and Gumroad to prevent XSS, injection, and prompt injection attacks.

### Sanitization Contexts

#### 1. Reddit Content (`sanitize_reddit_content`)

Applied to Reddit post bodies before LLM processing:

- Removes control characters (`\x00`-`\x1f` except `\n`)
- Decodes HTML entities (`&lt;` → `<`, `&amp;` → `&`)
- Removes null bytes (SQLite-unsafe)
- Preserves normal text for LLM processing

#### 2. Gumroad Listings (`sanitize_gumroad_content`)

Applied to product titles and descriptions before upload:

- Escapes HTML entities (`<` → `&lt;`, `&` → `&amp;`)
- Removes script tags: `<script>`, `</script>`
- Removes dangerous tags: `<iframe>`, `<object>`, `<embed>`, `<form>`
- Removes event handlers: `onclick=`, `onerror=`, `onfocus=`, `onload=`
- Removes javascript: protocol and data: URI schemes
- Escapes dangerous attributes

#### 3. Database Content (`sanitize_database_content`)

Applied before storing in SQLite:

- Removes null bytes (`\x00`)
- Validates UTF-8 encoding
- Prevents SQL injection through proper escaping

### XSS Prevention

Blocks these attack vectors:

```
<script>alert('xss')</script>           ✗ Blocked
<img src=x onerror="alert('xss')">      ✗ Blocked
<svg onload=alert('xss')>               ✗ Blocked
<iframe src="evil.com"></iframe>        ✗ Blocked
<a href="javascript:alert(1)">Click</a> ✗ Blocked
<base href="javascript:alert(1)">       ✗ Blocked
```

### Integration Points

- **problem_agent.py:** Sanitizes Reddit post bodies
- **content_agent.py:** Sanitizes generated product content
- **gumroad_agent.py:** Sanitizes title and description before upload

---

## API Resilience

**Module:** `services/retry_handler.py`

Automatically retries transient API failures with exponential backoff.

### Retry Strategies

| API | Max Attempts | Initial Backoff | Max Backoff | Multiplier |
|-----|--------------|-----------------|------------|-----------|
| OpenAI | 4 | 2s | 60s | 2x |
| Reddit | 3 | 3s | 30s | 2x |
| Gumroad | 3 | 2s | 30s | 2x |

### Backoff Schedule

Example (OpenAI):
```
Attempt 1: Fails → Wait 2s
Attempt 2: Fails → Wait 4s
Attempt 3: Fails → Wait 8s
Attempt 4: Fails → Wait 16s
Then: Raise exception (max attempts exceeded)
```

### Transient vs Fatal

**Transient (retried):**
- `TimeoutError`
- `ConnectionError`
- HTTP 429, 500-503

**Fatal (not retried):**
- `ValueError`, `TypeError`
- HTTP 400, 401
- Invalid credentials

### Integration Points

- **llm_client.py:** OpenAI API calls
- **reddit_client.py:** Reddit API calls
- **gumroad_client.py:** Gumroad API calls

---

## Audit Logging

**Module:** `services/audit_logger.py`

Immutable audit trail of all pipeline operations for compliance, debugging, and usage analysis.

### Tracked Actions

```
post_ingested            → Reddit post fetched
problem_extracted        → Problem analysis complete
spec_generated           → Product spec created
content_generated        → Product content written
content_verified         → Quality check passed
content_rejected         → Quality check failed
gumroad_listed           → Product listed on Gumroad
gumroad_uploaded         → Final upload successful
post_discarded           → Post rejected (not monetizable)
cost_limit_exceeded      → Budget exhausted
error_occurred           → Exception caught
```

### Audit Schema

```sql
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,        -- ISO 8601 UTC
    action TEXT NOT NULL,            -- Enum: above actions
    post_id TEXT,                    -- From Reddit
    run_id TEXT,                     -- From pipeline
    details TEXT,                    -- JSON blob
    error_occurred INTEGER DEFAULT 0, -- Boolean flag
    cost_limit_exceeded INTEGER DEFAULT 0 -- Boolean flag
);

CREATE INDEX idx_audit_post_id ON audit_log(post_id);
CREATE INDEX idx_audit_action ON audit_log(action);
CREATE INDEX idx_audit_timestamp_desc ON audit_log(timestamp DESC);
```

### Query Examples

```python
from services.audit_logger import AuditLogger

audit_logger = AuditLogger('data/pipeline.db')

# Get all operations for a post
history = audit_logger.get_post_history('post_abc123')

# Get all operations in a run
run_history = audit_logger.get_run_history('run_xyz789')

# Get recent errors
errors = audit_logger.get_recent_errors(limit=10, hours=24)

# Get human-readable timeline
timeline = audit_logger.get_timeline('post_abc123')
```

### Immutability

The audit log is **immutable** - no delete, update, or truncate operations are provided. This ensures a permanent record for compliance and forensic analysis.

---

## File Permissions

**Security Model:** Principle of least privilege

### Permission Enforcement

| File/Directory | Permissions | Purpose |
|----------------|-------------|---------|
| `.env` | 0600 (rw-------) | API keys accessible to owner only |
| `data/pipeline.db` | 0600 (rw-------) | Database accessible to owner only |
| `data/` | 0700 (rwx------) | Directory operations owner only |
| `data/artifacts/` | 0700 (rwx------) | Artifacts owner only |
| Backup files | 0600 (rw-------) | Backups owner only |

### Automatic Enforcement

Permissions are set during installation:

```bash
# In installer/setup_pi.sh
chmod 600 .env
chmod 600 data/pipeline.db
chmod 700 data data/artifacts data/artifacts/backups
```

### Verification

```bash
# Check permissions
ls -la .env
# -rw------- 1 root root 1234 Jan 12 20:15 .env

ls -ld data/
# drwx------ 2 root root 4096 Jan 12 20:15 data/
```

---

## Deployment Security

### Pre-Deployment Checklist

- [ ] Review `.env` file - ensure no test credentials in production
- [ ] Verify file permissions: `ls -la .env data/`
- [ ] Test configuration: `python main.py` (should validate on startup)
- [ ] Run test suite: `pytest tests/test_*.py -v`
- [ ] Check cron job: `crontab -l | grep pi-autopilot`
- [ ] Verify systemd timer: `systemctl status pi-autopilot.timer`

### Installation

```bash
# On Raspberry Pi (requires sudo)
sudo ./installer/setup_pi.sh

# The script will:
# 1. Install system dependencies
# 2. Clone repository
# 3. Create Python virtual environment
# 4. Install Python dependencies
# 5. Create data directories with correct permissions
# 6. Setup systemd service and timer
# 7. Setup daily backup cron job
```

### Monitoring

Check logs for security events:

```bash
# View systemd logs
journalctl -u pi-autopilot.service -f

# View backup logs
tail -f /var/log/pi-autopilot-backup.log

# Check recent errors
sqlite3 data/pipeline.db "SELECT * FROM audit_log WHERE error_occurred=1 ORDER BY timestamp DESC LIMIT 10;"
```

### Incident Response

**If API credentials are compromised:**

1. Immediately rotate the credential (in service dashboard)
2. Update `.env` with new credential
3. Restart service: `systemctl restart pi-autopilot.service`
4. Review audit log for suspicious activity

**If database is corrupted:**

1. Stop service: `systemctl stop pi-autopilot.service`
2. Restore from backup: `./scripts/restore_backup.sh <backup_file>`
3. Verify restoration: `python main.py` (test run)
4. Resume service: `systemctl start pi-autopilot.service`

**If storage is full:**

1. Check backup directory: `du -sh data/artifacts/backups/`
2. Remove old backups if needed: `ls -lt data/artifacts/backups/ | tail -20`
3. Manual cleanup: `rm data/artifacts/backups/pipeline_db_2025-*.sqlite.gz`

---

## Testing Security Features

### Unit Tests

Run security-specific tests:

```bash
# Config validation
pytest tests/test_config_validator.py -v

# Backup functionality
pytest tests/test_backup_manager.py -v

# Error handling
pytest tests/test_error_handler.py -v

# Input sanitization
pytest tests/test_sanitizer.py -v

# API retry logic
pytest tests/test_retry_handler.py -v

# Audit logging
pytest tests/test_audit_logger.py -v

# All security tests
pytest tests/test_*.py -v
```

### Integration Testing

```bash
# Full pipeline with mocked APIs
pytest tests/ -m integration -v

# Test with real APIs (slow, uses quota)
LIVE_API_TEST=1 pytest tests/ -v
```

### Security Penetration Testing

Test XSS payload blocking:

```bash
# Sample malicious Reddit post content
curl -X POST http://localhost:5000/test \
  -d 'body=<script>alert("xss")</script>'
# Expected: Payload blocked by sanitizer
```

---

## Related Documentation

- [CHANGELOG.md](docs/CHANGELOG.md) - Version history and release notes
- [ROADMAP.md](docs/ROADMAP.md) - Future security enhancements (Q2-Q4 2026)
- [IMPLEMENTATION_OUTLINE.md](docs/IMPLEMENTATION_OUTLINE.md) - Technical architecture details
- [IMPLEMENTATION_SUMMARY.md](docs/IMPLEMENTATION_SUMMARY.md) - Executive summary
- [README.md](../README.md) - Getting started and general documentation

---

## Support & Questions

For security-related issues or questions:

1. **Check the docs:** Start with IMPLEMENTATION_OUTLINE.md for detailed technical info
2. **Review the code:** Each module has comprehensive docstrings
3. **Run tests:** Test suite provides usage examples
4. **GitHub Issues:** Report security issues (privately if sensitive)

---

**Last Updated:** January 12, 2026  
**Status:** All security features implemented and tested  
**Maintenance:** Automatic backups run daily at 2 AM
