# Pi-Autopilot System Pipeline Overview

## Executive Summary

**Pi-Autopilot** is a fully automated digital product engine that transforms Reddit posts into monetizable digital products on Gumroad. The system runs autonomously on a Raspberry Pi, operating hourly via systemd timers with comprehensive cost controls, security features, and quality verification.

**Core Mission**: Reddit → Problem → Product → Verification → Gumroad Upload

---

## System Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         PI-AUTOPILOT PIPELINE                           │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Reddit     │─────▶│   Problem    │─────▶│     Spec     │
│  Ingestion   │      │  Extraction  │      │  Generation  │
└──────────────┘      └──────────────┘      └──────────────┘
                            │                      │
                            │ Discard?             │ Build? Confidence?
                            ▼                      ▼
                     [Skip if not               [Skip if 
                      monetizable]               rejected]
                                                   │
                                                   ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Gumroad    │◀─────│   Gumroad    │◀─────│   Content    │
│    Upload    │      │   Listing    │      │  Generation  │
└──────────────┘      └──────────────┘      └──────────────┘
      │                                            │
      │                                            ▼
      │                                      ┌──────────────┐
      │                                      │ Verification │
      │                                      └──────────────┘
      │                                            │
      │                                            │ Pass?
      │                                            ▼
      │                                      [Regenerate up to
      │                                       1 time if fails]
      │
      ▼
┌──────────────────────────────────────────────────────────────────┐
│               Product Live on Gumroad                            │
└──────────────────────────────────────────────────────────────────┘

                    ╔═══════════════════════════╗
                    ║   COST GOVERNOR           ║
                    ║   (Guards Every LLM Call) ║
                    ╚═══════════════════════════╝
                            │
                            ├─ Per-Run Token Limit (50k)
                            ├─ Per-Run USD Limit ($5)
                            └─ Lifetime USD Limit ($100)

                    ╔═══════════════════════════╗
                    ║   SYSTEMD TIMER           ║
                    ║   (Runs Hourly)           ║
                    ╚═══════════════════════════╝

                    ╔═══════════════════════════╗
                    ║   DASHBOARD               ║
                    ║   (Real-time Monitoring)  ║
                    ╚═══════════════════════════╝
