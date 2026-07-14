"""Input loading: txt lines, JSONL fields, directories, stdin, and error paths."""

import json

import pytest

from samey.reader import ReaderError, load_records


def test_lines_format_one_record_per_nonempty_line(tmp_path):
    p = tmp_path / "out.txt"
    p.write_text("alpha\n\nbeta\n  \ngamma\n")
    records = load_records([str(p)])
    assert [r.text for r in records] == ["alpha", "beta", "gamma"]


def test_records_are_numbered_globally_across_files(tmp_path):
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("one\ntwo\n")
    b.write_text("three\n")
    records = load_records([str(a), str(b)])
    assert [r.index for r in records] == [0, 1, 2]
    assert records[2].source == str(b)


def test_jsonl_extracts_default_text_field_and_skips_blanks(tmp_path):
    p = tmp_path / "gen.jsonl"
    p.write_text('{"text": "hello"}\n\n{"text": "world"}\n')
    records = load_records([str(p)])
    assert [r.text for r in records] == ["hello", "world"]


def test_jsonl_custom_and_dotted_field(tmp_path):
    p = tmp_path / "gen.jsonl"
    p.write_text(json.dumps({"response": {"content": "nested value"}}) + "\n")
    records = load_records([str(p)], field="response.content")
    assert records[0].text == "nested value"


def test_ndjson_bare_string_lines_are_records(tmp_path):
    # .ndjson routes through the jsonl reader; bare strings need no field.
    p = tmp_path / "gen.ndjson"
    p.write_text('"just a string"\n')
    assert load_records([str(p)])[0].text == "just a string"


def test_jsonl_field_errors_report_line_numbers(tmp_path):
    p = tmp_path / "gen.jsonl"
    p.write_text('{"text": "ok"}\n{"output": "no text key"}\n')
    with pytest.raises(ReaderError, match=":2: field 'text' not found"):
        load_records([str(p)])
    p.write_text('{"text": 42}\n')
    with pytest.raises(ReaderError, match=":1: field 'text' is int, expected string"):
        load_records([str(p)])


def test_jsonl_invalid_json_reports_line_number(tmp_path):
    p = tmp_path / "gen.jsonl"
    p.write_text('{"text": "ok"}\nnot json at all\n')
    with pytest.raises(ReaderError, match=":2: invalid JSON"):
        load_records([str(p)])


def test_directory_each_file_is_one_record_hidden_skipped(tmp_path):
    d = tmp_path / "outputs"
    d.mkdir()
    (d / "b.txt").write_text("second file\nwith two lines")
    (d / "a.txt").write_text("first file")
    (d / ".hidden").write_text("secret")
    records = load_records([str(d)])
    # Sorted by path, whole file = one record, dotfiles ignored.
    assert records[0].text == "first file"
    assert "two lines" in records[1].text
    assert len(records) == 2


def test_files_format_forces_whole_file_records(tmp_path):
    p = tmp_path / "multi.txt"
    p.write_text("line one\nline two\n")
    records = load_records([str(p)], fmt="files")
    assert len(records) == 1
    assert "line two" in records[0].text


def test_stdin_dash_reads_lines(tmp_path, monkeypatch):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("from stdin\nsecond\n"))
    records = load_records(["-"])
    assert [r.text for r in records] == ["from stdin", "second"]
    assert records[0].source == "<stdin>"


def test_stdin_with_files_format_is_one_whole_record(monkeypatch):
    # Same semantics as --format files on a regular file: the whole
    # stream is one record — it must not fall through to the jsonl parser.
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("line one\nline two\n"))
    records = load_records(["-"], fmt="files")
    assert len(records) == 1
    assert "line two" in records[0].text


def test_bad_paths_and_formats_raise_reader_errors():
    with pytest.raises(ReaderError, match="input not found"):
        load_records(["/nonexistent/example.txt"])
    with pytest.raises(ReaderError, match="no input paths"):
        load_records([])
    with pytest.raises(ReaderError, match="unknown format"):
        load_records(["whatever.txt"], fmt="csv")


def test_directory_misuse_raises(tmp_path):
    d = tmp_path / "outputs"
    d.mkdir()
    with pytest.raises(ReaderError, match="contains no files"):
        load_records([str(d)])
    (d / "a.txt").write_text("x")
    with pytest.raises(ReaderError, match="is a directory"):
        load_records([str(d)], fmt="lines")


def test_undecodable_file_is_a_clean_error(tmp_path):
    p = tmp_path / "bin.txt"
    p.write_bytes(b"\xff\xfe\x00\x01binary")
    with pytest.raises(ReaderError, match="not decodable"):
        load_records([str(p)])
