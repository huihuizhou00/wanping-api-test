#!/usr/bin/env bash

set -Eeuo pipefail

DRY_RUN=1
USER_COUNT=5
VOUCHER_ID=13
USER_ID_BASE=9000000000
SESSION_TTL_SECONDS=36000
REDIS_DB="${REDIS_DB:-1}"

TOKEN_CSV_RELATIVE="performance/jmeter/data/seckill-pilot-tokens.csv"

usage() {
  cat <<'EOF'
Usage:
  prepare_seckill_plus_pilot.sh [options]

Options:
  --voucher-id <id>       Voucher ID, default 13
  --user-count <count>    Pilot users, default 5, maximum 50
  --user-id-base <id>     Test user ID base, default 9000000000
  --apply                 Apply destructive preparation
  -h, --help              Show help

Dry-run is the default.

Applying changes requires both:
  --apply
  ALLOW_DESTRUCTIVE_SECKILL_TEST=YES
EOF
}

fail() {
  echo "PREPARATION_CHECK = FAILED" >&2
  echo "REASON = $*" >&2
  exit 1
}

while (($# > 0)); do
  case "$1" in
    --voucher-id)
      shift
      VOUCHER_ID="${1:-}"
      ;;
    --user-count)
      shift
      USER_COUNT="${1:-}"
      ;;
    --user-id-base)
      shift
      USER_ID_BASE="${1:-}"
      ;;
    --apply)
      DRY_RUN=0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      fail "unknown argument: $1"
      ;;
  esac

  shift
done

[[ "$VOUCHER_ID" =~ ^[1-9][0-9]*$ ]] \
  || fail "voucher-id must be a positive integer"

[[ "$USER_COUNT" =~ ^[1-9][0-9]*$ ]] \
  || fail "user-count must be a positive integer"

[[ "$USER_ID_BASE" =~ ^[1-9][0-9]*$ ]] \
  || fail "user-id-base must be a positive integer"

[[ "$REDIS_DB" =~ ^([0-9]|1[0-5])$ ]] \
  || fail "redis database must be between 0 and 15"

(( USER_COUNT <= 50 )) \
  || fail "pilot user-count must not exceed 50"

(( USER_ID_BASE >= 9000000000 )) \
  || fail "test user-id-base must be at least 9000000000"

USER_ID_MIN=$((USER_ID_BASE + 1))
USER_ID_MAX=$((USER_ID_BASE + USER_COUNT))

SCRIPT_DIR="$(
  cd "$(dirname "${BASH_SOURCE[0]}")" &&
  pwd
)"

REPO_ROOT="$(
  cd "$SCRIPT_DIR/../.." &&
  pwd
)"

cd "$REPO_ROOT"

TOKEN_CSV="$REPO_ROOT/$TOKEN_CSV_RELATIVE"

PERF_ROOT="${PERF_ROOT:-/mnt/wanping-performance/runs}"
RUN_ID="$(date +%Y%m%d-%H%M%S)"
RESULT_DIR="$PERF_ROOT/seckill-pilot-preparation-$RUN_ID"

TOKEN_PREFIX="perf-seckill-pilot-v${VOUCHER_ID}-u"

STOCK_KEY="seckill:stock:${VOUCHER_ID}"
ORDER_KEY="seckill:order:${VOUCHER_ID}"
TRACE_KEY="seckill:trace:log:${VOUCHER_ID}"

if ! mountpoint -q /mnt/wanping-performance; then
  fail "/mnt/wanping-performance is not mounted"
fi

if [[ ! -w /mnt/wanping-performance ]]; then
  fail "/mnt/wanping-performance is not writable"
fi

mkdir -p "$RESULT_DIR"

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

MYSQL_CONTAINER="$(
  docker ps \
    --format '{{.Names}}\t{{.Image}}' |
  awk '
    BEGIN { IGNORECASE=1 }
    /mysql/ {
      print $1
      exit
    }
  '
)"

[[ -n "$MYSQL_CONTAINER" ]] \
  || fail "MySQL container was not found"

