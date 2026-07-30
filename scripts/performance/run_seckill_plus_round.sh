#!/usr/bin/env bash

set -Eeuo pipefail

RUN_TYPE="${1:-}"
ROUND="${2:-}"

case "$RUN_TYPE" in
  baseline|candidate)
    ;;
  *)
    echo \
      "Usage: $0 <baseline|candidate> <round>" \
      >&2
    exit 2
    ;;
esac

if [[ ! "$ROUND" =~ ^[1-9][0-9]*$ ]]; then
  echo \
    "Round must be a positive integer" \
    >&2
  exit 2
fi

VOUCHER_ID=900013
USER_COUNT=20
USER_ID_BASE=9000000000
USER_ID_MIN=$((USER_ID_BASE + 1))
USER_ID_MAX=$((USER_ID_BASE + USER_COUNT))

REDIS_DB=1
RAMP_UP_SECONDS=2
LOOPS_PER_THREAD=1

PLAN="performance/jmeter/plans/seckill-plus-regression.jmx"
TOKEN_CSV_RELATIVE="performance/jmeter/data/seckill-pilot-tokens.csv"

JMETER_BIN="${JMETER_BIN:-/home/zoey/tools/jmeter/bin/jmeter}"
PERF_ROOT="${PERF_ROOT:-/mnt/wanping-performance/runs}"

SCRIPT_DIR="$(
  cd "$(dirname "${BASH_SOURCE[0]}")" &&
  pwd
)"

REPO_ROOT="$(
  cd "$SCRIPT_DIR/../.." &&
  pwd
)"

cd "$REPO_ROOT"

PREPARE_SCRIPT="\
scripts/performance/prepare_seckill_plus_pilot.sh"

TOKEN_CSV="$(
  realpath -m "$TOKEN_CSV_RELATIVE"
)"

case "$RUN_TYPE" in
  baseline)
    RESULT_REPO_DIR="performance/baselines/runs"
    ;;
  candidate)
    RESULT_REPO_DIR="performance/candidates/runs"
    ;;
esac

RUN_ID="$(date +%Y%m%d-%H%M%S)"

RAW_DIR="\
${PERF_ROOT}/\
seckill-plus-${RUN_TYPE}-round${ROUND}-${RUN_ID}"

mkdir -p \
  "$RAW_DIR/tmp" \
  "$RESULT_REPO_DIR"

printf '%s\n' "$RAW_DIR" \
  > "/tmp/seckill-plus-${RUN_TYPE}-round${ROUND}-latest-dir"

fail() {
  echo "SECKILL_PLUS_ROUND = FAILED" >&2
  echo "REASON = $*" >&2
  echo "RAW_DIR=$RAW_DIR" >&2
  exit 1
}

mysql_value() {
  local sql="$1"

  docker exec \
    -e PERF_SQL="$sql" \
    hmdp-mysql \
    sh -lc '
      mysql \
        -uroot \
        -p"$MYSQL_ROOT_PASSWORD" \
        -Ddingping \
        -N \
        -B \
        -e "$PERF_SQL"
    '
}

redis_value() {
  docker exec \
    hmdp-redis \
    redis-cli \
    -n "$REDIS_DB" \
    "$@"
}

echo "RUN_TYPE=$RUN_TYPE"
echo "ROUND=$ROUND"
echo "VOUCHER_ID=$VOUCHER_ID"
echo "USER_COUNT=$USER_COUNT"
echo "USER_ID_RANGE=${USER_ID_MIN}-${USER_ID_MAX}"
echo "REDIS_DB=$REDIS_DB"
echo "RAMP_UP_SECONDS=$RAMP_UP_SECONDS"
echo "LOOPS_PER_THREAD=$LOOPS_PER_THREAD"
echo "RAW_DIR=$RAW_DIR"

if ! mountpoint -q /mnt/wanping-performance; then
  fail "/mnt/wanping-performance is not mounted"
fi

if [[ ! -w /mnt/wanping-performance ]]; then
  fail "/mnt/wanping-performance is not writable"
fi

ROOT_USAGE="$(
  df -P / |
  awk '
    NR == 2 {
      gsub("%", "", $5)
      print $5
    }
  '
)"

