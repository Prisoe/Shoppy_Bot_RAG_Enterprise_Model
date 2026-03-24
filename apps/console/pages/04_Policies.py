import streamlit as st
import requests

st.set_page_config(page_title="Policies", page_icon="🛡️", layout="wide")
st.title("🛡️ Guardrail Policies")

API = st.session_state.get("api_base", "http://api:8000")
HEADERS = {"X-API-Key": st.session_state.get("api_key", "dev-api-key-change-in-prod")}

DEFAULT_POLICY_YAML = """rules:
  - name: no_refund_promises
    phase: post
    match:
      - "I will refund"
      - "guaranteed refund"
      - "full refund immediately"
      - "refund right now"
    action: require_approval

  - name: block_pii_requests
    phase: both
    match:
      - "credit card number"
      - "give me your password"
      - "SIN number"
      - "social insurance"
      - "social security"
    action: block

  - name: no_guarantee_language
    phase: post
    match:
      - "I guarantee"
      - "100% guaranteed"
      - "we promise"
    action: require_approval

  - name: require_citations
    action: require_citations
"""


def api(method, path, **kwargs):
    try:
        r = getattr(requests, method)(f"{API}{path}", headers=HEADERS, timeout=30, **kwargs)
        return r.json(), r.status_code
    except Exception as e:
        return {"error": str(e)}, 500


tab_list, tab_create = st.tabs(["📋 Active Policies", "➕ Create Policy"])

with tab_list:
    if st.button("🔄 Refresh"):
        st.rerun()

    policies, _ = api("get", "/policies/")
    if isinstance(policies, list) and policies:
        for p in policies:
            enabled_icon = "✅" if p["is_enabled"] else "⏸️"
            with st.expander(f"{enabled_icon} **{p['name']}** — {p['created_at'][:10]}"):
                if p.get("description"):
                    st.caption(p["description"])

                st.code(p["rule_yaml"], language="yaml")

                col1, col2, col3 = st.columns([1, 1, 4])
                toggle_label = "⏸️ Disable" if p["is_enabled"] else "▶️ Enable"
                if col1.button(toggle_label, key=f"tog_{p['id']}"):
                    result, code = api("patch", f"/policies/{p['id']}", json={"is_enabled": not p["is_enabled"]})
                    if code == 200:
                        st.rerun()

                if col2.button("🗑️ Delete", key=f"del_{p['id']}"):
                    result, code = api("delete", f"/policies/{p['id']}")
                    if code == 200:
                        st.success("Deleted")
                        st.rerun()
    else:
        st.info("No policies yet. Create one below.")
        st.info("💡 Tip: Use the default policy template to get started with sensible Shopify support guardrails.")

with tab_create:
    st.subheader("Create New Policy")
    with st.form("create_policy"):
        name = st.text_input("Policy Name", placeholder="no_refund_promises")
        description = st.text_input("Description (optional)", placeholder="Prevents agents from making refund promises")
        rule_yaml = st.text_area("Policy YAML", value=DEFAULT_POLICY_YAML, height=350)
        is_enabled = st.checkbox("Enable immediately", value=True)

        if st.form_submit_button("💾 Save Policy", type="primary"):
            if not name or not rule_yaml:
                st.error("Name and YAML are required")
            else:
                result, code = api("post", "/policies/", json={
                    "name": name,
                    "description": description,
                    "rule_yaml": rule_yaml,
                    "is_enabled": is_enabled,
                })
                if code in (200, 201):
                    st.success(f"✅ Policy '{name}' created")
                    st.rerun()
                else:
                    st.error(f"Error: {result}")

    with st.expander("📖 YAML Policy Format Reference"):
        st.markdown("""
**Actions available:**
- `block` — hard block, returns error immediately
- `require_approval` — queues for human review
- `redact` — remove matched content
- `require_citations` — flag if no KB citations in response

**Phase:**
- `pre` — evaluated on input (ticket)
- `post` — evaluated on output (response)
- `both` — evaluated on both

**Example rule:**
```yaml
rules:
  - name: my_rule
    phase: post
    match:
      - "term to match"
      - "another term"
    action: require_approval
```
        """)
