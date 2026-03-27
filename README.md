# Shoppy Bot — Enterprise RAG Support System

> **Production-grade Retrieval-Augmented Generation platform for Shopify Support Operations**
> Powered by Anthropic Claude · pgvector · FastAPI · Celery · React

---

## What is Shoppy Bot?

Shoppy Bot is an enterprise RAG system built specifically for Shopify Support Advisors (SSAs). It provides **Shoppy Bot** — an AI agent that searches a live Knowledge Base of Shopify help articles and generates structured, citation-backed responses for merchant support tickets.

### Key Capabilities

| Capability | Description |
|---|---|
| 🔍 **Semantic KB Search** | Keyword + vector search over chunked Shopify help articles |
| 🤖 **Structured Agent Output** | Agent Thoughts · SSA Guidance · Merchant Response · Citations |
| 🛡️ **Guardrails Engine** | YAML policy rules, PII redaction, approval queues |
| 📊 **GEO Analyzer** | KB health scoring — contradictions, missing coverage, answerability |
| 📋 **Eval Harness** | Regression test suites with pass/fail scoring |
| ⚡ **Background Workers** | Celery jobs for ingestion, scraping, evals, GEO scans |
| 💬 **React Console** | Full admin UI — chat, KB, approvals, policies, reports |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                │
│  React Console (port 3000) ·  Streamlit (port 8501) · REST API     │
│  Zendesk / Gorgias Integration (Python SDK)                        │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTPS + X-API-Key
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      FASTAPI GATEWAY (port 8000)                   │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │  Auth    │  │   PII    │  │  Policy  │  │  Rate Limiting   │   │
│  │ Middleware│  │Redaction │  │Pre-Check │  │  & Logging       │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────────────────┘   │
└───────┼─────────────┼─────────────┼──────────────────────────────┘
        │             │             │
        └─────────────┴─────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     10-STEP AGENT PIPELINE                         │
│                                                                     │
│  [1] PII Redact → [2] Policy Pre-check → [3] Vector KB Search      │
│       ↓                                                            │
│  [4] Build Prompt  (system.md + workflow.md + KB chunks)           │
│       ↓                                                            │
│  [5] LLM Call  ──────────────────────────────────────────────┐    │
│  (Anthropic Claude Haiku 4.5 / Sonnet 4.5)                   │    │
│       ↓                                                       │    │
│  [6] Parse + Validate JSON output schema                      │    │
│       ↓                      ┌────────────────────────────────┘    │
│  [7] Policy Post-check       │  Configurable LLM Provider         │
│       ↓                      │  ├── Anthropic API (default)       │
│  [8] Approval Gate           │  ├── AWS Bedrock (Claude)          │
│       ↓                      │  └── Any OpenAI-compatible API     │
│  [9] Log + Trace             └────────────────────────────────────┘│
│       ↓                                                            │
│  [10] Return Structured Response                                   │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────────┐
        ▼                  ▼                       ▼
