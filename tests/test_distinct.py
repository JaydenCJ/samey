"""Distinct-n, entropy, length stats, and compression redundancy."""

import math

from samey.distinct import (
    compression_redundancy,
    distinct_n,
    length_stats,
    token_entropy,
    vocab_stats,
)


def test_distinct_1_all_unique_tokens_gives_ratio_one():
    result = distinct_n([["a", "b"], ["c", "d"]], 1)
    assert result.unique == 4
    assert result.total == 4
    assert result.ratio == 1.0


def test_distinct_1_identical_records_pool_to_low_ratio():
    # Pooled distinct-n is the point: copies crater the ratio.
    result = distinct_n([["same", "words"]] * 5, 1)
    assert result.unique == 2
    assert result.total == 10
    assert result.ratio == 0.2


def test_distinct_2_counts_bigrams_across_records():
    result = distinct_n([["a", "b", "c"], ["a", "b", "c"]], 2)
    assert result.unique == 2  # (a,b), (b,c)
    assert result.total == 4


def test_distinct_n_degenerate_inputs():
    # Empty means "no evidence of repetition", not "fully repetitive" ...
    assert distinct_n([], 2).ratio == 1.0
    # ... and records shorter than n contribute nothing.
    assert distinct_n([["one"]], 3).total == 0


def test_vocab_stats_type_token_ratio_and_hapax():
    stats = vocab_stats([["a", "a", "b", "c"]])
    assert stats["tokens"] == 4.0
    assert stats["types"] == 3.0
    assert stats["type_token_ratio"] == 0.75
    # b and c appear once: 2 hapax out of 3 types.
    assert math.isclose(stats["hapax_ratio"], 2 / 3)


def test_token_entropy_uniform_distribution_is_fully_normalized():
    result = token_entropy([["a", "b", "c", "d"]])
    assert math.isclose(result["bits"], 2.0)
    assert math.isclose(result["normalized"], 1.0)


def test_token_entropy_degenerate_and_skewed_distributions():
    single = token_entropy([["same", "same", "same"]])
    assert single["bits"] == 0.0 and single["normalized"] == 0.0
    skewed = token_entropy([["a"] * 9 + ["b"]])
    assert 0.0 < skewed["normalized"] < 1.0


def test_compression_redundancy_separates_diverse_from_collapsed(
    diverse_texts, collapsed_texts
):
    # Unrelated prose shares character statistics, so the floor is ~0.3-0.45
    # rather than 0 — but it must sit clearly below collapsed-corpus levels.
    diverse = compression_redundancy(diverse_texts)
    collapsed = compression_redundancy(collapsed_texts)
    assert diverse < 0.5 < collapsed
    copies = ["the same sentence repeated over and over again in this corpus"] * 20
    assert compression_redundancy(copies) > 0.7


def test_compression_redundancy_edge_cases():
    assert compression_redundancy(["only one"]) == 0.0
    # Pathological length skew must still clamp into [0, 1].
    assert 0.0 <= compression_redundancy(["x" * 1000, "x" * 1000, "y" * 3]) <= 1.0


def test_length_stats_mean_min_max_stdev():
    stats = length_stats([["a"], ["a", "b"], ["a", "b", "c"]])
    assert stats["mean"] == 2.0
    assert stats["min"] == 1.0
    assert stats["max"] == 3.0
    assert math.isclose(stats["stdev"], math.sqrt(2 / 3))
    assert length_stats([]) == {"mean": 0.0, "min": 0.0, "max": 0.0, "stdev": 0.0}
