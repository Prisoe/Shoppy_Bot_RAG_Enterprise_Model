import streamlit as st
import requests
import json
from datetime import datetime

st.set_page_config(page_title="Prosper — Shopify Support Agent", page_icon="💬", layout="wide")

# ── Custom CSS for beautiful UI ────────────────────────────────────────────
st.markdown("""
<style>
    /* Main chat area */
    .stApp { background: #0f0f0f; }
    
    /* Message bubbles */
    .user-bubble {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 12px 16px;
        border-radius: 18px 18px 4px 18px;
        margin: 8px 0;
        max-width: 75%;
        margin-left: auto;
        word-wrap: break-word;
        font-size: 14px;
        line-height: 1.5;
    }
    .assistant-bubble {
        background: #1e1e2e;
        border: 1px solid #2d2d3f;
        color: #e2e2e8;
        padding: 12px 16px;
        border-radius: 18px 18px 18px 4px;
        margin: 8px 0;
        max-width: 85%;
        font-size: 14px;
        line-height: 1.6;
    }
    .citation-pill {
        display: inline-block;
        background: #1a3a5c;
        color: #60a5fa;
        border: 1px solid #2563eb;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 12px;
        margin: 3px 2px;
        text-decoration: none;
    }
    .meta-bar {
        font-size: 11px;
        color: #6b7280;
        margin-top: 6px;
        display: flex;
        gap: 12px;
    }
    .flag-badge {
        background: #2d1b0e;
        border: 1px solid #92400e;
        color: #fbbf24;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 11px;
    }
    .success-badge {
        background: #052e16;
        border: 1px solid #166534;
        color: #86efac;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 11px;
    }
    /* Sidebar stats */
    .stat-card {
        background: #1e1e2e;
        border: 1px solid #2d2d3f;
        border-radius: 8px;
        padding: 10px 14px;
        margin: 6px 0;
    }
    /* History item */
    .history-item {
        background: #1e1e2e;
        border: 1px solid #2d2d3f;
        border-radius: 8px;
        padding: 8px 12px;
        margin: 4px 0;
        cursor: pointer;
        font-size: 13px;
        color: #9ca3af;
    }
    div[data-testid="stChatMessage"] { background: transparent !important; }
</style>
""", unsafe_allow_html=True)

API = st.session_state.get("api_base", "http://api:8000")
HEADERS = {"X-API-Key": st.session_state.get("api_key", "dev-api-key-change-in-prod")}

def api_post(path, payload):
    try:
        r = requests.post(f"{API}{path}", headers={**HEADERS, "Content-Type": "application/json"},
                         json=payload, timeout=60)
        return r.json(), r.status_code
    except Exception as e:
        return {"error": str(e)}, 500

def api_get(path):
    try:
        r = requests.get(f"{API}{path}", headers=HEADERS, timeout=10)
        return r.json(), r.status_code
    except Exception as e:
        return {"error": str(e)}, 500

# ── Session init ───────────────────────────────────────────────────────────
import uuid as _uuid
if "conversations" not in st.session_state:
    st.session_state.conversations = {}
if "active_conv_id" not in st.session_state:
    cid = str(_uuid.uuid4())[:8].upper()
    st.session_state.active_conv_id = cid
    st.session_state.conversations[cid] = {"messages": [], "cost": 0.0, "created": datetime.now().strftime("%H:%M")}
if "total_cost" not in st.session_state:
    st.session_state.total_cost = 0.0

def current_conv():
    cid = st.session_state.active_conv_id
    if cid not in st.session_state.conversations:
        st.session_state.conversations[cid] = {"messages": [], "cost": 0.0, "created": datetime.now().strftime("%H:%M")}
    return st.session_state.conversations[cid]

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🤖 Prosper")
    st.caption("Shopify Support Agent")
    st.divider()

    # New conversation
    if st.button("＋ New Conversation", use_container_width=True, type="primary"):
        cid = str(_uuid.uuid4())[:8].upper()
        st.session_state.active_conv_id = cid
        st.session_state.conversations[cid] = {"messages": [], "cost": 0.0, "created": datetime.now().strftime("%H:%M")}
        st.rerun()

    # Settings
    with st.expander("⚙️ Settings"):
        product_area = st.selectbox("Product Area",
            ["general", "orders", "payments", "shipping", "products",
             "customers", "inventory", "analytics", "billing", "marketing"])
        channel = st.selectbox("Channel", ["chat", "email", "phone"])

    st.divider()

    # Session stats
    conv = current_conv()
    msgs = conv["messages"]
    agent_msgs = [m for m in msgs if m["role"] == "assistant"]
    st.markdown("**📊 Session Stats**")
    col1, col2 = st.columns(2)
    col1.metric("Turns", len(agent_msgs))
    col2.metric("Cost", f"${conv['cost']:.4f}")
    if agent_msgs:
        avg_chunks = sum(m.get("chunks_used", 0) for m in agent_msgs) / len(agent_msgs)
        avg_latency = sum(m.get("latency_ms", 0) for m in agent_msgs) / len(agent_msgs)
        col1.metric("KB Hits", f"{avg_chunks:.1f} avg")
        col2.metric("Latency", f"{avg_latency:.0f}ms")

    st.divider()

    # Conversation history
    st.markdown("**💬 Conversations**")
    for cid, c in sorted(st.session_state.conversations.items(),
                          key=lambda x: x[1]["created"], reverse=True):
        msgs_preview = c["messages"]
        first_msg = next((m["content"][:35] + "..." for m in msgs_preview if m["role"] == "user"), "Empty")
        is_active = cid == st.session_state.active_conv_id
        label = f"{'▶ ' if is_active else ''}{c['created']} — {first_msg}"
        if st.button(label, key=f"conv_{cid}", use_container_width=True):
            st.session_state.active_conv_id = cid
            st.rerun()

