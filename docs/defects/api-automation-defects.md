# 万评核心接口自动化缺陷记录

## 缺陷概览

| 编号 | 模块 | 缺陷描述 | 严重程度 | 状态 |
|---|---|---|---|---|
| DEFECT-001 | 登录拦截与异常处理 | 参数异常经过 `/error` 二次分发后被错误返回401 | 中 | 已修复 |
| DEFECT-002 | 商详与评分刷新 | 辅助MQ刷新失败导致商详主接口失败 | 高 | 已修复 |
| DEFECT-003 | RocketMQ运行环境 | Broker存储挂载丢失后进入不可写状态 | 高 | 已恢复 |
| DEFECT-004 | 商铺缓存 | 逻辑过期重建释放错Key，且缓存缺失无法自动回源 | 高 | 已修复 |
| DEFECT-005 | 登录状态管理 | ThreadLocal未清理导致无Token请求继承历史用户身份 | 高 | 已修复 |

## DEFECT-001 参数异常请求被错误返回401

- 模块：统一异常处理、登录拦截器
- 发现方式：商铺查询接口自动化
- 复现接口：GET /shop/of/type?current=1
- 实际结果：缺少typeId时，无Token或过期Token返回HTTP 401；有效Token返回HTTP 400
- 预期结果：参数错误与Token状态无关，统一返回HTTP 400
- 根因：Spring参数解析异常后转发至/error，LoginInterceptor再次拦截/error请求
- 修复：在MvcConfig中将/error加入登录拦截器排除路径
- 回归结果：无Token、过期Token和有效Token场景均稳定返回HTTP 400
- 状态：已修复并回归通过

## DEFECT-002 商铺详情因评分刷新MQ失败返回服务器异常

- 模块：商详聚合、店铺评分刷新
- 复现接口：GET /shop/detail/1
- 实际结果：商详数据已经聚合完成，但RocketMQ评分刷新消息发送失败后，接口返回success=false
- 预期结果：评分刷新属于辅助异步任务，其失败不应影响商详主链路
- 根因：ShopRatingRefreshServiceImpl.triggerIfExpired中的syncSend异常直接向上抛出
- 修复：对评分刷新消息发送增加异常捕获和降级日志，不影响商详响应
- 验证：删除临时评分刷新时间Key，真实覆盖MQ发送失败分支，商详接口仍返回成功
- 状态：已修复并回归通过

## DEFECT-003 RocketMQ Broker存储挂载丢失导致秒杀Plus发送失败

- 模块：RocketMQ、秒杀Plus异步建单
- 复现接口：POST /voucher-order/seckill-plus/12
- 实际结果：返回“下单人数过多，请重试”，消息连续发送3次失败
- 初步现象：NameServer正常、Broker端口正常、Topic路由正常
- 根因：/mnt/rocketmq-store不再是独立挂载点，Docker退回使用根分区目录；根分区占用约91%，Broker存储进入不可写状态
- 修复：恢复/mnt/rocketmq-store独立tmpfs挂载，重新创建Broker容器
- 验证：commitLogDiskRatio和consumeQueueDiskRatio显著下降，健康检查消息发送成功，秒杀Plus订单最终落库
- 补充措施：通过/etc/fstab配置tmpfs开机自动挂载
- 状态：已恢复并回归通过

## DEFECT-004 商铺缓存删除后无法自动恢复
- 发现方式：ShopApiTest.shouldReturnShopWhenQueryingExistingId：业务失败：店铺不存在但店铺1在MySQL中真实存在。每次手工预热后可以暂时恢复，随后缓存又会消失。
- 缓存删除来源：评分刷新任务执行完成后，DeleteShopCacheNode 会主动删除：cache:shop:1该操作本身用于避免继续展示旧评分，属于合理的缓存失效策略。
            根因一：缓存缺失直接返回空：逻辑过期查询发现Redis Key不存在时直接返回 null，没有回源MySQL。
            根因二：释放错锁Key：缓存异步重建获取的锁为：lock:shop:1。但 finally 中错误执行：unLock(key);导致本应删除锁Key，实际删除了刚刚重建的商铺缓存。
- 修复：修改为:UnLock(lockKey);同时补充缓存缺失回源逻辑：缓存Key不存在→ 查询MySQL→ 店铺存在则重建逻辑过期缓存→ 店铺不存在则写入短期空值缓存->回归结果
- 状态：已修复并通过全量回归。

## DEFECT-005 ThreadLocal用户信息未清理导致身份串用

- 发现方式：运行秒杀Plus防超卖并发专项后，再执行常规接口回归。
- 实际结果:无Token调用 `/user/me` 返回上一请求的用户信息 -> 调用秒杀Plus接口成功创建订单 -> 券12库存被无Token用例提前扣减 -> 后续正常秒杀及重复下单断言级联失败
- 预期结果:无Token请求不应继承任何历史用户身份，受保护接口必须返回HTTP 401。
- 根因:`RefreshTokenInterceptor.preHandle()` 将用户保存到 `UserHolder` 的ThreadLocal中，但 `afterCompletion()` 没有调用：UserHolder.removeUser();
- 状态：已修复并回归