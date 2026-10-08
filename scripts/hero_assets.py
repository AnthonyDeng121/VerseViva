"""Build or restore the three curated Hero songs as a deployment bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

HERO_IDS = (
    "song_00000000000000000000000000000003",
    "song_00000000000000000000000000000004",
    "song_00000000000000000000000000000005",
)
REQUIRED_FILES = (
    "profile.json",
    "audio/source.mp3",
    "audio/vocals.mp3",
    "audio/accompaniment.mp3",
    "audio/vocals.wav",
    "audio/accompaniment.wav",
)


def build(data_dir: Path, output: Path) -> None:
    songs_dir = data_dir / "songs"
    entries = []
    for song_id in HERO_IDS:
        song_dir = songs_dir / song_id
        for relative in REQUIRED_FILES:
            source = song_dir / relative
            if not source.is_file() or source.stat().st_size == 0:
                raise FileNotFoundError(f"Hero asset is missing: {source}")
            entries.append((source, Path("songs") / song_id / relative))

    manifest = {
        "formatVersion": 1,
        "createdAt": datetime.now(UTC).isoformat(),
        "heroSongIds": list(HERO_IDS),
        "files": [
            {
                "path": archive.as_posix(),
                "sizeBytes": source.stat().st_size,
                "sha256": _sha256(source),
            }
            for source, archive in entries
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for source, name in entries:
            archive.write(source, name.as_posix())
    temporary.replace(output)
    print(f"Hero bundle created: {output} ({output.stat().st_size / 1024 / 1024:.2f} MB)")


def restore(bundle: Path, data_dir: Path) -> None:
    target_root = data_dir.resolve()
    with zipfile.ZipFile(bundle) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        if tuple(manifest.get("heroSongIds", ())) != HERO_IDS:
            raise ValueError("Bundle Hero IDs do not match this VerseViva release")
        for item in manifest.get("files", []):
            relative = Path(item["path"])
            target = (target_root / relative).resolve()
            if target_root not in target.parents:
                raise ValueError(f"Unsafe bundle path: {relative}")
            payload = archive.read(relative.as_posix())
            if hashlib.sha256(payload).hexdigest() != item["sha256"]:
                raise ValueError(f"Checksum mismatch: {relative}")
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f".{target.name}.tmp")
            temporary.write_bytes(payload)
            temporary.replace(target)
    print(f"Hero bundle restored into: {target_root}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--data-dir", type=Path, default=Path("data"))
    build_parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/verseviva-hero-assets.zip"),
    )
    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("bundle", type=Path)
    restore_parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    if args.command == "build":
        build(args.data_dir, args.output)
    else:
        restore(args.bundle, args.data_dir)


if __name__ == "__main__":
    main()
