"""Command-line entry point for diff intake."""

from __future__ import annotations

import argparse
import asyncio

from src.services.diff_splitter import split_diff_file


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Review a unified diff.")
    parser.add_argument("diff_path", help="Path to a unified diff file")
    return parser


async def run_cli(diff_path: str) -> int:
    result = await split_diff_file(diff_path)
    if not result.ok:
        print(result.error)
        return 2
    print(f"Loaded {len(result.chunks)} diff chunk(s).")
    for chunk in result.chunks:
        print(f"- {chunk.file}")
    return 0


def main() -> None:
    args = _parser().parse_args()
    raise SystemExit(asyncio.run(run_cli(args.diff_path)))


if __name__ == "__main__":
    main()

