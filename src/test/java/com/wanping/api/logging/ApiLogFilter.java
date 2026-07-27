package com.wanping.api.logging;

import io.qameta.allure.Allure;
import io.restassured.filter.Filter;
import io.restassured.filter.FilterContext;
import io.restassured.response.Response;
import io.restassured.specification.FilterableRequestSpecification;
import io.restassured.specification.FilterableResponseSpecification;

import java.util.concurrent.TimeUnit;

/**
 * 统一记录接口请求与响应。
 *
 * authorization、验证码和登录Token只保存脱敏结果，
 * 避免敏感数据进入终端日志和Allure报告。
 */
public class ApiLogFilter implements Filter {

    @Override
    public Response filter(
            FilterableRequestSpecification request,
            FilterableResponseSpecification responseSpecification,
            FilterContext context) {

        long startTime =
                System.nanoTime();

        String requestLog =
                buildRequestLog(request);

        System.out.println();
        System.out.println(
                "================ API REQUEST ================"
        );
        System.out.println(requestLog);

        /*
         * 常规测试线程中写入Allure请求附件。
         *
         * 并发专项的工作线程没有JUnit测试上下文，
         * 因此不会错误地生成游离附件。
         */
        attachIfTestContextExists(
                "HTTP请求 - "
                        + request.getMethod()
                        + " "
                        + request.getURI(),
                "text/plain",
                requestLog,
                ".txt"
        );

        Response response =
                context.next(
                        request,
                        responseSpecification
                );

        long costMs =
                TimeUnit.NANOSECONDS
                        .toMillis(
                                System.nanoTime()
                                        - startTime
                        );

        String responseBody =
                maskResponseBody(
                        request.getURI(),
                        response.asString()
                );

        String responseSummary =
                "Status: "
                        + response.statusCode()
                        + "\nCost: "
                        + costMs
                        + " ms\nContent-Type: "
                        + safeValue(
                                response.contentType()
                        );

        System.out.println(
                "================ API RESPONSE ==============="
        );

        System.out.println(
                responseSummary.replace(
                        '\n',
                        ' '
                )
        );

        System.out.println(
                "ResponseBody: "
                        + responseBody
        );

        System.out.println(
                "============================================="
        );

        attachIfTestContextExists(
                "HTTP响应摘要 - "
                        + request.getMethod()
                        + " "
                        + request.getURI(),
                "text/plain",
                responseSummary,
                ".txt"
        );

        attachIfTestContextExists(
                "HTTP响应正文 - "
                        + request.getMethod()
                        + " "
                        + request.getURI(),
                responseContentType(response),
                responseBody,
                responseFileExtension(response)
        );

        return response;
    }

    /**
     * 生成终端日志和Allure附件共用的请求文本。
     */
    private static String buildRequestLog(
            FilterableRequestSpecification request) {

        StringBuilder builder =
                new StringBuilder();

        builder.append(
                request.getMethod()
        );

        builder.append(' ');

        builder.append(
                request.getURI()
        );

        if (!request.getQueryParams()
                .isEmpty()) {

            builder.append('\n');

            builder.append(
                    "QueryParams: "
            );

            builder.append(
                    maskSensitiveText(
                            String.valueOf(
                                    request.getQueryParams()
                            )
                    )
            );
        }

        String authorization =
                request.getHeaders()
                        .getValue(
                                "authorization"
                        );

        if (authorization != null
                && !authorization
                .trim()
                .isEmpty()) {

            builder.append('\n');

            builder.append(
                    "authorization: "
            );

            builder.append(
                    maskToken(
                            authorization
                    )
            );
        }

        Object requestBody =
                request.getBody();

        if (requestBody != null) {

            builder.append('\n');

            builder.append(
                    "RequestBody: "
            );

            builder.append(
                    maskSensitiveText(
                            String.valueOf(
                                    requestBody
                            )
                    )
            );
        }

        return builder.toString();
    }

    /**
     * 只有当前线程存在Allure测试上下文时才添加附件。
     *
     * VoucherOversellConcurrencyTest中的20个请求运行在
     * ExecutorService工作线程中，这些线程没有JUnit测试上下文，
     * 因此在这里跳过。后续由主测试线程添加并发结果汇总附件。
     */
    private static void attachIfTestContextExists(
            String name,
            String mediaType,
            String content,
            String fileExtension) {

        if (!Allure.getLifecycle()
                .getCurrentTestCaseOrStep()
                .isPresent()) {

            return;
        }

        Allure.addAttachment(
                name,
                mediaType,
                safeValue(content),
                fileExtension
        );
    }

    /**
     * 对响应体中的敏感数据进行脱敏。
     *
     * 登录接口成功时Token位于data字段，
     * 因此需要针对/user/login额外处理。
     */
    private static String maskResponseBody(
            String requestUri,
            String responseBody) {

        String masked =
                maskSensitiveText(
                        safeValue(
                                responseBody
                        )
                );

        if (requestUri != null
                && requestUri.contains(
                "/user/login"
        )) {

            masked =
                    masked.replaceAll(
                            "(\"data\"\\s*:\\s*\")[^\"]*(\")",
                            "$1******$2"
                    );
        }

        return masked;
    }

    /**
     * 脱敏JSON、Map或表单格式中的敏感字段。
     */
    private static String maskSensitiveText(
            String text) {

        String masked =
                safeValue(text);

        /*
         * JSON格式：
         * "code":"123456"
         * "token":"..."
         * "authorization":"..."
         */
        masked =
                masked.replaceAll(
                        "(?i)(\"?(authorization|token|code)\"?"
                                + "\\s*[:=]\\s*\")[^\"]*(\")",
                        "$1******$3"
                );

        /*
         * Map或表单格式：
         * code=123456
         * token=xxxx
         */
        masked =
                masked.replaceAll(
                        "(?i)((authorization|token|code)"
                                + "\\s*=\\s*)[^,}\\s&]+",
                        "$1******"
                );

        return masked;
    }

    private static String responseContentType(
            Response response) {

        String contentType =
                response.contentType();

        if (contentType != null
                && contentType
                .toLowerCase()
                .contains("json")) {

            return "application/json";
        }

        return "text/plain";
    }

    private static String responseFileExtension(
            Response response) {

        if ("application/json".equals(
                responseContentType(
                        response
                )
        )) {

            return ".json";
        }

        return ".txt";
    }

    private static String safeValue(
            String value) {

        return value == null
                ? ""
                : value;
    }

    private static String maskToken(
            String token) {

        String trimmedToken =
                token.trim();

        if (trimmedToken.length() <= 8) {
            return "********";
        }

        return trimmedToken.substring(
                0,
                4
        )
                + "..."
                + trimmedToken.substring(
                trimmedToken.length() - 4
        );
    }
}
