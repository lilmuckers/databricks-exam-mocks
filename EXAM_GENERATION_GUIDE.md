# Exam Generation Guide

This document defines all requirements for generating mock exam JSON files for the Data Exam Prep platform. It is the authoritative reference for AI models generating exam content.

**After generating any exam file, validate it:**
```bash
python3 scripts/validate.py --exam exams/<cert-id>/exam-NN.json
```

---

## 1. File Location and Naming

- Files live at `exams/<cert-id>/exam-NN.json` where `NN` is zero-padded: `01`, `02`, `03`
- `<cert-id>` must match the `id` field in `catalog.json` exactly (e.g., `data-engineer-associate`, `snowpro-core`)
- File must be valid JSON — no trailing commas, no comments

---

## 2. Top-Level Structure

An exam file has exactly two keys:

```json
{
  "meta": { ... },
  "questions": [ ... ]
}
```

No other top-level keys are permitted.

---

## 3. The `meta` Object

All fields are required. No additional fields permitted.

```json
{
  "meta": {
    "id":                "dea-exam-06",
    "certification":     "data-engineer-associate",
    "certificationName": "Databricks Certified Data Engineer Associate",
    "title":             "DBX-DEA-6: Unity Catalog and Data Governance",
    "version":           "1.0",
    "timeLimit":         90,
    "passingScore":      70,
    "totalQuestions":    45,
    "domains": [
      { "id": "data-governance", "name": "Data Governance",          "weight": 30 },
      { "id": "lakehouse-platform", "name": "Databricks Lakehouse",  "weight": 25 },
      { "id": "elt-processing",   "name": "ELT with Spark SQL",      "weight": 25 },
      { "id": "production-pipelines", "name": "Production Pipelines","weight": 20 }
    ],
    "difficulty":        "medium",
    "status":            "available"
  }
}
```

### Field Rules

| Field | Type | Rule |
|---|---|---|
| `id` | string | Kebab-case cert code + `-exam-` + 2-digit number. Examples: `dea-exam-01`, `aws-dea-exam-01`, `snowpro-snowpark-exam-02` |
| `certification` | string | Must exactly match the catalog cert `id` and folder name |
| `certificationName` | string | Official full name of the certification |
| `title` | string | Format: `<CODE>-<N>: <Topic Description>`. Code is the uppercase abbreviated exam code (DBX-DEA, SF-SPCA, SF-SPC, AWS-DEA, GCP-PDE, etc.) |
| `version` | string | Always `"1.0"` for new exams |
| `timeLimit` | integer | Minutes. Must match the official certification exam time limit |
| `passingScore` | integer | Official passing percentage. Almost always `70` |
| `totalQuestions` | integer | Must equal the exact count of items in the `questions` array |
| `domains` | array | All domain IDs used by questions in this exam. Weights must sum to **exactly 100**. See Section 5 for valid domain IDs |
| `difficulty` | string | `"easy"`, `"medium"`, or `"hard"`. Use `"medium"` for most exams |
| `status` | string | Always `"available"` for new exams |

---

## 4. Questions Array

- Minimum 40 questions, maximum 100. Typical target: **45–60 questions**
- Match the question count in the catalog `examDetails.questions` if possible
- Questions are answered by test-takers sequentially — order intentionally mixes domains and difficulties

### Difficulty Distribution (per exam)

| Difficulty | Target | Minimum |
|---|---|---|
| `easy` | 25% | 20% |
| `medium` | 50% | 40% |
| `hard` | 25% | 20% |

---

## 5. Domain Taxonomy

Every `domain` field in a question and every `id` in `meta.domains` must be an ID from the table below. These IDs are defined in `exams/catalog.json` → `domainGroups`.

**Do not invent new domain IDs** without first adding them to `catalog.json`. See Section 5.3.

### 5.1 Complete Domain ID Reference

