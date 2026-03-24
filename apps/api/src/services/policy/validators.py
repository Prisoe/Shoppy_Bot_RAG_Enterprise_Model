"""
Structural validators for agent output (independent of keyword rules).
"""
import json
from typing import Tuple, List


REQUIRED_OUTPUT_FIELDS = ["draft_reply", "clarifying_questions", "internal_checklist", "citations", "risk"]


def validate_output_schema(raw_output: str) -> Tuple[bool, dict, List[str]]:
    """
    Parse and validate the agent's JSON output.
    Returns (is_valid, parsed_dict, list_of_errors)
    """
    errors = []
    
    # Strip markdown code fences if present
    cleaned = raw_output.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[1:])
        cleaned = cleaned.rstrip("`").strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        return False, {}, [f"Invalid JSON: {e}"]

    for field in REQUIRED_OUTPUT_FIELDS:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if "risk" in data:
        risk = data["risk"]
        if not isinstance(risk.get("needs_approval"), bool):
            errors.append("risk.needs_approval must be boolean")
        if not isinstance(risk.get("flags"), list):
            errors.append("risk.flags must be a list")

    return len(errors) == 0, data, errors
