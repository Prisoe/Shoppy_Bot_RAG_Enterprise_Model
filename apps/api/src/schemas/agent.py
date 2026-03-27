from pydantic import BaseModel, Field
from typing import Optional


class TicketPayload(BaseModel):
    id: Optional[str] = None
    channel: Optional[str] = "chat"
    customer_message: str
    order_context: Optional[dict] = None


class KBFilters(BaseModel):
    product: Optional[str] = None
    language: Optional[str] = "en"


class ConversationMessage(BaseModel):
    role: str
    content: str


class ImagePayload(BaseModel):
    base64: str
    media_type: str = "image/png"


class LLMOverrides(BaseModel):
    temperature: Optional[float] = None   # 0.0–1.0
    max_tokens:  Optional[int]   = None   # 256–4096
    top_k:       Optional[int]   = None   # 1–500
    top_p:       Optional[float] = None   # 0.0–1.0


class AgentRunRequest(BaseModel):
    ticket: TicketPayload
    kb_filters: Optional[KBFilters] = KBFilters()
    agent_name: Optional[str] = "support_ops"
    conversation_history: Optional[list[ConversationMessage]] = []
    image_data: Optional[list[ImagePayload]] = None
    llm_overrides: Optional[LLMOverrides] = None


class CitationOut(BaseModel):
    chunk_id: str
    source_title: str
    source_url: Optional[str] = ""
    quote: str
    confidence_score: Optional[float] = None


class RiskOut(BaseModel):
    needs_approval: bool
    flags: list[str] = []


class AgentOutputOut(BaseModel):
    shoppy_thoughts: Optional[str] = None
    probing_questions: Optional[list[str]] = []
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
