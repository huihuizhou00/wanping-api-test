package com.wanping.api.reporting;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.wanping.api.database.VoucherOrderRepository.OrderRecord;
import io.qameta.allure.Allure;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 将Redis、MySQL和订单数据作为结构化证据写入Allure。
 *
 * Repository和RedisSupport仍只负责数据访问；
 * 本类只负责报告展示，不执行数据库或Redis查询。
 */
public final class AllureEvidenceSupport {

    private static final ObjectMapper OBJECT_MAPPER =
            new ObjectMapper();

    private AllureEvidenceSupport() {
    }

    /**
     * 附加某一阶段的秒杀数据状态。
     */
    public static void attachSeckillState(
            String stage,
            long userId,
            long voucherId,
            int redisStock,
            int mysqlStock,
            int mysqlOrderCount,
            boolean redisPurchased) {

        Map<String, Object> state =
                new LinkedHashMap<>();

        state.put(
                "stage",
                stage
        );

        state.put(
                "userId",
                userId
        );

        state.put(
                "voucherId",
                voucherId
        );

        state.put(
                "redisStock",
                redisStock
        );

        state.put(
                "mysqlStock",
                mysqlStock
        );

        state.put(
                "mysqlOrderCount",
                mysqlOrderCount
        );

        state.put(
                "redisPurchased",
                redisPurchased
        );

        state.put(
                "stockConsistent",
                redisStock == mysqlStock
        );

        attachJson(
                stage + " - Redis与MySQL状态",
                state
        );
    }

    /**
     * 附加异步落库后的订单信息。
     */
    public static void attachOrderRecord(
            String stage,
            OrderRecord order) {

        Map<String, Object> orderData =
                new LinkedHashMap<>();

        orderData.put(
                "stage",
                stage
        );

        orderData.put(
                "orderId",
                order.getId()
        );

        orderData.put(
                "userId",
                order.getUserId()
        );

        orderData.put(
                "voucherId",
                order.getVoucherId()
        );

        orderData.put(
                "status",
                order.getStatus()
        );

        attachJson(
                stage + " - MySQL订单记录",
                orderData
        );
    }

    /**
     * 附加任意结构化JSON证据。
     */
    public static void attachJson(
            String name,
            Object value) {

        try {
            String json =
                    OBJECT_MAPPER
                            .writerWithDefaultPrettyPrinter()
                            .writeValueAsString(
                                    value
                            );

            Allure.addAttachment(
                    name,
                    "application/json",
                    json,
                    ".json"
            );

        } catch (JsonProcessingException exception) {
            throw new IllegalStateException(
                    "生成Allure JSON附件失败，name="
                            + name,
                    exception
            );
        }
    }

    /**
     * 附加普通文本证据。
     */
    public static void attachText(
            String name,
            String content) {

        Allure.addAttachment(
                name,
                "text/plain",
                content == null
                        ? ""
                        : content,
                ".txt"
        );
    }
}
