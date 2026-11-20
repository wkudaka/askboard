import pytest

from askboard.ingestion.sniff import CsvFormat, CsvFormatError, detect_format, parse_csv


def test_detects_utf8_comma_file():
    raw = b"id,name,amount\n1,Ana,10.5\n2,Bruno,20\n"
    assert detect_format(raw) == CsvFormat(encoding="utf-8", delimiter=",")


def test_detects_utf8_bom_and_strips_it_from_header():
    raw = "﻿id;nome\n1;Ana\n".encode("utf-8")

    fmt = detect_format(raw)
    parsed = parse_csv(raw, fmt)

    assert fmt == CsvFormat(encoding="utf-8-sig", delimiter=";")
    assert parsed.header == ["id", "nome"]


def test_falls_back_to_cp1252_for_latin_files():
    raw = "id;cidade\n1;São Paulo\n2;Goiânia\n".encode("cp1252")

    fmt = detect_format(raw)
    parsed = parse_csv(raw, fmt)

    assert fmt.encoding == "cp1252"
    assert parsed.rows[0] == ["1", "São Paulo"]


@pytest.mark.parametrize("delimiter", [",", ";", "\t", "|"])
def test_detects_common_delimiters(delimiter):
    lines = [delimiter.join(["a", "b", "c"]), delimiter.join(["1", "2", "3"]), delimiter.join(["4", "5", "6"])]
    raw = ("\n".join(lines) + "\n").encode()

    assert detect_format(raw).delimiter == delimiter


def test_semicolon_wins_when_values_contain_decimal_commas():
    raw = b"produto;preco\nCaneta;1,50\nLapis;0,75\nCaderno;12,00\n"
    assert detect_format(raw).delimiter == ";"


def test_handles_quoted_fields_with_delimiters_and_newlines():
    raw = b'id,comment\n1,"hello, world"\n2,"multi\nline"\n'

    parsed = parse_csv(raw, detect_format(raw))

    assert parsed.rows == [["1", "hello, world"], ["2", "multi\nline"]]


def test_single_column_file_is_supported():
    raw = b"city\nRecife\nNatal\n"

    parsed = parse_csv(raw, detect_format(raw))

    assert parsed.header == ["city"]
    assert parsed.rows == [["Recife"], ["Natal"]]


def test_ragged_rows_are_reported_with_line_numbers_and_excluded():
    raw = b"a,b\n1,2\n3\n4,5,6\n7,8\n"

    parsed = parse_csv(raw, detect_format(raw))

    assert parsed.rows == [["1", "2"], ["7", "8"]]
    assert parsed.ragged_lines == [3, 4]


def test_blank_lines_are_skipped():
    raw = b"a,b\n1,2\n\n3,4\n\n"

    parsed = parse_csv(raw, detect_format(raw))

    assert parsed.rows == [["1", "2"], ["3", "4"]]
    assert parsed.ragged_lines == []


def test_values_are_stripped_of_surrounding_whitespace():
    raw = b"a , b\n 1 , x \n"

    parsed = parse_csv(raw, detect_format(raw))

    assert parsed.header == ["a", "b"]
    assert parsed.rows == [["1", "x"]]


@pytest.mark.parametrize("raw, message", [
    (b"", "empty"),
    (b"   \n\n", "empty"),
    (b"\x00\x01\x02\x89PNG\x00\x00", "binary"),
])
def test_rejects_unusable_files(raw, message):
    with pytest.raises(CsvFormatError, match=message):
        detect_format(raw)


def test_header_only_file_has_no_rows():
    raw = b"a,b,c\n"

    parsed = parse_csv(raw, detect_format(raw))

    assert parsed.header == ["a", "b", "c"]
    assert parsed.rows == []