echo "ROOT_DISK_USAGE_PERCENT=$ROOT_USAGE"

if (( ROOT_USAGE >= 95 )); then
  fail "root disk usage is at least 95%"
elif (( ROOT_USAGE >= 90 )); then
  echo "ROOT_DISK_GATE = WARNING"
else
  echo "ROOT_DISK_GATE = PASS"
fi

[[ -x "$JMETER_BIN" ]] \
  || fail "JMeter executable was not found"

[[ -f "$PLAN" ]] \
  || fail "JMeter plan was not found"

[[ -x "$PREPARE_SCRIPT" ]] \
  || fail "preparation script is not executable"

echo
echo "===== Preparation preflight ====="

set +e

REDIS_DB="$REDIS_DB" \
"$PREPARE_SCRIPT" \
  --voucher-id "$VOUCHER_ID" \
  --user-count "$USER_COUNT" \
  --user-id-base "$USER_ID_BASE" \
  2>&1 |
  tee "$RAW_DIR/preparation-preflight.log"

PREFLIGHT_EXIT_CODE="${PIPESTATUS[0]}"

set -e

echo "PREFLIGHT_EXIT_CODE=$PREFLIGHT_EXIT_CODE"

(( PREFLIGHT_EXIT_CODE == 0 )) \
  || fail "preparation preflight failed"

grep -q \
  '^SAFE_PREPARATION_PREFLIGHT = PASS$' \
  "$RAW_DIR/preparation-preflight.log" \
  || fail "preflight PASS marker is missing"

echo "PREPARATION_PREFLIGHT = PASS"

echo
echo "===== Apply preparation ====="

set +e

REDIS_DB="$REDIS_DB" \
ALLOW_DESTRUCTIVE_SECKILL_TEST=YES \
"$PREPARE_SCRIPT" \
  --voucher-id "$VOUCHER_ID" \
  --user-count "$USER_COUNT" \
  --user-id-base "$USER_ID_BASE" \
  --apply \
  2>&1 |
  tee "$RAW_DIR/preparation-apply.log"

PREPARATION_EXIT_CODE="${PIPESTATUS[0]}"

set -e

echo "PREPARATION_EXIT_CODE=$PREPARATION_EXIT_CODE"

(( PREPARATION_EXIT_CODE == 0 )) \
  || fail "preparation apply failed"

grep -q \
  '^SAFE_PREPARATION_CHECK = PASS$' \
  "$RAW_DIR/preparation-apply.log" \
  || fail "preparation PASS marker is missing"

echo "PREPARATION_APPLY = PASS"

[[ -f "$TOKEN_CSV" ]] \
  || fail "token CSV was not generated"

TOKEN_COUNT="$(
  wc -l < "$TOKEN_CSV" |
  tr -d ' '
)"

UNIQUE_TOKEN_COUNT="$(
  sort -u "$TOKEN_CSV" |
  wc -l |
  tr -d ' '
)"

echo "TOKEN_COUNT=$TOKEN_COUNT"
echo "UNIQUE_TOKEN_COUNT=$UNIQUE_TOKEN_COUNT"

[[ "$TOKEN_COUNT" == "$USER_COUNT" ]] \
  || fail "token count does not match user count"

[[ "$UNIQUE_TOKEN_COUNT" == "$USER_COUNT" ]] \
  || fail "tokens are not unique"

TOKEN_SESSION_COUNT="$(
  python3 - "$TOKEN_CSV" "$REDIS_DB" <<'PY'
from pathlib import Path
import subprocess
import sys

token_file = Path(sys.argv[1])
redis_db = sys.argv[2]

tokens = [
    line.strip()
    for line in token_file.read_text(
        encoding="utf-8"
    ).splitlines()
    if line.strip()
]

count = 0

for token in tokens:
    result = subprocess.run(
        [
            "docker",
            "exec",
            "hmdp-redis",
            "redis-cli",
            "-n",
            redis_db,
            "EXISTS",
            f"login:token:{token}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    if result.stdout.strip() == "1":
        count += 1

print(count)
PY
)"

echo "TOKEN_SESSION_COUNT=$TOKEN_SESSION_COUNT"

[[ "$TOKEN_SESSION_COUNT" == "$USER_COUNT" ]] \
  || fail "Redis token session count mismatch"

echo
echo "===== Authentication smoke ====="

FIRST_TOKEN="$(
  sed -n '1p' "$TOKEN_CSV"
)"

