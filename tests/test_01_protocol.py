"""REQ-01 接口协议与错误处理：路由、方法、Content-Type、请求体边界。"""

from __future__ import annotations

import pytest

from utils.asserts import assert_error, assert_ok

pytestmark = pytest.mark.req("REQ-01")


def test_health_ok(api):
    body = assert_ok(api.health())
    assert body["status"] == "ok"


def test_unknown_route_returns_json_404(api):
    resp = api.get("/no-such-endpoint")
    assert_error(resp, 404, "NOT_FOUND")


def test_unsupported_method_put(api):
    resp = api.request("PUT", "/orders")
    assert_error(resp, 405, "METHOD_NOT_ALLOWED")


def test_unsupported_method_delete(api):
    resp = api.request("DELETE", "/orders/O1")
    assert_error(resp, 405, "METHOD_NOT_ALLOWED")


def test_empty_body_rejected(api):
    resp = api.post("/orders")
    assert_error(resp, 400, "EMPTY_BODY")


def test_wrong_content_type_rejected(api):
    resp = api.request(
        "POST",
        "/orders",
        data='{"sku":"SKU-1001","qty":1}',
        headers={"Content-Type": "text/plain"},
    )
    assert_error(resp, 415, "UNSUPPORTED_MEDIA_TYPE")


@pytest.mark.parametrize("raw", ['{"sku":', "[1,2,3]", '"just a string"', "123"])
def test_invalid_json_rejected(api, raw):
    resp = api.request(
        "POST", "/orders", data=raw, headers={"Content-Type": "application/json"}
    )
    assert_error(resp, 400, "INVALID_JSON")


def test_oversized_body_rejected(api):
    big = {"sku": "SKU-1001", "qty": 1, "note": "x" * (65 * 1024)}
    resp = api.post("/orders", big)
    assert_error(resp, 413, "BODY_TOO_LARGE")


def test_error_body_shape(api):
    """错误响应统一为 {"error": {"code", "message"}}。"""
    body = assert_error(api.get("/orders/UNKNOWN"), 404, "ORDER_NOT_FOUND")
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]
