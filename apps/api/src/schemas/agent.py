from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID


class OrderContext(BaseModel):
    order_id: Optional[str] = None
    order_status: Optional[str] = None
    total_price: Optional[str] = None
    currency: Optional[str] = None
    items: Optional[list] = []
    extra: Optional[dict] = {}


class TicketPayload(BaseModel):
    id: Optional[str] = Field(default=None)
    channel: Optional[str] = Field(default="chat")
    customer_message: str
    order_context: Optional[OrderContext] = None


class KBFilters(BaseModel):
    product: Optional[str] = None
    language: Optional[str] = "en"


class ConversationMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class AgentRunRequest(BaseModel):
    ticket: TicketPayload
    kb_filters: Optional[KBFilters] = KBFilters()
    agent_name: Optional[str] = "support_ops"
    conversation_history: Optional[list[ConversationMessage]] = []


class CitationOut(BaseModel):
    chunk_id: str
    source_title: str
    source_url: Optional[str] = ""
    quote: str


class RiskOut(BaseModel):
    needs_approval: bool
    flags: list[str] = []


class AgentOutputOut(BaseModel):
    prospers_thoughts: Optional[str] = None
    ssa_guidance: Optional[list[str]] = []
    merchant_response: Optional[str] = None
    citations: Optional[list[CitationOut]] = []
    risk: Optional[RiskOut] = None


class AgentRunResponse(BaseModel):
    run_id: str
    status: str
    output: Optional[AgentOutputOut] = None
    chunks_used: Optional[int] = 0
    latency_ms: Optional[int] = 0
    cost_usd: Optional[float] = 0.0
    tokens: Optional[dict] = {}
    reason: Optional[list[str]] = None