AUTH_HTTP_CODE="$(
  curl -sS \
    -o "$RAW_DIR/auth-smoke.json" \
    -w '%{http_code}' \
    -H "authorization: ${FIRST_TOKEN}" \
    http://127.0.0.1:8082/user/me
)"

echo "AUTH_HTTP_CODE=$AUTH_HTTP_CODE"

python3 \
  - "$AUTH_HTTP_CODE" "$USER_ID_MIN" \
  "$RAW_DIR/auth-smoke.json" <<'PY'
import json
import sys
from pathlib import Path

http_code = sys.argv[1]
expected_user_id = sys.argv[2]
path = Path(sys.argv[3])

payload = json.loads(
    path.read_text(encoding="utf-8")
)

data = payload.get("data") or {}

assert http_code == "200", http_code
assert payload.get("success") is True, payload
assert str(data.get("id")) == expected_user_id, data

print("AUTH_SMOKE_CHECK = PASS")
PY

echo
echo "===== Initial state ====="

DB_STOCK_BEFORE="$(
  mysql_value "
    SELECT stock
    FROM tb_seckill_voucher
    WHERE voucher_id = ${VOUCHER_ID};
  "
)"

DB_ORDER_COUNT_BEFORE="$(
  mysql_value "
    SELECT COUNT(*)
    FROM tb_voucher_order
    WHERE voucher_id = ${VOUCHER_ID}
      AND user_id BETWEEN
        ${USER_ID_MIN} AND ${USER_ID_MAX};
  "
)"

REDIS_STOCK_BEFORE="$(
  redis_value \
    --raw \
    GET "seckill:stock:${VOUCHER_ID}"
)"

REDIS_ORDER_COUNT_BEFORE="$(
  redis_value \
    SCARD "seckill:order:${VOUCHER_ID}"
)"

REDIS_TRACE_COUNT_BEFORE="$(
  redis_value \
    HLEN "seckill:trace:log:${VOUCHER_ID}"
)"

echo "DB_STOCK_BEFORE=$DB_STOCK_BEFORE"
echo "DB_ORDER_COUNT_BEFORE=$DB_ORDER_COUNT_BEFORE"
echo "REDIS_STOCK_BEFORE=$REDIS_STOCK_BEFORE"
echo "REDIS_ORDER_COUNT_BEFORE=$REDIS_ORDER_COUNT_BEFORE"
echo "REDIS_TRACE_COUNT_BEFORE=$REDIS_TRACE_COUNT_BEFORE"

[[ "$DB_STOCK_BEFORE" == "$USER_COUNT" ]] \
  || fail "initial DB stock mismatch"

[[ "$DB_ORDER_COUNT_BEFORE" == "0" ]] \
  || fail "initial DB order count is not zero"

[[ "$REDIS_STOCK_BEFORE" == "$USER_COUNT" ]] \
  || fail "initial Redis stock mismatch"

[[ "$REDIS_ORDER_COUNT_BEFORE" == "0" ]] \
  || fail "initial Redis order set is not empty"

[[ "$REDIS_TRACE_COUNT_BEFORE" == "0" ]] \
  || fail "initial Redis trace is not empty"

echo "INITIAL_STATE_CHECK = PASS"

echo
echo "===== Run JMeter ====="

set +e

JVM_ARGS="\
-Djava.io.tmpdir=$RAW_DIR/tmp \
-Xms256m \
-Xmx512m" \
"$JMETER_BIN" \
  -n \
  -t "$PLAN" \
  -Jprotocol=http \
  -Jhost=127.0.0.1 \
  -Jport=8082 \
  -Jthreads="$USER_COUNT" \
  -Jramp_up="$RAMP_UP_SECONDS" \
  -Jloops="$LOOPS_PER_THREAD" \
  -Jvoucher_id="$VOUCHER_ID" \
  -Jtoken_csv="$TOKEN_CSV" \
  -Jconnect_timeout_ms=3000 \
  -Jresponse_timeout_ms=15000 \
  -Jjmeter.save.saveservice.output_format=csv \
  -Jjmeter.save.saveservice.print_field_names=true \
  -Jjmeter.save.saveservice.response_data.on_error=true \
  -Jjmeter.save.saveservice.assertion_results_failure_message=true \
  -l "$RAW_DIR/result.jtl" \
  -j "$RAW_DIR/jmeter.log" \
  2>&1 |
  tee "$RAW_DIR/console.log"

