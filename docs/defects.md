# 缺陷记录

## DEF-001 取消/超时关单后优惠券未释放（已修复）

| 项 | 内容 |
| --- | --- |
| 发现方式 | 需求 REQ-05 补充「订单未成交时优惠券应可再用」的规则用例 |
| 严重级别 | 中（影响用户体验，不阻塞下单） |
| 发现时间 | 首轮用例执行 |
| 关联用例 | `tests/test_05_coupon.py::test_cancel_releases_coupon`、`::test_expire_releases_coupon` |

### 复现步骤

1. `POST /orders`，sku=SKU-1001，qty=1，coupon=C10 → 201，`discount=1000`；
2. `POST /orders/{id}/cancel` → 200，`status=CANCELLED`，库存已返还；
3. 再次 `POST /orders`，同样带 `coupon=C10`。

### 期望 / 实际

- 期望：201，`discount=1000`（券随订单关闭而释放）
- 实际：409 `COUPON_USED`「优惠券已被使用: C10」

超时关单（`POST /admin/sweep` 使订单变为 EXPIRED）后同样复现。

### 根因

`Store.create_order` 在占用优惠券时直接把 `coupon["used"]` 置为 `True`，
而 `Store.cancel` / `Store.sweep_expired` 只做了「返还库存 + 记流水」，没有对应的优惠券释放逻辑——
**资源占用与资源释放不对称**。

### 修复

在 `cancel` 与 `sweep_expired` 关闭订单时调用统一的 `_release_coupon(order)`：
订单上带券则把券恢复为未使用。两条用例保留为回归用例。

### 回归验证

修复后执行全量用例：82 passed（原 80 条 + 2 条回归）。
