package com.wanping.api.assertions;

import io.restassured.response.Response;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

/**
 * 万评统一Result响应断言。
 *
 * 当前后端业务失败通常仍返回HTTP 200，
 * 通过success和errorMsg表示业务结果。
 */
public final class ResultAssertions {

    private ResultAssertions() {
        // 工具类不允许实例化
    }

    /**
     * 校验业务成功响应。
     */
    public static void assertBusinessSuccess(
            Response response) {

        assertNotNull(
                response,
                "HTTP响应不能为空"
        );

        String responseBody =
                response.asString();

        assertEquals(
                200,
                response.statusCode(),
                "HTTP状态码错误，响应体："
                        + responseBody
        );

        Boolean success =
                response.jsonPath()
                        .getBoolean("success");

        assertEquals(
                Boolean.TRUE,
                success,
                "业务应执行成功，响应体："
                        + responseBody
        );
    }

    /**
     * 校验业务失败响应。
     */
    public static void assertBusinessFailure(
            Response response,
            String expectedErrorMessage) {

        assertNotNull(
                response,
                "HTTP响应不能为空"
        );

        String responseBody =
                response.asString();

        assertEquals(
                200,
                response.statusCode(),
                "业务失败当前仍应返回HTTP 200，响应体："
                        + responseBody
        );

        Boolean success =
                response.jsonPath()
                        .getBoolean("success");

        assertEquals(
                Boolean.FALSE,
                success,
                "业务应执行失败，响应体："
                        + responseBody
        );

        String errorMessage =
                response.jsonPath()
                        .getString("errorMsg");

        assertEquals(
                expectedErrorMessage,
                errorMessage,
                "业务错误信息不符合预期，响应体："
                        + responseBody
        );
    }

    /**
     * 校验未登录响应。
     */
    public static void assertUnauthorized(
            Response response) {

        assertNotNull(
                response,
                "HTTP响应不能为空"
        );

        assertEquals(
                401,
                response.statusCode(),
                "未登录请求应返回401，响应体："
                        + response.asString()
        );
    }
}