# Investigation Guide — DS Team Code Alignment

**Goal:** Answer 5 critical questions before implementing refactoring  
**Estimated time:** 30-45 minutes  

---

## Investigation Checklist

### I1: LLM Calling Pattern

**Question:** How does DS team call the LLM? What model? What auth?

**Where to look:**
```bash
# Search DS team notebooks for LLM imports/calls
grep -r "import.*llm\|from.*llm" /home/u560060992/dbx/1-TILs/analysis/notebooks/
grep -r "dbutils.notebook.entry_point\|api_token\|requests.post" /home/u560060992/dbx/1-TILs/analysis/notebooks/
grep -r "databricks-gpt\|foundation\|litellm" /home/u560060992/dbx/1-TILs/analysis/notebooks/
```

**Files to check:**
- `/home/u560060992/dbx/1-TILs/analysis/notebooks/2.2 - Parse Documents.py`
- `/home/u560060992/dbx/1-TILs/analysis/notebooks/2.3 - Clean, Transform, and Chunk Parsed Text.py`
- `/home/u560060992/dbx/1-TILs/analysis/notebooks/til_profile_extraction_pilot_v2026-06-02a.txt` (if accessible)

**Record:**
```
DS Team LLM Pattern:
- Endpoint type: [Databricks serving | LiteLLM | Other: ___]
- Model name: ___________________
- Auth method: [api_token from dbutils | env var | other: ___]
- HTTP library: [requests | urllib | other: ___]
- Code location: ___________________
```

**Compare with FSR:**
- FSR uses LiteLLM gateway with LITELLM_API_KEY env var
- FSR code: `pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py` line ~350+

**Decision:** Should we use same pattern as DS team or FSR?

---

### I2: Shared Utility Functions

**Question:** Are there existing LLM calling utilities we should reuse?

**Where to look:**
```bash
# Search for existing LLM/prompt utilities
find /home/u560060992/dbx/pw_sdg_ai_ser_repo -name "*llm*" -o -name "*prompt*" 
grep -r "def call_llm\|def extract_json\|def parse_response" /home/u560060992/dbx/pw_sdg_ai_ser_repo/code_assets/

# Check what's in code_assets/
ls -la /home/u560060992/dbx/pw_sdg_ai_ser_repo/code_assets/
```

**Record:**
```
Shared Utilities:
- Call LLM: [exists: ___ | need to build]
- Parse response: [exists: ___ | need to build]
- Handle auth: [exists: ___ | need to build]
```

**Decision:** Reuse existing utilities or build new ones?

---

### I3: Table Schema & Naming Convention

**Question:** What is the final intended schema? Confirm with architecture.

**Where to look:**
```bash
# Check what tables already exist in vgpd
# (Can't do from CLI, but check any Databricks catalog docs)

# Look for schema definitions in code
grep -r "vgpd.til\|metadata.*table\|chunks.*table" /home/u560060992/dbx/1-TILs/ --include="*.md" --include="*.py"
```

**Files to check:**
- `/home/u560060992/dbx/1-TILs/design/til-design.md` (done: confirms medallion architecture)
- `/home/u560060992/dbx/FSR/README.md` (FSR patterns)
- `/home/u560060992/dbx/FSR/fsr-docs/*.md` (FSR schema docs)

**Record:**
```
Schema Decisions:
1. Is vgpd.til_profiles a schema or table?
   [ ] Schema (contains: til_metadata, til_chunks, etc.)
   [ ] Table (contains columns)

2. If schema: table names are
   - Metadata: vgpd.til_profiles.til_metadata
   - Chunks: vgpd.til_profiles.til_chunks
   - Other: ___________________

3. If table: structure is
   - til_number (PK)
   - parsed_profile (JSON)
   - Other columns: ___________________
```

**Compare with FSR:**
- FSR: `vaid.fsr_metadata.fsr_metadata` (schema.table.table is unusual, confirm this)

---

### I4: Unique Key & Re-extraction Strategy

**Question:** Can TILs be re-extracted? What's the versioning strategy?

**Where to look:**
- Design doc (`til-design.md`) for "reprocessing controls"
- DS team experiments: did they re-extract same TIL multiple times?
- FSR pattern: They store `document_id` (UUID) as PK, allow re-extraction

**Files to check:**
- `/home/u560060992/dbx/1-TILs/design/til-design.md` (look for "lineage", "versioning", "replay")
- DS team results: `/home/u560060992/dbx/1-TILs/analysis/ds-team-til-profile-results/`

