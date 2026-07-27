package com.wanping.api.support;

import com.wanping.api.config.TestConfig;
import com.wanping.api.database.VoucherOrderRepository;
import com.wanping.api.database.VoucherOrderRepository.OrderRecord;

import java.util.Optional;
import java.util.concurrent.TimeUnit;

/**
 * 等待RocketMQ异步建单最终落库。
 */
public class OrderAwaiter {

    private final VoucherOrderRepository repository;

    private final long timeoutMs;

    private final long intervalMs;

    public OrderAwaiter(
            VoucherOrderRepository repository) {

        this.repository =
                repository;

        this.timeoutMs =
                TestConfig.getInt(
                        "order.wait.timeout.ms",
                        10000
                );

        this.intervalMs =
                TestConfig.getInt(
                        "order.wait.interval.ms",
                        200
                );
    }

    public OrderRecord awaitOrder(
            long orderId) {

        long deadline =
                System.nanoTime()
                        + TimeUnit.MILLISECONDS
                        .toNanos(
                                timeoutMs
                        );

        while (System.nanoTime()
                < deadline) {

            Optional<OrderRecord> order =
                    repository.findById(
                            orderId
                    );

            if (order.isPresent()) {
                return order.get();
            }

            sleepBeforeRetry();
        }

        throw new IllegalStateException(
                "在"
                        + timeoutMs
                        + "ms内未等待到订单落库，orderId="
                        + orderId
        );
    }

    private void sleepBeforeRetry() {

        try {
            Thread.sleep(
                    intervalMs
            );
        } catch (InterruptedException exception) {

            Thread.currentThread()
                    .interrupt();

            throw new IllegalStateException(
                    "等待异步订单时线程被中断",
                    exception
            );
        }
    }
}