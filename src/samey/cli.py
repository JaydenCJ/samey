"""Command-line interface: score, dupes, ngrams, compare.

Exit codes: 0 success, 1 a --max-sameness / --min-distinct-2 gate failed,
2 bad usage or unreadable input. That split makes ``samey score`` drop
straight into a data-pipeline gate without wrapper scripts.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional, Sequence

from samey import __version__
from samey.phrases import top_ngrams
from samey.reader import ReaderError, load_records
from samey.report import (
    ReportOptions,
    build_report,
    compare_reports,
    render_compare,
    render_dupes,
    render_report,
)
from samey.textnorm import tokenize

EXIT_OK = 0
EXIT_GATE = 1
EXIT_USAGE = 2

PROG = "samey"


def _add_input_args(parser: argparse.ArgumentParser, nargs: str = "+") -> None:
    parser.add_argument("paths", nargs=nargs, help="input files, directories, or - for stdin")
    parser.add_argument(
        "--format",
        choices=("auto", "lines", "jsonl", "files"),
        default="auto",
        help="how to split inputs into records (default: auto)",
    )
    parser.add_argument(
        "--field",
        default="text",
        help="JSON field holding the text in jsonl inputs; dotted paths allowed (default: text)",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Measure output diversity and mode collapse in generated text sets.",
    )
    parser.add_argument("--version", action="version", version=f"{PROG} {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="command")

    p_score = sub.add_parser(
        "score", help="full diversity report with a 0-100 sameness score"
    )
    _add_input_args(p_score)
    p_score.add_argument(
        "--ngram",
        default="1,2,3",
        help="comma-separated distinct-n sizes to report (default: 1,2,3)",
    )
    p_score.add_argument(
        "--threshold",
        type=float,
        default=0.7,
        help="near-duplicate Jaccard threshold in (0,1] (default: 0.7)",
    )
    p_score.add_argument(
        "--max-sameness",
        type=float,
        default=None,
        metavar="SCORE",
        help="gate: exit 1 if the sameness score exceeds SCORE",
    )
    p_score.add_argument(
        "--min-distinct-2",
        type=float,
        default=None,
        metavar="RATIO",
        help="gate: exit 1 if distinct-2 falls below RATIO",
    )
    p_score.add_argument("--label", default=None, help="corpus label shown in the header")

    p_dupes = sub.add_parser("dupes", help="list exact and near-duplicate clusters")
    _add_input_args(p_dupes)
    p_dupes.add_argument(
        "--threshold",
        type=float,
        default=0.7,
        help="near-duplicate Jaccard threshold in (0,1] (default: 0.7)",
    )
    p_dupes.add_argument(
        "--preview",
        type=int,
        default=60,
        help="characters of each record to show (default: 60)",
    )

    p_ngrams = sub.add_parser(
        "ngrams", help="most repeated n-grams across records (collapse phrases)"
    )
    _add_input_args(p_ngrams)
    p_ngrams.add_argument("-n", type=int, default=3, help="n-gram size (default: 3)")
    p_ngrams.add_argument("--top", type=int, default=20, help="rows to show (default: 20)")
    p_ngrams.add_argument(
        "--min-records",
        type=int,
        default=2,
        help="only phrases appearing in at least this many records (default: 2)",
    )

    p_compare = sub.add_parser(
        "compare", help="compare the diversity of two corpora side by side"
    )
    p_compare.add_argument("path_a", help="baseline corpus")
    p_compare.add_argument("path_b", help="candidate corpus")
    p_compare.add_argument(
        "--format",
        choices=("auto", "lines", "jsonl", "files"),
        default="auto",
        help="how to split inputs into records (default: auto)",
    )
    p_compare.add_argument(
        "--field",
        default="text",
        help="JSON field holding the text in jsonl inputs; dotted paths allowed (default: text)",
    )
    p_compare.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    return parser


def _parse_ngram_sizes(raw: str) -> List[int]:
    try:
        sizes = [int(part) for part in raw.split(",") if part.strip()]
    except ValueError:
        raise ReaderError(f"--ngram expects comma-separated integers, got {raw!r}") from None
    if not sizes or any(n < 1 for n in sizes):
        raise ReaderError(f"--ngram sizes must be positive integers, got {raw!r}")
    return sizes


def _load(args: argparse.Namespace, paths: Sequence[str]):
    records = load_records(paths, fmt=args.format, field=args.field)
    if not records:
        raise ReaderError("inputs contained no records")
    return records


def _cmd_score(args: argparse.Namespace) -> int:
    records = _load(args, args.paths)
    options = ReportOptions(
        ngram_sizes=tuple(_parse_ngram_sizes(args.ngram)),
        dupe_threshold=args.threshold,
    )
    report = build_report(records, options)
    label = args.label or ", ".join(args.paths)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_report(report, label=label))

    failures: List[str] = []
    score = report["sameness"]["score"]
    if args.max_sameness is not None and score > args.max_sameness:
        failures.append(f"sameness {score:.1f} exceeds --max-sameness {args.max_sameness}")
    if args.min_distinct_2 is not None:
        d2 = report["distinct"].get("distinct_2")
        ratio = d2["ratio"] if d2 else 1.0 - report["sameness"]["components"]["distinct_2_deficit"]
        if ratio < args.min_distinct_2:
            failures.append(f"distinct-2 {ratio:.3f} below --min-distinct-2 {args.min_distinct_2}")
    for failure in failures:
        print(f"GATE FAIL: {failure}", file=sys.stderr)
    return EXIT_GATE if failures else EXIT_OK


def _cmd_dupes(args: argparse.Namespace) -> int:
    records = _load(args, args.paths)
    options = ReportOptions(dupe_threshold=args.threshold)
    report = build_report(records, options)
    clusters = report["duplicates"]["clusters"]
    if args.json:
        payload = {
            "records": len(records),
            "threshold": args.threshold,
            "clusters": [
                {
                    **cluster,
                    "texts": [records[m].text for m in cluster["members"]],
                }
                for cluster in clusters
            ],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_dupes(clusters, records, preview=args.preview))
    return EXIT_OK


def _cmd_ngrams(args: argparse.Namespace) -> int:
    records = _load(args, args.paths)
    token_lists = [tokenize(r.text) for r in records]
    try:
        phrases = top_ngrams(
            token_lists, args.n, top=args.top, min_records=args.min_records
        )
    except ValueError as exc:
        raise ReaderError(str(exc)) from None
    if args.json:
        print(
            json.dumps(
                [
                    {"phrase": p.text, "count": p.count, "records": p.records}
                    for p in phrases
                ],
                indent=2,
                sort_keys=True,
            )
        )
        return EXIT_OK
    if not phrases:
        unit = "record" if args.min_records == 1 else "records"
        print(f"no {args.n}-grams repeated across >= {args.min_records} {unit}")
        return EXIT_OK
    width = max(len("phrase"), max(len(p.text) for p in phrases))
    print(f"{'phrase':<{width}}  records  count")
    for p in phrases:
        print(f"{p.text:<{width}}  {p.records:>7}  {p.count:>5}")
    return EXIT_OK


def _cmd_compare(args: argparse.Namespace) -> int:
    records_a = _load(args, [args.path_a])
    records_b = _load(args, [args.path_b])
    report_a = build_report(records_a)
    report_b = build_report(records_b)
    rows = compare_reports(report_a, report_b)
    if args.json:
        print(
            json.dumps(
                {
                    "a": {"path": args.path_a, "records": len(records_a)},
                    "b": {"path": args.path_b, "records": len(records_b)},
                    "metrics": [
                        {"name": r.name, "a": r.a, "b": r.b, "delta": r.delta}
                        for r in rows
                    ],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(render_compare(rows, args.path_a, args.path_b))
    return EXIT_OK


_COMMANDS = {
    "score": _cmd_score,
    "dupes": _cmd_dupes,
    "ngrams": _cmd_ngrams,
    "compare": _cmd_compare,
}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return EXIT_USAGE
    try:
        return _COMMANDS[args.command](args)
    except (ReaderError, ValueError) as exc:
        print(f"{PROG}: error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except BrokenPipeError:
        return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
