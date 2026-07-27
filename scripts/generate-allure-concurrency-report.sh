#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.." \
  && pwd
)"

cd "${PROJECT_ROOT}"

RESULTS_DIR="target/allure-results"
REPORT_DIR="target/allure-report-concurrency"
REPORT_ARCHIVE="docs/test-results/allure-concurrency-report.zip"
EXPECTED_TEST_COUNT=1

if ! command -v allure >/dev/null 2>&1; then
    echo "错误：未找到allure命令。"
    exit 1
fi

echo "========================================"
echo "运行秒杀Plus防超卖并发专项"
echo "========================================"

mvn clean test \
  -Pconcurrency \
  -Dsurefire.useFile=false

RESULT_COUNT="$(
  find "${RESULTS_DIR}" \
    -maxdepth 1 \
    -name '*-result.json' \
    | wc -l \
    | tr -d '[:space:]'
)"

if [ "${RESULT_COUNT}" -ne "${EXPECTED_TEST_COUNT}" ]; then
    echo "错误：预期1个专项结果，实际为${RESULT_COUNT}。"
    exit 1
fi

JAVA_VERSION="$(
  java -version 2>&1 \
  | head -n 1
)"

MAVEN_VERSION="$(
  mvn -Dstyle.color=never -version 2>&1 \
  | head -n 1 \
  | sed -E 's/\x1B\[[0-9;]*[mK]//g'
)"

cat > "${RESULTS_DIR}/environment.properties" <<ENVEOF
Project=wanping-api-test
Test_Scope=seckill_plus_oversell_concurrency
Backend_URL=http://127.0.0.1:8082
Java=${JAVA_VERSION}
Maven=${MAVEN_VERSION}
Redis_Database=1
Database=MySQL
Message_Queue=RocketMQ
Concurrent_Users=20
Concurrent_Requests=20
Initial_Stock=5
Expected_Success=5
Expected_Failure=15
Report_Type=Concurrency_Consistency
ENVEOF

cat > "${RESULTS_DIR}/executor.json" <<'JSONEOF'
{
  "name": "Local Maven",
  "type": "local",
  "buildName": "秒杀Plus防超卖并发专项",
  "buildOrder": 1,
  "reportName": "万评秒杀Plus防超卖并发测试报告"
}
JSONEOF

allure generate \
  "${RESULTS_DIR}" \
  --clean \
  --output "${REPORT_DIR}"

test -f "${REPORT_DIR}/index.html"

mkdir -p docs/test-results
rm -f "${REPORT_ARCHIVE}"

(
  cd target
  zip -qr \
    "../${REPORT_ARCHIVE}" \
    allure-report-concurrency
)

echo
echo "并发专项Allure报告生成成功"
echo "测试数量：${RESULT_COUNT}"
echo "HTML报告：${REPORT_DIR}"
echo "归档文件：${REPORT_ARCHIVE}"
echo
echo "查看报告："
echo "allure open ${REPORT_DIR}"
