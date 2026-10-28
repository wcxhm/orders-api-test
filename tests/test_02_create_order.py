"""REQ-02 下单主流程：等价类、边界值、字段校验、库存占用。"""

from __future__ import annotations

import pytest

from utils.asserts import assert_error, assert_ok, assert_stock
from utils.data_factory import SEED_PRICE, SEED_STOCK, make_order, stock_of

pytestmark = pytest.mark.req("REQ-02")


def test_create_order_success(api):
    body = assert_ok(api.create_order("SKU-1001", 1), 201)
    assert body["status"] == "CREATED"
    assert body["sku"] == "SKU-1001"
    assert body["qty"] == 1
    assert body["amount"] == SEED_PRICE["SKU-1001"]
    assert body["order_id"].startswith("O")


def test_create_order_deducts_stock_immediately(api):
    before = stock_of(api, "SKU-1001")
    make_order(api, "SKU-1001", 3)
    assert_stock(api, "SKU-1001", before - 3)


def test_amount_is_price_times_qty(api):
    body = assert_ok(api.create_order("SKU-1002", 4), 201)
    assert body["amount"] == SEED_PRICE["SKU-1002"] * 4


@pytest.mark.parametrize("qty", [0, -1, 100, 1000, "3", 3.5, True, False, [], {}])
def test_invalid_qty_rejected(api, qty):
    resp = api.create_order("SKU-1001", qty)
    assert_error(resp, 400, "INVALID_QTY")


def test_missing_qty_rejected(api):
    resp = api.create_order("SKU-1001", None)
    assert_error(resp, 400, "INVALID_QTY")


def test_missing_sku_rejected(api):
    resp = api.create_order(None, 1)
    assert_error(resp, 400, "INVALID_SKU")


@pytest.mark.parametrize("sku", ["", "   ", 123, [], {"a": 1}])
def test_invalid_sku_rejected(api, sku):
    resp = api.create_order(sku, 1)
    assert_error(resp, 400, "INVALID_SKU")


def test_unknown_sku_rejected(api):
    resp = api.create_order("SKU-9999", 1)
    assert_error(resp, 404, "PRODUCT_NOT_FOUND")


def test_qty_lower_boundary_one(api):
    body = assert_ok(api.create_order("SKU-1001", 1), 201)
    assert body["qty"] == 1


def test_order_exact_remaining_stock(api):
    """边界：恰好买完库存应成功，再下一单报库存不足。"""
    stock = stock_of(api, "SKU-1003")  # 种子 5
    assert_ok(api.create_order("SKU-1003", stock), 201)
    assert_stock(api, "SKU-1003", 0)
    assert_error(api.create_order("SKU-1003", 1), 409, "OUT_OF_STOCK")


def test_order_more_than_stock_rejected(api):
    resp = api.create_order("SKU-1003", SEED_STOCK["SKU-1003"] + 1)
    assert_error(resp, 409, "OUT_OF_STOCK")


def test_stock_unchanged_after_failed_order(api):
    """失败的下单不能占用库存。"""
    before = stock_of(api, "SKU-1003")
    assert_error(api.create_order("SKU-1003", 99), 409, "OUT_OF_STOCK")
    assert_stock(api, "SKU-1003", before)


def test_consecutive_orders_deplete_stock(api):
    make_order(api, "SKU-1003", 2)
    make_order(api, "SKU-1003", 2)
    assert_stock(api, "SKU-1003", 1)


def test_order_detail_matches_create_response(api):
    created = assert_ok(api.create_order("SKU-1002", 2), 201)
    detail = assert_ok(api.order(created["order_id"]))
    for field in ("order_id", "sku", "qty", "amount", "status"):
        assert detail[field] == created[field]
