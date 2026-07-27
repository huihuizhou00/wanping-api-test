package com.wanping.api.tests;

import com.wanping.api.base.BaseTest;
import com.wanping.api.client.VoucherOrderClient;
import com.wanping.api.config.TestConfig;
import com.wanping.api.database.VoucherOrderRepository;
import com.wanping.api.support.ConcurrentUserSessionProvider;
import com.wanping.api.support.ConcurrentUserSessionProvider.UserSession;
import com.wanping.api.support.SeckillRedisSupport;
import io.restassured.response.Response;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;


import com.wanping.api.reporting.AllureEvidenceSupport;
import io.qameta.allure.Epic;
import io.qameta.allure.Feature;
import io.qameta.allure.Severity;
import io.qameta.allure.SeverityLevel;
import io.qameta.allure.Story;
import org.junit.jupiter.api.DisplayName;

import java.util.LinkedHashMap;
import java.util.Map;
/**
 * 秒杀Plus防超卖并发专项。
 *
 * 20个不同用户同时抢购库存为5的专用券：
 * HTTP成功5个，失败15个；
 * Redis与MySQL最终均为库存0、订单5条。
 */
@Epic("万评核心接口自动化")
@Feature("秒杀Plus并发一致性")
@DisplayName("秒杀Plus防超卖并发专项")
@Tag("concurrency")
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class VoucherOversellConcurrencyTest
        extends BaseTest {

    private VoucherOrderClient orderClient;

    private VoucherOrderRepository repository;

    private SeckillRedisSupport redisSupport;

    private List<UserSession> sessions;

    private long voucherId;

    private int initialStock;

    private int concurrentRequests;

    private long requestTimeoutMs;

    private long orderTimeoutMs;

    private long orderIntervalMs;

    @BeforeAll
    void prepareOversellTest() {

        orderClient =
                new VoucherOrderClient();

        repository =
                new VoucherOrderRepository();

        redisSupport =
                new SeckillRedisSupport();

        voucherId =
                Long.parseLong(
                        TestConfig.getRequired(
                                "test.seckill.oversell.voucher.id"
                        )
                );

        initialStock =
                TestConfig.getInt(
                        "test.seckill.oversell.initial.stock",
                        5
                );

        concurrentRequests =
                TestConfig.getInt(
                        "test.seckill.oversell.concurrent.requests",
                        20
                );

        int userCount =
                TestConfig.getInt(
                        "test.seckill.oversell.user.count",
                        20
                );

        if (userCount != concurrentRequests) {
            throw new IllegalStateException(
                    "当前专项要求一个用户只发送一个请求，"
                            + "userCount必须等于concurrentRequests"
            );
        }

        requestTimeoutMs =
                TestConfig.getInt(
                        "test.seckill.oversell.request.timeout.ms",
                        20000
                );

        orderTimeoutMs =
                TestConfig.getInt(
                        "test.seckill.oversell.order.timeout.ms",
                        20000
                );

        orderIntervalMs =
                TestConfig.getInt(
                        "test.seckill.oversell.order.interval.ms",
                        200
                );

        String phonePrefix =
                TestConfig.getRequired(
                        "test.seckill.oversell.phone.prefix"
                );

        int phoneStart =
                TestConfig.getInt(
                        "test.seckill.oversell.phone.start",
                        1
                );

        /*
         * 通过真实登录链路准备20个Token。
         * 首次执行会注册用户，后续重复使用。
         */
        sessions =
                new ConcurrentUserSessionProvider()
                        .obtainSessions(
                                phonePrefix,
                                phoneStart,
                                userCount
                        );

        List<Long> userIds =
                sessions.stream()
                        .map(UserSession::getUserId)
                        .collect(Collectors.toList());

        /*
         * 先恢复MySQL，再恢复Redis。
         * 券13是本专项独占测试数据。
         */
        repository.resetDedicatedVoucherData(
                voucherId,
                initialStock
        );

        redisSupport.resetDedicatedVoucherData(
                voucherId,
                initialStock,
                userIds
        );

        assertEquals(
                concurrentRequests,
                sessions.size(),
                "并发测试用户数量不正确"
        );

        assertEquals(
                concurrentRequests,
                userIds.stream()
                        .distinct()
                        .count(),
                "并发测试用户ID必须互不相同"
        );

        assertEquals(
                initialStock,
                repository.findVoucherStock(voucherId),
                "测试开始前MySQL库存错误"
        );

        assertEquals(
                initialStock,
                redisSupport.getStock(voucherId),
                "测试开始前Redis库存错误"
        );

        assertEquals(
                0,
                repository.countByVoucher(voucherId),
                "测试开始前不应存在历史订单"
        );

        assertTrue(
                redisSupport
                        .getPurchasedUserIds(voucherId)
                        .isEmpty(),
                "测试开始前Redis已购集合应为空"
        );
    }

    @Test
    @DisplayName("20个用户并发抢购库存5：严格成功5单且不超卖")
    @Story("多用户并发防超卖")
    @Severity(SeverityLevel.BLOCKER)
    void shouldNotOversellWhenTwentyUsersCompeteForFiveStocks()
            throws Exception {

        Map<String, Object> concurrencyParameters =
        new LinkedHashMap<>();

        concurrencyParameters.put(
                "voucherId",
                voucherId
        );

        concurrencyParameters.put(
                "concurrentUsers",
                concurrentRequests
        );

        concurrencyParameters.put(
                "concurrentRequests",
                concurrentRequests
        );

        concurrencyParameters.put(
                "initialStock",
                initialStock
        );

        concurrencyParameters.put(
                "expectedSuccessCount",
                initialStock
        );

        concurrencyParameters.put(
                "expectedFailureCount",
                concurrentRequests - initialStock
        );

        concurrencyParameters.put(
                "requestTimeoutMs",
                requestTimeoutMs
        );

        concurrencyParameters.put(
                "orderTimeoutMs",
                orderTimeoutMs
        );

        AllureEvidenceSupport.attachJson(
                "防超卖并发参数",
                concurrencyParameters
        );
        ExecutorService executor =
                Executors.newFixedThreadPool(
                        concurrentRequests
                );

        CountDownLatch readyLatch =
                new CountDownLatch(
                        concurrentRequests
                );

        CountDownLatch startLatch =
                new CountDownLatch(1);

        List<Future<AttemptResult>> futures =
                new ArrayList<>();

        try {
            for (UserSession session : sessions) {

                futures.add(
                        executor.submit(() -> {

                            readyLatch.countDown();

                            boolean started =
                                    startLatch.await(
                                            requestTimeoutMs,
                                            TimeUnit.MILLISECONDS
                                    );

                            if (!started) {
                                throw new IllegalStateException(
                                        "并发开始信号等待超时，userId="
                                                + session.getUserId()
                                );
                            }

                            Response response =
                                    orderClient.seckillPlus(
                                            voucherId,
                                            session.getToken()
                                    );

                            return AttemptResult.from(
                                    session,
                                    response
                            );
                        })
                );
            }

            assertTrue(
                    readyLatch.await(
                            requestTimeoutMs,
                            TimeUnit.MILLISECONDS
                    ),
                    "20个并发线程未在限定时间内全部就绪"
            );

            /*
             * 一次性释放20个线程，尽可能同时请求。
             */
            startLatch.countDown();

            List<AttemptResult> results =
                    new ArrayList<>();

            for (Future<AttemptResult> future : futures) {
                results.add(
                        future.get(
                                requestTimeoutMs,
                                TimeUnit.MILLISECONDS
                        )
                );
            }

            assertEquals(
                    concurrentRequests,
                    results.size(),
                    "并发请求结果数量不正确"
            );

            for (AttemptResult result : results) {
                assertEquals(
                        200,
                        result.getStatusCode(),
                        "秒杀业务响应应为HTTP 200，结果："
                                + result
                );
            }

            List<AttemptResult> successes =
                results.stream()
                        .filter(AttemptResult::isSuccess)
                        .collect(Collectors.toList());

            List<AttemptResult> failures =
                    results.stream()
                            .filter(result -> !result.isSuccess())
                            .collect(Collectors.toList());

            List<Map<String, Object>> requestDetails =
                    new ArrayList<>();

            for (AttemptResult result : results) {

                Map<String, Object> detail =
                        new LinkedHashMap<>();

                detail.put(
                        "userId",
                        result.getUserId()
                );

                detail.put(
                        "phone",
                        result.getPhone()
                );

                detail.put(
                        "statusCode",
                        result.getStatusCode()
                );

                detail.put(
                        "success",
                        result.isSuccess()
                );

                detail.put(
                        "orderId",
                        result.getOrderId()
                );

                detail.put(
                        "errorMsg",
                        result.getErrorMsg()
                );

                requestDetails.add(detail);
            }

            Map<String, Object> requestSummary =
                    new LinkedHashMap<>();

            requestSummary.put(
                    "totalRequests",
                    results.size()
            );

            requestSummary.put(
                    "successCount",
                    successes.size()
            );

            requestSummary.put(
                    "failureCount",
                    failures.size()
            );

            requestSummary.put(
                    "expectedSuccessCount",
                    initialStock
            );

            requestSummary.put(
                    "expectedFailureCount",
                    concurrentRequests - initialStock
            );

            requestSummary.put(
                    "requests",
                    requestDetails
            );

            AllureEvidenceSupport.attachJson(
                    "20个并发请求结果汇总",
                    requestSummary
            );


            /*
             * 严格口径：
             * 库存5时必须正好成功5个。
             */
            assertEquals(
                    initialStock,
                    successes.size(),
                    "成功请求数必须等于初始库存，结果："
                            + results
            );

            assertEquals(
                    concurrentRequests - initialStock,
                    failures.size(),
                    "失败请求数不正确"
            );

            for (AttemptResult failure : failures) {
                assertTrue(
                        failure.getErrorMsg() != null
                                && failure.getErrorMsg()
                                .contains("库存不足"),
                        "非成功请求应由库存不足导致，结果："
                                + failure
                );
            }

            Set<Long> successfulOrderIds =
                    successes.stream()
                            .map(AttemptResult::getOrderId)
                            .collect(Collectors.toSet());

            Set<Long> successfulUserIds =
                    successes.stream()
                            .map(AttemptResult::getUserId)
                            .collect(Collectors.toSet());

            assertEquals(
                    initialStock,
                    successfulOrderIds.size(),
                    "成功订单ID必须互不重复"
            );

            assertEquals(
                    initialStock,
                    successfulUserIds.size(),
                    "成功购买用户必须互不重复"
            );

            /*
             * 等待RocketMQ消费者完成5条订单落库。
             */
            awaitExpectedOrderCount(
                    voucherId,
                    initialStock
            );

            Set<Long> databaseOrderIds =
                    repository.findOrderIdsByVoucher(
                            voucherId
                    );

            Set<Long> databaseUserIds =
                    repository.findUserIdsByVoucher(
                            voucherId
                    );

            Set<Long> redisUserIds =
                    redisSupport.getPurchasedUserIds(
                            voucherId
                    );

            int databaseOrderCount =
                    repository.countByVoucher(
                            voucherId
                    );

            int databaseUserCount =
                    repository.countDistinctUsersByVoucher(
                            voucherId
                    );

            int redisStockAfter =
                    redisSupport.getStock(
                            voucherId
                    );

            int mysqlStockAfter =
                    repository.findVoucherStock(
                            voucherId
                    );

            Map<String, Object> finalState =
                    new LinkedHashMap<>();

            finalState.put(
                    "voucherId",
                    voucherId
            );

            finalState.put(
                    "initialStock",
                    initialStock
            );

            finalState.put(
                    "httpSuccessCount",
                    successes.size()
            );

            finalState.put(
                    "httpFailureCount",
                    failures.size()
            );

            finalState.put(
                    "redisStock",
                    redisStockAfter
            );

            finalState.put(
                    "mysqlStock",
                    mysqlStockAfter
            );

            finalState.put(
                    "mysqlOrderCount",
                    databaseOrderCount
            );

            finalState.put(
                    "mysqlDistinctUserCount",
                    databaseUserCount
            );

            finalState.put(
                    "successfulOrderIds",
                    successfulOrderIds.stream()
                            .sorted()
                            .collect(Collectors.toList())
            );

            finalState.put(
                    "databaseOrderIds",
                    databaseOrderIds.stream()
                            .sorted()
                            .collect(Collectors.toList())
            );

            finalState.put(
                    "successfulUserIds",
                    successfulUserIds.stream()
                            .sorted()
                            .collect(Collectors.toList())
            );

            finalState.put(
                    "redisPurchasedUserIds",
                    redisUserIds.stream()
                            .sorted()
                            .collect(Collectors.toList())
            );

            finalState.put(
                    "databaseUserIds",
                    databaseUserIds.stream()
                            .sorted()
                            .collect(Collectors.toList())
            );

            finalState.put(
                    "redisAndMysqlStockConsistent",
                    redisStockAfter == mysqlStockAfter
            );

            finalState.put(
                    "orderCountWithinStockBoundary",
                    databaseOrderCount <= initialStock
            );

            finalState.put(
                    "redisStockNonNegative",
                    redisStockAfter >= 0
            );

            finalState.put(
                    "mysqlStockNonNegative",
                    mysqlStockAfter >= 0
            );

            AllureEvidenceSupport.attachJson(
                    "防超卖最终一致性快照",
                    finalState
            );

            assertEquals(
                    initialStock,
                    databaseOrderCount,
                    "MySQL订单数必须等于初始库存"
            );

            assertEquals(
                    initialStock,
                    databaseUserCount,
                    "MySQL购买用户数必须等于初始库存"
            );

            assertEquals(
                    successfulOrderIds,
                    databaseOrderIds,
                    "接口返回的订单ID与MySQL订单不一致"
            );

            assertEquals(
                    successfulUserIds,
                    databaseUserIds,
                    "接口成功用户与MySQL购买用户不一致"
            );

            assertEquals(
                    successfulUserIds,
                    redisUserIds,
                    "接口成功用户与Redis已购集合不一致"
            );

            assertEquals(
                    0,
                    redisStockAfter,
                    "Redis最终库存必须为0"
            );

            assertEquals(
                    0,
                    mysqlStockAfter,
                    "MySQL最终库存必须为0"
            );

            assertTrue(
                    databaseOrderCount <= initialStock,
                    "MySQL订单数不能超过初始库存"
            );

            assertTrue(
                    redisStockAfter >= 0,
                    "Redis库存不能为负数"
            );

            assertTrue(
                    mysqlStockAfter >= 0,
                    "MySQL库存不能为负数"
            );

        } finally {
            startLatch.countDown();
            executor.shutdownNow();
        }
    }

    private void awaitExpectedOrderCount(
            long targetVoucherId,
            int expectedCount) {

        long deadline =
                System.nanoTime()
                        + TimeUnit.MILLISECONDS
                        .toNanos(orderTimeoutMs);

        while (System.nanoTime() < deadline) {

            int currentCount =
                    repository.countByVoucher(
                            targetVoucherId
                    );

            if (currentCount == expectedCount) {
                return;
            }

            if (currentCount > expectedCount) {
                throw new AssertionError(
                        "等待过程中已经发生超卖，expected="
                                + expectedCount
                                + "，actual="
                                + currentCount
                );
            }

            try {
                Thread.sleep(orderIntervalMs);
            } catch (InterruptedException exception) {
                Thread.currentThread().interrupt();

                throw new IllegalStateException(
                        "等待并发订单落库时线程被中断",
                        exception
                );
            }
        }

        throw new AssertionError(
                "在"
                        + orderTimeoutMs
                        + "ms内未等待到"
                        + expectedCount
                        + "条订单，当前订单数="
                        + repository
                        .countByVoucher(
                                targetVoucherId
                        )
        );
    }

    private static final class AttemptResult {

        private final long userId;

        private final String phone;

        private final int statusCode;

        private final boolean success;

        private final Long orderId;

        private final String errorMsg;

        private AttemptResult(
                long userId,
                String phone,
                int statusCode,
                boolean success,
                Long orderId,
                String errorMsg) {

            this.userId = userId;
            this.phone = phone;
            this.statusCode = statusCode;
            this.success = success;
            this.orderId = orderId;
            this.errorMsg = errorMsg;
        }

        private static AttemptResult from(
                UserSession session,
                Response response) {

            Boolean successValue =
                    response.jsonPath()
                            .get("success");

            boolean success =
                    Boolean.TRUE.equals(successValue);

            Long orderId = null;

            if (success) {
                Number orderIdValue =
                        response.jsonPath()
                                .get("data");

                assertNotNull(
                        orderIdValue,
                        "成功响应必须返回orderId"
                );

                orderId =
                        orderIdValue.longValue();
            }

            String errorMsg =
                    response.jsonPath()
                            .getString("errorMsg");

            return new AttemptResult(
                    session.getUserId(),
                    session.getPhone(),
                    response.statusCode(),
                    success,
                    orderId,
                    errorMsg
            );
        }

        public long getUserId() {
            return userId;
        }

        public String getPhone() {
            return phone;
        }

        public int getStatusCode() {
            return statusCode;
        }

        public boolean isSuccess() {
            return success;
        }

        public Long getOrderId() {
            return orderId;
        }

        public String getErrorMsg() {
            return errorMsg;
        }

        @Override
        public String toString() {
            return "AttemptResult{"
                    + "userId=" + userId
                    + ", phone='" + phone + '\''
                    + ", statusCode=" + statusCode
                    + ", success=" + success
                    + ", orderId=" + orderId
                    + ", errorMsg='" + errorMsg + '\''
                    + '}';
        }
    }
}