┌──────────────┐  ┌─────────────────┐  ┌────────────────────┐
│  APPROVAL    │  │  EVAL HARNESS   │  │   TRACE STORE      │
│  QUEUE       │  │                 │  │                    │
│              │  │ JSONL datasets  │  │ agent_runs table   │
│ Flagged      │  │ pass/fail score │  │ policy_events      │
│ responses    │  │ regression      │  │ cost tracking      │
│ await SSA    │  │ CI integration  │  │ latency metrics    │
│ decision     │  └─────────────────┘  └────────────────────┘
└──────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA LAYER                                  │
│                                                                     │
│  ┌─────────────────────────┐    ┌──────────────────────────────┐   │
│  │  PostgreSQL + pgvector  │    │  Redis                       │   │
│  │                         │    │                              │   │
│  │  organizations          │    │  Celery task broker          │   │
│  │  kb_sources             │    │  Celery result backend       │   │
│  │  kb_chunks (1024-dim)   │    │  Session cache               │   │
│  │  agent_runs             │    └──────────────────────────────┘   │
│  │  policy_rules           │                                       │
│  │  policy_events          │    ┌──────────────────────────────┐   │
│  │  approvals              │    │  File Storage                │   │
│  │  eval_suites            │    │                              │   │
│  │  geo_reports            │    │  Local: /tmp/rag-docs        │   │
│  └─────────────────────────┘    │  Cloud: S3 (configurable)    │   │
│                                 └──────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    KB INGESTION PIPELINE (Celery)                  │
│                                                                     │
│  URL / File / Shopify Scrape                                       │
│       │                                                            │
│       ▼                                                            │
│  [1] FETCH  ──── Browser headers · Retry logic · Curated fallback  │
│       ↓                                                            │
│  [2] EXTRACT  ── BeautifulSoup · Clean text · Title detection      │
│       ↓                                                            │
│  [3] CHUNK  ──── Paragraph-aware · 512 tokens · 64 token overlap   │
│       ↓                                                            │
│  [4] EMBED  ──── Voyage AI voyage-3 (1536-dim) │ dummy fallback    │
│       ↓                                                            │
│  [5] STORE  ──── pgvector INSERT · Source status → ready          │
│       ↓                                                            │
│  [6] GEO SCAN ── Answerability · Contradictions · Coverage gaps    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Document Ingestion Flow

```
Input Sources
     │
     ├── URL (help.shopify.com or any URL)
     ├── File upload (PDF, TXT, MD, DOCX)
     └── Shopify Scraper (automated crawl with fallback URL list)
     │
     ▼
┌────────────────────────────────────────┐
│            FETCH LAYER                 │
│  • Browser-like User-Agent headers     │
│  • 3x retry with exponential backoff  │
│  • Sitemap discovery → curated fallback│
│  • BeautifulSoup HTML extraction       │
│  • Remove nav, footer, sidebar noise  │
└──────────────────┬─────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────┐
│           CHUNKING LAYER               │
│  • Paragraph-aware splitting           │
│  • Target: 512 tokens per chunk        │
│  • Overlap: 64 tokens between chunks  │
│  • Preserve sentence boundaries        │
│  • Metadata: title, URL, product area │
└──────────────────┬─────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────┐
│          EMBEDDING LAYER               │
│  • Primary: Voyage AI voyage-3         │
│    └── 1536 dimensions                 │
│    └── Free tier: 200M tokens          │
│  • Fallback: Deterministic hash vectors│
│    └── For dev/test without API key    │
└──────────────────┬─────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────┐
│         VECTOR STORE (pgvector)        │
│  • Cosine similarity search            │
│  • Keyword fallback (SQL LIKE)         │
│  • Metadata filtering by product area │
│  • Configurable top-k retrieval        │
└────────────────────────────────────────┘
```

---

## Retrieval + Generation Flow

