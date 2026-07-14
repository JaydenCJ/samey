"""Text normalization, tokenization, and n-gram extraction.

Everything downstream (distinct-n, self-similarity, duplicate detection)
depends on these primitives being deterministic and locale-independent, so
they use plain ``str`` operations and a fixed regex — no locale, no ICU.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterator, List, Sequence, Tuple

# A token is a run of word characters, optionally joined by an internal
# apostrophe ("don't" stays one token). \w with re.UNICODE covers CJK
# ideographs, kana, and accented letters, so multilingual outputs tokenize
# sensibly without a language-specific segmenter.
_TOKEN_RE = re.compile(r"\w+(?:'\w+)*", re.UNICODE)

_WS_RE = re.compile(r"\s+")


def normalize(text: str, *, casefold: bool = True, collapse_ws: bool = True) -> str:
    """Return a canonical form of *text* used for exact-duplicate hashing.

    Applies Unicode NFKC (so full-width and half-width variants of the same
    character compare equal), optional casefolding, and optional whitespace
    collapsing. The result is stripped.
    """
    out = unicodedata.normalize("NFKC", text)
    if casefold:
        out = out.casefold()
    if collapse_ws:
        out = _WS_RE.sub(" ", out)
    return out.strip()


def tokenize(text: str, *, casefold: bool = True) -> List[str]:
    """Split *text* into word tokens.

    Punctuation is dropped; the token stream is what every token-level metric
    in samey operates on. Casefolding is on by default because diversity
    metrics should not reward "The"/"the" as two distinct types.
    """
    if casefold:
        text = text.casefold()
    return _TOKEN_RE.findall(unicodedata.normalize("NFKC", text))


def ngrams(tokens: Sequence[str], n: int) -> Iterator[Tuple[str, ...]]:
    """Yield contiguous *n*-grams over *tokens* as tuples.

    Yields nothing when the sequence is shorter than *n*; callers decide how
    to handle short records (see :func:`ngram_set`).
    """
    if n < 1:
        raise ValueError(f"n must be >= 1, got {n}")
    for i in range(len(tokens) - n + 1):
        yield tuple(tokens[i : i + n])


def ngram_set(tokens: Sequence[str], n: int) -> frozenset:
    """Return the set of *n*-grams for one record.

    Records shorter than *n* tokens fall back to their full token tuple as a
    single shingle, so a two-word record still participates in trigram-based
    similarity instead of silently vanishing from the comparison.
    """
    grams = frozenset(ngrams(tokens, n))
    if not grams and tokens:
        return frozenset({tuple(tokens)})
    return grams


def char_shingles(text: str, k: int = 4) -> frozenset:
    """Return the set of *k*-character shingles of normalized *text*.

    Used as a fallback signal for records with almost no word tokens (emoji
    strings, code fragments). Shorter texts yield their whole string.
    """
    norm = normalize(text)
    if not norm:
        return frozenset()
    if len(norm) <= k:
        return frozenset({norm})
    return frozenset(norm[i : i + k] for i in range(len(norm) - k + 1))
