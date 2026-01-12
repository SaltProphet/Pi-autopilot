# Changelog

All notable changes to Pi-Autopilot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security Enhancements (In Progress)
See [ROADMAP.md](ROADMAP.md) for detailed implementation timeline.

#### High Priority - COMPLETED (Jan 12, 2026)
- [x] Secrets validation on startup (config validation module)
- [x] Automated database backups (daily snapshots)
- [x] Structured error logging to artifacts

#### Medium Priority - IN PROGRESS
- [ ] Input sanitization for user-generated content
- [ ] Retry logic with exponential backoff for API calls
- [ ] Audit trail for all pipeline operations

#### Low Priority - PLANNED
- [ ] File permissions hardening in setup script
- [ ] Config integrity checks on initialization

## [2.1.0] - 2026-01-12

### Added - Security Hardening Release
- **Config Validator:** Validates all required configuration on startup
  - Required field checking (API keys, credentials)
  - API key format validation
  - Numeric range validation for cost limits
  - Path accessibility checks
  - Subreddit name validation

- **Backup Manager:** Automated database backups with retention policy
  - Daily backups with 7-day retention
  - Weekly backups with 4-week retention
  - Monthly backups with 12-month retention
  - Backup status monitoring
  - Database restore functionality

- **Error Handler:** Structured error logging to artifacts
  - Full error context (traceback, timestamp, stage)
  - Error categorization (transient vs. fatal)
  - Immutable error artifacts in JSON format
  - Python version tracking for debugging

- **Input Sanitizer:** Content sanitization for different contexts
  - Reddit content sanitization (control char removal, HTML decode)
  - Gumroad listing sanitization (HTML entity escape, XSS prevention)
  - Database content sanitization (null byte removal)
  - Safe URL validation
  - Script tag removal

- **Retry Handler:** API retry logic with exponential backoff
  - API-specific backoff strategies (Reddit, OpenAI, Gumroad)
  - Configurable max attempts and backoff parameters
  - Transient error detection
  - Retry statistics tracking

- **Audit Logger:** Immutable operation tracking
  - All pipeline operations logged to database
  - Action categorization (ingestion, extraction, verification, upload)
  - Post history and timeline queries
  - Recent error aggregation
  - Indexed queries for performance

### Changed
- `requirements.txt`: Added tenacity==8.2.3 and bleach==6.1.0
- `config.py`: Now validates configuration on startup

### Security
- All error logs restricted to 0600 permissions (owner read/write only)
- API key format validation prevents misconfiguration
- Input sanitization prevents XSS in Gumroad listings
- Retry logic prevents API thrashing
- Audit trail provides compliance tracking

## [2.0.0] - 2026-01-12

### Added
- Cost governor with three enforcement layers (tokens, per-run USD, lifetime USD)
- Verifier-first architecture for content quality gates
- SQLite storage layer with schema for reddit_posts, pipeline_runs, cost_tracking
- Prompt-based agents for problem extraction, spec generation, content creation
- Integration with Reddit, OpenAI GPT-4, and Gumroad APIs
- Systemd service and timer for automated execution on Raspberry Pi
- Dockerfile for containerized deployment
- GitHub Actions workflow for deployment to Pi

### Features
- Automatic Reddit post ingestion from configured subreddits
- Problem extraction with monetizability filtering
- Product specification generation with confidence scoring
- Content generation with mandatory structured sections
- Quality verification with auto-rejection criteria
- Gumroad product listing and upload
- Cost tracking and limit enforcement
- Kill switch for emergency pipeline termination
- Artifact-based state management for recovery

### Configuration
- Environment-based settings via `.env` file
- Configurable cost limits (per-run tokens, per-run USD, lifetime USD)
- Subreddit targeting with score filtering
- Token pricing for different OpenAI models
- Regeneration attempt limits

## [1.0.0] - 2025-12-01

### Initial Release
- Basic pipeline architecture
- Core agent implementations
- Cost governor prototype
- SQLite database setup
- Documentation and examples

---

## Release Process

**Version Bumping:**
1. Update version in `__init__.py` (future)
2. Update `CHANGELOG.md` with changes
3. Tag release: `git tag v2.x.x`
4. Push: `git push origin main --tags`

**Deployment:**
1. Run tests: `pytest`
2. Build Docker image: `docker build -t pi-autopilot:v2.x.x .`
3. Deploy to Pi via GitHub Actions or manual SSH

**Rollback:**
1. Revert to previous tag: `git checkout v2.x.x-1`
2. Restart service: `systemctl restart pi-autopilot.service`
3. Check logs: `journalctl -u pi-autopilot -f`
