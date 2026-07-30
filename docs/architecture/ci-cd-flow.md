# CI/CD 流程

## 流程图

```mermaid
flowchart LR
    A[Feature Branch]
    --> B[Pull Request]
    --> C[Deterministic CI]
    --> D{Required Checks}
    D -->|失败| E[禁止合并]
    D -->|通过| F[Merge main]
    F --> G[main Deterministic CI]
    G -->|失败| H[不发布]
    G -->|成功| I[workflow_run]
    I --> J[Checkout head_sha]
    J --> K[Build Quality Site]
    K --> L[Security Check]
    L --> M[Pages Artifact]
    M --> N[GitHub Pages]
```

## CI 与 CD 边界

### Deterministic CI

负责：

- 仓库安全检查；
- Python 测试；
- Java 测试代码编译；
- 质量站点生成器测试；
- 本地质量站点构建与检查。

### Quality Report CD

负责：

- 接收 `main` 上成功的 CI 事件；
- 检出 `workflow_run.head_sha`；
- 生成质量站点；
- 上传 Pages Artifact；
- 发布 GitHub Pages。

CD 不连接业务数据库，也不执行真实 JMeter 或 Ollama。
