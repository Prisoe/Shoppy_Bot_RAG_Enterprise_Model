"""Tests for the policy engine."""
import pytest
from src.services.policy.engine import PolicyEngine


SAMPLE_POLICY = """
rules:
  - name: No refund promises
    match: ["i will refund", "refund is guaranteed"]
    action: require_approval
    reason: Refund commitments need review

  - name: Block sensitive data
    match: ["credit card number", "password"]
    action: block
    reason: Never request credentials

  - name: Require citations
    action: require_citations
    prompt_hint: Cite all KB sources.
"""


def test_input_block():
    engine = PolicyEngine(SAMPLE_POLICY)
    decisions = engine.evaluate_input("Please provide your credit card number")
    assert any(d.action == "block" for d in decisions)


def test_input_approval():
    engine = PolicyEngine(SAMPLE_POLICY)
    decisions = engine.evaluate_input("I will refund your order right away")
    assert any(d.action == "require_approval" for d in decisions)


def test_input_clean():
    engine = PolicyEngine(SAMPLE_POLICY)
    decisions = engine.evaluate_input("How do I update my shipping address?")
    assert not engine.has_blocking_decision(decisions)
    assert not engine.needs_approval(decisions)


def test_output_missing_citations():
    engine = PolicyEngine(SAMPLE_POLICY)
    decisions = engine.evaluate_output("Here is the information you need.", citations=[])
    assert engine.needs_approval(decisions)


def test_output_with_citations():
    engine = PolicyEngine(SAMPLE_POLICY)
    decisions = engine.evaluate_output("Here is the answer [Source: Help Center].",
        citations=[{"chunk_id": "abc", "source_title": "Help Center", "quote": "..."}])
    blocking = [d for d in decisions if d.action in ("block", "require_approval")]
    assert len(blocking) == 0


def test_policy_constraints_text():
    engine = PolicyEngine(SAMPLE_POLICY)
    constraints = engine.get_policy_constraints_text()
    assert isinstance(constraints, list)
    assert any("Cite" in c for c in constraints)