REDIS_CONTAINER="$(
  docker ps \
    --format '{{.Names}}\t{{.Image}}' |
  awk '
    BEGIN { IGNORECASE=1 }
    /redis/ && $0 !~ /redisinsight/ {
      print $1
      exit
    }
  '
)"

[[ -n "$REDIS_CONTAINER" ]] \
  || fail "Redis container was not found"

docker exec "$MYSQL_CONTAINER" \
  sh -lc '
    test -n "${MYSQL_ROOT_PASSWORD:-}"
  ' \
  || fail "MYSQL_ROOT_PASSWORD is absent in MySQL container"

BUSINESS_DB="$(
  docker exec "$MYSQL_CONTAINER" \
    sh -lc '
      mysql \
        -uroot \
        -p"$MYSQL_ROOT_PASSWORD" \
        -N \
        -B \
        -e "
          SELECT TABLE_SCHEMA
          FROM information_schema.TABLES
          WHERE TABLE_NAME = '\''tb_seckill_voucher'\''
          LIMIT 1;
        "
    '
)"

[[ -n "$BUSINESS_DB" ]] \
  || fail "business database was not found"

mysql_exec() {
  local sql="$1"

  docker exec \
    -e PERF_DB_NAME="$BUSINESS_DB" \
    -e PERF_SQL="$sql" \
    "$MYSQL_CONTAINER" \
    sh -lc '
      mysql \
        -uroot \
        -p"$MYSQL_ROOT_PASSWORD" \
        -D"$PERF_DB_NAME" \
        -N \
        -B \
        -e "$PERF_SQL"
    '
}

redis_cmd() {
  docker exec \
    "$REDIS_CONTAINER" \
    redis-cli \
    -n \
    "$REDIS_DB" \
    "$@"
}

echo "MYSQL_CONTAINER=$MYSQL_CONTAINER"
echo "BUSINESS_DB=$BUSINESS_DB"
echo "REDIS_CONTAINER=$REDIS_CONTAINER"
echo "REDIS_DB=$REDIS_DB"
echo "VOUCHER_ID=$VOUCHER_ID"
echo "USER_COUNT=$USER_COUNT"
echo "USER_ID_RANGE=${USER_ID_MIN}-${USER_ID_MAX}"
echo "TOKEN_CSV=$TOKEN_CSV"

curl -fsS \
  "http://127.0.0.1:8082/shop/of/type?typeId=1&current=1" \
  > "$RESULT_DIR/shop-health.json" \
  || fail "application health request failed"

curl -fsS \
  "http://127.0.0.1:8082/jvm/status" \
  > "$RESULT_DIR/jvm-status.json" \
  || fail "JVM status request failed"

python3 - "$RESULT_DIR/jvm-status.json" <<'PY'
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

for name, expected_value in expected.items():
    actual = data.get(name)

    if actual != expected_value:
        raise AssertionError(
            f"{name}: expected={expected_value}, "
            f"actual={actual}"
        )

print("JVM_FAULT_GATE = PASS")
PY

REQUIRED_TABLE_COUNT="$(
  mysql_exec "
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME IN (
        'tb_seckill_voucher',
        'tb_voucher_order',
        'tb_voucher_reconcile_log',
        'tb_order_create_verify_task',
        'tb_order_create_recovery_task',
        'tb_seckill_reconcile_task'
      );
  "
)"

[[ "$REQUIRED_TABLE_COUNT" == "6" ]] \
  || fail "required extension tables are incomplete"

VOUCHER_ROW="$(
  mysql_exec "
    SELECT CONCAT_WS(
      '|',
      voucher_id,
      stock,
      DATE_FORMAT(begin_time, '%Y-%m-%d %H:%i:%s'),
      DATE_FORMAT(end_time, '%Y-%m-%d %H:%i:%s'),
      CASE
        WHEN NOW() < begin_time THEN 'NOT_STARTED'
        WHEN NOW() > end_time THEN 'EXPIRED'
        ELSE 'ACTIVE'
      END
    )
    FROM tb_seckill_voucher
    WHERE voucher_id = ${VOUCHER_ID};
  "
)"

[[ -n "$VOUCHER_ROW" ]] \
  || fail "voucher ${VOUCHER_ID} does not exist"

