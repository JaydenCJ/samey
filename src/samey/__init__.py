"""samey — measure output diversity and mode collapse in generated text sets.

The public API mirrors the CLI: load records, compute diversity metrics
(distinct-n, self-similarity, duplicate clusters, compression redundancy),
and fold them into a single 0-100 sameness score.
"""

from samey.distinct import (
    DistinctResult,
    compression_redundancy,
    distinct_n,
    token_entropy,
    vocab_stats,
)
from samey.dupes import DupeCluster, find_duplicates
from samey.phrases import top_ngrams
from samey.reader import Record, ReaderError, load_records
from samey.report import ReportOptions, build_report, sameness_band, sameness_score
from samey.selfsim import jaccard, self_similarity
from samey.textnorm import ngrams, normalize, tokenize

__version__ = "0.1.0"

__all__ = [
    "DistinctResult",
    "DupeCluster",
    "Record",
    "ReaderError",
    "ReportOptions",
    "__version__",
    "build_report",
    "compression_redundancy",
    "distinct_n",
    "find_duplicates",
    "jaccard",
    "load_records",
    "ngrams",
    "normalize",
    "sameness_band",
    "sameness_score",
    "self_similarity",
    "token_entropy",
    "tokenize",
    "top_ngrams",
    "vocab_stats",
]
