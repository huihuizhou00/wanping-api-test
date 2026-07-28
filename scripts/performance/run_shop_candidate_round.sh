#!/usr/bin/env bash

set -Eeuo pipefail

ROUND="${1:-}"

if [[ ! "$ROUND" =~ ^[1-9][0-9]*$ ]]; then
  echo "Usage: $0 <round-number>" >&2
  exit 2
fi

SCRIPT_DIR="$(
  cd "$(dirname "${BASH_SOURCE[0]}")" &&
  pwd
)"

REPO_ROOT="$(
  cd "$SCRIPT_DIR/../.." &&
  pwd
)"

cd "$REPO_ROOT"

PERF_RESULT_ROOT="${PERF_RESULT_ROOT:-/mnt/wanping-performance/runs}"
JMETER_BIN="${JMETER_BIN:-/home/zoey/tools/jmeter/bin/jmeter}"

PLAN="performance/jmeter/plans/shop-query.jmx"
EXTRACTOR="scripts/performance/extract_jmeter_metrics.py"
CANDIDATE_RUN_ROOT="performance/candidates/runs"

EXPECTED_WARMUP_SAMPLES=20
EXPECTED_RUN_SAMPLES=400

if [[ ! -x "$JMETER_BIN" ]]; then
  echo "JMETER_BIN_CHECK = FAILED: $JMETER_BIN" >&2
  exit 3
fi

if [[ ! -f "$PLAN" ]]; then
  echo "JMETER_PLAN_CHECK = FAILED: $PLAN" >&2
  exit 4
fi

if [[ ! -f "$EXTRACTOR" ]]; then
  echo "METRICS_EXTRACTOR_CHECK = FAILED: $EXTRACTOR" >&2
  exit 5
fi

if ! mountpoint -q /mnt/wanping-performance; then
  echo "PERFORMANCE_MOUNT_CHECK = FAILED" >&2
  exit 6
fi

if [[ ! -w /mnt/wanping-performance ]]; then
  echo "PERFORMANCE_MOUNT_WRITABLE = FAILED" >&2
  exit 7
fi

echo "PERFORMANCE_MOUNT_CHECK = PASS"

ROOT_USAGE="$(
  df -P / |
  awk 'NR == 2 {
    gsub("%", "", $5)
    print $5
  }'
)"

echo "ROOT_DISK_USAGE_PERCENT=$ROOT_USAGE"

if (( ROOT_USAGE >= 95 )); then
  echo "ROOT_DISK_GATE = FAILED" >&2
  exit 8
elif (( ROOT_USAGE >= 90 )); then
  echo "ROOT_DISK_GATE = WARNING"
else
  echo "ROOT_DISK_GATE = PASS"
fi

RUN_ID="$(date +%Y%m%d-%H%M%S)"

CANDIDATE_DIR="$PERF_RESULT_ROOT/candidate-shop-query-round${ROUND}-${RUN_ID}"

mkdir -p \
  "$CANDIDATE_DIR/warmup/tmp" \
  "$CANDIDATE_DIR/run/tmp" \
  "$CANDIDATE_RUN_ROOT"

echo "CANDIDATE_DIR=$CANDIDATE_DIR"

curl -fsS \
  "http://127.0.0.1:8082/shop/of/type?typeId=1&current=1" \
  > "$CANDIDATE_DIR/shop-health.json"

echo "SHOP_HEALTH_CHECK = PASS"

curl -fsS \
  "http://127.0.0.1:8082/jvm/status" \
  > "$CANDIDATE_DIR/jvm-status-before.json"

python3 - "$CANDIDATE_DIR/jvm-status-before.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])

data = json.loads(
    path.read_text(encoding="utf-8")
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

    if actual != expected_value:
        raise AssertionError(
            f"{key}: expected={expected_value}, actual={actual}"
        )

print("JVM_FAULT_GATE = PASS")
PY

record_environment() {
  local stage="$1"
  local output="$CANDIDATE_DIR/environment-${stage}.txt"

  {
    echo "RUN_TYPE=candidate"
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

  local output="$CANDIDATE_DIR/$phase"

  mkdir -p "$output/tmp"

  set +e

  JVM_ARGS="\
-Djava.io.tmpdir=$output/tmp \
-Xms256m \
-Xmx512m" \
  "$JMETER_BIN" \
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
    2>&1 |
    tee "$output/console.log"

  local exit_code="${PIPESTATUS[0]}"

  set -e

  echo "$exit_code" > "$output/exit-code.txt"
  echo "${phase^^}_EXIT_CODE=$exit_code"

  if (( exit_code != 0 )); then
    echo "${phase^^}_JMETER_CHECK = FAILED" >&2
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
    if row["success"].strip().lower() != "true"
]

print(f"{label}_SAMPLE_COUNT =", len(rows))
print(f"{label}_SUCCESS_COUNT =", len(rows) - len(errors))
print(f"{label}_ERROR_COUNT =", len(errors))

for row in errors[:5]:
    print(
        "FAILED_SAMPLE =",
        {
            "label": row.get("label"),
            "responseCode": row.get("responseCode"),
            "responseMessage": row.get("responseMessage"),
            "failureMessage": row.get("failureMessage"),
        },
    )

if len(rows) != expected:
    raise AssertionError(
        f"{label}: expected={expected}, actual={len(rows)}"
    )

if errors:
    raise AssertionError(
        f"{label}: error_count={len(errors)}"
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
  "$CANDIDATE_DIR/warmup/result.jtl" \
  "$EXPECTED_WARMUP_SAMPLES" \
  WARMUP

sleep 3

run_jmeter_phase \
  run \
  20 \
  2 \
  20

check_jtl \
  "$CANDIDATE_DIR/run/result.jtl" \
  "$EXPECTED_RUN_SAMPLES" \
  CANDIDATE

python3 \
  "$EXTRACTOR" \
  --jtl "$CANDIDATE_DIR/run/result.jtl" \
  --output "$CANDIDATE_DIR/run/metrics.json" \
  --scenario shop-query \
  --run-type candidate |
  tee "$CANDIDATE_DIR/run/metrics-console.log"

cp \
  "$CANDIDATE_DIR/run/metrics.json" \
  "$CANDIDATE_RUN_ROOT/shop-query-round${ROUND}.json"

record_environment "after"

python3 - "$CANDIDATE_DIR/run/metrics.json" "$ROUND" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
round_number = sys.argv[2]

data = json.loads(
    path.read_text(encoding="utf-8")
)

metrics = data["metrics"]

print(f"ROUND = {round_number}")

for name in [
    "sample_count",
    "success_count",
    "error_count",
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

if metrics["sample_count"] != 400:
    raise AssertionError(
        f"sample_count={metrics['sample_count']}"
    )

if metrics["error_count"] != 0:
    raise AssertionError(
        f"error_count={metrics['error_count']}"
    )

print(
    f"SHOP_CANDIDATE_ROUND{round_number}_CHECK = PASS"
)
PY

echo "CANDIDATE_RAW_DIR=$CANDIDATE_DIR"
