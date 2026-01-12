# Pi-Autopilot AI Coding Instructions

**Core Mission:** Fully automated digital product engine—Reddit → Problem → Product → Verification → Gumroad upload, with aggressive cost controls.

## Architecture & Data Flow

**Linear Pipeline (non-negotiable order):**
```
Reddit Posts → Problem Extraction → Product Spec → Content Gen → Verification → Gumroad Upload
```

**Key insight:** Each stage outputs JSON artifacts (saved to `data/artifacts/<post_id>/`), enabling recovery and iteration without re-running prior stages.

**Stage responsibilities:**
- **Problem Extraction** (`agents/problem_agent.py`): Classify Reddit posts as monetizable; output discard flag + urgency score
- **Spec Generation** (`agents/spec_agent.py`): Decide product type (guide/template/prompt_pack); compute price + confidence
- **Content Generation** (`agents/content_agent.py`): Write sellable copy (no fluff, structured sections)
- **Verification** (`agents/verifier_agent.py`): Judge quality; regenerate if confidence < threshold
- **Gumroad** (`agents/gumroad_agent.py`): Format listing + upload; final irreversible step

## Cost Control (Non-Negotiable)

**Three enforcement layers** (all checked before LLM calls):
1. **Per-run token limit** (`MAX_TOKENS_PER_RUN`, default 50k): Pipeline aborts if exceeded
2. **Per-run USD limit** (`MAX_USD_PER_RUN`, default $5): Estimated cost; aborts if exceeded  
3. **Lifetime USD limit** (`MAX_USD_LIFETIME`, default $100): Persisted in `cost_tracking` SQLite table; aborts if exceeded

**Implementation pattern:**
```python
# ALWAYS in LLM-calling agents:
estimated_input = cost_governor.estimate_tokens(prompt)
estimated_output = max_tokens  # set per-agent max
cost_governor.check_limits_before_call(estimated_input, estimated_output)
# ... make LLM call ...
cost_governor.record_usage(actual_input_tokens, actual_output_tokens)
```

**Token estimation:** Uses `tiktoken` for GPT-4; falls back to `text_length / 3.5` if unavailable.

## Prompt Engineering & Schema Enforcement

**Mental model:** Agents = code, Intelligence = prompts, Consistency = schemas.

**Prompt file locations** (`prompts/`):
- `problem_extraction.txt`: Forces JSON output with discard flag
- `product_spec.txt`: Forces confidence score; auto-rejects confidence < 70
- `product_content.txt`: Enforces structured sections (What/Who/Framework/Steps)
- `verifier.txt`: Checks for confidence, evidence, specificity

**Prompt injection pattern:**
```python
prompt_template = load_file("prompts/{stage}.txt")
system_prompt = prompt_template.replace('<<PLACEHOLDER>>', actual_data)
result = llm_client.call_structured(system_prompt, "", max_tokens=1500)
```

**Why structured calls?** Always use `call_structured()` for schemas (returns JSON dict); use `call_text()` only for content (markdown copy).

## Data Models & Schemas

**All models are dataclasses in `models/`:**
- `Problem`: discard, problem_summary, who_has_it, why_it_matters, urgency_score, evidence_quotes
- `ProductSpec`: build, product_type, deliverables, price_recommendation, confidence
- `Verdict`: pass, failing_checks, improvement_suggestions, regeneration_needed

**Key pattern:** Always serialize with `.to_dict()` before saving to artifacts; models enforce type safety.

## Storage & Artifact Management

**Database:** SQLite at `DATABASE_PATH` (default `./data/pipeline.db`)

**Tables:**
- `reddit_posts`: id, title, body, subreddit, score, author, url, raw_json
- `pipeline_runs`: post_id, stage, status, artifact_path, error_message, created_at
- `cost_tracking`: run_id, tokens_sent, tokens_received, usd_cost, timestamp, abort_reason

**Artifact pattern:**
```python
artifact_dir = f"data/artifacts/{post_id}/"
filename = f"{stage}_{timestamp}.json"  # allows multiple attempts per stage
save_artifact(post_id, stage, data_dict)  # automatically timestamped
```

**Why timestamped?** Enables tracing regeneration attempts without data loss.

## External Integrations

**Reddit (`services/reddit_client.py`):**
- PRAW library; requires `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`
- Monitors configured subreddits (comma-separated in config); filters by `REDDIT_MIN_SCORE`
- Store raw JSON; parse only title, body, subreddit, author, score

**OpenAI (`services/llm_client.py`):**
- Wrapper around `openai.ChatCompletion`; always routes through `CostGovernor`
- All calls include `response_format={"type": "json_object"}` when structured
- Token pricing in config (`OPENAI_INPUT_TOKEN_PRICE`, `OPENAI_OUTPUT_TOKEN_PRICE`)

**Gumroad (`services/gumroad_client.py`):**
- Final upload target; requires `GUMROAD_ACCESS_TOKEN`
- Products link back to Reddit source (transparency + attribution)

## Configuration & Deployment

**Environment-based (`.env`):**
- All secrets injected at runtime via `BaseSettings` (pydantic-settings)
- `KILL_SWITCH=true` stops entire pipeline (emergency brake)
- Regeneration attempts capped (`MAX_REGENERATION_ATTEMPTS`, default 1)

**Local dev:** `python main.py` executes full pipeline; respects all cost limits.

**Production (Raspberry Pi):** Systemd service (`saltprophet.service`) runs via installer scripts.

## Testing & Validation

**Test structure** (`tests/`):
- Unit tests: isolated agent/service logic (mock LLM calls)
- Integration tests: end-to-end pipeline with real database
- Markers: `@pytest.mark.smoke`, `@pytest.mark.regression`, `@pytest.mark.unit`, `@pytest.mark.integration`

**Common patterns:**
- Mock `LLMClient` to avoid API calls in unit tests
- Use `pytest-mock` for cost governor mocking
- Always test schema violations (e.g., missing discard flag)

## Debugging & Iteration

**When an agent fails:**
1. Check artifact JSON at `data/artifacts/{post_id}/{stage}_{timestamp}.json`
2. Inspect `pipeline_runs` table for stage status + error_message
3. Review prompt in `prompts/{stage}.txt` for clarity/constraints
4. Check cost_tracking table: `SELECT * FROM cost_tracking WHERE run_id = ?` to spot abort reasons

**Regeneration workflow:**
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
