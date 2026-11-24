#!/usr/bin/env python3
"""
benchmark.py — runs every experiment from the proposal and records raw timings.

Experiments (each configuration repeated REPS times; the MEDIAN is reported):
  E1 serial baseline      serial program, N = 10k, 25k, 50k, 100k
  E2 thread scaling       OpenMP static, N = 100k, threads = 1,2,4,6,8,10,12,14
  E3 problem-size scaling OpenMP, N = 10k..100k at 10 threads (all P-cores)
                          and at 14 threads (all cores)
  E4 scheduling           static vs dynamic vs guided, N = 100k, 10 & 14 threads
  E5 SIMD extension       '#pragma omp simd' kernel, N = 100k, several threads

Raw results are appended to results/raw_runs.csv after every single run, so an
interrupted benchmark can simply be restarted: finished runs are skipped.

  python3 scripts/benchmark.py            full benchmark (~45 min on M4 Pro)
  python3 scripts/benchmark.py --quick    small sizes, 2 reps (~1 min, for testing)
"""
import csv
import os
import platform
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin")
RES = os.path.join(ROOT, "results")
FIELDS = ["experiment", "impl", "n", "steps", "threads", "schedule", "chunk",
          "simd", "rep", "time_s", "interactions_per_s", "gflops"]

QUICK = "--quick" in sys.argv
REPS = 2 if QUICK else 5
STEPS = 10
NCPU = os.cpu_count() or 8
SIZES = [2000, 4000, 8000] if QUICK else [10000, 25000, 50000, 100000]
BIG = SIZES[-1]
P_CORES = 10  # Apple M4 Pro: 10 performance + 4 efficiency cores
THREADS = sorted({t for t in [1, 2, 4, 6, 8, 10, 12, 14] if t <= NCPU} | {NCPU})


def plan():
    runs = []  # (experiment, exe, n, threads, schedule, simd)
    for n in SIZES:
        runs.append(("E1_serial", "serial", n, 1, "none", 0))
    for t in THREADS:
        runs.append(("E2_threads", "omp", BIG, t, "static", 0))
    for t in sorted({min(P_CORES, NCPU), NCPU}):
        for n in SIZES:
            runs.append(("E3_size", "omp", n, t, "static", 0))
            runs.append(("E3_size", "omp", n, t, "dynamic", 0))
    for t in sorted({min(P_CORES, NCPU), NCPU}):
        for s in ["static", "dynamic", "guided"]:
            runs.append(("E4_schedule", "omp", BIG, t, s, 0))
    for t in sorted({1, 4, min(P_CORES, NCPU), NCPU}):
        runs.append(("E5_simd", "omp", BIG, t, "static", 1))
    return runs


def key(exp, impl, n, t, s, simd, rep):
    return (exp, impl, str(n), str(t), s, str(simd), str(rep))


def main():
    os.makedirs(RES, exist_ok=True)
    raw = os.path.join(RES, "raw_runs_quick.csv" if QUICK else "raw_runs.csv")
    done = set()
    if os.path.exists(raw):
        with open(raw) as f:
            for r in csv.DictReader(f):
                impl = "serial" if r["impl"] == "serial" else "omp"
                done.add(key(r["experiment"], impl, r["n"], r["threads"],
                             r["schedule"], r["simd"], r["rep"]))
    new_file = not os.path.exists(raw)
    fout = open(raw, "a", newline="")
    w = csv.writer(fout)
    if new_file:
        w.writerow(FIELDS)

    with open(os.path.join(RES, "system_info.txt"), "w") as f:
        cpu = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                             capture_output=True, text=True).stdout.strip() \
            if platform.system() == "Darwin" else platform.processor()
        cc = subprocess.run(["cc", "--version"], capture_output=True, text=True).stdout.splitlines()[0]
        f.write(f"CPU: {cpu}\nLogical cores: {NCPU}\nOS: {platform.platform()}\n"
                f"Compiler: {cc}\nFlags: -O3 -std=c11 (+ -fopenmp via libomp for the parallel build)\n"
                f"Steps per run: {STEPS}\nRepetitions: {REPS} (median reported)\n")

    runs = plan()
    total = len(runs) * REPS
    i = 0
    for rep in range(1, REPS + 1):        # outer loop over reps: spreads any
        for exp, impl, n, t, s, simd in runs:  # background noise across configs
            i += 1
            if key(exp, impl, n, t, s, simd, rep) in done:
                continue
            if impl == "serial":
                cmd = [os.path.join(BIN, "nbody_serial"), "-n", str(n), "-s", str(STEPS)]
            else:
                cmd = [os.path.join(BIN, "nbody_omp"), "-n", str(n), "-s", str(STEPS),
                       "-t", str(t), "-S", s] + (["-v"] if simd else [])
            out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
            c = [l for l in out.splitlines() if l.startswith("CSV,")][0].split(",")
            row = [exp, c[1], n, STEPS, c[4], c[5], c[6], c[7], rep, c[8], c[9], c[10]]
            w.writerow(row)
            fout.flush()
            print(f"[{i:3d}/{total}] {exp:12s} {c[1]:8s} N={n:<6d} t={c[4]:>2s} "
                  f"{s:8s} -> {float(c[8]):9.3f} s", flush=True)
    fout.close()
    print("done ->", os.path.relpath(raw, ROOT))


if __name__ == "__main__":
    main()
