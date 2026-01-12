# Pi-Autopilot AI Coding Instructions

**Core Mission:** Fully automated digital product engine—Reddit → Problem → Product → Verification → Gumroad upload, with aggressive cost controls.

## Architecture & Data Flow

**Linear Pipeline (non-negotiable order):**
```
Reddit Ingest → Problem Extraction → Spec Generation → Content Generation → Verification → Gumroad Upload
```

**Key insight:** Each stage outputs timestamped JSON/markdown artifacts to `data/artifacts/{post_id}/`, enabling recovery and regeneration without re-running prior stages.

**Stage responsibilities & entry gates:**
- **Reddit Ingest** (`agents/reddit_ingest.py`): Fetch posts from configured subreddits; filter by `REDDIT_MIN_SCORE`; store raw JSON to `reddit_posts` table
- **Problem Extraction** (`agents/problem_agent.py`): Classify posts as monetizable; output `discard` flag (auto-skip if true) + urgency score (0-100); truncate post body at 2000 chars using `_truncate_preserving_boundary()`
- **Spec Generation** (`agents/spec_agent.py`): Decide product type (guide/template/prompt_pack); compute price + confidence; **gate: rejects if `build=false` or `confidence<70` or `len(deliverables)<3`**
- **Content Generation** (`agents/content_agent.py`): Write markdown copy (no fluff, enforce structured sections); routes through `InputSanitizer` before returning
- **Verification** (`agents/verifier_agent.py`): Judge content quality/completeness; sets `regeneration_needed` flag; **max regeneration attempts: `MAX_REGENERATION_ATTEMPTS` (default 1 = no retry)**
- **Gumroad Upload** (`agents/gumroad_agent.py`): Format listing + upload; **final irreversible step**

## Cost Control (Non-Negotiable)

**Three enforcement layers** (all checked before LLM calls):
1. **Per-run token limit** (`MAX_TOKENS_PER_RUN`, default 50k): Pipeline aborts if exceeded
2. **Per-run USD limit** (`MAX_USD_PER_RUN`, default $5): Estimated cost at call time; aborts if exceeded  
3. **Lifetime USD limit** (`MAX_USD_LIFETIME`, default $100): Persisted in `cost_tracking` SQLite table; pipeline blocks if already spent

**Implementation pattern (MANDATORY):**
```python
# In LLMClient wrapper - agents don't call check_limits directly:
combined_input = system_prompt + user_content
estimated_input = cost_governor.estimate_tokens(combined_input)
estimated_output = max_tokens
cost_governor.check_limits_before_call(estimated_input, estimated_output)  # Raises CostLimitExceeded
# ... make OpenAI API call ...
cost_governor.record_usage(response.usage.prompt_tokens, response.usage.completion_tokens)
```

**Token estimation:** Uses `tiktoken.encoding_for_model()` if available; falls back to `len(text) / 3.5` estimate. Estimate conservatively—abort is irreversible for a post.

**Abort is terminal:** When `CostLimitExceeded` is raised, current post is logged to `audit_log` with `cost_limit_exceeded=1` but pipeline continues to next post.

## Prompt Engineering & Schema Enforcement

**Mental model:** Agents = code, Intelligence = prompts, Consistency = schemas.

**Prompt file locations** (`prompts/`) with placeholder injection:
- `problem_extraction.txt`: Injects `<<REDDIT_POSTS_AND_COMMENTS>>` (truncated post body); returns `{discard, problem_summary, who_has_it, why_it_matters, current_bad_solutions[], urgency_score, evidence_quotes[]}`
- `product_spec.txt`: Injects `<<PROBLEM>>` from problem extraction; returns `{build, product_type, working_title, target_buyer, deliverables[], price_recommendation, confidence, ...}`
- `product_content.txt`: Injects `<<TYPE>>`, `<<BUYER>>`, `<<JOB>>`, `<<DELIVERABLES>>`, `<<FAILURE_REASON>>`; returns markdown (no JSON)
- `verifier.txt`: Injects content markdown; returns `{pass, reasons[], improvement_suggestions, regeneration_needed}`

**Prompt injection pattern:**
```python
prompt_template = load_file("prompts/{stage}.txt")
system_prompt = prompt_template  # Never modify after load
system_prompt = system_prompt.replace('<<KEY>>', actual_value)
# Sanitize user inputs before placeholder injection
result = llm_client.call_structured(system_prompt, "", max_tokens=1500)
```

**LLM call patterns:**
- `call_structured()`: Enforces `response_format={"type": "json_object"}`; returns parsed dict (problem/spec/verdict)
- `call_text()`: No JSON enforcement; returns raw markdown string (content only)

## Data Models & Schemas

