package com.wanping.api.tests;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.concurrent.TimeUnit;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.MethodOrderer;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;

import com.wanping.api.assertions.ResultAssertions;
import com.wanping.api.base.BaseTest;
import com.wanping.api.client.AuthClient;
import com.wanping.api.client.VoucherOrderClient;
import com.wanping.api.config.TestConfig;
import com.wanping.api.database.VoucherOrderRepository;
import com.wanping.api.database.VoucherOrderRepository.OrderRecord;
import com.wanping.api.support.OrderAwaiter;
import com.wanping.api.support.RedisCodeReader;
import com.wanping.api.support.SeckillRedisSupport;
import com.wanping.api.support.TokenUtil;
import java.util.Collections;
import io.restassured.response.Response;


import com.wanping.api.reporting.AllureEvidenceSupport;
import io.qameta.allure.Epic;
import io.qameta.allure.Feature;
import io.qameta.allure.Severity;
import io.qameta.allure.SeverityLevel;
import io.qameta.allure.Story;
import org.junit.jupiter.api.DisplayName;
/**
 * 秒杀Plus接口与异步订单落库自动化。
 *
 * 用例具有明确业务顺序：
 * 基础异常场景
 * → 正向秒杀
 * → 重复下单。
 */
@Epic("万评核心接口自动化")
@Feature("秒杀Plus")
@DisplayName("秒杀Plus接口自动化")
@TestMethodOrder(
        MethodOrderer.OrderAnnotation.class
)
class VoucherOrderApiTest extends BaseTest {

    private static VoucherOrderClient orderClient;

    private static VoucherOrderRepository orderRepository;

    private static SeckillRedisSupport redisSupport;

    private static OrderAwaiter orderAwaiter;

    private static String token;

    private static long userId;

    private static long voucherId;

    private static int initialStock;

    private static Long createdOrderId;

    @BeforeAll
    static void initializeSeckillTests() {

        orderClient =
                new VoucherOrderClient();

        orderRepository =
                new VoucherOrderRepository();

        redisSupport =
                new SeckillRedisSupport();

        orderAwaiter =
                new OrderAwaiter(
                        orderRepository
                );

        userId =
                Long.parseLong(
                        TestConfig.getRequired(
                                "test.user.id"
                        )
                );

        voucherId =
                Long.parseLong(
                        TestConfig.getRequired(
                                "test.seckill.plus.voucher.id"
                        )
                );

        initialStock =
                TestConfig.getInt(
                        "test.seckill.initial.stock",
                        2
                );

        /*
        * 券12为本测试类独占的自动化专用券。
        *
        * 整券重置可以清理ThreadLocal泄漏等异常场景下，
        * 其他测试用户误购买券12留下的订单和Redis状态。
        */
        orderRepository.resetDedicatedVoucherData(
                voucherId,
                initialStock
        );

        redisSupport.resetDedicatedVoucherData(
                voucherId,
                initialStock,
                Collections.singletonList(userId)
        );

        assertEquals(
                initialStock,
                orderRepository
                        .findVoucherStock(
                                voucherId
                        ),
                "测试开始前MySQL库存错误"
        );

        assertEquals(
                initialStock,
                redisSupport.getStock(
                        voucherId
                ),
                "测试开始前Redis库存错误"
        );

        assertEquals(
                0,
                orderRepository
                        .countByUserAndVoucher(
                                userId,
                                voucherId
                        ),
                "测试开始前不应存在历史订单"
        );

        token =
                TokenUtil.obtainToken(
                        new AuthClient(),
                        new RedisCodeReader(),
                        TestConfig.getRequired(
                                "test.user.phone"
                        )
                );
    }

    /**
     * 秒杀接口要求登录。
     */
    @Test
    @Order(1)
    void shouldReturn401WhenSeckillPlusHasNoToken() {

        Response response =
                orderClient
                        .seckillPlusWithoutToken(
                                voucherId
                        );

        ResultAssertions.assertUnauthorized(
                response
        );
    }