```

---

## Pipeline Stages in Detail

### Stage 1: Reddit Ingestion
**File**: `agents/reddit_ingest.py`  
**Function**: `ingest_reddit_posts()`

**Purpose**: Fetch posts from configured subreddits and store in database.

**Process**:
1. Connects to Reddit API via PRAW library
2. Fetches posts from comma-separated subreddits (configured in `.env`)
3. Filters by minimum score threshold (default: 10)
4. Limits posts per subreddit (default: 20)
5. Saves posts to `reddit_posts` SQLite table with full metadata

**Configuration**:
- `REDDIT_SUBREDDITS`: Comma-separated list (e.g., "SideProject,Entrepreneur,startups")
- `REDDIT_MIN_SCORE`: Minimum upvotes required
- `REDDIT_POST_LIMIT`: Max posts to fetch per subreddit

**Output**:
```json
{
  "total_saved": 15,
  "post_ids": ["abc123", "def456", ...]
}
```

**Database Schema** (`reddit_posts`):
- `id`: Unique Reddit post ID
- `title`: Post title
- `body`: Post content (selftext)
- `timestamp`: Post creation time
- `subreddit`: Subreddit name
- `author`: Reddit username
- `score`: Upvotes
- `url`: Full Reddit URL
- `raw_json`: Complete Reddit API response

---

### Stage 2: Problem Extraction
**File**: `agents/problem_agent.py`  
**Function**: `extract_problem(post_data, llm_client)`

**Purpose**: Analyze Reddit post to identify monetizable problems.

**Process**:
1. Loads prompt template from `prompts/problem_extraction.txt`
2. Sanitizes Reddit content to prevent XSS attacks
3. Truncates post body to 2000 chars (preserves sentence boundaries)
4. Injects post data into prompt template
5. Calls OpenAI API with structured JSON output
6. Validates response against `Problem` data model

**Prompt Injection**:
```python
reddit_text = f"""
Title: {post_data['title']}
Subreddit: r/{post_data['subreddit']}
Author: {post_data['author']}
Score: {post_data['score']}
Content: {truncated_body}
"""
system_prompt = prompt_template.replace('<<REDDIT_POSTS_AND_COMMENTS>>', reddit_text)
```

**Discard Criteria** (Pipeline skips if `discard=true`):
- No economic consequence
- Generic complaints without specificity
- Not actionable or monetizable

**Output** (`Problem` model):
```json
{
  "discard": false,
  "problem_summary": "Entrepreneurs struggle to validate SaaS ideas before building",
  "who_has_it": "First-time founders with technical skills but no market validation experience",
  "why_it_matters": "90% of startups fail due to building products nobody wants",
  "current_bad_solutions": [
    "Generic market research templates",
    "Expensive consulting services",
    "Trial and error approach"
  ],
  "urgency_score": 85,
  "evidence_quotes": [
    "I spent 6 months building a product nobody wanted",
    "Wish I had validated the idea first"
  ]
}
```

**Artifact Storage**: `data/artifacts/{post_id}/problem_{timestamp}.json`

---

### Stage 3: Spec Generation
**File**: `agents/spec_agent.py`  
**Function**: `generate_spec(problem_data, llm_client)`

**Purpose**: Decide product type, scope, and pricing for the identified problem.

**Process**:
1. Loads prompt template from `prompts/product_spec.txt`
2. Converts problem data to JSON and injects into prompt
3. Calls OpenAI API with structured JSON output
4. Validates response against `ProductSpec` data model
5. Enforces rejection gates

**Rejection Gates** (Pipeline skips if any fail):
1. `build == false` → Not worth building
2. `confidence < 70` → Too uncertain
3. `deliverables.length < 3` → Insufficient scope

**Product Types**:
- **Guide**: Step-by-step tutorial with examples
- **Template**: Pre-built document/spreadsheet/checklist
- **Prompt Pack**: Collection of AI prompts for specific tasks

**Output** (`ProductSpec` model):
```json
{
  "build": true,
  "product_type": "guide",
  "working_title": "The SaaS Idea Validation Blueprint",
  "target_buyer": "Technical founders launching their first SaaS product",
  "job_to_be_done": "Validate a SaaS idea in 2 weeks without writing code",
  "why_existing_products_fail": "Most guides are generic checklists without actionable steps or real examples",
  "deliverables": [
    "5-step validation framework with timeline",
    "Customer interview script templates",
    "Landing page conversion checklist",
    "10 real validation case studies",
    "Notion template for tracking progress"
  ],
  "price_recommendation": 19.99,
  "confidence": 87
}
```

**Artifact Storage**: `data/artifacts/{post_id}/spec_{timestamp}.json`

---

### Stage 4: Content Generation
**File**: `agents/content_agent.py`  
**Function**: `generate_content(spec_data, llm_client)`

**Purpose**: Write the actual digital product content (markdown).

**Process**:
1. Loads prompt template from `prompts/product_content.txt`
2. Injects spec fields into prompt placeholders:
   - `<<TYPE>>` → product_type
   - `<<BUYER>>` → target_buyer
   - `<<JOB>>` → job_to_be_done
   - `<<DELIVERABLES>>` → comma-joined deliverables list
   - `<<FAILURE_REASON>>` → why_existing_products_fail
3. Calls OpenAI API (text output, not JSON)
4. Sanitizes generated content for Gumroad safety

**Content Requirements** (enforced by prompt):
- No generic fluff or filler
- Structured sections with clear headers
- Concrete examples and actionable steps
- Specific to the target buyer persona
- Deliverables must be detailed and complete

**Output** (Markdown string):
```markdown
# The SaaS Idea Validation Blueprint

## Who This Is For
Technical founders launching their first SaaS product who need...

## The Problem
90% of startups fail because...

## The 5-Step Framework
### Step 1: Define Your Hypothesis
...specific instructions with examples...

### Step 2: Identify Your ICP
...detailed guidance...

[etc.]
```

**Artifact Storage**: `data/artifacts/{post_id}/content_{timestamp}.md`

---

### Stage 5: Verification
**File**: `agents/verifier_agent.py`  
**Function**: `verify_content(content, llm_client)`

**Purpose**: Quality-check content before publishing; regenerate once if needed.

**Process**:
1. Loads prompt template from `prompts/verifier.txt`
2. Sends content markdown to OpenAI for evaluation
3. Calls OpenAI API with structured JSON output
4. Validates response against `Verdict` data model
5. Applies pass/fail logic

**Quality Checks**:
1. `example_quality_score >= 7` (scale of 1-10)
2. `generic_language_detected == false`
3. `missing_elements == []` (all required sections present)

**Fail Conditions** (Content rejected if any true):
- Example quality score < 7
- Generic language detected (e.g., "various methods", "different approaches")
- Missing required elements (e.g., no examples, no actionable steps)

**Regeneration Logic**:
```python
regeneration_count = 0
content_verified = False

while regeneration_count <= MAX_REGENERATION_ATTEMPTS and not content_verified:
    content = generate_content(spec_data, llm_client)
    verdict = verify_content(content, llm_client)
    
    if verdict["pass"]:
        content_verified = True
    else:
        regeneration_count += 1

if not content_verified:
    # HARD DISCARD - Post permanently rejected
