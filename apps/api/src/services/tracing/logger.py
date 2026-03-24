from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import AgentRun, PolicyEvent


class TraceLogger:
    def __init__(self, db: AsyncSession, org_id: str):
        self.db = db
        self.org_id = org_id

    async def create_run(self, agent_name, ticket_id, input_payload) -> AgentRun:
        run = AgentRun(org_id=self.org_id, agent_name=agent_name,
            ticket_id=ticket_id, input_payload=input_payload, status="pending")
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)
        return run

    async def update_retrieved_chunks(self, run_id, chunk_ids):
        run = await self.db.get(AgentRun, run_id)
        if run:
            run.retrieved_chunk_ids = chunk_ids
            await self.db.commit()

    async def log_policy_event(self, run_id, decision, stage):
        event = PolicyEvent(run_id=run_id, rule_name=decision.rule_name, stage=stage,
            action_taken=decision.action, details={"reason": decision.reason})
        self.db.add(event)
        await self.db.commit()

    async def finalize_run(self, run, status, output_payload, llm_result=None):
        run.status = status
        run.output_payload = output_payload
        if llm_result:
            run.prompt_tokens = llm_result.get("prompt_tokens", 0)
            run.completion_tokens = llm_result.get("completion_tokens", 0)
            run.cost_usd = llm_result.get("cost_usd", 0.0)
            run.latency_ms = llm_result.get("latency_ms", 0)
            run.model_used = llm_result.get("model", "")
        await self.db.commit()
