
---

# 核心接口自动化测试

## 测试范围

当前覆盖：

- 登录与Token鉴权
- 商铺ID、名称和类型查询
- 商详聚合
- 店铺优惠券查询
- 秒杀Plus异步下单
- Redis与MySQL灰盒断言

当前测试规模：

```text
23条自动化测试
= 22条HTTP接口测试
+ 1条框架冒烟测试

## Allure测试报告

### 常规回归报告

运行23条常规自动化并生成Allure报告：

```bash
./scripts/generate-allure-report.sh
