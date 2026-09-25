"""Safe access to already-split diff chunks."""

from __future__ import annotations

from collections.abc import Mapping

from agents import function_tool
from agents.run_context import RunContextWrapper
from src.context.review_context import ReviewContext


def read_diff_chunk(file: str, *, chunks: Mapping[str, str]) -> str:
    """Return a diff chunk or a model-readable error message."""

    try:
        value = chunks.get(file)
        if value is None:
            return f"Could not read diff for file: {file}. It may not be part of this diff."
        return value
    except (AttributeError, KeyError, TypeError):
        return f"Could not read diff for file: {file}. It may not be part of this diff."


def make_diff_chunk_tool(chunks: Mapping[str, str]):
    """Create an SDK tool whose only model-visible input is ``file``."""

    @function_tool
    def read_chunk(ctx: RunContextWrapper[ReviewContext], file: str) -> str:
        del ctx
        return read_diff_chunk(file, chunks=chunks)

    read_chunk.name = "read_diff_chunk"
    read_chunk.description = "Read the already-split unified diff chunk for one file."
    return read_chunk
