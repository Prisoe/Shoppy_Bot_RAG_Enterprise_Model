"""
Simple Python SDK client for the RAG Assistant API.
Use this to integrate with Zendesk, Gorgias, or any other ticketing system.

Usage:
    from packages.sdk.client import RAGClient

    client = RAGClient(base_url="http://localhost:8000", api_key="your-key")
    result = client.run_agent(
        customer_message="How do I process a refund?",
        channel="chat",
        product_area="orders"
    )
    print(result["output"]["merchant_response"])
"""
import requests
from typing import Optional


class RAGClient:
    def __init__(self, base_url: str, api_key: str, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    def health(self) -> dict:
        return self._get("/health")

    def run_agent(
        self,
        customer_message: str,
        channel: str = "chat",
        ticket_id: Optional[str] = None,
        product_area: Optional[str] = None,
        order_context: Optional[dict] = None,
        agent_name: str = "support_ops",
    ) -> dict:
        payload = {
            "ticket": {
                "id": ticket_id or "SDK-RUN",
                "channel": channel,
                "customer_message": customer_message,
                "order_context": order_context or {},
            },
            "kb_filters": {"product": product_area} if product_area else {},
            "agent_name": agent_name,
        }
        return self._post("/agent/run", payload)

    def query_kb(self, query: str, top_k: int = 8, product_area: Optional[str] = None) -> list:
        return self._post("/kb/query", {"query": query, "top_k": top_k, "product_area": product_area})

    def list_pending_approvals(self) -> list:
        return self._get("/approvals/pending")

    def approve(self, approval_id: str, reviewer_id: str, notes: str = "") -> dict:
        return self._post(f"/approvals/{approval_id}/decide",
                          {"decision": "approved", "reviewer_id": reviewer_id, "notes": notes})

    def reject(self, approval_id: str, reviewer_id: str, notes: str = "") -> dict:
        return self._post(f"/approvals/{approval_id}/decide",
                          {"decision": "rejected", "reviewer_id": reviewer_id, "notes": notes})

    def trigger_geo_scan(self) -> dict:
        return self._post("/geo/scan", {})

    def get_latest_geo_report(self) -> dict:
        return self._get("/geo/reports/latest")

    def _get(self, path: str) -> dict:
        r = requests.get(f"{self.base_url}{path}", headers=self.headers, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, data: dict) -> dict:
        r = requests.post(f"{self.base_url}{path}", headers=self.headers, json=data, timeout=self.timeout)
        r.raise_for_status()
        return r.json()