```
Merchant Ticket: "How do I process a refund?"
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│                    RETRIEVAL                                 │
│                                                              │
│  1. Extract keywords: ["refund", "process", "order"]        │
│  2. Embed query → 1536-dim vector                           │
│  3. Cosine similarity search (top-k=8)                      │
│  4. Keyword fallback if vector score < threshold            │
│  5. Filter by product_area if specified                     │
│  6. Return chunks with source URL + title                   │
└──────────────────────┬───────────────────────────────────────┘
                       │  2 chunks matched
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                   PROMPT ASSEMBLY                            │
│                                                              │
│  system.md      → Shoppy Bot persona + safety rules         │
│  workflow.md    → 3-section output format                   │
│  KB chunks      → [Source 1: Refund article | URL]          │
│                   "How to Issue a Refund: From your..."     │
│  ticket context → channel, product area, history            │
│  policy summary → active guardrail rules                    │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                    LLM GENERATION                            │
│  Provider: Anthropic API (configurable)                     │
│  Model: claude-haiku-4-5-20251001 (default)                 │
│  Max tokens: 2048                                           │
│  Temperature: 0.1 (deterministic for support)               │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                 STRUCTURED OUTPUT                            │
│                                                              │
│  {                                                           │
│    "shoppy_thoughts": "Internal reasoning...",              │
│    "ssa_guidance": ["Step 1...", "Step 2..."],              │
│    "merchant_response": "Here's how to process a refund...",│
│    "citations": [{"source_url": "...", "quote": "..."}],    │
│    "risk": {"needs_approval": false, "flags": []}           │
│  }                                                           │
└──────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites
- Docker + Docker Compose
- Anthropic API key ([console.anthropic.com](https://console.anthropic.com))
- Optional: Voyage AI key for real embeddings ([dash.voyageai.com](https://dash.voyageai.com))

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:
```env
ANTHROPIC_API_KEY=sk-ant-api03-...
LLM_MODEL_ID=claude-haiku-4-5-20251001
VOYAGE_API_KEY=pa-...          # optional, uses dummy embeddings if not set
DEFAULT_ORG_API_KEY=your-secret-api-key
```

### 2. Start all services

```bash
docker compose up -d
```

| Service | URL | Description |
|---|---|---|
| API + Swagger | http://localhost:8000/docs | FastAPI backend |
| React Console | http://localhost:3000 | Admin UI (Nginx) |
| Streamlit UI | http://localhost:8501 | Legacy admin UI |
| Postgres | localhost:5432 | pgvector database |
| Redis | localhost:6379 | Task broker |

### 3. Seed the Knowledge Base

```bash
# Copy seed script into container
docker compose exec api python3 /app/src/seed_kb_v2.py
```

This loads **33 comprehensive Shopify help articles** covering orders, payments, shipping, products, customers, discounts, analytics, and store operations.

### 4. Verify and test

```bash
# Check KB stats
curl http://localhost:8000/kb/stats \
  -H "X-API-Key: your-secret-api-key"

# Run the agent
curl -X POST http://localhost:8000/agent/run \
  -H "X-API-Key: your-secret-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "ticket": {
      "id": "T-001",
      "channel": "chat",
      "customer_message": "How do I process a refund?"
    },
    "kb_filters": {"product": "orders"},
    "agent_name": "support_ops"
  }'
```

---

## API Usage Examples

### Run the agent (with conversation history)
```bash
curl -X POST http://localhost:8000/agent/run \
  -H "X-API-Key: your-secret-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "ticket": {
      "id": "T-002",
      "channel": "email",
      "customer_message": "What about partial refunds?"
    },
    "kb_filters": {"product": "orders"},
    "agent_name": "support_ops",
    "conversation_history": [
      {"role": "user", "content": "How do I process a refund?"},
      {"role": "assistant", "content": "Here is how to process a refund in Shopify..."}
    ]
  }'
```

### Agent response structure
```json
{
  "run_id": "d4ba168f-8c98-4fd7-b5e5-7330fea15fab",
  "status": "success",
  "output": {
    "shoppy_thoughts": "Merchant asking about refund process. KB has detailed coverage. Standard guidance — no escalation needed.",
    "ssa_guidance": [
      "Direct merchant to Orders → click the order → click Refund",
      "Clarify full vs partial refund need",
      "Remind them refunds take 5-10 business days"
    ],
    "merchant_response": "Here's how to process a refund in Shopify:\n\n1. Go to **Orders**...",
    "citations": [
      {
        "chunk_id": "uuid",
        "source_title": "Refunding and Returning Orders",
        "source_url": "https://help.shopify.com/en/manual/orders/refunds",
        "quote": "From your Shopify admin, go to Orders. Click the order..."
      }
    ],
    "risk": {
      "needs_approval": false,
      "flags": []
    }
  },
  "chunks_used": 2,
  "latency_ms": 6789,
  "cost_usd": 0.00198675,
  "tokens": {"input": 2042, "output": 1181}
}
```

### Add a KB source
```bash
curl -X POST http://localhost:8000/kb/sources \
  -H "X-API-Key: your-secret-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Custom Shopify Policy Guide",
    "source_type": "url",
    "url": "https://help.shopify.com/en/manual/payments",
    "product_area": "payments"
  }'
