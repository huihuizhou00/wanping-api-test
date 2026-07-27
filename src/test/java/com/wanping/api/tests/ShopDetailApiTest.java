package com.wanping.api.tests;

import com.wanping.api.assertions.ResultAssertions;
import com.wanping.api.base.BaseTest;
import com.wanping.api.client.ShopDetailClient;
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
 * 商详聚合与优惠券查询接口自动化。
 *
 * 覆盖：
 * 1. 公开访问商详；
 * 2. 聚合结构完整性；
 * 3. 非法shopId格式；
 * 4. 已有商铺优惠券；
 * 5. 不存在商铺优惠券；
 * 6. 优惠券路径参数格式错误。
 */
class ShopDetailApiTest extends BaseTest {

    private static ShopDetailClient shopDetailClient;

    private static long existingShopId;

    private static long notFoundShopId;

    @BeforeAll
    static void initializeShopDetailTests() {

        shopDetailClient =
                new ShopDetailClient();

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
    }

    /**
     * 商详属于公开接口，
     * 不携带Token也应正常访问。
     */
    @Test
    void shouldReturnShopDetailWithoutToken() {

        Response response =
                shopDetailClient.queryShopDetail(
                        existingShopId
                );

        ResultAssertions.assertBusinessSuccess(
                response
        );

        Long actualShopId =
                response.jsonPath()
                        .getLong("data.shopId");

        String shopName =
                response.jsonPath()
                        .getString("data.shopName");

        assertEquals(
                existingShopId,
                actualShopId,
                "商详中的shopId应与请求参数一致"
        );

        assertNotNull(
                shopName,
                "商详中的shopName不能为空"
        );

        assertFalse(
                shopName.trim().isEmpty(),
                "商详中的shopName不能为空字符串"
        );
    }

    /**
     * 商详不是单表查询，
     * 应返回聚合页面所需的主要集合字段。
     */
    @Test
    void shouldReturnCompleteShopDetailAggregate() {

        Response response =
                shopDetailClient.queryShopDetail(
                        existingShopId
                );

        ResultAssertions.assertBusinessSuccess(
                response
        );

        List<Object> tags =
                response.jsonPath()
                        .getList("data.tags");

        List<Object> vouchers =
                response.jsonPath()
                        .getList("data.vouchers");

        List<Object> blogs =
                response.jsonPath()
                        .getList("data.blogs");

        List<Object> reviews =
                response.jsonPath()
                        .getList("data.reviews");

        List<Object> recommendations =
                response.jsonPath()
                        .getList(
                                "data.recommendations"
                        );

        List<Object> relatedShops =
                response.jsonPath()
                        .getList(
                                "data.relatedShops"
                        );

        assertNotNull(
                tags,
                "决策标签列表不能为null"
        );

        assertNotNull(
                vouchers,
                "优惠券列表不能为null"
        );

        assertNotNull(
                blogs,
                "探店博客列表不能为null"
        );

        assertNotNull(
                reviews,
                "评价列表不能为null"
        );

        assertNotNull(
                recommendations,
                "推荐卡片列表不能为null"
        );

        assertNotNull(
                relatedShops,
                "关联商铺列表不能为null"
        );

        /*
         * 源码会根据基础资料生成评分、销量、
         * 评论数等基础决策标签。
         */
        assertFalse(
                tags.isEmpty(),
                "已有商铺的决策标签不应为空"
        );
    }

    /**
     * Long类型路径参数无法解析时，
     * Spring应直接返回HTTP 400。
     */
    @Test
    void shouldReturn400WhenShopDetailIdIsNotNumeric() {

        Response response =
                shopDetailClient
                        .queryShopDetailWithRawId(
                                "not-a-number"
                        );

        assertEquals(
                400,
                response.statusCode(),
                "非数字shopId应返回HTTP 400，响应体："
                        + response.asString()
        );
    }

    /**
     * SQL初始化数据中，商铺1存在优惠券。
     */
    @Test
    void shouldReturnVouchersForExistingShop() {

        Response response =
                shopDetailClient.queryVouchers(
                        existingShopId
                );

        ResultAssertions.assertBusinessSuccess(
                response
        );

        List<Long> shopIds =
                response.jsonPath()
                        .getList(
                                "data.shopId",
                                Long.class
                        );

        assertNotNull(
                shopIds,
                "优惠券shopId列表不能为空"
        );

        assertFalse(
                shopIds.isEmpty(),
                "已有测试商铺应至少存在一张优惠券"
        );

        assertTrue(
                shopIds.stream()
                        .allMatch(
                                shopId ->
                                        shopId != null
                                                && shopId
                                                == existingShopId
                        ),
                "返回优惠券必须全部属于请求商铺"
        );
    }

    /**
     * 不存在商铺没有优惠券，
     * 当前业务实现返回成功加空列表。
     */
    @Test
    void shouldReturnEmptyVoucherListForUnknownShop() {

        Response response =
                shopDetailClient.queryVouchers(
                        notFoundShopId
                );

        ResultAssertions.assertBusinessSuccess(
                response
        );

        List<Object> vouchers =
                response.jsonPath()
                        .getList("data");

        assertNotNull(
                vouchers,
                "优惠券列表不能为null"
        );

        assertTrue(
                vouchers.isEmpty(),
                "不存在商铺的优惠券列表应为空"
        );
    }

    /**
     * 路径参数类型错误在进入Service前失败。
     */
    @Test
    void shouldReturn400WhenVoucherShopIdIsNotNumeric() {

        Response response =
                shopDetailClient
                        .queryVouchersWithRawShopId(
                                "invalid-id"
                        );

        assertEquals(
                400,
                response.statusCode(),
                "非数字shopId应返回HTTP 400，响应体："
                        + response.asString()
        );
    }
}