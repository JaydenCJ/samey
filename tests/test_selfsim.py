"""Self-similarity: exact Jaccard, MinHash estimation, and determinism."""

import math

from samey.selfsim import (
    jaccard,
    minhash_signature,
    self_similarity,
    signature_similarity,
)
from samey.textnorm import tokenize


def _prep(texts):
    return [tokenize(t) for t in texts], list(texts)


def test_jaccard_values_across_overlap_spectrum():
    full = frozenset({("a",), ("b",)})
    assert jaccard(full, full) == 1.0
    assert jaccard(frozenset({("a",)}), frozenset({("b",)})) == 0.0
    a = frozenset({("x",), ("y",)})
    b = frozenset({("y",), ("z",)})
    assert math.isclose(jaccard(a, b), 1 / 3)
    # Two empty sets count as identical; one empty set shares nothing.
    assert jaccard(frozenset(), frozenset()) == 1.0
    assert jaccard(frozenset(), full) == 0.0


def test_self_similarity_of_copies_is_one():
    tokens, texts = _prep(["the cat sat on the mat"] * 4)
    result = self_similarity(tokens, texts)
    assert result.mean == 1.0
    assert result.max == 1.0
    assert result.pairs == 6


def test_self_similarity_orders_collapsed_above_diverse(diverse_texts, collapsed_texts):
    dt, _ = _prep(diverse_texts)
    ct, _ = _prep(collapsed_texts)
    low = self_similarity(dt, diverse_texts).mean
    high = self_similarity(ct, collapsed_texts).mean
    assert low < 0.05
    assert high > 0.5


def test_self_similarity_fewer_than_two_records_is_zero():
    tokens, texts = _prep(["only one record"])
    result = self_similarity(tokens, texts)
    assert result.mean == 0.0
    assert result.pairs == 0


def test_self_similarity_top_pairs_are_ranked_and_indexed():
    tokens, texts = _prep(
        [
            "alpha beta gamma delta",
            "alpha beta gamma delta",  # exact copy of 0
            "totally different words here now",
        ]
    )
    result = self_similarity(tokens, texts)
    top = result.top_pairs[0]
    assert (top[0], top[1]) == (0, 1)
    assert top[2] == 1.0


def test_self_similarity_records_without_tokens_use_char_fallback():
    # Pure-punctuation records still compare instead of crashing.
    tokens, texts = _prep([":) :) :)", ":) :) :)", "some real words in this one"])
    result = self_similarity(tokens, texts)
    assert result.max == 1.0


def test_minhash_signature_deterministic_and_exact_on_identity():
    shingles = frozenset({("a", "b"), ("b", "c"), ("c", "d")})
    assert minhash_signature(shingles) == minhash_signature(shingles)
    s = frozenset((f"tok{i}",) for i in range(30))
    assert signature_similarity(minhash_signature(s), minhash_signature(s)) == 1.0


def test_minhash_estimates_jaccard_within_tolerance():
    # 50%-overlap sets: estimate should land near 1/3 (Jaccard of the union).
    a = frozenset((f"tok{i}",) for i in range(100))
    b = frozenset((f"tok{i}",) for i in range(50, 150))
    est = signature_similarity(minhash_signature(a), minhash_signature(b))
    assert abs(est - 1 / 3) < 0.12


def test_large_corpus_switches_to_minhash_and_stays_deterministic():
    # 30 distinct templates x 20 copies = 600 records > EXACT_PAIR_LIMIT.
    texts = [
        f"template {i} with some shared filler words in the middle {i}"
        for i in range(30)
        for _ in range(20)
    ]
    tokens = [tokenize(t) for t in texts]
    first = self_similarity(tokens, texts, exact_limit=400)
    second = self_similarity(tokens, texts, exact_limit=400)
    assert first.method == "minhash"
    assert first.mean == second.mean  # bit-for-bit reproducible
    assert first.mean > 0.2  # heavy duplication must register


def test_exact_and_minhash_agree_on_the_same_corpus():
    texts = [f"record number {i} says something moderately unique {i * 7}" for i in range(50)]
    texts += ["a duplicated sentence appearing many times"] * 10
    tokens = [tokenize(t) for t in texts]
    exact = self_similarity(tokens, texts, exact_limit=1000)
    approx = self_similarity(tokens, texts, exact_limit=10)
    assert exact.method == "exact"
    assert approx.method == "minhash"
    assert abs(exact.mean - approx.mean) < 0.05
