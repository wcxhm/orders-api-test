"""断言助手：把「HTTP 状态码 + 业务错误码」的校验收敛成一行。

直接 assert status == 400 会在失败时丢失业务错误码信息；
assert_error 同时校验两者，并在消息里带上完整响应体。
"""

from __future__ import annotations

from utils.client import ApiResponse


def assert_ok(resp: ApiResponse, status: int = 200) -> dict:
    assert resp.status == status, f"期望 {status}，实际 {resp.status}，响应: {resp.body}"
    assert isinstance(resp.body, dict), f"响应不是 JSON 对象: {resp.body}"
    assert "error" not in resp.body, f"不应返回错误: {resp.body}"
    return resp.body


def assert_error(resp: ApiResponse, status: int, code: str) -> dict:
    assert resp.status == status, f"期望 {status}，实际 {resp.status}，响应: {resp.body}"
    assert isinstance(resp.body, dict) and "error" in resp.body, f"缺少 error 结构: {resp.body}"
    actual = resp.error_code
    assert actual == code, f"期望错误码 {code}，实际 {actual}，响应: {resp.body}"
    return resp.body


def assert_stock(api, sku: str, expected: int) -> None:
    resp = api.stock(sku)
    body = assert_ok(resp)
    assert body["stock"] == expected, f"{sku} 库存期望 {expected}，实际 {body['stock']}"


def assert_order_status(api, order_id: str, expected: str) -> dict:
    body = assert_ok(api.order(order_id))
    assert body["status"] == expected, f"订单状态期望 {expected}，实际 {body['status']}"
    return body
