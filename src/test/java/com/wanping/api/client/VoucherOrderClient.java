package com.wanping.api.client;

import io.restassured.response.Response;

import static io.restassured.RestAssured.given;

/**
 * 秒杀Plus接口客户端。
 *
 * 只负责构造和发送HTTP请求，
 * 不负责Redis、MySQL查询和业务断言。
 */
public class VoucherOrderClient {

    /**
     * 携带合法Token调用秒杀Plus。
     */
    public Response seckillPlus(
            long voucherId,
            String token) {

        return given()
                .header(
                        "authorization",
                        token
                )
                .pathParam(
                        "voucherId",
                        voucherId
                )
                .when()
                .post(
                        "/voucher-order/seckill-plus/{voucherId}"
                )
                .then()
                .extract()
                .response();
    }

    /**
     * 不携带Token调用秒杀Plus。
     */
    public Response seckillPlusWithoutToken(
            long voucherId) {

        return given()
                .pathParam(
                        "voucherId",
                        voucherId
                )
                .when()
                .post(
                        "/voucher-order/seckill-plus/{voucherId}"
                )
                .then()
                .extract()
                .response();
    }

    /**
     * 使用原始字符串作为voucherId，
     * 用于验证路径参数类型错误。
     */
    public Response seckillPlusWithRawVoucherId(
            String voucherId,
            String token) {

        return given()
                .header(
                        "authorization",
                        token
                )
                .pathParam(
                        "voucherId",
                        voucherId
                )
                .when()
                .post(
                        "/voucher-order/seckill-plus/{voucherId}"
                )
                .then()
                .extract()
                .response();
    }
}