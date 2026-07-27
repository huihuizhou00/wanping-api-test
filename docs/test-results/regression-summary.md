cat > docs/test-results/regression-summary.md <<'EOF'
# 万评核心接口自动化回归摘要

## 一、测试目标

本轮针对万评项目核心HTTP接口建立自动化回归能力，覆盖登录鉴权、商铺查询、商详聚合、优惠券查询、秒杀Plus异步下单和多用户并发防超卖场景。

测试不仅验证HTTP响应，还结合Redis、RocketMQ和MySQL进行灰盒断言，检查库存预扣、消息消费、订单落库和最终数据一致性。

## 二、测试技术

- Java 8
- Maven
- JUnit 5
- RestAssured
- Jackson
- Jedis
- JDBC
- Maven Surefire
- CountDownLatch
- ExecutorService

## 三、测试资产规模

### 常规回归

| 类型 | 数量 |
|---|---:|
| 常规自动化测试 | 23 |
| HTTP接口测试 | 22 |
| 测试框架冒烟测试 | 1 |
| 失败 | 0 |
| 错误 | 0 |
| 跳过 | 0 |

`FrameworkSmokeTest` 仅验证RestAssured和测试配置能否正确加载，不属于真实HTTP接口测试。

### 并发专项

| 类型 | 数量 |
|---|---:|
| 秒杀Plus防超卖专项 | 1 |
| 并发用户 | 20 |
| 并发请求 | 20 |
| 初始库存 | 5 |
| 成功请求 | 5 |
| 失败请求 | 15 |
| Redis最终库存 | 0 |
| MySQL最终库存 | 0 |
| MySQL最终订单 | 5 |

当前共形成24项自动化测试资产：
23条常规自动化
+
1条防超卖并发一致性专项

## Allure报告能力

项目已接入Allure JUnit 5适配器，并形成两类独立报告。

### 常规回归报告

- 测试数量：23
- 通过率：100%
- HTTP请求和响应附件
- 秒杀前后Redis与MySQL状态快照
- RocketMQ消费后的MySQL订单记录
- 重复下单前后无副作用证据
- 测试环境与本地执行器信息

### 防超卖并发专项报告

- 测试数量：1
- 并发用户：20
- 初始库存：5
- 成功请求：5
- 失败请求：15
- Redis最终库存：0
- MySQL最终库存：0
- MySQL最终订单：5

并发专项使用JUnit主线程生成聚合附件，不为20个ExecutorService工作线程分别生成HTTP附件。

### 报告产物

```text
docs/test-results/allure-report.zip
docs/test-results/allure-concurrency-report.zip