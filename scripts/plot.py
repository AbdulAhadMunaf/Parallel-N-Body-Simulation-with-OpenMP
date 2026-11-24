#!/usr/bin/env python3
"""
plot.py — turns results/raw_runs.csv into summary tables and graphs.

For every configuration the MEDIAN of the repetitions is used.
Speedup is always measured against the TRUE SERIAL program (nbody_serial,
compiled without OpenMP) at the same N:   S = T_serial / T_parallel,  E = S / p

Outputs
  results/summary.csv          one row per configuration (median, min, max)
  results/summary.md           the tables used in the report / presentation
  graphs/*.png                 figures

  python3 scripts/plot.py            (uses results/raw_runs.csv)
  python3 scripts/plot.py --quick    (uses results/raw_runs_quick.csv)
"""
import csv
import os
import statistics as st
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUICK = "--quick" in sys.argv
RAW = os.path.join(ROOT, "results", "raw_runs_quick.csv" if QUICK else "raw_runs.csv")
GDIR = os.path.join(ROOT, "graphs")
P_CORES = 10

# Palette (validated categorical slots, fixed order) + neutral ink
BLUE, ORANGE, AQUA, VIOLET = "#2a78d6", "#eb6834", "#1baf7a", "#6250d6"
INK, INK2, GRID, GRAY = "#0b0b0b", "#52514e", "#e4e3df", "#8a8984"

plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 200, "font.size": 10,
    "axes.edgecolor": GRAY, "axes.labelcolor": INK2, "axes.titlesize": 12,
    "axes.titleweight": "bold", "axes.titlecolor": INK, "axes.titlelocation": "left",
    "xtick.color": INK2, "ytick.color": INK2, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False,
    "legend.frameon": False, "lines.linewidth": 2, "lines.markersize": 7,
})


def load():
    groups = defaultdict(list)
    with open(RAW) as f:
        for r in csv.DictReader(f):
            k = (r["experiment"], r["impl"], int(r["n"]), int(r["threads"]), r["schedule"])
            groups[k].append(float(r["time_s"]))
    return {k: (st.median(v), min(v), max(v), len(v)) for k, v in groups.items()}


def med(D, exp, impl, n, t, s):
    v = D.get((exp, impl, n, t, s))
    return v[0] if v else None


