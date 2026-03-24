"""
YAML-based policy engine.
Evaluates rules against text and returns allow/block/require_approval/require_citations.
"""
import re
import yaml
from dataclasses import dataclass
from src.db.models import PolicyAction


@dataclass
class PolicyDecision:
    action: PolicyAction
    rule_name: str
    detail: dict


def load_rules_from_yaml(yaml_str: str) -> list[dict]:
    data = yaml.safe_load(yaml_str)
    return data.get("rules", [])


def evaluate_pre(text: str, rules: list[dict]) -> list[PolicyDecision]:
    """Evaluate rules before LLM call (on user input)."""
    return _evaluate(text, rules, phase="pre")


def evaluate_post(text: str, rules: list[dict], has_citations: bool = False) -> list[PolicyDecision]:
    """Evaluate rules after LLM call (on output)."""
    decisions = _evaluate(text, rules, phase="post")

    # Check citation requirement
    for rule in rules:
        if rule.get("action") == "require_citations" and not has_citations:
            decisions.append(PolicyDecision(
                action=PolicyAction.require_approval,
                rule_name=rule.get("name", "require_citations"),
                detail={"reason": "Response must include citations"},
            ))

    return decisions


def _evaluate(text: str, rules: list[dict], phase: str) -> list[PolicyDecision]:
    decisions = []
    lower_text = text.lower()

    for rule in rules:
        rule_phase = rule.get("phase", "post")
        if rule_phase != phase and rule_phase != "both":
            continue

        matches = rule.get("match", [])
        action_str = rule.get("action", "allow")
        action = _parse_action(action_str)

        if action == PolicyAction.require_citations:
            continue  # handled separately in evaluate_post

        matched_terms = []
        for term in matches:
            if re.search(re.escape(term.lower()), lower_text):
                matched_terms.append(term)

        if matched_terms:
            decisions.append(PolicyDecision(
                action=action,
                rule_name=rule.get("name", "unnamed"),
                detail={"matched_terms": matched_terms, "rule": rule},
            ))

    return decisions


def _parse_action(action_str: str) -> PolicyAction:
    mapping = {
        "allow": PolicyAction.allow,
        "block": PolicyAction.block,
        "require_approval": PolicyAction.require_approval,
        "redact": PolicyAction.redact,
        "require_citations": PolicyAction.require_citations,
    }
    return mapping.get(action_str, PolicyAction.allow)


def most_severe_action(decisions: list[PolicyDecision]) -> PolicyAction | None:
    """Return the most severe action from a list of decisions."""
    severity = [
        PolicyAction.block,
        PolicyAction.require_approval,
        PolicyAction.redact,
        PolicyAction.require_citations,
        PolicyAction.allow,
    ]
    for action in severity:
        if any(d.action == action for d in decisions):
            return action
    return None
