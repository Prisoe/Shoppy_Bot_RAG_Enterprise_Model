import streamlit as st
import requests
import json

st.set_page_config(page_title="Agent Runs", page_icon="⚡", layout="wide")
st.title("⚡ Agent Runs")

API = st.session_state.get("api_base", "http://api:8000")
HEADERS = {"X-API-Key": st.session_state.get("api_key", "dev-api-key-change-in-prod")}


def api(method, path, **kwargs):
    try:
        r = getattr(requests, method)(f"{API}{path}", headers=HEADERS, timeout=60, **kwargs)
        return r.json(), r.status_code
    except Exception as e:
        return {"error": str(e)}, 500


# ── Live Test ───────────────────────────────────────────────
st.subheader("🧪 Test the Agent")
with st.expander("Run a test ticket", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        channel = st.selectbox("Channel", ["chat", "email", "phone"])
        product_area = st.selectbox("Product Area", ["general", "orders", "payments", "shipping", "products"])
    with col2:
        ticket_id = st.text_input("Ticket ID (optional)", value="TEST-001")

    message = st.text_area(
        "Customer Message",
        value="Hi, I was charged twice for my order #1234. Can you help me get a refund?",
        height=100,
    )

    if st.button("🚀 Run Agent", type="primary"):
        payload = {
            "ticket": {"id": ticket_id, "channel": channel, "customer_message": message},
            "kb_filters": {"product": product_area},
            "agent_name": "support_ops",
        }
        with st.spinner("Running agent pipeline..."):
            result, code = api("post", "/agent/run", json=payload)

        if code == 200:
            status = result.get("status", "unknown")
            status_color = {"success": "✅", "needs_approval": "⚠️", "blocked": "🚫", "error": "❌"}.get(status, "❓")
            st.success(f"{status_color} Status: **{status.upper()}** | Latency: {result.get('latency_ms')}ms | Cost: ${result.get('cost_usd', 0):.4f}")

            output = result.get("output", {})
            if output:
                t1, t2, t3 = st.tabs(["🧠 Prosper's Thoughts", "📋 SSA Guidance", "💬 Merchant Response"])
                with t1:
                    st.write(output.get("prospers_thoughts", "—"))
                with t2:
                    for step in output.get("ssa_guidance", []):
                        st.markdown(f"• {step}")
                with t3:
                    merchant_resp = output.get("merchant_response", "—")
                    st.text_area("Copy-paste ready response", value=merchant_resp, height=200)

                citations = output.get("citations", [])
                if citations:
                    st.subheader("📎 Citations")
                    for c in citations:
                        st.markdown(f"**{c.get('source_title')}** — _{c.get('quote', '')[:120]}_")

                risk = output.get("risk", {})
                if risk.get("needs_approval"):
                    st.warning(f"⚠️ Flagged for approval. Flags: {', '.join(risk.get('flags', []))}")
        else:
            st.error(f"Agent error: {result}")

# ── Run History ─────────────────────────────────────────────
st.divider()
st.subheader("📜 Recent Runs")

col1, col2 = st.columns([3, 1])
status_filter = col1.selectbox("Filter by status", ["all", "success", "needs_approval", "blocked", "approved", "rejected"])
if col2.button("🔄 Refresh"):
    st.rerun()

params = {} if status_filter == "all" else {"status": status_filter}
runs, _ = api("get", "/agent/runs", params=params)

if isinstance(runs, list) and runs:
    for run in runs:
        status = run.get("status", "unknown")
        icon = {"success": "✅", "needs_approval": "⚠️", "blocked": "🚫", "approved": "👍", "rejected": "👎", "error": "❌"}.get(status, "❓")
        label = f"{icon} {run['created_at'][:19]} | {status.upper()} | {run.get('latency_ms')}ms | ${run.get('cost_usd', 0):.4f}"

        with st.expander(label):
            output = run.get("output", {})
            if output:
                st.markdown(f"**Merchant Response:**\n\n{output.get('merchant_response', '—')}")
                if output.get("citations"):
                    st.markdown("**Citations:** " + " | ".join(c.get("source_title", "") for c in output["citations"]))
                risk = output.get("risk", {})
                if risk.get("flags"):
                    st.warning(f"Flags: {', '.join(risk['flags'])}")
            st.caption(f"Run ID: {run['run_id']} | Tokens: {run.get('input_tokens', 0)}in / {run.get('output_tokens', 0)}out")
else:
    st.info("No runs yet. Use the test panel above to run your first agent call.")
