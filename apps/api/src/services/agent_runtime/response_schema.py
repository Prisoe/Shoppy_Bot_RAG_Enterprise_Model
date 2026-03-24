"""
Validates and parses the LLM's JSON output.
Retries once with a format correction prompt if parsing fails.
"""
import json
import re
from src.services.llm.client import call_llm


def parse_agent_response(raw_text: str) -> dict:
    """Extract JSON from LLM output, with fallback."""
    # Try direct parse
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding first { ... } block
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Return structured error response
    return {
        "prospers_thoughts": "Unable to parse structured response.",
        "ssa_guidance": ["Please review the raw output and retry."],
        "merchant_response": raw_text,
        "citations": [],
        "risk": {"needs_approval": True, "flags": ["parse_error"]},
        "_parse_error": True,
    }


def validate_response(data: dict) -> tuple[bool, list[str]]:
    """Returns (is_valid, list_of_issues)."""
    required = ["prospers_thoughts", "ssa_guidance", "merchant_response", "citations", "risk"]
    issues = [f"Missing field: {k}" for k in required if k not in data]

    if "risk" in data:
        if "needs_approval" not in data["risk"]:
            issues.append("risk.needs_approval is required")

    if "citations" in data and not isinstance(data["citations"], list):
        issues.append("citations must be a list")

    return len(issues) == 0, issues


def fix_response_with_llm(system_prompt: str, bad_output: str) -> dict:
    """Ask the LLM to reformat a bad output."""
    fix_prompt = f"""The following response was not valid JSON. 
Please reformat it exactly according to the output schema and return only valid JSON.

Bad output:
{bad_output}

Return only the JSON object, no markdown, no explanation."""

    result = call_llm(system_prompt, fix_prompt, max_tokens=2048)
    return parse_agent_response(result["text"])