IFS='|' read -r \
  DB_VOUCHER_ID \
  DB_STOCK \
  DB_BEGIN_TIME \
  DB_END_TIME \
  ACTIVITY_STATUS \
  <<< "$VOUCHER_ROW"

echo "DB_STOCK_BEFORE=$DB_STOCK"
echo "DB_BEGIN_TIME=$DB_BEGIN_TIME"
echo "DB_END_TIME=$DB_END_TIME"
echo "ACTIVITY_STATUS=$ACTIVITY_STATUS"

[[ "$ACTIVITY_STATUS" == "ACTIVE" ]] \
  || fail "voucher activity is ${ACTIVITY_STATUS}"

outside_count() {
  local table="$1"

  mysql_exec "
    SELECT COUNT(*)
    FROM ${table}
    WHERE voucher_id = ${VOUCHER_ID}
      AND (
        user_id IS NULL
        OR user_id NOT BETWEEN
          ${USER_ID_MIN} AND ${USER_ID_MAX}
      );
  "
}

OUTSIDE_ORDER_COUNT="$(
  outside_count tb_voucher_order
)"

OUTSIDE_RECONCILE_LOG_COUNT="$(
  outside_count tb_voucher_reconcile_log
)"

OUTSIDE_VERIFY_COUNT="$(
  outside_count tb_order_create_verify_task
)"

OUTSIDE_RECOVERY_COUNT="$(
  outside_count tb_order_create_recovery_task
)"

OUTSIDE_RECONCILE_TASK_COUNT="$(
  outside_count tb_seckill_reconcile_task
)"

echo "OUTSIDE_ORDER_COUNT=$OUTSIDE_ORDER_COUNT"
echo "OUTSIDE_RECONCILE_LOG_COUNT=$OUTSIDE_RECONCILE_LOG_COUNT"
echo "OUTSIDE_VERIFY_COUNT=$OUTSIDE_VERIFY_COUNT"
echo "OUTSIDE_RECOVERY_COUNT=$OUTSIDE_RECOVERY_COUNT"
echo "OUTSIDE_RECONCILE_TASK_COUNT=$OUTSIDE_RECONCILE_TASK_COUNT"

for value in \
  "$OUTSIDE_ORDER_COUNT" \
  "$OUTSIDE_RECONCILE_LOG_COUNT" \
  "$OUTSIDE_VERIFY_COUNT" \
  "$OUTSIDE_RECOVERY_COUNT" \
  "$OUTSIDE_RECONCILE_TASK_COUNT"
do
  [[ "$value" == "0" ]] \
    || fail "voucher contains non-test business records"
done

OUTSIDE_REDIS_USERS="$(
  redis_cmd \
    --raw \
    EVAL '
      local cursor = "0"
      local invalid_count = 0
      local minimum_user_id = tonumber(ARGV[1])
      local maximum_user_id = tonumber(ARGV[2])

      repeat
        local scan_result = redis.call(
          "SSCAN",
          KEYS[1],
          cursor,
          "COUNT",
          200
        )

        cursor = scan_result[1]

        for _, member in ipairs(
          scan_result[2]
        ) do
          local numeric_user_id = tonumber(
            member
          )

          if (
            member == ""
            or numeric_user_id == nil
            or numeric_user_id < minimum_user_id
            or numeric_user_id > maximum_user_id
          ) then
            invalid_count = invalid_count + 1
          end
        end
      until cursor == "0"

      return invalid_count
    ' \
    1 \
    "$ORDER_KEY" \
    "$USER_ID_MIN" \
    "$USER_ID_MAX"
)"

[[ "$OUTSIDE_REDIS_USERS" =~ ^[0-9]+$ ]] \
  || fail "invalid Redis validation result"

echo "OUTSIDE_REDIS_USERS=$OUTSIDE_REDIS_USERS"

[[ "$OUTSIDE_REDIS_USERS" == "0" ]] \
  || fail "Redis order set contains non-test users"

REDIS_STOCK_BEFORE="$(
  redis_cmd \
    --raw \
    GET \
    "$STOCK_KEY"
)"

REDIS_ORDER_COUNT_BEFORE="$(
  redis_cmd \
    SCARD \
    "$ORDER_KEY"
)"