    /**
     * 非数字voucherId在进入业务层前失败。
     */
    @Test
    @Order(2)
    void shouldReturn400WhenVoucherIdIsNotNumeric() {

        Response response =
                orderClient
                        .seckillPlusWithRawVoucherId(
                                "invalid-id",
                                token
                        );

        assertEquals(
                400,
                response.statusCode(),
                "非数字voucherId应返回HTTP 400，响应体："
                        + response.asString()
        );
    }

    /**
     * Redis库存未初始化时，
     * Lua返回-1，对应业务错误。
     */
    @Test
    @Order(3)
    void shouldFailWhenSeckillStockIsNotInitialized() {

        long unknownVoucherId =
                999999L;

        Response response =
                orderClient.seckillPlus(
                        unknownVoucherId,
                        token
                );

        ResultAssertions.assertBusinessFailure(
                response,
                "秒杀库存未初始化"
        );
    }

    /**
     * 正向链路：
     *
     * HTTP成功
     * → Redis预扣库存
     * → MQ异步建单
     * → MySQL订单与库存最终落地。
     */
    @Test
    @Order(4)
    @DisplayName("正常秒杀：Redis预扣并通过RocketMQ异步建单")
    @Story("正常秒杀与最终一致性")
    @Severity(SeverityLevel.CRITICAL)
    void shouldCreateOrderThroughSeckillPlus() {

        int redisStockBefore =
                redisSupport.getStock(
                        voucherId
                );

        int mysqlStockBefore =
                orderRepository
                        .findVoucherStock(
                                voucherId
                        );

        int orderCountBefore =
                orderRepository
                        .countByUserAndVoucher(
                                userId,
                                voucherId
                        );

        boolean purchasedBefore =
                redisSupport.hasPurchased(
                        userId,
                        voucherId
                );

        AllureEvidenceSupport.attachSeckillState(
                "秒杀请求前",
                userId,
                voucherId,
                redisStockBefore,
                mysqlStockBefore,
                orderCountBefore,
                purchasedBefore
        );

        Response response =
                orderClient.seckillPlus(
                        voucherId,
                        token
                );

        ResultAssertions.assertBusinessSuccess(
                response
        );

        Long orderId =
                response.jsonPath()
                        .getLong("data");

        assertNotNull(
                orderId,
                "秒杀成功后orderId不能为空"
        );

        assertTrue(
                orderId > 0,
                "orderId必须大于0"
        );

        createdOrderId =
                orderId;

        /*
        * 等待RocketMQ消费者完成订单落库。
        */
        OrderRecord order =
                orderAwaiter.awaitOrder(
                        orderId
                );

        int redisStockAfter =
                redisSupport.getStock(
                        voucherId
                );

        int mysqlStockAfter =
                orderRepository
                        .findVoucherStock(
                                voucherId
                        );

        int orderCountAfter =
                orderRepository
                        .countByUserAndVoucher(
                                userId,
                                voucherId
                        );

        boolean purchasedAfter =
                redisSupport.hasPurchased(
                        userId,
                        voucherId
                );

        AllureEvidenceSupport.attachOrderRecord(
                "RocketMQ消费完成后",
                order
        );

        AllureEvidenceSupport.attachSeckillState(
                "秒杀完成后",
                userId,
                voucherId,
                redisStockAfter,
                mysqlStockAfter,
                orderCountAfter,
                purchasedAfter
        );

        assertEquals(
                orderId.longValue(),
                order.getId(),
                "数据库订单ID不一致"
        );

        assertEquals(
                userId,
                order.getUserId(),
                "数据库订单用户不一致"
        );

        assertEquals(
                voucherId,
                order.getVoucherId(),
                "数据库订单优惠券不一致"
        );

        /*
        * VoucherOrderStatus.UNPAID的数据库值为1。
        */
        assertEquals(
                1,
                order.getStatus(),
                "新建订单状态应为未支付"
        );

        assertEquals(
                0,
                orderCountBefore,
                "秒杀前不应存在该用户历史订单"
        );

        assertEquals(
                1,
                orderCountAfter,
                "同一用户同一优惠券应只有1条订单"
        );

        assertEquals(
                initialStock,
                redisStockBefore,
                "秒杀前Redis库存错误"
        );

        assertEquals(
                initialStock,
                mysqlStockBefore,
                "秒杀前MySQL库存错误"
        );

        assertEquals(
                initialStock - 1,
                redisStockAfter,
                "Redis库存应只扣减1次"
        );

        assertEquals(
                initialStock - 1,
                mysqlStockAfter,
                "MySQL库存应只扣减1次"
        );

        assertEquals(
                redisStockAfter,
                mysqlStockAfter,
                "Redis与MySQL库存应保持一致"
        );

        assertTrue(
                !purchasedBefore,
                "秒杀前用户不应位于Redis已购集合"
        );

        assertTrue(
                purchasedAfter,
                "秒杀成功后用户应进入Redis已购集合"
        );
    }

