"""HTTP 客户端封装：统一超时、JSON 解析、错误码提取。

测试代码只关心「发什么请求、得到什么语义结果」，不关心 requests 细节。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


@dataclass
class ApiResponse:
    status: int
    body: Any

    @property
    def error_code(self) -> str | None:
        if isinstance(self.body, dict):
            return (self.body.get("error") or {}).get("code")
        return None

    def __repr__(self) -> str:  # 断言失败时可读
        return f"<ApiResponse {self.status} {self.body}>"


class ApiClient:
    def __init__(self, base_url: str, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    # ---------- 底层 ----------
    def request(self, method: str, path: str, **kwargs) -> ApiResponse:
        kwargs.setdefault("timeout", self.timeout)
        resp = self.session.request(method, f"{self.base_url}{path}", **kwargs)
        try:
            body = resp.json()
        except ValueError:
            body = resp.text
        return ApiResponse(resp.status_code, body)

    def get(self, path: str, **kwargs) -> ApiResponse:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, json_body: Any = None, **kwargs) -> ApiResponse:
        if json_body is not None:
            kwargs["json"] = json_body
        return self.request("POST", path, **kwargs)

    # ---------- 业务语义 ----------
    def health(self) -> ApiResponse:
        return self.get("/health")

    def product(self, sku: str) -> ApiResponse:
        return self.get(f"/products/{sku}")

    def stock(self, sku: str) -> ApiResponse:
        return self.get(f"/stock/{sku}")

    def create_order(self, sku: str | None = None, qty: int | str | None = 1, coupon: str | None = None,
                     **extra) -> ApiResponse:
        payload: dict[str, Any] = {}
        if sku is not None:
            payload["sku"] = sku
        if qty is not None:
            payload["qty"] = qty
        if coupon is not None:
            payload["coupon"] = coupon
        payload.update(extra)
        return self.post("/orders", payload)

    def order(self, order_id: str) -> ApiResponse:
        return self.get(f"/orders/{order_id}")

    def pay(self, order_id: str) -> ApiResponse:
        return self.post(f"/orders/{order_id}/pay")

    def cancel(self, order_id: str) -> ApiResponse:
        return self.post(f"/orders/{order_id}/cancel")

    # ---------- 测试管理员接口 ----------
    def reset(self) -> ApiResponse:
        return self.post("/admin/reset")

    def sweep(self, now: float | None = None) -> ApiResponse:
        return self.post("/admin/sweep", {} if now is None else {"now": now})

    def snapshot(self) -> ApiResponse:
        return self.get("/admin/snapshot")
