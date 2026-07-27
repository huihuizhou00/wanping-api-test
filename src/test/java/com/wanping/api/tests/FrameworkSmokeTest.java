package com.wanping.api.tests;

import com.wanping.api.base.BaseTest;
import io.restassured.RestAssured;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 验证测试框架配置是否能够正常加载。
 *
 * 当前测试不调用业务接口，
 * 只验证自动化项目骨架。
 */
class FrameworkSmokeTest extends BaseTest {

    @Test
    void shouldLoadRestAssuredConfiguration() {

        assertFalse(
                RestAssured.baseURI == null
                        || RestAssured.baseURI
                        .trim()
                        .isEmpty(),
                "baseURI不能为空"
        );

        assertTrue(
                RestAssured.baseURI
                        .startsWith("http"),
                "baseURI必须是HTTP地址"
        );
    }
}