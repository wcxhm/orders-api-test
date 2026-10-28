"""测试数据工厂：每个测试通过这里造数据，避免用例之间共享状态。"""

from __future__ import annotations

from utils.asserts import assert_ok

# 与 app/store.py 的默认种子保持一致，测试显式声明依赖的初始库存
SEED_STOCK = {
    "SKU-1001": 20,
    "SKU-1002": 50,
    "SKU-1003": 5,
}

SEED_PRICE = {
    "SKU-1001": 39900,
    "SKU-1002": 12900,
    "SKU-1003": 25900,
}


def make_order(api, sku: str = "SKU-1001", qty: int = 1, coupon: str | None = None, pay: bool = False) -> dict:
    """下一个订单（可选直接支付），返回订单体。"""
    resp = api.create_order(sku=sku, qty=qty, coupon=coupon)
    order = assert_ok(resp, 201)
    if pay:
        assert_ok(api.pay(order["order_id"]))
        order = assert_ok(api.order(order["order_id"]))
    return order


def stock_of(api, sku: str) -> int:
    return assert_ok(api.stock(sku))["stock"]


def ledger_for(snapshot: dict, sku: str, reason: str | None = None) -> list[dict]:
    entries = [e for e in snapshot["ledger"] if e["sku"] == sku]
    if reason is not None:
        entries = [e for e in entries if e["reason"] == reason]
    return entries
