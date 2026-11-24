## Table 1 — Serial vs parallel at every problem size (10 steps, median of runs)

| N | Serial time | OpenMP 10 thr (static) | Speedup | OpenMP 14 thr (dynamic) | Speedup | Best | Best speedup |
|---|---|---|---|---|---|---|---|
| 10,000 | 1.023 s | 0.115 s | 8.92x | 0.104 s | 9.82x | 0.104 s | 9.82x |
| 25,000 | 6.393 s | 0.696 s | 9.18x | 0.624 s | 10.24x | 0.624 s | 10.24x |
| 50,000 | 25.656 s | 2.799 s | 9.16x | 2.562 s | 10.01x | 2.562 s | 10.01x |
| 100,000 | 101.935 s | 11.268 s | 9.05x | 10.320 s | 9.88x | 10.320 s | 9.88x |

## Table 2 — Thread scaling, N = 100,000 (static schedule)

| Threads | Time | Speedup vs serial | Efficiency | Speedup vs OpenMP-1 |
|---|---|---|---|---|
| serial | 101.93 s | 1.00x | 100% | — |
| 1 | 101.29 s | 1.01x | 101% | 1.00x |
| 2 | 51.73 s | 1.97x | 99% | 1.96x |
| 4 | 26.41 s | 3.86x | 96% | 3.84x |
| 6 | 17.83 s | 5.72x | 95% | 5.68x |
| 8 | 13.46 s | 7.57x | 95% | 7.52x |
| 10 | 11.37 s | 8.97x | 90% | 8.91x |
| 12 | 10.78 s | 9.46x | 79% | 9.40x |
| 14 | 10.84 s | 9.40x | 67% | 9.34x |

## Table 3 — Scheduling, N = 100,000

| Threads | static | dynamic,64 | guided,64 |
|---|---|---|---|
| 10 | 11.30 s (9.02x) | 11.28 s (9.03x) | 11.30 s (9.02x) |
| 14 | 10.53 s (9.68x) | 10.24 s (9.95x) | 10.34 s (9.86x) |

## Table 4 — SIMD extension, N = 100,000 (static)

| Threads | parallel for | parallel for + omp simd | SIMD gain | Speedup vs serial |
|---|---|---|---|---|
| 1 | 101.29 s | 68.53 s | 1.48x | 1.49x |
| 4 | 26.41 s | 17.89 s | 1.48x | 5.70x |
| 10 | 11.37 s | 7.47 s | 1.52x | 13.65x |
| 14 | 10.84 s | 7.37 s | 1.47x | 13.82x |

## Table 5 — Serial run time vs N (O(N²) check)

| N | Serial time | Ratio to previous | Expected (N ratio)² |
|---|---|---|---|
| 10,000 | 1.023 s | — | — |
| 25,000 | 6.393 s | 6.25 | 6.25 |
| 50,000 | 25.656 s | 4.01 | 4.00 |
| 100,000 | 101.935 s | 3.97 | 4.00 |