**Data Engineering** (`data-engineering` group)
`data-loading` · `data-movement` · `data-pipeline-design` · `data-processing` · `data-transformation` · `designing-data-processing` · `development-processing` · `dynamic-tables` · `elt-processing` · `incremental-processing` · `ingestion-acquisition` · `ingestion-processing` · `ingestion-transformation` · `preparing-data` · `production-pipelines` · `store-management` · `storing-data` · `streams-tasks` · `structured-streaming` · `transformation-quality`

**Storage & Architecture** (`storage-architecture` group)
`account-organisation` · `architecture` · `business-continuity` · `data-modeling` · `lakehouse-platform` · `storage` · `storage-compute`

**Compute & SQL** (`compute-sql` group)
`advanced-sql` · `data-exploration` · `databricks-sql` · `dataframe-api` · `pandas-on-spark` · `querying` · `semi-structured` · `semi-structured-data` · `spark-architecture` · `spark-connect` · `spark-dataframe` · `spark-sql` · `sql-lakehouse` · `virtual-warehouses`

**Machine Learning** (`machine-learning` group)
`cortex-ml` · `databricks-ml` · `experimentation` · `feature-store` · `ml-workflows` · `model-deployment` · `model-lifecycle` · `model-registry` · `scaling-ml` · `spark-ml`

**AI & Generative AI** (`ai-generative-ai` group)
`application-development` · `context-window` · `cortex-ai` · `data-preparation` · `design-applications` · `governance-evaluation` · `maintaining-applications` · `memory` · `responsible-ai` · `retrieval-search` · `system-prompts` · `tools-mcp`

**Platform & Development** (`platform-development` group)
`app-framework` · `container-deployment` · `ecosystem` · `fundamentals` · `marketplace` · `packaging` · `snowpark` · `snowpark-dataframe` · `snowpark-ml` · `stored-procedures` · `streamlit` · `streamlit-governance` · `testing-debugging` · `udfs-udtfs`

**Security & Governance** (`security-governance` group)
`access-control` · `account-administration` · `account-and-security` · `audit-compliance` · `data-governance` · `data-protection` · `data-sharing` · `governance` · `network-security` · `security` · `security-architecture` · `security-compliance` · `security-governance` · `security-permissions` · `sharing` · `sharing-and-collaboration` · `sharing-federation` · `storage-and-protection`

**Performance & Operations** (`performance-operations` group)
`cost-optimisation` · `cost-performance` · `debugging-deploying` · `maintaining-systems` · `monitoring` · `monitoring-alerting` · `operations-support` · `performance` · `performance-and-tuning` · `performance-architecture` · `performance-tuning` · `resource-monitoring` · `solution-monitoring` · `tuning-troubleshooting`

**Analytics & Visualization** (`analytics-visualization` group)
`data-management` · `deploy-maintain` · `model-data` · `prepare-data` · `visualization` · `visualization-dashboards` · `visualize-analyze`

### 5.2 Choosing the Right Domain ID

Pick the most specific ID that fits. Guidance by platform:

**Databricks certifications** — use primarily:
- `lakehouse-platform`, `elt-processing`, `incremental-processing`, `production-pipelines`, `data-governance` (DEA)
- `data-processing`, `data-modeling`, `structured-streaming`, `performance-tuning`, `data-governance`, `storage`, `data-pipeline-design` (DEP)
- `databricks-ml`, `feature-store`, `model-registry`, `model-deployment`, `experimentation`, `scaling-ml` (ML Pro/Associate)
- `application-development`, `retrieval-search`, `context-window`, `responsible-ai`, `governance-evaluation` (GenAI Engineer)
- `spark-architecture`, `spark-dataframe`, `spark-sql`, `performance-tuning` (Spark Developer)

