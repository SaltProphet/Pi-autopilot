# Prompts

Agent-locked, schema-forced prompts for the Reddit-to-Gumroad pipeline.

## Mental Model

**Agents = code**  
**Intelligence = prompts**  
**Consistency = schemas**  
**Profit = rejection + iteration**

## Pipeline Flow

```
Reddit Post → Problem Extraction → Product Spec → Content Generation → Verification → Gumroad Listing
```

## Prompt Files

### 1. `problem_extraction.txt`
**Used by:** `product_generator.py` (Step 1)  
**Purpose:** Turn raw Reddit posts/comments into a precise, monetizable problem statement.  
**Output:** Problem JSON with discard flag, urgency score, and evidence quotes.

### 2. `product_spec.txt`
**Used by:** `product_generator.py` (Step 2)  
**Purpose:** Decide if problem becomes a product, and exactly what kind.  
**Output:** Product spec with type, price, deliverables, and confidence score.  
**Auto-kill:** confidence < 70, deliverables < 3, generic language.

### 3. `product_content.txt`
**Used by:** `product_generator.py` (Step 3)  
**Purpose:** Generate the actual sellable content.  
**Format:** Structured with mandatory sections (What/Who/Framework/Steps/Failures/Example).  
**Rules:** No filler, no motivation, no teaching tone.

### 4. `prompt_pack.txt`
**Used by:** `product_generator.py` (For prompt_pack product type)  
**Purpose:** Generate professional-grade prompt collections.  
**Minimum:** 5 prompts per pack with strict structure enforcement.

### 5. `verifier.txt`
**Used by:** `verifier_agent.py`  
**Purpose:** Quality gate - reject aggressively before publishing.  
**Output:** Pass/fail with specific reasons and quality scores.  
**Auto-fail:** example_quality_score < 7, generic language detected.

### 6. `gumroad_listing.txt`
**Used by:** `gumroad_uploader.py`  
**Purpose:** Create conversion-oriented listing copy for skeptical buyers.  
**Format:** Title, Subtitle, Description, What You Get, Who NOT For, FAQ, Refund Policy.

### 7. `pricing_adjustment.txt`
**Used by:** Future pricing optimization module  
**Purpose:** Adjust pricing based on evidence (views, sales, refunds).  
**Output:** Price recommendation with risk assessment.

## Usage in Code

Prompts are loaded as templates with placeholder replacement:

```python
# Load prompt template
with open('prompts/problem_extraction.txt', 'r') as f:
    prompt_template = f.read()

# Replace placeholders
prompt = prompt_template.replace('<<REDDIT_POSTS_AND_COMMENTS>>', reddit_data)

# Call OpenAI with structured output
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "system", "content": prompt}],
    response_format={"type": "json_object"}
)
```

## Key Principles

1. **No hand-wavy prompts** - Every prompt enforces structure
2. **Rejection > iteration** - Fail fast with clear criteria
3. **Schemas are mandatory** - All outputs must be valid JSON
4. **No fluff allowed** - Generic language triggers auto-fail
5. **Evidence-based** - Decisions based on data, not vibes

## Failure Modes Built-In

Each prompt includes explicit failure conditions:
- Missing required elements
- Generic/vague language
- Insufficient confidence scores
- Lack of concrete examples
- Broad/unfocused audiences

## Integration Points

- **Step 1-3:** Product generation pipeline
- **Step 4:** Specialized for prompt packs
- **Step 5:** Quality verification gate
- **Step 6:** Gumroad listing creation
- **Step 7:** Post-launch optimization

---

**These prompts are the intelligence layer.** The agents are just executors.
