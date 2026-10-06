import shutil
from pathlib import Path

from pydantic import ValidationError

from server.models.song import AudioAssets, VocalArrangementMode
from server.services.vocal_parts.structure import derive_structural_vocal_parts
from server.storage.profile_store import ProfileStore

JUNO_HERO_SONG_ID = "song_00000000000000000000000000000002"


def build_juno_hero_profile(project_root: Path):
    store = ProfileStore(project_root / "data")
    source = None
    for song_dir in store.songs_dir.iterdir():
        try:
            candidate = store.get(song_dir.name) if song_dir.is_dir() else None
        except ValidationError:
            continue
        if candidate and candidate.title.casefold() == "juno":
            source = candidate
            break
    if source is None:
        raise FileNotFoundError("No analyzed Juno profile is available")

    source_audio = project_root / "data" / "songs" / source.song_id / "audio"
    target_audio = project_root / "data" / "songs" / JUNO_HERO_SONG_ID / "audio"
    target_audio.mkdir(parents=True, exist_ok=True)
    for audio_file in source_audio.iterdir():
        if audio_file.is_file():
            shutil.copy2(audio_file, target_audio / audio_file.name)

    profile = source.model_copy(
        update={
            "song_id": JUNO_HERO_SONG_ID,
            "title": "Juno — Language & Vocal Layers",
            "audio": AudioAssets(
                source_url=f"/api/v1/songs/{JUNO_HERO_SONG_ID}/audio/source",
                vocal_url=(
                    f"/api/v1/songs/{JUNO_HERO_SONG_ID}/audio/vocals"
                    if source.audio.vocal_url
                    else None
                ),
                accompaniment_url=(
                    f"/api/v1/songs/{JUNO_HERO_SONG_ID}/audio/accompaniment"
                    if (target_audio / "accompaniment.wav").is_file()
                    else None
                ),
            ),
            "vocal_parts": derive_structural_vocal_parts(source.sentences),
            "analysis": source.analysis.model_copy(
                update={"vocal_arrangement_mode": VocalArrangementMode.dual_track}
            ),
        }
    )
    store.save(profile)
    return profile


def main() -> None:
    profile = build_juno_hero_profile(Path(__file__).resolve().parents[2])
    print(f"song_id={profile.song_id} vocal_parts={len(profile.vocal_parts)}")


if __name__ == "__main__":
    main()
