package com.wanping.api.base;

import com.wanping.api.config.TestConfig;
import io.restassured.RestAssured;
import io.restassured.config.HttpClientConfig;
import org.junit.jupiter.api.BeforeAll;
import com.wanping.api.logging.ApiLogFilter;

/**
 * 所有接口测试类的公共父类。
 *
 * 负责：
 * 1. 初始化Base URI；
 * 2. 初始化接口前缀；
 * 3. 设置请求超时；
 * 4. 失败时打印请求和响应。
 */
public abstract class BaseTest {

    @BeforeAll
    static void setUpRestAssured() {

        RestAssured.baseURI =
                TestConfig.getRequired(
                        "base.url"
                );

        RestAssured.basePath =
                TestConfig.get(
                        "api.prefix",
                        ""
                );

        int timeoutMs =
                TestConfig.getInt(
                        "request.timeout.ms",
                        5000
                );

        RestAssured.config =
                RestAssured.config()
                        .httpClient(
                                HttpClientConfig
                                        .httpClientConfig()
                                        .setParam(
                                                "http.connection.timeout",
                                                timeoutMs
                                        )
                                        .setParam(
                                                "http.socket.timeout",
                                                timeoutMs
                                        )
                                        .setParam(
                                                "http.connection-manager.timeout",
                                                (long) timeoutMs
                                        )
                        );

        /*
         * 用例失败时打印完整请求和响应，
         * 正常通过时不刷屏。
         */
        RestAssured
                .enableLoggingOfRequestAndResponseIfValidationFails();

        /*
        * 统一输出脱敏后的请求与响应日志。
        */
        /*
        * BaseTest的@BeforeAll会在每个测试类执行。
        * 使用replace避免全局ApiLogFilter不断累积。
        */
        RestAssured.replaceFiltersWith(
                new ApiLogFilter()
        );

        System.out.println(
                "[API-TEST] baseURI="
                        + RestAssured.baseURI
                        + RestAssured.basePath
        );


    }
}
