"""pytest 全局夹具：启动被测服务、按用例重置数据、提供 API 客户端。"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.client import ApiClient  # noqa: E402


def _wait_health(base_url: str, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if requests.get(f"{base_url}/health", timeout=0.5).status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(0.1)
    raise RuntimeError(f"被测服务在 {timeout}s 内未就绪: {base_url}")


@pytest.fixture(scope="session")
def server_url() -> str:
    # 用 coverage 启动被测服务子进程（parallel 模式），会话结束后由 run_ci.py 合并统计
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "coverage", "run", "--parallel-mode",
            str(ROOT / "app" / "server.py"), "--port", "0", "--ttl", "900",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=str(ROOT),
    )
    try:
        line = (proc.stdout.readline() or "").strip()
        assert line.startswith("LISTENING"), f"被测服务启动失败，输出: {line!r}"
        base_url = f"http://127.0.0.1:{int(line.split()[1])}"
        _wait_health(base_url)
        yield base_url
    finally:
        # 优雅关闭：让被测服务进程正常退出，coverage 才能把数据写盘
        try:
            requests.post(f"{base_url}/admin/shutdown", timeout=2)
        except requests.RequestException:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture()
def api(server_url: str) -> ApiClient:
    """每个用例独立的干净数据。"""
    client = ApiClient(server_url)
    assert client.reset().status == 200
    return client
