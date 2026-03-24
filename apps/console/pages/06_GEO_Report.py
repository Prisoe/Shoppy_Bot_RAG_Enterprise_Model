import streamlit as st
import requests

st.set_page_config(page_title="GEO Report", page_icon="📊", layout="wide")
st.title("📊 GEO Report — KB Health")
st.markdown("*Generative Engine Optimization: how well can AI answer from your knowledge base?*")

API = st.session_state.get("api_base", "http://api:8000")
HEADERS = {"X-API-Key": st.session_state.get("api_key", "dev-api-key-change-in-prod")}


def api(method, path, **kwargs):
    try:
        r = getattr(requests, method)(f"{API}{path}", headers=HEADERS, timeout=30, **kwargs)
        return r.json(), r.status_code
    except Exception as e:
        return {"error": str(e)}, 500


col_scan, col_refresh, _ = st.columns([1, 1, 4])
if col_scan.button("🔍 Run GEO Scan", type="primary"):
    with st.spinner("Queuing GEO scan..."):
        result, code = api("post", "/geo/scan")
        if code == 200:
            st.success(f"✅ GEO scan queued. Refresh in a few seconds.")
        else:
            st.error(str(result))

if col_refresh.button("🔄 Refresh"):
    st.rerun()

report, code = api("get", "/geo/reports/latest")

if code != 200 or "message" in report:
    st.info("No GEO report yet. Click **Run GEO Scan** to analyze your KB.")
    st.stop()

# ── Score Header ───────────────────────────────────────────
score = report.get("answerability_score", 0)
score_color = "🟢" if score >= 80 else "🟡" if score >= 60 else "🔴"

c1, c2, c3, c4 = st.columns(4)
c1.metric("Answerability Score", f"{score_color} {score}%")
c2.metric("Contradictions", len(report.get("contradictions", [])))
c3.metric("Missing Questions", len(report.get("missing_questions", [])))
c4.metric("Outdated Pages", len(report.get("outdated_pages", [])))

st.caption(f"Report generated: {report.get('created_at', '')[:19]}")
st.progress(int(score) / 100)

# ── Recommendations ─────────────────────────────────────────
recs = report.get("recommendations", [])
if recs:
    st.subheader("💡 Recommendations")
    for rec in recs:
        st.info(f"• {rec}")

st.divider()
tab1, tab2, tab3 = st.tabs(["⚡ Contradictions", "❓ Missing Questions", "📅 Outdated Pages"])

with tab1:
    contradictions = report.get("contradictions", [])
    if contradictions:
        for c in contradictions:
            severity_icon = "🔴" if c.get("severity") == "high" else "🟡"
            with st.expander(f"{severity_icon} Topic: **{c['topic']}** — {c.get('severity', 'medium').upper()}"):
                col1, col2 = st.columns(2)
                col1.markdown("**Sources saying YES / allowed:**")
                for s in c.get("positive_sources", []):
                    col1.markdown(f"• {s}")
                col2.markdown("**Sources saying NO / not allowed:**")
                for s in c.get("negative_sources", []):
                    col2.markdown(f"• {s}")
                st.warning("Action: Review and consolidate these conflicting articles.")
    else:
        st.success("✅ No contradictions detected in your KB.")

with tab2:
    missing = report.get("missing_questions", [])
    if missing:
        high = [m for m in missing if m.get("priority") == "high"]
        medium = [m for m in missing if m.get("priority") == "medium"]

        if high:
            st.error(f"**{len(high)} High Priority** — these topics have very low coverage")
            for m in high:
                st.markdown(f"🔴 `{m['question']}` — coverage: {int(m['coverage_score']*100)}%")

        if medium:
            st.warning(f"**{len(medium)} Medium Priority**")
            for m in medium:
                st.markdown(f"🟡 `{m['question']}` — coverage: {int(m['coverage_score']*100)}%")

        st.info("Action: Create help center articles or FAQ entries for these questions.")
    else:
        st.success("✅ All common support questions are covered in your KB.")

with tab3:
    outdated = report.get("outdated_pages", [])
    if outdated:
        for o in outdated:
            with st.expander(f"📅 {o.get('source_title', 'Unknown')}"):
                st.markdown(f"**Reason:** {o.get('reason', '')}")
                st.markdown(f"**URL:** {o.get('source_url', 'N/A')}")
                st.markdown("**Snippet:**")
                st.text(o.get("snippet", "")[:300])
                st.warning("Action: Review and update or remove this article.")
    else:
        st.success("✅ No obviously outdated pages found.")

# ── Report History ──────────────────────────────────────────
st.divider()
st.subheader("📈 Report History")
history, _ = api("get", "/geo/reports")
if isinstance(history, list) and len(history) > 1:
    import pandas as pd
    df = pd.DataFrame([
        {
            "Date": r["created_at"][:19],
            "Score": r.get("answerability_score", 0),
            "Contradictions": r.get("contradictions_count", 0),
            "Missing Qs": r.get("missing_questions_count", 0),
            "Outdated": r.get("outdated_pages_count", 0),
        }
        for r in history
    ])
    st.dataframe(df, use_container_width=True)
    st.line_chart(df.set_index("Date")["Score"])
else:
    st.info("Run more GEO scans over time to see trends.")
