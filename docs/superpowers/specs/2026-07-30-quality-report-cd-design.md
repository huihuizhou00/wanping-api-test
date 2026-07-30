# 万评统一质量报告站点与 GitHub Pages CD 设计

## 1. 背景

万评 API 测试项目已经包含 Java 接口自动化、AI Case 生成与评审、AI 失败诊断、确定性 CI、Self-hosted Ollama 评测，以及商铺查询和秒杀 Plus 性能回归。

现有测试结果分散在 JSON、Markdown、Allure 和 GitHub Actions 中，缺少统一的展示入口。

本阶段增加轻量级 CD：

> 当 `main` 分支的 `Deterministic CI` 成功后，自动汇总仓库内已经版本化的测试报告，生成静态质量站点，并发布到 GitHub Pages。

本阶段交付的是质量报告站点，不是万评业务系统。

## 2. 建设目标

1. 从版本化报告生成统一静态质量站点；
2. 通过 GitHub Pages 提供固定访问入口；
3. 只在 `main` 的 `Deterministic CI` 成功后自动发布；
4. 保证 CI 验证 Commit、CD 构建 Commit 和页面展示 Commit 一致；
5. 展示接口测试、AI 测试、性能回归和业务一致性结果；
6. 支持 `workflow_dispatch` 手动重新发布；
7. 不发布 Token、JTL、日志、`.env` 和真实凭证；
8. 更新 README 与架构文档，形成可复现的项目闭环。

## 3. 非目标范围

- 不部署 Spring Boot、MySQL、Redis、RocketMQ 或 Nginx；
- 不在 GitHub-hosted Runner 中执行真实 JMeter 压测；
- 不在 Pages CD 中启动 Ollama；
- 不要求 Self-hosted Runner 始终在线；
- 不修改现有 Pull Request Required Checks；
- 不维护 `gh-pages` 分支；
- 不在 CD 中修改数据库或 Redis 数据；
- 不重新计算性能阈值；
- 不发布 JTL、Token CSV、JMeter 日志和环境变量。

## 4. 现有工作流

确定性 CI：

```text
.github/workflows/ci.yml
name: Deterministic CI
```

AI 诊断评测：

```text
.github/workflows/ai-diagnosis-eval.yml
name: AI Diagnosis Evaluation
```

职责边界：

- `Deterministic CI` 是 Pages CD 的自动触发源；
- `AI Diagnosis Evaluation` 依赖 Self-hosted Runner 和 Ollama，不阻塞 Pages 发布；
- Pages 只展示已经版本化的 AI 评测结果。

## 5. 整体流程

```text
功能分支
→ Pull Request
→ Deterministic CI
→ Required Checks
→ 合并 main
→ main 对应 CI 成功
→ workflow_run 触发 Quality Report CD
→ 检出 workflow_run.head_sha
→ 生成静态质量站点
→ 上传 Pages Artifact
→ 部署 GitHub Pages
```

CI 判断代码是否满足合并要求，CD 发布已经通过验证的质量结果。

## 6. CD 触发设计

新增：

```text
.github/workflows/quality-report-cd.yml
```

核心触发：

```yaml
on:
  workflow_run:
    workflows:
      - Deterministic CI
    types:
      - completed
    branches:
      - main

  workflow_dispatch:
```

自动发布必须满足：

```text
workflow_run.conclusion == success
workflow_run.head_branch == main
```

自动发布检出：

```text
github.event.workflow_run.head_sha
```

从而保证：

```text
CI 验证 Commit
=
CD 构建 Commit
=
Pages 展示 Commit
```

手动触发时检出当前 `main`，用于重新发布和故障恢复。

## 7. GitHub Pages 发布

使用 GitHub 官方 Pages Actions：

```text
actions/configure-pages
actions/upload-pages-artifact
actions/deploy-pages
```

最小权限：

```yaml
permissions:
  contents: read
  pages: write
  id-token: write
```

并发控制：

```yaml
concurrency:
  group: pages
  cancel-in-progress: true
```

Pages 仓库配置：

```text
Settings
→ Pages
→ Build and deployment
→ Source
→ GitHub Actions
```

## 8. 报告清单

新增：

```text
quality-site/report-manifest.json
```

生成器只读取 Manifest 明确声明的报告。

必需报告：

```text
docs/test-results/day15-performance/shop-query-comparison.json
docs/test-results/day15-performance/shop-query-regression.md
docs/test-results/day15-performance/seckill-plus-comparison.json
docs/test-results/day15-performance/seckill-plus-regression.md
```

必需报告缺失、格式错误、字段非法或路径越界时，站点构建失败。

可选报告：

```text
docs/test-results/day12-ai-case-review/review-summary.json
docs/test-results/day12-ai-case-review/review-summary.md
docs/test-results/day13-ai-diagnosis/baseline-v2/diagnosis-evaluation.json
docs/test-results/day13-ai-diagnosis/baseline-v2/diagnosis-evaluation.md
```

可选报告缺失时显示 `UNAVAILABLE`，不伪造数据，也不阻止 Pages 发布。

## 9. 静态站点生成器

新增：

```text
scripts/reports/build_quality_site.py
scripts/reports/tests/test_build_quality_site.py
```

输出：

```text
build/quality-site/
```

生成流程：

```text
读取 Manifest
→ 校验报告路径
→ 读取版本化报告
→ 适配统一展示模型
→ 生成 index.html
→ 复制 CSS
→ 复制公开 Markdown
→ 生成 build-metadata.json
```

