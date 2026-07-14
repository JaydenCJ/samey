"""Report assembly, the sameness score, bands, rendering, and compare rows."""

import json
import math

import pytest

from conftest import make_records
from samey.report import (
    ReportOptions,
    build_report,
    compare_reports,
    render_compare,
    render_report,
    sameness_band,
    sameness_score,
)


def test_sameness_score_bounds():
    assert sameness_score(distinct2=1.0, selfsim_mean=0.0, dupe_fraction=0.0) == 0.0
    assert sameness_score(distinct2=0.0, selfsim_mean=1.0, dupe_fraction=1.0) == 100.0


def test_sameness_score_weights_sum_correctly():
    # Each component alone contributes exactly its weight x 100.
    assert math.isclose(sameness_score(0.0, 0.0, 0.0), 35.0)
    assert math.isclose(sameness_score(1.0, 1.0, 0.0), 35.0)
    assert math.isclose(sameness_score(1.0, 0.0, 1.0), 30.0)


def test_sameness_band_boundaries():
    assert sameness_band(0.0) == "diverse"
    assert sameness_band(25.0) == "diverse"
    assert sameness_band(25.1) == "repetitive"
    assert sameness_band(50.1) == "mode collapse likely"
    assert sameness_band(75.1) == "collapsed"
    assert sameness_band(100.0) == "collapsed"


def test_build_report_diverse_corpus_scores_low(diverse_records):
    report = build_report(diverse_records)
    assert report["records"] == 10
    assert report["sameness"]["score"] < 25
    assert report["sameness"]["band"] == "diverse"
    assert report["duplicates"]["cluster_count"] == 0


def test_build_report_collapsed_corpus_scores_high(collapsed_records, diverse_records):
    collapsed = build_report(collapsed_records)
    assert collapsed["sameness"]["score"] > 60
    assert collapsed["duplicates"]["duplicate_fraction"] > 0.5
    # The two corpora must be separated by a wide, unambiguous gap.
    diverse = build_report(diverse_records)
    assert collapsed["sameness"]["score"] > diverse["sameness"]["score"] + 30


def test_build_report_empty_corpus_raises():
    with pytest.raises(ValueError, match="zero records"):
        build_report([])


def test_build_report_single_record_is_fully_diverse():
    report = build_report(make_records(["just one output"]))
    assert report["self_similarity"]["mean"] == 0.0
    assert report["duplicates"]["cluster_count"] == 0
    assert report["sameness"]["score"] < 1.0


def test_build_report_respects_custom_ngram_sizes(diverse_records):
    report = build_report(diverse_records, ReportOptions(ngram_sizes=(1, 4)))
    assert set(report["distinct"]) == {"distinct_1", "distinct_4"}
    # distinct-2 is still computed internally for the score.
    assert 0.0 <= report["sameness"]["components"]["distinct_2_deficit"] <= 1.0


def test_build_report_threshold_flows_into_duplicates(collapsed_records):
    strict = build_report(collapsed_records, ReportOptions(dupe_threshold=0.99))
    loose = build_report(collapsed_records, ReportOptions(dupe_threshold=0.4))
    assert (
        loose["duplicates"]["redundant_records"]
        >= strict["duplicates"]["redundant_records"]
    )
    assert strict["duplicates"]["threshold"] == 0.99


def test_build_report_is_deterministic_and_json_serializable(collapsed_records):
    first = build_report(collapsed_records)
    second = build_report(collapsed_records)
    assert first == second
    json.dumps(first)  # must not raise


def test_render_report_shows_headline_numbers_and_bar(collapsed_records, diverse_records):
    report = build_report(collapsed_records)
    text = render_report(report, label="demo")
    assert "samey score — demo (10 records)" in text
    assert "distinct-1" in text and "distinct-2" in text and "distinct-3" in text
    assert "/ 100" in text
    assert report["sameness"]["band"] in text
    # A low score renders a mostly-empty bar.
    low = render_report(build_report(diverse_records))
    bar_line = next(line for line in low.splitlines() if "sameness" in line)
    assert bar_line.count("░") > bar_line.count("█")


def test_render_report_uses_singular_forms_for_counts_of_one():
    # Two half-identical records -> 1 pair, 1 cluster, 1 redundant record.
    report = build_report(make_records(["copy me exactly", "copy me exactly"]))
    text = render_report(report, label="tiny")
    assert "(1 pair, exact)" in text
    assert "1 cluster, 1 redundant record " in text
    assert "1 clusters" not in text and "1 pairs" not in text


def test_compare_reports_flags_diversity_regression(diverse_records, collapsed_records):
    rows = compare_reports(build_report(diverse_records), build_report(collapsed_records))
    by_name = {r.name: r for r in rows}
    assert by_name["sameness score"].delta > 0
    assert by_name["distinct-2"].delta < 0
    rendered = render_compare(rows, "old", "new")
    assert "more same" in rendered
    assert "sameness score" in rendered
    # Comparing a report against itself renders "=" verdicts everywhere.
    same = build_report(diverse_records)
    unchanged = render_compare(compare_reports(same, same), "a", "b")
    assert "=" in unchanged
    assert "more same" not in unchanged and "more diverse" not in unchanged
