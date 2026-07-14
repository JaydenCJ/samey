#!/usr/bin/env bash
# Smoke test for samey: score a diverse and a collapsed corpus, check the
# gate exit codes, duplicate clusters, repeated phrases, corpus comparison,
# and JSON output. Self-contained: pure stdlib, no network, idempotent.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

# Zero runtime dependencies: running from src/ needs no install.
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/samey-smoke.XXXXXX")"
trap 'rm -rf "$WORKDIR"' EXIT

fail() { echo "SMOKE FAIL: $1" >&2; exit 1; }

echo "[smoke] python: $("$PYTHON" --version 2>&1)"

# 1. A diverse corpus lands in the diverse band and passes a tight gate.
diverse_out="$("$PYTHON" -m samey score "$ROOT/examples/diverse.txt" --max-sameness 25)" \
  || fail "diverse corpus should pass --max-sameness 25"
echo "$diverse_out" | sed 's/^/[score] /'
grep -q "(diverse)" <<<"$diverse_out" || fail "diverse corpus not labelled diverse"

# 2. A collapsed corpus scores high and trips the same gate with exit 1.
set +e
collapsed_out="$("$PYTHON" -m samey score "$ROOT/examples/collapsed.jsonl" --max-sameness 25 2>"$WORKDIR/err")"
rc=$?
set -e
[ "$rc" -eq 1 ] || fail "collapsed corpus should exit 1 on the gate, got $rc"
grep -q "GATE FAIL" "$WORKDIR/err" || fail "gate failure not reported on stderr"
grep -q "mode collapse likely" <<<"$collapsed_out" \
  || fail "collapsed corpus not labelled 'mode collapse likely'"

# 3. JSON output parses and carries the expected top-level keys.
"$PYTHON" -m samey score "$ROOT/examples/collapsed.jsonl" --json >"$WORKDIR/report.json"
"$PYTHON" - "$WORKDIR/report.json" <<'EOF' || fail "JSON report invalid or incomplete"
import json, sys
report = json.load(open(sys.argv[1]))
assert report["records"] == 12
assert {"distinct", "self_similarity", "duplicates", "sameness"} <= set(report)
assert report["sameness"]["score"] > 50
EOF

# 4. dupes finds the planted 8-record template cluster.
dupes_out="$("$PYTHON" -m samey dupes "$ROOT/examples/collapsed.jsonl")"
echo "$dupes_out" | sed 's/^/[dupes] /'
grep -q "cluster 0: 8 records" <<<"$dupes_out" || fail "expected an 8-record cluster"
grep -q "7 redundant records" <<<"$dupes_out" || fail "expected 7 redundant records"

# 5. ngrams surfaces the collapse phrase.
ngrams_out="$("$PYTHON" -m samey ngrams "$ROOT/examples/collapsed.jsonl" -n 3 --top 5)"
grep -q "a product description" <<<"$ngrams_out" || fail "collapse phrase not surfaced"

# 6. compare flags the collapsed corpus as a diversity regression.
compare_out="$("$PYTHON" -m samey compare "$ROOT/examples/diverse.txt" "$ROOT/examples/collapsed.jsonl")"
echo "$compare_out" | sed 's/^/[compare] /'
grep -q "more same" <<<"$compare_out" || fail "compare did not flag the regression"

# 7. stdin works, and unreadable input exits 2 with a clean error.
stdin_out="$(printf 'twin line\ntwin line\nother line\n' | "$PYTHON" -m samey dupes -)"
grep -q "cluster 0: 2 records" <<<"$stdin_out" || fail "stdin dupes failed"
set +e
"$PYTHON" -m samey score "$WORKDIR/does-not-exist.txt" 2>"$WORKDIR/err2"
rc=$?
set -e
[ "$rc" -eq 2 ] || fail "missing input should exit 2, got $rc"
grep -q "input not found" "$WORKDIR/err2" || fail "missing-input error not reported"

# 8. --version agrees with the package version.
version_out="$("$PYTHON" -m samey --version)"
pkg_version="$("$PYTHON" -c 'import samey; print(samey.__version__)')"
[ "$version_out" = "samey $pkg_version" ] \
  || fail "--version mismatch: '$version_out' vs package '$pkg_version'"

echo "SMOKE OK"
