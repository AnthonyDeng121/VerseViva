from server.models.song import SongSentence, WordTiming
from server.pipelines.language_coach import _build_prompt
from server.services.language import (
    EvidenceStrength,
    LanguageObservation,
    ObservationResult,
    apply_language_observations,
    generate_language_candidates,
)


class FixedLexicon:
    pronunciations = {
        "we're": ["W", "IY", "R"],
        "old": ["OW", "L", "D"],
        "up": ["AH", "P"],
        "in": ["IH", "N"],
        "let": ["L", "EH", "T"],
        "you": ["Y", "UW"],
        "our": ["AW", "ER"],
        "innocence": ["IH", "N", "AH", "S", "AH", "N", "S"],
        "but": ["B", "AH", "T"],
    }

    def phonemes(self, word: str) -> list[str]:
        return self.pronunciations[word.lower()]


def make_sentence() -> SongSentence:
    return SongSentence(
        id="sentence_001",
        start_seconds=0,
        end_seconds=3,
        lyrics="We're old up in let you",
        words=[
            WordTiming(id="w1", text="We're", start_seconds=0, end_seconds=0.4),
            WordTiming(id="w2", text="old", start_seconds=0.4, end_seconds=0.8),
            WordTiming(id="w3", text="up", start_seconds=0.9, end_seconds=1.2),
            WordTiming(id="w4", text="in", start_seconds=1.2, end_seconds=1.5),
            WordTiming(id="w5", text="let", start_seconds=1.6, end_seconds=2.0),
            WordTiming(id="w6", text="you", start_seconds=2.0, end_seconds=2.5),
        ],
    )


def test_candidate_generation_checks_every_word_boundary_and_uses_phonemes() -> None:
    candidates = generate_language_candidates([make_sentence()], lexicon=FixedLexicon())

    assert len(candidates) == 5
    by_span = {candidate.target_span: candidate for candidate in candidates}
    assert by_span["We're old"].boundary_kind == "consonant_to_vowel"
    assert by_span["up in"].boundary_kind == "consonant_to_vowel"
    assert by_span["let you"].boundary_kind == "stop_to_glide"
    assert by_span["We're old"].left_segment == "R"

    rhotic_sentence = SongSentence(
        id="sentence_002",
        start_seconds=0,
        end_seconds=1,
        lyrics="our innocence",
        words=[
            WordTiming(id="r1", text="our", start_seconds=0, end_seconds=0.5),
            WordTiming(id="r2", text="innocence", start_seconds=0.5, end_seconds=1),
        ],
    )
    rhotic = generate_language_candidates(
        [rhotic_sentence], lexicon=FixedLexicon()
    )[0]
    assert rhotic.boundary_kind == "rhotic_to_vowel"


def test_candidates_never_cross_primary_and_parenthetical_secondary_lanes() -> None:
    sentence = SongSentence(
        id="sentence_lanes",
        start_seconds=0,
        end_seconds=1,
        lyrics="up (But)",
        words=[
            WordTiming(id="up", text="up", start_seconds=0, end_seconds=0.4),
            WordTiming(id="but", text="But", start_seconds=0.4, end_seconds=0.8),
        ],
    )

    candidates = generate_language_candidates([sentence], lexicon=FixedLexicon())

    assert candidates == []


def test_verified_observations_become_compact_marks_and_expandable_details() -> None:
    sentence = make_sentence()
    candidates = generate_language_candidates([sentence], lexicon=FixedLexicon())
    by_span = {candidate.target_span: candidate for candidate in candidates}
    observations = [
        LanguageObservation(
            candidate_id=by_span["We're old"].id,
            result=ObservationResult.linked_or_resegmented,
            evidence_strength=EvidenceStrength.strong,
            audible_evidence=["前词尾音直接进入后词元音起音。"],
            needs_human_review=False,
        ),
        LanguageObservation(
            candidate_id=by_span["let you"].id,
            result=ObservationResult.not_audibly_released,
            evidence_strength=EvidenceStrength.moderate,
            audible_evidence=["没有听到 t 的独立释放。"],
            needs_human_review=True,
        ),
    ]

    annotated = apply_language_observations(
        [sentence],
        candidates,
        observations,
        provider="gemini",
        model="fake-gemini",
    )[0]

    assert [hint.marks[0].symbol for hint in annotated.language_hints] == ["‿", "×"]
    assert annotated.language_hints[0].details[0].locale == "zh-CN"
    assert annotated.language_hints[0].source == "llm_suggestion"
    assert annotated.language_hints[1].evidence["needsHumanReview"] is True


def test_weak_or_no_change_observations_do_not_reach_the_lyric_ui() -> None:
    sentence = make_sentence()
    candidates = generate_language_candidates([sentence], lexicon=FixedLexicon())
    observations = [
        LanguageObservation(
            candidate_id=candidates[0].id,
            result=ObservationResult.linked_or_resegmented,
            evidence_strength=EvidenceStrength.weak,
            audible_evidence=["证据很弱。"],
            needs_human_review=True,
        ),
        LanguageObservation(
            candidate_id=candidates[1].id,
            result=ObservationResult.continuous_without_change,
            evidence_strength=EvidenceStrength.strong,
            audible_evidence=["只是自然连续。"],
            needs_human_review=False,
        ),
    ]

    annotated = apply_language_observations(
        [sentence],
        candidates,
        observations,
        provider="gemini",
        model="fake-gemini",
    )[0]

    assert annotated.language_hints == []


def test_prompt_requires_a_verdict_for_every_g2p_candidate() -> None:
    sentence = make_sentence()
    candidates = generate_language_candidates([sentence], lexicon=FixedLexicon())

    prompt = _build_prompt(sentence.lyrics, [sentence], candidates)

    assert "每个 ID 恰好返回一次" in prompt
    assert "linked_or_resegmented" in prompt
    assert all(candidate.id in prompt for candidate in candidates)
    assert "If you" in prompt
    assert "Let you" in prompt
    assert "三选一" in prompt
