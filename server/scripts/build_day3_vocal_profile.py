import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from server.models.song import (
    AnalysisMetadata,
    AudioAssets,
    LyricsSource,
    SongProfile,
    VocalArrangementMode,
    VocalLane,
    VocalPart,
    VocalPartIdentityStatus,
    VocalPartRole,
    VocalPartSource,
    VocalPartTimingStatus,
)
from server.pipelines.whisperx.converter import convert_whisperx_json
from server.services.lyrics_reconciliation import reconcile_provided_lyrics
from server.storage.profile_store import ProfileStore, write_profile_json

DAY3_VOCAL_SONG_ID = "song_00000000000000000000000000000003"
DAY3_DURATION_SECONDS = 36.340893

PRIMARY_WINDOWS = (
    ("primary_01", 0.39, 2.10),
    ("primary_02", 2.24, 4.60),
    ("primary_03", 4.60, 7.65),
    ("primary_04", 7.65, 12.27),
    ("primary_05", 12.28, 14.85),
    ("primary_06", 15.05, 17.45),
    ("primary_07", 17.63, 19.14),
    ("primary_08", 19.18, 21.34),
)

REPEATED_PRIMARY_WINDOWS = (
    (("primary_01", "primary_02"), 21.48, 26.77),
    (("primary_03", "primary_04"), 26.85, 29.95),
    (("primary_05", "primary_06"), 29.97, 32.22),
    (("primary_07", "primary_08"), 32.45, 36.28),
)


def build_day3_vocal_profile(
    project_root: Path, *, persist_profile: bool = True
) -> tuple[SongProfile, Path]:
    day3_dir = project_root / "data" / "day3"
    source_audio = day3_dir / "input" / "get him back!.mp3"
    demucs_dir = day3_dir / "output" / "demucs" / "htdemucs" / "get him back!"
    vocals_audio = demucs_dir / "vocals.wav"
    accompaniment_audio = demucs_dir / "no_vocals.wav"
    transcript_path = day3_dir / "output" / "whisperx" / "get him back!.json"
    cues_path = project_root / "server" / "fixtures" / "get-him-back-vocal-cues.json"
    required = (source_audio, vocals_audio, accompaniment_audio, transcript_path, cues_path)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing Day 3 artifacts: {', '.join(missing)}")

    cue_payload = json.loads(cues_path.read_text(encoding="utf-8"))
    cues = {cue["id"]: cue["text"] for cue in cue_payload["cues"]}
    primary_lines = [cues[cue_id] for cue_id, _, _ in PRIMARY_WINDOWS]
    primary_lines.extend(
        ", ".join(cues[cue_id] for cue_id in cue_ids)
        for cue_ids, _, _ in REPEATED_PRIMARY_WINDOWS
    )
    alignment = convert_whisperx_json(transcript_path)
    sentences, reconciled = reconcile_provided_lyrics(
        "\n".join(primary_lines), alignment.sentences
    )
    if not reconciled or len(sentences) != len(primary_lines):
        sentences = alignment.sentences
    primary_parts = [
        _candidate_part(
            part_id=f"part_{cue_id}",
            lane=VocalLane.primary,
            role=VocalPartRole.lead,
            start=start,
            end=end,
            lyrics=cues[cue_id],
            source=VocalPartSource.acoustic_candidate,
            confidence=0.78,
            cue_ids=[cue_id],
            evidence_note="WhisperX time anchor corrected against the lyric cue.",
        )
        for cue_id, start, end in PRIMARY_WINDOWS
    ]
    for index, (cue_ids, start, end) in enumerate(REPEATED_PRIMARY_WINDOWS, start=1):
        primary_parts.append(
            _candidate_part(
                part_id=f"part_primary_repeat_{index:02d}",
                lane=VocalLane.primary,
                role=VocalPartRole.lead,
                start=start,
                end=end,
                lyrics=", ".join(cues[cue_id] for cue_id in cue_ids),
                source=VocalPartSource.acoustic_candidate,
                confidence=0.74,
                cue_ids=list(cue_ids),
                evidence_note="WhisperX detected the repeated lead passage with imperfect words.",
            )
        )

    all_windows = [
        (part.start_seconds, part.end_seconds) for part in primary_parts
    ]
    timing_path = day3_dir / "output" / "vocal-parts" / "gemini-cue-timings.json"
    gemini_timings = _load_gemini_timings(timing_path)
    secondary_parts = [
        _candidate_part(
            part_id=f"part_secondary_response_{index:02d}",
            lane=VocalLane.secondary,
            role=VocalPartRole.response,
            start=gemini_timings.get(f"secondary_{index:02d}", (start, end, 0.0))[0],
            end=gemini_timings.get(f"secondary_{index:02d}", (start, end, 0.0))[1],
            lyrics=cues[f"secondary_{index:02d}"],
            source=VocalPartSource.lyrics_provider,
            confidence=gemini_timings.get(f"secondary_{index:02d}", (start, end, 0.72))[2],
            cue_ids=[f"secondary_{index:02d}"],
            evidence_note=(
                "Parenthesized provider lyric is fixed; timing comes from Gemini when "
                "available, otherwise the overlapping WhisperX phrase window is used."
            ),
        )
        for index, (start, end) in enumerate(all_windows, start=1)
    ]

    audio_dir = project_root / "data" / "songs" / DAY3_VOCAL_SONG_ID / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_audio, audio_dir / "source.mp3")
    shutil.copy2(vocals_audio, audio_dir / "vocals.wav")
    shutil.copy2(accompaniment_audio, audio_dir / "accompaniment.wav")
    created_at = datetime.fromtimestamp(source_audio.stat().st_mtime, tz=UTC)
    profile = SongProfile(
        song_id=DAY3_VOCAL_SONG_ID,
        title="get him back! — Bridge Vocal Layers",
        duration_seconds=DAY3_DURATION_SECONDS,
        language="en",
        audio=AudioAssets(
            source_url=f"/api/v1/songs/{DAY3_VOCAL_SONG_ID}/audio/source",
            vocal_url=f"/api/v1/songs/{DAY3_VOCAL_SONG_ID}/audio/vocals",
            accompaniment_url=(
                f"/api/v1/songs/{DAY3_VOCAL_SONG_ID}/audio/accompaniment"
            ),
        ),
        sentences=sentences,
        vocal_parts=[*primary_parts, *secondary_parts],
        analysis=AnalysisMetadata(
            pipeline_version="day3-vocal-parts-v2",
            separation_model="htdemucs",
            alignment_model="whisperx-small-plus-lyric-cues",
            lyrics_source=LyricsSource.corrected,
            lyrics_provider="cifraclub-parenthetical-demo-truth",
            lyrics_match_confidence=0.9,
            created_at=created_at,
            language_analysis_provider=(
                "gemini-cue-timing" if gemini_timings else "whisperx-window-fallback"
            ),
            language_analysis_model="gemini-3.8-flash",
            vocal_arrangement_mode=VocalArrangementMode.dual_track,
        ),
    )
    fixture_path = day3_dir / "output" / "vocal-parts" / "song-profile.json"
    write_profile_json(profile, fixture_path)
    if persist_profile:
        ProfileStore(project_root / "data").save(profile)
    return profile, fixture_path