**Record:**
```
Re-extraction Policy:
1. Can a TIL be re-extracted (e.g., new LLM version)?
   [ ] Yes: keep version history
   [ ] No: overwrite latest
   [ ] Other: ___________________

2. If yes: unique key is
   [ ] til_number only
   [ ] til_number + version/revision
   [ ] til_number + extraction_timestamp
   [ ] Other: ___________________

3. Storage strategy
   [ ] Overwrite (MERGE ON til_number, UPDATE)
   [ ] Keep history (INSERT all versions, filter at query time)
   [ ] Other: ___________________
```

**Compare with FSR:**
- FSR: Uses `document_id` (UUID) as PK, allows re-extraction, only UPDATE if metadata_status NOT IN (COMPLETED, FAILED)

---

### I5: Metadata Status & Quality Tracking

**Question:** Should we track extraction status like FSR?

**Where to look:**
- FSR code: MetadataStatus enum (PENDING, COMPLETED, FAILED)
- Design doc: any mention of "status" or "state machine"
- DS team: did they track extraction success/failure per TIL?

**Files to check:**
- `pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py` (MetadataStatus pattern)
- DS team results CSV (do they have status field?)

**Record:**
```
Status Tracking:
1. Should we track metadata_status (PENDING → COMPLETED | FAILED)?
   [ ] Yes: like FSR pattern
   [ ] No: simpler, no status tracking
   [ ] Other: ___________________

2. If yes: also track chunk_status (for Process 2)?
   [ ] Yes: chunk_status = (PENDING → COMPLETED | FAILED)
   [ ] No: only metadata_status

3. Additional status fields?
   [ ] extraction_confidence (already in schema)
   [ ] validation_status (pass/review/fail)
   [ ] Other: ___________________
```

---

## Quick Search Commands

Run these in terminal to accelerate investigation:

```bash
# Q1: Find all LLM-related code in DS team notebooks
find /home/u560060992/dbx/1-TILs -name "*.py" -o -name "*.txt" | xargs grep -l "llm\|foundation\|gpt" 2>/dev/null

# Q2: Check if shared utilities exist
ls -la /home/u560060992/dbx/pw_sdg_ai_ser_repo/code_assets/
find /home/u560060992/dbx/pw_sdg_ai_ser_repo -type f -name "*util*" | head -20

# Q3: Search for schema/table definitions
grep -r "vgpd\|catalog\|schema\|table" /home/u560060992/dbx/1-TILs/design/*.md

# Q4: Check DS team results structure
head -50 /home/u560060992/dbx/1-TILs/analysis/ds-team-til-profile-results/*/til_profile_pilot_*/til_metadata.csv

# Q5: Look for status/state machine patterns
grep -r "status\|state\|pending\|completed" /home/u560060992/dbx/pw_sdg_ai_ser_repo --include="*.py" | grep -i "metadata\|chunk" | head -20
```

---

## Decision Template

Once you complete investigation, fill this out:

```markdown
# Investigation Results

**Date:** [YYYY-MM-DD]  
**Investigator:** [You]  
**Time spent:** [X minutes]  

## I1: LLM Calling Pattern
- DS Team uses: [Pattern]
- FSR uses: LiteLLM gateway
- **Decision:** We will use [Pattern] because [Reason]
- **Implementation:** Update [Files] with [Changes]

## I2: Shared Utilities
- Existing: [List or "None"]
- **Decision:** We will [Reuse | Build new] because [Reason]
- **Implementation:** [Details]

## I3: Table Schema
- Final schema: [Schema path]
- **Decision:** [Schema structure] because [Reason]
- **Implementation:** [Column definitions]

## I4: Unique Key & Re-extraction
- Unique key: [Key definition]
- Re-extraction policy: [Policy]
- **Decision:** MERGE ON [Fields] with [WHEN clauses]
- **Implementation:** [SQL template]

## I5: Status Tracking
- Track status: [Yes | No]
- Statuses to use: [List or "None"]
- **Decision:** [Reasoning]
- **Implementation:** [Code changes]

## Next Steps
1. [Action 1]
2. [Action 2]
3. [Action 3]
```

---

## Estimated Investigation Time

| Item | Time |
|------|------|
| I1: LLM pattern | 10 min |
| I2: Utilities | 5 min |
| I3: Schema | 10 min |
| I4: Unique key | 10 min |
| I5: Status | 5 min |
| **Total** | **40 min** |

Start with I1 and I3 (highest priority), then I4, I2, I5.

