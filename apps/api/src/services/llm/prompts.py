"""
Prompt loader — reads versioned prompt files from /prompts directory.
Injects KB context, ticket data, and policy constraints at runtime.
"""
import os
from pathlib import Path
from typing import List, Dict
from src.config import settings


def load_prompt(agent: str, file: str) -> str:
    """Load a prompt file: prompts/{agent}/{file}"""
    path = Path(settings.PROMPTS_DIR) / agent / file
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def build_support_ops_messages(
    ticket_text: str,
    kb_chunks: List[dict],
    policy_constraints: List[str] = None,
) -> List[Dict[str, str]]:
    """
    Compose the full message array for the support ops agent.
    """
    system_prompt = load_prompt("support_ops", "system.md")
    workflow_prompt = load_prompt("support_ops", "workflow.md")

    # Build KB context block
    kb_context = _format_kb_context(kb_chunks)

    # Build policy constraint block
    policy_block = ""
    if policy_constraints:
        policy_block = "\n\n**Active Policy Constraints:**\n" + "\n".join(
            f"- {c}" for c in policy_constraints
        )

    user_content = f"""
{workflow_prompt}

---
**Knowledge Base Context (cite these in your response):**
{kb_context}
{policy_block}

---
**Ticket / Query:**
{ticket_text}

---
Respond ONLY in valid JSON matching the output schema.
"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


def _format_kb_context(chunks: List[dict]) -> str:
    if not chunks:
        return "No relevant KB articles found."
    lines = []
    for i, chunk in enumerate(chunks, 1):
        lines.append(
            f"[{i}] Source: {chunk['source_title']} (score: {chunk['score']})\n"
            f"{chunk['text'][:500]}..."
        )
    return "\n\n".join(lines)