**All models are dataclasses in `models/`:**
- `Problem` (`models/problem.py`): `discard (bool)`, `problem_summary`, `who_has_it`, `why_it_matters`, `current_bad_solutions[]`, `urgency_score (0-100)`, `evidence_quotes[]`
- `ProductSpec` (`models/product_spec.py`): `build (bool)`, `product_type`, `working_title`, `target_buyer`, `deliverables[] (min 3)`, `price_recommendation`, `confidence (0-100)`, `why_existing_products_fail`, `job_to_be_done`
- `Verdict` (`models/verdict.py`): `pass (bool)`, `reasons[]`, `improvement_suggestions[]`, `regeneration_needed (bool)`

**Key patterns:**
- Always call `.to_dict()` before saving to JSON artifacts
- Models enforce type safety; never construct from raw dicts without validation
- Schemas are contracts—missing fields = `call_structured()` call failed, log it

## Storage & Artifact Management

**Database:** SQLi`id (PK)`, `title`, `body`, `timestamp`, `subreddit`, `author`, `score`, `url`, `raw_json`
- `pipeline_runs`: `id`, `post_id (FK)`, `stage`, `status` (completed/discarded/rejected/failed), `artifact_path`, `error_message`, `created_at`
- `cost_tracking`: `id`, `run_id`, `tokens_sent`, `tokens_received`, `usd_cost`, `timestamp`, `model`, `abort_reason`
- `audit_log`: `id`, `timestamp`, `action` (post_ingested/problem_extracted/etc), `post_id`, `run_id`, `details (JSON)`, `error_occurred (bool)`, `cost_limit_exceeded (bool)`

**Artifact structure:**
```
data/
  artifacts/
    {post_id}/
      problem_{unix_timestamp}.json
      spec_{unix_timestamp}.json
      content_{unix_timestamp}.md
      verdict_attempt_{n}.json
      error_logs/
        {stage}_{timestamp}.json
``` & Resilience

**Reddit (`services/reddit_client.py`):**
- PRAW library; requires `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` from `.env`
- Fetches from comma-separated subreddits in `REDDIT_SUBREDDITS`; filters by `REDDIT_MIN_SCORE` (default 10); limit per subreddit: `REDDIT_POST_LIMIT`
- Always store raw JSON to `reddit_posts.raw_json` for audit trail
- `RedditClient.fetch_posts()` returns list of dicts: `{id, title, body, subreddit, author, score, url, timestamp}`

**OpenAI (`services/llm_client.py`):**
- Wrapper around `openai.ChatCompletion`; ALL LLM calls must route through `LLMClient` instance passed by main.py
- Automatically enforces cost limits via `CostGovernor.check_limits_before_call()` before API call
- Structured calls: `response_format={"type": "json_object"}`; text calls: no format restriction
- Token pricing: `OPENAI_INPUT_TOKEN_PRICE`, `OPENAI_OUTPUT_TOKEN_PRICE` (default: $0.00003/$0.00006 for GPT-4)
- **Retry logic:** `RetryHandler` wraps API calls with exponential backoff for transient errors

**Gumroad (`services/gumroad_client.py`):**
- Final irreversible upload target; requires `GUMROAD_ACCESS_TOKEN` from `.env`
- Products include Reddit source URL (transparency + attribution)
- No retry—if upload fails, post is marked in audit log; requires manual intervention
- Wrapper around `openai.ChatCompletion`; always routes through `CostGovernor`
- All calls include `response_format={"type": "json_object"}` when structured
- Token pricing in config (`OPENAI_INPUT_TOKEN_PRICE`, `OPENAI_OUTPUT_TOKEN_PRICE`)

**Gumroad (`services/gumroad_client.py`):**
- Final upload target; requires `GUMROAD_ACCESS_TOKEN`
- Products link back to Reddit source (transparency + attribution)
and settings injected at runtime via `BaseSettings` (pydantic-settings) in `config.py`
- Settings load order: environment variables override `.env` override defaults
- `KILL_SWITCH=true` stops entire pipeline immediately (emergency brake)
- `MAX_REGENERATION_ATTEMPTS` caps content regeneration loops (default 1 = generate once, verify once, no retry)
- **Config validation:** `ConfigValidator` runs on startup; aborts if any required field missing (error message printed to stdout)

**Local dev workflow:**
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && vim .env  # Fill in API credentials
mkdir -p data/artifacts
python main.py  # Full pipeline, respects all cost/time limits
```
 - run with `pytest`:
- **Unit tests** (`@pytest.mark.unit`): Isolated agent/service logic; mock LLM calls via `unittest.mock.patch`
- **Integration tests** (`@pytest.mark.integration`): End-to-end pipeline with real SQLite database
- **Common fixtures:** `temp_db` (temp SQLite file), `cost_governor` (mocked), `monkeypatch` (override config)

**Testing patterns:**
- Mock `LLMClient.call_structured()` to return hardcoded dicts; mock `call_text()` to return markdown strings
- Mock `CostGovernor` to test cost limit logic without actual API calls
- Use `pytest-mock` for patching: `monkeypatch.setattr(config.settings, 'max_usd_per_run', 1.0)`
- Always test schema violations: missing fields, wrong types (models should raise on `.from_dict()`)
- Test error paths: `CostLimitExceeded`, `ConfigValidationError`, transient API errors

**Running tests:**
```bash
pytest tests/ -v --tb=short  # All tests
pytest tests/test_cost_governor.py -m unit  # Unit only
pytest tests/test_storage.py -m integration  # Integration only
```.service`) runs via installer scripts.

