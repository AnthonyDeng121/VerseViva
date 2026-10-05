import pytest
from pydantic import ValidationError

from server.services.vocal_parts.gemini import _gemini_schema
from server.services.vocal_parts.models import VocalPartCandidate, VocalPartCandidateBatch


def test_vocal_part_candidate_batch_uses_camel_case_contract() -> None:
    batch = VocalPartCandidateBatch(
        audio_duration_seconds=36.34,
        candidates=[
            VocalPartCandidate(
                id="secondary_01",
                lane="secondary",
                role="response",
                start_seconds=0.8,
                end_seconds=2.4,
                lyrics="I want to get him back",
                confidence=0.81,
                audible_evidence=["A quieter response overlaps the lead."],
                matched_cue_ids=["secondary_short"],
                needs_human_review=True,
            )
        ],
    )

    payload = batch.model_dump(mode="json", by_alias=True)

    assert payload["audioDurationSeconds"] == 36.34
    assert payload["candidates"][0]["startSeconds"] == 0.8
    assert payload["candidates"][0]["matchedCueIds"] == ["secondary_short"]


def test_vocal_part_candidate_rejects_invalid_ranges_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        VocalPartCandidate(
            id="bad",
            lane="secondary",
            role="response",
            start_seconds=2,
            end_seconds=1,
            lyrics="response",
            confidence=0.5,
            needs_human_review=True,
        )

    with pytest.raises(ValidationError):
        VocalPartCandidateBatch.model_validate(
            {"audioDurationSeconds": 2, "candidates": [], "invented": True}
        )

    with pytest.raises(ValidationError):
        VocalPartCandidateBatch(audio_duration_seconds=0)


def test_gemini_schema_omits_unsupported_additional_properties() -> None:
    schema = _gemini_schema(VocalPartCandidateBatch.model_json_schema())

    assert "additionalProperties" not in schema
    assert "title" not in schema
    assert "additionalProperties" not in str(schema)
