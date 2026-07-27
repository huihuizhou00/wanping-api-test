package com.wanping.api.client;

import static io.restassured.RestAssured.given;

import io.restassured.response.Response;

/**
 * 商详聚合与优惠券查询HTTP客户端。
 *
 * 只负责请求构造，不包含测试断言。
 */
public class ShopDetailClient {

    /**
     * 查询聚合商详。
     */
    public Response queryShopDetail(
            long shopId) {

        return given()
                .pathParam(
                        "shopId",
                        shopId
                )
                .when()
                .get("/shop/detail/{shopId}")
                .then()
                .extract()
                .response();
    }

    /**
     * 使用原始字符串作为shopId，
     * 用于测试数字格式错误。
     */
    public Response queryShopDetailWithRawId(
            String shopId) {

        return given()
                .pathParam(
                        "shopId",
                        shopId
                )
                .when()
                .get("/shop/detail/{shopId}")
                .then()
                .extract()
                .response();
    }

    /**
     * 查询指定商铺的优惠券。
     */
    public Response queryVouchers(
            long shopId) {

        return given()
                .pathParam(
                        "shopId",
                        shopId
                )
                .when()
                .get("/voucher/list/{shopId}")
                .then()
                .extract()
                .response();
    }

    /**
     * 使用原始字符串测试优惠券接口路径参数。
     */
    public Response queryVouchersWithRawShopId(
            String shopId) {

        return given()
                .pathParam(
                        "shopId",
                        shopId
                )
                .when()
                .get("/voucher/list/{shopId}")
                .then()
                .extract()
                .response();
    }
}