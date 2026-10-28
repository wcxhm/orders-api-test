"""REQ-06 超时关单：TTL 边界、库存返还、幂等扫描。"""

from __future__ import annotations

import pytest

from utils.asserts import assert_error, assert_ok, assert_order_status, assert_stock
from utils.data_factory import SEED_STOCK, ledger_for, make_order, stock_of

pytestmark = pytest.mark.req("REQ-06")

TTL = 900


def test_not_expired_before_ttl(api):
    order = make_order(api, "SKU-1001", 1)
    body = assert_ok(api.sweep(order["created_at"] + TTL - 1))
    assert body["expired"] == []
    assert_order_status(api, order["order_id"], "CREATED")


def test_expired_at_ttl_boundary(api):
    """边界：正好等于 TTL 即到期（>= 规则）。"""
    order = make_order(api, "SKU-1001", 1)
    body = assert_ok(api.sweep(order["created_at"] + TTL))
    assert body["expired"] == [order["order_id"]]
    assert_order_status(api, order["order_id"], "EXPIRED")


def test_expired_order_returns_stock(api):
    order = make_order(api, "SKU-1001", 2)
    assert_ok(api.sweep(order["created_at"] + TTL + 1))
    assert_stock(api, "SKU-1001", SEED_STOCK["SKU-1001"])


def test_expired_order_writes_ledger(api):
    order = make_order(api, "SKU-1002", 3)
    assert_ok(api.sweep(order["created_at"] + TTL + 1))
    snapshot = assert_ok(api.snapshot())
    entries = ledger_for(snapshot, "SKU-1002", "ORDER_EXPIRED")
    assert len(entries) == 1
    assert entries[0]["delta"] == 3
    assert entries[0]["order_id"] == order["order_id"]


def test_paid_order_never_expires(api):
    order = make_order(api, "SKU-1001", 1, pay=True)
    body = assert_ok(api.sweep(order["created_at"] + TTL + 1))
    assert body["expired"] == []
    assert_order_status(api, order["order_id"], "PAID")


def test_cancelled_order_not_expired_twice(api):
    order = make_order(api, "SKU-1001", 1)
    assert_ok(api.cancel(order["order_id"]))
    before = stock_of(api, "SKU-1001")
    body = assert_ok(api.sweep(order["created_at"] + TTL + 1))
    assert body["expired"] == []
    assert_stock(api, "SKU-1001", before), "取消已返还，扫描不能再返还一次"


def test_sweep_is_idempotent(api):
    order = make_order(api, "SKU-1001", 1)
    first = assert_ok(api.sweep(order["created_at"] + TTL + 1))
    second = assert_ok(api.sweep(order["created_at"] + TTL + 1))
    assert first["expired"] == [order["order_id"]]
    assert second["expired"] == []


def test_cancel_expired_order_rejected(api):
    order = make_order(api, "SKU-1001", 1)
    assert_ok(api.sweep(order["created_at"] + TTL + 1))
    assert_error(api.cancel(order["order_id"]), 409, "INVALID_STATE")
