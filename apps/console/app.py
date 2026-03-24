import streamlit as st
import os

st.set_page_config(
    page_title="RAG Assistant Console",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE = os.getenv("API_BASE_URL", "http://api:8000")
API_KEY = os.getenv("DEFAULT_ORG_API_KEY", "dev-api-key-change-in-prod")

st.session_state.setdefault("api_base", API_BASE)
st.session_state.setdefault("api_key", API_KEY)

st.sidebar.title("🤖 RAG Assistant")
st.sidebar.markdown("Enterprise Support Ops Platform")
st.sidebar.divider()

with st.sidebar.expander("⚙️ API Settings", expanded=False):
    st.session_state.api_base = st.text_input("API URL", value=st.session_state.api_base)
    st.session_state.api_key = st.text_input("API Key", value=st.session_state.api_key, type="password")

st.sidebar.divider()
st.sidebar.caption("Powered by AWS Bedrock · pgvector · FastAPI")

st.title("🤖 Enterprise RAG Assistant")
st.markdown("""
Welcome to the **AgentOps Console** — your control plane for the Shopify Support RAG system.

Use the sidebar pages to:
- **KB Upload** — ingest help center articles and documents
- **Agent Runs** — view and inspect all agent executions
- **Approvals** — review and approve flagged responses
- **Policies** — manage guardrail rules
- **Evals** — run regression test suites
- **GEO Report** — analyze knowledge base health
""")

col1, col2, col3 = st.columns(3)
try:
    import requests
    resp = requests.get(f"{st.session_state.api_base}/health", timeout=5)
    if resp.status_code == 200:
        data = resp.json()
        col1.metric("API Status", "✅ Online")
        col2.metric("Model", data.get("model", "—").split(".")[-1])
        col3.metric("Version", data.get("version", "—"))
    else:
        col1.metric("API Status", "❌ Error")
except Exception:
    col1.metric("API Status", "❌ Offline")
    st.warning("API is not reachable. Check your API URL and that the server is running.")
