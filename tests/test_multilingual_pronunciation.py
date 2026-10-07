from server.models.song import SongSentence, WordTiming
from server.pipelines.song_analysis import _detect_lyrics_language
from server.services.language import add_pronunciation_guides, generate_language_candidates
from server.services.language.pronunciation import romanize_japanese, romanize_korean
from server.services.lyrics.lrclib import _normalize


def _words(values: list[str]) -> list[WordTiming]:
    return [
        WordTiming(
            id=f"word_{index}",
            text=value,
            start_seconds=index * 0.5,
            end_seconds=(index + 1) * 0.5,
        )
        for index, value in enumerate(values)
    ]


def test_korean_guide_is_syllable_readable_and_builds_sound_change_candidates() -> None:
    sentence = SongSentence(
        id="ko_hook",
        start_seconds=0,
        end_seconds=4,
        lyrics="Baby, 날 터질 것처럼 안아줘",
        words=_words(["Baby", "날", "터질", "것처럼", "안아줘"]),
    )
    annotated = add_pronunciation_guides([sentence], "ko")[0]

    assert annotated.pronunciation is not None
    assert annotated.pronunciation.text == "Baby, nal teo jil geot cheo reom an a jwo"
    candidates = generate_language_candidates([annotated], language="ko")
    by_span = {candidate.target_span: candidate for candidate in candidates}
    assert by_span["geot cheo"].phenomenon == "final_stop_unreleased"
    assert by_span["reom an"].phenomenon == "liaison"
    assert by_span["reom an"].observed_pronunciation == "reo man"


def test_japanese_guide_uses_correct_compound_kana_reading() -> None:
    assert romanize_japanese("忘れちゃう") == "wa su re cha u"
    assert "chi ya" not in romanize_japanese("忘れちゃう")
    assert romanize_japanese("動物園は　忙しい") == "do u bu tsu e n wa i so ga shi i"
    assert romanize_japanese("シャワーだゾウ") == "sha waa da zo u"


def test_lrclib_matching_preserves_japanese_and_korean_titles() -> None:
    assert _normalize("動物園は大変だ") == "動物園は大変だ"
    assert _normalize("마지막처럼") == "마지막처럼"


def test_romanizers_leave_english_available_in_mixed_lyrics() -> None:
    assert romanize_korean("Baby 안아줘") == "Baby an a jwo"


def test_lyrics_script_wins_over_mixed_english_intro() -> None:
    assert _detect_lyrics_language("BLACKPINK in your area\nBaby 날 터질 것처럼 안아줘") == "ko"
    assert _detect_lyrics_language("大人になったら忘れちゃうのかな") == "ja"
