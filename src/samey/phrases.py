"""Repeated-phrase mining: which n-grams show up across many records?

Mode collapse rarely repeats whole outputs first — it repeats *phrases*
("as an ai language model", "in today's fast-paced world"). Ranking n-grams
by how many distinct records they appear in surfaces those attractors long
before duplicate clusters form.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import List, Sequence, Tuple

from samey.textnorm import ngrams


@dataclass(frozen=True)
class PhraseCount:
    """One repeated n-gram: text, total hits, and distinct records touched."""

    phrase: Tuple[str, ...]
    count: int  # total occurrences across the corpus
    records: int  # number of distinct records containing it

    @property
    def text(self) -> str:
        return " ".join(self.phrase)


def top_ngrams(
    token_lists: Sequence[Sequence[str]],
    n: int = 3,
    *,
    top: int = 20,
    min_records: int = 2,
) -> List[PhraseCount]:
    """Rank *n*-grams by record spread, then by total count.

    ``min_records`` filters out phrases that merely repeat inside a single
    long record — those indicate rambling, not collapse. Ties break
    alphabetically so output is stable.
    """
    if top < 1:
        raise ValueError(f"top must be >= 1, got {top}")
    if min_records < 1:
        raise ValueError(f"min_records must be >= 1, got {min_records}")
    totals: Counter = Counter()
    spread: Counter = Counter()
    for tokens in token_lists:
        grams = list(ngrams(tokens, n))
        totals.update(grams)
        spread.update(set(grams))
    ranked = [
        PhraseCount(phrase=g, count=totals[g], records=spread[g])
        for g in totals
        if spread[g] >= min_records
    ]
    ranked.sort(key=lambda p: (-p.records, -p.count, p.phrase))
    return ranked[:top]
