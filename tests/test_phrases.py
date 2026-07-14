"""Repeated-phrase mining (the ngrams subcommand's engine)."""

import pytest

from samey.phrases import top_ngrams
from samey.textnorm import tokenize


def _prep(texts):
    return [tokenize(t) for t in texts]


def test_phrase_shared_across_records_ranks_first():
    tokens = _prep(
        [
            "in conclusion the answer is yes",
            "in conclusion the answer is no",
            "in conclusion we cannot say",
            "a sentence with no shared phrases at all",
        ]
    )
    phrases = top_ngrams(tokens, 2)
    assert phrases[0].text == "in conclusion"
    assert phrases[0].records == 3
    assert phrases[0].count == 3


def test_min_records_filters_single_record_repetition():
    # A phrase repeated 5 times inside ONE record is rambling, not collapse.
    tokens = _prep(["again and again and again and again and again", "other text here"])
    phrases = top_ngrams(tokens, 2, min_records=2)
    assert all(p.records >= 2 for p in phrases)
    assert not any(p.text == "again and" for p in phrases)


def test_min_records_one_admits_intra_record_repeats():
    tokens = _prep(["la la la la"])
    phrases = top_ngrams(tokens, 2, min_records=1)
    assert phrases[0].text == "la la"
    assert phrases[0].count == 3
    assert phrases[0].records == 1


def test_top_limits_rows_and_ties_break_alphabetically():
    tokens = _prep(["z z", "z z", "a a", "a a"])
    phrases = top_ngrams(tokens, 2)
    assert [p.text for p in phrases] == ["a a", "z z"]
    assert len(top_ngrams(_prep(["a b c d e f", "a b c d e f"]), 2, top=3)) == 3


def test_count_tracks_total_occurrences_across_corpus():
    tokens = _prep(["go go go", "go go"])
    phrases = top_ngrams(tokens, 2, min_records=2)
    assert phrases[0].text == "go go"
    assert phrases[0].count == 3  # two in record 0, one in record 1
    assert phrases[0].records == 2


def test_no_repeats_yields_empty_list(diverse_texts):
    tokens = _prep(diverse_texts)
    assert top_ngrams(tokens, 4) == []


def test_invalid_arguments_raise():
    with pytest.raises(ValueError):
        top_ngrams([], 2, top=0)
    with pytest.raises(ValueError):
        top_ngrams([], 2, min_records=0)
