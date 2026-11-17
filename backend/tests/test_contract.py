"""The backend's copy of the contract must match what the AI service publishes.

ai_openapi.json is a snapshot of the AI service's schema. Regenerate it after
every change to the AI service's contract, from the repository root:

    cd ai-service
    uv run python -c "import json; from app.main import app; print(json.dumps(app.openapi(), indent=1, sort_keys=True))" > ../backend/tests/ai_openapi.json
"""

import json
from pathlib import Path

from pydantic.json_schema import models_json_schema

from app.ai_contract import PlanRequest, PlanResponse

PUBLISHED = json.loads((Path(__file__).parent / "ai_openapi.json").read_text())
THEIRS = PUBLISHED["components"]["schemas"]

# Our schemas, with references written the way OpenAPI writes them.
_, OUR_SCHEMA = models_json_schema(
    [(PlanRequest, "validation"), (PlanResponse, "serialization")],
    ref_template="#/components/schemas/{model}",
)
OURS = OUR_SCHEMA["$defs"]

SENT = ("PlanRequest", "Constraints", "WeeklyHours", "PlanTask", "TaskType")
READ = ("PlanResponse", "DayPlan", "Block", "TaskAssessment", "Assessment")


def fields(schema: dict) -> dict:
    """Field names, types and limits.

    Titles and descriptions do not matter, and neither do defaults: whether a
    field may be left out is checked through the "required" lists.
    """
    ignored = ("title", "description", "default")
    return {
        name: {k: v for k, v in rules.items() if k not in ignored}
        for name, rules in schema.get("properties", {}).items()
    }


def test_every_model_we_use_is_published():
    assert set(OURS) <= set(THEIRS)


def test_what_we_send_is_exactly_what_they_accept():
    for name in SENT:
        ours, theirs = OURS[name], THEIRS[name]
        if "enum" in ours:  # every value we may send must be accepted
            assert set(ours["enum"]) <= set(theirs["enum"]), name
            continue
        # They forbid unknown fields, so each field we send must exist, with the
        # same type and limits, and we must send every field they require.
        assert {key: fields(theirs).get(key) for key in fields(ours)} == fields(ours), (
            name
        )
        assert set(theirs.get("required", [])) <= set(fields(ours)), name


def test_what_we_read_is_what_they_answer():
    for name in (*READ, "FallbackReason"):
        ours, theirs = OURS[name], THEIRS[name]
        if "enum" in ours:  # every value they may answer must be known to us
            assert set(theirs["enum"]) <= set(ours["enum"]), name
            continue
        # Each field we read must exist on their side with the same type.
        # Extra fields on their side are fine: our models ignore them.
        assert {key: fields(theirs).get(key) for key in fields(ours)} == fields(ours), (
            name
        )