REDIS_TRACE_COUNT_BEFORE="$(
  redis_cmd \
    HLEN \
    "$TRACE_KEY"
)"

echo "REDIS_STOCK_BEFORE=${REDIS_STOCK_BEFORE:-MISSING}"
echo "REDIS_ORDER_COUNT_BEFORE=$REDIS_ORDER_COUNT_BEFORE"
echo "REDIS_TRACE_COUNT_BEFORE=$REDIS_TRACE_COUNT_BEFORE"

{
  echo "mode=$(
    if (( DRY_RUN == 1 )); then
      echo dry-run
    else
      echo apply
    fi
  )"
  echo "voucher_id=$VOUCHER_ID"
  echo "user_count=$USER_COUNT"
  echo "user_id_min=$USER_ID_MIN"
  echo "user_id_max=$USER_ID_MAX"
  echo "activity_status=$ACTIVITY_STATUS"
  echo "db_stock_before=$DB_STOCK"
  echo "redis_stock_before=${REDIS_STOCK_BEFORE:-MISSING}"
  echo "redis_order_count_before=$REDIS_ORDER_COUNT_BEFORE"
  echo "redis_trace_count_before=$REDIS_TRACE_COUNT_BEFORE"
  echo "root_disk_usage_percent=$ROOT_USAGE"
} > "$RESULT_DIR/preparation-before.txt"

if (( DRY_RUN == 1 )); then
  echo
  echo "PREPARATION_MODE = DRY_RUN"
  echo "DATABASE_MUTATION = NOT_EXECUTED"
  echo "REDIS_MUTATION = NOT_EXECUTED"
  echo "TOKEN_CSV_WRITE = NOT_EXECUTED"
  echo "SAFE_PREPARATION_PREFLIGHT = PASS"
  echo "PREPARATION_EVIDENCE=$RESULT_DIR"
  exit 0
fi

if [[ "${ALLOW_DESTRUCTIVE_SECKILL_TEST:-}" != "YES" ]]; then
  fail \
    "set ALLOW_DESTRUCTIVE_SECKILL_TEST=YES " \
    "together with --apply"
fi

mysql_exec "
  START TRANSACTION;

  DELETE FROM tb_voucher_order WHERE voucher_id = ${VOUCHER_ID} AND user_id BETWEEN ${USER_ID_MIN} AND ${USER_ID_MAX};
  DELETE FROM tb_voucher_reconcile_log WHERE voucher_id = ${VOUCHER_ID} AND user_id BETWEEN ${USER_ID_MIN} AND ${USER_ID_MAX};
  DELETE FROM tb_order_create_verify_task WHERE voucher_id = ${VOUCHER_ID} AND user_id BETWEEN ${USER_ID_MIN} AND ${USER_ID_MAX};
  DELETE FROM tb_order_create_recovery_task WHERE voucher_id = ${VOUCHER_ID} AND user_id BETWEEN ${USER_ID_MIN} AND ${USER_ID_MAX};
  DELETE FROM tb_seckill_reconcile_task WHERE voucher_id = ${VOUCHER_ID} AND user_id BETWEEN ${USER_ID_MIN} AND ${USER_ID_MAX};

  UPDATE tb_seckill_voucher
  SET stock = ${USER_COUNT}
  WHERE voucher_id = ${VOUCHER_ID};

  COMMIT;
"

redis_cmd \
  DEL \
  "$STOCK_KEY" \
  "$ORDER_KEY" \
  "$TRACE_KEY" \
  >/dev/null

mkdir -p "$(dirname "$TOKEN_CSV")"
: > "$TOKEN_CSV"
chmod 600 "$TOKEN_CSV"

for user_id in $(
  seq "$USER_ID_MIN" "$USER_ID_MAX"
); do
  token="${TOKEN_PREFIX}${user_id}"
  token_key="login:token:${token}"
  request_key="seckill:req:${VOUCHER_ID}:${user_id}"

  redis_cmd \
    DEL \
    "$token_key" \
    "$request_key" \
    >/dev/null

  redis_cmd \
    HSET \
    "$token_key" \
    id \
    "$user_id" \
    nickName \
    "perf-user-${user_id}" \
    icon \
    "" \
    >/dev/null

  redis_cmd \
    EXPIRE \
    "$token_key" \
    "$SESSION_TTL_SECONDS" \
    >/dev/null

  printf '%s\n' "$token" \
    >> "$TOKEN_CSV"