生成器不执行 JMeter、不调用 Ollama、不连接 MySQL 或 Redis，也不重新计算性能门禁。

## 10. 页面内容

首页展示：

```text
项目概览
├── 当前 Commit
├── 发布时间
├── 发布方式
├── 上游 CI 链接
├── 总体状态
├── 确定性测试
├── AI Case 生成与评审
├── AI 失败诊断评测
├── 商铺查询性能回归
├── 秒杀 Plus 性能回归
├── 业务一致性
└── 原始报告入口
```

支持状态：

```text
PASS
WARNING
FAIL
OBSERVE
UNAVAILABLE
```

页面必须保留源报告状态。

## 11. 当前性能结果

商铺查询：

```text
Baseline RPS：209.205
Candidate RPS：213.447
Baseline P95：8 ms
Candidate P95：8 ms
Baseline P99：16 ms
Candidate P99：9 ms
最终状态：PASS
```

秒杀 Plus：

```text
Baseline RPS：4.238
Candidate RPS：4.219
Baseline P95：3082 ms
Candidate P95：3054 ms
订单数：20
独立用户数：20
重复订单数：0
最终状态：PASS
```

页面需要说明：

> 秒杀 Plus 当前约 3 秒响应时间包含应用层异步订单确认等待，不能直接解释为 Lua 或 Redis 原子校验本身耗时。

实际页面指标必须从 JSON 读取，不能硬编码。

## 12. 路径与安全边界

报告路径必须：

- 使用仓库内相对路径；
- 不允许绝对路径和 Windows 盘符路径；
- 不允许包含 `..`；
- 不允许符号链接逃逸；
- 解析后的真实路径必须位于仓库根目录；
- 只能读取 Manifest 声明的文件。

禁止发布：

```text
*.jtl
jmeter.log
console.log
*token*.csv
.env
.env.*
*.pem
*.key
```

禁止发布真实 Bearer Token、密码、API Key、Secret 和 Access Token。

## 13. CI/CD Job

`build-site`：

```text
解析发布上下文
→ 检出目标 Commit
→ 配置 Python
→ 运行生成器测试
→ 构建站点
→ 冒烟检查
→ 敏感信息检查
→ 上传 Pages Artifact
```

`deploy-pages`：

```text
等待 build-site 成功
→ 使用 github-pages Environment
→ 部署 Pages
→ 输出 Pages URL
```

同时修改 `.github/workflows/ci.yml`，新增 `Quality site tests`，执行生成器测试、本地构建和安全检查，但不执行 JMeter、Ollama、数据库或 Redis 操作。

## 14. 异常处理

- 上游 CI 失败：不部署，保留上一成功版本；
- 必需报告缺失或格式错误：构建失败，不上传 Artifact；
- 可选报告缺失：显示 `UNAVAILABLE`，继续发布；
- Pages 部署失败：不回滚 `main`，可通过 `workflow_dispatch` 重试。

## 15. 测试范围

覆盖：

- Manifest 校验；
- 重复报告 ID；
- 非法报告类型；
- 绝对路径、`..` 和符号链接逃逸；
- 商铺查询和秒杀 Plus 报告适配；
- 业务一致性字段；
- 可选报告缺失；
- HTML 转义；
- Commit 与 CI 链接；
- 构建元数据；
- Markdown 和 CSS 复制；
- 站内链接；
- JTL、Token CSV、日志和真实凭证检查。

## 16. 计划目录

```text
.github/workflows/
├── ci.yml
├── ai-diagnosis-eval.yml
└── quality-report-cd.yml

quality-site/
├── report-manifest.json
└── assets/style.css

scripts/reports/
├── build_quality_site.py
├── check_quality_site.py
└── tests/

docs/architecture/
├── testing-architecture.md
├── ai-testing-flow.md
├── ci-cd-flow.md
└── performance-regression-flow.md

build/quality-site/
└── 本地或 CI 生成，不提交 Git
```

## 17. 实施顺序

```text
1. 创建 Manifest 与忽略规则
2. 实现 Manifest 校验和路径安全
3. 适配性能与 AI 报告
4. 生成 HTML、CSS 和构建元数据
5. 增加站点安全检查
6. 接入 Deterministic CI
7. 增加 GitHub Pages CD
8. 更新 README 与架构文档
9. 完成本地与线上验收
```

## 18. 完成标准

- 所有已有测试继续通过；
- 站点生成器测试全部通过；
- 本地可以生成 `build/quality-site`；
- 必需报告缺失会阻止构建；
- 可选报告缺失显示 `UNAVAILABLE`；
- 构建目录不存在敏感运行产物；
- `main` 的 `Deterministic CI` 成功后自动触发 CD；
- CD 发布上游 CI 对应的 `head_sha`；
- CI 失败时不执行 Pages 部署；
- Pages 首页可以访问；
- 商铺查询和秒杀 Plus 显示真实指标；
- README 命令与目录可以复现；
- Git 工作区最终保持干净。

## 19. 项目表达

> 为万评系统搭建覆盖接口自动化、AI 测试用例生成、失败诊断评测和性能回归的质量工程体系，通过 GitHub Actions 设置合并质量门禁，并在 `main` 验证成功后自动发布 GitHub Pages 质量报告，实现从测试设计、执行、诊断、评测到结果交付的 CI/CD 闭环。
