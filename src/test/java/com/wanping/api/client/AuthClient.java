package com.wanping.api.client;

import io.restassured.http.ContentType;
import io.restassured.response.Response;

import java.util.HashMap;
import java.util.Map;

import static io.restassured.RestAssured.given;

/**
 * 登录与鉴权接口客户端。
 *
 * 只负责发送HTTP请求，
 * 不负责读取Redis或编排完整登录流程。
 */
public class AuthClient {

    /**
     * 发送手机验证码。
     */
    public Response sendCode(
            String phone) {

        return given()
                .queryParam(
                        "phone",
                        phone
                )
                .when()
                .post("/user/code")
                .then()
                .extract()
                .response();
    }

    /**
     * 使用手机号和验证码登录。
     */
    public Response login(
            String phone,
            String code) {

        Map<String, Object> requestBody =
                new HashMap<>();

        requestBody.put(
                "phone",
                phone
        );

        requestBody.put(
                "code",
                code
        );

        return given()
                .contentType(
                        ContentType.JSON
                )
                .body(
                        requestBody
                )
                .when()
                .post("/user/login")
                .then()
                .extract()
                .response();
    }

    /**
     * 携带Token查询当前用户。
     */
    public Response currentUser(
            String token) {

        return given()
                .header(
                        "authorization",
                        token
                )
                .when()
                .get("/user/me")
                .then()
                .extract()
                .response();
    }

    /**
     * 不携带Token查询当前用户。
     */
    public Response currentUserWithoutToken() {

        return given()
                .when()
                .get("/user/me")
                .then()
                .extract()
                .response();
    }
}