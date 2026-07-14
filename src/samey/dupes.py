"""Duplicate detection: exact groups and near-duplicate clusters.

Exact duplicates are grouped by a hash of the NFKC-casefolded, whitespace-
collapsed text. Near-duplicates are clustered by Jaccard similarity over
token trigram shingles: all-pairs for small corpora, MinHash LSH banding for
large ones, with union-find to merge overlapping pairs into clusters.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Sequence, Tuple

from samey.selfsim import (
    SIGNATURE_SIZE,
    jaccard,
    minhash_signature,
    record_shingles,
)
from samey.textnorm import normalize

# LSH banding: 32 bands x 4 rows over the 128-slot signature. Candidate
# probability at Jaccard s is 1-(1-s^4)^32 — ~0.97 at s=0.7, ~0.24 at s=0.4 —
# a good net for the default 0.7 threshold (every candidate is re-verified).
LSH_BANDS = 32
LSH_ROWS = SIGNATURE_SIZE // LSH_BANDS

# All-pairs verification limit; above this, LSH prunes the candidate set.
EXACT_PAIR_LIMIT = 400


@dataclass(frozen=True)
class DupeCluster:
    """A cluster of records judged to be the same output.

    ``exact`` is True when every member normalizes to identical text;
    ``members`` are record indices, representative first (lowest index).
    """

    members: Tuple[int, ...]
    exact: bool
    similarity: float  # min pairwise similarity within the cluster (1.0 exact)

    @property
    def representative(self) -> int:
        return self.members[0]

    @property
    def redundant(self) -> int:
        """How many records the cluster wastes (all but the representative)."""
        return len(self.members) - 1


class _UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            # Deterministic: smaller root wins, so representatives are stable.
            if ra < rb:
                self.parent[rb] = ra
            else:
                self.parent[ra] = rb


def exact_key(text: str) -> str:
    """Stable hash key for exact-duplicate grouping (normalization applied)."""
    norm = normalize(text)
    return hashlib.blake2b(norm.encode("utf-8"), digest_size=16).hexdigest()


def find_duplicates(
    token_lists: Sequence[Sequence[str]],
    texts: Sequence[str],
    *,
    threshold: float = 0.7,
    shingle_n: int = 3,
    exact_pair_limit: int = EXACT_PAIR_LIMIT,
) -> List[DupeCluster]:
    """Cluster records whose shingle Jaccard is >= *threshold*.

    Exact duplicates (identical after normalization) are always clustered,
    whatever the threshold. Clusters come back sorted by size (largest
    first), then by representative index, so output order is deterministic.
    """
    if not 0.0 < threshold <= 1.0:
        raise ValueError(f"threshold must be in (0, 1], got {threshold}")
    count = len(texts)
    if count < 2:
        return []

    uf = _UnionFind(count)
    pair_sims: Dict[Tuple[int, int], float] = {}

    # Pass 1: exact duplicates by normalized hash. Free and always right.
    by_key: Dict[str, List[int]] = defaultdict(list)
    for i, text in enumerate(texts):
        by_key[exact_key(text)].append(i)
    exact_groups = {tuple(g) for g in by_key.values() if len(g) > 1}
    for group in exact_groups:
        for other in group[1:]:
            uf.union(group[0], other)
            pair_sims[(group[0], other)] = 1.0

    # Pass 2: near-duplicates over token shingles.
    shingles = record_shingles(token_lists, texts, shingle_n)
    for i, j in _candidate_pairs(shingles, count, exact_pair_limit):
        sim = jaccard(shingles[i], shingles[j])
        if sim >= threshold:
            uf.union(i, j)
            pair_sims[(i, j)] = sim

    return _collect(uf, pair_sims, texts, count)


def _candidate_pairs(
    shingles: Sequence[FrozenSet], count: int, exact_pair_limit: int
):
    """Yield pairs worth verifying: all pairs when small, LSH bands when big."""
    if count <= exact_pair_limit:
        for i in range(count):
            for j in range(i + 1, count):
                yield (i, j)
        return
    sigs = [minhash_signature(s) for s in shingles]
    seen = set()
    for band in range(LSH_BANDS):
        buckets: Dict[Tuple[int, ...], List[int]] = defaultdict(list)
        lo = band * LSH_ROWS
        for idx, sig in enumerate(sigs):
            buckets[sig[lo : lo + LSH_ROWS]].append(idx)
        for members in buckets.values():
            if len(members) < 2:
                continue
            for a in range(len(members)):
                for b in range(a + 1, len(members)):
                    pair = (members[a], members[b])
                    if pair not in seen:
                        seen.add(pair)
                        yield pair


def _collect(
    uf: _UnionFind,
    pair_sims: Dict[Tuple[int, int], float],
    texts: Sequence[str],
    count: int,
) -> List[DupeCluster]:
    groups: Dict[int, List[int]] = defaultdict(list)
    for i in range(count):
        groups[uf.find(i)].append(i)

    clusters: List[DupeCluster] = []
    for members in groups.values():
        if len(members) < 2:
            continue
        members.sort()
        keys = {exact_key(texts[m]) for m in members}
        exact = len(keys) == 1
        if exact:
            min_sim = 1.0
        else:
            sims = [
                s
                for (a, b), s in pair_sims.items()
                if a in members and b in members
            ]
            min_sim = min(sims) if sims else 0.0
        clusters.append(
            DupeCluster(members=tuple(members), exact=exact, similarity=min_sim)
        )
    clusters.sort(key=lambda c: (-len(c.members), c.members[0]))
    return clusters


def duplicate_fraction(clusters: Sequence[DupeCluster], total: int) -> float:
    """Share of the corpus that is redundant: sum of (cluster size - 1) / N.

    This is the "money wasted" number — the fraction of generations you paid
    for that added nothing a smaller set would not have.
    """
    if total == 0:
        return 0.0
    return sum(c.redundant for c in clusters) / total
