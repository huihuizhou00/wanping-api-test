package com.wanping.api.tests;

import com.wanping.api.assertions.ResultAssertions;
import com.wanping.api.base.BaseTest;
import com.wanping.api.client.AuthClient;
import com.wanping.api.config.TestConfig;
import com.wanping.api.support.RedisCodeReader;
import com.wanping.api.support.TokenUtil;
import io.restassured.response.Response;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.MethodOrderer;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 用户登录与鉴权接口自动化测试。
 *
 * 覆盖：
 * 1. 无Token访问；
 * 2. 非法手机号；
 * 3. 验证码生成与Redis落库；
 * 4. 错误验证码；
 * 5. 正确验证码登录和查询当前用户。
 */
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class LoginApiTest extends BaseTest {

    private static AuthClient authClient;

    private static RedisCodeReader redisCodeReader;

    private static String testPhone;

    @BeforeAll
    static void initializeLoginTest() {

        authClient = new AuthClient();

        redisCodeReader =
                new RedisCodeReader();

        testPhone =
                TestConfig.getRequired(
                        "test.user.phone"
                );
    }

    /**
     * 未登录时，LoginInterceptor应返回401。
     *
     * 该用例放在鉴权正向用例前面，
     * 避免当前后端ThreadLocal清理缺失问题
     * 干扰基础未登录校验。
     */
    @Test
    @Order(1)
    void shouldReturn401WhenQueryingCurrentUserWithoutToken() {

        Response response =
                authClient.currentUserWithoutToken();

        ResultAssertions.assertUnauthorized(
                response
        );
    }

    /**
     * 非法手机号应返回业务失败。
     */
    @Test
    @Order(2)
    void shouldRejectInvalidPhoneWhenSendingCode() {

        Response response =
                authClient.sendCode(
                        "123456"
                );

        ResultAssertions.assertBusinessFailure(
                response,
                "手机号格式错误"
        );
    }

    /**
     * 合法手机号发送验证码后，
     * Redis数据库1中应出现6位数字验证码。
     */
    @Test
    @Order(3)
    void shouldStoreSixDigitCodeInRedis() {

        Response response =
                authClient.sendCode(
                        testPhone
                );

        ResultAssertions.assertBusinessSuccess(
                response
        );

        String code =
                redisCodeReader.waitForCode(
                        testPhone
                );

        assertNotNull(
                code,
                "Redis验证码不能为空"
        );

        assertTrue(
                code.matches("\\d{6}"),
                "验证码应为6位数字，实际值：" + code
        );
    }

    /**
     * 错误验证码应返回业务失败，
     * 但HTTP状态仍然是200。
     */
    @Test
    @Order(4)
    void shouldRejectWrongVerificationCode() {

        Response sendCodeResponse =
                authClient.sendCode(
                        testPhone
                );

        ResultAssertions.assertBusinessSuccess(
                sendCodeResponse
        );

        String actualCode =
                redisCodeReader.waitForCode(
                        testPhone
                );

        /*
         * 避免极小概率下真实验证码正好为000000。
         */
        String wrongCode =
                "000000".equals(actualCode)
                        ? "111111"
                        : "000000";

        Response loginResponse =
                authClient.login(
                        testPhone,
                        wrongCode
                );

        ResultAssertions.assertBusinessFailure(
                loginResponse,
                "验证码不一致，请重新输入"
        );
    }

    /**
     * 完整验证：
     *
     * 发送验证码
     * → Redis读取验证码
     * → 登录获取Token
     * → 携带Token查询当前用户。
     */
    @Test
    @Order(5)
    void shouldLoginAndQueryCurrentUserWithToken() {

        String token =
                TokenUtil.obtainToken(
                        authClient,
                        redisCodeReader,
                        testPhone
                );

        assertNotNull(
                token,
                "登录Token不能为空"
        );

        assertFalse(
                token.trim().isEmpty(),
                "登录Token不能为空字符串"
        );

        Response currentUserResponse =
                authClient.currentUser(
                        token
                );

        ResultAssertions.assertBusinessSuccess(
                currentUserResponse
        );

        Long userId =
                currentUserResponse
                        .jsonPath()
                        .getLong("data.id");

        String nickName =
                currentUserResponse
                        .jsonPath()
                        .getString("data.nickName");

        assertNotNull(
                userId,
                "当前用户ID不能为空"
        );

        assertNotNull(
                nickName,
                "当前用户昵称不能为空"
        );

        assertFalse(
                nickName.trim().isEmpty(),
                "当前用户昵称不能为空字符串"
        );
    }
}