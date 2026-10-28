# 需求追踪矩阵（由 scripts/run_ci.py 自动生成）

共 7 个需求域、82 条用例（含参数化展开）。

| 需求 | 用例数 | 覆盖用例 |
| --- | --- | --- |
| REQ-01 接口协议与错误处理 | 12 | `test_health_ok`<br>`test_unknown_route_returns_json_404`<br>`test_unsupported_method_put`<br>`test_unsupported_method_delete`<br>`test_empty_body_rejected`<br>`test_wrong_content_type_rejected`<br>`test_invalid_json_rejected`<br>`test_oversized_body_rejected`<br>…（共 12 条） |
| REQ-02 下单主流程 | 27 | `test_create_order_success`<br>`test_create_order_deducts_stock_immediately`<br>`test_amount_is_price_times_qty`<br>`test_invalid_qty_rejected`<br>`test_missing_qty_rejected`<br>`test_missing_sku_rejected`<br>`test_invalid_sku_rejected`<br>`test_unknown_sku_rejected`<br>…（共 27 条） |
| REQ-03 库存与并发 | 6 | `test_ledger_records_each_occupation`<br>`test_cancel_returns_stock`<br>`test_cancel_ledger_delta_is_positive`<br>`test_concurrent_orders_do_not_oversell`<br>`test_stock_never_negative_after_mixed_operations`<br>`test_paid_order_still_occupies_stock` |
| REQ-04 支付与状态机 | 9 | `test_pay_created_order`<br>`test_pay_is_idempotent`<br>`test_pay_unknown_order`<br>`test_pay_cancelled_order_rejected`<br>`test_pay_expired_order_rejected`<br>`test_cancel_paid_order_rejected`<br>`test_cancel_is_idempotent_and_restores_once`<br>`test_cancel_unknown_order`<br>…（共 9 条） |
| REQ-05 优惠券 | 13 | `test_coupon_applied_when_eligible`<br>`test_coupon_below_threshold_rejected`<br>`test_unknown_coupon_rejected`<br>`test_coupon_wrong_type_rejected`<br>`test_coupon_cannot_be_reused`<br>`test_failed_order_does_not_consume_coupon`<br>`test_coupon_discount_reflected_in_order_detail`<br>`test_no_coupon_means_zero_discount`<br>…（共 13 条） |
| REQ-06 超时关单 | 8 | `test_not_expired_before_ttl`<br>`test_expired_at_ttl_boundary`<br>`test_expired_order_returns_stock`<br>`test_expired_order_writes_ledger`<br>`test_paid_order_never_expires`<br>`test_cancelled_order_not_expired_twice`<br>`test_sweep_is_idempotent`<br>`test_cancel_expired_order_rejected` |
| REQ-07 数据一致性 | 7 | `test_stock_equals_seed_plus_ledger`<br>`test_stock_after_pay_and_expire`<br>`test_every_order_has_valid_status`<br>`test_order_amount_consistent_with_product`<br>`test_ledger_references_existing_orders`<br>`test_no_negative_stock_in_snapshot`<br>`test_paid_orders_keep_stock_deducted_in_ledger` |