```

**Output** (`Verdict` model):
```json
{
  "pass": true,
  "reasons": [
    "Examples are specific and actionable",
    "No generic language detected",
    "All deliverables present"
  ],
  "missing_elements": [],
  "generic_language_detected": false,
  "example_quality_score": 9
}
```

**Artifact Storage**: `data/artifacts/{post_id}/verdict_attempt_{n}.json`

**Key Insight**: Maximum regeneration attempts = 1 (default), meaning:
- First attempt generates content
- Verification runs
- If fails, regenerate **once**
- If second attempt fails → **HARD DISCARD** (post permanently rejected)

---

### Stage 6: Gumroad Listing
**File**: `agents/gumroad_agent.py`  
**Function**: `create_listing(spec_data, content, llm_client)`

**Purpose**: Generate Gumroad-optimized product listing copy.

**Process**:
1. Loads prompt template from `prompts/gumroad_listing.txt`
2. Creates product summary from spec + content preview
3. Calls OpenAI API (text output, not JSON)
4. Sanitizes listing for Gumroad safety

**Listing Format**:
```
Title: The SaaS Idea Validation Blueprint

Description:
[Compelling description targeting the buyer persona]

What You Get:
- 5-step validation framework with timeline
- Customer interview script templates
- [etc.]

Who This Is For:
Technical founders launching their first SaaS product

Who This Is NOT For:
Experienced entrepreneurs who have already validated multiple products

Price: $19.99
```

**Artifact Storage**: `data/artifacts/{post_id}/gumroad_listing_{timestamp}.txt`

---

### Stage 7: Gumroad Upload
**File**: `agents/gumroad_agent.py`  
**Function**: `upload_to_gumroad(spec_data, listing_text, content_file_path)`

**Purpose**: Upload product to Gumroad (final irreversible step).

**Process**:
1. Parses listing text to extract title and description
2. Validates essential fields (title ≥ 3 chars, description ≥ 10 chars)
3. Sanitizes title and description
4. Converts price to cents (e.g., $19.99 → 1999)
5. Calls Gumroad API via `GumroadClient.create_product()`
6. Returns upload result with product URL

**Field Extraction**:
```python
title = _extract_field(listing_text, 'Title:', spec_data['working_title'])
description = _extract_description(listing_text)
price_cents = int(spec_data['price_recommendation'] * 100)
```

**Gumroad API Call**:
```python
product = gumroad_client.create_product(
    name=title[:100],  # Gumroad max: 100 chars
    description=description,
    price_cents=price_cents
)
```

**Output**:
```json
{
  "product_id": "gumroad_id_abc123",
  "product_url": "https://gum.co/abc123",
  "success": true
}
```

**Artifact Storage**: `data/artifacts/{post_id}/gumroad_upload_{timestamp}.json`

**Key Notes**:
- This is the **final irreversible step**
- No retry logic (one attempt only)
- Product includes Reddit source URL for transparency
- If upload fails, post is marked in audit log for manual intervention

---

## Supporting Systems

### Cost Governor
**File**: `services/cost_governor.py`  
**Class**: `CostGovernor`

**Purpose**: Enforce hard spending limits to prevent runaway API costs.

**Three-Tier Protection**:

1. **Per-Run Token Limit** (`MAX_TOKENS_PER_RUN`, default 50k)
   - Tracks tokens across all LLM calls in a single pipeline run
   - Aborts pipeline if exceeded

2. **Per-Run USD Limit** (`MAX_USD_PER_RUN`, default $5.00)
   - Estimates cost before each LLM call
   - Aborts pipeline if estimated total exceeds limit

3. **Lifetime USD Limit** (`MAX_USD_LIFETIME`, default $100.00)
   - Persists cumulative cost in `cost_tracking` SQLite table
   - Blocks entire pipeline if lifetime spending exceeds limit

**Token Estimation**:
- Uses `tiktoken` library if available (accurate)
- Fallback: `len(text) / 3.5` (conservative estimate)

**Cost Calculation**:
```python
input_cost = input_tokens * OPENAI_INPUT_TOKEN_PRICE
output_cost = output_tokens * OPENAI_OUTPUT_TOKEN_PRICE
total_cost = input_cost + output_cost
```

**Abort Behavior**:
```python
if estimated_cost exceeds any limit:
    raise CostLimitExceeded(reason)
    write_abort_record()  # data/artifacts/abort_{run_id}.json
    log_to_database()     # cost_tracking table
    stop_pipeline()       # Current post skipped, audit logged
```

**Key Insight**: Cost checks happen **before** every LLM call (proactive, not reactive).

---

### LLM Client
**File**: `services/llm_client.py`  
**Class**: `LLMClient`

**Purpose**: Wrapper around OpenAI API with cost enforcement and retry logic.

**Two Call Types**:

1. **Structured Calls** (`call_structured`):
   - Enforces `response_format={"type": "json_object"}`
   - Used for: Problem extraction, Spec generation, Verification
   - Returns: Parsed JSON dict

2. **Text Calls** (`call_text`):
   - No JSON enforcement
   - Used for: Content generation, Listing creation
   - Returns: Raw string

**Pattern** (applies to both call types):
```python
def call_structured(system_prompt, user_content, max_tokens):
    # 1. Estimate tokens
    combined_input = system_prompt + user_content
    estimated_input = cost_governor.estimate_tokens(combined_input)
    estimated_output = max_tokens
    
    # 2. Check limits (raises CostLimitExceeded if exceeds)
    cost_governor.check_limits_before_call(estimated_input, estimated_output)
    
    # 3. Make API call with retry logic
    response = retry_handler.call_with_retry(
        lambda: openai.ChatCompletion.create(...)
    )
    
    # 4. Record actual usage
    cost_governor.record_usage(
        response.usage.prompt_tokens,
        response.usage.completion_tokens
    )
    
    # 5. Return result
    return json.loads(response.choices[0].message.content)
