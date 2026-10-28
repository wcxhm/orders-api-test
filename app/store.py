"""被测系统（SUT）：内存版订单 / 库存 / 优惠券领域模型。

设计要点（这些是测试要验证的业务规则，不是实现细节）：
  1. 下单时校验 sku、数量区间 1..99、库存充足；成功后立即占用库存。
  2. 优惠券只能用一次，且有门槛（满减）；不可用时下单失败。
  3. 支付：CREATED -> PAID；重复支付幂等（返回同一结果，不重复扣款）。
  4. 取消：仅 CREATED 可取消，取消后返还库存；PAID 不可取消。
  5. 超时：CREATED 超过 TTL 未支付 -> EXPIRED，返还库存。
  6. 所有库存变动都要有流水（ledger），用于数据一致性校验。
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any


class ApiError(Exception):
    """带 HTTP 语义的业务异常。"""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


DEFAULT_PRODUCTS: dict[str, dict[str, Any]] = {
    "SKU-1001": {"name": "机械键盘", "price": 39900, "stock": 20},
    "SKU-1002": {"name": "无线鼠标", "price": 12900, "stock": 50},
    "SKU-1003": {"name": "显示器支架", "price": 25900, "stock": 5},
}

DEFAULT_COUPONS: dict[str, dict[str, Any]] = {
    "C10": {"discount": 1000, "min_spend": 10000},
    "C50": {"discount": 5000, "min_spend": 50000},
}


class Store:
    def __init__(self, order_ttl_seconds: int = 900):
        self.ttl = order_ttl_seconds
        self._lock = threading.RLock()
        self.products: dict[str, dict[str, Any]] = {}
        self.orders: dict[str, dict[str, Any]] = {}
        self.coupons: dict[str, dict[str, Any]] = {}
        self.ledger: list[dict[str, Any]] = []
        self.reset()

    # ---------- 测试辅助 ----------
    def reset(self) -> None:
        with self._lock:
            self.products = {k: dict(v) for k, v in DEFAULT_PRODUCTS.items()}
            self.coupons = {k: {**v, "used": False} for k, v in DEFAULT_COUPONS.items()}
            self.orders = {}
            self.ledger = []

    def _log(self, sku: str, delta: int, reason: str, order_id: str | None) -> None:
        self.ledger.append(
            {
                "sku": sku,
                "delta": delta,
                "reason": reason,
                "order_id": order_id,
                "at": time.time(),
            }
        )

    # ---------- 查询 ----------
    def get_product(self, sku: str) -> dict[str, Any]:
        product = self.products.get(sku)
        if product is None:
            raise ApiError(404, "PRODUCT_NOT_FOUND", f"sku 不存在: {sku}")
        return {"sku": sku, **product}

    def get_stock(self, sku: str) -> dict[str, Any]:
        product = self.products.get(sku)
        if product is None:
            raise ApiError(404, "PRODUCT_NOT_FOUND", f"sku 不存在: {sku}")
        return {"sku": sku, "stock": product["stock"]}

    def get_order(self, order_id: str) -> dict[str, Any]:
        order = self.orders.get(order_id)
        if order is None:
            raise ApiError(404, "ORDER_NOT_FOUND", f"订单不存在: {order_id}")
        return dict(order)

    # ---------- 下单 ----------
    def create_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        sku = payload.get("sku")
        qty = payload.get("qty")
        coupon_code = payload.get("coupon")

        if not isinstance(sku, str) or not sku.strip():
            raise ApiError(400, "INVALID_SKU", "sku 必填且为非空字符串")
        if isinstance(qty, bool) or not isinstance(qty, int):
            raise ApiError(400, "INVALID_QTY", "qty 必须是整数")
        if qty < 1 or qty > 99:
            raise ApiError(400, "INVALID_QTY", "qty 取值范围 1..99")
        if coupon_code is not None and not isinstance(coupon_code, str):
            raise ApiError(400, "INVALID_COUPON", "coupon 必须是字符串")

        with self._lock:
            product = self.products.get(sku)
            if product is None:
                raise ApiError(404, "PRODUCT_NOT_FOUND", f"sku 不存在: {sku}")
            if product["stock"] < qty:
                raise ApiError(409, "OUT_OF_STOCK", f"库存不足: 剩余 {product['stock']}")

            amount = product["price"] * qty
            discount = 0
            if coupon_code:
                coupon = self.coupons.get(coupon_code)
                if coupon is None:
                    raise ApiError(400, "INVALID_COUPON", f"优惠券不存在: {coupon_code}")
                if coupon["used"]:
                    raise ApiError(409, "COUPON_USED", f"优惠券已被使用: {coupon_code}")
                if amount < coupon["min_spend"]:
                    raise ApiError(400, "COUPON_NOT_APPLICABLE", "未达到优惠券使用门槛")
                discount = coupon["discount"]
                coupon["used"] = True

            order_id = f"O{uuid.uuid4().hex[:12].upper()}"
            order = {
                "order_id": order_id,
                "sku": sku,
                "qty": qty,
                "amount": amount - discount,
                "discount": discount,
                "coupon": coupon_code,
                "status": "CREATED",
                "created_at": time.time(),
                "paid_at": None,
            }
            product["stock"] -= qty
            self._log(sku, -qty, "ORDER_CREATED", order_id)
            self.orders[order_id] = order
            return dict(order)

    # ---------- 支付 ----------
    def pay(self, order_id: str) -> dict[str, Any]:
        with self._lock:
            order = self.orders.get(order_id)
            if order is None:
                raise ApiError(404, "ORDER_NOT_FOUND", f"订单不存在: {order_id}")
            if order["status"] == "PAID":
                return dict(order)  # 幂等：重复支付返回同一结果
            if order["status"] != "CREATED":
                raise ApiError(409, "INVALID_STATE", f"订单状态 {order['status']} 不可支付")
            order["status"] = "PAID"
            order["paid_at"] = time.time()
            return dict(order)

    # ---------- 取消 ----------
    def cancel(self, order_id: str) -> dict[str, Any]:
        with self._lock:
            order = self.orders.get(order_id)
            if order is None:
                raise ApiError(404, "ORDER_NOT_FOUND", f"订单不存在: {order_id}")
            if order["status"] == "CANCELLED":
                return dict(order)  # 幂等
            if order["status"] != "CREATED":
                raise ApiError(409, "INVALID_STATE", f"订单状态 {order['status']} 不可取消")
            order["status"] = "CANCELLED"
            self.products[order["sku"]]["stock"] += order["qty"]
            self._log(order["sku"], order["qty"], "ORDER_CANCELLED", order_id)
            return dict(order)

    # ---------- 超时扫描 ----------
    def sweep_expired(self, now: float | None = None) -> list[str]:
        now = time.time() if now is None else now
        expired: list[str] = []
        with self._lock:
            for order in self.orders.values():
                if order["status"] != "CREATED":
                    continue
                if now - order["created_at"] >= self.ttl:
                    order["status"] = "EXPIRED"
                    self.products[order["sku"]]["stock"] += order["qty"]
                    self._log(order["sku"], order["qty"], "ORDER_EXPIRED", order["order_id"])
                    expired.append(order["order_id"])
        return expired

    # ---------- 一致性快照 ----------
    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "stock": {sku: p["stock"] for sku, p in self.products.items()},
                "orders": [dict(o) for o in self.orders.values()],
                "ledger": [dict(e) for e in self.ledger],
            }
