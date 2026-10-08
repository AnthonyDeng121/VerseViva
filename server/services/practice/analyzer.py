import asyncio
import json
import time
from pathlib import Path

from server.models.practice import LanguageIssueType
from server.models.song import LanguageHint, SongSentence, VocalPart
from server.pipelines.language_coach import _is_retryable_gemini_error
from server.services.practice.models import AcousticFindingBatch


class GeminiPracticeAnalyzer:
    provider = "gemini"

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError("Gemini API key is required for practice analysis")
        self.api_key = api_key
        self.model = model

    async def analyze(
        self,
        audio_path: Path,
        sentences: list[SongSentence],
        reference_vocal_path: Path | None = None,
    ) -> AcousticFindingBatch:
        return await asyncio.to_thread(
            self._analyze_sync,
            audio_path,
            sentences,
            reference_vocal_path,
        )

    async def analyze_secondary(
        self,
        audio_path: Path,
        reference_vocal_path: Path,
        vocal_part: VocalPart,
    ) -> AcousticFindingBatch:
        return await asyncio.to_thread(
            self._analyze_secondary_sync,
            audio_path,
            reference_vocal_path,
            vocal_part,
        )

    def _analyze_secondary_sync(
        self,
        audio_path: Path,
        reference_vocal_path: Path,
        vocal_part: VocalPart,
    ) -> AcousticFindingBatch:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                return self._analyze_secondary_once(
                    audio_path,
                    reference_vocal_path,
                    vocal_part,
                )
            except Exception as exc:
                last_error = exc
                if attempt == 2 or not _is_retryable_gemini_error(exc):
                    raise
                time.sleep(2 ** (attempt + 1))
        raise RuntimeError("Gemini secondary practice analysis failed") from last_error

    def _analyze_sync(
        self,
        audio_path: Path,
        sentences: list[SongSentence],
        reference_vocal_path: Path | None,
    ) -> AcousticFindingBatch:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                return self._analyze_once(audio_path, sentences, reference_vocal_path)
            except Exception as exc:
                last_error = exc
                if attempt == 2 or not _is_retryable_gemini_error(exc):
                    raise
                time.sleep(2 ** (attempt + 1))
        raise RuntimeError("Gemini practice analysis failed") from last_error

    def _analyze_once(
        self,
        audio_path: Path,
        sentences: list[SongSentence],
        reference_vocal_path: Path | None,
    ) -> AcousticFindingBatch:
        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError("Practice analysis requires google-genai") from exc

        client = genai.Client(api_key=self.api_key)
        uploaded = _wait_for_active(client, client.files.upload(file=str(audio_path)))
        reference_audio = None
        if reference_vocal_path is not None:
            reference_audio = _wait_for_active(
                client,
                client.files.upload(file=str(reference_vocal_path)),
            )
        try:
            audio_inputs = []
            if reference_audio is not None:
                audio_inputs.append(
                    {
                        "type": "audio",
                        "uri": reference_audio.uri,
                        "mime_type": reference_audio.mime_type,
                    }
                )
            audio_inputs.append(
                {
                    "type": "audio",
                    "uri": uploaded.uri,
                    "mime_type": uploaded.mime_type,
                }
            )
            interaction = client.interactions.create(
                model=self.model,
                input=[
                    {"type": "text", "text": _build_prompt(sentences)},
                    *audio_inputs,
                ],
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": AcousticFindingBatch.model_json_schema(),
                },
            )
            batch = AcousticFindingBatch.model_validate_json(interaction.output_text)
            known = {hint.id for sentence in sentences for hint in sentence.language_hints}
            findings = [finding for finding in batch.findings if finding.hint_id in known]
            return batch.model_copy(update={"findings": findings})
        finally:
            for item in (uploaded, reference_audio):
                name = getattr(item, "name", None)
                if name:
                    try:
                        client.files.delete(name=name)
                    except Exception:
                        pass

    def _analyze_secondary_once(
        self,
        audio_path: Path,
        reference_vocal_path: Path,
        vocal_part: VocalPart,
    ) -> AcousticFindingBatch:
        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError("Practice analysis requires google-genai") from exc

        client = genai.Client(api_key=self.api_key)
        user_audio = client.files.upload(file=str(audio_path))
        reference_audio = client.files.upload(file=str(reference_vocal_path))
        user_audio = _wait_for_active(client, user_audio)
        reference_audio = _wait_for_active(client, reference_audio)
        try:
            interaction = client.interactions.create(
                model=self.model,
                input=[
                    {"type": "text", "text": _build_secondary_prompt(vocal_part)},
                    {
                        "type": "audio",
                        "uri": reference_audio.uri,
                        "mime_type": reference_audio.mime_type,
                    },
                    {
                        "type": "audio",
                        "uri": user_audio.uri,
                        "mime_type": user_audio.mime_type,
                    },
                ],
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": AcousticFindingBatch.model_json_schema(),
                },
            )
            batch = AcousticFindingBatch.model_validate_json(interaction.output_text)
            known = {
                secondary_target_id(vocal_part.id, issue_type)
                for issue_type in LanguageIssueType
            }
            findings = [item for item in batch.findings if item.hint_id in known]
            return batch.model_copy(update={"findings": findings})
        finally:
            for uploaded in (user_audio, reference_audio):
                name = getattr(uploaded, "name", None)
                if name:
                    try:
                        client.files.delete(name=name)
                    except Exception:
                        pass


