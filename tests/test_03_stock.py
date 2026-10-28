"""REQ-03 库存与并发：占用、返还、超卖防护、库存流水。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from utils.asserts import assert_error, assert_ok, assert_stock
from utils.client import ApiClient
from utils.data_factory import SEED_STOCK, ledger_for, make_order, stock_of

import pytest

pytestmark = pytest.mark.req("REQ-03")


def test_ledger_records_each_occupation(api):
    order = make_order(api, "SKU-1001", 2)
    snapshot = assert_ok(api.snapshot())
    entries = ledger_for(snapshot, "SKU-1001", "ORDER_CREATED")
    assert len(entries) == 1
    assert entries[0]["delta"] == -2
    assert entries[0]["order_id"] == order["order_id"]


def test_cancel_returns_stock(api):
    order = make_order(api, "SKU-1001", 3)
    before = stock_of(api, "SKU-1001")
    assert_ok(api.cancel(order["order_id"]))
    assert_stock(api, "SKU-1001", before + 3)


def test_cancel_ledger_delta_is_positive(api):
    order = make_order(api, "SKU-1002", 2)
    assert_ok(api.cancel(order["order_id"]))
    snapshot = assert_ok(api.snapshot())
    entries = ledger_for(snapshot, "SKU-1002", "ORDER_CANCELLED")
    assert len(entries) == 1 and entries[0]["delta"] == 2


def test_concurrent_orders_do_not_oversell(server_url):
    """并发 12 个请求抢 5 件库存：只有 5 个成功，其余 409，库存不为负。"""
    admin = ApiClient(server_url)
    admin.reset()
    stock = SEED_STOCK["SKU-1003"]
    assert stock == 5

    def buy(_):
        client = ApiClient(server_url)
        resp = client.create_order("SKU-1003", 1)
        return resp.status

    with ThreadPoolExecutor(max_workers=12) as pool:
        statuses = list(pool.map(buy, range(12)))

    assert statuses.count(201) == stock, f"成功数应为 {stock}，实际 {statuses.count(201)}"
    assert statuses.count(409) == 12 - stock
    assert_stock(admin, "SKU-1003", 0)
    assert admin.stock("SKU-1003").body["stock"] >= 0


def test_stock_never_negative_after_mixed_operations(api):
    make_order(api, "SKU-1003", 2)
    make_order(api, "SKU-1003", 2)
    assert_error(api.create_order("SKU-1003", 5), 409, "OUT_OF_STOCK")
    assert stock_of(api, "SKU-1003") >= 0


def test_paid_order_still_occupies_stock(api):
    order = make_order(api, "SKU-1001", 2)
    assert_ok(api.pay(order["order_id"]))
    assert_stock(api, "SKU-1001", SEED_STOCK["SKU-1001"] - 2)
