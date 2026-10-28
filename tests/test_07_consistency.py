"""REQ-07 数据一致性：库存、订单、流水三方对账。"""

from __future__ import annotations

import pytest

from utils.asserts import assert_ok
from utils.data_factory import SEED_PRICE, SEED_STOCK, make_order

pytestmark = pytest.mark.req("REQ-07")

VALID_STATUS = {"CREATED", "PAID", "CANCELLED", "EXPIRED"}


def _ledger_sum(snapshot: dict, sku: str) -> int:
    return sum(e["delta"] for e in snapshot["ledger"] if e["sku"] == sku)


def test_stock_equals_seed_plus_ledger(api):
    order = make_order(api, "SKU-1001", 3)
    make_order(api, "SKU-1002", 2)
    assert_ok(api.cancel(order["order_id"]))

    snapshot = assert_ok(api.snapshot())
    for sku, seed in SEED_STOCK.items():
        assert snapshot["stock"][sku] == seed + _ledger_sum(snapshot, sku), f"{sku} 库存与流水不一致"


def test_stock_after_pay_and_expire(api):
    paid = make_order(api, "SKU-1001", 2, pay=True)
    unpaid = make_order(api, "SKU-1003", 2)
    assert_ok(api.sweep(unpaid["created_at"] + 901))

    snapshot = assert_ok(api.snapshot())
    for sku, seed in SEED_STOCK.items():
        assert snapshot["stock"][sku] == seed + _ledger_sum(snapshot, sku)

    assert snapshot["stock"]["SKU-1001"] == SEED_STOCK["SKU-1001"] - 2
    assert snapshot["stock"]["SKU-1003"] == SEED_STOCK["SKU-1003"]
    assert paid["status"] == "PAID"


def test_every_order_has_valid_status(api):
    make_order(api, "SKU-1001", 1)
    make_order(api, "SKU-1002", 1, pay=True)
    snapshot = assert_ok(api.snapshot())
    for order in snapshot["orders"]:
        assert order["status"] in VALID_STATUS, order


def test_order_amount_consistent_with_product(api):
    make_order(api, "SKU-1001", 2)
    snapshot = assert_ok(api.snapshot())
    for order in snapshot["orders"]:
        expected = SEED_PRICE[order["sku"]] * order["qty"] - order["discount"]
        assert order["amount"] == expected, f"订单金额不一致: {order}"


def test_ledger_references_existing_orders(api):
    make_order(api, "SKU-1001", 1)
    snapshot = assert_ok(api.snapshot())
    order_ids = {o["order_id"] for o in snapshot["orders"]}
    for entry in snapshot["ledger"]:
        assert entry["order_id"] in order_ids


def test_no_negative_stock_in_snapshot(api):
    make_order(api, "SKU-1003", 5)
    snapshot = assert_ok(api.snapshot())
    assert all(v >= 0 for v in snapshot["stock"].values())


def test_paid_orders_keep_stock_deducted_in_ledger(api):
    make_order(api, "SKU-1002", 4, pay=True)
    snapshot = assert_ok(api.snapshot())
    created = [e for e in snapshot["ledger"] if e["reason"] == "ORDER_CREATED"]
    assert sum(e["delta"] for e in created) == -4
    assert not [e for e in snapshot["ledger"] if e["reason"] in {"ORDER_CANCELLED", "ORDER_EXPIRED"}]
