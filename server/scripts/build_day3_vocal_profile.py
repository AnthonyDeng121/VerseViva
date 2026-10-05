import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from server.models.song import (
    AnalysisMetadata,
    AudioAssets,
    LyricsSource,
    SongProfile,
    VocalLane,
    VocalPart,
    VocalPartRole,
    VocalPartSource,
)
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


def build_day3_vocal_profile(project_root: Path) -> tuple[SongProfile, Path]:
    day3_dir = project_root / "data" / "day3"
    source_audio = day3_dir / "input" / "get him back!.mp3"
    transcript_path = day3_dir / "output" / "whisperx" / "get him back!.json"
    cues_path = project_root / "server" / "fixtures" / "get-him-back-vocal-cues.json"
    required = (source_audio, transcript_path, cues_path)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing Day 3 artifacts: {', '.join(missing)}")

    cue_payload = json.loads(cues_path.read_text(encoding="utf-8"))
    cues = {cue["id"]: cue["text"] for cue in cue_payload["cues"]}
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
    secondary_parts = [
        _candidate_part(
            part_id=f"part_secondary_response_{index:02d}",
            lane=VocalLane.secondary,
            role=VocalPartRole.response,
            start=start,
            end=end,
            lyrics=cues["secondary_short" if index in {1, 11} else "secondary_long"],
            source=VocalPartSource.lyrics_structure_candidate,
            confidence=0.64,
            cue_ids=["secondary_short" if index in {1, 11} else "secondary_long"],
            evidence_note=(
                "Parenthesized lyric structure overlaps this lead window; "
                "audio review pending."
            ),
        )
        for index, (start, end) in enumerate(all_windows, start=1)
    ]

    audio_dir = project_root / "data" / "songs" / DAY3_VOCAL_SONG_ID / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_audio, audio_dir / "source.mp3")
    created_at = datetime.fromtimestamp(source_audio.stat().st_mtime, tz=UTC)
    profile = SongProfile(
        song_id=DAY3_VOCAL_SONG_ID,
        title="get him back! — Bridge Vocal Layers",
        duration_seconds=DAY3_DURATION_SECONDS,
        language="en",
        audio=AudioAssets(
            source_url=f"/api/v1/songs/{DAY3_VOCAL_SONG_ID}/audio/source",
            vocal_url=None,
        ),
        sentences=[],
        vocal_parts=[*primary_parts, *secondary_parts],
        analysis=AnalysisMetadata(
            pipeline_version="day3-vocal-parts-v1",
            separation_model="not_run_mixed_reference_only",
            pitch_model="not_run",
            alignment_model="whisperx-small-plus-lyric-cues",
            lyrics_source=LyricsSource.corrected,
            lyrics_provider="cifraclub-structure-candidate",
            lyrics_match_confidence=0.9,
            created_at=created_at,
            language_analysis_provider="gemini-quota-blocked",
            language_analysis_model="gemini-3.8-flash",
        ),
    )
    fixture_path = day3_dir / "output" / "vocal-parts" / "song-profile.json"
    write_profile_json(profile, fixture_path)
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
        needs_human_review=True,
        evidence={
            "audioRef": "data/day3/input/get him back!.mp3",
            "transcriptRef": "data/day3/output/whisperx/get him back!.json",
            "cueIds": cue_ids,
            "note": evidence_note,
        },
    )


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    profile, fixture_path = build_day3_vocal_profile(project_root)
    print(f"Created {fixture_path}")
    print(f"song_id={profile.song_id} vocal_parts={len(profile.vocal_parts)}")


if __name__ == "__main__":
    main()
