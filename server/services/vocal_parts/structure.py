import re

from server.models.song import (
    SongSentence,
    VocalLane,
    VocalPart,
    VocalPartRole,
    VocalPartSource,
)

PARENTHETICAL = re.compile(r"\(([^()]+)\)")


def derive_structural_vocal_parts(sentences: list[SongSentence]) -> list[VocalPart]:
    """Create review-only lane candidates when lyrics contain parenthetical vocals."""

    secondary: list[VocalPart] = []
    for sentence_index, sentence in enumerate(sentences, start=1):
        for cue_index, match in enumerate(PARENTHETICAL.finditer(sentence.lyrics), start=1):
            cue = match.group(1).strip()
            if not cue:
                continue
            secondary.append(
                VocalPart(
                    id=f"part_secondary_{sentence_index:03d}_{cue_index:02d}",
                    lane=VocalLane.secondary,
                    role=VocalPartRole.response,
                    start_seconds=sentence.start_seconds,
                    end_seconds=sentence.end_seconds,
                    lyrics=cue,
                    sentence_ids=[sentence.id],
                    source=VocalPartSource.lyrics_structure_candidate,
                    confidence=0.55,
                    needs_human_review=True,
                    evidence={"parentheticalText": match.group(0)},
                )
            )
    if not secondary:
        return []

    primary = [
        VocalPart(
            id=f"part_primary_{index:03d}",
            lane=VocalLane.primary,
            role=VocalPartRole.lead,
            start_seconds=sentence.start_seconds,
            end_seconds=sentence.end_seconds,
            lyrics=PARENTHETICAL.sub("", sentence.lyrics).strip() or sentence.lyrics,
            sentence_ids=[sentence.id],
            source=VocalPartSource.acoustic_candidate,
            confidence=0.65,
            needs_human_review=True,
            evidence={"basis": "alignedLeadSentence"},
        )
        for index, sentence in enumerate(sentences, start=1)
    ]
    return [*primary, *secondary]
