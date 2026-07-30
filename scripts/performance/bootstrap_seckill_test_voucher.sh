#!/usr/bin/env bash

set -Eeuo pipefail

DRY_RUN=1

VOUCHER_ID=900013
SHOP_ID=1
STOCK=5

VOUCHER_TITLE="[PERF-ONLY] Seckill Plus"
VOUCHER_SUB_TITLE="Dedicated performance test voucher"
VOUCHER_RULES="Performance testing only. Do not use for business."
PAY_VALUE=1
ACTUAL_VALUE=100

usage() {
  cat <<'EOF'
Usage:
  bootstrap_seckill_test_voucher.sh [options]

Options:
  --voucher-id <id>    Dedicated voucher ID, default 900013
  --shop-id <id>       Shop ID, default 1
  --stock <count>      Initial stock, default 5
  --apply              Create or refresh dedicated voucher
  -h, --help           Show help

Dry-run is the default.

Applying requires both:
  --apply
  ALLOW_TEST_VOUCHER_BOOTSTRAP=YES
EOF
}

fail() {
  echo "TEST_VOUCHER_BOOTSTRAP = FAILED" >&2
  echo "REASON = $*" >&2
  exit 1
}

while (($# > 0)); do
  case "$1" in
    --voucher-id)
      shift
      VOUCHER_ID="${1:-}"
      ;;
    --shop-id)
      shift
      SHOP_ID="${1:-}"
      ;;
    --stock)
      shift
      STOCK="${1:-}"
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

[[ "$SHOP_ID" =~ ^[1-9][0-9]*$ ]] \
  || fail "shop-id must be a positive integer"

[[ "$STOCK" =~ ^[1-9][0-9]*$ ]] \
  || fail "stock must be a positive integer"

(( VOUCHER_ID >= 900000 )) \
  || fail "dedicated voucher-id must be at least 900000"

(( STOCK <= 10000 )) \
  || fail "stock must not exceed 10000"

SCRIPT_DIR="$(
  cd "$(dirname "${BASH_SOURCE[0]}")" &&
  pwd
)"

REPO_ROOT="$(
  cd "$SCRIPT_DIR/../.." &&
  pwd
)"

cd "$REPO_ROOT"

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

docker exec "$MYSQL_CONTAINER" \
  sh -lc '
    test -n "${MYSQL_ROOT_PASSWORD:-}"
  ' \
  || fail "MYSQL_ROOT_PASSWORD is absent"

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

SHOP_EXISTS="$(
  mysql_exec "
    SELECT COUNT(*)
    FROM tb_shop
    WHERE id = ${SHOP_ID};
  "
)"

[[ "$SHOP_EXISTS" == "1" ]] \
  || fail "shop ${SHOP_ID} does not exist"

BASE_VOUCHER_ROW="$(
  mysql_exec "
    SELECT CONCAT_WS(
      '|',
      id,
      title,
      type,
      status,
      shop_id
    )
    FROM tb_voucher
    WHERE id = ${VOUCHER_ID};
  "
)"

SECKILL_VOUCHER_EXISTS="$(
  mysql_exec "
    SELECT COUNT(*)
    FROM tb_seckill_voucher
    WHERE voucher_id = ${VOUCHER_ID};
  "
)"

if [[ -n "$BASE_VOUCHER_ROW" ]]; then
  IFS='|' read -r \
    EXISTING_ID \
    EXISTING_TITLE \
    EXISTING_TYPE \
    EXISTING_STATUS \
    EXISTING_SHOP_ID \
    <<< "$BASE_VOUCHER_ROW"

  if [[ "$EXISTING_TITLE" != "$VOUCHER_TITLE" ]]; then
    fail \
      "existing voucher id is not owned by performance test: " \
      "id=${VOUCHER_ID}, title=${EXISTING_TITLE}"
  fi

  OWNERSHIP_STATUS="OWNED_EXISTING_VOUCHER"
else
  if [[ "$SECKILL_VOUCHER_EXISTS" != "0" ]]; then
    fail \
      "seckill voucher exists without owned base voucher"
  fi

  OWNERSHIP_STATUS="AVAILABLE_NEW_VOUCHER_ID"
fi

echo "MYSQL_CONTAINER=$MYSQL_CONTAINER"
echo "BUSINESS_DB=$BUSINESS_DB"
echo "VOUCHER_ID=$VOUCHER_ID"
echo "SHOP_ID=$SHOP_ID"
echo "STOCK=$STOCK"
echo "VOUCHER_TITLE=$VOUCHER_TITLE"
echo "OWNERSHIP_STATUS=$OWNERSHIP_STATUS"
echo "SECKILL_VOUCHER_EXISTS=$SECKILL_VOUCHER_EXISTS"

