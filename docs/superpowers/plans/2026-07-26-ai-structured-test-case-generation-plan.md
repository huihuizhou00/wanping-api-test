# AI Structured Test Case Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python tool that generates 24 structured Wanping API test scenarios through an OpenAI-compatible model, validates them, exports JSONL/CSV, and records human review outcomes.

**Architecture:** Keep AI test design separate from the Java test runner. Store verified API/business rules in YAML, generate module-sized JSON batches, validate with JSON Schema and deterministic business checks, then export auditable candidate cases and review metrics.

**Tech Stack:** Python 3.8+, OpenAI Python client, jsonschema, PyYAML, python-dotenv, unittest.

## Global Constraints

- Do not modify or execute Java test code from the generator.
- Do not invent endpoints, Redis keys, database tables, or business messages.
- Generate exactly 24 candidate scenarios with configured module quotas.
- Keep model credentials outside source control.
- Preserve invalid candidates with validation errors for pass-rate analysis.

---

### Task 1: Project scaffold and source-of-truth rules

**Files:**
- Create: `ai-case-generator/requirements.txt`
- Create: `ai-case-generator/.env.example`
- Create: `ai-case-generator/config/generator.yaml`
- Create: `ai-case-generator/config/api_rules.yaml`

- [ ] Create the Python generator directory and dependencies.
- [ ] Encode only rules supported by the existing Java clients, tests and test properties.
- [ ] Verify YAML loads successfully with `python -c`.

### Task 2: JSON Schema and prompt

**Files:**
- Create: `ai-case-generator/schemas/test-case-batch.schema.json`
- Create: `ai-case-generator/prompts/generate_cases.txt`

- [ ] Define strict fields, enums and nested request/assertion structures.
- [ ] Require JSON-only output and explicit source rule IDs.
- [ ] Validate the schema file is valid JSON.

### Task 3: Model client and prompt construction

**Files:**
- Create: `ai-case-generator/src/__init__.py`
- Create: `ai-case-generator/src/settings.py`
- Create: `ai-case-generator/src/model_client.py`
- Create: `ai-case-generator/src/prompting.py`

- [ ] Load `.env` and YAML configuration.
- [ ] Call any OpenAI-compatible `/v1/chat/completions` endpoint.
- [ ] Extract JSON from plain or fenced model output.
- [ ] Build one prompt per module and include retry feedback.

### Task 4: Deterministic validation

**Files:**
- Create: `ai-case-generator/src/validators.py`
- Test: `ai-case-generator/tests/test_validators.py`
- Create: `ai-case-generator/tests/fixtures/valid_batch.json`
- Create: `ai-case-generator/tests/fixtures/invalid_batch.json`

- [ ] Add Schema validation with per-case errors.
- [ ] Add endpoint/method, auth, message, seckill and concurrency checks.
- [ ] Add duplicate ID and module quota checks.
- [ ] Run unittest and confirm all validator tests pass.

### Task 5: Generation, export and review metrics

**Files:**
- Create: `ai-case-generator/src/exporters.py`
- Create: `ai-case-generator/src/generate_cases.py`
- Create: `ai-case-generator/src/review_summary.py`

- [ ] Generate each configured module separately with retries.
- [ ] Merge, validate and write raw JSON, JSONL, CSV and validation summary.
- [ ] Add `pending/accepted/rejected/revised` human review fields.
- [ ] Calculate Schema pass rate, business pass rate and human adoption rate.

### Task 6: Documentation and end-to-end verification

**Files:**
- Create: `ai-case-generator/README.md`
- Create: `ai-case-generator/output/.gitkeep`

- [ ] Document Ollama environment variables and commands.
- [ ] Run offline tests and prompt dry-run.
- [ ] Run live generation with an installed Ollama model.
- [ ] Confirm output contains 24 rows and review fields.
