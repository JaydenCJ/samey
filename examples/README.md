# samey examples

Two tiny corpora with opposite diversity profiles, useful for trying every
subcommand without generating anything:

- `diverse.txt` — 12 unrelated sentences, one per line. Scores in the
  **diverse** band (sameness < 1).
- `collapsed.jsonl` — 12 product descriptions where one template dominates.
  Scores in the **mode collapse likely** band (sameness ≈ 67), with one
  8-record near-duplicate cluster.

Run from the repository root (no install needed thanks to zero dependencies):

```bash
export PYTHONPATH=src

# Full report with the 0-100 sameness score
python3 -m samey score examples/diverse.txt
python3 -m samey score examples/collapsed.jsonl

# Fail a pipeline when sameness crosses a budget (exit code 1)
python3 -m samey score examples/collapsed.jsonl --max-sameness 40

# Inspect what actually collapsed
python3 -m samey dupes examples/collapsed.jsonl
python3 -m samey ngrams examples/collapsed.jsonl -n 3 --top 5

# Did the new sampling config help? Compare two corpora
python3 -m samey compare examples/diverse.txt examples/collapsed.jsonl
```

`collapsed.jsonl` stores records as `{"id": ..., "text": ...}`; samey reads
the `text` field by default (override with `--field`). `scripts/smoke.sh`
runs all of the commands above end-to-end and asserts on their output.