```

**Key Features**:
- Automatic cost limit enforcement (no agent needs to check)
- Exponential backoff retry for transient API errors
- Token/cost tracking persisted to database

---

### Storage Layer
**File**: `services/storage.py`  
**Class**: `Storage`

**Purpose**: SQLite database management for all pipeline data.

**Database Schema**:

1. **`reddit_posts`**:
   - Stores raw Reddit posts
   - Fields: `id`, `title`, `body`, `timestamp`, `subreddit`, `author`, `score`, `url`, `raw_json`

2. **`pipeline_runs`**:
   - Tracks pipeline stage execution
   - Fields: `id`, `post_id` (FK), `stage`, `status`, `artifact_path`, `error_message`, `created_at`
   - Statuses: `completed`, `discarded`, `rejected`, `failed`, `cost_limit_exceeded`

3. **`cost_tracking`**:
   - Records every LLM API call
   - Fields: `id`, `run_id`, `tokens_sent`, `tokens_received`, `usd_cost`, `timestamp`, `model`, `abort_reason`

4. **`audit_log`**:
   - Immutable operation history
   - Fields: `id`, `timestamp`, `action`, `post_id`, `run_id`, `details` (JSON), `error_occurred`, `cost_limit_exceeded`

**Key Methods**:
- `save_post(post_data)`: Insert Reddit post (de-duplication by ID)
- `get_unprocessed_posts()`: Fetch posts not yet processed
- `log_pipeline_run(post_id, stage, status, artifact_path)`: Record stage result

---

### Security Modules

#### Config Validator
**File**: `services/config_validator.py`  
**Class**: `ConfigValidator`

**Purpose**: Validate all configuration on startup (fail-fast).

**Checks**:
- Required API keys present and non-empty
- Numeric values within reasonable ranges
- Boolean flags parseable
- Paths writable
- Subreddit names valid format

**Behavior**: Raises `ConfigValidationError` if any check fails → Pipeline aborts before starting

---

#### Input Sanitizer
**File**: `services/sanitizer.py`  
**Class**: `InputSanitizer`

**Purpose**: Prevent XSS attacks from Reddit/LLM content.

**Methods**:
1. `sanitize_reddit_content(text)`: Cleans Reddit post bodies
2. `sanitize_gumroad_content(text)`: Cleans generated content/listings

**Protections**:
- Removes `<script>` tags
- Escapes HTML entities
- Strips dangerous attributes (`onclick`, `onerror`, etc.)
- Neutralizes JavaScript URLs (`javascript:`)

**Usage**: Called before prompt injection and before Gumroad upload

---

#### Retry Handler
**File**: `services/retry_handler.py`  
**Class**: `RetryHandler`

**Purpose**: Exponential backoff retry for transient API errors.

**Retry Logic**:
```python
max_retries = 3
base_delay = 1.0  # seconds

for attempt in range(max_retries):
    try:
        return api_call()
    except TransientError:
        if attempt < max_retries - 1:
            delay = base_delay * (2 ** attempt)  # 1s, 2s, 4s
            time.sleep(delay + random.uniform(0, 1))  # Add jitter
        else:
            raise