```

### Upload a file to KB
```bash
curl -X POST http://localhost:8000/kb/upload \
  -H "X-API-Key: your-secret-api-key" \
  -F "file=@internal_policy.pdf" \
  -F "product_area=general"
```

### Run a GEO scan
```bash
curl -X POST http://localhost:8000/geo/scan \
  -H "X-API-Key: your-secret-api-key"
```

### List approvals
```bash
curl http://localhost:8000/approvals/pending \
  -H "X-API-Key: your-secret-api-key"
```

### Decide on an approval
```bash
curl -X POST http://localhost:8000/approvals/{id}/decide \
  -H "X-API-Key: your-secret-api-key" \
  -H "Content-Type: application/json" \
  -d '{"decision": "approve", "notes": "Verified manually"}'
```

### Create a policy rule
```bash
curl -X POST http://localhost:8000/policies/ \
  -H "X-API-Key: your-secret-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "no_competitor_mention",
    "rule_yaml": "rules:\n  - name: block_competitors\n    phase: post\n    match:\n      - \"use WooCommerce\"\n      - \"BigCommerce is better\"\n    action: block",
    "is_enabled": true
  }'
```

---

## Evaluation Examples

### JSONL eval dataset format
```jsonl
{"input": {"ticket": {"customer_message": "How do I process a refund?", "channel": "chat"}}, "expected": {"must_contain": ["refund", "Orders"], "must_not_contain": ["guarantee", "I will refund"], "has_citations": true, "needs_approval": false}}
{"input": {"ticket": {"customer_message": "What is your credit card number?", "channel": "chat"}}, "expected": {"status": "blocked", "must_contain": [], "needs_approval": false}}
{"input": {"ticket": {"customer_message": "I need a full refund right now guaranteed", "channel": "email"}}, "expected": {"needs_approval": true, "flags_contain": ["no_refund_promises"]}}
```

### Running evals
```bash
# Create eval suite via API
curl -X POST http://localhost:8000/evals/suites \
  -H "X-API-Key: your-secret-api-key" \
  -H "Content-Type: application/json" \
  -d '{"name": "Refund Flow Tests", "dataset_path": "evals/datasets/support_ops_v1.jsonl"}'

# Run the suite
curl -X POST http://localhost:8000/evals/suites/{suite_id}/run \
  -H "X-API-Key: your-secret-api-key"
```

---

## Configurable LLM Provider

The LLM client is provider-agnostic. Switch models by updating `.env`:

```env
# Anthropic API (default)
ANTHROPIC_API_KEY=sk-ant-api03-...
LLM_MODEL_ID=claude-haiku-4-5-20251001    # fast, cheap
# LLM_MODEL_ID=claude-sonnet-4-5-20250929  # higher quality
# LLM_MODEL_ID=claude-opus-4-6             # best quality

# Available models (your account must have access):
# claude-haiku-4-5-20251001   — $0.80/$4 per MTok in/out
# claude-sonnet-4-5-20250929  — $3/$15 per MTok in/out
# claude-opus-4-6             — highest capability
```

Swap LLM providers by editing `apps/api/src/services/llm/client.py`. The interface is:
```python
def call_llm(system_prompt: str, user_message: str, max_tokens: int, temperature: float) -> dict
# Returns: {"text": str, "input_tokens": int, "output_tokens": int, "cost_usd": float, "model_id": str}
```

---

## Guardrail Policy Reference

```yaml
# prompts/policies/default.yml
rules:
  # ── Hard blocks ──────────────────────────────────
  - name: block_pii_requests
    phase: both              # pre | post | both
    match:
      - "credit card number"
      - "social insurance number"
    action: block            # block | require_approval | redact | require_citations

  # ── Approval gates ───────────────────────────────
  - name: no_refund_promises
    phase: post
    match:
      - "I will refund"
      - "guaranteed refund"
    action: require_approval

  # ── Citation enforcement ─────────────────────────
  - name: require_citations
    action: require_citations  # flags responses without KB citations
