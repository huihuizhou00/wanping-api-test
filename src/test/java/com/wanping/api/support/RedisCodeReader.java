package com.wanping.api.support;

import com.wanping.api.config.TestConfig;
import redis.clients.jedis.Jedis;

import java.util.concurrent.TimeUnit;

/**
 * 从Redis读取登录验证码。
 *
 * 当前万评本地环境：
 * database=1
 * key=login:code:{phone}
 */
public class RedisCodeReader {

    private static final String LOGIN_CODE_KEY_PREFIX =
            "login:code:";

    private final String host;

    private final int port;

    private final String password;

    private final int database;

    private final int redisTimeoutMs;

    private final long waitTimeoutMs;

    private final long waitIntervalMs;

    public RedisCodeReader() {

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

        this.redisTimeoutMs =
                TestConfig.getInt(
                        "redis.timeout.ms",
                        3000
                );

        this.waitTimeoutMs =
                TestConfig.getInt(
                        "code.wait.timeout.ms",
                        3000
                );

        this.waitIntervalMs =
                TestConfig.getInt(
                        "code.wait.interval.ms",
                        100
                );
    }

    /**
     * 等待并读取指定手机号的验证码。
     */
    public String waitForCode(
            String phone) {

        String redisKey =
                LOGIN_CODE_KEY_PREFIX
                        + phone;

        long deadline =
                System.nanoTime()
                        + TimeUnit.MILLISECONDS
                        .toNanos(
                                waitTimeoutMs
                        );

        try (Jedis jedis =
                     new Jedis(
                             host,
                             port,
                             redisTimeoutMs
                     )) {

            if (password != null
                    && !password
                    .trim()
                    .isEmpty()) {

                jedis.auth(
                        password.trim()
                );
            }

            jedis.select(
                    database
            );

            while (System.nanoTime() < deadline) {

                String code =
                        jedis.get(
                                redisKey
                        );

                if (code != null
                        && !code
                        .trim()
                        .isEmpty()) {

                    return code.trim();
                }

                sleepBeforeRetry();
            }
        }

        throw new IllegalStateException(
                "在"
                        + waitTimeoutMs
                        + "ms内未读取到验证码，Redis Key："
                        + redisKey
                        + "，database="
                        + database
        );
    }

    private void sleepBeforeRetry() {

        try {
            Thread.sleep(
                    waitIntervalMs
            );
        } catch (InterruptedException exception) {

            Thread.currentThread()
                    .interrupt();

            throw new IllegalStateException(
                    "等待Redis验证码时线程被中断",
                    exception
            );
        }
    }
}