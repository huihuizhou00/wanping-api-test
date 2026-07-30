# 万评项目环境快照

## 1. 快照用途

该文档记录代码封版前主机环境，供后续迁移、故障排查和面试说明使用。

## 2. 系统环境

```text
操作系统：Ubuntu 20.04 系列
内核：Linux 5.15.0-139-generic
架构：amd64
默认区域：zh_CN
平台编码：UTF-8
```

## 3. Java 与 Maven

```text
OpenJDK：11.0.27
JVM：OpenJDK 64-Bit Server VM
Maven：Apache Maven 3.6.3
Maven Home：/usr/share/maven
Java Home：/usr/lib/jvm/java-11-openjdk-amd64
```

## 4. Python

```text
Python：3.12.9
虚拟环境解释器：
/home/zoey/.venvs/wanping-api-test/bin/python3
```

已验证依赖：

```text
jsonschema：4.26.0
PyYAML：6.0.3
```

项目依赖文件：

```text
ai-case-generator/requirements.txt
```

内容：

```text
openai>=1.40,<2
jsonschema>=4.20,<5
PyYAML>=6,<7
python-dotenv>=1.0,<2
```

## 5. Git

```text
Git：2.25.1
主分支：main
封版前审计 Commit：a3fbce2
远端：origin/main
```

## 6. JMeter

JMeter 已安装并能够执行性能测试。

当前审计命令的输出只截取到启动 Banner，未记录精确版本号。封版前建议补充：

```bash
jmeter --version 2>&1 | tail -20
```

## 7. 在线交付

```text
GitHub 仓库：
https://github.com/huihuizhou00/wanping-api-test

GitHub Pages：
https://huihuizhou00.github.io/wanping-api-test/
```

Pages 当前展示：

- 商铺查询性能回归：PASS；
- 秒杀 Plus 性能回归：PASS；
- AI Case 生成与人工评审：OBSERVE；
- AI 失败诊断评测：OBSERVE。

## 8. 分支完整性审计

Day13 AI 失败诊断：

```text
SQUASH_IN_MAIN=PASS
TREE_EQUIVALENT=PASS
```

Day15 JMeter 性能回归：

```text
SQUASH_IN_MAIN=PASS
TREE_EQUIVALENT=PASS
```

结论：旧功能分支内容已通过 Squash Merge 完整进入 `main`，不存在尚未进入主分支的代码功能。
