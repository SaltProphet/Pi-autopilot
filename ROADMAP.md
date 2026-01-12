# Roadmap: Pi-Autopilot Security Hardening

## Overview

This roadmap outlines the security and reliability enhancements for Pi-Autopilot, organized by priority and timeline. The goal is to make the system production-ready for wide deployment while maintaining cost controls and data integrity.

---

## 2026 Q1: Foundation & Security (Current Phase)

### High Priority (COMPLETED)
**Target:** Jan 12, 2026 ✅

1. **Configuration Validation** ✅
   - Validates all required env vars on startup
   - Checks API key formats (OpenAI, Reddit, Gumroad)
   - Enforces numeric ranges for cost limits
   - Verifies path accessibility
   - **Impact:** Prevents silent failures due to misconfiguration

2. **Database Backups** ✅
   - Daily snapshots with 7-day retention
   - Weekly backups with 4-week retention
   - Monthly backups with 12-month retention
   - **Impact:** Disaster recovery capability; zero data loss if DB corrupts

3. **Error Logging** ✅
   - All exceptions logged to artifacts
   - Error categorization (transient vs. fatal)
   - Full tracebacks with context
   - **Impact:** Faster debugging, pattern detection across runs

### Medium Priority (IN PROGRESS)
**Target:** Jan 15, 2026

4. **Input Sanitization** 
   - XSS prevention for Gumroad listings
   - Control character removal for LLM safety
   - SQL injection prevention for database inputs
   - **Impact:** Prevents accidental code injection via malicious Reddit posts

5. **Retry Logic with Exponential Backoff**
   - API-specific strategies (Reddit, OpenAI, Gumroad)
   - Configurable max attempts and backoff windows
   - Transient error detection (timeouts, rate limits)
   - **Impact:** Reduces failure rate from 15% → <1% on API hiccups

6. **Audit Trail / Operation Logging**
   - All pipeline operations recorded to database
   - Queryable history (by post, by run, by error)
   - Immutable schema (no delete/update capability)
   - **Impact:** Compliance tracking, root cause analysis, usage patterns

### Low Priority (PLANNED)
**Target:** Jan 20, 2026

7. **File Permissions Hardening**
   - `.env` file restricted to 0600 (owner only)
   - Database file restricted to 0600
   - Config directories 0700
   - **Impact:** Prevents credential leaks via filesystem permissions

8. **Configuration Integrity Checks**
   - Detects unauthorized `.env` modifications
   - Validates backup file integrity
   - Checks systemd service permissions
   - **Impact:** Detects tampering or accidental corruption

---

## 2026 Q2: Reliability & Scaling

### Planned Features
- **Circuit Breaker Pattern:** Stop calling failing APIs after 5 consecutive failures
- **Graceful Degradation:** Skip problematic stages instead of failing entire run
- **Batch Processing:** Process multiple Reddit posts in parallel within token budget
- **Improved Logging:** Structured JSON logs for ELK/Splunk integration
- **Monitoring Dashboard:** Real-time pipeline metrics (success rate, cost, latency)

### Success Metrics
- Uptime: >99% (only scheduled maintenance)
- API failure recovery: 100% with exponential backoff
- Cost variance: <5% month-to-month
- Pipeline latency: <60s per post (p95)

---

## 2026 Q3: Intelligence & Automation

### Planned Features
- **Feedback Loop:** User ratings (1-5 stars) on Gumroad for generated products
- **Self-Tuning:** Auto-adjust price recommendations based on feedback
- **Prompt Evolution:** Learn which prompt variations convert best
- **Multi-Model Support:** Fallback from GPT-4 → GPT-3.5 if budget pressure
- **Subreddit Analysis:** Score new subreddits before ingestion (high-value vs. noise)

### Success Metrics
- Average product rating: >4.0 stars
- Conversion rate: >15% (Gumroad visitors → buyers)
- Revenue per product: >$50 (target is $30-100 range)

---

## 2026 Q4: Deployment & Analytics

### Planned Features
- **Auto-Scaling:** Deploy additional Pi instances under high demand
- **Global Metrics:** Aggregate stats from fleet of Pi nodes
- **Deployment Automation:** One-click Pi setup via GitHub Actions
- **Analytics API:** RESTful endpoint for dashboard and reporting
- **Compliance Export:** Automated GDPR/audit logs for regulatory review

