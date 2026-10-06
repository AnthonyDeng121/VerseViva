import argparse
import asyncio
from pathlib import Path

from server.config import get_settings
from server.pipelines.song_analysis import build_default_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one persisted VerseViva analysis job.")
    parser.add_argument("job_id")
    parser.add_argument("source", type=Path)
    args = parser.parse_args()

    source = args.source.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    asyncio.run(build_default_pipeline(get_settings()).run(args.job_id, source))


if __name__ == "__main__":
    main()
