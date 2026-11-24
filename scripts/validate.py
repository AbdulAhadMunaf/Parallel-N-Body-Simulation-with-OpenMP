#!/usr/bin/env python3
"""
validate.py — correctness checks for the OpenMP N-body code.

Check 1  Serial vs parallel: run the serial program and the OpenMP program
         (several thread counts / schedules) on the SAME seeded input and
         compare the final positions and velocities element by element.
         - plain OpenMP kernel: expected BIT-IDENTICAL to serial, because each
           body's inner sum is still done by one thread in the same order.
         - omp simd kernel: expected to differ only by rounding (~1e-13),
           because SIMD lanes change the order of the floating-point additions.
Check 2  Physics: total energy (kinetic + potential) must stay ~constant.

Results are written to results/validation.txt (used by the report).
"""
import os
import struct
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin")
TMP = os.path.join(ROOT, "results", "tmp")
OUT = os.path.join(ROOT, "results", "validation.txt")
N, STEPS = 8000, 20
NCPU = os.cpu_count() or 4


def run(cmd):
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    csv = [l for l in res.stdout.splitlines() if l.startswith("CSV,")][0].split(",")
    return res.stdout, csv


def load(path):
    with open(path, "rb") as f:
        (n,) = struct.unpack("<Q", f.read(8))
        data = np.frombuffer(f.read(), dtype=np.float64)
    return data.reshape(6, n)  # x, y, z, vx, vy, vz


def main():
    os.makedirs(TMP, exist_ok=True)
    lines = []

    def log(s=""):
        print(s)
        lines.append(s)

    log(f"VALIDATION  (N={N}, steps={STEPS}, seed=42, machine cores={NCPU})")
    log("=" * 78)

    ref_path = os.path.join(TMP, "serial.bin")
    run([os.path.join(BIN, "nbody_serial"), "-n", str(N), "-s", str(STEPS), "-o", ref_path])
    ref = load(ref_path)
    scale = np.max(np.abs(ref))

    configs = [
        ("OpenMP  1 thread  static", ["-t", "1", "-S", "static"], True),
        ("OpenMP  2 threads static", ["-t", "2", "-S", "static"], True),
        ("OpenMP  4 threads static", ["-t", "4", "-S", "static"], True),
        (f"OpenMP {NCPU:2d} threads static", ["-t", str(NCPU), "-S", "static"], True),
        (f"OpenMP {NCPU:2d} threads dynamic", ["-t", str(NCPU), "-S", "dynamic"], True),
        (f"OpenMP {NCPU:2d} threads guided", ["-t", str(NCPU), "-S", "guided"], True),
        (f"OpenMP {NCPU:2d} threads + simd", ["-t", str(NCPU), "-v"], False),
    ]
    log("\nCheck 1: final state of parallel run vs serial run")
    log(f"{'configuration':30s} {'max |diff|':>12s} {'max rel diff':>13s}  result")
    all_ok = True
    for name, args, expect_exact in configs:
        p = os.path.join(TMP, "par.bin")
        run([os.path.join(BIN, "nbody_omp"), "-n", str(N), "-s", str(STEPS), "-o", p] + args)
        par = load(p)
        diff = np.max(np.abs(par - ref))
        rel = diff / scale
        if expect_exact:
            ok = diff == 0.0
            verdict = "PASS (bit-identical)" if ok else "FAIL"
        else:
            ok = rel < 1e-10
            verdict = "PASS (rounding only)" if ok else "FAIL"
        all_ok &= ok
        log(f"{name:30s} {diff:12.3e} {rel:13.3e}  {verdict}")

    log("\nCheck 2: energy conservation (leapfrog integrator, dt=0.001)")
    log(f"{'program':30s} {'steps':>6s} {'rel. energy drift':>18s}  result")
    for name, exe, extra in [
        ("serial", "nbody_serial", []),
        (f"OpenMP {NCPU} threads", "nbody_omp", ["-t", str(NCPU)]),
    ]:
        for steps in (10, 100):
            out, csv = run([os.path.join(BIN, exe), "-n", "4000", "-s", str(steps), "-e"] + extra)
            drift = float(csv[11])
            ok = drift < 1e-4
            all_ok &= ok
            log(f"{name:30s} {steps:6d} {drift:18.3e}  {'PASS' if ok else 'FAIL'}")

    log("\nOVERALL: " + ("ALL CHECKS PASSED" if all_ok else "SOME CHECKS FAILED"))
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n(saved to {os.path.relpath(OUT, ROOT)})")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
