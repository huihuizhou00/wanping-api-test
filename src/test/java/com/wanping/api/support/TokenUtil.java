package com.wanping.api.support;

import com.wanping.api.assertions.ResultAssertions;
import com.wanping.api.client.AuthClient;
import io.restassured.response.Response;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;

/**
 * 登录Token获取工具。
 *
 * 编排：
 * 发送验证码
 * → Redis读取验证码
 * → 登录
 * → 提取Token。
 */
public final class TokenUtil {

    private TokenUtil() {
        // 工具类不允许实例化
    }

    public static String obtainToken(
            AuthClient authClient,
            RedisCodeReader redisCodeReader,
            String phone) {

        assertNotNull(
                authClient,
                "AuthClient不能为空"
        );

        assertNotNull(
                redisCodeReader,
                "RedisCodeReader不能为空"
        );

        assertNotNull(
                phone,
                "测试手机号不能为空"
        );

        /*
         * 1. 调用真实验证码接口。
         */
        Response sendCodeResponse =
                authClient.sendCode(
                        phone
                );

        ResultAssertions.assertBusinessSuccess(
                sendCodeResponse
        );

        /*
         * 2. 从Redis数据库1读取动态验证码。
         */
        String verificationCode =
                redisCodeReader.waitForCode(
                        phone
                );

        /*
         * 3. 调用真实登录接口。
         */
        Response loginResponse =
                authClient.login(
                        phone,
                        verificationCode
                );

        ResultAssertions.assertBusinessSuccess(
                loginResponse
        );

        /*
         * 4. Token直接位于data字段。
         */
        String token =
                loginResponse
                        .jsonPath()
                        .getString("data");
        assertNotNull(
                token,
                "登录响应中的Token不能为空，响应体："
                        + loginResponse.asString()
        );

        assertFalse(
                token.trim().isEmpty(),
                "登录响应中的Token不能为空字符串"
        );

        return token.trim();
    }
}