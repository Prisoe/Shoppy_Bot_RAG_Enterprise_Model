"""
Loads versioned prompt files from /app/prompts directory.
"""
import os
from src.config import get_settings

settings = get_settings()


def load_prompt(agent_name: str, filename: str) -> str:
    path = os.path.join(settings.prompts_dir, agent_name, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Prompt file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def build_system_prompt(agent_name: str, policy_rules_text: str = "") -> str:
    """
    Combines system.md + workflow.md + policy rules into one system prompt.
    """
    parts = []

    try:
        parts.append(load_prompt(agent_name, "system.md"))
    except FileNotFoundError:
        pass

    try:
        parts.append(load_prompt(agent_name, "workflow.md"))
    except FileNotFoundError:
        pass

    if policy_rules_text:
        parts.append(f"\n---\n**Active Policy Rules (enforce strictly):**\n{policy_rules_text}")

    return "\n\n---\n\n".join(parts)


def load_output_schema(agent_name: str) -> dict:
    import json
    path = os.path.join(settings.prompts_dir, agent_name, "output_schema.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}