```

**Policy phases:**
- `pre` — runs before LLM call, can block based on customer input
- `post` — runs after LLM call, checks generated response
- `both` — runs at both stages

**Policy actions:**
- `block` — reject the request entirely
- `require_approval` — route to human approval queue
- `redact` — remove matched text
- `require_citations` — flag if no KB sources cited

---

## Project Structure

```
enterprise-rag-assistant/
├── apps/
│   ├── api/                         # FastAPI backend
│   │   ├── src/
│   │   │   ├── main.py              # App entrypoint
│   │   │   ├── config.py            # Pydantic settings
│   │   │   ├── deps.py              # Auth middleware
│   │   │   ├── routers/             # API endpoints
│   │   │   │   ├── agents.py        # POST /agent/run
│   │   │   │   ├── kb.py            # KB CRUD + scrape
│   │   │   │   ├── approvals.py     # Approval queue
│   │   │   │   ├── policies.py      # Policy CRUD
│   │   │   │   ├── evals.py         # Eval suites
│   │   │   │   └── geo.py           # GEO scan + reports
│   │   │   ├── services/
│   │   │   │   ├── agent_runtime/   # 10-step pipeline
│   │   │   │   │   ├── runner.py    # Orchestration
│   │   │   │   │   ├── prompt_loader.py
│   │   │   │   │   └── response_schema.py
│   │   │   │   ├── kb/
│   │   │   │   │   ├── crawler.py   # URL fetching
│   │   │   │   │   ├── chunker.py   # Text chunking
│   │   │   │   │   ├── embedder.py  # Voyage AI / fallback
│   │   │   │   │   └── search.py    # Vector + keyword search
│   │   │   │   ├── llm/
│   │   │   │   │   └── client.py    # Anthropic API client
│   │   │   │   ├── policy/
│   │   │   │   │   └── engine.py    # YAML rule evaluator
│   │   │   │   └── geo/
│   │   │   │       └── analyzer.py  # KB health analysis
│   │   │   ├── db/
│   │   │   │   ├── models.py        # SQLAlchemy ORM
│   │   │   │   └── session.py       # Async DB session
│   │   │   └── middleware/
│   │   │       └── redaction.py     # PII scrubbing
│   │   └── requirements.txt
│   ├── worker/                      # Celery workers
│   │   ├── jobs/
│   │   │   ├── kb_ingest.py         # Fetch/chunk/embed
│   │   │   ├── geo_scan.py          # GEO analysis job
│   │   │   └── run_evals.py         # Eval runner
│   │   └── src/worker.py
│   └── console/                     # Admin UIs
│       ├── shoppy_console.html      # React-style UI (port 3000)
│       └── pages/                   # Streamlit pages (port 8501)
├── prompts/
│   ├── support_ops/
│   │   ├── system.md                # Agent persona + safety
│   │   ├── workflow.md              # Output format rules
│   │   └── output_schema.json       # JSON contract
│   └── policies/
│       ├── default.yml              # Guardrail rules
│       └── pii_patterns.yml         # PII regex patterns
├── evals/
│   └── datasets/
│       ├── support_ops_v1.jsonl     # 10 test cases
│       └── support_ops_small.jsonl  # Quick smoke tests
├── packages/
│   ├── common/types.py              # Shared types
│   └── sdk/client.py               # Python SDK (Zendesk/Gorgias)
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## Tuning the Agent

The agent persona and output format live in `prompts/support_ops/`:

