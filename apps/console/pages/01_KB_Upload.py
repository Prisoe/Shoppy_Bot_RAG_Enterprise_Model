import streamlit as st
import requests
import json

st.set_page_config(page_title="KB Upload", page_icon="📚", layout="wide")
st.title("📚 Knowledge Base")

API = st.session_state.get("api_base", "http://api:8000")
HEADERS = {"X-API-Key": st.session_state.get("api_key", "dev-api-key-change-in-prod")}


def api(method, path, **kwargs):
    try:
        r = getattr(requests, method)(f"{API}{path}", headers=HEADERS, timeout=30, **kwargs)
        return r.json(), r.status_code
    except Exception as e:
        return {"error": str(e)}, 500


tab1, tab2, tab3, tab4 = st.tabs(["📊 Stats", "🔗 Add URL", "📁 Upload File", "🛍️ Shopify Scrape"])

# ── Stats ──────────────────────────────────────────────────
with tab1:
    if st.button("🔄 Refresh Stats"):
        st.rerun()
    stats, _ = api("get", "/kb/stats")
    if "error" not in stats:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Sources", stats.get("total_sources", 0))
        c2.metric("Ready Sources", stats.get("ready_sources", 0))
        c3.metric("Total Chunks", stats.get("total_chunks", 0))
        c4.metric("Embedded Chunks", stats.get("embedded_chunks", 0))
    else:
        st.error(f"Could not load stats: {stats['error']}")

    st.divider()
    st.subheader("All Sources")
    sources, _ = api("get", "/kb/sources")
    if isinstance(sources, list) and sources:
        for s in sources:
            status_icon = {"ready": "✅", "processing": "⏳", "failed": "❌", "pending": "🕐"}.get(s["status"], "❓")
            with st.expander(f"{status_icon} {s['title']} — {s['source_type']}"):
                col1, col2 = st.columns([3, 1])
                col1.write(f"**URL:** {s.get('url', 'N/A')}")
                col1.write(f"**Product Area:** {s.get('product_area', 'general')}")
                col1.write(f"**Language:** {s.get('language', 'en')}")
                col1.write(f"**Created:** {s['created_at'][:19]}")
                if s.get("error_message"):
                    col1.error(f"Error: {s['error_message']}")
                if col2.button("🗑️ Delete", key=f"del_{s['id']}"):
                    result, code = api("delete", f"/kb/sources/{s['id']}")
                    if code == 200:
                        st.success("Deleted")
                        st.rerun()
                    else:
                        st.error(str(result))
    else:
        st.info("No KB sources yet. Add a URL or upload a file to get started.")

# ── Add URL ────────────────────────────────────────────────
with tab2:
    st.subheader("Add URL Source")
    with st.form("add_url"):
        title = st.text_input("Title", placeholder="Shopify Shipping Guide")
        url = st.text_input("URL", placeholder="https://help.shopify.com/en/manual/shipping")
        product_area = st.selectbox("Product Area", ["general", "orders", "payments", "shipping",
                                                       "products", "customers", "apps", "analytics",
                                                       "inventory", "themes", "marketing"])
        submitted = st.form_submit_button("➕ Add & Ingest")
        if submitted:
            if not url or not title:
                st.error("Title and URL are required")
            else:
                payload = {"title": title, "source_type": "url", "url": url, "product_area": product_area}
                result, code = api("post", "/kb/sources", json=payload)
                if code in (200, 201):
                    st.success(f"✅ Source queued for ingestion: {title}")
                else:
                    st.error(f"Error: {result}")

# ── Upload File ────────────────────────────────────────────
with tab3:
    st.subheader("Upload Document")
    uploaded = st.file_uploader("Upload PDF, TXT, MD or HTML", type=["pdf", "txt", "md", "html"])
    product_area_f = st.selectbox("Product Area", ["general", "orders", "payments", "shipping",
                                                     "products", "customers", "apps"], key="pa_file")
    if uploaded and st.button("⬆️ Upload & Ingest"):
        with st.spinner("Uploading..."):
            files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type)}
            try:
                r = requests.post(
                    f"{API}/kb/upload",
                    headers=HEADERS,
                    files=files,
                    params={"product_area": product_area_f},
                    timeout=60,
                )
                if r.status_code in (200, 201):
                    st.success(f"✅ {uploaded.name} queued for ingestion")
                else:
                    st.error(f"Error: {r.text}")
            except Exception as e:
                st.error(str(e))

# ── Shopify Scrape ─────────────────────────────────────────
with tab4:
    st.subheader("🛍️ Shopify Help Center Scraper")
    st.info("This will automatically crawl help.shopify.com and ingest articles into your KB.")
    max_pages = st.slider("Max pages to scrape", 10, 500, 100, step=10)
    sections = st.multiselect(
        "Sections",
        ["/en/manual", "/en/partners", "/en/api"],
        default=["/en/manual"],
    )
    if st.button("🚀 Start Shopify Scrape"):
        with st.spinner("Queuing scrape job..."):
            result, code = api("post", "/kb/scrape-shopify", json={"max_pages": max_pages, "sections": sections})
            if code == 200:
                st.success(f"✅ Scrape queued: {result.get('task_id', '')}")
            else:
                st.error(str(result))

# ── KB Search Tester ──────────────────────────────────────
st.divider()
st.subheader("🔍 Test KB Search")
query = st.text_input("Search query", placeholder="How do I process a refund?")
if st.button("Search") and query:
    results, _ = api("post", "/kb/query", json={"query": query, "top_k": 5})
    if isinstance(results, list):
        for r in results:
            with st.expander(f"[{r['score']:.3f}] {r['metadata'].get('source_title', 'Unknown')}"):
                st.write(r["text"])
                st.caption(f"Source: {r['metadata'].get('source_url', 'N/A')}")
    else:
        st.error(str(results))