def _candidate_part(
    *,
    part_id: str,
    lane: VocalLane,
    role: VocalPartRole,
    start: float,
    end: float,
    lyrics: str,
    source: VocalPartSource,
    confidence: float,
    cue_ids: list[str],
    evidence_note: str,
) -> VocalPart:
    return VocalPart(
        id=part_id,
        lane=lane,
        role=role,
        start_seconds=start,
        end_seconds=end,
        lyrics=lyrics,
        source=source,
        confidence=confidence,
        needs_human_review=source != VocalPartSource.lyrics_provider,
        identity_status=(
            VocalPartIdentityStatus.confirmed
            if source == VocalPartSource.lyrics_provider
            else VocalPartIdentityStatus.candidate
        ),
        timing_status=(
            VocalPartTimingStatus.audio_model_observed
            if source == VocalPartSource.lyrics_provider and confidence > 0
            else VocalPartTimingStatus.aligned_sentence_fallback
        ),
        timing_confidence=confidence if source == VocalPartSource.lyrics_provider else None,
        timing_needs_human_review=source == VocalPartSource.lyrics_provider,
        evidence={
            "audioRef": "data/day3/output/demucs/htdemucs/get him back!/vocals.wav",
            "transcriptRef": "data/day3/output/whisperx/get him back!.json",
            "cueIds": cue_ids,
            "note": evidence_note,
        },
    )


def _load_gemini_timings(path: Path) -> dict[str, tuple[float, float, float]]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        item["cueId"]: (
            float(item["startSeconds"]),
            float(item["endSeconds"]),
            float(item["confidence"]),
        )
        for item in payload.get("timings", [])
        if item.get("detected")
    }


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    profile, fixture_path = build_day3_vocal_profile(project_root)
    print(f"Created {fixture_path}")
    print(f"song_id={profile.song_id} vocal_parts={len(profile.vocal_parts)}")


if __name__ == "__main__":
    main()
