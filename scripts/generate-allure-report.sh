#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.." \
  && pwd
)"

cd "${PROJECT_ROOT}"

RESULTS_DIR="target/allure-results"
REPORT_DIR="target/allure-report"
REPORT_ARCHIVE="docs/test-results/allure-report.zip"
EXPECTED_TEST_COUNT=23

if ! command -v allure >/dev/null 2>&1; then
    echo "错误：未找到allure命令。"
    echo '请确认$HOME/tools/allure/bin已经加入PATH。'
    exit 1
fi

if ! command -v mvn >/dev/null 2>&1; then
    echo "错误：未找到mvn命令。"
    exit 1
fi

echo "========================================"
echo "运行万评23条常规自动化测试"
echo "========================================"

mvn clean test \
  -Dsurefire.useFile=false

RESULT_COUNT="$(
  find "${RESULTS_DIR}" \
    -maxdepth 1 \
    -name '*-result.json' \
    | wc -l
)"

RESULT_COUNT="$(
  echo "${RESULT_COUNT}" \
  | tr -d '[:space:]'
)"

echo "Allure测试结果数量：${RESULT_COUNT}"

if [ "${RESULT_COUNT}" -ne "${EXPECTED_TEST_COUNT}" ]; then
    echo "错误：预期生成${EXPECTED_TEST_COUNT}个测试结果，实际为${RESULT_COUNT}。"
    exit 1
fi

echo "========================================"
echo "写入测试环境信息"
echo "========================================"

JAVA_VERSION="$(
  java -version 2>&1 \
  | head -n 1
)"

MAVEN_VERSION="$(
  mvn -Dstyle.color=never -version 2>&1 \
  | head -n 1 \
  | sed -E 's/\x1B\[[0-9;]*[mK]//g'
)"

OS_VERSION="$(
  if command -v lsb_release >/dev/null 2>&1; then
      lsb_release -ds
  else
      uname -sr
  fi
)"

cat > "${RESULTS_DIR}/environment.properties" <<ENVEOF
Project=wanping-api-test
Test_Scope=23_regular_automation_tests
Backend_URL=http://127.0.0.1:8082
Java=${JAVA_VERSION}
Maven=${MAVEN_VERSION}
Operating_System=${OS_VERSION}
Redis_Database=1
Database=MySQL
Message_Queue=RocketMQ
Test_Framework=JUnit_5_and_RestAssured
Report_Type=Regular_Regression
Concurrency_Profile=Excluded
ENVEOF

cat > "${RESULTS_DIR}/executor.json" <<'JSONEOF'
{
  "name": "Local Maven",
  "type": "local",
  "buildName": "万评核心接口常规回归",
  "buildOrder": 1,
  "reportName": "万评API自动化测试报告"
}
JSONEOF

echo "========================================"
echo "生成Allure HTML报告"
echo "========================================"

allure generate \
  "${RESULTS_DIR}" \
  --clean \
  --output "${REPORT_DIR}"

if [ ! -f "${REPORT_DIR}/index.html" ]; then
    echo "错误：未生成${REPORT_DIR}/index.html"
    exit 1
fi

mkdir -p docs/test-results

rm -f "${REPORT_ARCHIVE}"

(
  cd target
  zip -qr \
    "../${REPORT_ARCHIVE}" \
    allure-report
)

echo
echo "========================================"
echo "Allure报告生成成功"
echo "========================================"
echo "原始结果：${RESULTS_DIR}"
echo "HTML报告：${REPORT_DIR}"
echo "归档文件：${REPORT_ARCHIVE}"
echo "测试数量：${RESULT_COUNT}"
echo
echo "浏览报告："
echo "allure open ${REPORT_DIR}"
