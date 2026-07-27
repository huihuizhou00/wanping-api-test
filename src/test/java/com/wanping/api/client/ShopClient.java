package com.wanping.api.client;

import io.restassured.response.Response;

import static io.restassured.RestAssured.given;

/**
 * 商铺查询接口客户端。
 *
 * 只负责请求构造，不包含业务断言。
 */
public class ShopClient {

    /**
     * 根据商铺ID查询。
     */
    public Response queryById(
            long shopId) {

        return given()
                .pathParam(
                        "shopId",
                        shopId
                )
                .when()
                .get("/shop/{shopId}")
                .then()
                .extract()
                .response();
    }

    /**
     * 根据名称关键字分页查询。
     */
    public Response queryByName(
            String name,
            int current) {

        return given()
                .queryParam(
                        "name",
                        name
                )
                .queryParam(
                        "current",
                        current
                )
                .when()
                .get("/shop/of/name")
                .then()
                .extract()
                .response();
    }

    /**
     * 不传名称，查询第一页商铺。
     */
    public Response queryFirstPageWithoutName() {

        return given()
                .queryParam(
                        "current",
                        1
                )
                .when()
                .get("/shop/of/name")
                .then()
                .extract()
                .response();
    }

    /**
     * 根据商铺类型分页查询。
     */
    public Response queryByType(
            int typeId,
            int current) {

        return given()
                .queryParam(
                        "typeId",
                        typeId
                )
                .queryParam(
                        "current",
                        current
                )
                .when()
                .get("/shop/of/type")
                .then()
                .extract()
                .response();
    }

    /**
     * 缺少必填typeId参数。
     */
    public Response queryByTypeWithoutTypeId() {

        return given()
                .queryParam(
                        "current",
                        1
                )
                .when()
                .get("/shop/of/type")
                .then()
                .extract()
                .response();
    }
}