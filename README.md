# Enterprise RAG Assistant
### Production-grade Shopify Support RAG system — powered by AWS Bedrock

A fully agentic support operations platform with:
- **RAG pipeline** — document ingestion, chunking, pgvector embeddings, semantic search
- **AWS Bedrock** — Claude 3.5 Sonnet (LLM) + Titan Embeddings v2 (1024-dim)
- **Shopify KB** — automatic crawl of help.shopify.com + your own internal docs
- **Guardrails** — YAML policy engine, PII redaction, approval queues
- **Evals** — regression test suites with scoring
- **GEO Analyzer** — KB health: contradictions, missing questions, answerability score
- **Streamlit Console** — full admin UI (KB, runs, approvals, policies, evals, GEO)

---

## Architecture

```
Client (Zendesk / Gorgias / API / Streamlit)
        │
        ▼
FastAPI Agent Gateway  (auth · PII redaction · policy pre-check)
        │
        ▼
RAG Pipeline  (query embed → pgvector search → rerank → LLM generation)
        │
        ▼
Guardrails  (citation check · forbidden phrases · approval gate)
        │
        ▼
Trace Logger  (agent_runs · policy_events · costs)
        │
    ┌───┴────────────────┐
    ▼                    ▼
Approvals Queue      Eval Harness
(Streamlit review)   (regression scoring)
        │
        ▼
Data Layer: Postgres + pgvector · Redis · S3/local · Celery workers
        │
        ▼
KB Ingestion Pipeline  (crawl → chunk → embed → GEO analyze)
```

---

## Quick Start

### 1. Prerequisites
- Docker + Docker Compose
- AWS account with Bedrock access enabled
- AWS IAM user with `AmazonBedrockFullAccess` policy

### 2. Configure AWS credentials

```bash
cp .env.example .env
```

Edit `.env` and fill in:
```
AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=YOUR_AWS_SECRET_ACCESS_KEY
AWS_REGION=us-east-1
```

> **Bedrock model access**: In the AWS Console → Bedrock → Model access, enable:
> - `anthropic.claude-3-5-sonnet-20241022-v2:0`
> - `amazon.titan-embed-text-v2:0`

### 3. Start all services

```bash
make up
```

Services:
| Service | URL |
|---|---|
| API + Swagger docs | http://localhost:8000/docs |
| Streamlit Console | http://localhost:8501 |
| Postgres | localhost:5432 |
| Redis | localhost:6379 |

### 4. Seed default policies

```bash
make seed-policies
```

### 5. Ingest Shopify Help Center

```bash
make scrape-shopify
```

This crawls `help.shopify.com/en/manual` (up to 100 pages by default) and ingests articles into your KB. You can also upload your own internal docs via the Console → KB Upload.

### 6. Test the agent

```bash
make test-agent
```

Or open the Streamlit Console at http://localhost:8501 → **Agent Runs** → paste a ticket message.

---

## API Reference

### Run the agent
```bash
curl -X POST http://localhost:8000/agent/run \
  -H "X-API-Key: dev-api-key-change-in-prod" \
  -H "Content-Type: application/json" \
  -d '{
    "ticket": {
      "id": "T-001",
      "channel": "chat",
      "customer_message": "I was charged twice for my order."
    },
    "kb_filters": { "product": "payments" },
    "agent_name": "support_ops"
  }'
```

### Response structure
```json
{
  "run_id": "uuid",
  "status": "success",
  "output": {
    "prospers_thoughts": "Internal SSA-only reasoning...",
    "ssa_guidance": ["Step 1...", "Step 2..."],
    "merchant_response": "Copy-paste ready message for merchant...",
    "citations": [{ "chunk_id": "...", "source_title": "...", "quote": "..." }],
    "risk": { "needs_approval": false, "flags": [] }
  },
  "chunks_used": 5,
  "latency_ms": 1842,
  "cost_usd": 0.0043
}
```

### Ingest a URL
```bash
curl -X POST http://localhost:8000/kb/sources \
  -H "X-API-Key: dev-api-key-change-in-prod" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Shopify Payments Guide",
    "source_type": "url",
    "url": "https://help.shopify.com/en/manual/payments",
    "product_area": "payments"
  }'
```

### Upload a file
```bash
curl -X POST http://localhost:8000/kb/upload \
  -H "X-API-Key: dev-api-key-change-in-prod" \
  -F "file=@my_policy.pdf" \
  -F "product_area=general"
```

---

## Project Structure

```
enterprise-rag-assistant/
├── apps/
│   ├── api/          # FastAPI backend + RAG pipeline
│   ├── worker/       # Celery background jobs
│   └── console/      # Streamlit admin UI
├── prompts/          # Agent prompt files (edit to tune the agent)
│   ├── support_ops/  # system.md · workflow.md · output_schema.json
│   └── policies/     # default.yml · pii_patterns.yml
├── evals/
│   └── datasets/     # JSONL test cases
├── packages/
│   ├── common/       # Shared types
│   └── sdk/          # Python client SDK
├── docker-compose.yml
├── .env.example
└── Makefile
```

---

## Tuning the Agent

The agent brain lives in `prompts/support_ops/`:

| File | Purpose |
|---|---|
| `system.md` | Core persona, tone, safety rules |
| `workflow.md` | Output format, section definitions |
| `output_schema.json` | Strict JSON contract |

**No code changes needed** — edit the markdown files and restart the API.

---

## Guardrail Policies

Create and manage policies via the Console or API. Each policy is a YAML rule:

```yaml
rules:
  - name: no_refund_promises
    phase: post          # pre | post | both
    match:
      - "I will refund"
      - "guaranteed refund"
    action: require_approval   # block | require_approval | redact | require_citations
```

---

## Eval Dataset Format

Each line in a `.jsonl` file:

```json
{
  "input": {
    "ticket": { "customer_message": "How do I process a refund?", "channel": "chat" }
  },
  "expected": {
    "must_contain": ["refund"],
    "must_not_contain": ["guarantee"],
    "has_citations": true,
    "needs_approval": false
  }
}
```

---

## Production Checklist

- [ ] Change `DEFAULT_ORG_API_KEY` to a strong random secret
- [ ] Set `APP_ENV=production` in `.env`
- [ ] Enable S3 storage: set `USE_LOCAL_STORAGE=false` and configure `S3_BUCKET_NAME`
- [ ] Add HTTPS reverse proxy (nginx/Caddy) in front of the API
- [ ] Set up Celery beat for scheduled GEO scans and eval runs
- [ ] Monitor cost per run via the Runs dashboard
- [ ] Review and customize `prompts/policies/default.yml` for your org's specific policies
