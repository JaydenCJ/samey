# Contributing to samey

Thanks for your interest in contributing. Issues, discussions, and pull
requests are all welcome.

## Getting started

You need Python 3.9 or newer; nothing else.

```bash
git clone https://github.com/JaydenCJ/samey
cd samey
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
bash scripts/smoke.sh
```

`scripts/smoke.sh` runs the real CLI end-to-end against the corpora in
`examples/` — scoring, gates, duplicate clusters, phrase mining, comparison,
JSON output — and must print `SMOKE OK`.

## Before you open a pull request

1. Format touched files consistently with the surrounding code (PEP 8,
   4-space indents; formatting is enforced in review).
2. Keep the tree lint-clean (`python3 -m compileall src` must be silent;
   ruff defaults if you have it).
3. `pytest` — the full suite must pass.
4. `bash scripts/smoke.sh` — must print `SMOKE OK`.
5. Add tests for behavior changes; keep logic in pure, unit-testable
   modules and out of `cli.py`.

## Ground rules

- **No new runtime dependencies.** The package is standard-library only;
  that is the headline feature. Test-only dependencies belong in the `dev`
  extra and need justification in the PR.
- **Determinism is a contract.** Same corpus in, same numbers out — across
  runs, machines, and Python versions. No wall-clock, no unseeded RNG, no
  `hash()` on strings.
- **Metric changes need docs.** Anything that changes a reported number
  must update `docs/metrics.md` in the same pull request.
- No network calls, no telemetry. samey reads local files and prints.
- Code comments and doc comments are written in English.
- **Keep the three READMEs aligned.** `README.md`, `README.zh.md`, and
  `README.ja.md` are line-for-line translations; update all three when you
  change one (English is authoritative).

## Reporting bugs

Please include `samey --version` output, the exact command line, and a
minimal corpus that reproduces the issue (a few lines of text or JSONL is
usually enough — the metrics are deterministic, so small repros transfer).

## Security

Please do not open public issues for suspected vulnerabilities; use
GitHub's private vulnerability reporting on the repository instead.