```

**Transient Errors**:
- Network timeouts
- 429 Rate Limit Exceeded
- 503 Service Unavailable
- Connection errors

**Non-Retryable Errors**:
- 401 Unauthorized (bad API key)
- 400 Bad Request (invalid payload)
- 404 Not Found

---

#### Error Handler
**File**: `services/error_handler.py`  
**Class**: `ErrorHandler`

**Purpose**: Structured error logging and categorization.

**Methods**:
1. `log_error(post_id, stage, exception, context)`: Write error artifact
2. `categorize_error(exception)`: Identify if transient or permanent

**Error Artifacts** (`data/artifacts/{post_id}/error_logs/{stage}_{timestamp}.json`):
```json
{
  "post_id": "abc123",
  "stage": "content_generation",
  "error_type": "OpenAIError",
  "error_message": "Rate limit exceeded",
  "traceback": "...",
  "context": {"attempt": 2},
  "timestamp": 1234567890,
  "is_transient": true
}
```

**Categorization**:
- Transient → Allow retry
- Permanent → Log and skip

---

#### Audit Logger
**File**: `services/audit_logger.py`  
**Class**: `AuditLogger`

**Purpose**: Immutable trail of all pipeline operations.

**Logged Actions**:
- `post_ingested`: Reddit post saved to database
- `post_discarded`: Post rejected (not monetizable)
- `problem_extracted`: Problem successfully extracted
- `spec_generated`: Spec created (or rejected)
- `content_verified`: Content passed verification
- `content_rejected`: Content failed verification
- `gumroad_listed`: Listing generated
- `gumroad_uploaded`: Product uploaded
- `cost_limit_exceeded`: Pipeline aborted due to cost
- `error_occurred`: Exception caught

**Database Entry**:
```python
audit_logger.log(
    action='spec_generated',
    post_id='abc123',
    run_id='run_1234567890',
    details={'title': 'The SaaS Validation Blueprint', 'confidence': 87},
    error_occurred=False,
    cost_limit_exceeded=False
)
```

---

#### Backup Manager
**File**: `services/backup_manager.py`  
**Class**: `BackupManager`

**Purpose**: Automated daily database backups with retention.

**Process**:
1. Pipeline start → Check if backup exists today
2. If not → Create gzip-compressed SQLite backup
3. Save to `data/artifacts/backups/pipeline_db_{date}.sqlite.gz`
4. Cleanup old backups (default retention: 30 days)

**Recovery**:
```bash
./scripts/restore_backup.sh data/artifacts/backups/pipeline_db_20260112.sqlite.gz
```

---

### Dashboard
**File**: `dashboard.py`  
**Framework**: Flask web app

**Purpose**: Real-time monitoring of pipeline activity.

**Endpoints**:
- `/` → Main dashboard UI
- `/api/stats` → JSON stats (cost, counts, recent activity)
- `/api/posts` → Active posts being processed
- `/api/audit` → Recent audit log entries

**Metrics Displayed**:
- **Cost Tracking**:
  - Lifetime cost
  - Last 24h cost
  - Token usage
- **Pipeline Stats**:
  - Total posts ingested
  - Posts completed
  - Posts discarded
  - Posts rejected
  - Errors
- **Recent Activity**:
  - Last 20 audit log entries
  - Timestamps and details
- **Active Posts**:
  - Current stage for each post
  - Status

**Access**: `http://<raspberry-pi-ip>:8000`

---

## Data Flow

### Artifact Directory Structure
```
data/
├── pipeline.db                      # SQLite database
└── artifacts/
    ├── backups/
    │   └── pipeline_db_20260112.sqlite.gz
    ├── abort_{run_id}.json          # Cost limit aborts
    └── {post_id}/
        ├── problem_{timestamp}.json
        ├── spec_{timestamp}.json
        ├── content_{timestamp}.md
        ├── verdict_attempt_1.json
        ├── verdict_attempt_2.json   # If regenerated
        ├── gumroad_listing_{timestamp}.txt
        ├── gumroad_upload_{timestamp}.json
        └── error_logs/
            └── {stage}_{timestamp}.json
```

### Inter-Agent Communication

**Pattern**: All agents communicate via disk-based JSON/Markdown artifacts (no in-memory passing between agents after initial run).

**Example Flow**:
1. `reddit_ingest.py` → Writes to `reddit_posts` table
2. `main.py` reads from table → Passes dict to `problem_agent.py`
3. `problem_agent.py` → Returns dict → `main.py` saves to `problem_{timestamp}.json`
4. `main.py` reads problem artifact → Passes dict to `spec_agent.py`
5. `spec_agent.py` → Returns dict → `main.py` saves to `spec_{timestamp}.json`
6. [etc.]

**Key Insight**: Artifacts enable recovery and regeneration without re-running prior stages.

---

## Automation & Deployment

### Systemd Timer
**Files**: `saltprophet.service`, `saltprophet.timer`

**Schedule**: Hourly (configurable via `OnUnitActiveSec`)

**Installation**:
```bash
sudo ./installer/setup_pi.sh
```

**What It Does**:
1. Copies service/timer files to `/etc/systemd/system/`
2. Creates `/opt/pi-autopilot/` directory
3. Copies all code and prompts
4. Sets up Python virtual environment
5. Configures `.env` permissions (chmod 600)
6. Enables and starts timer

**Commands**:
```bash
# Check timer status
systemctl status pi-autopilot.timer

# View recent runs
journalctl -u pi-autopilot.service -n 50

# Manual trigger
sudo systemctl start pi-autopilot.service

# Change schedule
sudo systemctl edit pi-autopilot.timer
# Add: OnUnitActiveSec=30min
sudo systemctl daemon-reload
```

---

### Dashboard Service
**File**: `pi-autopilot-dashboard.service`

**Port**: 8000

**Auto-Start**: Enabled after `setup_pi.sh`

**Commands**:
```bash
# Check dashboard status
systemctl status pi-autopilot-dashboard

# View dashboard logs
journalctl -u pi-autopilot-dashboard -f

# Restart dashboard
sudo systemctl restart pi-autopilot-dashboard
```

---

## Rejection & Discard Logic