if (( DRY_RUN == 1 )); then
  echo
  echo "BOOTSTRAP_MODE = DRY_RUN"
  echo "DATABASE_MUTATION = NOT_EXECUTED"
  echo "TEST_VOUCHER_BOOTSTRAP_PREFLIGHT = PASS"
  exit 0
fi

if [[ "${ALLOW_TEST_VOUCHER_BOOTSTRAP:-}" != "YES" ]]; then
  fail \
    "set ALLOW_TEST_VOUCHER_BOOTSTRAP=YES " \
    "together with --apply"
fi

mysql_exec "
  START TRANSACTION;

  INSERT INTO tb_voucher (
    id,
    shop_id,
    title,
    sub_title,
    rules,
    pay_value,
    actual_value,
    type,
    status
  )
  VALUES (
    ${VOUCHER_ID},
    ${SHOP_ID},
    '${VOUCHER_TITLE}',
    '${VOUCHER_SUB_TITLE}',
    '${VOUCHER_RULES}',
    ${PAY_VALUE},
    ${ACTUAL_VALUE},
    1,
    1
  )
  ON DUPLICATE KEY UPDATE
    shop_id = VALUES(shop_id),
    title = VALUES(title),
    sub_title = VALUES(sub_title),
    rules = VALUES(rules),
    pay_value = VALUES(pay_value),
    actual_value = VALUES(actual_value),
    type = 1,
    status = 1,
    update_time = CURRENT_TIMESTAMP;

  INSERT INTO tb_seckill_voucher (
    voucher_id,
    stock,
    begin_time,
    end_time
  )
  VALUES (
    ${VOUCHER_ID},
    ${STOCK},
    DATE_SUB(NOW(), INTERVAL 1 DAY),
    DATE_ADD(NOW(), INTERVAL 30 DAY)
  )
  ON DUPLICATE KEY UPDATE
    stock = VALUES(stock),
    begin_time = VALUES(begin_time),
    end_time = VALUES(end_time),
    update_time = CURRENT_TIMESTAMP;

  COMMIT;
"

VERIFICATION_ROW="$(
  mysql_exec "
    SELECT CONCAT_WS(
      '|',
      v.id,
      v.title,
      v.type,
      v.status,
      v.shop_id,
      s.stock,
      DATE_FORMAT(s.begin_time, '%Y-%m-%d %H:%i:%s'),
      DATE_FORMAT(s.end_time, '%Y-%m-%d %H:%i:%s'),
      CASE
        WHEN NOW() < s.begin_time THEN 'NOT_STARTED'
        WHEN NOW() > s.end_time THEN 'EXPIRED'
        ELSE 'ACTIVE'
      END
    )
    FROM tb_voucher v
    JOIN tb_seckill_voucher s
      ON s.voucher_id = v.id
    WHERE v.id = ${VOUCHER_ID};
  "
)"

[[ -n "$VERIFICATION_ROW" ]] \
  || fail "dedicated voucher verification returned no row"

IFS='|' read -r \
  VERIFIED_ID \
  VERIFIED_TITLE \
  VERIFIED_TYPE \
  VERIFIED_STATUS \
  VERIFIED_SHOP_ID \
  VERIFIED_STOCK \
  VERIFIED_BEGIN_TIME \
  VERIFIED_END_TIME \
  VERIFIED_ACTIVITY_STATUS \
  <<< "$VERIFICATION_ROW"

[[ "$VERIFIED_TITLE" == "$VOUCHER_TITLE" ]] \
  || fail "voucher ownership marker verification failed"

[[ "$VERIFIED_TYPE" == "1" ]] \
  || fail "voucher type verification failed"

[[ "$VERIFIED_STATUS" == "1" ]] \
  || fail "voucher status verification failed"

[[ "$VERIFIED_STOCK" == "$STOCK" ]] \
  || fail "voucher stock verification failed"

[[ "$VERIFIED_ACTIVITY_STATUS" == "ACTIVE" ]] \
  || fail "voucher activity verification failed"

echo
echo "BOOTSTRAP_MODE = APPLY"
echo "VERIFIED_VOUCHER_ID=$VERIFIED_ID"
echo "VERIFIED_TITLE=$VERIFIED_TITLE"
echo "VERIFIED_TYPE=$VERIFIED_TYPE"
echo "VERIFIED_STATUS=$VERIFIED_STATUS"
echo "VERIFIED_SHOP_ID=$VERIFIED_SHOP_ID"
echo "VERIFIED_STOCK=$VERIFIED_STOCK"
echo "VERIFIED_BEGIN_TIME=$VERIFIED_BEGIN_TIME"
echo "VERIFIED_END_TIME=$VERIFIED_END_TIME"
echo "VERIFIED_ACTIVITY_STATUS=$VERIFIED_ACTIVITY_STATUS"
echo "TEST_VOUCHER_BOOTSTRAP = PASS"
