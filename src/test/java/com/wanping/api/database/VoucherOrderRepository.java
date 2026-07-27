package com.wanping.api.database;

import com.wanping.api.config.TestConfig;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.Optional;

import java.util.LinkedHashSet;
import java.util.Set;

/**
 * 秒杀订单数据库查询与专用测试数据管理。
 *
 * 注意：
 * 重置操作只允许作用于专用测试用户和专用测试券。
 */
public class VoucherOrderRepository {

    private final String url;

    private final String username;

    private final String password;

    public VoucherOrderRepository() {

        String driverClassName =
                TestConfig.getRequired(
                        "db.driver-class-name"
                );

        this.url =
                TestConfig.getRequired(
                        "db.url"
                );

        this.username =
                TestConfig.getRequired(
                        "db.username"
                );

        this.password =
                TestConfig.get(
                        "db.password",
                        ""
                );

        try {
            Class.forName(
                    driverClassName
            );
        } catch (ClassNotFoundException exception) {
            throw new IllegalStateException(
                    "MySQL驱动加载失败："
                            + driverClassName,
                    exception
            );
        }
    }

    /**
     * 恢复秒杀Plus专用测试数据。
     *
     * 只操作指定用户和指定优惠券。
     */
    public void resetDedicatedTestData(
            long userId,
            long voucherId,
            int initialStock) {

        try (Connection connection =
                     openConnection()) {

            connection.setAutoCommit(
                    false
            );

            try {

                /*
                 * 删除旧的异步校验、恢复和对账数据，
                 * 避免以前的测试任务继续影响本轮结果。
                 */
                deleteByUserAndVoucher(
                        connection,
                        "DELETE FROM tb_order_create_verify_task "
                                + "WHERE user_id = ? AND voucher_id = ?",
                        userId,
                        voucherId
                );

                deleteByUserAndVoucher(
                        connection,
                        "DELETE FROM tb_order_create_recovery_task "
                                + "WHERE user_id = ? AND voucher_id = ?",
                        userId,
                        voucherId
                );

                deleteByUserAndVoucher(
                        connection,
                        "DELETE FROM tb_seckill_reconcile_task "
                                + "WHERE user_id = ? AND voucher_id = ?",
                        userId,
                        voucherId
                );

                deleteByUserAndVoucher(
                        connection,
                        "DELETE FROM tb_voucher_reconcile_log "
                                + "WHERE user_id = ? AND voucher_id = ?",
                        userId,
                        voucherId
                );

                /*
                 * 删除该测试用户对该测试券的历史订单。
                 */
                deleteByUserAndVoucher(
                        connection,
                        "DELETE FROM tb_voucher_order "
                                + "WHERE user_id = ? AND voucher_id = ?",
                        userId,
                        voucherId
                );

                /*
                 * 恢复MySQL秒杀库存。
                 */
                int updatedRows;

                try (PreparedStatement statement =
                             connection.prepareStatement(
                                     "UPDATE tb_seckill_voucher "
                                             + "SET stock = ? "
                                             + "WHERE voucher_id = ?"
                             )) {

                    statement.setInt(
                            1,
                            initialStock
                    );

                    statement.setLong(
                            2,
                            voucherId
                    );

                    updatedRows =
                            statement.executeUpdate();
                }

                if (updatedRows != 1) {
                    throw new IllegalStateException(
                            "恢复MySQL库存失败，voucherId="
                                    + voucherId
                                    + "，更新行数="
                                    + updatedRows
                    );
                }

                connection.commit();

            } catch (Exception exception) {

                connection.rollback();

                throw exception;
            }

        } catch (Exception exception) {
            throw new IllegalStateException(
                    "重置秒杀Plus测试数据失败",
                    exception
            );
        }
    }

    /**
     * 根据订单ID查询订单。
     */
    public Optional<OrderRecord> findById(
            long orderId) {

        String sql =
                "SELECT id, user_id, voucher_id, status "
                        + "FROM tb_voucher_order "
                        + "WHERE id = ?";

        try (Connection connection =
                     openConnection();
             PreparedStatement statement =
                     connection.prepareStatement(
                             sql
                     )) {

            statement.setLong(
                    1,
                    orderId
            );

            try (ResultSet resultSet =
                         statement.executeQuery()) {

                if (!resultSet.next()) {
                    return Optional.empty();
                }

                return Optional.of(
                        new OrderRecord(
                                resultSet.getLong("id"),
                                resultSet.getLong("user_id"),
                                resultSet.getLong("voucher_id"),
                                resultSet.getInt("status")
                        )
                );
            }

        } catch (SQLException exception) {
            throw new IllegalStateException(
                    "查询订单失败，orderId="
                            + orderId,
                    exception
            );
        }
    }