    /**
     * 一人一单：
     *
     * 第二次请求失败，
     * 并且不能产生额外库存扣减和重复订单。
     */
    @Test
    @Order(5)
    @DisplayName("重复秒杀：一人一单且不产生额外副作用")
    @Story("一人一单")
    @Severity(SeverityLevel.CRITICAL)
    void shouldRejectDuplicateSeckillWithoutSideEffects()
            throws InterruptedException {

        assertNotNull(
                createdOrderId,
                "正向秒杀用例必须先成功"
        );

        /*
        * 等待请求频率限制Key过期，
        * 确保进入一人一单业务校验。
        */
        TimeUnit.MILLISECONDS.sleep(
                1100
        );

        int redisStockBefore =
                redisSupport.getStock(
                        voucherId
                );

        int mysqlStockBefore =
                orderRepository
                        .findVoucherStock(
                                voucherId
                        );

        int orderCountBefore =
                orderRepository
                        .countByUserAndVoucher(
                                userId,
                                voucherId
                        );

        boolean purchasedBefore =
                redisSupport.hasPurchased(
                        userId,
                        voucherId
                );

        AllureEvidenceSupport.attachSeckillState(
                "重复请求前",
                userId,
                voucherId,
                redisStockBefore,
                mysqlStockBefore,
                orderCountBefore,
                purchasedBefore
        );

        Response response =
                orderClient.seckillPlus(
                        voucherId,
                        token
                );

        ResultAssertions.assertBusinessFailure(
                response,
                "不能重复下单"
        );

        int redisStockAfter =
                redisSupport.getStock(
                        voucherId
                );

        int mysqlStockAfter =
                orderRepository
                        .findVoucherStock(
                                voucherId
                        );

        int orderCountAfter =
                orderRepository
                        .countByUserAndVoucher(
                                userId,
                                voucherId
                        );

        boolean purchasedAfter =
                redisSupport.hasPurchased(
                        userId,
                        voucherId
                );

        AllureEvidenceSupport.attachSeckillState(
                "重复请求后",
                userId,
                voucherId,
                redisStockAfter,
                mysqlStockAfter,
                orderCountAfter,
                purchasedAfter
        );

        assertEquals(
                1,
                orderCountBefore,
                "重复请求前数据库应只有1条订单"
        );

        assertEquals(
                orderCountBefore,
                orderCountAfter,
                "重复下单不能产生新订单"
        );

        assertEquals(
                redisStockBefore,
                redisStockAfter,
                "重复下单不能再次扣减Redis库存"
        );

        assertEquals(
                mysqlStockBefore,
                mysqlStockAfter,
                "重复下单不能再次扣减MySQL库存"
        );

        assertEquals(
                redisStockAfter,
                mysqlStockAfter,
                "重复请求后Redis与MySQL库存应一致"
        );

        assertTrue(
                purchasedBefore,
                "重复请求前用户应已位于Redis已购集合"
        );

        assertTrue(
                purchasedAfter,
                "重复请求后Redis已购状态不应丢失"
        );
    }
}