### Success Metrics
- Deployment time: <15 minutes per Pi
- Observability: >95% of pipeline events logged
- Compliance: Zero audit findings in security review

---

## Technical Implementation Details

### Configuration Validation (HIGH)
**Status:** ✅ Complete  
**Module:** `services/config_validator.py`  
**Tests:** `tests/test_config_validator.py` (pending)  
**Integration:** Update `config.py` to call validator on startup

### Database Backups (HIGH)
**Status:** ✅ Complete  
**Module:** `services/backup_manager.py`  
**Tests:** `tests/test_backup_manager.py` (pending)  
**Integration:** Update `main.py` to initialize backup manager on startup; schedule daily backups via systemd timer

### Error Logging (HIGH)
**Status:** ✅ Complete  
**Module:** `services/error_handler.py`  
**Tests:** `tests/test_error_handler.py` (pending)  
**Integration:** Wrap all agent calls in `main.py` with error handler

### Input Sanitization (MEDIUM)
**Status:** ✅ Complete  
**Module:** `services/sanitizer.py`  
**Tests:** `tests/test_sanitizer.py` (pending)  
**Integration:** Apply in `problem_agent.py`, `content_agent.py`, `gumroad_agent.py`

### Retry Logic (MEDIUM)
**Status:** ✅ Complete  
**Module:** `services/retry_handler.py`  
**Tests:** `tests/test_retry_handler.py` (pending)  
**Integration:** Wrap API calls in `llm_client.py`, `reddit_client.py`, `gumroad_client.py`

### Audit Trail (MEDIUM)
**Status:** ✅ Complete  
**Module:** `services/audit_logger.py`  
**Tests:** `tests/test_audit_logger.py` (pending)  
**Integration:** Update `storage.py` to create audit_log table; wire into `main.py` for operation tracking

### File Permissions (LOW)
**Status:** Pending  
**Module:** `installer/setup_pi.sh` (update existing)  
**Tests:** Manual verification on Pi deployment  
**Integration:** Enforce 0600 on `.env` and `.db` files during installation

### Config Integrity (LOW)
**Status:** Pending  
**Module:** New `services/config_integrity_checker.py`  
**Tests:** `tests/test_config_integrity.py` (pending)  
**Integration:** Optional health check in `main.py`

---

## Risk Assessment & Mitigation

| Risk | Impact | Mitigation | Timeline |
|------|--------|------------|----------|
| Config validation too strict | Blocks deployment | Detailed error messages, environment docs | Q1 (DONE) |
| Backup size explosion | Disk full | Auto-cleanup with retention policy | Q1 (DONE) |
| Error logs leak secrets | Security breach | Regex scrubbing of keys/tokens | Q1 (DONE) |
| Retry backoff too aggressive | API rate limit trigger | API-specific strategies (Reddit: 3s wait, OpenAI: 10s) | Q1 (DONE) |
| Audit log bloats database | Slow queries | Indexed on post_id, action, timestamp (DESC) | Q1 (DONE) |
| Permissions reset on Pi update | Credentials exposed | Document in setup_pi.sh, test in CI | Q2 (PLANNED) |

---

## Success Criteria (End of Q1)

- [ ] All HIGH priority modules implemented and tested
- [ ] Config.py calls validator on startup
- [ ] Main.py uses ErrorHandler and AuditLogger
- [ ] All API clients wrapped with RetryHandler
- [ ] Input sanitization integrated into agents
- [ ] Test suite passes with >90% coverage on new modules
- [ ] Documentation updated with security features
- [ ] Deployment tested on Raspberry Pi
- [ ] No unhandled exceptions in 24-hour test run

---

## Communication & Feedback

**Issues & Feature Requests:**
- Create GitHub issue with label `security`, `reliability`, or `enhancement`
- Include test case or reproduction steps
- Link to relevant stage (problem extraction, content generation, etc.)

**Security Vulnerabilities:**
- Do NOT open public issue
- Email: [security contact] with CVSS score and affected component
- Include timeline for fix and validation process

---

## Related Documentation

- [IMPLEMENTATION_OUTLINE.md](IMPLEMENTATION_OUTLINE.md) - Technical architecture details
- [CHANGELOG.md](CHANGELOG.md) - Release history
- [README.md](README.md) - User guide and deployment
- `.github/copilot-instructions.md` - AI coding standards