**Snowflake certifications** — use primarily:
- `querying`, `semi-structured-data`, `virtual-warehouses`, `storage-and-protection`, `account-and-security`, `sharing-and-collaboration`, `data-movement`, `performance-and-tuning` (SnowPro Core)
- `data-pipeline-design`, `streams-tasks`, `dynamic-tables`, `snowpark`, `snowpark-dataframe`, `transformation-quality` (SnowPro Advanced Data Engineer)
- `architecture`, `storage-compute`, `business-continuity`, `performance-architecture`, `security-architecture` (SnowPro Advanced Architect)
- `cortex-ml`, `cortex-ai`, `snowpark-ml` (SnowPro Advanced Data Scientist)
- `data-sharing`, `sharing-federation`, `governance`, `data-governance`, `security-governance` (SnowPro Advanced Administrator)
- `snowpark`, `snowpark-dataframe`, `udfs-udtfs`, `stored-procedures`, `testing-debugging` (SnowPro Specialty Snowpark)

**AWS certifications** — use primarily:
- `ingestion-acquisition`, `data-processing`, `storing-data`, `querying`, `data-governance`, `security`, `monitoring` (AWS Data Engineer Associate)

**Google Cloud certifications** — use primarily:
- `data-pipeline-design`, `data-processing`, `data-modeling`, `storing-data`, `data-governance`, `security`, `monitoring-alerting` (GCP Professional Data Engineer)

### 5.3 Adding a New Domain ID

Only add a new domain ID if the concept genuinely does not fit any existing ID. Steps:

1. Choose a kebab-case ID that clearly describes the domain (e.g., `graph-analytics`)
2. Open `exams/catalog.json`
3. Find the most appropriate `domainGroups` entry
4. Add the new ID to that group's `domains` array (keep the array alphabetically sorted)
5. Only create a **new domainGroup** if the domain represents an entirely new subject area not covered by any of the 9 existing groups

**Never use a domain ID in an exam file before adding it to catalog.json.**

---

## 6. Question Structure

Every question must have all of these fields, in this order:

```json
{
  "id":          "q01",
  "domain":      "lakehouse-platform",
  "type":        "single",
  "difficulty":  "easy",
  "stem":        "Which of the following BEST describes ...",
  "options": [
    { "id": "A", "text": "Option A text" },
    { "id": "B", "text": "Option B text" },
    { "id": "C", "text": "Option C text" },
    { "id": "D", "text": "Option D text" }
  ],
  "correct":     ["B"],
  "explanation": "B is correct because ... A is incorrect because ... C is incorrect because ... D is incorrect because ...",
  "reference":   "Delta Lake transaction log and ACID guarantees"
}
```

### 6.1 `id`

- Format: `q` followed by 2-digit sequential number: `q01`, `q02`, … `q45`
- Must be **unique** within the exam file
- Do **not** include exam numbers or prefixes: `e1-q01` is **invalid** — use `q01`

### 6.2 `type`

- `"single"` — exactly one correct answer
- `"multiple"` — two or more correct answers

**Critical:** `type` describes the answer format, NOT the difficulty. Never set `type` to `"easy"`, `"hard"`, or `"medium"` — those are values for the `difficulty` field only.

### 6.3 `difficulty`

- `"easy"` — recall of a specific fact or direct application of a single concept
- `"medium"` — requires understanding relationships or applying a concept in context
- `"hard"` — requires synthesising multiple concepts, troubleshooting a scenario, or distinguishing subtle differences

### 6.4 `stem`

- Must be at least 20 characters
- Write in second or third person: "A data engineer wants to...", "Which command..."
- For scenario questions: state the scenario clearly, then ask a specific question
- For multiple-select questions: **the stem must end with `(Select TWO)`, `(Select THREE)`, etc.**
  - Example: "Which TWO of the following are valid trigger types for Structured Streaming? (Select TWO)"
- Avoid negation ("Which is NOT...") unless testing a critical misconception
- Code blocks and inline code are rendered in the UI: use backtick notation or triple-backtick blocks

### 6.5 `options`

- Minimum **4** options, maximum **6**. Standard is 4 (A–D)
- Option `id` values must be **consecutive uppercase letters starting from A**: `A`, `B`, `C`, `D` (for 4 options), `A`–`E` (for 5), `A`–`F` (for 6)
- **Forbidden option texts** (these are lazy distractors that reveal the answer by elimination):
  - "All of the above"
  - "None of the above"
  - "Both A and B"
  - "All the above"
  - "None of these"