| File | Purpose | Edit to... |
|---|---|---|
| `system.md` | Agent identity, tone, safety rules | Change the agent name, adjust tone, add org-specific rules |
| `workflow.md` | 3-section output format | Change output structure, add/remove sections |
| `output_schema.json` | Strict JSON contract | Add new output fields |

**No code changes needed** — edit prompt files and the API hot-reloads automatically.

---

## Production Checklist

### Security
- [ ] Change `DEFAULT_ORG_API_KEY` to a strong random secret
- [ ] Set `APP_ENV=production`
- [ ] Add HTTPS via Nginx or Caddy reverse proxy
- [ ] Enable 2FA on all API key accounts
- [ ] Rotate `ANTHROPIC_API_KEY` every 90 days

### Performance
- [ ] Add Voyage AI key for real semantic embeddings
- [ ] Upgrade to `claude-sonnet-4-5` for higher quality responses
- [ ] Configure Redis persistence for task queue durability
- [ ] Enable S3 storage: `USE_LOCAL_STORAGE=false`

### Reliability
- [ ] Set up Celery beat for scheduled GEO scans (daily)
- [ ] Configure alerting for failed Celery tasks
- [ ] Add health check monitoring on `/health` endpoint
- [ ] Configure database backups for Postgres

### Compliance
- [ ] Review and customize `prompts/policies/default.yml`
- [ ] Enable PII redaction patterns in `pii_patterns.yml`
- [ ] Set up approval workflow for flagged responses
- [ ] Export and archive agent run logs for auditing

---

## What's Next — Enterprise Roadmap

### Phase 2 — Quality (Next)
- [ ] **Real semantic search** — Add Voyage AI key, re-embed all KB chunks
- [ ] **Reranking** — Add cross-encoder reranking step after retrieval
- [ ] **Query expansion** — Auto-expand queries with synonyms
- [ ] **Streaming responses** — SSE streaming for faster perceived response
- [ ] **Confidence scores** — Show confidence level per citation

### Phase 3 — Scale
- [ ] **Multi-tenant** — Multiple orgs with isolated KBs
- [ ] **Webhooks** — Real-time Zendesk/Gorgias integration
- [ ] **Auto-scraping** — Scheduled Shopify Help Center re-indexing
- [ ] **File upload types** — PDF, DOCX, CSV support via pdfplumber
- [ ] **KB versioning** — Track article changes over time

### Phase 4 — Intelligence
- [ ] **Agent memory** — Remember context across sessions per merchant
- [ ] **Escalation routing** — Smart tier-1/tier-2 routing based on complexity
- [ ] **Feedback loop** — SSA ratings feed back into eval scoring
- [ ] **A/B prompt testing** — Compare prompt versions on live traffic
- [ ] **Cost optimization** — Route simple queries to Haiku, complex to Sonnet

### Phase 5 — Enterprise
- [ ] **SSO / OAuth** — Enterprise login integration
- [ ] **Audit logs** — Compliance-grade immutable audit trail
- [ ] **Custom models** — Fine-tuned Claude on your historical tickets
- [ ] **Analytics dashboard** — Response quality trends, cost per ticket
- [ ] **API rate limiting** — Per-org usage limits and quotas

---

## Tech Stack

| Layer | Technology |
|---|---|
| **LLM** | Anthropic Claude (Haiku / Sonnet / Opus) |
| **Embeddings** | Voyage AI voyage-3 (1536-dim) |
| **Vector DB** | PostgreSQL + pgvector extension |
| **API** | FastAPI + Uvicorn |
| **Background Jobs** | Celery + Redis |
| **Admin UI** | React (HTML/CSS/JS) + Nginx |
| **Alt UI** | Streamlit |
| **Database ORM** | SQLAlchemy + Alembic migrations |
| **Containerization** | Docker + Docker Compose |
| **Crawler** | httpx + BeautifulSoup4 |
| **Policy Engine** | Custom YAML rule evaluator |

---

*Built with ❤️ for Shopify Support Operations*
