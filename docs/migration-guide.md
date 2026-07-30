# 万评 AI 测试与质量工程迁移指南

## 1. 文档目的

本指南用于在更换主机后恢复 `wanping-api-test` 项目，并确保接口测试、AI Case Generator、性能工具测试、质量站点和 GitHub Actions 配置可以继续被理解与验证。

项目已经进入功能冻结阶段。迁移后的首要目标是“可读取、可安装、可验证、可展示”，而不是继续新增功能。

## 2. 项目入口

- GitHub 仓库：`https://github.com/huihuizhou00/wanping-api-test`
- GitHub Pages：`https://huihuizhou00.github.io/wanping-api-test/`
- 默认分支：`main`
- 封版前审计 Commit：`a3fbce2`
- 计划封版 Tag：`v1.0.0-quality-closure`

封版 Tag 创建后，应优先使用 Tag 作为固定恢复点。

## 3. 当前环境基线

| 组件 | 当前环境 |
|---|---|
| 操作系统 | Ubuntu 20.04 系列，Linux 5.15，amd64 |
| Java | OpenJDK 11.0.27 |
| Maven | Apache Maven 3.6.3 |
| Python | Python 3.12.9 |
| Python 虚拟环境 | `~/.venvs/wanping-api-test` |
| Git | Git 2.25.1 |
| JMeter | 已安装；当前审计日志未截取到精确版本号 |
| 页面发布 | GitHub Pages + GitHub Actions |

JMeter 精确版本可在旧主机执行：

```bash
jmeter --version 2>&1 | tail -20
```

## 4. 新主机推荐环境

优先使用 Linux 或 WSL2，推荐：

- JDK 11；
- Maven 3.6+；
- Python 3.12；
- Git；
- Apache JMeter；
- 可选：Docker、MySQL、Redis、RocketMQ，用于启动被测万评业务系统。

确定性测试和质量站点生成不要求连接 MySQL、Redis、RocketMQ 或 Ollama。

真实接口测试与 JMeter 性能回归需要被测服务及对应基础设施。

## 5. 克隆与恢复

### 5.1 从 GitHub 克隆

```bash
git clone   https://github.com/huihuizhou00/wanping-api-test.git

cd wanping-api-test

git fetch --all --tags
git checkout v1.0.0-quality-closure
```

若封版 Tag 尚未创建，可临时使用：

```bash
git checkout main
```

### 5.2 从 Git Bundle 恢复

```bash
git clone   wanping-api-test-complete.bundle   wanping-api-test

cd wanping-api-test
git fetch --all --tags
```

## 6. Python 环境恢复

仓库已经提供：

```text
ai-case-generator/requirements.txt
```

依赖范围：

```text
openai>=1.40,<2
jsonschema>=4.20,<5
PyYAML>=6,<7
python-dotenv>=1.0,<2
```

创建独立虚拟环境：

```bash
python3 -m venv   "$HOME/.venvs/wanping-api-test"

source   "$HOME/.venvs/wanping-api-test/bin/activate"

python -m pip install   --upgrade pip setuptools wheel

python -m pip install   -r ai-case-generator/requirements.txt
```

验证关键依赖：

```bash
python - <<'PY'
import jsonschema
import yaml
import openai
import dotenv

print("PYTHON_DEPENDENCY_CHECK = PASS")
PY
```

## 7. Java 环境恢复

检查环境：

```bash
java -version
mvn -version
```

编译测试代码：

```bash
mvn   --batch-mode   --no-transfer-progress   -DskipTests   test-compile
```

## 8. 本地验证命令

### 8.1 AI Case Generator

```bash
source   "$HOME/.venvs/wanping-api-test/bin/activate"

(
  cd ai-case-generator

  python -m unittest discover     -s tests     -p "test_*.py"     -v
)
```

### 8.2 性能工具测试

```bash
python -m unittest discover   -s scripts/performance/tests   -p "test_*.py"   -v
```

### 8.3 质量站点测试

```bash
python -m unittest discover   -s scripts/reports/tests   -p "test_*.py"   -v
```

### 8.4 本地生成质量站点

```bash
PUBLISHED_AT="$(
  date -u +%Y-%m-%dT%H:%M:%SZ
)"

python scripts/reports/build_quality_site.py   --repository-root .   --manifest quality-site/report-manifest.json   --output build/quality-site   --commit-sha "$(git rev-parse HEAD)"   --branch "$(git branch --show-current)"   --publish-mode local   --ci-run-url ""   --published-at "$PUBLISHED_AT"   --repository wanping-api-test

python scripts/reports/check_quality_site.py   --site build/quality-site
```

生成入口：

```text
build/quality-site/index.html
```

## 9. GitHub Actions

### Deterministic CI

文件：

```text
.github/workflows/ci.yml
```

负责：

- 仓库安全检查；
- Python 确定性测试；
- Java 测试代码编译；
- 质量站点测试、构建和安全检查。

### AI Diagnosis Evaluation

文件：

```text
.github/workflows/ai-diagnosis-eval.yml
```

依赖 Self-hosted Runner 和 Ollama，不阻塞 Pull Request Required Checks。

### Quality Report CD

文件：

```text
.github/workflows/quality-report-cd.yml
```

`main` 上的 Deterministic CI 成功后，通过 `workflow_run` 触发，并使用上游 `head_sha` 构建和发布 GitHub Pages。

## 10. 被测系统与外部服务

`wanping-api-test` 是测试工程，不包含完整被测业务服务。

换机时还需要保存或重新获取：

- 万评业务系统源码仓库；
- MySQL 表结构与必要基础数据；
- Redis、RocketMQ、Nginx 等环境配置；
- JMeter 实际执行所需的服务地址；
- 不可提交的本地环境变量和账号配置。

性能回归使用的专用测试券：

```text
900013
```

性能测试用户使用高位测试 ID，避免与普通业务用户冲突。

## 11. 私密配置迁移

禁止提交到 GitHub：

- `.env`；
- API Key；
- GitHub Token；
- 数据库密码；
- Bearer Token；
- SSH 私钥；
- Ollama 或模型服务私有配置。

建议使用密码管理器或加密压缩包保存，并记录：

```text
配置名称
用途
原主机路径
新主机目标路径
关联服务
是否必须
```

## 12. 不需要迁移的运行产物

通常不需要复制：

- `target/`；
- `build/quality-site/`；
- `__pycache__/`；
- 临时 Token CSV；
- JMeter 日志；
- 重复 JTL；
- Redis 缓存；
- 可由脚本重新生成的专用测试数据。

需要保留的证据：

- 版本化 comparison JSON；
- regression Markdown；
- 最终测试截图；
- 关键验收日志；
- GitHub Pages 地址；
- 封版 Tag 和 Release。

## 13. 最小恢复验收

新主机完成以下检查即可证明迁移成功：

```text
1. 可以检出 v1.0.0-quality-closure
2. Python 依赖安装成功
3. AI Case Generator 测试通过
4. 性能工具测试通过
5. Java test-compile 通过
6. 质量站点可以本地生成
7. GitHub Pages 可以访问
```

真实接口测试和 JMeter 压测可以在被测服务环境恢复后再执行，不影响代码封版。