    /**
     * 查询同一用户对同一优惠券的订单数量。
     */
    public int countByUserAndVoucher(
            long userId,
            long voucherId) {

        String sql =
                "SELECT COUNT(*) "
                        + "FROM tb_voucher_order "
                        + "WHERE user_id = ? "
                        + "AND voucher_id = ?";

        try (Connection connection =
                     openConnection();
             PreparedStatement statement =
                     connection.prepareStatement(
                             sql
                     )) {

            statement.setLong(
                    1,
                    userId
            );

            statement.setLong(
                    2,
                    voucherId
            );

            try (ResultSet resultSet =
                         statement.executeQuery()) {

                resultSet.next();

                return resultSet.getInt(1);
            }

        } catch (SQLException exception) {
            throw new IllegalStateException(
                    "统计用户优惠券订单失败",
                    exception
            );
        }
    }

    /**
     * 查询MySQL秒杀库存。
     */
    public int findVoucherStock(
            long voucherId) {

        String sql =
                "SELECT stock "
                        + "FROM tb_seckill_voucher "
                        + "WHERE voucher_id = ?";

        try (Connection connection =
                     openConnection();
             PreparedStatement statement =
                     connection.prepareStatement(
                             sql
                     )) {

            statement.setLong(
                    1,
                    voucherId
            );

            try (ResultSet resultSet =
                         statement.executeQuery()) {

                if (!resultSet.next()) {
                    throw new IllegalStateException(
                            "MySQL中不存在秒杀券："
                                    + voucherId
                    );
                }

                return resultSet.getInt(
                        "stock"
                );
            }

        } catch (SQLException exception) {
            throw new IllegalStateException(
                    "查询MySQL秒杀库存失败",
                    exception
            );
        }
    }

    private void deleteByUserAndVoucher(
            Connection connection,
            String sql,
            long userId,
            long voucherId)
            throws SQLException {

        try (PreparedStatement statement =
                     connection.prepareStatement(
                             sql
                     )) {

            statement.setLong(
                    1,
                    userId
            );

            statement.setLong(
                    2,
                    voucherId
            );

            statement.executeUpdate();
        }
    }

    private Connection openConnection()
            throws SQLException {

        return DriverManager.getConnection(
                url,
                username,
                password
        );
    }

    /**
     * 数据库订单快照。
     */
    public static final class OrderRecord {

        private final long id;

        private final long userId;

        private final long voucherId;

        private final int status;

        public OrderRecord(
                long id,
                long userId,
                long voucherId,
                int status) {

            this.id = id;
            this.userId = userId;
            this.voucherId = voucherId;
            this.status = status;
        }

        public long getId() {
            return id;
        }

        public long getUserId() {
            return userId;
        }

        public long getVoucherId() {
            return voucherId;
        }

        public int getStatus() {
            return status;
        }

        @Override
        public String toString() {
            return "OrderRecord{"
                    + "id=" + id
                    + ", userId=" + userId
                    + ", voucherId=" + voucherId
                    + ", status=" + status
                    + '}';
        }
    }

    /**
     * 重置防超卖专用券的全部测试状态。
     *
     * voucherId必须是并发自动化专用券，
     * 本方法会删除该券的历史订单及相关任务记录。
     */
    public void resetDedicatedVoucherData(
            long voucherId,
            int initialStock) {

        try (Connection connection =
                    openConnection()) {

            connection.setAutoCommit(false);

            try {
                /*
                * 清理该券的异步建单校验、恢复、
                * 对账和历史订单。
                */
                deleteByVoucher(
                        connection,
                        "DELETE FROM tb_order_create_verify_task "
                                + "WHERE voucher_id = ?",
                        voucherId
                );

                deleteByVoucher(
                        connection,
                        "DELETE FROM tb_order_create_recovery_task "
                                + "WHERE voucher_id = ?",
                        voucherId
                );

                deleteByVoucher(
                        connection,
                        "DELETE FROM tb_seckill_reconcile_task "
                                + "WHERE voucher_id = ?",
                        voucherId
                );

                deleteByVoucher(
                        connection,
                        "DELETE FROM tb_voucher_reconcile_log "
                                + "WHERE voucher_id = ?",
                        voucherId
                );

                deleteByVoucher(
                        connection,
                        "DELETE FROM tb_voucher_order "
                                + "WHERE voucher_id = ?",
                        voucherId
                );

                /*
                * 清理该专用券以前产生的可靠消息失败记录。
                */
                try (PreparedStatement statement =
                            connection.prepareStatement(
                                    "DELETE FROM tb_mq_event_record "
                                            + "WHERE destination LIKE "
                                            + "'seckill-plus-order-topic:%' "
                                            + "AND payload LIKE ?"
                            )) {

                    statement.setString(
                            1,
                            "%\"voucherId\":"
                                    + voucherId
                                    + "%"
                    );

                    statement.executeUpdate();
                }

                int updatedRows;

                try (PreparedStatement statement =
                            connection.prepareStatement(
                                    "UPDATE tb_seckill_voucher "
                                            + "SET stock = ? "
                                            + "WHERE voucher_id = ?"
                            )) {

                    statement.setInt(
                            1,
                            initialStock
                    );

                    statement.setLong(
                            2,
                            voucherId
                    );

                    updatedRows =
                            statement.executeUpdate();
                }

                if (updatedRows != 1) {
                    throw new IllegalStateException(
                            "并发测试券不存在或库存恢复失败，voucherId="
                                    + voucherId
                                    + "，updatedRows="
                                    + updatedRows
                    );
                }

                connection.commit();

            } catch (Exception exception) {
                connection.rollback();
                throw exception;
            }

        } catch (Exception exception) {
            throw new IllegalStateException(
                    "重置防超卖专用券失败，voucherId="
                            + voucherId,
                    exception
            );
        }
    }

