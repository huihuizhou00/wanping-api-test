# Seckill Plus Performance Regression

## Final Status

**PASS**

## Fixed Load Model

- Voucher ID: `900013`
- Redis database: `1`
- Threads: `20`
- Ramp-up: `2 seconds`
- Loops per thread: `1`
- Unique tokens: `20`
- Expected samples: `20`

## Baseline Metrics

| Metric | Value |
|---|---:|
| sample_count | 20 |
| error_rate | 0.0 |
| throughput_rps | 4.238 |
| mean_ms | 3023.55 |
| median_ms | 3012.0 |
| p95_ms | 3082 |
| p99_ms | 3082 |
| max_ms | 3082 |

## Candidate Metrics

| Metric | Value |
|---|---:|
| sample_count | 20 |
| error_rate | 0.0 |
| throughput_rps | 4.219 |
| mean_ms | 3016.5 |
| median_ms | 3012.0 |
| p95_ms | 3054 |
| p99_ms | 3054 |
| max_ms | 3054 |

## Performance Regression Checks

| Check | Baseline | Candidate | Change | Threshold | Status |
|---|---:|---:|---:|---:|---|
| sample_count | 20 | 20 | - | 20 | PASS |
| error_rate | 0.0 | 0.0 | 0.00% | 0.0 | PASS |
| throughput_rps | 4.238 | 4.219 | 0.45% | 0.15 | PASS |
| p95_ms | 3082 | 3054 | -0.91% | 0.15 | PASS |
| p99_ms | 3082 | 3054 | -0.91% | 0.2 | PASS |
| max_ms | 3082 | 3054 | -0.91% | observe | OBSERVE |

## Business Consistency Checks

| Check | Baseline | Candidate | Expected | Status |
|---|---:|---:|---:|---|
| voucher_id | 900013 | 900013 | 900013 | PASS |
| db_stock | 0 | 0 | 0 | PASS |
| order_count | 20 | 20 | 20 | PASS |
| distinct_user_count | 20 | 20 | 20 | PASS |
| duplicate_user_count | 0 | 0 | 0 | PASS |
| deduct_log_count | 20 | 20 | 20 | PASS |
| restore_log_count | 0 | 0 | 0 | PASS |
| verify_open_count | 0 | 0 | 0 | PASS |
| recovery_task_count | 0 | 0 | 0 | PASS |
| reconcile_task_count | 0 | 0 | 0 | PASS |
| redis_stock | 0 | 0 | 0 | PASS |
| redis_order_count | 20 | 20 | 20 | PASS |
| redis_trace_count | 20 | 20 | 20 | PASS |
| request_key_count | 0 | 0 | 0 | PASS |

## Environment Warnings

- Baseline root disk warning: `True`
- Candidate root disk warning: `True`
- Performance raw artifacts were written to `/mnt/wanping-performance`.

## Raw Artifact Policy

JTL files, JMeter logs, console logs and token CSV files are excluded from Git.
Only compact round metrics, comparison JSON and this Markdown report are versioned.

Successful requests include the application's approximately three-second asynchronous order confirmation wait.