# ── Main chat area ─────────────────────────────────────────────────────────
conv = current_conv()
ticket_id = f"CHAT-{st.session_state.active_conv_id}"

# Header
col1, col2 = st.columns([4, 1])
col1.markdown(f"## 💬 Prosper Support Agent")
col1.caption(f"Ticket `{ticket_id}` · {channel.upper()} · {product_area}")
with col2:
    if st.button("📋 View Runs"):
        runs, _ = api_get("/agent/runs?limit=5")
        if isinstance(runs, list):
            st.session_state.show_runs = runs

# Show recent runs if requested
if st.session_state.get("show_runs"):
    with st.expander("📋 Recent Agent Runs", expanded=True):
        for run in st.session_state.show_runs[:5]:
            status_icon = {"success": "✅", "needs_approval": "⚠️", "blocked": "🚫"}.get(run.get("status"), "❓")
            st.markdown(f"{status_icon} `{run['run_id'][:8]}` · {run.get('status','').upper()} · "
                       f"${run.get('cost_usd',0):.4f} · {run.get('latency_ms',0)}ms")
        if st.button("Close"):
            st.session_state.show_runs = None
            st.rerun()

st.divider()

# ── Chat messages ──────────────────────────────────────────────────────────
for msg in conv["messages"]:
    if msg["role"] == "user":
        with st.chat_message("user", avatar="🧑‍💼"):
            st.markdown(msg["content"])
    else:
        with st.chat_message("assistant", avatar="🤖"):
            output = msg.get("output", {})
            merchant_resp = output.get("merchant_response", msg["content"])
            st.markdown(merchant_resp)

            # Citations
            citations = output.get("citations", [])
            if citations:
                st.markdown("**📚 Sources:**")
                for c in citations:
                    url = c.get("source_url", "")
                    title = c.get("source_title", "Shopify Help")
                    if url:
                        st.markdown(f"• [{title}]({url})")
                    else:
                        st.markdown(f"• {title}")

            # Guidance expander
            guidance = output.get("ssa_guidance", [])
            thoughts = output.get("prospers_thoughts", "")
            if guidance:
                with st.expander("📋 SSA Guidance", expanded=False):
                    for i, step in enumerate(guidance, 1):
                        st.markdown(f"{i}. {step}")
                    if thoughts:
                        st.divider()
                        st.caption(f"💭 {thoughts}")

            # Status row
            risk = output.get("risk", {})
            flags = [f for f in risk.get("flags", []) if f not in ["require_citations"]]
            col1, col2, col3 = st.columns([2, 2, 3])
            col1.caption(f"💰 ${msg.get('cost', 0):.5f}")
            col2.caption(f"⚡ {msg.get('latency_ms', 0)}ms")
            col3.caption(f"📄 {msg.get('chunks_used', 0)} KB chunks")
            if flags:
                st.warning(f"⚠️ {', '.join(flags)}", icon="⚠️")

# ── Input ──────────────────────────────────────────────────────────────────
user_input = st.chat_input("Ask Prosper anything about Shopify...")

if user_input:
    conv["messages"].append({"role": "user", "content": user_input})

    # Build history
    history = []
    for m in conv["messages"][:-1]:
        if m["role"] == "user":
            history.append({"role": "user", "content": m["content"]})
        else:
            assistant_text = m.get("output", {}).get("merchant_response", m.get("content", ""))
            history.append({"role": "assistant", "content": assistant_text})

    payload = {
        "ticket": {"id": ticket_id, "channel": channel, "customer_message": user_input},
        "kb_filters": {"product": product_area},
        "agent_name": "support_ops",
        "conversation_history": history,
    }

    with st.spinner("Prosper is thinking..."):
        result, code = api_post("/agent/run", payload)

    if code == 200:
        output = result.get("output", {})
        cost = result.get("cost_usd", 0)
        conv["cost"] = conv.get("cost", 0) + cost
        conv["messages"].append({
            "role": "assistant",
            "content": output.get("merchant_response", "Unable to generate response."),
            "output": output,
            "cost": cost,
            "latency_ms": result.get("latency_ms", 0),
            "chunks_used": result.get("chunks_used", 0),
            "run_id": result.get("run_id"),
        })
    else:
        conv["messages"].append({
            "role": "assistant",
            "content": f"⚠️ Error: {result.get('error', 'Unknown error')}",
            "output": {}, "cost": 0, "latency_ms": 0, "chunks_used": 0,
        })

    st.rerun()
