# API Usage Examples

> All requests require the `x-api-key` header.

---

## 1. Create an Organization and API Key

```bash
# Create org
curl -X POST "http://localhost:8000/auth/orgs?name=Acme+Support&slug=acme"
# Response: { "org_id": "uuid...", "name": "Acme Support" }

# Create API key
curl -X POST "http://localhost:8000/auth/api-keys?org_id=uuid...&label=production"
# Response: { "api_key": "sk-ao-...", "label": "production" }
```

---

## 2. Ingest Knowledge Base Content

```bash
# Add a help center URL
curl -X POST "http://localhost:8000/kb/sources/url" \
  -H "x-api-key: sk-ao-..." \
  -H "Content-Type: application/json" \
  -d '{"url": "https://help.shopify.com/en/manual/checkout-settings", "title": "Checkout Settings"}'

# Upload a Markdown file
curl -X POST "http://localhost:8000/kb/sources/upload" \
  -H "x-api-key: sk-ao-..." \
  -F "file=@./docs/refund-policy.md"

# Test semantic retrieval
curl -X POST "http://localhost:8000/kb/query?query=checkout+not+working&top_k=3" \
  -H "x-api-key: sk-ao-..."
```

---

## 3. Run the Support Ops Agent

```bash
curl -X POST "http://localhost:8000/agent/run" \
  -H "x-api-key: sk-ao-..." \
  -H "Content-Type: application/json" \
  -d '{
    "ticket": {
      "ticket_id": "T-4821",
      "customer_message": "My checkout button disappeared after I installed a new theme.",
      "channel": "email"
    },
    "kb_top_k": 5
  }'
```

**Success response:**
```json
{
  "status": "success",
  "run_id": "3f9c1a2b-...",
  "output": {
    "prospers_thoughts": "Theme-related checkout breakage. Check version and recent customizations.",
    "ssa_guidance": "1. Check Online Store > Themes\n2. Compare with backup version\n3. Test in incognito browser\n4. Check theme.liquid for conflicting scripts",
    "draft_reply": "Thanks for reaching out! Here are the steps to restore checkout...",
    "clarifying_questions": ["Which theme are you using?", "Was any app recently installed?"],
    "internal_checklist": ["Verify theme version", "Check app script injections"],
    "citations": [
      { "chunk_id": "abc123", "source_title": "Checkout Settings", "quote": "Theme conflicts can prevent checkout from rendering..." }
    ],
    "risk": { "needs_approval": false, "flags": [] }
  },
  "kb_sources_used": 3,
  "tokens": { "prompt": 1240, "completion": 380, "cost_usd": 0.000782 }
}
```

**Needs approval (refund topic flagged):**
```json
{
  "status": "needs_approval",
  "run_id": "7d2e9f1c-...",
  "policy_flags": ["No refund promises"]
}
```

---

## 4. Approval Queue

```bash
# List pending approvals
curl "http://localhost:8000/approvals/pending" -H "x-api-key: sk-ao-..."

# Approve
curl -X POST "http://localhost:8000/approvals/7d2e9f1c-.../decide" \
  -H "x-api-key: sk-ao-..." \
  -d '{"decision": "approved", "reviewer_id": "john@acme.com"}'

# Reject
curl -X POST "http://localhost:8000/approvals/7d2e9f1c-.../decide" \
  -H "x-api-key: sk-ao-..." \
  -d '{"decision": "rejected", "notes": "Refund not applicable here"}'
```

---

## 5. Custom Policy Rules

```bash
curl -X POST "http://localhost:8000/policies/" \
  -H "x-api-key: sk-ao-..." \
  -H "Content-Type: application/json" \
  -d '{
    "name": "No competitor mentions",
    "rule_yaml": "rules:\n  - name: No competitors\n    match: [\"woocommerce\", \"bigcommerce\"]\n    action: require_approval\n    prompt_hint: Do not reference competitor platforms."
  }'
```

---

## 6. GEO Report

```bash
curl "http://localhost:8000/geo/report" -H "x-api-key: sk-ao-..."
```

**Response:**
```json
{
  "generated_at": "2026-03-18T12:00:00",
  "summary": {
    "total_chunks": 847,
    "avg_answerability_score": 0.72,
    "contradiction_count": 4
  },
  "recommendations": [
    "Review 4 potential contradictions across KB sources.",
    "Add Q&A format structure to improve AI answerability."
  ]
}
```

---

## 7. Python SDK

```python
import asyncio
from packages.sdk.client import AgentOpsClient

async def main():
    client = AgentOpsClient(base_url="http://localhost:8000", api_key="sk-ao-...")

    # Run agent on a support ticket
    result = await client.run_agent(
        ticket_text="My checkout is broken after a theme update",
        ticket_id="T-4821",
    )
    print(result["status"])
    print(result["output"]["draft_reply"])

    # Ingest a KB source
    await client.add_kb_url("https://help.shopify.com/en/manual/payments")

    # Get GEO report
    report = await client.geo_report()
    print(report["summary"])

asyncio.run(main())
```
