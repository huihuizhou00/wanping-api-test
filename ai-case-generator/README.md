# 万评AI结构化测试场景生成器

## 目标

基于已经验证的万评接口、Redis、MySQL和RocketMQ规则，通过OpenAI兼容模型生成24条结构化测试场景，并输出Schema通过率、业务规则通过率和人工采纳结果。

## 环境

```bash
cd ~/workspace/wanping-api-test/ai-case-generator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

复制配置：

```bash
cp .env.example .env
ollama list
```

根据 `ollama list` 修改 `.env` 中的 `AI_MODEL`。默认OpenAI兼容地址为：

```text
http://127.0.0.1:11434/v1
```

## 离线验证

```bash
python -m unittest discover -s tests -v
python -m src.generate_cases --dry-run
```

## 调用Ollama生成24条场景

```bash
python -m src.generate_cases --fail-on-invalid
```

输出：

```text
output/generated-cases.json
output/generated-cases.jsonl
output/generated-cases.csv
output/validation-summary.json
output/raw/
```

生成器按6个模块分批调用模型，降低一次输出24条造成截断的概率。

## 校验已有模型输出

```bash
python -m src.generate_cases \
  --input output/raw-model-response.json \
  --fail-on-invalid
```

## 人工审核

打开 `output/generated-cases.csv`，修改：

```text
business_review_status=pending/accepted/rejected/revised
review_comment=采纳理由、拒绝理由或修改内容
```

统计结果：

```bash
python -m src.review_summary output/generated-cases.csv
```

输出：

```text
output/review-summary.md
output/review-summary.json
```

## 边界

- Schema通过只表示结构正确，不代表业务正确。
- 业务校验只使用 `config/api_rules.yaml` 中的已验证规则。
- AI候选场景不会自动修改或执行Java测试代码。
