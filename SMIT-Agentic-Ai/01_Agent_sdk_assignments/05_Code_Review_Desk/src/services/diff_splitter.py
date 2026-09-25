"""Unified-diff intake and per-file splitting."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class DiffChunk:
    file: str
    text: str


@dataclass(frozen=True)
class DiffSplitResult:
    chunks: tuple[DiffChunk, ...] = ()
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


_HEADER = re.compile(r"^diff --git a/(.+?) b/(.+?)$", re.MULTILINE)


def split_unified_diff(diff_text: str) -> DiffSplitResult:
    """Split a unified diff into one chunk per diff header."""

    if not diff_text.strip():
        return DiffSplitResult(error="The diff is empty.")

    matches = list(_HEADER.finditer(diff_text))
    if not matches:
        return DiffSplitResult(error="The input is not a valid unified diff.")

    chunks: list[DiffChunk] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(diff_text)
        file_name = match.group(2)
        chunks.append(DiffChunk(file=file_name, text=diff_text[start:end].rstrip() + "\n"))
    return DiffSplitResult(chunks=tuple(chunks))


async def split_diff_file(path: str | Path) -> DiffSplitResult:
    """Read and split a diff asynchronously, returning readable errors."""

    try:
        text = await asyncio.to_thread(Path(path).read_text, encoding="utf-8")
    except (OSError, UnicodeError):
        return DiffSplitResult(error=f"Could not read diff file: {path}")
    return split_unified_diff(text)

