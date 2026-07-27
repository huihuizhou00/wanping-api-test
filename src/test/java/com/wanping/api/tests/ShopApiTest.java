package com.wanping.api.tests;

import com.wanping.api.assertions.ResultAssertions;
import com.wanping.api.base.BaseTest;
import com.wanping.api.client.ShopClient;
import com.wanping.api.config.TestConfig;
import io.restassured.response.Response;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 商铺查询接口自动化。
 *
 * 覆盖：
 * 1. 已存在ID；
 * 2. 不存在ID；
 * 3. 名称关键字；
 * 4. 空名称分页；
 * 5. 类型分页；
 * 6. 缺少必填参数。
 */
class ShopApiTest extends BaseTest {

    private static ShopClient shopClient;

    private static long existingShopId;

    private static long notFoundShopId;

    private static String shopNameKeyword;

    private static int shopTypeId;

    @BeforeAll
    static void initializeShopTests() {

        shopClient =
                new ShopClient();

        existingShopId =
                Long.parseLong(
                        TestConfig.getRequired(
                                "test.shop.id"
                        )
                );

        notFoundShopId =
                Long.parseLong(
                        TestConfig.getRequired(
                                "test.shop.not-found.id"
                        )
                );

        shopNameKeyword =
                TestConfig.getRequired(
                        "test.shop.name.keyword"
                );

        shopTypeId =
                TestConfig.getInt(
                        "test.shop.type.id",
                        1
                );
    }

    @Test
    void shouldReturnShopWhenQueryingExistingId() {

        Response response =
                shopClient.queryById(
                        existingShopId
                );

        ResultAssertions.assertBusinessSuccess(
                response
        );

        Long actualShopId =
                response.jsonPath()
                        .getLong("data.id");

        String shopName =
                response.jsonPath()
                        .getString("data.name");

        assertEquals(
                existingShopId,
                actualShopId
        );

        assertNotNull(
                shopName,
                "商铺名称不能为空"
        );

        assertFalse(
                shopName.trim().isEmpty(),
                "商铺名称不能为空字符串"
        );
    }

    @Test
    void shouldReturnBusinessFailureWhenShopDoesNotExist() {

        Response response =
                shopClient.queryById(
                        notFoundShopId
                );

        ResultAssertions.assertBusinessFailure(
                response,
                "店铺不存在！"
        );
    }

    @Test
    void shouldFindShopByNameKeyword() {

        Response response =
                shopClient.queryByName(
                        shopNameKeyword,
                        1
                );

        ResultAssertions.assertBusinessSuccess(
                response
        );

        List<String> shopNames =
                response.jsonPath()
                        .getList(
                                "data.name",
                                String.class
                        );

        assertNotNull(
                shopNames,
                "商铺名称列表不能为空"
        );

        assertFalse(
                shopNames.isEmpty(),
                "名称查询结果不能为空"
        );

        assertTrue(
                shopNames.stream()
                        .anyMatch(
                                name ->
                                        name != null
                                                && name.contains(
                                                shopNameKeyword
                                        )
                        ),
                "至少一个商铺名称应包含关键字："
                        + shopNameKeyword
        );
    }

    @Test
    void shouldReturnFirstPageWhenNameIsNotProvided() {

        Response response =
                shopClient
                        .queryFirstPageWithoutName();

        ResultAssertions.assertBusinessSuccess(
                response
        );

        List<Object> shops =
                response.jsonPath()
                        .getList("data");

        assertNotNull(
                shops,
                "商铺列表不能为空"
        );

        assertFalse(
                shops.isEmpty(),
                "第一页商铺列表不能为空"
        );

        assertTrue(
                shops.size() <= 10,
                "返回数量不应超过MAX_PAGE_SIZE"
        );
    }

    @Test
    void shouldReturnShopsOfRequestedType() {

        Response response =
                shopClient.queryByType(
                        shopTypeId,
                        1
                );

        ResultAssertions.assertBusinessSuccess(
                response
        );

        List<Integer> typeIds =
                response.jsonPath()
                        .getList(
                                "data.typeId",
                                Integer.class
                        );

        assertNotNull(
                typeIds,
                "类型ID列表不能为空"
        );

        assertFalse(
                typeIds.isEmpty(),
                "类型查询结果不能为空"
        );

        assertTrue(
                typeIds.stream()
                        .allMatch(
                                typeId ->
                                        typeId != null
                                                && typeId
                                                == shopTypeId
                        ),
                "返回商铺的typeId必须全部等于："
                        + shopTypeId
        );
    }

    @Test
    void shouldReturn400WhenTypeIdIsMissing() {

        Response response =
                shopClient
                        .queryByTypeWithoutTypeId();

        assertEquals(
                400,
                response.statusCode(),
                "缺少必填typeId应返回HTTP 400，响应体："
                        + response.asString()
        );
    }
}