### Post Rejection Flowchart
```
Reddit Post
    │
    ▼
Problem Extraction
    │
    ├─ discard=true? ────────────────────────────▶ [DISCARDED]
    │                                                     │
    ▼ No                                                  │
Spec Generation                                           │
    │                                                     │
    ├─ build=false? ─────────────────────────────▶ [REJECTED]
    ├─ confidence < 70? ─────────────────────────▶ [REJECTED]
    ├─ deliverables.length < 3? ─────────────────▶ [REJECTED]
    │                                                     │
    ▼ All Pass                                            │
Content Generation                                        │
    │                                                     │
    ▼                                                     │
Verification                                              │
    │                                                     │
    ├─ pass=true? ──────────────────────────────▶ Continue to Gumroad
    │                                                     │
    ▼ No                                                  │
Regenerate (max 1 time)                                   │
    │                                                     │
    ├─ pass=true? ──────────────────────────────▶ Continue to Gumroad
    │                                                     │
    ▼ No                                                  │
[HARD DISCARD]                                            │
    │                                                     │
    └─────────────────────────────────────────────────────┘
                              │
                              ▼
                    Logged in audit_log
                    Artifact saved
                    Pipeline continues to next post
```

### Status Definitions

- **COMPLETED**: Post processed successfully and uploaded to Gumroad
- **DISCARDED**: Post not monetizable (problem_extraction stage)
- **REJECTED**: Post failed spec generation gates (confidence, deliverables, etc.)
- **HARD DISCARD**: Content failed verification twice (max regeneration attempts exceeded)
- **FAILED**: Unexpected error occurred (logged to error_logs/)
- **COST_LIMIT_EXCEEDED**: Pipeline aborted due to spending limits

---

## Configuration Reference

### Environment Variables (`.env`)

```env
# Reddit API
REDDIT_CLIENT_ID=abc123
REDDIT_CLIENT_SECRET=xyz789
REDDIT_USER_AGENT=Pi-Autopilot/2.0
REDDIT_SUBREDDITS=SideProject,Entrepreneur,startups
REDDIT_MIN_SCORE=10
REDDIT_POST_LIMIT=20

# OpenAI API
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4
OPENAI_INPUT_TOKEN_PRICE=0.00003
OPENAI_OUTPUT_TOKEN_PRICE=0.00006

# Gumroad API
GUMROAD_ACCESS_TOKEN=gum_...

# Storage
DATABASE_PATH=./data/pipeline.db
ARTIFACTS_PATH=./data/artifacts

# Cost Controls
MAX_TOKENS_PER_RUN=50000
MAX_USD_PER_RUN=5.0
MAX_USD_LIFETIME=100.0

# Quality Controls
MAX_REGENERATION_ATTEMPTS=1

# Emergency Stop
KILL_SWITCH=false
```

---

## Outcomes & Success Metrics

### Pipeline Success Scenario

**Input**: Reddit post from r/SideProject with 50 upvotes
```
Title: "Struggling to validate my SaaS idea before building"
Body: "I'm a developer with a SaaS idea but don't want to spend 6 months 
building something nobody wants. I've tried generic market research but it's 
too vague. Anyone have a concrete validation process?"
```

**Stage Outputs**:

1. **Problem Extraction**:
   - `discard: false` ✅
   - Problem: "Developers waste months building unvalidated SaaS products"
   - Urgency: 85/100
   - → **Proceeds to Spec**

2. **Spec Generation**:
   - `build: true` ✅
   - `confidence: 87` ✅ (>70)
   - `deliverables: 5 items` ✅ (>3)
   - Product type: Guide
   - Price: $19.99
   - → **Proceeds to Content**

3. **Content Generation**:
   - 3000 tokens generated
   - Markdown with 8 sections
   - → **Proceeds to Verification**

4. **Verification (Attempt 1)**:
   - `pass: true` ✅
   - `example_quality_score: 9` ✅ (≥7)
   - `generic_language_detected: false` ✅
   - `missing_elements: []` ✅
   - → **Proceeds to Gumroad**

5. **Gumroad Listing**:
   - Title: "The SaaS Idea Validation Blueprint"
   - Description: 800 characters
   - → **Proceeds to Upload**

6. **Gumroad Upload**:
   - `success: true` ✅
   - Product URL: `https://gum.co/abc123`
   - → **PIPELINE COMPLETE** ✅

**Database Records**:
- `reddit_posts`: 1 row
- `pipeline_runs`: 7 rows (1 per stage + 1 final)
- `cost_tracking`: ~5 rows (LLM calls)
- `audit_log`: ~10 entries

**Cost**:
- Tokens sent: ~8,000
- Tokens received: ~6,000
- Total cost: ~$0.60

**Time**: ~90 seconds (API latency dependent)

**Outcome**: Live Gumroad product ready for sale 🎉

---

### Pipeline Failure Scenarios

#### Scenario 1: Not Monetizable
```
Reddit post: "My code editor has a minor UI bug"
↓
Problem Extraction: discard=true (no economic impact)
↓
Status: DISCARDED
Outcome: Post skipped, no product created
```

#### Scenario 2: Low Confidence
```
Reddit post: "Vague problem with unclear specifics"
↓
Problem Extraction: discard=false
↓
Spec Generation: confidence=45 (<70)
↓
Status: REJECTED
Outcome: Post skipped, no product created
```

