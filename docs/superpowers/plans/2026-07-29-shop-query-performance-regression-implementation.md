# Shop Query Performance Regression Implementation Plan

## Goal

对商铺查询接口执行三轮 Candidate 性能测试，取三轮指标中位数，与既有基线自动比较，并生成 PASS、WARNING 或 FAIL 结论。

## Fixed Workload

测试接口：

    GET http://127.0.0.1:8082/shop/of/type?typeId=1&current=1

每轮配置：

- 预热：5 线程、1 秒 Ramp-up、每线程 4 次，共 20 个样本
- 正式测试：20 线程、2 秒 Ramp-up、每线程 20 次，共 400 个样本
- Candidate 总轮数：3
- 每轮间隔：10 秒

## Existing Baseline

- Throughput：209.205 RPS
- Mean：6.595 ms
- Median：6 ms
- P90：8 ms
- P95：8 ms
- P99：16 ms
- Max：57 ms
- Error Rate：0%
- Status：provisional

## Regression Rules

### Hard Gates

- 样本数必须等于 400
- 错误率不得超过 1%
- 吞吐量下降不得超过 15%
- P95 上升不得超过 20%

当前硬门禁边界：

- Throughput 不得低于 177.824 RPS
- P95 不得高于 9.6 ms
- 由于 JMeter 响应时间为整数毫秒，P95 小于等于 9 ms 通过，达到 10 ms 时失败

### Warning Gate

- P99 上升超过 25% 时输出 WARNING
- 当前 P99 警告线为 20 ms

### Observe Metric

- Max 只记录，不参与 PASS、WARNING 或 FAIL 判定

### Status and Exit Code

- PASS：退出码 0
- WARNING：退出码 0
- FAIL：退出码 1
- 状态优先级为 FAIL、WARNING、PASS

## Existing Components

复用以下已有资产：

    performance/jmeter/plans/shop-query.jmx
    scripts/performance/extract_jmeter_metrics.py
    scripts/performance/run_shop_baseline_round.sh
    performance/baselines/shop-query.json

JMeter 原始结果保存在：

    /mnt/wanping-performance/runs

真实 JTL、JMeter 日志、控制台日志和 Token CSV 不进入 Git。

## Task 1: Candidate Aggregator

创建文件：

    scripts/performance/build_shop_candidate.py
    scripts/performance/tests/test_build_shop_candidate.py

职责：

- 读取三轮 Candidate JSON
- 检查每轮 scenario 为 shop-query
- 检查每轮 run_type 为 candidate
- 检查每轮 sample_count 为 400
- 检查每轮 error_count 为 0
- 对指定指标计算三轮中位数
- 输出 performance/candidates/shop-query.json

中位数字段：

- throughput_rps
- mean_ms
- median_ms
- p90_ms
- p95_ms
- p99_ms
- max_ms

固定字段：

- sample_count：400
- error_count：0
- error_rate：0.0
- round_count：3
- status：provisional
- candidate_method：median_of_three_rounds

采用 TDD：

    编写失败测试
    运行测试确认 RED
    实现最小功能
    运行测试确认 GREEN
    提交代码

## Task 2: Performance Comparator

创建文件：

    scripts/performance/compare_performance.py
    scripts/performance/tests/test_compare_performance.py

职责：

- 读取基线和 Candidate JSON
- 检查两者 scenario 一致
- 检查两者 load_model 一致
- 检查必要 metrics 字段完整
- 计算吞吐量下降比例
- 计算 P95 上升比例
- 计算 P99 上升比例
- 输出逐项检查结果
- 汇总最终 PASS、WARNING 或 FAIL

必须覆盖以下测试：

- 所有指标满足阈值时返回 PASS
- P99 超过警告线时返回 WARNING
- 样本数不等于 400 时返回 FAIL
- 错误率超过 1% 时返回 FAIL
- 吞吐量下降超过 15% 时返回 FAIL
- P95 上升超过 20% 时返回 FAIL
- 场景不一致时拒绝比较
- 负载模型不一致时拒绝比较
- 基线关键指标小于等于 0 时拒绝比较

## Task 3: Markdown Report

修改文件：

    scripts/performance/compare_performance.py
    scripts/performance/tests/test_compare_performance.py

输出文件：

    docs/test-results/day15-performance/shop-query-comparison.json
    docs/test-results/day15-performance/shop-query-regression.md

Markdown 报告必须包含：

- Final Status
- Fixed Load Model
- Baseline Metrics
- Candidate Metrics
- Regression Checks
- Environment Warnings
- Raw Artifact Policy

指标比较表必须包含：

- Metric
- Baseline
- Candidate
- Change
- Threshold
- Status

## Task 4: Candidate Runner

创建文件：

    scripts/performance/run_shop_candidate_round.sh

调用方式：

    scripts/performance/run_shop_candidate_round.sh <round-number>

必须与基线保持一致：

- 使用同一个 shop-query.jmx
- 目标地址为 127.0.0.1:8082
- 预热为 5 线程、1 秒 Ramp-up、每线程 4 次
- 正式测试为 20 线程、2 秒 Ramp-up、每线程 20 次
- 连接超时为 3000 ms
- 响应超时为 10000 ms
- 每轮正式样本数为 400

每轮输出：

    performance/candidates/runs/shop-query-round<N>.json

每轮运行前检查：

- /mnt/wanping-performance 已挂载
- 根分区使用率低于 95%
- /jvm/status 中故障注入全部关闭
- JMX 文件存在
- 指标提取器存在

每轮验收：

- JMeter 退出码为 0
- Warm-up 样本数为 20
- Warm-up 错误数为 0
- 正式样本数为 400
- 正式错误数为 0
- 指标提取成功

## Task 5: Execute Three Candidate Rounds

执行顺序：

    Candidate Round 1
    等待 10 秒
    Candidate Round 2
    等待 10 秒
    Candidate Round 3
    构建 Candidate 三轮中位数

输出：

    performance/candidates/runs/shop-query-round1.json
    performance/candidates/runs/shop-query-round2.json
    performance/candidates/runs/shop-query-round3.json
    performance/candidates/shop-query.json

## Task 6: Compare and Archive Report

比较器输入：

    performance/baselines/shop-query.json
    performance/candidates/shop-query.json

比较器输出：

    docs/test-results/day15-performance/shop-query-comparison.json
    docs/test-results/day15-performance/shop-query-regression.md

退出码规则：

- PASS 返回 0
- WARNING 返回 0
- FAIL 返回 1

环境异常不能被解释为代码性能退化。出现以下情况时应立即停止：

- JMeter 执行失败
- JTL 样本数不正确
- JTL 存在失败样本
- JVM 故障注入未关闭
- 性能结果盘未挂载
- 基线与 Candidate 场景不同
- 基线与 Candidate 负载不同
- 三轮 Candidate 文件不完整

## Task 7: Final Verification

执行以下检查：

- 全部 Python 单元测试通过
- Python 文件语法检查通过
- Bash 脚本语法检查通过
- JSON 格式检查通过
- git diff --check 无输出
- Git 暂存区中没有真实 JTL
- Git 暂存区中没有 Token CSV
- Git 暂存区中没有 JMeter 运行日志
- 固定测试夹具 sample-result.jtl 可以提交
- 最终性能报告文件存在

最终交付：

- 参数化 JMeter 计划
- 商铺查询三轮基线
- 商铺查询三轮 Candidate
- Candidate 汇总器
- 性能比较器
- JSON 比较结果
- Markdown 性能回归报告
- 运行产物隔离规则
