"""REQ-05 优惠券：门槛、一次性、失败不消耗。"""

from __future__ import annotations

import pytest

from utils.asserts import assert_error, assert_ok
from utils.data_factory import SEED_PRICE, make_order

pytestmark = pytest.mark.req("REQ-05")


def test_coupon_applied_when_eligible(api):
    body = assert_ok(api.create_order("SKU-1001", 1, coupon="C10"), 201)
    assert body["discount"] == 1000
    assert body["amount"] == SEED_PRICE["SKU-1001"] - 1000


def test_coupon_below_threshold_rejected(api):
    # C50 门槛 50000，鼠标单价 12900
    resp = api.create_order("SKU-1002", 1, coupon="C50")
    assert_error(resp, 400, "COUPON_NOT_APPLICABLE")


def test_unknown_coupon_rejected(api):
    assert_error(api.create_order("SKU-1001", 1, coupon="NOPE"), 400, "INVALID_COUPON")


@pytest.mark.parametrize("coupon", [123, [], {}])
def test_coupon_wrong_type_rejected(api, coupon):
    assert_error(api.create_order("SKU-1001", 1, coupon=coupon), 400, "INVALID_COUPON")


def test_coupon_cannot_be_reused(api):
    assert_ok(api.create_order("SKU-1001", 1, coupon="C10"), 201)
    assert_error(api.create_order("SKU-1001", 1, coupon="C10"), 409, "COUPON_USED")


def test_failed_order_does_not_consume_coupon(api):
    """未达门槛而失败，不能把券标成已用。"""
    assert_error(api.create_order("SKU-1002", 1, coupon="C50"), 400, "COUPON_NOT_APPLICABLE")
    body = assert_ok(api.create_order("SKU-1001", 2, coupon="C50"), 201)
    assert body["discount"] == 5000


def test_coupon_discount_reflected_in_order_detail(api):
    created = assert_ok(api.create_order("SKU-1001", 1, coupon="C10"), 201)
    detail = assert_ok(api.order(created["order_id"]))
    assert detail["coupon"] == "C10"
    assert detail["discount"] == 1000
    assert detail["amount"] == created["amount"]


def test_no_coupon_means_zero_discount(api):
    body = assert_ok(api.create_order("SKU-1001", 1), 201)
    assert body["discount"] == 0


def test_cancel_releases_coupon(api):
    """取消订单后，优惠券应回到未使用状态（用户可再用）。"""
    order = make_order(api, "SKU-1001", 1, coupon="C10")
    assert_ok(api.cancel(order["order_id"]))
    body = assert_ok(api.create_order("SKU-1001", 1, coupon="C10"), 201)
    assert body["discount"] == 1000


def test_expire_releases_coupon(api):
    """超时关单后，优惠券同样应释放。"""
    order = make_order(api, "SKU-1001", 1, coupon="C10")
    assert_ok(api.sweep(order["created_at"] + 901))
    body = assert_ok(api.create_order("SKU-1001", 1, coupon="C10"), 201)
    assert body["discount"] == 1000


def test_paid_then_coupon_still_used(api):
    """已支付订单用过的券也不能再用。"""
    order = make_order(api, "SKU-1001", 1, coupon="C10", pay=True)
    assert order["status"] == "PAID"
    assert_error(api.create_order("SKU-1001", 1, coupon="C10"), 409, "COUPON_USED")
