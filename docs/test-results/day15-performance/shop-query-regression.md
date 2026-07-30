# Shop Query Performance Regression

## Final Status

**PASS**

## Fixed Load Model

- Threads: 20
- Ramp-up: 2 seconds
- Loops per thread: 20
- Expected samples: 400
- Warm-up samples: 20

## Baseline Metrics

| Metric | Value |
|---|---:|
| sample_count | 400 |
| error_count | 0 |
| error_rate | 0.00% |
| throughput_rps | 209.205 |
| mean_ms | 6.595 |
| median_ms | 6.0 |
| p90_ms | 8 |
| p95_ms | 8 |
| p99_ms | 16 |
| max_ms | 57 |

## Candidate Metrics

| Metric | Value |
|---|---:|
| sample_count | 400 |
| error_count | 0 |
| error_rate | 0.00% |
| throughput_rps | 213.447 |
| mean_ms | 6.162 |
| median_ms | 6.0 |
| p90_ms | 7 |
| p95_ms | 8 |
| p99_ms | 9 |
| max_ms | 57 |

## Regression Checks

| Metric | Baseline | Candidate | Change | Threshold | Status |
|---|---:|---:|---:|---|---|
| Sample Count | 400 | 400 | N/A | equal to 400 | PASS |
| Error Rate | 0.0 | 0.0 | 0.00% | <= 1.00% | PASS |
| Throughput | 209.205 | 213.447 | -2.03% | decrease <= 15.00% | PASS |
| P95 | 8 | 8 | 0.00% | increase <= 20.00% | PASS |
| P99 | 16 | 9 | -43.75% | increase <= 25.00% | PASS |
| Max | 57 | 57 | 0.00% | observe only | OBSERVE |

## Environment Warnings

- Root disk usage: 92%
- Baseline status: provisional
- Candidate status: provisional

## Raw Artifact Policy

- Raw JTL and JMeter logs: `/mnt/wanping-performance`
- Raw runtime artifacts are not committed to Git.
