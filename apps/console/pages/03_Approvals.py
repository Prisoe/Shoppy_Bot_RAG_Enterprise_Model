import streamlit as st
import requests

st.set_page_config(page_title="Approvals", page_icon="✅", layout="wide")
st.title("✅ Approvals Queue")

API = st.session_state.get("api_base", "http://api:8000")
HEADERS = {"X-API-Key": st.session_state.get("api_key", "dev-api-key-change-in-prod")}


def api(method, path, **kwargs):
    try:
        r = getattr(requests, method)(f"{API}{path}", headers=HEADERS, timeout=30, **kwargs)
        return r.json(), r.status_code
    except Exception as e:
        return {"error": str(e)}, 500


tab_pending, tab_history = st.tabs(["🟡 Pending", "📋 History"])

with tab_pending:
    if st.button("🔄 Refresh"):
        st.rerun()

    pending, _ = api("get", "/approvals/pending")
    if isinstance(pending, list) and pending:
        st.info(f"**{len(pending)} response(s) awaiting review**")
        for item in pending:
            output = item.get("output", {})
            merchant_resp = output.get("merchant_response", "—") if output else "—"
            risk = output.get("risk", {}) if output else {}

            with st.expander(f"⚠️ {item['created_at'][:19]} | Run: {item['run_id'][:8]}..."):
                st.markdown(f"**Risk Flags:** {', '.join(risk.get('flags', ['none']))}")

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Ticket:**")
                    ticket = item.get("input", {}).get("ticket", {})
                    st.write(ticket.get("customer_message", "N/A"))

                with col2:
                    st.markdown("**Proposed Merchant Response:**")
                    st.text_area("", value=merchant_resp, height=150, key=f"resp_{item['approval_id']}", disabled=True)

                if output and output.get("ssa_guidance"):
                    st.markdown("**SSA Guidance:**")
                    for step in output["ssa_guidance"]:
                        st.markdown(f"• {step}")

                st.divider()
                reviewer_id = st.text_input("Your name / ID", key=f"rev_{item['approval_id']}", value="reviewer")
                notes = st.text_area("Notes (optional)", key=f"notes_{item['approval_id']}", height=60)

                c1, c2, _ = st.columns([1, 1, 4])
                if c1.button("👍 Approve", key=f"app_{item['approval_id']}", type="primary"):
                    result, code = api("post", f"/approvals/{item['approval_id']}/decide",
                                       json={"decision": "approved", "reviewer_id": reviewer_id, "notes": notes})
                    if code == 200:
                        st.success("Approved ✅")
                        st.rerun()
                    else:
                        st.error(str(result))

                if c2.button("👎 Reject", key=f"rej_{item['approval_id']}"):
                    result, code = api("post", f"/approvals/{item['approval_id']}/decide",
                                       json={"decision": "rejected", "reviewer_id": reviewer_id, "notes": notes})
                    if code == 200:
                        st.warning("Rejected")
                        st.rerun()
                    else:
                        st.error(str(result))
    else:
        st.success("✅ No pending approvals — queue is clear!")

with tab_history:
    history, _ = api("get", "/approvals/history")
    if isinstance(history, list) and history:
        for item in history:
            icon = "👍" if item["decision"] == "approved" else "👎"
            label = f"{icon} {item.get('decided_at', '')[:19]} | {item['decision'].upper()} by {item.get('reviewer_id', '?')}"
            with st.expander(label):
                st.write(f"**Notes:** {item.get('notes', '—')}")
                st.caption(f"Run ID: {item['run_id']} | Approval ID: {item['approval_id']}")
    else:
        st.info("No approval history yet.")
