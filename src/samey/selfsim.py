"""Pairwise self-similarity: how much do records resemble *each other*?

The headline number is the mean Jaccard similarity over record pairs,
computed on token n-gram sets. Small corpora get the exact all-pairs answer;
large ones get a MinHash estimate over a deterministic sample of pairs, so
results are reproducible run-to-run with no wall-clock or RNG-state leakage.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Sequence, Tuple

from samey.textnorm import char_shingles, ngram_set

# All-pairs is O(N^2) set intersections; 400 records = 79 800 pairs, which is
# still instant. Beyond that we switch to MinHash signatures.
EXACT_PAIR_LIMIT = 400

# MinHash accuracy ~ 1/sqrt(k); 128 hashes gives a standard error around 0.09
# per pair, and averaging over thousands of sampled pairs shrinks it further.
SIGNATURE_SIZE = 128

# Cap on sampled pairs for the mean estimate on large corpora.
MAX_SAMPLED_PAIRS = 20000

_MERSENNE_PRIME = (1 << 61) - 1
_SEED = 0x53414D45  # "SAME"


def _hash_params(k: int = SIGNATURE_SIZE) -> List[Tuple[int, int]]:
    """Fixed (a, b) parameters for k universal hash functions.

    Seeded with a constant so signatures are identical across runs, machines,
    and Python versions (Mersenne Twister output is stable by spec).
    """
    rng = random.Random(_SEED)
    return [
        (rng.randrange(1, _MERSENNE_PRIME), rng.randrange(0, _MERSENNE_PRIME))
        for _ in range(k)
    ]


_PARAMS = _hash_params()


def _stable_hash(item: Tuple[str, ...]) -> int:
    """64-bit stable hash of one shingle (never Python's salted hash())."""
    digest = hashlib.blake2b("\x1f".join(item).encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big")


def minhash_signature(shingles: FrozenSet[Tuple[str, ...]]) -> Tuple[int, ...]:
    """MinHash signature of a shingle set; empty sets get an all-max sentinel."""
    if not shingles:
        return tuple([_MERSENNE_PRIME] * SIGNATURE_SIZE)
    base = [_stable_hash(s) for s in shingles]
    sig = []
    for a, b in _PARAMS:
        sig.append(min((a * h + b) % _MERSENNE_PRIME for h in base))
    return tuple(sig)


def signature_similarity(sig_a: Sequence[int], sig_b: Sequence[int]) -> float:
    """Estimated Jaccard: the fraction of signature slots that agree."""
    matches = sum(1 for x, y in zip(sig_a, sig_b) if x == y)
    return matches / len(sig_a)


def jaccard(a: FrozenSet, b: FrozenSet) -> float:
    """Exact Jaccard similarity; two empty sets count as identical (1.0)."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / (len(a) + len(b) - inter)


def record_shingles(
    token_lists: Sequence[Sequence[str]], texts: Sequence[str], n: int
) -> List[FrozenSet]:
    """Shingle set per record: token n-grams, char shingles as a fallback.

    Records with no word tokens at all (emoji runs, punctuation art) fall
    back to character 4-shingles so they still compare against each other.
    """
    out: List[FrozenSet] = []
    for tokens, text in zip(token_lists, texts):
        if tokens:
            out.append(ngram_set(tokens, n))
        else:
            out.append(char_shingles(text))
    return out


@dataclass(frozen=True)
class SelfSimilarity:
    """Mean/max pairwise similarity plus how the numbers were obtained."""

    mean: float
    max: float
    pairs: int
    method: str  # "exact" or "minhash"
    top_pairs: Tuple[Tuple[int, int, float], ...]


def self_similarity(
    token_lists: Sequence[Sequence[str]],
    texts: Sequence[str],
    *,
    n: int = 2,
    exact_limit: int = EXACT_PAIR_LIMIT,
    max_pairs: int = MAX_SAMPLED_PAIRS,
    top_k: int = 5,
) -> SelfSimilarity:
    """Mean pairwise Jaccard over record pairs, on token *n*-gram sets.

    Fewer than two records yields 0.0 by definition (there is nothing to be
    similar to). ``top_pairs`` lists the most similar pairs found, which is
    usually the fastest route to eyeballing what collapsed.
    """
    count = len(token_lists)
    if count < 2:
        return SelfSimilarity(mean=0.0, max=0.0, pairs=0, method="exact", top_pairs=())
    shingles = record_shingles(token_lists, texts, n)

    if count <= exact_limit:
        sims: List[Tuple[int, int, float]] = []
        for i in range(count):
            for j in range(i + 1, count):
                sims.append((i, j, jaccard(shingles[i], shingles[j])))
        method = "exact"
    else:
        sigs = [minhash_signature(s) for s in shingles]
        rng = random.Random(_SEED ^ count)  # deterministic per corpus size
        all_pairs = count * (count - 1) // 2
        sample = min(max_pairs, all_pairs)
        seen = set()
        sims = []
        while len(seen) < sample:
            i = rng.randrange(count)
            j = rng.randrange(count)
            if i == j:
                continue
            pair = (min(i, j), max(i, j))
            if pair in seen:
                continue
            seen.add(pair)
            sims.append((pair[0], pair[1], signature_similarity(sigs[pair[0]], sigs[pair[1]])))
        method = "minhash"

    values = [s for _, _, s in sims]
    mean = sum(values) / len(values)
    ranked = sorted(sims, key=lambda t: (-t[2], t[0], t[1]))[:top_k]
    return SelfSimilarity(
        mean=mean,
        max=max(values),
        pairs=len(sims),
        method=method,
        top_pairs=tuple(ranked),
    )


def to_dict(result: SelfSimilarity) -> Dict[str, object]:
    """JSON-friendly view used by the CLI report."""
    return {
        "mean": result.mean,
        "max": result.max,
        "pairs": result.pairs,
        "method": result.method,
        "top_pairs": [
            {"a": a, "b": b, "similarity": s} for a, b, s in result.top_pairs
        ],
    }
