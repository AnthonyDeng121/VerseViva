import argparse
import shutil
from pathlib import Path

from server.models.song import AudioAssets
from server.storage.profile_store import ProfileStore


def promote_song_profile(project_root: Path, source_song_id: str, target_song_id: str):
    store = ProfileStore(project_root / "data")
    source = store.get(source_song_id)
    if source is None:
        raise FileNotFoundError(f"Song Profile not found: {source_song_id}")

    source_audio = store.songs_dir / source_song_id / "audio"
    target_audio = store.songs_dir / target_song_id / "audio"
    target_audio.mkdir(parents=True, exist_ok=True)
    for audio_file in source_audio.iterdir():
        if audio_file.is_file():
            shutil.copy2(audio_file, target_audio / audio_file.name)

    profile = source.model_copy(
        update={
            "song_id": target_song_id,
            "audio": AudioAssets(
                source_url=f"/api/v1/songs/{target_song_id}/audio/source",
                vocal_url=(
                    f"/api/v1/songs/{target_song_id}/audio/vocals"
                    if (target_audio / "vocals.wav").is_file()
                    else None
                ),
                accompaniment_url=(
                    f"/api/v1/songs/{target_song_id}/audio/accompaniment"
                    if (target_audio / "accompaniment.wav").is_file()
                    else None
                ),
            ),
        }
    )
    store.save(profile)
    return profile


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote an analyzed song to a stable Hero ID.")
    parser.add_argument("source_song_id")
    parser.add_argument("target_song_id")
    args = parser.parse_args()
    profile = promote_song_profile(
        Path(__file__).resolve().parents[2], args.source_song_id, args.target_song_id
    )
    print(
        f"song_id={profile.song_id} sentences={len(profile.sentences)} "
        f"vocal_parts={len(profile.vocal_parts)}"
    )


if __name__ == "__main__":
    main()
