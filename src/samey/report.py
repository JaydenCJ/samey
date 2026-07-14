"""Fold the individual metrics into one report and one sameness score.

The sameness score is a weighted blend of three complementary signals::

    sameness = 100 * (0.35 * (1 - distinct-2)
                    + 0.35 * mean pairwise self-similarity
                    + 0.30 * duplicate fraction)

Rationale: distinct-2 reacts to phrase-level repetition, self-similarity to
whole-record resemblance, and the duplicate fraction to outright wasted
generations. Each alone is gameable; together they are hard to fool. The
full derivation lives in docs/metrics.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from samey import distinct as _distinct
from samey import dupes as _dupes
from samey import selfsim as _selfsim
from samey.reader import Record
from samey.textnorm import tokenize

WEIGHT_DISTINCT = 0.35
WEIGHT_SELFSIM = 0.35
WEIGHT_DUPES = 0.30

BANDS = (
    (25.0, "diverse"),
    (50.0, "repetitive"),
    (75.0, "mode collapse likely"),
    (100.0, "collapsed"),
)


@dataclass(frozen=True)
class ReportOptions:
    """Knobs shared by the CLI and the library entry point."""

    ngram_sizes: Sequence[int] = (1, 2, 3)
    selfsim_n: int = 2
    dupe_threshold: float = 0.7
    dupe_shingle_n: int = 3


def sameness_score(
    distinct2: float, selfsim_mean: float, dupe_fraction: float
) -> float:
    """Blend the three components into a 0-100 score (higher = more same)."""
    raw = (
        WEIGHT_DISTINCT * (1.0 - distinct2)
        + WEIGHT_SELFSIM * selfsim_mean
        + WEIGHT_DUPES * dupe_fraction
    )
    return max(0.0, min(100.0, 100.0 * raw))


def sameness_band(score: float) -> str:
    """Human-readable verdict band for a score."""
    for upper, label in BANDS:
        if score <= upper:
            return label
    return BANDS[-1][1]


def build_report(records: Sequence[Record], options: Optional[ReportOptions] = None) -> Dict:
    """Compute every metric for *records* and return a JSON-ready dict.

    Raises ``ValueError`` on an empty corpus: a report over nothing would
    have to invent numbers, and silent zeros hide broken pipelines.
    """
    if not records:
        raise ValueError("cannot build a report over zero records")
    opts = options or ReportOptions()
    texts = [r.text for r in records]
    token_lists = [tokenize(t) for t in texts]

    distinct = {
        f"distinct_{n}": _asdict_distinct(_distinct.distinct_n(token_lists, n))
        for n in opts.ngram_sizes
    }
    selfsim = _selfsim.self_similarity(token_lists, texts, n=opts.selfsim_n)
    clusters = _dupes.find_duplicates(
        token_lists,
        texts,
        threshold=opts.dupe_threshold,
        shingle_n=opts.dupe_shingle_n,
    )
    dupe_fraction = _dupes.duplicate_fraction(clusters, len(records))

    distinct2 = _lookup_distinct2(distinct, token_lists)
    score = sameness_score(distinct2, selfsim.mean, dupe_fraction)

    return {
        "records": len(records),
        "distinct": distinct,
        "vocabulary": _distinct.vocab_stats(token_lists),
        "entropy": _distinct.token_entropy(token_lists),
        "length": _distinct.length_stats(token_lists),
        "compression_redundancy": _distinct.compression_redundancy(texts),
        "self_similarity": _selfsim.to_dict(selfsim),
        "duplicates": {
            "threshold": opts.dupe_threshold,
            "clusters": [
                {
                    "members": list(c.members),
                    "exact": c.exact,
                    "similarity": c.similarity,
                    "redundant": c.redundant,
                }
                for c in clusters
            ],
            "cluster_count": len(clusters),
            "redundant_records": sum(c.redundant for c in clusters),
            "duplicate_fraction": dupe_fraction,
        },
        "sameness": {
            "score": score,
            "band": sameness_band(score),
            "components": {
                "distinct_2_deficit": 1.0 - distinct2,
                "self_similarity_mean": selfsim.mean,
                "duplicate_fraction": dupe_fraction,
            },
            "weights": {
                "distinct_2_deficit": WEIGHT_DISTINCT,
                "self_similarity_mean": WEIGHT_SELFSIM,
                "duplicate_fraction": WEIGHT_DUPES,
            },
        },
    }


def _asdict_distinct(result: _distinct.DistinctResult) -> Dict:
    return {"unique": result.unique, "total": result.total, "ratio": result.ratio}


def _lookup_distinct2(distinct: Dict, token_lists: Sequence[Sequence[str]]) -> float:
    """Distinct-2 for the score, computed even if 2 was not in --ngram."""
    if "distinct_2" in distinct:
        return distinct["distinct_2"]["ratio"]
    return _distinct.distinct_n(token_lists, 2).ratio


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

BAR_WIDTH = 24


def _bar(fraction: float, width: int = BAR_WIDTH) -> str:
    filled = round(max(0.0, min(1.0, fraction)) * width)
    return "█" * filled + "░" * (width - filled)


def _count(n: int, noun: str) -> str:
    """``1 cluster`` / ``2 clusters`` — no '1 clusters' in any output."""
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def render_report(report: Dict, *, label: str = "corpus") -> str:
    """Terminal rendering of a report dict produced by :func:`build_report`."""
    lines: List[str] = []
    same = report["sameness"]
    lines.append(f"samey score — {label} ({_count(report['records'], 'record')})")
    lines.append("")
    lines.append(
        f"  sameness   {_bar(same['score'] / 100)}  {same['score']:5.1f} / 100  ({same['band']})"
    )
    lines.append("")
    lines.append("  distinct-n            unique / total    ratio")
    for key in sorted(report["distinct"], key=lambda k: int(k.rsplit("_", 1)[1])):
        d = report["distinct"][key]
        n = key.rsplit("_", 1)[1]
        lines.append(
            f"    distinct-{n}   {d['unique']:>10} / {d['total']:<8} {d['ratio']:6.3f}"
        )
    sim = report["self_similarity"]
    lines.append("")
    lines.append(
        f"  self-similarity  mean {sim['mean']:.3f}  max {sim['max']:.3f}"
        f"  ({_count(sim['pairs'], 'pair')}, {sim['method']})"
    )
    dup = report["duplicates"]
    lines.append(
        f"  duplicates       {_count(dup['cluster_count'], 'cluster')},"
        f" {_count(dup['redundant_records'], 'redundant record')}"
        f" ({dup['duplicate_fraction']:.1%} of corpus)"
    )
    lines.append(
        f"  entropy          {report['entropy']['bits']:.2f} bits"
        f" (normalized {report['entropy']['normalized']:.3f})"
    )
    lines.append(
        f"  compression      {report['compression_redundancy']:.1%} cross-record redundancy"
    )
    vocab = report["vocabulary"]
    lines.append(
        f"  vocabulary       {int(vocab['types'])} types / {int(vocab['tokens'])} tokens"
        f"  (hapax {vocab['hapax_ratio']:.1%})"
    )
    return "\n".join(lines)


def render_dupes(
    report_clusters: Sequence[Dict], records: Sequence[Record], *, preview: int = 60
) -> str:
    """Terminal rendering for the ``dupes`` subcommand."""
    if not report_clusters:
        return "no duplicate clusters found"
    lines: List[str] = []
    for i, cluster in enumerate(report_clusters):
        kind = "exact" if cluster["exact"] else f"near (≥{cluster['similarity']:.2f})"
        lines.append(
            f"cluster {i}: {_count(len(cluster['members']), 'record')}, {kind}"
        )
        for m in cluster["members"]:
            text = records[m].text.strip().replace("\n", " ")
            if len(text) > preview:
                text = text[: preview - 1] + "…"
            lines.append(f"    #{m:<5} {text}")
    total = sum(c["redundant"] for c in report_clusters)
    lines.append(
        f"{_count(len(report_clusters), 'cluster')}, {_count(total, 'redundant record')}"
    )
    return "\n".join(lines)


@dataclass
class CompareRow:
    name: str
    a: float
    b: float
    better: str = field(default="lower")  # which direction is more diverse

    @property
    def delta(self) -> float:
        return self.b - self.a


def compare_reports(report_a: Dict, report_b: Dict) -> List[CompareRow]:
    """Rows for the ``compare`` subcommand, one per headline metric."""
    return [
        CompareRow("sameness score", report_a["sameness"]["score"], report_b["sameness"]["score"]),
        CompareRow(
            "distinct-2",
            _ratio(report_a, 2),
            _ratio(report_b, 2),
            better="higher",
        ),
        CompareRow(
            "self-similarity mean",
            report_a["self_similarity"]["mean"],
            report_b["self_similarity"]["mean"],
        ),
        CompareRow(
            "duplicate fraction",
            report_a["duplicates"]["duplicate_fraction"],
            report_b["duplicates"]["duplicate_fraction"],
        ),
        CompareRow(
            "entropy (normalized)",
            report_a["entropy"]["normalized"],
            report_b["entropy"]["normalized"],
            better="higher",
        ),
    ]


def _ratio(report: Dict, n: int) -> float:
    entry = report["distinct"].get(f"distinct_{n}")
    return entry["ratio"] if entry else 0.0


def render_compare(rows: Sequence[CompareRow], label_a: str, label_b: str) -> str:
    """Two-column comparison with a diversity verdict per row."""
    width = max(len(r.name) for r in rows)
    la = max(len(label_a), len(label_b), 8)
    lines = [f"{'metric':<{width}}  {label_a:>{la}}  {label_b:>{la}}  {'delta':>8}"]
    for r in rows:
        if abs(r.delta) < 1e-9:
            verdict = "="
        else:
            improved = (r.delta < 0) == (r.better == "lower")
            verdict = "more diverse" if improved else "more same"
        lines.append(
            f"{r.name:<{width}}  {r.a:>{la}.3f}  {r.b:>{la}.3f}  {r.delta:>+8.3f}  {verdict}"
        )
    return "\n".join(lines)