JMETER_EXIT_CODE="${PIPESTATUS[0]}"

set -e

echo "JMETER_EXIT_CODE=$JMETER_EXIT_CODE"

(( JMETER_EXIT_CODE == 0 )) \
  || fail "JMeter returned non-zero exit code"

python3 - "$RAW_DIR/result.jtl" "$USER_COUNT" <<'PY'
import csv
import sys
from collections import Counter
from pathlib import Path

path = Path(sys.argv[1])
expected = int(sys.argv[2])

with path.open(
    encoding="utf-8-sig",
    newline="",
) as file:
    rows = list(csv.DictReader(file))

errors = [
    row
    for row in rows
    if (
        row.get("success", "")
        .strip()
        .lower()
        != "true"
    )
]

codes = Counter(
    row.get("responseCode")
    for row in rows
)

print("SAMPLE_COUNT =", len(rows))
print("SUCCESS_COUNT =", len(rows) - len(errors))
print("ERROR_COUNT =", len(errors))
print("RESPONSE_CODES =", dict(codes))

for row in errors[:10]:
    print(
        "FAILED_SAMPLE =",
        {
            "responseCode":
                row.get("responseCode"),
            "failureMessage":
                row.get("failureMessage"),
            "elapsed":
                row.get("elapsed"),
        },
    )

assert len(rows) == expected, (
    f"expected={expected}, actual={len(rows)}"
)
assert not errors, (
    f"error_count={len(errors)}"
)
assert set(codes) == {"200"}, codes

print("JTL_HTTP_CHECK = PASS")
PY

echo
echo "===== Wait for asynchronous orders ====="

ORDER_COUNT=0

for attempt in $(seq 1 60); do
  ORDER_COUNT="$(
    mysql_value "
      SELECT COUNT(*)
      FROM tb_voucher_order
      WHERE voucher_id = ${VOUCHER_ID}
        AND user_id BETWEEN
          ${USER_ID_MIN} AND ${USER_ID_MAX};
    "
  )"

  echo \
    "ORDER_POLL_ATTEMPT=$attempt" \
    "ORDER_COUNT=$ORDER_COUNT"

  if [[ "$ORDER_COUNT" == "$USER_COUNT" ]]; then
    break
  fi

  sleep 1
done

DB_STOCK="$(
  mysql_value "
    SELECT stock
    FROM tb_seckill_voucher
    WHERE voucher_id = ${VOUCHER_ID};
  "
)"

DISTINCT_USER_COUNT="$(
  mysql_value "
    SELECT COUNT(DISTINCT user_id)
    FROM tb_voucher_order
    WHERE voucher_id = ${VOUCHER_ID}
      AND user_id BETWEEN
        ${USER_ID_MIN} AND ${USER_ID_MAX};
  "
)"

DUPLICATE_USER_COUNT="$(
  mysql_value "
    SELECT COUNT(*)
    FROM (
      SELECT user_id
      FROM tb_voucher_order
      WHERE voucher_id = ${VOUCHER_ID}
        AND user_id BETWEEN
          ${USER_ID_MIN} AND ${USER_ID_MAX}
      GROUP BY user_id
      HAVING COUNT(*) > 1
    ) duplicated;
  "
)"

DEDUCT_LOG_COUNT="$(
  mysql_value "
    SELECT COUNT(*)
    FROM tb_voucher_reconcile_log
    WHERE voucher_id = ${VOUCHER_ID}
      AND user_id BETWEEN
        ${USER_ID_MIN} AND ${USER_ID_MAX}
      AND log_type = 'DEDUCT'
      AND business_type = 'SUCCESS';
  "
)"

