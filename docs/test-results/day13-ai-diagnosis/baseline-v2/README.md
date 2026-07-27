# AI失败诊断 Baseline v2

本轮在Baseline v1基础上修复了诊断标题的语义答案泄漏。

Gold Dataset保留用于缺陷复盘的原始title，同时新增只描述可观察故障现象的diagnosis_title。模型输入仅使用diagnosis_title。

本轮通过两类检查：

- 字段级答案泄漏检查
- 标题根因关键词语义泄漏检查

该版本作为后续模型、Prompt和证据输入优化的正式基线。
