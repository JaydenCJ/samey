"""Corpus-level lexical diversity: distinct-n, entropy, compression redundancy.

These are the cheap, order-independent signals. Distinct-n is the classic
generation-diversity metric (unique n-grams / total n-grams); token entropy
captures how flat the vocabulary distribution is; compression redundancy
measures cross-record repetition that token metrics can miss (templated
sentences with one word swapped compress extremely well together).
"""

from __future__ import annotations

import math
import zlib
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Sequence

from samey.textnorm import ngrams


@dataclass(frozen=True)
class DistinctResult:
    """Distinct-n outcome: ``ratio`` is unique/total, 1.0 when total is 0."""

    n: int
    unique: int
    total: int

    @property
    def ratio(self) -> float:
        if self.total == 0:
            return 1.0
        return self.unique / self.total


def distinct_n(token_lists: Sequence[Sequence[str]], n: int) -> DistinctResult:
    """Compute distinct-n across all records pooled together.

    Pooling matters: per-record distinct-n stays high even when every record
    is a copy of the same sentence. Pooled distinct-n is what actually drops
    under mode collapse.
    """
    seen = set()
    total = 0
    for tokens in token_lists:
        for gram in ngrams(tokens, n):
            seen.add(gram)
            total += 1
    return DistinctResult(n=n, unique=len(seen), total=total)


def vocab_stats(token_lists: Sequence[Sequence[str]]) -> Dict[str, float]:
    """Return corpus vocabulary statistics.

    ``type_token_ratio`` is distinct-1 by another name; ``hapax_ratio`` (share
    of words appearing exactly once) drops sharply in template-heavy output.
    """
    counts: Counter = Counter()
    for tokens in token_lists:
        counts.update(tokens)
    total = sum(counts.values())
    types = len(counts)
    hapax = sum(1 for c in counts.values() if c == 1)
    return {
        "tokens": float(total),
        "types": float(types),
        "type_token_ratio": types / total if total else 1.0,
        "hapax_ratio": hapax / types if types else 0.0,
    }


def token_entropy(token_lists: Sequence[Sequence[str]]) -> Dict[str, float]:
    """Shannon entropy of the unigram distribution, in bits.

    ``normalized`` divides by log2(vocabulary size), giving 1.0 for a
    perfectly flat distribution and approaching 0.0 when a handful of tokens
    dominate. A single-type corpus has entropy 0 and normalized entropy 0.
    """
    counts: Counter = Counter()
    for tokens in token_lists:
        counts.update(tokens)
    total = sum(counts.values())
    if total == 0 or len(counts) <= 1:
        return {"bits": 0.0, "normalized": 0.0 if len(counts) <= 1 else 1.0}
    bits = 0.0
    for c in counts.values():
        p = c / total
        bits -= p * math.log2(p)
    return {"bits": bits, "normalized": bits / math.log2(len(counts))}


def compression_redundancy(texts: Sequence[str]) -> float:
    """Cross-record redundancy from zlib, in [0, 1].

    Compares compressing the whole corpus at once against compressing each
    record on its own::

        redundancy = 1 - size(z(concat)) / sum(size(z(record)))

    When records repeat each other, the concatenated stream compresses far
    better than the records do alone and the score climbs toward 1. This
    catches "same template, one slot changed" collapse that distinct-1
    misses. Note the floor is not 0: unrelated prose in one language still
    shares character statistics, so diverse corpora typically land around
    0.3-0.45 — read the number comparatively, not absolutely.
    """
    texts = [t for t in texts if t]
    if len(texts) < 2:
        return 0.0
    individual = sum(len(zlib.compress(t.encode("utf-8"), 9)) for t in texts)
    joint = len(zlib.compress("\n".join(texts).encode("utf-8"), 9))
    if individual == 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - joint / individual))


def length_stats(token_lists: Sequence[Sequence[str]]) -> Dict[str, float]:
    """Record-length distribution (in tokens): mean, min, max, and stdev.

    Near-zero length variance across hundreds of generations is itself a
    collapse smell, so the report surfaces it alongside lexical metrics.
    """
    lengths: List[int] = [len(t) for t in token_lists]
    if not lengths:
        return {"mean": 0.0, "min": 0.0, "max": 0.0, "stdev": 0.0}
    mean = sum(lengths) / len(lengths)
    var = sum((x - mean) ** 2 for x in lengths) / len(lengths)
    return {
        "mean": mean,
        "min": float(min(lengths)),
        "max": float(max(lengths)),
        "stdev": math.sqrt(var),
    }