RESTORE_LOG_COUNT="$(
  mysql_value "
    SELECT COUNT(*)
    FROM tb_voucher_reconcile_log
    WHERE voucher_id = ${VOUCHER_ID}
      AND user_id BETWEEN
        ${USER_ID_MIN} AND ${USER_ID_MAX}
      AND log_type = 'RESTORE';
  "
)"

VERIFY_OPEN_COUNT="$(
  mysql_value "
    SELECT COUNT(*)
    FROM tb_order_create_verify_task
    WHERE voucher_id = ${VOUCHER_ID}
      AND user_id BETWEEN
        ${USER_ID_MIN} AND ${USER_ID_MAX}
      AND task_status IN (
        'PENDING',
        'VERIFYING',
        'RETRYING',
        'FAILED'
      );
  "
)"

RECOVERY_TASK_COUNT="$(
  mysql_value "
    SELECT COUNT(*)
    FROM tb_order_create_recovery_task
    WHERE voucher_id = ${VOUCHER_ID}
      AND user_id BETWEEN
        ${USER_ID_MIN} AND ${USER_ID_MAX};
  "
)"

RECONCILE_TASK_COUNT="$(
  mysql_value "
    SELECT COUNT(*)
    FROM tb_seckill_reconcile_task
    WHERE voucher_id = ${VOUCHER_ID}
      AND user_id BETWEEN
        ${USER_ID_MIN} AND ${USER_ID_MAX};
  "
)"

REDIS_STOCK="$(
  redis_value \
    --raw \
    GET "seckill:stock:${VOUCHER_ID}"
)"

REDIS_ORDER_COUNT="$(
  redis_value \
    SCARD "seckill:order:${VOUCHER_ID}"
)"

REDIS_TRACE_COUNT="$(
  redis_value \
    HLEN "seckill:trace:log:${VOUCHER_ID}"
)"

REQUEST_KEY_COUNT="$(
  docker exec hmdp-redis \
    sh -lc "
      redis-cli \
        -n ${REDIS_DB} \
        --scan \
        --pattern \
        'seckill:req:${VOUCHER_ID}:*' |
      wc -l
    " |
  tr -d ' '
)"

cat > "$RAW_DIR/business-summary.txt" <<EOF
voucher_id=$VOUCHER_ID
db_stock=$DB_STOCK
order_count=$ORDER_COUNT
distinct_user_count=$DISTINCT_USER_COUNT
duplicate_user_count=$DUPLICATE_USER_COUNT
deduct_log_count=$DEDUCT_LOG_COUNT
restore_log_count=$RESTORE_LOG_COUNT
verify_open_count=$VERIFY_OPEN_COUNT
recovery_task_count=$RECOVERY_TASK_COUNT
reconcile_task_count=$RECONCILE_TASK_COUNT
redis_stock=$REDIS_STOCK
redis_order_count=$REDIS_ORDER_COUNT
redis_trace_count=$REDIS_TRACE_COUNT
request_key_count=$REQUEST_KEY_COUNT
EOF

cat "$RAW_DIR/business-summary.txt"

[[ "$DB_STOCK" == "0" ]] \
  || fail "DB stock is not zero"

[[ "$ORDER_COUNT" == "$USER_COUNT" ]] \
  || fail "DB order count mismatch"

[[ "$DISTINCT_USER_COUNT" == "$USER_COUNT" ]] \
  || fail "distinct user count mismatch"

[[ "$DUPLICATE_USER_COUNT" == "0" ]] \
  || fail "duplicate orders exist"

[[ "$DEDUCT_LOG_COUNT" == "$USER_COUNT" ]] \
  || fail "deduct log count mismatch"

[[ "$RESTORE_LOG_COUNT" == "0" ]] \
  || fail "restore logs exist"

[[ "$VERIFY_OPEN_COUNT" == "0" ]] \
  || fail "open verification tasks exist"

[[ "$RECOVERY_TASK_COUNT" == "0" ]] \
  || fail "recovery tasks exist"

[[ "$RECONCILE_TASK_COUNT" == "0" ]] \
  || fail "reconcile tasks exist"

[[ "$REDIS_STOCK" == "0" ]] \
  || fail "Redis stock is not zero"

