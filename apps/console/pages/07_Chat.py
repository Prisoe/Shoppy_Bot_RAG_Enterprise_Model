import streamlit as st
import requests
import json

st.set_page_config(page_title="Prosper Chat", page_icon="💬", layout="wide")

API = st.session_state.get("api_base", "http://api:8000")
HEADERS = {"X-API-Key": st.session_state.get("api_key", "dev-api-key-change-in-prod")}

def api_post(path, payload):
    try:
        r = requests.post(f"{API}{path}", headers={**HEADERS, "Content-Type": "application/json"},
                         json=payload, timeout=60)
        return r.json(), r.status_code
    except Exception as e:
        return {"error": str(e)}, 500

# ── Session state ──────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "ticket_id" not in st.session_state:
    import uuid
    st.session_state.ticket_id = f"CHAT-{str(uuid.uuid4())[:8].upper()}"
if "total_cost" not in st.session_state:
    st.session_state.total_cost = 0.0
if "run_count" not in st.session_state:
    st.session_state.run_count = 0

# ── Header ─────────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns([3, 1, 1])
col1.title("💬 Prosper Support Agent")
col1.caption(f"Ticket: `{st.session_state.ticket_id}`")

product_area = col2.selectbox("Product Area", 
    ["general", "orders", "payments", "shipping", "products", "customers", "inventory", "analytics"],
    label_visibility="collapsed")
channel = col3.selectbox("Channel", ["chat", "email", "phone"], label_visibility="collapsed")

if col2.button("🔄 New Conversation"):
    import uuid
    st.session_state.messages = []
    st.session_state.ticket_id = f"CHAT-{str(uuid.uuid4())[:8].upper()}"
    st.session_state.total_cost = 0.0
    st.session_state.run_count = 0
    st.rerun()

st.divider()

# ── Chat display ───────────────────────────────────────────────────────────
chat_container = st.container()
with chat_container:
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            with st.chat_message("user", avatar="🧑‍💼"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("assistant", avatar="🤖"):
                output = msg.get("output", {})
                
                # Merchant response (main message)
                merchant_resp = output.get("merchant_response", msg["content"])
                st.markdown(merchant_resp)
                
                # Citations with links
                citations = output.get("citations", [])
                if citations:
                    st.markdown("---")
                    st.markdown("**📚 Sources:**")
                    for c in citations:
                        url = c.get("source_url", "")
                        title = c.get("source_title", "Shopify Help")
                        if url:
                            st.markdown(f"• [{title}]({url})")
                        else:
                            st.markdown(f"• {title}")
                
                # SSA Guidance in expander
                guidance = output.get("ssa_guidance", [])
                if guidance:
                    with st.expander("📋 SSA Guidance (internal)", expanded=False):
                        for step in guidance:
                            st.markdown(f"• {step}")
                        thoughts = output.get("prospers_thoughts", "")
                        if thoughts:
                            st.markdown("---")
                            st.markdown(f"*Prosper's thoughts: {thoughts}*")
                
                # Risk flags
                risk = output.get("risk", {})
                if risk.get("flags"):
                    meaningful_flags = [f for f in risk["flags"] if f not in ["require_citations"]]
                    if meaningful_flags:
                        st.warning(f"⚠️ {', '.join(meaningful_flags)}")
                
                # Metadata
                st.caption(f"💰 ${msg.get('cost', 0):.4f} · ⚡ {msg.get('latency_ms', 0)}ms · 📄 {msg.get('chunks_used', 0)} KB chunks")

# ── Chat input ─────────────────────────────────────────────────────────────
st.divider()
user_input = st.chat_input("Type your support question here... (e.g. 'How do I issue a refund?')")

if user_input:
    # Add user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Build conversation history for API
    history = []
    for msg in st.session_state.messages[:-1]:  # exclude current message
        if msg["role"] == "user":
            history.append({"role": "user", "content": msg["content"]})
        else:
            # Use merchant response as assistant turn in history
            assistant_content = msg.get("output", {}).get("merchant_response", msg.get("content", ""))
            history.append({"role": "assistant", "content": assistant_content})
    
    payload = {
        "ticket": {
            "id": st.session_state.ticket_id,
            "channel": channel,
            "customer_message": user_input,
        },
        "kb_filters": {"product": product_area},
        "agent_name": "support_ops",
        "conversation_history": history,
    }
    
    with st.spinner("Prosper is thinking..."):
        result, code = api_post("/agent/run", payload)
    
    if code == 200:
        output = result.get("output", {})
        cost = result.get("cost_usd", 0)
        st.session_state.total_cost += cost
        st.session_state.run_count += 1
        
        st.session_state.messages.append({
            "role": "assistant",
            "content": output.get("merchant_response", "I was unable to generate a response."),
            "output": output,
            "cost": cost,
            "latency_ms": result.get("latency_ms", 0),
            "chunks_used": result.get("chunks_used", 0),
            "run_id": result.get("run_id"),
        })
    else:
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"Error: {result.get('error', 'Unknown error')}",
            "output": {},
            "cost": 0,
            "latency_ms": 0,
            "chunks_used": 0,
        })
    
    st.rerun()

# ── Session stats ──────────────────────────────────────────────────────────
if st.session_state.run_count > 0:
    st.sidebar.divider()
    st.sidebar.markdown("### 📊 Session Stats")
    st.sidebar.metric("Messages", st.session_state.run_count)
    st.sidebar.metric("Total Cost", f"${st.session_state.total_cost:.4f}")
