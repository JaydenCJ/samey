"""Tokenization and normalization primitives: everything downstream trusts these."""

import pytest

from samey.textnorm import char_shingles, ngram_set, ngrams, normalize, tokenize


def test_tokenize_splits_on_punctuation_and_casefolds():
    assert tokenize("Hello, World! Hello.") == ["hello", "world", "hello"]
    assert tokenize("version 2 of 3") == ["version", "2", "of", "3"]
    assert tokenize("") == []


def test_tokenize_keeps_internal_apostrophes_as_one_token():
    # "don't" must not become ["don", "t"] or bigram metrics get noisy.
    assert tokenize("Don't panic") == ["don't", "panic"]


def test_tokenize_casefold_can_be_disabled():
    assert tokenize("Hello World", casefold=False) == ["Hello", "World"]


def test_tokenize_handles_cjk_text():
    # \w matches ideographs, so CJK text yields tokens instead of vanishing.
    tokens = tokenize("今日は良い天気です")
    assert tokens and all(tokens)


def test_normalize_collapses_whitespace_and_casefolds():
    assert normalize("  Hello\t\n  WORLD  ") == "hello world"
    assert normalize("Hello World", casefold=False) == "Hello World"


def test_normalize_nfkc_unifies_fullwidth_characters():
    # Full-width "ＡＢＣ" and ASCII "abc" are the same output in disguise.
    assert normalize("ＡＢＣ") == normalize("abc")


def test_ngrams_windows_and_short_sequences():
    assert list(ngrams(["a", "b", "c"], 2)) == [("a", "b"), ("b", "c")]
    # Sequences shorter than n yield nothing; callers handle the fallback.
    assert list(ngrams(["a", "b"], 3)) == []


def test_ngrams_rejects_nonpositive_n():
    with pytest.raises(ValueError):
        list(ngrams(["a"], 0))


def test_ngram_set_fallbacks_for_short_and_empty_records():
    # A 2-token record must still exist in trigram space.
    assert ngram_set(["hi", "there"], 3) == frozenset({("hi", "there")})
    assert ngram_set([], 3) == frozenset()


def test_char_shingles_window_and_short_text():
    assert char_shingles("abcde", 4) == frozenset({"abcd", "bcde"})
    assert char_shingles("ab", 4) == frozenset({"ab"})
