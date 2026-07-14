"""Duplicate clustering: exact groups, near-dup thresholds, LSH path, union-find."""

import pytest

from samey.dupes import duplicate_fraction, exact_key, find_duplicates
from samey.textnorm import tokenize


def _prep(texts):
    return [tokenize(t) for t in texts], list(texts)


def test_exact_key_normalizes_case_whitespace_and_width():
    assert exact_key("Hello  World") == exact_key("hello world")
    assert exact_key("ＯＫ") == exact_key("ok")
    assert exact_key("alpha") != exact_key("beta")


def test_exact_duplicates_cluster_regardless_of_threshold():
    tokens, texts = _prep(["copy of this", "copy of this", "something else entirely"])
    clusters = find_duplicates(tokens, texts, threshold=1.0)
    assert len(clusters) == 1
    assert clusters[0].members == (0, 1)
    assert clusters[0].exact is True
    assert clusters[0].similarity == 1.0


def test_near_duplicates_cluster_at_default_threshold():
    tokens, texts = _prep(
        [
            "an entirely unrelated sentence about cooking pasta well",
            "the quick brown fox jumps over the lazy dog today",
            "the quick brown fox jumps over the lazy dog tonight",
        ]
    )
    clusters = find_duplicates(tokens, texts)
    assert len(clusters) == 1
    assert clusters[0].members == (1, 2)
    assert clusters[0].representative == 1  # lowest index leads
    assert clusters[0].exact is False
    assert 0.7 <= clusters[0].similarity < 1.0
    # Raising the threshold above their similarity splits the pair again.
    assert find_duplicates(tokens, texts, threshold=0.95) == []


def test_transitive_merging_via_union_find():
    # A~B and B~C should form one {A,B,C} cluster even if A~C is weaker.
    tokens, texts = _prep(
        [
            "alpha beta gamma delta epsilon zeta eta theta",
            "alpha beta gamma delta epsilon zeta eta iota",
            "alpha beta gamma delta epsilon zeta mu iota",
        ]
    )
    clusters = find_duplicates(tokens, texts, threshold=0.5)
    assert len(clusters) == 1
    assert clusters[0].members == (0, 1, 2)


def test_clusters_sorted_largest_first():
    tokens, texts = _prep(
        ["pair one text", "pair one text", "triple text", "triple text", "triple text"]
    )
    clusters = find_duplicates(tokens, texts)
    assert [len(c.members) for c in clusters] == [3, 2]


def test_clean_corpora_have_no_clusters(diverse_texts):
    tokens, texts = _prep(diverse_texts)
    assert find_duplicates(tokens, texts) == []
    solo_tokens, solo_texts = _prep(["alone"])
    assert find_duplicates(solo_tokens, solo_texts) == []


def test_invalid_threshold_raises():
    tokens, texts = _prep(["a b c", "a b c"])
    with pytest.raises(ValueError, match="threshold"):
        find_duplicates(tokens, texts, threshold=0.0)
    with pytest.raises(ValueError, match="threshold"):
        find_duplicates(tokens, texts, threshold=1.5)


def test_duplicate_fraction_counts_redundant_records():
    tokens, texts = _prep(["x y z"] * 4 + ["completely different words here"])
    clusters = find_duplicates(tokens, texts)
    # 4 copies -> 3 redundant out of 5 records.
    assert duplicate_fraction(clusters, 5) == 0.6
    assert duplicate_fraction([], 0) == 0.0


def test_lsh_path_finds_planted_duplicates_deterministically():
    # 600 records forces the LSH candidate path (limit 400); the planted
    # copies must still be found without all-pairs comparison.
    texts = [f"unique sentence number {i} talking about topic {i * 13}" for i in range(590)]
    texts += ["this exact sentence was planted ten times to be found"] * 10
    tokens = [tokenize(t) for t in texts]
    clusters = find_duplicates(tokens, texts)
    planted = [c for c in clusters if len(c.members) == 10]
    assert planted and planted[0].exact is True
    assert planted[0].members == tuple(range(590, 600))
    # Bit-for-bit reproducible: same corpus in, same clusters out.
    again = find_duplicates(tokens, texts)
    assert [c.members for c in again] == [c.members for c in clusters]


def test_short_records_cluster_via_fallback_shingles():
    # Two-token records are shorter than the 3-gram shingle; the full-tuple
    # fallback keeps them comparable.
    tokens, texts = _prep(["ok thanks", "ok thanks", "nope bye"])
    clusters = find_duplicates(tokens, texts)
    assert clusters[0].members == (0, 1)