## Testing & Validation

**Test structure** (`tests/`):
- Unit tests: isolated agent/service logic (mock LLM calls)
- Integration tests: end-to-end pipeline with real database
- Marker post fails—diagnostics workflow:**

1. **Check audit log:** `SELECT * FROM audit_log WHERE post_id = ? ORDER BY timestamp DESC LIMIT 20`
   - Look for `error_occurred=1` or `cost_limit_exceeded=1` rows
2. **Check pipeline_runs:** `SELECT * FROM pipeline_runs WHERE post_id = ? ORDER BY created_at DESC`
   - Identifies which stage failed (status = failed/rejected/discarded)
   - `artifact_path` points to stage output or error log
3. **Review artifact:** `cat data/artifacts/{post_id}/{stage}_{timestamp}.json` (problem/spec/verdict) or `.md` (content)
   - If stage produced output, artifact exists; missing fields → LLM schema validation failed
4. **Check error artifact:** `cat data/artifacts/{post_id}/error_logs/{stage}_{timestamp}.json` (if stage raised exception)
   - Contains full traceback, exception type, and context
5. **Review prompt:** `cat prompts/{stage}.txt`
   - Verify all `<<PLACEHOLDER>>` are covered; check constraints (min deliverables, confidence threshold)
text, max_length)` for Reddit post bodies (defined in `agents/problem_agent.py`); prefers paragraph/line breaks over mid-sentence cuts
- **Error handling:** Catch & re-raise with context: `raise RuntimeError(f"...context...") from e`; log exception type + traceback to artifact; never silently discard
- **Type hints:** Full annotations required; use `Optional[type]` for nullable fields, `List[type]` for arrays
- **Logging:** Print only stage milestones (pipeline flow) to stdout; save detailed context to artifacts (`save_artifact()`, error logs)
- **Input sanitization:** Always route Reddit/user content through `InputSanitizer.sanitize_reddit_content()` or `.sanitize_gumroad_content()` before LLM injection
- **File I/O:** Always use absolute paths via `settings.artifacts_path`, `settings.database_path`; handle `OSError` explicitly

## Golden Rules for Modifications

1. **Cost limits are sacred:** Never bypass `CostGovernor.check_limits_before_call()`. Pass `cost_governor` to agents; it's injected by main.py.
2. **Prompt changes = schema changes:** Every prompt update should verify output schema (via test); missing fields → silent failure.
3. **Artifacts are truth:** Always save outputs JSON → `save_artifact(post_id, stage, dict)` or markdown → `save_content_artifact(post_id, content)`. Never rely on in-memory state for recovery.
4. **Pipeline order is fixed:** No parallelization—each stage depends on prior stage's artifact. Main.py enforces order; respect it.
5. **External API resilience:** Reddit, OpenAI, Gumroad can timeout. `RetryHandler` covers OpenAI; manually add backoff retry if extending other APIs.
6. **Database consistency:** Use `Storage` class for all DB writes (enforces schema). Never execute raw SQL outside `Storage` or `CostGovernor`.
7. **Post-discard flow:** Once a post is discarded (problem extraction) or rejected (spec generation), skip remaining stages (main.py lines 105-115 show pattern)
- Verifier marks `regeneration_needed=true` → content agent re-runs with adjusted prompt
- Max attempts: `MAX_REGENERATION_ATTEMPTS` (default 1, meaning no retry)
- Always log why regeneration was triggered (verifier output)

## Code Style Conventions

- **Truncation:** Use `_truncate_preserving_boundary()` for Reddit post bodies (prefer breaks at paragraphs/lines, not mid-sentence)
- **Error handling:** Catch & re-raise with context (`raise RuntimeError(...) from e`); never silently discard
- **Type hints:** Full annotations required (Pydantic models + function signatures)
- **Logging:** Print stage milestones (not debug spam); save detailed artifacts instead

## Golden Rules for Modifications

1. **Cost limits are sacred:** Never bypass `CostGovernor.check_limits_before_call()`. If a feature costs tokens, pre-check.
2. **Prompt changes need schema validation:** Every prompt change should update `call_structured()` parsing or tests.
3. **Artifacts are truth:** Always save outputs (problem → gumroad upload); never trust in-memory state for recovery.
4. **Pipeline order is fixed:** Don't parallelize stages; each depends on prior's artifact.
5. **External APIs require retry logic:** Reddit API, OpenAI, Gumroad can fail; add exponential backoff if extending integrations.
