"""Load generation outputs from files, directories, JSONL, or stdin.

Every input becomes a flat list of :class:`Record` objects, so the metric
modules never care where text came from. Formats:

- ``lines``  — one record per non-empty line (plain .txt).
- ``jsonl``  — one JSON value per line; objects are indexed by ``field``
  (dotted paths supported), bare strings are taken as-is.
- ``files``  — a directory: every file inside is one whole record.
- ``auto``   — pick per path: directories -> files, ``.jsonl``/``.ndjson``
  -> jsonl, everything else -> lines.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

FORMATS = ("auto", "lines", "jsonl", "files")


class ReaderError(ValueError):
    """Raised for unreadable inputs: missing paths, bad JSON, missing fields."""


@dataclass(frozen=True)
class Record:
    """One generation output: its position, where it came from, and its text."""

    index: int
    source: str
    text: str


def load_records(
    paths: Sequence[str],
    *,
    fmt: str = "auto",
    field: str = "text",
    encoding: str = "utf-8",
) -> List[Record]:
    """Read all *paths* (``-`` means stdin) into a list of records.

    Records are numbered globally in input order so duplicate-cluster output
    can point back at a stable index even across multiple files.
    """
    if fmt not in FORMATS:
        raise ReaderError(f"unknown format {fmt!r}; expected one of {', '.join(FORMATS)}")
    if not paths:
        raise ReaderError("no input paths given")

    records: List[Record] = []
    for raw in paths:
        if raw == "-":
            if fmt == "files":
                # Same semantics as --format files on a regular file:
                # the whole stream is one record.
                _append(records, "<stdin>", sys.stdin.read())
            else:
                _extend_lines(records, sys.stdin.read().splitlines(), "<stdin>", fmt, field)
            continue
        path = Path(raw)
        if not path.exists():
            raise ReaderError(f"input not found: {raw}")
        if path.is_dir():
            if fmt not in ("auto", "files"):
                raise ReaderError(f"{raw} is a directory; use --format files or auto")
            _extend_dir(records, path, encoding)
            continue
        effective = fmt
        if fmt == "auto":
            effective = "jsonl" if path.suffix.lower() in (".jsonl", ".ndjson") else "lines"
        if effective == "files":
            _append(records, str(path), _read_file(path, encoding))
            continue
        try:
            lines = path.read_text(encoding=encoding).splitlines()
        except UnicodeDecodeError as exc:
            raise ReaderError(f"{raw}: not decodable as {encoding}: {exc}") from None
        _extend_lines(records, lines, str(path), effective, field)
    return records


def _extend_lines(
    records: List[Record], lines: Iterable[str], source: str, fmt: str, field: str
) -> None:
    if fmt in ("auto", "lines"):
        for line in lines:
            if line.strip():
                _append(records, source, line)
        return
    # jsonl
    for lineno, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ReaderError(f"{source}:{lineno}: invalid JSON: {exc.msg}") from None
        _append(records, f"{source}:{lineno}", _extract_field(value, field, source, lineno))


def _extract_field(value: object, field: str, source: str, lineno: int) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        raise ReaderError(
            f"{source}:{lineno}: expected a JSON object or string, got {type(value).__name__}"
        )
    current: object = value
    for part in field.split("."):
        if not isinstance(current, dict) or part not in current:
            raise ReaderError(f"{source}:{lineno}: field {field!r} not found")
        current = current[part]
    if not isinstance(current, str):
        raise ReaderError(
            f"{source}:{lineno}: field {field!r} is {type(current).__name__}, expected string"
        )
    return current


def _extend_dir(records: List[Record], path: Path, encoding: str) -> None:
    files = sorted(p for p in path.rglob("*") if p.is_file() and not p.name.startswith("."))
    if not files:
        raise ReaderError(f"directory {path} contains no files")
    for file in files:
        _append(records, str(file), _read_file(file, encoding))


def _read_file(path: Path, encoding: str) -> str:
    try:
        return path.read_text(encoding=encoding)
    except UnicodeDecodeError as exc:
        raise ReaderError(f"{path}: not decodable as {encoding}: {exc}") from None


def _append(records: List[Record], source: str, text: str) -> None:
    if text.strip():
        records.append(Record(index=len(records), source=source, text=text))
