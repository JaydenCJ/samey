# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-13

### Added

- `samey score`: full diversity report with pooled distinct-n (configurable
  sizes), mean/max pairwise self-similarity, duplicate clusters, token
  entropy, length statistics, compression redundancy, vocabulary stats, and
  a weighted 0-100 sameness score with verdict bands.
- Pipeline gates: `--max-sameness` and `--min-distinct-2` make `score` exit
  1 with a `GATE FAIL` line on stderr, so it drops straight into
  generation pipelines.
- `samey dupes`: exact duplicate groups (NFKC + casefold + whitespace
  normalization) and near-duplicate clusters (token trigram-shingle Jaccard,
  configurable threshold) merged with union-find; text previews or full
  JSON output.
- `samey ngrams`: repeated-phrase mining ranked by how many distinct records
  contain each n-gram — surfaces collapse phrases before whole records
  duplicate.
- `samey compare`: side-by-side diversity diff of two corpora with a
  more-diverse / more-same verdict per metric.
- Scale path: exact all-pairs Jaccard up to 400 records, then 128-hash
  MinHash signatures with LSH banding (32×4) and deterministic pair
  sampling — bit-for-bit reproducible on every run.
- Input formats: plain text (record per line), JSONL/NDJSON with dotted
  `--field` paths, directories (record per file), stdin via `-`; multiple
  inputs pool into one corpus with global record numbering.
- `--json` on every subcommand for machine-readable output.
- Metric definitions documented in `docs/metrics.md`; runnable corpora in
  `examples/`.
- 91 pytest tests and `scripts/smoke.sh`, an end-to-end CLI smoke run that
  prints `SMOKE OK`.

### Notes

- The repository ships no CI workflow; verification is local —
  `pip install -e '.[dev]' && pytest && bash scripts/smoke.sh`.

[0.1.0]: https://github.com/JaydenCJ/samey/releases/tag/v0.1.0
