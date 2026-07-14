"""End-to-end CLI behavior: subcommands, JSON output, gates, and exit codes."""

import json

import pytest

from samey import __version__
from samey.cli import main


@pytest.fixture
def diverse_file(tmp_path, diverse_texts):
    p = tmp_path / "diverse.txt"
    p.write_text("\n".join(diverse_texts) + "\n")
    return str(p)


@pytest.fixture
def collapsed_file(tmp_path, collapsed_texts):
    p = tmp_path / "collapsed.txt"
    p.write_text("\n".join(collapsed_texts) + "\n")
    return str(p)


def test_no_command_prints_help_and_exits_2(capsys):
    assert main([]) == 2
    assert "score" in capsys.readouterr().out


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"samey {__version__}"


def test_score_text_output_has_score_band_and_label(capsys, collapsed_file):
    assert main(["score", collapsed_file, "--label", "nightly-batch"]) == 0
    out = capsys.readouterr().out
    assert "sameness" in out
    assert "/ 100" in out
    assert "nightly-batch" in out


def test_score_json_output_is_valid_and_complete(capsys, collapsed_file):
    assert main(["score", collapsed_file, "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["records"] == 10
    assert {"distinct", "self_similarity", "duplicates", "sameness"} <= set(report)


def test_score_gate_max_sameness(capsys, collapsed_file, diverse_file):
    assert main(["score", collapsed_file, "--max-sameness", "40"]) == 1
    assert "GATE FAIL" in capsys.readouterr().err
    assert main(["score", diverse_file, "--max-sameness", "40"]) == 0
    assert "GATE FAIL" not in capsys.readouterr().err


def test_score_gate_min_distinct_2(capsys, collapsed_file):
    assert main(["score", collapsed_file, "--min-distinct-2", "0.9"]) == 1
    assert "distinct-2" in capsys.readouterr().err


def test_score_custom_ngram_sizes(capsys, diverse_file):
    assert main(["score", diverse_file, "--ngram", "1,4", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert set(report["distinct"]) == {"distinct_1", "distinct_4"}


def test_score_bad_option_values_are_usage_errors(capsys, collapsed_file):
    assert main(["score", collapsed_file, "--ngram", "1,x"]) == 2
    assert "error" in capsys.readouterr().err
    assert main(["score", collapsed_file, "--threshold", "2.0"]) == 2
    assert "threshold" in capsys.readouterr().err


def test_score_unreadable_inputs_are_usage_errors(capsys, tmp_path):
    assert main(["score", "/nonexistent/example.txt"]) == 2
    assert "input not found" in capsys.readouterr().err
    p = tmp_path / "empty.txt"
    p.write_text("\n\n")
    assert main(["score", str(p)]) == 2
    assert "no records" in capsys.readouterr().err


def test_score_jsonl_field_and_multi_input_pooling(
    capsys, tmp_path, collapsed_texts, diverse_file, collapsed_file
):
    p = tmp_path / "gen.jsonl"
    p.write_text("\n".join(json.dumps({"output": t}) for t in collapsed_texts) + "\n")
    assert main(["score", str(p), "--field", "output", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["records"] == 10
    # Multiple paths pool into one corpus with global record numbering.
    assert main(["score", diverse_file, collapsed_file, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["records"] == 20


def test_dupes_lists_clusters_with_truncated_previews(capsys, collapsed_file):
    assert main(["dupes", collapsed_file, "--preview", "30"]) == 0
    out = capsys.readouterr().out
    assert "cluster 0" in out
    assert "#0" in out
    assert "redundant records" in out
    assert "…" in out  # 30-char preview truncates the template sentence


def test_dupes_json_includes_member_texts(capsys, collapsed_file):
    assert main(["dupes", collapsed_file, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["clusters"]
    first = payload["clusters"][0]
    assert len(first["texts"]) == len(first["members"])


def test_dupes_none_found_message(capsys, diverse_file):
    assert main(["dupes", diverse_file]) == 0
    assert "no duplicate clusters" in capsys.readouterr().out


def test_ngrams_table_and_json_show_top_phrases(capsys, collapsed_file):
    assert main(["ngrams", collapsed_file, "-n", "3", "--top", "5"]) == 0
    out = capsys.readouterr().out
    assert "as a helpful" in out
    assert "records" in out and "count" in out
    assert main(["ngrams", collapsed_file, "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows and rows[0]["records"] >= 2


def test_ngrams_edge_cases(capsys, diverse_file):
    assert main(["ngrams", diverse_file, "-n", "5"]) == 0
    assert "no 5-grams repeated" in capsys.readouterr().out
    assert main(["ngrams", diverse_file, "--top", "0"]) == 2


def test_compare_flags_regression_in_text_and_json(capsys, diverse_file, collapsed_file):
    assert main(["compare", diverse_file, collapsed_file]) == 0
    out = capsys.readouterr().out
    assert "sameness score" in out
    assert "more same" in out
    assert main(["compare", diverse_file, collapsed_file, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["a"]["records"] == 10
    names = [m["name"] for m in payload["metrics"]]
    assert "sameness score" in names and "distinct-2" in names


def test_stdin_and_directory_input_sources(
    capsys, monkeypatch, tmp_path, collapsed_texts, diverse_texts
):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("\n".join(collapsed_texts)))
    assert main(["score", "-", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["records"] == 10
    d = tmp_path / "outputs"
    d.mkdir()
    for i, t in enumerate(diverse_texts[:4]):
        (d / f"gen_{i}.txt").write_text(t)
    assert main(["score", str(d), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["records"] == 4
