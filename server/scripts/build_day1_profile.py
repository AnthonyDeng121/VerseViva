import asyncio
from datetime import UTC, datetime
from pathlib import Path

from server.models.song import AudioAssets, LyricsSource, SongProfile
from server.pipelines.audio_probe import FfprobeAudioDurationProbe
from server.pipelines.basic_pitch import convert_basic_pitch_contour
from server.pipelines.whisperx import convert_whisperx_json
from server.services.song_profile_builder import build_song_profile
from server.storage.profile_store import ProfileStore, write_profile_json

DAY1_SONG_ID = "song_00000000000000000000000000000001"


def build_day1_profile(project_root: Path) -> tuple[SongProfile, Path]:
    day1_dir = project_root / "data" / "day1"
    output_dir = day1_dir / "output"
    source_audio = day1_dir / "input" / "song-60s.mp3"
    vocals = output_dir / "demucs" / "htdemucs" / "song-60s" / "vocals.wav"
    pitch_csv = output_dir / "pitch" / "vocals_basic_pitch.csv"
    pitch_npz = output_dir / "pitch" / "vocals_basic_pitch.npz"
    alignment_json = output_dir / "whisperx" / "vocals.json"

    required = (source_audio, vocals, pitch_csv, pitch_npz, alignment_json)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing Day 1 artifacts: {', '.join(missing)}")

    pitch_conversion = convert_basic_pitch_contour(pitch_csv, pitch_npz)
    alignment = convert_whisperx_json(alignment_json)
    duration = asyncio.run(FfprobeAudioDurationProbe().duration_seconds(source_audio))
    created_at = datetime.fromtimestamp(alignment_json.stat().st_mtime, tz=UTC)
    profile = build_song_profile(
        song_id=DAY1_SONG_ID,
        title="Day 1 60-second Sample",
        duration_seconds=duration,
        language=alignment.language,
        audio=AudioAssets(
            source_url=f"/api/v1/songs/{DAY1_SONG_ID}/audio/source",
            vocal_url=f"/api/v1/songs/{DAY1_SONG_ID}/audio/vocals",
        ),
        sentences=alignment.sentences,
        notes=pitch_conversion.notes,
        pitch_points=pitch_conversion.pitch_points,
        pitch_processing=pitch_conversion.summary,
        pipeline_version="day3-reference-pitch-v1",
        separation_model="htdemucs",
        pitch_model="basic-pitch",
        alignment_model="whisperx",
        lyrics_source=LyricsSource.asr,
        created_at=created_at,
    )

    fixture_path = output_dir / "song-profile.json"
    write_profile_json(profile, fixture_path)
    ProfileStore(project_root / "data").save(profile)
    return profile, fixture_path


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    profile, fixture_path = build_day1_profile(project_root)
    word_count = sum(len(sentence.words) for sentence in profile.sentences)
    note_count = sum(len(sentence.notes) for sentence in profile.sentences)
    pitch_point_count = sum(len(sentence.pitch_contour) for sentence in profile.sentences)
    print(f"Created {fixture_path}")
    print(
        f"song_id={profile.song_id} sentences={len(profile.sentences)} "
        f"words={word_count} assigned_notes={note_count} pitch_points={pitch_point_count}"
    )


if __name__ == "__main__":
    main()
