"""被测系统（SUT）HTTP 外壳：标准库 http.server，零第三方依赖。

启动：
    python app/server.py --port 0 --ttl 900

--port 0 时随机端口，启动完成后在 stdout 打印 `LISTENING <port>` 供测试夹具解析。
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from store import ApiError, Store

MAX_BODY = 64 * 1024


def make_handler(store: Store):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        # ---------- 基础工具 ----------
        def log_message(self, fmt: str, *args) -> None:  # 静音，避免污染测试输出
            pass

        def _send(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _error(self, exc: ApiError) -> None:
            self._send(exc.status, {"error": {"code": exc.code, "message": exc.message}})

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                raise ApiError(413, "BODY_TOO_LARGE", "请求体超过 64KB")
            ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip()
            raw = self.rfile.read(length) if length else b""
            if not raw:
                raise ApiError(400, "EMPTY_BODY", "请求体不能为空")
            if ctype != "application/json":
                raise ApiError(415, "UNSUPPORTED_MEDIA_TYPE", f"不支持的 Content-Type: {ctype or '空'}")
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise ApiError(400, "INVALID_JSON", "请求体不是合法 JSON")
            if not isinstance(data, dict):
                raise ApiError(400, "INVALID_JSON", "请求体必须是 JSON 对象")
            return data

        # ---------- 路由 ----------
        def _dispatch(self, method: str) -> None:
            path = urlparse(self.path).path.rstrip("/") or "/"
            parts = [p for p in path.split("/") if p]

            try:
                if method == "GET" and path == "/health":
                    return self._send(200, {"status": "ok"})

                if method == "GET" and len(parts) == 2 and parts[0] == "products":
                    return self._send(200, store.get_product(parts[1]))

                if method == "GET" and len(parts) == 2 and parts[0] == "stock":
                    return self._send(200, store.get_stock(parts[1]))

                if method == "GET" and len(parts) == 2 and parts[0] == "orders":
                    return self._send(200, store.get_order(parts[1]))

                if method == "POST" and path == "/orders":
                    return self._send(201, store.create_order(self._read_json()))

                if method == "POST" and len(parts) == 3 and parts[0] == "orders" and parts[2] == "pay":
                    return self._send(200, store.pay(parts[1]))

                if method == "POST" and len(parts) == 3 and parts[0] == "orders" and parts[2] == "cancel":
                    return self._send(200, store.cancel(parts[1]))

                # 测试专用：重置 / 超时扫描 / 快照
                if method == "POST" and path == "/admin/reset":
                    store.reset()
                    return self._send(200, {"status": "reset"})

                if method == "POST" and path == "/admin/sweep":
                    body = self._read_json() if int(self.headers.get("Content-Length") or 0) else {}
                    now = body.get("now")
                    if now is not None and not isinstance(now, (int, float)):
                        raise ApiError(400, "INVALID_NOW", "now 必须是数字时间戳")
                    return self._send(200, {"expired": store.sweep_expired(now)})

                if method == "POST" and path == "/admin/shutdown":
                    import threading
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return self._send(200, {"status": "shutting-down"})

                if method == "GET" and path == "/admin/snapshot":
                    return self._send(200, store.snapshot())

                raise ApiError(404, "NOT_FOUND", f"未知接口: {method} {path}")
            except ApiError as exc:
                self._error(exc)

        def do_GET(self) -> None:  # noqa: N802
            self._dispatch("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._dispatch("POST")

        def do_PUT(self) -> None:  # noqa: N802
            self._send(405, {"error": {"code": "METHOD_NOT_ALLOWED", "message": "PUT 不支持"}})

        def do_DELETE(self) -> None:  # noqa: N802
            self._send(405, {"error": {"code": "METHOD_NOT_ALLOWED", "message": "DELETE 不支持"}})

    return Handler


def serve(port: int = 0, ttl: int = 900) -> ThreadingHTTPServer:
    store = Store(order_ttl_seconds=ttl)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(store))
    server.daemon_threads = True
    return server


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--ttl", type=int, default=900)
    args = parser.parse_args()

    server = serve(args.port, args.ttl)
    print(f"LISTENING {server.server_address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    sys.exit(main())