[[ "$REDIS_ORDER_COUNT" == "$USER_COUNT" ]] \
  || fail "Redis order set count mismatch"

[[ "$REDIS_TRACE_COUNT" == "$USER_COUNT" ]] \
  || fail "Redis trace count mismatch"

[[ "$REQUEST_KEY_COUNT" == "0" ]] \
  || fail "request keys remain"

echo "BUSINESS_CONSISTENCY_CHECK = PASS"

METRICS_OUTPUT="\
$RAW_DIR/metrics.json"

python3 \
  - "$RAW_DIR/result.jtl" \
  "$RAW_DIR/business-summary.txt" \
  "$METRICS_OUTPUT" \
  "$RUN_TYPE" \
  "$ROUND" \
  "$RAW_DIR" \
  "$ROOT_USAGE" <<'PY'
from __future__ import annotations

import csv
import json
import math
import statistics
import sys
from pathlib import Path


jtl_path = Path(sys.argv[1])
business_path = Path(sys.argv[2])
output_path = Path(sys.argv[3])
run_type = sys.argv[4]
round_number = int(sys.argv[5])
raw_dir = sys.argv[6]
root_usage = int(sys.argv[7])

with jtl_path.open(
    encoding="utf-8-sig",
    newline="",
) as file:
    rows = list(csv.DictReader(file))

elapsed = sorted(
    int(row["elapsed"])
    for row in rows
)

timestamps = [
    int(row["timeStamp"])
    for row in rows
]

end_timestamps = [
    int(row["timeStamp"])
    + int(row["elapsed"])
    for row in rows
]

duration_seconds = max(
    (
        max(end_timestamps)
        - min(timestamps)
    )
    / 1000,
    0.001,
)


def percentile(
    values: list[int],
    percentile_value: float,
) -> int:
    index = (
        math.ceil(
            len(values) * percentile_value
        )
        - 1
    )
    return values[index]


business: dict[str, int | str] = {}

for line in business_path.read_text(
    encoding="utf-8"
).splitlines():
    name, value = line.split("=", 1)

    try:
        business[name] = int(value)
    except ValueError:
        business[name] = value

metrics = {
    "sample_count": len(rows),
    "success_count": len(rows),
    "error_count": 0,
    "error_rate": 0.0,
    "duration_seconds": round(
        duration_seconds,
        3,
    ),
    "throughput_rps": round(
        len(rows) / duration_seconds,
        3,
    ),
    "mean_ms": round(
        statistics.mean(elapsed),
        3,
    ),
    "median_ms": statistics.median(
        elapsed
    ),
    "p90_ms": percentile(
        elapsed,
        0.90,
    ),
    "p95_ms": percentile(
        elapsed,
        0.95,
    ),
    "p99_ms": percentile(
        elapsed,
        0.99,
    ),
    "max_ms": elapsed[-1],
}

report = {
    "scenario": "seckill-plus",
    "run_type": run_type,
    "round": round_number,
    "status": "PASS",
    "target": {
        "protocol": "http",
        "host": "127.0.0.1",
        "port": 8082,
        "voucher_id": 900013,
        "redis_database": 1,
    },
    "load_model": {
        "threads": 20,
        "ramp_up_seconds": 2,
        "loops_per_thread": 1,
        "unique_tokens": 20,
        "expected_samples": 20,
    },
    "metrics": metrics,
    "business_consistency": business,
    "environment": {
        "root_disk_usage_percent":
            root_usage,
    },
    "raw_artifact_directory": raw_dir,
}

output_path.write_text(
    json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)

for name, value in metrics.items():
    print(
        name.upper(),
        "=",
        value,
    )

print("ROUND_METRICS_CHECK = PASS")
PY

REPO_METRICS_OUTPUT="\
${RESULT_REPO_DIR}/\
seckill-plus-round${ROUND}.json"

cp \
  "$METRICS_OUTPUT" \
  "$REPO_METRICS_OUTPUT"

echo
echo "SECKILL_PLUS_ROUND = PASS"
echo "RUN_TYPE=$RUN_TYPE"
echo "ROUND=$ROUND"
echo "RAW_DIR=$RAW_DIR"
echo "METRICS_OUTPUT=$REPO_METRICS_OUTPUT"
