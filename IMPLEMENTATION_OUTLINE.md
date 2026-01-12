# Implementation Outline: Security Hardening

This document provides the technical architecture and implementation details for Pi-Autopilot's security hardening initiative.

---

## 1. Configuration Validation (`services/config_validator.py`)

### Purpose
Validates all required configuration on startup before the pipeline executes, preventing silent failures due to missing env vars or invalid API key formats.

### Architecture

```
Settings (pydantic)
    ↓
ConfigValidator.validate_or_raise()
    ├─→ validate_required_fields() → Check API keys, credentials, paths
    ├─→ validate_api_key_formats() → Regex validation (OpenAI: 48 hex chars, etc)
    ├─→ validate_numeric_ranges() → Cost limits, token budgets
    ├─→ validate_path_accessibility() → Writable directories
    ├─→ validate_subreddit_names() → Comma-separated format
    └─→ Raise ConfigValidationError with detailed list
```

### Key Methods

| Method | Input | Output | Purpose |
|--------|-------|--------|---------|
| `__init__(settings)` | Pydantic Settings object | None | Constructor |
| `validate_or_raise()` | None | Dict[str, bool] or raises | Run all checks, abort on first failure |
| `validate_required_fields()` | None | Dict[str, bool] | Check for None/empty values |
| `validate_api_key_formats()` | None | Dict[str, bool] | Regex checks per API |
| `validate_numeric_ranges()` | None | Dict[str, bool] | Min/max bounds |
| `validate_path_accessibility()` | None | Dict[str, bool] | os.access() checks |
| `validate_subreddit_names()` | None | Dict[str, bool] | Format validation |

### Integration Points

**config.py** (required update):
```python
# After: settings = Settings()
validator = ConfigValidator(settings)
validator.validate_or_raise()  # Raises ConfigValidationError if invalid
```

### Error Handling

Raises `ConfigValidationError` with list of all failed checks:
```
ConfigValidationError: Configuration validation failed:
  - OPENAI_API_KEY: Invalid format (must be 48 hex characters)
  - REDDIT_CLIENT_ID: Missing required field
  - MAX_USD_PER_RUN: Out of range (must be 1-1000)
```

### Testing Strategy

```python
# test_config_validator.py
def test_validate_required_fields_missing_api_key()
def test_validate_api_key_formats_invalid_openai_key()
def test_validate_numeric_ranges_out_of_bounds()
def test_validate_path_accessibility_unwritable_dir()
def test_validate_subreddit_names_invalid_format()
def test_validate_or_raise_multiple_errors()
```

---

## 2. Database Backups (`services/backup_manager.py`)

### Purpose
Automated daily database backups with retention policy (7-day daily, 4-week weekly, 12-month monthly) for disaster recovery.

### Architecture

```
BackupManager
├─→ backup_database()
│   ├─ Compress current pipeline.db → pipeline_db_2026-01-12T143022.sqlite.gz
│   ├─ Save to data/artifacts/backups/
│   ├─ Set permissions to 0o600 (owner read/write only)
│   └─ Return backup file path
├─→ restore_database(backup_path)
│   ├─ Decompress backup file
│   ├─ Verify file integrity (SQLite header check)
│   ├─ Replace current pipeline.db
│   └─ Return restoration status
├─→ cleanup_old_backups()
│   ├─ Daily: Keep last 7
│   ├─ Weekly: Keep last 4
│   ├─ Monthly: Keep last 12
│   └─ Delete older files
└─→ get_backup_status()
    ├─ Total backups count
    ├─ Total disk usage
    ├─ Latest backup date
    └─ Return status dict
```

### Retention Policy

| Frequency | Retention | Schedule |
|-----------|-----------|----------|
| Daily | 7 backups | Every 24h (cron) |
| Weekly | 4 backups | Sundays (cron) |
| Monthly | 12 backups | 1st of month (cron) |

### Key Methods

| Method | Input | Output | Purpose |
|--------|-------|--------|---------|
| `backup_database()` | None | str (path) | Create timestamped backup |
| `restore_database(path)` | str | Dict[status, timestamp] | Recover from backup |
| `cleanup_old_backups()` | None | Dict[count, size] | Enforce retention |
| `get_backup_status()` | None | Dict[count, usage, latest] | Metrics |

### Integration Points

**main.py** (required update):
```python
backup_manager = BackupManager(settings.DATABASE_PATH)
# Call daily via systemd timer or startup
backup_manager.backup_database()
backup_manager.cleanup_old_backups()
```