def save(fig, name):
    os.makedirs(GDIR, exist_ok=True)
    fig.tight_layout()
    fig.savefig(os.path.join(GDIR, name), bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  wrote graphs/" + name)


def fmt_s(x):
    return f"{x:.0f} s" if x >= 10 else (f"{x:.1f} s" if x >= 1 else f"{x:.2f} s")


def main():
    D = load()
    sizes = sorted({k[2] for k in D if k[0] == "E1_serial"})
    BIG = sizes[-1]
    threads = sorted({k[3] for k in D if k[0] == "E2_threads"})
    tmax = max(threads)
    tp = min(P_CORES, tmax)
    Tser = {n: med(D, "E1_serial", "serial", n, 1, "none") for n in sizes}
    T2 = {t: med(D, "E2_threads", "omp", BIG, t, "static") for t in threads}
    simd_t = sorted({k[3] for k in D if k[0] == "E5_simd"})
    T5 = {t: med(D, "E5_simd", "omp_simd", BIG, t, "static") for t in simd_t}

    # ---------------- summary.csv ----------------
    with open(os.path.join(ROOT, "results", "summary.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["experiment", "impl", "n", "threads", "schedule", "median_s", "min_s",
                    "max_s", "reps", "speedup_vs_serial", "efficiency"])
        for k in sorted(D):
            m, lo, hi, c = D[k]
            S = Tser[k[2]] / m if Tser.get(k[2]) else 0
            w.writerow(list(k) + [f"{m:.4f}", f"{lo:.4f}", f"{hi:.4f}", c, f"{S:.2f}",
                                  f"{S / k[3]:.3f}"])

    # ---------------- summary.md ----------------
    L = []
    L.append(f"## Table 1 — Serial vs parallel at every problem size (10 steps, median of runs)\n")
    L.append(f"| N | Serial time | OpenMP {tp} thr (static) | Speedup | OpenMP {tmax} thr (dynamic) | Speedup | Best | Best speedup |")
    L.append("|---|---|---|---|---|---|---|---|")
    for n in sizes:
        a = med(D, "E3_size", "omp", n, tp, "static")
        b = med(D, "E3_size", "omp", n, tmax, "dynamic")
        best = min(x for x in [a, b] if x)
        L.append(f"| {n:,} | {Tser[n]:.3f} s | {a:.3f} s | {Tser[n]/a:.2f}x | {b:.3f} s | "
                 f"{Tser[n]/b:.2f}x | {best:.3f} s | {Tser[n]/best:.2f}x |")
    L.append(f"\n## Table 2 — Thread scaling, N = {BIG:,} (static schedule)\n")
    L.append("| Threads | Time | Speedup vs serial | Efficiency | Speedup vs OpenMP-1 |")
    L.append("|---|---|---|---|---|")
    L.append(f"| serial | {Tser[BIG]:.2f} s | 1.00x | 100% | — |")
    for t in threads:
        S = Tser[BIG] / T2[t]
        L.append(f"| {t} | {T2[t]:.2f} s | {S:.2f}x | {100*S/t:.0f}% | {T2[1]/T2[t]:.2f}x |")
    L.append(f"\n## Table 3 — Scheduling, N = {BIG:,}\n")
    L.append("| Threads | static | dynamic,64 | guided,64 |")
    L.append("|---|---|---|---|")
    for t in sorted({k[3] for k in D if k[0] == "E4_schedule"}):
        row = [med(D, "E4_schedule", "omp", BIG, t, s) for s in ["static", "dynamic", "guided"]]
        L.append(f"| {t} | " + " | ".join(f"{x:.2f} s ({Tser[BIG]/x:.2f}x)" for x in row) + " |")
    L.append(f"\n## Table 4 — SIMD extension, N = {BIG:,} (static)\n")
    L.append("| Threads | parallel for | parallel for + omp simd | SIMD gain | Speedup vs serial |")
    L.append("|---|---|---|---|---|")
    for t in simd_t:
        L.append(f"| {t} | {T2[t]:.2f} s | {T5[t]:.2f} s | {T2[t]/T5[t]:.2f}x | {Tser[BIG]/T5[t]:.2f}x |")
    L.append("\n## Table 5 — Serial run time vs N (O(N²) check)\n")
    L.append("| N | Serial time | Ratio to previous | Expected (N ratio)² |")
    L.append("|---|---|---|---|")
    prev = None
    for n in sizes:
        r = f"{Tser[n]/Tser[prev]:.2f}" if prev else "—"
        e = f"{(n/prev)**2:.2f}" if prev else "—"
        L.append(f"| {n:,} | {Tser[n]:.3f} s | {r} | {e} |")
        prev = n
    with open(os.path.join(ROOT, "results", "summary.md"), "w") as f:
        f.write("\n".join(L) + "\n")
    print("  wrote results/summary.md, results/summary.csv")

    # ---------------- Fig 1: serial vs parallel, all sizes ----------------
    fig, ax = plt.subplots(figsize=(8, 4.4))
    xs = range(len(sizes))
    w = 0.26
    par_p = [med(D, "E3_size", "omp", n, tp, "static") for n in sizes]
    par_m = [med(D, "E3_size", "omp", n, tmax, "dynamic") for n in sizes]
    series = [(f"Serial (no OpenMP)", [Tser[n] for n in sizes], GRAY),
              (f"OpenMP {tp} threads", par_p, BLUE),
              (f"OpenMP {tmax} threads", par_m, ORANGE)]
    for j, (lab, vals, col) in enumerate(series):
        pos = [x + (j - 1) * w for x in xs]
        ax.bar(pos, vals, w - 0.03, color=col, label=lab)
        for p, v in zip(pos, vals):
            ax.text(p, v * 1.12, fmt_s(v), ha="center", va="bottom", fontsize=7.5, color=INK2)
    ax.set_yscale("log")
    ax.set_xticks(list(xs))
    ax.set_xticklabels([f"N = {n:,}" for n in sizes])
    ax.set_ylabel("Execution time (s, log scale)")
    ax.set_ylim(top=max(Tser.values()) * 4)
    ax.set_title("Serial vs parallel execution time (10 steps)")
    ax.legend(loc="upper left", ncol=3)
    ax.grid(axis="x", visible=False)
    save(fig, "fig1_serial_vs_parallel_time.png")

    # ---------------- Fig 2: time vs threads ----------------
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.axhline(Tser[BIG], color=GRAY, ls="--", lw=1.5)
    ax.text(tmax, Tser[BIG] * 1.03, f"serial baseline {Tser[BIG]:.1f} s", ha="right",
            va="bottom", color=INK2, fontsize=8.5)
    ax.plot(threads, [T2[t] for t in threads], "o-", color=BLUE, label="OpenMP parallel for")
    ax.plot(simd_t, [T5[t] for t in simd_t], "s-", color=ORANGE, label="OpenMP parallel for + simd")
    ax.set_xlabel("Threads")
    ax.set_ylabel("Execution time (s)")
    ax.set_xticks(threads)
    ax.set_ylim(0, Tser[BIG] * 1.15)
    ax.set_title(f"Execution time vs threads (N = {BIG:,})")
    ax.axvspan(P_CORES + 0.5, tmax + 0.5, color="#f1efe8", zorder=0)
    ax.text(P_CORES + 0.7, Tser[BIG] * 0.6, "efficiency\ncores in use", fontsize=8, color=INK2)
    ax.legend(loc="upper center")
    save(fig, "fig2_time_vs_threads.png")

    # ---------------- Fig 3: speedup vs threads ----------------
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot([0, tmax], [0, tmax], "--", color=GRAY, lw=1.5, label="Ideal (linear) speedup")
    sp = [Tser[BIG] / T2[t] for t in threads]
    ax.plot(threads, sp, "o-", color=BLUE, label="OpenMP parallel for")
    ax.plot(simd_t, [Tser[BIG] / T5[t] for t in simd_t], "s-", color=ORANGE,
            label="OpenMP parallel for + simd")
    for t, s in zip(threads, sp):
        if t in (tp, tmax):
            ax.annotate(f"{s:.1f}x", (t, s), textcoords="offset points", xytext=(0, -16),
                        ha="center", fontsize=8.5, color=INK2)
    ax.axvspan(P_CORES + 0.5, tmax + 0.5, color="#f1efe8", zorder=0)
    ax.set_xlabel("Threads")
    ax.set_ylabel("Speedup  S = T_serial / T_p")
    ax.set_xticks(threads)
    ax.set_xlim(0, tmax + 0.5)
    ax.set_ylim(0, max(tmax, max(Tser[BIG] / v for v in T5.values())) * 1.1)
    ax.set_title(f"Speedup vs threads (N = {BIG:,})")
    ax.legend(loc="upper left")
    save(fig, "fig3_speedup_vs_threads.png")

    # ---------------- Fig 4: efficiency ----------------
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.axhline(100, color=GRAY, ls="--", lw=1.5, label="Ideal (100%)")
    ax.plot(threads, [100 * Tser[BIG] / T2[t] / t for t in threads], "o-", color=BLUE,
            label="OpenMP parallel for")
    ax.axvspan(P_CORES + 0.5, tmax + 0.5, color="#f1efe8", zorder=0)
    ax.set_xlabel("Threads")
    ax.set_ylabel("Efficiency  E = S / p  (%)")
    ax.set_xticks(threads)
    ax.set_ylim(0, 115)
    ax.set_title(f"Parallel efficiency vs threads (N = {BIG:,})")
    ax.legend(loc="lower left")
    save(fig, "fig4_efficiency_vs_threads.png")

    # ---------------- Fig 5: speedup vs N ----------------
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot(sizes, [Tser[n] / v for n, v in zip(sizes, par_p)], "o-", color=BLUE,
            label=f"{tp} threads, static")
    ax.plot(sizes, [Tser[n] / v for n, v in zip(sizes, par_m)], "s-", color=ORANGE,
            label=f"{tmax} threads, dynamic")
    ax.set_xlabel("Number of bodies N")
    ax.set_ylabel("Speedup vs serial")
    ax.set_xticks(sizes)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v/1000)}k"))
    ax.set_ylim(0, tmax)
    ax.set_title("Speedup vs problem size")
    ax.legend(loc="lower right")
    save(fig, "fig5_speedup_vs_size.png")

    # ---------------- Fig 6: scheduling ----------------
    sch_t = sorted({k[3] for k in D if k[0] == "E4_schedule"})
    fig, ax = plt.subplots(figsize=(7, 4.2))
    scheds = [("static", BLUE), ("dynamic", ORANGE), ("guided", AQUA)]
    w = 0.26
    for j, (s, col) in enumerate(scheds):
        vals = [med(D, "E4_schedule", "omp", BIG, t, s) for t in sch_t]
        pos = [i + (j - 1) * w for i in range(len(sch_t))]
        ax.bar(pos, vals, w - 0.03, color=col, label=s if s == "static" else s + ", chunk 64")
        for p, v in zip(pos, vals):
            ax.text(p, v * 1.01, f"{v:.2f}", ha="center", va="bottom", fontsize=8, color=INK2)
    ax.set_xticks(range(len(sch_t)))
    ax.set_xticklabels([f"{t} threads" + (" (P-cores only)" if t == P_CORES else " (P + E cores)")
                        for t in sch_t])
    ax.set_ylabel("Execution time (s)")
    ax.set_title(f"Loop scheduling comparison (N = {BIG:,})")
    ax.legend(loc="upper center", ncol=3, bbox_to_anchor=(0.5, -0.1))
    ax.grid(axis="x", visible=False)
    save(fig, "fig6_scheduling.png")

    # ---------------- Fig 7: serial run time vs N (O(N^2)) ----------------
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot(sizes, [Tser[n] for n in sizes], "o-", color=GRAY, label="Serial (measured)")
    ax.plot(sizes, par_p, "o-", color=BLUE, label=f"OpenMP {tp} threads (measured)")
    ref = [Tser[sizes[-1]] * (n / sizes[-1]) ** 2 for n in sizes]
    ax.plot(sizes, ref, ":", color=INK2, lw=1.5, label="O(N²) reference")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xticks(sizes)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v/1000)}k"))
    ax.xaxis.set_minor_formatter(FuncFormatter(lambda v, _: ""))
    ax.set_xlabel("Number of bodies N (log)")
    ax.set_ylabel("Execution time (s, log)")
    ax.set_title("Run time grows as N² — serial and parallel")
    ax.legend(loc="upper left")
    save(fig, "fig7_time_vs_size.png")


if __name__ == "__main__":
    main()