- Each option must be a complete, independently evaluable statement
- Distractors must be plausible to someone with partial knowledge — not obviously wrong
- Options should be roughly similar in length and specificity

### 6.6 `correct`

- Array of option ID strings: `["B"]` for single, `["A", "C"]` for multiple
- For `type: "single"`: exactly **1** element
- For `type: "multiple"`: **2–4** elements
- All values must be valid option IDs that exist in the `options` array

### 6.7 `explanation`

- Minimum 50 characters (typically 100–300 characters)
- Must explain **every option** — why correct answers are right AND why each wrong answer is wrong
- Format: "**B** is correct because [specific reason]. **A** is incorrect because [specific reason]. **C** is incorrect because [specific reason]. **D** is incorrect because [specific reason]."
- Do not use vague language like "B is best". State the specific technical reason
- Explanations are shown to test-takers after answering — treat them as teaching moments

### 6.8 `reference`

- Short string naming the documentation section, concept, or feature being tested
- Examples:
  - `"Delta Lake OPTIMIZE and Z-ORDER commands"`
  - `"Snowflake Time Travel and Fail-safe"`
  - `"Unity Catalog privilege hierarchy"`
  - `"Structured Streaming trigger types: processingTime, availableNow, continuous"`

---

## 7. Question Writing Quality Rules

### Do
- Test concepts from the official exam guide and certification syllabus
- Write distractors that represent common misconceptions or mistakes practitioners make
- Use realistic scenario names (e.g., a data engineer called "Maya", a table called `orders`)
- Include code snippets when testing specific syntax (`%run`, `MERGE INTO`, `CREATE STREAMING LIVE TABLE`)
- Ensure the correct answer is unambiguously correct based on official documentation

### Do Not
- Test trivia or overly specific version numbers that may change
- Write questions where two options are both defensibly correct
- Make the correct answer the longest or most detailed option (answer-length bias)
- Always put the correct answer at position B or C (rotate it)
- Copy questions verbatim from other sources
- Include questions that require knowledge beyond the certification's stated exam guide scope
- Generate placeholder text like "This question tests…" in any field

---

## 8. Complete Example Question

### Single-select (medium, with code block)

```json
{
  "id": "q14",
  "domain": "incremental-processing",
  "type": "single",
  "difficulty": "medium",
  "stem": "A data engineer writes the following Auto Loader stream:\n\n```python\n(spark.readStream\n  .format('cloudFiles')\n  .option('cloudFiles.format', 'json')\n  .option('cloudFiles.schemaLocation', '/checkpoints/schema')\n  .load('/landing/events')\n  .writeStream\n  .trigger(availableNow=True)\n  .option('checkpointLocation', '/checkpoints/events')\n  .toTable('events_bronze')\n)\n```\n\nWhat is the behaviour of `trigger(availableNow=True)`?",
  "options": [
    { "id": "A", "text": "The stream runs continuously, processing new files as they arrive" },
    { "id": "B", "text": "The stream processes all files currently available then stops, like a batch job" },
    { "id": "C", "text": "The stream processes one micro-batch every 30 seconds" },
    { "id": "D", "text": "The stream processes a single micro-batch of at most 1000 records then stops" }
  ],
  "correct": ["B"],
  "explanation": "B is correct. `availableNow=True` (formerly `Trigger.Once`) processes all data currently available in the source in one or more micro-batches then terminates — semantically like a batch job but leveraging streaming checkpointing for idempotency. A is incorrect because continuous processing requires `trigger(processingTime='X seconds')` or no trigger. C is incorrect because a time-based trigger would use `trigger(processingTime='30 seconds')`. D is incorrect because `availableNow` does not impose a record limit; it processes all available data.",
  "reference": "Structured Streaming trigger types: availableNow (formerly Trigger.Once)"
}
```

