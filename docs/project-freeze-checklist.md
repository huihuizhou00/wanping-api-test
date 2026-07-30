# 万评项目封版清单

## A. 代码与分支

- [ ] `main` 与 `origin/main` 一致
- [ ] 工作区干净
- [ ] Day13 分支完整性审计通过
- [ ] Day15 分支完整性审计通过
- [ ] 不存在需要继续合并的功能代码
- [ ] 旧分支在 Bundle 和 Tag 完成后再删除

## B. 依赖与迁移

- [ ] `ai-case-generator/requirements.txt` 内容完整
- [ ] Python 虚拟环境可重新创建
- [ ] 关键依赖导入成功
- [ ] `docs/migration-guide.md` 已提交
- [ ] `docs/environment-snapshot.md` 已提交
- [ ] 私密配置清单已单独保存
- [ ] 被测万评业务项目源码已备份
- [ ] MySQL 表结构或必要数据已备份

## C. 最终验证

- [ ] 质量站点测试通过
- [ ] 性能工具测试通过
- [ ] AI Case Generator 测试通过
- [ ] Java `test-compile` 通过
- [ ] 真实质量站点本地构建通过
- [ ] 质量站点安全检查通过
- [ ] Git 工作区最终干净

## D. 线上交付

- [ ] `main` 的 Deterministic CI 成功
- [ ] Quality Report CD 成功
- [ ] GitHub Pages 可访问
- [ ] 页面 Commit 与 `main` HEAD 一致
- [ ] 商铺查询状态为 PASS
- [ ] 秒杀 Plus 状态为 PASS
- [ ] AI Case 状态如实显示为 OBSERVE
- [ ] AI 失败诊断状态如实显示为 OBSERVE

## E. 封版发布

- [ ] 创建 `v1.0.0-quality-closure` Tag
- [ ] 推送 Tag
- [ ] 创建 GitHub Release
- [ ] Release 中记录测试结果和 Pages 地址
- [ ] 记录最终 Commit SHA

## F. 离线备份

- [ ] 创建 `wanping-api-test-complete.bundle`
- [ ] 验证 Git Bundle
- [ ] 为被测业务项目创建 Git Bundle
- [ ] 备份关键配置与数据库结构
- [ ] 备份最终验收日志
- [ ] 将备份复制到另一块硬盘或云盘

## G. 代码冻结

- [ ] 不再新增功能
- [ ] 不再重构
- [ ] 不再调整性能阈值
- [ ] 不为了页面美观修改 AI 评测结果
- [ ] 只允许修复无法克隆、无法安装、CI 完全失败等阻断问题
- [ ] 后续工作转入简历、投递、模拟面试和八股复习
