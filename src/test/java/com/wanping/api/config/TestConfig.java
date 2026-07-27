package com.wanping.api.config;

import java.io.IOException;
import java.io.InputStream;
import java.util.Properties;

/**
 * 自动化测试环境配置。
 *
 * 配置读取优先级：
 * JVM启动参数 > 环境变量 > test.properties
 */
public final class TestConfig {

    private static final String CONFIG_FILE =
            "config/test.properties";

    private static final Properties PROPERTIES =
            new Properties();

    static {
        try (InputStream inputStream =
                     TestConfig.class
                             .getClassLoader()
                             .getResourceAsStream(
                                     CONFIG_FILE
                             )) {

            if (inputStream == null) {
                throw new IllegalStateException(
                        "找不到测试配置文件："
                                + CONFIG_FILE
                );
            }

            PROPERTIES.load(inputStream);

        } catch (IOException exception) {
            throw new IllegalStateException(
                    "读取测试配置文件失败",
                    exception
            );
        }
    }

    private TestConfig() {
        // 工具类不允许实例化
    }

    /**
     * 获取必填配置。
     */
    public static String getRequired(
            String key) {

        String value = get(key, null);

        if (value == null
                || value.trim().isEmpty()) {
            throw new IllegalStateException(
                    "缺少必填配置：" + key
            );
        }

        return value.trim();
    }

    /**
     * 获取配置，未配置时返回默认值。
     */
    public static String get(
            String key,
            String defaultValue) {

        /*
         * 第一优先级：
         * mvn test -Dbase.url=...
         */
        String systemValue =
                System.getProperty(key);

        if (systemValue != null
                && !systemValue.trim().isEmpty()) {
            return systemValue.trim();
        }

        /*
         * 第二优先级：
         * BASE_URL、API_PREFIX
         */
        String environmentKey =
                key.toUpperCase()
                        .replace('.', '_');

        String environmentValue =
                System.getenv(environmentKey);

        if (environmentValue != null
                && !environmentValue
                        .trim()
                        .isEmpty()) {
            return environmentValue.trim();
        }

        /*
         * 第三优先级：
         * test.properties
         */
        String propertyValue =
                PROPERTIES.getProperty(key);

        if (propertyValue == null) {
            return defaultValue;
        }

        return propertyValue.trim();
    }

    public static int getInt(
            String key,
            int defaultValue) {

        String value = get(
                key,
                String.valueOf(defaultValue)
        );

        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException exception) {
            throw new IllegalStateException(
                    "配置不是合法整数："
                            + key
                            + "="
                            + value,
                    exception
            );
        }
    }
}