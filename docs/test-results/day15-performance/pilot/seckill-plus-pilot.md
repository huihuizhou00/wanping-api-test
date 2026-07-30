# Seckill Plus Pilot

## Result

**PASS**

## Fixed Load Model

- Voucher ID: `900013`
- Redis database: `1`
- Threads: `5`
- Ramp-up: `1 second`
- Loops per thread: `1`
- Unique tokens: `5`
- Expected samples: `5`

## JMeter Metrics

| Metric | Value |
|---|---:|
| Samples | 5 |
| Successes | 5 |
| Errors | 0 |
| Minimum | 3010 ms |
| Median | 3014 ms |
| P95 | 3207 ms |
| Maximum | 3207 ms |

## Business Consistency

| Check | Value |
|---|---:|
| DB stock | 0 |
| Order count | 5 |
| Distinct users | 5 |
| Duplicate users | 0 |
| Deduct logs | 5 |
| Restore logs | 0 |
| Open verification tasks | 0 |
| Recovery tasks | 0 |
| Reconcile tasks | 0 |
| Redis stock | 0 |
| Redis order users | 5 |
| Redis traces | 5 |
| Request keys remaining | 0 |

## Interpretation

The authentication, Redis Lua reservation, RocketMQ order
creation, MySQL stock deduction, order persistence and reconciliation
chain completed successfully.

The approximately three-second latency includes the application's
asynchronous order confirmation wait. With only five samples, the P95
equals the maximum and must not be treated as a formal baseline.

## Raw Artifacts

`/mnt/wanping-performance/runs/seckill-plus-pilot-20260730-135635`
