package com.wanping.api.support;

import com.wanping.api.config.TestConfig;
import redis.clients.jedis.Jedis;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
/**
 * 秒杀Plus Redis状态查询与专用测试数据重置。
 */
public class SeckillRedisSupport {

    private static final String STOCK_KEY_PREFIX =
            "seckill:stock:";

    private static final String ORDER_KEY_PREFIX =
            "seckill:order:";

    private static final String REQUEST_KEY_PREFIX =
            "seckill:req:";

    private static final String TRACE_LOG_KEY_PREFIX =
            "seckill:trace:log:";

    private final String host;

    private final int port;

    private final String password;

    private final int database;

    private final int timeoutMs;

    public SeckillRedisSupport() {

        this.host =
                TestConfig.getRequired(
                        "redis.host"
                );

        this.port =
                TestConfig.getInt(
                        "redis.port",
                        6379
                );

        this.password =
                TestConfig.get(
                        "redis.password",
                        ""
                );

        this.database =
                TestConfig.getInt(
                        "redis.database",
                        1
                );

        this.timeoutMs =
                TestConfig.getInt(
                        "redis.timeout.ms",
                        3000
                );
    }

    /**
     * 恢复专用秒杀券的Redis状态。
     */
    public void resetDedicatedTestData(
            long userId,
            long voucherId,
            int initialStock) {

        try (Jedis jedis =
                     createJedis()) {

            jedis.set(
                    stockKey(voucherId),
                    String.valueOf(initialStock)
            );

            jedis.srem(
                    orderKey(voucherId),
                    String.valueOf(userId)
            );

            jedis.del(
                    requestKey(
                            voucherId,
                            userId
                    )
            );

            /*
             * 券12为专用自动化数据，
             * 可以清理该券以前的追踪日志。
             */
            jedis.del(
                    traceLogKey(
                            voucherId
                    )
            );
        }
    }

    public int getStock(
            long voucherId) {

        try (Jedis jedis =
                     createJedis()) {

            String value =
                    jedis.get(
                            stockKey(voucherId)
                    );

            if (value == null) {
                throw new IllegalStateException(
                        "Redis秒杀库存不存在，voucherId="
                                + voucherId
                );
            }

            return Integer.parseInt(
                    value
            );
        }
    }

    public boolean hasPurchased(
            long userId,
            long voucherId) {

        try (Jedis jedis =
                     createJedis()) {

            return jedis.sismember(
                    orderKey(voucherId),
                    String.valueOf(userId)
            );
        }
    }

    private Jedis createJedis() {

        Jedis jedis =
                new Jedis(
                        host,
                        port,
                        timeoutMs
                );

        if (password != null
                && !password.trim().isEmpty()) {

            jedis.auth(
                    password.trim()
            );
        }

        jedis.select(
                database
        );

        return jedis;
    }

    private String stockKey(
            long voucherId) {

        return STOCK_KEY_PREFIX
                + voucherId;
    }

    private String orderKey(
            long voucherId) {

        return ORDER_KEY_PREFIX
                + voucherId;
    }

    private String requestKey(
            long voucherId,
            long userId) {

        return REQUEST_KEY_PREFIX
                + voucherId
                + ":"
                + userId;
    }

    private String traceLogKey(
            long voucherId) {

        return TRACE_LOG_KEY_PREFIX
                + voucherId;
    }

    /**
     * 重置整张并发专用券的Redis状态。
     */
    public void resetDedicatedVoucherData(
            long voucherId,
            int initialStock,
            List<Long> userIds) {

        try (Jedis jedis =
                    createJedis()) {

            jedis.set(
                    stockKey(voucherId),
                    String.valueOf(initialStock)
            );

            /*
            * 券13为并发专项专用券，
            * 可以整体清空已购集合和trace日志。
            */
            jedis.del(
                    orderKey(voucherId)
            );

            jedis.del(
                    traceLogKey(voucherId)
            );

            for (Long userId : userIds) {
                jedis.del(
                        requestKey(
                                voucherId,
                                userId
                        )
                );
            }
        }
    }

    public Set<Long> getPurchasedUserIds(
            long voucherId) {

        try (Jedis jedis =
                    createJedis()) {

            Set<String> members =
                    jedis.smembers(
                            orderKey(voucherId)
                    );

            Set<Long> userIds =
                    new LinkedHashSet<>();

            for (String member : members) {
                userIds.add(
                        Long.parseLong(member)
                );
            }

            return userIds;
        }
    }
}