#### Scenario 3: Verification Failure
```
Reddit post: Monetizable problem
↓
Problem Extraction: Pass
↓
Spec Generation: Pass
↓
Content Generation (Attempt 1): Generic content
↓
Verification: pass=false (generic_language_detected=true)
↓
Content Generation (Attempt 2): Still generic
↓
Verification: pass=false
↓
Status: HARD DISCARD (max attempts exceeded)
Outcome: Post permanently rejected
```

#### Scenario 4: Cost Limit
```
Pipeline processing 10 posts
↓
Post 8: Cost estimate before LLM call
↓
Run cost: $4.80, Estimate: +$0.40 = $5.20
↓
MAX_USD_PER_RUN ($5.00) would be exceeded
↓
Status: COST_LIMIT_EXCEEDED
Outcome: Post 8 skipped, pipeline aborts, posts 9-10 not processed
Artifact: abort_{run_id}.json written
```

---

## Diagnostics & Troubleshooting

### Post Failed - Where Did It Fail?

**Step 1**: Query `pipeline_runs` table
```sql
SELECT * FROM pipeline_runs 
WHERE post_id = 'abc123' 
ORDER BY created_at DESC;
```

**Output**:
```
| stage               | status     | artifact_path                          |
|---------------------|------------|----------------------------------------|
| content_generation  | completed  | data/artifacts/abc123/content_*.md     |
| verification        | failed     | data/artifacts/abc123/verdict_*.json   |
```
→ Failed at verification stage

---

**Step 2**: Review artifact
```bash
cat data/artifacts/abc123/verdict_attempt_1.json
```

**Output**:
```json
{
  "pass": false,
  "reasons": ["Generic language detected: 'various methods'"],
  "missing_elements": [],
  "generic_language_detected": true,
  "example_quality_score": 5
}
```
→ Content too generic

---

**Step 3**: Check audit log
```sql
SELECT * FROM audit_log 
WHERE post_id = 'abc123' 
ORDER BY timestamp DESC 
LIMIT 5;
```

**Output**:
```
| action            | details                                      |
|-------------------|----------------------------------------------|
| content_rejected  | {"attempt": 2, "reasons": ["Generic..."]}    |
| content_rejected  | {"attempt": 1, "reasons": ["Generic..."]}    |
| spec_generated    | {"title": "...", "confidence": 78}           |
| problem_extracted | {"summary": "...", "urgency_score": 70}      |
```
→ Failed twice, hard discarded

---

### Pipeline Aborted - Why?

**Step 1**: Check for abort artifact
```bash
ls data/artifacts/abort_*.json
cat data/artifacts/abort_1234567890.json
```

**Output**:
```json
{
  "run_id": 1234567890,
  "abort_reason": "MAX_USD_PER_RUN exceeded: 5.12 > 5.0",
  "run_tokens_sent": 48000,
  "run_tokens_received": 35000,
  "run_cost": 5.12,
  "timestamp": 1736724445
}
```
→ Exceeded per-run dollar limit

---

**Step 2**: Query cost tracking
```sql
SELECT SUM(tokens_sent) as total_input, 
       SUM(tokens_received) as total_output,
       SUM(usd_cost) as total_cost
FROM cost_tracking 
WHERE run_id = 1234567890;
```

**Output**:
```
| total_input | total_output | total_cost |
|-------------|--------------|------------|
| 48000       | 35000        | 5.12       |
```
→ Confirmed: Run cost exceeded limit

---

**Step 3**: Check which posts consumed most tokens
```sql
SELECT c.timestamp, p.post_id, p.stage, c.tokens_sent, c.usd_cost
FROM cost_tracking c
JOIN pipeline_runs p ON c.run_id = p.post_id
WHERE c.run_id = 1234567890
ORDER BY c.usd_cost DESC
LIMIT 10;
```
→ Identify expensive posts (e.g., very long Reddit posts, complex specs)

---

### Dashboard Not Showing Data

**Check 1**: Dashboard service running?
```bash
systemctl status pi-autopilot-dashboard
```

**Check 2**: Database accessible?
```bash
sqlite3 data/pipeline.db "SELECT COUNT(*) FROM reddit_posts;"
```

**Check 3**: Network port open?
```bash
curl http://localhost:8000/api/stats
```

---

## Key Insights & Design Decisions

### 1. **Verifier-First Philosophy**
- Quality gates at multiple stages (problem, spec, verification)
- Fail fast: Discard early rather than waste LLM tokens
- Hard discard after max attempts: Prevent infinite loops

### 2. **Disk-Based State**
- All artifacts saved to disk (JSON/Markdown)
- Enables recovery without re-running stages
- Debugging: Inspect artifacts to understand failures
- No in-memory state that can be lost

### 3. **Cost Controls Are Non-Negotiable**
- Checks before every LLM call (proactive)
- Three-tier limits (tokens, per-run USD, lifetime USD)
- Abort is terminal: No retry after limit exceeded
- Conservative estimation: Better to underestimate than exceed

