#!/usr/bin/env bash

set -Eeuo pipefail

ROUND="${1:-}"

if [[ ! "$ROUND" =~ ^[1-9][0-9]*$ ]]; then
  echo "Usage: $0 <round-number>" >&2
  exit 2
fi

SCRIPT_DIR="$(
  cd "$(dirname "${BASH_SOURCE[0]}")" \
  && pwd
)"

REPO_ROOT="$(
  cd "$SCRIPT_DIR/../.." \
  && pwd
)"

cd "$REPO_ROOT"

PERF_RESULT_ROOT="${PERF_RESULT_ROOT:-/mnt/wanping-performance/runs}"
PLAN="performance/jmeter/plans/shop-query.jmx"
EXTRACTOR="scripts/performance/extract_jmeter_metrics.py"

command -v jmeter >/dev/null
test -f "$PLAN"
test -f "$EXTRACTOR"

mountpoint -q /mnt/wanping-performance

ROOT_USAGE="$(
  df -P / \
  | awk 'NR == 2 {
      gsub("%", "", $5)
      print $5
    }'
)"

echo "ROOT_DISK_USAGE_PERCENT=$ROOT_USAGE"

if (( ROOT_USAGE >= 95 )); then
  echo "ROOT_DISK_GATE = FAILED" >&2
  exit 3
fi

if (( ROOT_USAGE >= 90 )); then
  echo "ROOT_DISK_GATE = WARNING"
else
  echo "ROOT_DISK_GATE = PASS"
fi

RUN_ID="$(date +%Y%m%d-%H%M%S)"

BASELINE_DIR="$PERF_RESULT_ROOT/baseline-shop-query-round${ROUND}-${RUN_ID}"

mkdir -p \
  "$BASELINE_DIR/warmup/tmp" \
  "$BASELINE_DIR/run/tmp"

echo "BASELINE_DIR=$BASELINE_DIR"

curl -fsS \
  'http://127.0.0.1:8082/jvm/status' \
  > "$BASELINE_DIR/jvm-status-before.json"

python3 - "$BASELINE_DIR/jvm-status-before.json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(
    Path(sys.argv[1]).read_text(
        encoding="utf-8"
    )
)["data"]

expected = {
    "cpuLoopRunning": False,
    "cpuRegexRunning": False,
    "memoryLeakChunks": 0,
    "deadlockActive": False,
    "threadExplosionActive": False,
    "fullGcAllocations": 0,
}

for key, expected_value in expected.items():
    actual = data.get(key)

    assert actual == expected_value, (
        f"{key}: expected={expected_value}, "
        f"actual={actual}"
    )

print("JVM_FAULT_GATE = PASS")
PY

record_environment() {
  local stage="$1"
  local output="$BASELINE_DIR/environment-${stage}.txt"

  {
    echo "ROUND=$ROUND"
    echo "STAGE=$stage"
    echo "TIME=$(date --iso-8601=seconds)"
    echo "TARGET=http://127.0.0.1:8082"
    echo "THREADS=20"
    echo "RAMP_UP_SECONDS=2"
    echo "LOOPS_PER_THREAD=20"
    echo "EXPECTED_SAMPLES=400"

    echo
    echo "=== ROOT DISK ==="
    df -P /

    echo
    echo "=== PERFORMANCE MOUNT ==="
    df -P /mnt/wanping-performance

    echo
    echo "=== LOAD ==="
    uptime

    echo
    echo "=== MEMORY ==="
    free -h
  } > "$output"
}

run_jmeter_phase() {
  local phase="$1"
  local threads="$2"
  local ramp_up="$3"
  local loops="$4"

  local output="$BASELINE_DIR/$phase"

  mkdir -p "$output/tmp"

  set +e

  JVM_ARGS="\
-Djava.io.tmpdir=$output/tmp \
-Xms256m \
-Xmx512m" \
  jmeter \
    -n \
    -t "$PLAN" \
    -Jprotocol=http \
    -Jhost=127.0.0.1 \
    -Jport=8082 \
    -Jthreads="$threads" \
    -Jramp_up="$ramp_up" \
    -Jloops="$loops" \
    -Jtype_id=1 \
    -Jcurrent=1 \
    -Jconnect_timeout_ms=3000 \
    -Jresponse_timeout_ms=10000 \
    -Jjmeter.save.saveservice.output_format=csv \
    -Jjmeter.save.saveservice.print_field_names=true \
    -l "$output/result.jtl" \
    -j "$output/jmeter.log" \
    2>&1 \
    | tee "$output/console.log"

  local exit_code="${PIPESTATUS[0]}"

  set -e

  echo "$exit_code" \
    > "$output/exit-code.txt"

  echo "${phase^^}_EXIT_CODE=$exit_code"

  if (( exit_code != 0 )); then
    echo "$phase JMeter execution failed" >&2
    exit "$exit_code"
  fi
}

check_jtl() {
  local path="$1"
  local expected="$2"
  local label="$3"

  python3 - "$path" "$expected" "$label" <<'PY'
import csv
import sys
from pathlib import Path

path = Path(sys.argv[1])
expected = int(sys.argv[2])
label = sys.argv[3]

with path.open(
    encoding="utf-8-sig",
    newline="",
) as file:
    rows = list(csv.DictReader(file))

errors = [
    row
    for row in rows
    if row["success"].strip().lower()
    != "true"
]

print(f"{label}_SAMPLE_COUNT =", len(rows))
print(f"{label}_ERROR_COUNT =", len(errors))

for row in errors[:5]:
    print(
        "FAILED_SAMPLE =",
        row.get("responseCode"),
        row.get("failureMessage"),
    )

assert len(rows) == expected, (
    f"expected={expected}, actual={len(rows)}"
)

assert not errors, (
    f"error_count={len(errors)}"
)

print(f"{label}_CHECK = PASS")
PY
}

record_environment "before"

run_jmeter_phase \
  warmup \
  5 \
  1 \
  4

check_jtl \
  "$BASELINE_DIR/warmup/result.jtl" \
  20 \
  WARMUP

sleep 3

run_jmeter_phase \
  run \
  20 \
  2 \
  20

check_jtl \
  "$BASELINE_DIR/run/result.jtl" \
  400 \
  BASELINE

python3 \
  "$EXTRACTOR" \
  --jtl "$BASELINE_DIR/run/result.jtl" \
  --output "$BASELINE_DIR/run/metrics.json" \
  --scenario shop-query \
  --run-type baseline \
  | tee "$BASELINE_DIR/run/metrics-console.log"

mkdir -p \
  performance/baselines/runs

cp \
  "$BASELINE_DIR/run/metrics.json" \
  "performance/baselines/runs/shop-query-round${ROUND}.json"

record_environment "after"

python3 - "$BASELINE_DIR/run/metrics.json" "$ROUND" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(
    Path(sys.argv[1]).read_text(
        encoding="utf-8"
    )
)

round_number = sys.argv[2]
metrics = data["metrics"]

print(f"ROUND = {round_number}")

for name in [
    "sample_count",
    "error_rate",
    "duration_seconds",
    "throughput_rps",
    "mean_ms",
    "median_ms",
    "p90_ms",
    "p95_ms",
    "p99_ms",
    "max_ms",
]:
    print(
        f"{name.upper()} =",
        metrics[name],
    )

assert metrics["sample_count"] == 400
assert metrics["error_count"] == 0

print(
    f"SHOP_BASELINE_ROUND{round_number}_CHECK = PASS"
)
PY

echo "BASELINE_RAW_DIR=$BASELINE_DIR"