**installer/setup_pi.sh** (required update):
```bash
# Add cron job for daily backups
0 2 * * * cd /path/to/Pi-autopilot && python -c "from services.backup_manager import BackupManager; BackupManager('./data/pipeline.db').backup_database()"
```

### Disaster Recovery Script

**scripts/restore_backup.sh** (new):
```bash
#!/bin/bash
# Usage: ./scripts/restore_backup.sh data/artifacts/backups/pipeline_db_2026-01-12.sqlite.gz
python -c "from services.backup_manager import BackupManager; BackupManager('./data/pipeline.db').restore_database('$1')"
```

### Testing Strategy

```python
# test_backup_manager.py
def test_backup_creates_file()
def test_backup_file_has_restricted_permissions()
def test_restore_verifies_backup_integrity()
def test_cleanup_enforces_retention_policy()
def test_backup_status_returns_metrics()
def test_restore_on_corrupted_backup_fails()
```

---

## 3. Error Logging (`services/error_handler.py`)

### Purpose
Captures all exceptions with full context (traceback, timestamp, categorization) and logs to artifacts for debugging and pattern detection.

### Architecture

```
Exception in Agent
    ↓
ErrorHandler.log_error(
    post_id,
    stage,  # problem_extraction, spec_generation, etc
    exception,
    context={...}
)
    ├─→ categorize_error(exception)
    │   ├─ Transient? (timeout, connection error, rate limit)
    │   └─ Fatal? (validation error, type error, value error)
    ├─→ Generate artifact JSON
    │   ├─ timestamp, stage, error_type, categorization
    │   ├─ traceback (full stack)
    │   ├─ python_version (for environment debugging)
    │   └─ context (post content, prompt sent, etc)
    ├─→ Save to data/artifacts/{post_id}/error_{timestamp}.json
    ├─→ Set permissions 0o600
    └─→ Return error_artifact_path
```

### Error Categorization

**Transient Errors** (retry is appropriate):
- `TimeoutError`
- `ConnectionError`
- `OSError` (networking)
- OpenAI: 429 (rate limit), 503 (service unavailable)
- Reddit: 429, 503
- Gumroad: 429, 503