### Multiple-select (hard)

```json
{
  "id": "q27",
  "domain": "data-governance",
  "type": "multiple",
  "difficulty": "hard",
  "stem": "A data engineer needs to grant an analyst the ability to query tables in the `reporting` schema within Unity Catalog but prevent them from reading any tables in the `pii` schema in the same catalog. Which TWO privilege assignments achieve this with least privilege? (Select TWO)",
  "options": [
    { "id": "A", "text": "GRANT USE CATALOG ON CATALOG main TO analyst_group" },
    { "id": "B", "text": "GRANT SELECT ON SCHEMA main.reporting TO analyst_group" },
    { "id": "C", "text": "GRANT SELECT ON CATALOG main TO analyst_group" },
    { "id": "D", "text": "GRANT USE SCHEMA ON SCHEMA main.reporting TO analyst_group" },
    { "id": "E", "text": "GRANT USE SCHEMA ON SCHEMA main.pii TO analyst_group" }
  ],
  "correct": ["A", "D"],
  "explanation": "A and D are correct. In Unity Catalog, to query tables in a schema the principal needs USE CATALOG on the catalog (A) and USE SCHEMA on the target schema (D) — plus SELECT on the tables or schema. This grants minimum access without touching the pii schema. B is incorrect because SELECT on the schema alone is insufficient without USE SCHEMA; also B would need to be combined with A and D but SELECT is not required by itself to satisfy the question. C is incorrect because SELECT ON CATALOG grants SELECT on every schema including pii, violating least privilege. E is incorrect because granting USE SCHEMA on the pii schema would give access to pii, which is explicitly prohibited.",
  "reference": "Unity Catalog privilege hierarchy: USE CATALOG, USE SCHEMA, SELECT"
}
```

---

## 9. Domain Weight Distribution

The `meta.domains` array declares which domains the exam covers and in what proportion. Rules:

- Weights must sum to **exactly 100**
- Reflect the actual distribution of questions in the exam (a domain with weight 20 should have roughly 20% of questions)
- Use weights from the official exam guide where available — real certification exams publish domain weights in their study guides
- Minimum weight per declared domain: **1** (don't declare a domain you won't test)
- Maximum weight: **60** (no single domain should dominate entirely)

Example for a 45-question exam:
```json
"domains": [
  { "id": "lakehouse-platform",  "name": "Databricks Lakehouse Platform",  "weight": 24 },
  { "id": "elt-processing",      "name": "ELT with Spark SQL and Python",  "weight": 29 },
  { "id": "incremental-processing", "name": "Incremental Data Processing", "weight": 22 },
  { "id": "production-pipelines","name": "Production Pipelines",           "weight": 16 },
  { "id": "data-governance",     "name": "Data Governance",                "weight": 9  }
]
```

---

## 10. Exam Title Code Reference

Use the correct code prefix in the `title` field for each certification:

