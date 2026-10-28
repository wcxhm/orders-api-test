# 订单服务接口自动化测试体系

一套可直接运行的接口自动化测试项目：被测系统是一个订单服务（下单 / 支付 / 取消 / 超时关单 / 优惠券 / 库存），
测试侧用 pytest + requests 搭建用例分层、测试数据工厂、断言助手、覆盖率、HTML 报告与需求追踪矩阵。

## 结果

| 指标 | 数值 |
| --- | --- |
| 用例数 | 82（含参数化展开） |
| 需求域 | 7 |
| 全量通过耗时 | 3.5s |
| 被测服务覆盖率 | 96%（server.py 96% / store.py 96%） |
| 发现缺陷 | 1 个（DEF-001，已修复并补回归用例） |

## 目录结构

```
orders-api-test/
├── app/                     # 被测系统（SUT，标准库实现，零第三方依赖）
│   ├── store.py             # 领域规则：库存/订单状态机/优惠券/超时
│   └── server.py            # HTTP 外壳（http.server）+ 测试专用 admin 接口
├── tests/                   # 用例，按需求域分文件
│   ├── conftest.py          # 被测服务生命周期、数据重置、client 夹具
│   ├── test_01_protocol.py  # REQ-01 协议与错误处理
│   ├── test_02_create_order.py
│   ├── test_03_stock.py     # 含并发不超卖
│   ├── test_04_payment.py   # 状态机与幂等
│   ├── test_05_coupon.py
│   ├── test_06_timeout.py   # TTL 边界
│   └── test_07_consistency.py  # 库存/订单/流水对账
├── utils/                   # client / asserts / data_factory
├── scripts/run_ci.py        # 一键回归：用例 + 覆盖率 + 报告 + 追踪矩阵
├── docs/                    # 测试计划、追踪矩阵、缺陷记录
└── reports/                 # 运行产物（HTML 报告、覆盖率、JUnit XML）
```

## 运行

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 只跑用例
.venv\Scripts\python.exe -m pytest

# 一键回归：用例 + 覆盖率 + HTML 报告 + 需求追踪矩阵
.venv\Scripts\python.exe scripts\run_ci.py
```

产物：

- `reports/report.html`：pytest-html 用例报告
- `reports/coverage/index.html`：被测服务覆盖率
- `docs/traceability.md`：需求 → 用例追踪矩阵

## 测试设计要点

- **等价类 / 边界值**：qty 取 0、1、99、100、负数、字符串、浮点、布尔、容器；库存恰好买完 vs 超买 1 件。
- **协议层**：错误路由、不支持的方法、Content-Type、空体、非法 JSON、超长请求体。
- **状态机**：CREATED→PAID→（不可取消）、CREATED→CANCELLED、CREATED→EXPIRED，非法流转返回 409。
- **幂等**：重复支付不刷新支付时间；重复取消不重复返还库存。
- **并发**：12 线程抢 5 件库存，断言成功数恰好 5、拒绝数 7、库存不为负。
- **数据一致性**：`当前库存 = 初始库存 + Σ流水 delta`，并在订单/流水/库存三方对账。
- **时间相关**：用 `/admin/sweep` 注入 now，把 TTL 边界（ttl-1 / ttl）做成确定性用例，不依赖 sleep。

## 已知说明

被测系统是本项目自带的演示服务，目的是提供一个可控对象来演练复杂测试场景（超卖、幂等、超时、对账）。
`/admin/*` 是测试专用接口，生产系统不应暴露。

## 相关项目

- [rag-qa-evaluation](https://github.com/wcxhm/rag-qa-evaluation) —— 企业知识库 RAG 问答 Agent 的输出质量评测与鲁棒性验证（48 题评测集、拒答阈值扫描、OOV 漏拒答缺陷排查）
