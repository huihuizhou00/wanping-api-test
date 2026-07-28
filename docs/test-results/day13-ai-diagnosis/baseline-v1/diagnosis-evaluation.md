# AI失败诊断首轮评估报告

## 一、评估信息

- 模型：qwen2.5:7b
- 故障样本数：5

## 二、确定性指标

- Schema通过率：5/5（100.00%）
- 故障层级准确率：4/5（80.00%）
- 根因标签准确率：0/5（0.00%）
- 层级与标签完全匹配率：0/5（0.00%）
- 平均证据关键词召回率：35.00%

## 三、人工复核

- 需要人工复核根因文本：5/5
- 说明：结构化指标由程序计算，自由文本因果关系仍需人工确认。

## 四、逐条结果

### DEFECT-001

- Schema通过：True
- 故障层级：期望 `application`，实际 `application`，命中=True
- 根因标签：期望 `INTERCEPTOR_ROUTING`，实际 `BUSINESS_LOGIC_ERROR`，命中=False
- 证据关键词召回：2/4（50.00%）

### DEFECT-002

- Schema通过：True
- 故障层级：期望 `application`，实际 `middleware`，命中=False
- 根因标签：期望 `ASYNC_DEGRADATION`，实际 `ASYNC_TASK_FAILURE`，命中=False
- 证据关键词召回：3/4（75.00%）

### DEFECT-003

- Schema通过：True
- 故障层级：期望 `middleware`，实际 `middleware`，命中=True
- 根因标签：期望 `BROKER_STORAGE_NOT_WRITABLE`，实际 `STORAGE_LOSS`，命中=False
- 证据关键词召回：0/4（0.00%）

### DEFECT-004

- Schema通过：True
- 故障层级：期望 `cache`，实际 `cache`，命中=True
- 根因标签：期望 `CACHE_REBUILD_AND_WRONG_UNLOCK_KEY`，实际 `CACHE_REBUILD_FAILURE`，命中=False
- 证据关键词召回：0/5（0.00%）

### DEFECT-005

- Schema通过：True
- 故障层级：期望 `context`，实际 `context`，命中=True
- 根因标签：期望 `THREADLOCAL_CONTEXT_LEAK`，实际 `CONTEXT_THREADLOCAL_NOT_CLEANED`，命中=False
- 证据关键词召回：3/6（50.00%）