### 4. **Sequential Execution**
- No parallel processing (simplicity over speed)
- One post at a time (easier debugging)
- Clear pipeline flow (no race conditions)

### 5. **Security by Default**
- Input sanitization for Reddit content (XSS prevention)
- Output sanitization for Gumroad uploads
- Config validation on startup (fail-fast)
- File permissions enforced (`.env` chmod 600)

### 6. **Audit Trail Everything**
- Immutable `audit_log` table
- Every action logged with timestamp + details
- Enables forensic analysis of pipeline behavior
- Compliance-ready (can prove what happened when)

### 7. **One Regeneration, Then Discard**
- Default `MAX_REGENERATION_ATTEMPTS = 1`
- Prevents infinite retry loops
- Balances quality vs. cost
- If content can't pass verification in 2 tries → not worth building

### 8. **Autonomous Operation**
- Raspberry Pi runs unattended
- Systemd timer ensures hourly execution
- Dashboard for monitoring (no intervention needed)
- Kill switch for emergency stop (preserves data)

---

## Success Criteria

### Operational Success
✅ Pipeline runs hourly without human intervention  
✅ Cost controls prevent overspending  
✅ Quality gates maintain product standards  
✅ Dashboard provides real-time visibility  
✅ Audit trail enables debugging  

### Product Success
✅ 10-20% of ingested posts become products (realistic conversion)  
✅ Generated content passes verification >80% on first attempt  
✅ Gumroad uploads succeed >95% of attempts  
✅ Average cost per product: <$1.00  

### Quality Success
✅ No generic/fluff content published  
✅ All products have concrete examples and actionables  
✅ Target buyer personas are specific (not "anyone")  
✅ Pricing matches value (not generic $10)  

---

## Future Enhancements

### Q1 2026
- **Advanced Verification**: Multi-agent consensus (3 verifiers vote)
- **Dynamic Pricing**: Adjust based on problem urgency and market data
- **A/B Testing**: Generate 2 versions, publish both, track performance

### Q2 2026
- **Feedback Loop**: Scrape Gumroad sales data, retrain prompts
- **Multi-Platform**: Expand beyond Gumroad (Etsy, Shopify, etc.)
- **Customer Analysis**: Analyze buyer demographics, optimize targeting

### Q3 2026
- **Content Expansion**: Add video/audio generation (Synthesia, ElevenLabs)
- **Template Library**: Pre-built templates for common product types
- **Automated Marketing**: Auto-generate social media posts, email sequences

### Q4 2026
- **AI Competitor Analysis**: Scrape existing products, identify gaps
- **Smart Bundling**: Group related products into higher-value packages
- **Performance Prediction**: ML model to predict product success before building

---

## Conclusion

**Pi-Autopilot** is a complete end-to-end system that:
1. **Discovers** problems from Reddit
2. **Validates** monetizability with AI
3. **Generates** high-quality digital products
4. **Verifies** quality before publishing
5. **Publishes** autonomously to Gumroad
6. **Monitors** costs and activity in real-time
7. **Audits** every action for transparency

**Key Differentiators**:
- **Verifier-first**: Quality gates prevent low-value products
- **Cost-controlled**: Hard limits prevent runaway spending
- **Autonomous**: Runs unattended on Raspberry Pi
- **Transparent**: Full audit trail and artifact storage
- **Secure**: Input sanitization, config validation, permission enforcement

**Outcome**: A self-sustaining digital product factory that runs 24/7, generates passive income, and requires minimal human intervention.

---

## Quick Reference Commands

```bash
# Installation
sudo ./installer/setup_pi.sh

# Check pipeline timer
systemctl status pi-autopilot.timer

# View recent pipeline runs
journalctl -u pi-autopilot.service -n 50

# Manual pipeline trigger
sudo systemctl start pi-autopilot.service

# Access dashboard
http://<pi-ip>:8000

# Query lifetime cost
sqlite3 data/pipeline.db "SELECT SUM(usd_cost) FROM cost_tracking;"

# View recent audit log
sqlite3 data/pipeline.db "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 20;"

# Check unprocessed posts
sqlite3 data/pipeline.db "SELECT COUNT(*) FROM reddit_posts WHERE id NOT IN (SELECT DISTINCT post_id FROM pipeline_runs);"

# Restore from backup
./scripts/restore_backup.sh data/artifacts/backups/pipeline_db_20260112.sqlite.gz

# Emergency stop
echo "KILL_SWITCH=true" >> /opt/pi-autopilot/.env
sudo systemctl stop pi-autopilot.timer

# Resume after emergency stop
sed -i 's/KILL_SWITCH=true/KILL_SWITCH=false/' /opt/pi-autopilot/.env
sudo systemctl start pi-autopilot.timer
```

---

**Document Version**: 1.0  
**Last Updated**: January 12, 2026  
**Repository**: https://github.com/SaltProphet/Pi-autopilot  
**Maintainer**: SaltProphet