        //查询券数量
        public int countByVoucher(
            long voucherId) {

        String sql =
                "SELECT COUNT(*) "
                        + "FROM tb_voucher_order "
                        + "WHERE voucher_id = ?";

        try (Connection connection =
                    openConnection();
            PreparedStatement statement =
                    connection.prepareStatement(sql)) {

            statement.setLong(
                    1,
                    voucherId
            );

            try (ResultSet resultSet =
                        statement.executeQuery()) {

                resultSet.next();
                return resultSet.getInt(1);
            }

        } catch (SQLException exception) {
            throw new IllegalStateException(
                    "统计秒杀券订单数失败，voucherId="
                            + voucherId,
                    exception
            );
        }
    }
        //查询购买用户数
        public int countDistinctUsersByVoucher(
            long voucherId) {

        String sql =
                "SELECT COUNT(DISTINCT user_id) "
                        + "FROM tb_voucher_order "
                        + "WHERE voucher_id = ?";

        try (Connection connection =
                    openConnection();
            PreparedStatement statement =
                    connection.prepareStatement(sql)) {

            statement.setLong(
                    1,
                    voucherId
            );

            try (ResultSet resultSet =
                        statement.executeQuery()) {

                resultSet.next();
                return resultSet.getInt(1);
            }

        } catch (SQLException exception) {
            throw new IllegalStateException(
                    "统计秒杀券购买用户数失败，voucherId="
                            + voucherId,
                    exception
            );
        }
    }

        //查询数据库订单ID集合
        public Set<Long> findOrderIdsByVoucher(
            long voucherId) {

        String sql =
                "SELECT id "
                        + "FROM tb_voucher_order "
                        + "WHERE voucher_id = ?";

        Set<Long> orderIds =
                new LinkedHashSet<>();

        try (Connection connection =
                    openConnection();
            PreparedStatement statement =
                    connection.prepareStatement(sql)) {

            statement.setLong(
                    1,
                    voucherId
            );

            try (ResultSet resultSet =
                        statement.executeQuery()) {

                while (resultSet.next()) {
                    orderIds.add(
                            resultSet.getLong("id")
                    );
                }
            }

            return orderIds;

        } catch (SQLException exception) {
            throw new IllegalStateException(
                    "查询秒杀券订单ID失败，voucherId="
                            + voucherId,
                    exception
            );
        }
    }

    //查询数据库购买用户集合
    public Set<Long> findUserIdsByVoucher(
            long voucherId) {

        String sql =
                "SELECT user_id "
                        + "FROM tb_voucher_order "
                        + "WHERE voucher_id = ?";

        Set<Long> userIds =
                new LinkedHashSet<>();

        try (Connection connection =
                    openConnection();
            PreparedStatement statement =
                    connection.prepareStatement(sql)) {

            statement.setLong(
                    1,
                    voucherId
            );

            try (ResultSet resultSet =
                        statement.executeQuery()) {

                while (resultSet.next()) {
                    userIds.add(
                            resultSet.getLong("user_id")
                    );
                }
            }

            return userIds;

        } catch (SQLException exception) {
            throw new IllegalStateException(
                    "查询秒杀券购买用户失败，voucherId="
                            + voucherId,
                    exception
            );
        }
    }

    //增加单券删除辅助方法
    private void deleteByVoucher(
            Connection connection,
            String sql,
            long voucherId)
            throws SQLException {

        try (PreparedStatement statement =
                    connection.prepareStatement(sql)) {

            statement.setLong(
                    1,
                    voucherId
            );

            statement.executeUpdate();
        }
    }
}
