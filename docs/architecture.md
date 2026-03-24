# Architecture Overview

## System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                              │
│   Zendesk / Gorgias / Freshdesk / Direct API / SDK              │
└────────────────────────────┬────────────────────────────────────┘
                             │  POST /agent/run  (x-api-key)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FASTAPI AGENT GATEWAY                         │
│                                                                  │
│  1. Auth (API key → org_id)                                     │
│  2. RedactionMiddleware (PII scrub on input)                    │
│  3. Policy Pre-Check (keyword/regex rules)                      │
│  4. KB Retrieval (pgvector cosine similarity)                   │
│  5. Prompt Assembly (system + workflow + KB context + policy)   │
│  6. LLM Call (OpenAI GPT-4o, configurable)                     │
│  7. Schema Validation (strict JSON output contract)             │
│  8. Policy Post-Check (output safety + citation check)         │
│  9. Approval Gate (queue if needs_approval=true)               │
│  10. Trace Log (full audit to agent_runs table)                │
└──────────────┬─────────────────────┬───────────────────────────┘
               │                     │
               ▼                     ▼
  ┌────────────────────┐   ┌──────────────────────────┐
  │  PostgreSQL +      │   │  Redis                   │
  │  pgvector          │   │  (Celery task queue)     │
  │                    │   └──────────┬───────────────┘
  │  Tables:           │              │
  │  - organizations   │              ▼
  │  - api_keys        │   ┌──────────────────────────┐
  │  - kb_sources      │   │  Celery Worker           │
  │  - kb_chunks       │   │                          │
  │  - agent_runs      │   │  - kb_ingest job         │
  │  - policy_rules    │   │    (chunk + embed)       │
  │  - policy_events   │   │  - run_evals job         │
  │  - approvals       │   │  - geo_scan job (daily)  │
  │  - eval_suites     │   └──────────────────────────┘
  │  - eval_runs       │
  └────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    STREAMLIT CONSOLE                             │
│                                                                  │
│  01_KB_Upload     → manage knowledge base sources               │
│  02_Agent_Runs    → test agent + view run history               │
│  03_Approvals     → approve/reject flagged runs                 │
│  04_Policies      → manage YAML guardrail rules                 │
│  05_Evals         → run regression suites                       │
│  06_GEO_Report    → KB health + answerability analysis          │
└─────────────────────────────────────────────────────────────────┘
```

---

## RAG Pipeline Detail

```
Ticket Text
    │
    ▼
[Embed query] ──→ text-embedding-3-small (1536-dim vector)
    │
    ▼
[pgvector search] ──→ cosine similarity against kb_chunks.embedding
    │                  WHERE org_id = ? AND source.status = 'ready'
    ▼
[Top-K chunks] ──→ ranked by similarity score (min 0.5)
    │
    ▼
[Prompt injection]
    system.md
    + workflow.md
    + KB context (source title + text excerpt + index)
    + policy constraints (from active rules)
    + ticket text
    │
    ▼
[GPT-4o] ──→ response_format: json_object
    │
    ▼
[Schema validation] ──→ validate against output_schema.json
    │                    retry once on failure
    ▼
[Output] ──→ { prospers_thoughts, ssa_guidance, draft_reply,
               clarifying_questions, internal_checklist,
               citations, risk }
```

---

## Prompt Architecture (Shoppy Bot → Platform)

The original Shoppy/Prosper prompt is decomposed into versioned files:

| File | Purpose |
|---|---|
| `prompts/support_ops/system.md` | Role, tone, safety rules, citation requirement |
| `prompts/support_ops/workflow.md` | 3-section output structure: Thoughts / SSA Guidance / Merchant Reply |
| `prompts/support_ops/output_schema.json` | Strict JSON contract enforced by runtime validator |
| `prompts/policies/default.yml` | Keyword/regex guardrail rules |
| `prompts/policies/pii_patterns.yml` | PII redaction patterns |

**Key properties:**
- Prompts are files, not hardcoded strings — version-controlled, A/B testable
- Output schema is validated in code, not just prompted
- Policy constraints are injected at runtime from DB (per-org overrides)

---

## Data Flow: KB Ingestion

```
User uploads file / adds URL (Console or API)
    │
    ▼
KBSource row created (status: pending)
    │
    ▼
Background job triggered (Celery worker)
    │
    ├── Fetch content (HTTP or file read)
    │
    ├── Chunk (512 tokens, 64 overlap, paragraph-aware)
    │
    ├── Embed (batch OpenAI embeddings)
    │
    └── Upsert to kb_chunks (pgvector)
         │
         └── KBSource status → "ready"
```

---

## Multi-Tenancy

Every table has an `org_id` foreign key.  
API keys are scoped to one org.  
All queries filter by `org_id` — orgs cannot access each other's data.

---

## Deployment Options

| Option | Good for |
|---|---|
| Docker Compose (included) | Local dev, small teams |
| Railway / Render | Quick cloud deploy, single-region |
| AWS ECS + RDS + ElastiCache | Production, multi-region |
| Kubernetes | Enterprise scale |
