"""REQ-04 支付与状态机：幂等、非法流转、取消规则。"""

from __future__ import annotations

import pytest

from utils.asserts import assert_error, assert_ok, assert_order_status, assert_stock
from utils.data_factory import make_order, stock_of

pytestmark = pytest.mark.req("REQ-04")


def test_pay_created_order(api):
    order = make_order(api, "SKU-1001", 1)
    body = assert_ok(api.pay(order["order_id"]))
    assert body["status"] == "PAID"
    assert body["paid_at"] is not None


def test_pay_is_idempotent(api):
    order = make_order(api, "SKU-1001", 1)
    first = assert_ok(api.pay(order["order_id"]))
    second = assert_ok(api.pay(order["order_id"]))
    assert second["status"] == "PAID"
    assert second["paid_at"] == first["paid_at"], "重复支付不应刷新支付时间"


def test_pay_unknown_order(api):
    assert_error(api.pay("O-NOT-EXIST"), 404, "ORDER_NOT_FOUND")


def test_pay_cancelled_order_rejected(api):
    order = make_order(api, "SKU-1001", 1)
    assert_ok(api.cancel(order["order_id"]))
    assert_error(api.pay(order["order_id"]), 409, "INVALID_STATE")


def test_pay_expired_order_rejected(api):
    order = make_order(api, "SKU-1001", 1)
    assert_ok(api.sweep(order["created_at"] + 901))
    assert_order_status(api, order["order_id"], "EXPIRED")
    assert_error(api.pay(order["order_id"]), 409, "INVALID_STATE")


def test_cancel_paid_order_rejected(api):
    order = make_order(api, "SKU-1001", 1, pay=True)
    assert_error(api.cancel(order["order_id"]), 409, "INVALID_STATE")
    assert_order_status(api, order["order_id"], "PAID")


def test_cancel_is_idempotent_and_restores_once(api):
    order = make_order(api, "SKU-1001", 2)
    before = stock_of(api, "SKU-1001")
    assert_ok(api.cancel(order["order_id"]))
    assert_ok(api.cancel(order["order_id"]))
    assert_stock(api, "SKU-1001", before + 2), "重复取消不能重复返还库存"


def test_cancel_unknown_order(api):
    assert_error(api.cancel("O-NOT-EXIST"), 404, "ORDER_NOT_FOUND")


def test_cancelled_order_cannot_be_reused(api):
    order = make_order(api, "SKU-1001", 1)
    assert_ok(api.cancel(order["order_id"]))
    assert_order_status(api, order["order_id"], "CANCELLED")
    # 取消后库存已返还，但该订单本身不可再支付
    assert_error(api.pay(order["order_id"]), 409, "INVALID_STATE")