| Certification | Code prefix | Example title |
|---|---|---|
| Databricks Data Engineer Associate | `DBX-DEA` | `DBX-DEA-3: Delta Lake and Auto Loader` |
| Databricks Data Engineer Professional | `DBX-DEP` | `DBX-DEP-6: Performance and Optimization` |
| Databricks Machine Learning Associate | `DBX-MLA` | `DBX-MLA-2: Feature Engineering and MLflow` |
| Databricks Machine Learning Professional | `DBX-MLP` | `DBX-MLP-3: Model Serving and Monitoring` |
| Databricks Generative AI Engineer Associate | `DBX-GAIA` | `DBX-GAIA-3: RAG Pipelines and Evaluation` |
| Databricks Spark Developer Associate | `DBX-SDA` | `DBX-SDA-4: Spark SQL and DataFrames` |
| Databricks Data Analyst Associate | `DBX-DAA` | `DBX-DAA-2: Databricks SQL and Dashboards` |
| Databricks Context Engineering Associate | `DBX-CEA` | `DBX-CEA-2: Memory and MCP Tooling` |
| SnowPro Core | `SF-SPC` | `SF-SPC-4: Virtual Warehouses and Storage` |
| SnowPro Advanced Data Engineer | `SF-SPADE` | `SF-SPADE-4: Streams and Dynamic Tables` |
| SnowPro Advanced Architect | `SF-SPCA` | `SF-SPCA-3: High Availability and DR` |
| SnowPro Advanced Data Scientist | `SF-SPDS` | `SF-SPDS-2: Cortex ML and Feature Store` |
| SnowPro Advanced Administrator | `SF-SPAA` | `SF-SPAA-3: Data Governance and Sharing` |
| SnowPro Specialty Native Apps | `SF-SPSNA` | `SF-SPSNA-2: Streamlit and Marketplace` |
| SnowPro Specialty Snowpark | `SF-SPSSP` | `SF-SPSSP-2: Stored Procedures and UDFs` |
| AWS Data Engineer Associate | `AWS-DEA` | `AWS-DEA-2: Glue, Redshift and S3` |
| GCP Professional Data Engineer | `GCP-PDE` | `GCP-PDE-2: BigQuery and Dataflow` |
| Microsoft Power BI Data Analyst | `MS-PBI` | `MS-PBI-2: DAX and Data Modeling` |

---

## 11. Validation Checklist

Before submitting an exam file, verify all of the following:

**Structure**
- [ ] File is valid JSON (no trailing commas, no comments)
- [ ] Top level has only `meta` and `questions` keys
- [ ] `meta.totalQuestions` equals `questions.length`

**Meta**
- [ ] `meta.id` format is `<code>-exam-<NN>` (e.g., `dea-exam-06`)
- [ ] `meta.certification` matches the catalog cert `id` exactly
- [ ] `meta.title` format is `<CODE>-<N>: <Description>` (e.g., `DBX-DEA-6: ...`)
- [ ] `meta.version` is `"1.0"`
- [ ] `meta.timeLimit` matches the official certification time limit
- [ ] `meta.passingScore` matches the official passing score (usually 70)
- [ ] `meta.domains` weights sum to exactly 100
- [ ] All domain IDs in `meta.domains` exist in `catalog.json` domainGroups
- [ ] `meta.status` is `"available"`

**Questions**
- [ ] Question count is between 40 and 100
- [ ] Difficulty distribution: ~25% easy, ~50% medium, ~25% hard
- [ ] Question IDs are sequential `q01`–`qNN` with no gaps, no prefixes
- [ ] No duplicate question IDs
- [ ] Every `domain` value exists in `catalog.json` domainGroups
- [ ] Every `domain` value appears in `meta.domains`
- [ ] All `type` values are exactly `"single"` or `"multiple"` (not `"easy"`, `"hard"`, etc.)
- [ ] Single-type questions have exactly 1 correct answer
- [ ] Multiple-type questions have 2–4 correct answers
- [ ] Multiple-type stems end with `(Select TWO)` / `(Select THREE)` etc.
- [ ] Options use consecutive IDs A, B, C, D (minimum 4, maximum 6)
- [ ] No option uses "All of the above", "None of the above", or "Both A and B"
- [ ] All `correct` values reference valid option IDs in the question
- [ ] Explanations cover WHY each option is right or wrong
- [ ] Explanations are at least 50 characters

**Run the validator:**
```bash
python3 scripts/validate.py --exam exams/<cert-id>/exam-NN.json
```
All errors must be fixed. Warnings should be reviewed.

---

## 12. Adding a New Certification

If generating exams for a new certification:

1. Add the certification entry to `exams/catalog.json` in the `certifications` array (see existing entries for the full required structure)
2. Create the directory `exams/<cert-id>/`
3. Identify which domain IDs from Section 5 apply; add any missing domain IDs to `catalog.json` per Section 5.3
4. Populate `syllabus` in the catalog entry — AI generators use this to produce accurate questions
5. Run `python3 scripts/validate.py --catalog` to verify the catalog before generating exam files
