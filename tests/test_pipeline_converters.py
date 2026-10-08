from pathlib import Path

import pytest

from server.pipelines.errors import PipelineOutputError
from server.pipelines.whisperx.converter import convert_whisperx_json

ROOT = Path(__file__).resolve().parents[1]
WHISPERX_FIXTURE = ROOT / "server" / "fixtures" / "whisperx-real-alignment.json"


def test_whisperx_converter_handles_real_day1_alignment() -> None:
    result = convert_whisperx_json(WHISPERX_FIXTURE)

    assert result.language == "en"
    assert len(result.sentences) == 4
    assert sum(len(sentence.words) for sentence in result.sentences) == 96
    assert result.sentences[0].id == "sentence_001"
    assert result.sentences[0].words[0].id == "word_001_001"


def test_whisperx_converter_omits_words_without_timestamps(tmp_path: Path) -> None:
    source = tmp_path / "alignment.json"
    source.write_text(
        '{"language":"en","segments":[{"start":0,"end":1,"text":"hello world",'
        '"words":[{"word":"hello"},{"word":"world","start":0.5,"end":1}]}]}',
        encoding="utf-8",
    )

    result = convert_whisperx_json(source)

    assert result.sentences[0].lyrics == "hello world"
    assert [word.text for word in result.sentences[0].words] == ["world"]


def test_converter_reports_invalid_model_output(tmp_path: Path) -> None:
    source = tmp_path / "bad.json"
    source.write_text("not valid model output", encoding="utf-8")

    with pytest.raises(PipelineOutputError):
        convert_whisperx_json(source)