done

redis_cmd \
  SET \
  "$STOCK_KEY" \
  "$USER_COUNT" \
  >/dev/null

DB_STOCK_AFTER="$(
  mysql_exec "
    SELECT stock
    FROM tb_seckill_voucher
    WHERE voucher_id = ${VOUCHER_ID};
  "
)"

DB_TEST_ORDER_COUNT_AFTER="$(
  mysql_exec "
    SELECT COUNT(*)
    FROM tb_voucher_order
    WHERE voucher_id = ${VOUCHER_ID}
      AND user_id BETWEEN
        ${USER_ID_MIN} AND ${USER_ID_MAX};
  "
)"

REDIS_STOCK_AFTER="$(
  redis_cmd \
    --raw \
    GET \
    "$STOCK_KEY"
)"

REDIS_ORDER_COUNT_AFTER="$(
  redis_cmd \
    SCARD \
    "$ORDER_KEY"
)"

CSV_LINE_COUNT="$(
  wc -l < "$TOKEN_CSV" |
  tr -d ' '
)"

TOKEN_SESSION_COUNT=0

for user_id in $(
  seq "$USER_ID_MIN" "$USER_ID_MAX"
); do
  token="${TOKEN_PREFIX}${user_id}"

  if [[ "$(
    redis_cmd EXISTS "login:token:${token}"
  )" == "1" ]]; then
    TOKEN_SESSION_COUNT=$((TOKEN_SESSION_COUNT + 1))
  fi
done

[[ "$DB_STOCK_AFTER" == "$USER_COUNT" ]] \
  || fail "DB stock verification failed"

[[ "$DB_TEST_ORDER_COUNT_AFTER" == "0" ]] \
  || fail "test orders were not cleared"

[[ "$REDIS_STOCK_AFTER" == "$USER_COUNT" ]] \
  || fail "Redis stock verification failed"

[[ "$REDIS_ORDER_COUNT_AFTER" == "0" ]] \
  || fail "Redis order set was not cleared"

[[ "$CSV_LINE_COUNT" == "$USER_COUNT" ]] \
  || fail "token CSV line count mismatch"

[[ "$TOKEN_SESSION_COUNT" == "$USER_COUNT" ]] \
  || fail "Redis login session count mismatch"

{
  echo "voucher_id=$VOUCHER_ID"
  echo "user_count=$USER_COUNT"
  echo "user_id_min=$USER_ID_MIN"
  echo "user_id_max=$USER_ID_MAX"
  echo "db_stock_after=$DB_STOCK_AFTER"
  echo "db_test_order_count_after=$DB_TEST_ORDER_COUNT_AFTER"
  echo "redis_stock_after=$REDIS_STOCK_AFTER"
  echo "redis_order_count_after=$REDIS_ORDER_COUNT_AFTER"
  echo "token_session_count=$TOKEN_SESSION_COUNT"
  echo "token_csv_line_count=$CSV_LINE_COUNT"
  echo "token_csv=$TOKEN_CSV"
} > "$RESULT_DIR/preparation-after.txt"

echo
echo "PREPARATION_MODE = APPLY"
echo "DB_STOCK_AFTER=$DB_STOCK_AFTER"
echo "DB_TEST_ORDER_COUNT_AFTER=$DB_TEST_ORDER_COUNT_AFTER"
echo "REDIS_STOCK_AFTER=$REDIS_STOCK_AFTER"
echo "REDIS_ORDER_COUNT_AFTER=$REDIS_ORDER_COUNT_AFTER"
echo "TOKEN_SESSION_COUNT=$TOKEN_SESSION_COUNT"
echo "TOKEN_CSV_LINE_COUNT=$CSV_LINE_COUNT"
echo "TOKEN_CSV=$TOKEN_CSV"
echo "SAFE_PREPARATION_CHECK = PASS"
echo "PREPARATION_EVIDENCE=$RESULT_DIR"
