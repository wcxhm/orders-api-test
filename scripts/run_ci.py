"""CI 入口：跑全量用例 -> 合并被测服务覆盖率 -> HTML 报告 -> 需求追踪矩阵。

用法：
    python scripts/run_ci.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
DOCS = ROOT / "docs"

REQ_BY_FILE = {
    "test_01_protocol.py": "REQ-01 接口协议与错误处理",
    "test_02_create_order.py": "REQ-02 下单主流程",
    "test_03_stock.py": "REQ-03 库存与并发",
    "test_04_payment.py": "REQ-04 支付与状态机",
    "test_05_coupon.py": "REQ-05 优惠券",
    "test_06_timeout.py": "REQ-06 超时关单",
    "test_07_consistency.py": "REQ-07 数据一致性",
}


def _run(cmd: list[str]) -> int:
    print("$", " ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=str(ROOT))


def run_pytest() -> int:
    REPORTS.mkdir(exist_ok=True)
    return _run([
        sys.executable, "-m", "pytest",
        f"--html={REPORTS / 'report.html'}", "--self-contained-html",
        f"--junitxml={REPORTS / 'junit.xml'}",
    ])


def coverage_report() -> None:
    """合并被测服务子进程产生的 .coverage.* 文件并出报告。"""
    _run([sys.executable, "-m", "coverage", "combine"])
    _run([sys.executable, "-m", "coverage", "report", "-m"])
    _run([sys.executable, "-m", "coverage", "html", "-d", str(REPORTS / "coverage")])


def build_traceability() -> None:
    """需求 -> 用例 追踪矩阵：用例数来自 pytest 实际收集结果，名称来自测试函数。"""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    counts: dict[str, int] = {}
    for line in proc.stdout.splitlines():
        match = re.search(r"tests[\\/](\S+?\.py):\s*(\d+)", line.strip())
        if match:
            counts[match.group(1)] = int(match.group(2))

    req_map: dict[str, tuple[int, list[str]]] = {}
    for filename, req in REQ_BY_FILE.items():
        path = ROOT / "tests" / filename
        names = re.findall(r"^def (test_\w+)", path.read_text(encoding="utf-8"), re.M)
        req_map[req] = (counts.get(filename, len(names)), names)

    DOCS.mkdir(exist_ok=True)
    total = sum(c for c, _ in req_map.values())
    lines = [
        "# 需求追踪矩阵（由 scripts/run_ci.py 自动生成）",
        "",
        f"共 {len(req_map)} 个需求域、{total} 条用例（含参数化展开）。",
        "",
        "| 需求 | 用例数 | 覆盖用例 |",
        "| --- | --- | --- |",
    ]
    for req in sorted(req_map):
        count, names = req_map[req]
        shown = "<br>".join(f"`{n}`" for n in names[:8])
        if len(names) > 8:
            shown += f"<br>…（共 {count} 条）"
        lines.append(f"| {req} | {count} | {shown} |")
    (DOCS / "traceability.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"追踪矩阵已生成：{DOCS / 'traceability.md'}（{total} 条用例）")


if __name__ == "__main__":
    code = run_pytest()
    coverage_report()
    build_traceability()
    sys.exit(code)
