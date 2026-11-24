# Parallel N-Body Simulation with OpenMP

**Course:** Parallel and Distributed Computing (PDC), FAST NUCES Karachi · **Instructor:** Muhammad Minhal Raza
**Group:** Abdul Ahad Munaf (K23-0590) · Syed Kashan Hamid (K23-0747) · Mohammad Mehroz (K23-0748)

Direct all-pairs gravitational N-body simulation (O(N²) per step) in C11, with a
**pure serial baseline** and an **OpenMP shared-memory parallel version**, plus a
benchmark suite that compares the two (time, speedup, efficiency) across thread
counts, problem sizes, loop schedules and SIMD vectorisation.

## Folder layout

```
src/nbody.h          shared constants, Bodies struct (Structure-of-Arrays), options
src/common.c         allocation, seeded initialisation, output, CLI parsing (used by BOTH programs)
src/nbody_serial.c   SEQUENTIAL baseline — compiled WITHOUT OpenMP
src/nbody_omp.c      OpenMP version — same physics, plus pragmas (+ simd kernel, reductions)
scripts/validate.py  correctness: parallel == serial (bit-identical) + energy conservation
scripts/benchmark.py runs all experiments, 5 repetitions each -> results/raw_runs.csv
scripts/plot.py      medians -> results/summary.md, results/summary.csv, graphs/*.png
results/             raw data, summary tables, validation output, system info
graphs/              all figures used in the report
report/              final project report (.docx) + generator script
```

## Build & run

```bash
brew install libomp        # macOS only, once (Linux gcc already has OpenMP)
make                       # builds bin/nbody_serial and bin/nbody_omp

./bin/nbody_serial -n 20000 -s 10                 # serial
./bin/nbody_omp    -n 20000 -s 10 -t 10           # OpenMP, 10 threads, static
./bin/nbody_omp    -n 20000 -s 10 -t 14 -S dynamic
./bin/nbody_omp    -n 20000 -s 10 -t 10 -v        # + '#pragma omp simd'
./bin/nbody_omp    -n 4000  -s 100 -e             # print energy drift

make run        # 30-second serial vs parallel demo (good for the live presentation)
make validate   # correctness checks
make bench      # full benchmark (~45 min on Apple M4 Pro)
make plots      # regenerate tables + graphs
```

Options: `-n` bodies, `-s` steps, `-r` seed, `-t` threads, `-S static|dynamic|guided`,
`-c` chunk, `-v` SIMD kernel, `-e` energy check, `-o file` dump final state.

## Method in one paragraph

Each step uses the leapfrog (kick–drift–kick) integrator. The force loop computes, for
every body *i*, the softened gravitational acceleration from all *N* bodies. In the
OpenMP version the outer *i* loop is split across threads with
`#pragma omp parallel for`; each thread writes only its own `a[i]`, so there are no
races, locks or atomics. Newton's third-law symmetry is intentionally not used, because
updating `a[j]` from another thread's row would create write conflicts. Kick and drift
loops are parallelised separately; the implicit barrier after each loop ensures no
thread reads half-updated positions. Total energy uses `reduction(+:ke,pe)`.

See `report/` for the full report. The team presentation handoff is the shared doc: https://claude.ai/artifact/MvnEvh54qRawnb3JW2H84M
