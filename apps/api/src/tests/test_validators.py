"""Tests for output schema validators."""
import pytest
from src.services.policy.validators import validate_output_schema


VALID_OUTPUT = '''
{
  "prospers_thoughts": "Internal note here.",
  "ssa_guidance": "Step 1. Check the theme settings.",
  "draft_reply": "Hi there! Here is how to fix this...",
  "clarifying_questions": ["Which theme are you using?"],
  "internal_checklist": ["Check theme version", "Test in incognito"],
  "citations": [
    {"chunk_id": "abc123", "source_title": "Help Center", "quote": "Theme conflicts can..."}
  ],
  "risk": {"needs_approval": false, "flags": []}
}
'''

INVALID_OUTPUT = '''{"draft_reply": "Hi there!"}'''


def test_valid_output():
    is_valid, data, errors = validate_output_schema(VALID_OUTPUT)
    assert is_valid
    assert data["draft_reply"] == "Hi there! Here is how to fix this..."
    assert errors == []


def test_missing_fields():
    is_valid, data, errors = validate_output_schema(INVALID_OUTPUT)
    assert not is_valid
    assert any("ssa_guidance" in e for e in errors)


def test_strips_markdown_fences():
    fenced = '''```json
{"prospers_thoughts":"x","ssa_guidance":"y","draft_reply":"z","clarifying_questions":[],"internal_checklist":[],"citations":[],"risk":{"needs_approval":false,"flags":[]}}
```'''
    is_valid, data, errors = validate_output_schema(fenced)
    assert is_valid


def test_invalid_json():
    is_valid, data, errors = validate_output_schema("not json at all {{{")
    assert not is_valid
    assert any("Invalid JSON" in e for e in errors)
