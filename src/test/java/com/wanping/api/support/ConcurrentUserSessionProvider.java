package com.wanping.api.support;

import com.wanping.api.client.AuthClient;
import io.restassured.response.Response;

import java.util.ArrayList;
import java.util.List;

import static io.restassured.RestAssured.given;

/**
 * 固定并发测试用户会话准备器。
 *
 * 首次运行时，登录接口会自动创建测试用户；
 * 后续运行复用相同手机号，不会持续生成新用户。
 */
public class ConcurrentUserSessionProvider {

    private final AuthClient authClient;

    private final RedisCodeReader redisCodeReader;

    public ConcurrentUserSessionProvider() {
        this.authClient = new AuthClient();
        this.redisCodeReader = new RedisCodeReader();
    }

    public List<UserSession> obtainSessions(
            String phonePrefix,
            int phoneStart,
            int userCount) {

        List<UserSession> sessions =
                new ArrayList<>(userCount);

        for (int index = 0;
             index < userCount;
             index++) {

            int sequence =
                    phoneStart + index;

            String phone =
                    phonePrefix
                            + String.format(
                            "%02d",
                            sequence
                    );

            String token =
                    TokenUtil.obtainToken(
                            authClient,
                            redisCodeReader,
                            phone
                    );

            Response meResponse =
                    given()
                            .header(
                                    "authorization",
                                    token
                            )
                            .when()
                            .get("/user/me")
                            .then()
                            .extract()
                            .response();

            if (meResponse.statusCode() != 200) {
                throw new IllegalStateException(
                        "查询并发测试用户失败，phone="
                                + phone
                                + "，response="
                                + meResponse.asString()
                );
            }

            Boolean success =
                    meResponse.jsonPath()
                            .get("success");

            if (!Boolean.TRUE.equals(success)) {
                throw new IllegalStateException(
                        "并发测试用户登录状态异常，phone="
                                + phone
                                + "，response="
                                + meResponse.asString()
                );
            }

            Number userIdValue =
                    meResponse.jsonPath()
                            .get("data.id");

            if (userIdValue == null) {
                throw new IllegalStateException(
                        "未获得并发测试用户ID，phone="
                                + phone
                );
            }

            sessions.add(
                    new UserSession(
                            userIdValue.longValue(),
                            phone,
                            token
                    )
            );
        }

        return sessions;
    }

    public static final class UserSession {

        private final long userId;

        private final String phone;

        private final String token;

        public UserSession(
                long userId,
                String phone,
                String token) {

            this.userId = userId;
            this.phone = phone;
            this.token = token;
        }

        public long getUserId() {
            return userId;
        }

        public String getPhone() {
            return phone;
        }

        public String getToken() {
            return token;
        }

        @Override
        public String toString() {
            return "UserSession{"
                    + "userId=" + userId
                    + ", phone='" + phone + '\''
                    + '}';
        }
    }
}