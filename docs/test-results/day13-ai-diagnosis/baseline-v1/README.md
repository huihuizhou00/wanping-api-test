# AI失败诊断 Baseline v1

本轮诊断输入未显式包含failure_layer、root_cause_tag、
root_cause、remediation和evidence_keywords等答案字段。

但部分title包含已确认根因，例如：

- Broker存储挂载丢失
- ThreadLocal未清理

因此本轮只能作为字段级无泄漏基线，不能作为严格的语义无泄漏基线。

## 自动指标

- Schema通过率：100%
- 故障层级准确率：80%
- 根因标签精确匹配率：0%
- 完全匹配率：0%
- 证据关键词平均召回率：35%

## 人工指标

- 完全正确：0
- 部分正确：4
- 证据不足：1
- 综合评分：16/30，53.33%
