"""Detects encoding/delimiter of an uploaded CSV and parses it into string rows."""

import csv
import io
from dataclasses import dataclass, field

CANDIDATE_DELIMITERS = (",", ";", "\t", "|")
_SAMPLE_LINES = 50
_UTF8_BOM = b"\xef\xbb\xbf"


class CsvFormatError(ValueError):
    """The upload cannot be read as a CSV file."""


@dataclass(frozen=True)
class CsvFormat:
    encoding: str
    delimiter: str


@dataclass
class ParsedCsv:
    header: list[str]
    rows: list[list[str]]
    row_lines: list[int] = field(default_factory=list)  # source line of each row (1-based)
    ragged_lines: list[int] = field(default_factory=list)  # rows dropped: wrong column count


def _detect_encoding(raw: bytes) -> str:
    if raw.startswith(_UTF8_BOM):
        return "utf-8-sig"
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    try:
        raw.decode("cp1252")
        return "cp1252"
    except UnicodeDecodeError:
        return "latin-1"  # decodes any byte sequence


def _sample(text: str) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    return "\n".join(lines[:_SAMPLE_LINES])


def _score(sample: str, delimiter: str) -> tuple[float, int]:
    """(share of rows matching the header width, header width); 0 if only one column."""
    rows = [r for r in csv.reader(io.StringIO(sample), delimiter=delimiter) if r]
    if not rows or len(rows[0]) < 2:
        return (0.0, 0)
    width = len(rows[0])
    body = rows[1:] or rows
    consistent = sum(1 for r in body if len(r) == width) / len(body)
    return (consistent, width)


def detect_format(raw: bytes) -> CsvFormat:
    if not raw.strip():
        raise CsvFormatError("The file is empty")
    if b"\x00" in raw[:8192]:
        raise CsvFormatError("The file looks binary, not a CSV text file")

    encoding = _detect_encoding(raw)
    sample = _sample(raw.decode(encoding))
    if not sample:
        raise CsvFormatError("The file is empty")

    best = max(CANDIDATE_DELIMITERS, key=lambda d: _score(sample, d))
    if _score(sample, best)[1] == 0:
        best = ","  # single-column file
    return CsvFormat(encoding=encoding, delimiter=best)


def parse_csv(raw: bytes, fmt: CsvFormat) -> ParsedCsv:
    text = raw.decode(fmt.encoding)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=fmt.delimiter)

    header: list[str] | None = None
    parsed = ParsedCsv(header=[], rows=[])
    for record in reader:
        values = [v.strip() for v in record]
        if not any(values):
            continue  # blank line
        if header is None:
            header = values
            continue
        if len(values) != len(header):
            parsed.ragged_lines.append(reader.line_num)
            continue
        parsed.rows.append(values)
        parsed.row_lines.append(reader.line_num)

    if header is None:
        raise CsvFormatError("The file has no header row")
    parsed.header = header
    return parsed
