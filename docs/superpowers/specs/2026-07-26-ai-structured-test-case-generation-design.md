# AI结构化测试场景生成设计

## 目标

在现有 `wanping-api-test` 仓库中增加独立的 Python 测试设计辅助工具。工具根据已经验证的万评接口、Redis、MySQL和异步链路规则，通过 OpenAI 兼容接口调用 Ollama 或在线模型，生成不少于20条结构化测试场景，并完成 JSON Schema 校验、基础业务规则校验、JSONL/CSV导出和人工审核统计。

## 边界

- 不修改或执行现有Java自动化测试代码。
- 不使用Web搜索补充业务规则。
- 不允许模型发明接口、Redis Key、数据库表或错误文案。
- AI输出只作为测试设计候选，必须保留人工审核状态。
- 第一版固定生成24条：登录鉴权4、商铺查询4、商详与优惠券4、秒杀Plus7、缓存与异步3、并发与一致性2。

## 架构

```text
已验证的接口与业务规则YAML
→ 按模块构建Prompt
→ OpenAI兼容模型接口
→ 原始JSON结果
→ JSON Schema校验
→ 业务规则校验
→ JSONL/CSV候选场景
→ 人工审核
→ 通过率与采纳率摘要
```

生成器按模块分批调用模型，避免一次生成24条导致输出截断。各模块结果合并后统一校验和导出。

## 组件

- `config/api_rules.yaml`：接口、鉴权、错误文案、Redis和MySQL规则的唯一事实来源。
- `config/generator.yaml`：生成数量、模块配额、温度、重试次数。
- `schemas/test-case-batch.schema.json`：约束AI原始输出结构。
- `prompts/generate_cases.txt`：约束模型只基于规则生成JSON。
- `src/model_client.py`：OpenAI兼容模型调用。
- `src/validators.py`：Schema与业务规则校验。
- `src/exporters.py`：JSONL、CSV和校验摘要输出。
- `src/generate_cases.py`：命令行入口，按模块生成并汇总。
- `src/review_summary.py`：统计格式通过率、业务通过率和人工采纳率。

## 输出字段

AI生成字段：`case_id`、`module`、`title`、`priority`、`test_type`、`endpoint`、`method`、`preconditions`、`request`、`expected_http_status`、`expected_business_result`、`redis_assertions`、`mysql_assertions`、`risk_tags`、`source_rules`。

工具补充字段：`schema_valid`、`business_valid`、`validation_errors`、`business_review_status`、`review_comment`。

## 校验策略

Schema校验负责字段、类型、枚举和必填项。业务校验负责接口与HTTP方法匹配、鉴权逻辑、已知错误文案、路径参数错误、秒杀成功场景的数据断言、并发防超卖边界和模块配额。Schema通过不代表业务正确。

## 错误处理

模型输出无法解析、数量不符或模块不符时，最多重试2次，并把错误反馈给模型。最终仍失败时保存原始响应并终止生成。全局校验完成后，即使个别场景不合格，也输出全部候选及错误，便于统计格式通过率和人工审核。

## 验收标准

- 能使用OpenAI兼容接口调用本地Ollama。
- 生成24条候选场景，且不少于20条。
- 输出JSONL和CSV。
- 输出Schema与业务校验摘要。
- CSV包含人工采纳状态和未采纳原因字段。
- 单元测试覆盖合法数据、未知接口、重复用例ID和并发边界缺失。