def issue_type_for_hint(hint: LanguageHint) -> LanguageIssueType | None:
    phenomenon = hint.phenomenon.lower()
    operations = {item.operation.value for item in hint.transformations}
    if "elision" in phenomenon or "unreleased" in phenomenon or "delete" in operations:
        return LanguageIssueType.expected_elision_realized
    if "identical" in phenomenon or "merge" in phenomenon:
        return LanguageIssueType.identical_consonants_separated
    if "assimilation" in phenomenon:
        return LanguageIssueType.coalescent_assimilation_missing
    return None


def _wait_for_active(client, uploaded, timeout_seconds: float = 60.0):
    """Gemini rejects freshly uploaded files until server-side processing is ACTIVE."""
    deadline = time.monotonic() + timeout_seconds
    current = uploaded
    while time.monotonic() < deadline:
        state = getattr(current, "state", None)
        state_name = str(getattr(state, "name", state) or "").upper()
        if state_name.endswith("ACTIVE") or not state_name:
            return current
        if state_name.endswith("FAILED"):
            raise RuntimeError("Gemini 音频文件处理失败")
        time.sleep(1)
        name = getattr(current, "name", None)
        if not name:
            return current
        current = client.files.get(name=name)
    raise TimeoutError("Gemini 音频文件未在 60 秒内准备完成")


def _build_prompt(sentences: list[SongSentence]) -> str:
    targets = []
    for sentence in sentences:
        for hint in sentence.language_hints:
            issue_type = issue_type_for_hint(hint)
            if issue_type is None:
                continue
            words = sentence.words[hint.start_word_index : hint.end_word_index + 1]
            targets.append(
                {
                    "hintId": hint.id,
                    "sentenceId": sentence.id,
                    "lyrics": sentence.lyrics,
                    "targetWords": " ".join(word.text for word in words),
                    "referencePhenomenon": hint.phenomenon,
                    "expectedIssueTypeWhenUserDiffers": issue_type.value,
                    "transformations": [
                        item.model_dump(mode="json", by_alias=True)
                        for item in hint.transformations
                    ],
                }
            )
    return f"""
你会依次收到参考整体人声（若提供）和用户录音。参考人声仅用于核对本次原唱的实际处理，
用户录音才是诊断对象；不得把不同 Vocal lane 的声音或歌词互相连接。
你正在核查一段用户练唱录音，只判断 TARGETS 中已有的语言演唱目标。

规则：
- 不评价音高、音色、情绪，也不输出 timing_deviation 或任何毫秒级偏差。
- 不得根据歌词拼写猜测用户唱法；只写录音中可听见的证据。
- 必须为每个 TARGET 恰好返回一次，使用 issue_detected、reference_matched 或 uncertain；
  不得添加 TARGETS 之外的问题。
- issue_detected：用户没有实现参考目标，issueType 必须等于目标给定值。
- reference_matched：用户已实现参考目标，issueType 必须为 null。
- uncertain：伴奏泄漏、叠唱、噪声、漏唱或发音不清导致不能可靠判断，issueType 必须为 null。
- 若整段录音无法可靠判断，recordingUsable=false，并填写 insufficientReason。
- audibleEvidence 使用简短中文，只描述听到的声音；不得声称观察到舌位、频谱或波形。

TARGETS:
{json.dumps(targets, ensure_ascii=False)}
""".strip()


def secondary_target_id(part_id: str, issue_type: LanguageIssueType) -> str:
    return f"secondary:{part_id}:{issue_type.value}"


def _build_secondary_prompt(vocal_part: VocalPart) -> str:
    targets = [
        {
            "hintId": secondary_target_id(vocal_part.id, issue_type),
            "issueType": issue_type.value,
        }
        for issue_type in LanguageIssueType
    ]
    return f"""
你会依次收到两段音频：第一段是包含多层人声的参考 vocals stem，第二段是用户单独录制的次轨。
只比较以下已确认 secondary 歌词在参考区间中的语言演唱动作与用户录音，不评价音高、音色、
情绪，不输出 timing_deviation 或毫秒偏差。

次轨角色：{vocal_part.role.value}
确定歌词：{vocal_part.lyrics}
参考区间：{vocal_part.start_seconds:.3f} 至 {vocal_part.end_seconds:.3f} 秒
允许核查的 TARGETS：{json.dumps(targets, ensure_ascii=False)}

约束：
- 参考 stem 含主唱和其他重叠人声；如果无法把确定歌词的发音动作可靠辨认出来，必须返回
  recordingUsable=false，不得借主唱听感推断次轨。
- issue_detected 只用于参考和用户之间清楚可听的语言动作差异，issueType 必须匹配 hintId。
- reference_matched 表示该类差异没有出现；uncertain 表示单项无法判断。
- 必须为每个 TARGET 恰好返回一次，才能与该次轨近期练习进行同目标比较。
- 最多返回 3 个 issue_detected；问题不足时不得凑数。
- audibleEvidence 只用简短中文描述实际听感，不得编造频谱、舌位或波形证据。
""".strip()