**Fatal Errors** (don't retry):
- `ConfigValidationError`
- `TypeError`
- `ValueError`
- `KeyError`
- Schema validation failures
- OpenAI: 401 (auth), 400 (bad request)

### Key Methods

| Method | Input | Output | Purpose |
|--------|-------|--------|---------|
| `log_error(post_id, stage, exception, context)` | str, str, Exception, dict | str | Log exception to artifact |
| `categorize_error(exception)` | Exception | Dict[is_transient, category] | Classify error type |
| `get_error_artifacts(post_id)` | str | List[Path] | Retrieve all error logs for post |

### Integration Points

**main.py** (required update):
```python
from services.error_handler import ErrorHandler

error_handler = ErrorHandler()
try:
    result = content_agent.generate_content(spec)
except Exception as e:
    error_artifact = error_handler.log_error(
        post_id=post.id,
        stage='content_generation',
        exception=e,
        context={'spec': spec, 'prompt': prompt_used}
    )
    if error_handler.categorize_error(e)['is_transient']:
        # Retry logic here (with RetryHandler)
        pass
    else:
        # Fail permanently, skip to next post
        raise
```

### Error Artifact Schema

```json
{
  "unix_timestamp": 1704969600.123,
  "error_type": "TimeoutError",
  "categorization": {
    "is_transient": true,
    "category": "api_timeout",
    "suggested_action": "retry_with_backoff"
  },
  "traceback": "Traceback (most recent call last):\n  ...",
  "python_version": "3.11.4",
  "context": {
    "post_id": "xyz123",
    "stage": "content_generation",
    "additional": {}
  }
}
```

### Testing Strategy

```python
# test_error_handler.py
def test_categorize_error_transient()
def test_categorize_error_fatal()
def test_log_error_saves_artifact()
def test_artifact_has_restricted_permissions()
def test_traceback_includes_full_stack()
def test_get_error_artifacts_returns_list()
```

---

## 4. Input Sanitization (`services/sanitizer.py`)

### Purpose
Sanitizes user-generated content from Reddit posts before processing or uploading to Gumroad, preventing XSS, SQL injection, and LLM prompt injection.

### Architecture

```
Input String
    ↓
InputSanitizer
├─→ sanitize_reddit_content(text)
│   ├─ Decode HTML entities (&#xNN;, &lt;, etc)
│   ├─ Remove control characters (\x00-\x1f except \n)
│   ├─ Remove Null bytes (SQLite-unsafe)
│   └─ Return clean text for LLM
├─→ sanitize_gumroad_content(text)
│   ├─ Escape HTML entities (&, <, >, ", ')
│   ├─ Remove script tags and event handlers
│   ├─ Strip iframe/object/embed/form tags
│   ├─ Remove on* attributes (onclick, onerror, etc)
│   └─ Return safe HTML
└─→ sanitize_database_content(text)
    ├─ Remove Null bytes (\x00)
    ├─ Validate UTF-8 encoding
    └─ Return DB-safe string
```

### Key Methods

| Method | Input | Output | Purpose |
|--------|-------|--------|---------|
| `sanitize_reddit_content(text)` | str | str | LLM-safe (decode, strip control chars) |
| `sanitize_gumroad_content(text)` | str | str | Web-safe (HTML escape, XSS blocks) |
| `sanitize_database_content(text)` | str | str | DB-safe (null bytes, UTF-8) |

### XSS Prevention Patterns

```python
# Remove these patterns:
DANGEROUS_PATTERNS = [
    r'<script[^>]*>.*?</script>',      # Script tags
    r'on\w+\s*=',                       # Event handlers (onclick, onerror, etc)
    r'<iframe[^>]*>.*?</iframe>',      # Iframes
    r'<object[^>]*>.*?</object>',      # Objects
    r'<embed[^>]*>',                    # Embedded content
    r'javascript:',                     # JS protocol
    r'data:text/html',                 # Data URI HTML
]
```

### Integration Points

**problem_agent.py** (required update):
```python
from services.sanitizer import InputSanitizer

sanitizer = InputSanitizer()
clean_body = sanitizer.sanitize_reddit_content(reddit_post.body)
```

**content_agent.py** (required update):
```python
# Sanitize generated content before uploading
clean_content = sanitizer.sanitize_gumroad_content(generated_content)
```

**gumroad_agent.py** (required update):
```python
# Sanitize title and description before upload
clean_title = sanitizer.sanitize_gumroad_content(product_title)
```

### Testing Strategy

```python
# test_sanitizer.py
def test_sanitize_reddit_content_removes_control_chars()
def test_sanitize_reddit_content_decodes_html_entities()
def test_sanitize_gumroad_content_removes_script_tags()
def test_sanitize_gumroad_content_escapes_html()
def test_sanitize_gumroad_content_blocks_event_handlers()
def test_sanitize_gumroad_content_blocks_iframes()
def test_sanitize_database_content_removes_nulls()
def test_xss_payloads_are_blocked()  # Run 20+ known XSS vectors
```

---

## 5. Retry Logic (`services/retry_handler.py`)

### Purpose
Automatically retries transient API failures (timeouts, rate limits, service unavailable) with exponential backoff to improve reliability.

### Architecture

```
API Call (Reddit, OpenAI, Gumroad)
    ↓
RetryHandler.with_retry(
    func,
    api_type='openai',  # or 'reddit', 'gumroad'
    max_attempts=4
)
    ├─→ Call function
    ├─→ On transient error:
    │   ├─ Sleep: 2s (attempt 1) → 4s → 8s → 16s
    │   └─ Retry
    ├─→ On fatal error: Raise immediately
    ├─→ On max attempts exceeded: Raise LastRetryError
    └─→ Return result or raise
```

### API-Specific Strategies

| API | Max Attempts | Initial Backoff | Max Backoff | Multiplier |
|-----|--------------|-----------------|------------|-----------|
| OpenAI | 4 | 2s | 60s | 2x |
| Reddit | 3 | 3s | 30s | 2x |
| Gumroad | 3 | 2s | 30s | 2x |

### Key Methods

| Method | Input | Output | Purpose |
|--------|-------|--------|---------|
| `with_retry(func, api_type, max_attempts)` | Callable, str, int | T | Wrap function with retry logic |
| `get_retry_stats()` | None | Dict[metrics] | Return success rates |

### Transient vs Fatal Errors

```python
TRANSIENT_EXCEPTIONS = [
    TimeoutError,
    ConnectionError,
    OSError,  # Network errors
]

# API-specific status codes
TRANSIENT_CODES = {
    'openai': [429, 500, 502, 503],
    'reddit': [429, 500, 502, 503],
    'gumroad': [429, 500, 502, 503],
}
```

### Integration Points

**llm_client.py** (required update):
```python
from services.retry_handler import RetryHandler

retry_handler = RetryHandler()

def call_openai_with_retry(prompt, max_tokens):
    return retry_handler.with_retry(
        lambda: self.client.chat.completions.create(...),
        api_type='openai'
    )
```

**reddit_client.py** (required update):
```python
def get_posts_with_retry(subreddit):
    return retry_handler.with_retry(
        lambda: reddit.subreddit(subreddit).new(limit=10),
        api_type='reddit'
    )
```

**gumroad_client.py** (required update):
```python
def upload_product_with_retry(product_data):
    return retry_handler.with_retry(
        lambda: requests.post('https://api.gumroad.com/products', data),
        api_type='gumroad'
    )
```

### Testing Strategy

```python
# test_retry_handler.py
def test_retry_on_timeout()
def test_retry_on_connection_error()
def test_no_retry_on_validation_error()
def test_exponential_backoff_timing()
def test_max_attempts_exceeded()
def test_api_specific_strategies()
def test_retry_stats_tracking()
```

---

## 6. Audit Trail (`services/audit_logger.py`)

### Purpose
Immutable audit trail of all pipeline operations for compliance, debugging, and usage pattern analysis.

### Architecture

```
Pipeline Event
(post_ingested, problem_extracted, etc)
    ↓
AuditLogger.log(action, post_id, run_id, details)
    ├─→ Record to audit_log table
    │   ├─ id (auto-increment)
    │   ├─ timestamp (UTC)
    │   ├─ action (enum: 11 types)
    │   ├─ post_id (from reddit)
    │   ├─ run_id (from pipeline)
    │   ├─ details (JSON blob)
    │   └─ error_occurred (bool)
    ├─→ Commit to SQLite
    └─→ Return log_id
```

### Supported Actions

```python
ACTIONS = [
    'post_ingested',          # Reddit post fetched
    'problem_extracted',      # Problem analysis complete
    'spec_generated',         # Product spec created
    'content_generated',      # Product content written
    'content_verified',       # Verification passed
    'content_rejected',       # Verification failed
    'gumroad_listed',         # Product listed on Gumroad
    'gumroad_uploaded',       # Final upload successful
    'post_discarded',         # Post rejected (not monetizable)
    'cost_limit_exceeded',    # Budget exhausted
    'error_occurred',         # Exception caught
]
```

### Key Methods

| Method | Input | Output | Purpose |
|--------|-------|--------|---------|
| `log(action, post_id, run_id, details)` | str, str, str, dict | int | Record event, return log_id |
| `get_post_history(post_id)` | str | List[dict] | All operations for post |
| `get_run_history(run_id)` | str | List[dict] | All operations in run |
| `get_recent_errors(limit, hours)` | int, int | List[dict] | Recent error events |
| `get_timeline(post_id)` | str | str | Human-readable timeline |

### Database Schema

```sql
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,  -- ISO 8601 UTC
    action TEXT NOT NULL,     -- Enum: post_ingested, etc
    post_id TEXT,             -- Optional: from Reddit
    run_id TEXT,              -- Optional: from pipeline
    details TEXT,             -- JSON blob with context
    error_occurred INTEGER,   -- 0 or 1 (bool)
    cost_limit_exceeded INTEGER -- 0 or 1 (bool)
);

CREATE INDEX idx_audit_post_id ON audit_log(post_id);
CREATE INDEX idx_audit_action ON audit_log(action);
CREATE INDEX idx_audit_timestamp_desc ON audit_log(timestamp DESC);
```

### Integration Points

**storage.py** (required update):
```python
def _init_db(self):
    # ... existing tables ...
    self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            action TEXT NOT NULL,
            post_id TEXT,
            run_id TEXT,
            details TEXT,
            error_occurred INTEGER DEFAULT 0,
            cost_limit_exceeded INTEGER DEFAULT 0
        )
    """)
    self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_post_id ON audit_log(post_id)")
    # ... etc
```

**main.py** (required update):
```python
from services.audit_logger import AuditLogger

audit_logger = AuditLogger(settings.DATABASE_PATH)

# On post ingestion:
audit_logger.log(
    action='post_ingested',
    post_id=reddit_post.id,
    run_id=run_id,
    details={'subreddit': reddit_post.subreddit, 'score': reddit_post.score}
)

# On problem extraction:
audit_logger.log(
    action='problem_extracted',
    post_id=post.id,
    run_id=run_id,
    details={'discard': problem.discard, 'urgency_score': problem.urgency_score}
)

# On error:
audit_logger.log(
    action='error_occurred',
    post_id=post.id,
    run_id=run_id,
    details={'stage': 'content_generation', 'error_type': 'TimeoutError'},
    error_occurred=True
)
```

### Testing Strategy

```python
# test_audit_logger.py
def test_log_records_action()
def test_log_stores_json_details()
def test_get_post_history_returns_all_ops()
def test_get_run_history_filters_by_run()
def test_get_recent_errors_filters_on_flag()
def test_get_timeline_human_readable()
def test_audit_log_immutable_no_deletes()
def test_indexes_improve_query_performance()
```

---

## Integration Checklist

After completing all 6 modules, these updates are required:

### 1. config.py
- [ ] Import ConfigValidator
- [ ] Call validate_or_raise() after Settings instantiation
- [ ] Catch ConfigValidationError and display errors

### 2. storage.py
- [ ] Update _init_db() to create audit_log table
- [ ] Create indexes on post_id, action, timestamp

### 3. main.py
- [ ] Import ErrorHandler, AuditLogger, BackupManager
- [ ] Initialize BackupManager on startup
- [ ] Call backup_database() and cleanup_old_backups() daily
- [ ] Wrap all agent calls with try/except → ErrorHandler.log_error()
- [ ] Call AuditLogger.log() for each pipeline stage completion
- [ ] Handle transient errors with retry logic

### 4. llm_client.py
- [ ] Import RetryHandler
- [ ] Wrap OpenAI API calls with with_retry(..., api_type='openai')

### 5. reddit_client.py
- [ ] Import RetryHandler
- [ ] Wrap Reddit API calls with with_retry(..., api_type='reddit')

### 6. gumroad_client.py
- [ ] Import RetryHandler
- [ ] Wrap Gumroad API calls with with_retry(..., api_type='gumroad')

### 7. problem_agent.py
- [ ] Import InputSanitizer
- [ ] Apply sanitize_reddit_content() to post bodies

### 8. content_agent.py
- [ ] Import InputSanitizer
- [ ] Apply sanitize_gumroad_content() to generated content

### 9. gumroad_agent.py
- [ ] Import InputSanitizer
- [ ] Apply sanitize_gumroad_content() to title and description

### 10. installer/setup_pi.sh
- [ ] Add cron job for daily backups
- [ ] Enforce file permissions (chmod 600 .env, .db; chmod 700 directories)

### 11. scripts/restore_backup.sh (NEW)
- [ ] Create shell script to restore from backup
- [ ] Document restore procedure in README.md

---

## Testing Strategy Summary

**Unit Tests** (80% coverage):
- Each module has dedicated test file: test_config_validator.py, test_backup_manager.py, etc
- Mock external dependencies (SQLite, filesystem) where needed
- Test happy path, error cases, and edge cases

**Integration Tests** (60% coverage):
- Full pipeline run with 5 sample Reddit posts
- Verify artifacts created, backups taken, audit logs recorded
- Simulate API failures and verify retry logic

**Deployment Tests** (manual):
- Test on Raspberry Pi with real Reddit/OpenAI/Gumroad APIs
- Verify permissions (0600 on .env, .db; 0700 on directories)
- Check cron job for daily backups
- Verify systemd service starts cleanly

---

## Cost Impact

| Module | Tokens per Run | Est. Monthly Cost |
|--------|----------------|-------------------|
| Error logging artifacts | ~100 (JSON writes) | Negligible |
| Audit logging | ~50 (SQLite writes) | Negligible |
| Retry backoff delay | 0 (retry same prompt) | Negligible |
| Input sanitization | 0 (local processing) | Negligible |
| Backup compression | 0 (offline) | Negligible |
| **Total** | **~150 extra** | **<$0.01** |

No token overhead on LLM calls. All new modules are local processing.

---

## Deployment Timeline

- **Day 1 (Today):** Create all 6 modules, update requirements.txt
- **Day 2:** Update config.py, storage.py, main.py
- **Day 3:** Update API client files (llm_client, reddit_client, gumroad_client)
- **Day 4:** Update agent files (problem_agent, content_agent, gumroad_agent)
- **Day 5:** Update setup_pi.sh, create restore script
- **Day 6:** Comprehensive testing (unit + integration)
- **Day 7:** Deploy to Raspberry Pi, 24-hour monitoring

---

## Related Documentation

- [CHANGELOG.md](CHANGELOG.md) - Release notes
- [ROADMAP.md](ROADMAP.md) - Feature timeline
- [README.md](README.md) - User guide
- `.github/copilot-instructions.md` - AI coding standards
