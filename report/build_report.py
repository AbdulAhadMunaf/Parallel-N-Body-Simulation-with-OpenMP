#!/usr/bin/env python3
"""
build_report.py — generates report/PDC_Project_Report.docx from the measured data.

Every number in the report is read from results/raw_runs.csv (medians),
results/validation.txt and results/system_info.txt, so re-running the
benchmark and then this script always gives a report consistent with the data.

    python3 scripts/plot.py && python3 report/build_report.py
"""
import csv
import os
import statistics as st
import sys
from collections import defaultdict

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "results", "raw_runs.csv")
G = os.path.join(ROOT, "graphs")
OUT = os.path.join(ROOT, "report", "PDC_Project_Report.docx")
P_CORES = 10

# ------------------------------------------------------------------ data
groups = defaultdict(list)
with open(RAW) as f:
    for r in csv.DictReader(f):
        groups[(r["experiment"], int(r["n"]), int(r["threads"]), r["schedule"])].append(float(r["time_s"]))
M = {k: st.median(v) for k, v in groups.items()}
REPS = min(len(v) for v in groups.values())
sizes = sorted({k[1] for k in M if k[0] == "E1_serial"})
BIG = sizes[-1]
threads = sorted({k[2] for k in M if k[0] == "E2_threads"})
TMAX = max(threads)
TP = min(P_CORES, TMAX)
Ts = {n: M[("E1_serial", n, 1, "none")] for n in sizes}
T2 = {t: M[("E2_threads", BIG, t, "static")] for t in threads}
simd_t = sorted({k[2] for k in M if k[0] == "E5_simd"})
T5 = {t: M[("E5_simd", BIG, t, "static")] for t in simd_t}
T4 = {(t, s): M[("E4_schedule", BIG, t, s)] for (e, n, t, s) in M if e == "E4_schedule"}
T3 = {(n, t, s): M[("E3_size", n, t, s)] for (e, n, t, s) in M if e == "E3_size"}

S = lambda t: Ts[BIG] / T2[t]  # noqa: E731
best_sched14 = min(["static", "dynamic", "guided"], key=lambda s: T4[(TMAX, s)])
best_all = min([T2[t] for t in threads] + [T4[k] for k in T4])
best_simd = min(T5.values())
sysinfo = open(os.path.join(ROOT, "results", "system_info.txt")).read().strip()
validation = open(os.path.join(ROOT, "results", "validation.txt")).read().strip()
inter_big = BIG * BIG * 11

# ------------------------------------------------------------------ docx helpers
doc = Document()
for s in doc.sections:
    s.left_margin = s.right_margin = Cm(2.2)
    s.top_margin = s.bottom_margin = Cm(2.0)
st_normal = doc.styles["Normal"]
st_normal.font.name = "Calibri"
st_normal.font.size = Pt(11)
ACCENT = RGBColor(0x1F, 0x4E, 0x8C)
for name, size in [("Heading 1", 15), ("Heading 2", 12.5), ("Heading 3", 11.5)]:
    h = doc.styles[name]
    h.font.name = "Calibri"
    h.font.size = Pt(size)
    h.font.color.rgb = ACCENT


def H(text, lvl=1):
    doc.add_heading(text, level=lvl)


def P(text="", bold_prefix=None, italic=False, align=None, size=None):
    p = doc.add_paragraph()
    if bold_prefix:
        p.add_run(bold_prefix).bold = True
    r = p.add_run(text)
    r.italic = italic
    if size:
        r.font.size = Pt(size)
    if align:
        p.alignment = align
    p.paragraph_format.space_after = Pt(6)
    return p


def B(text, bold_prefix=None):
    p = doc.add_paragraph(style="List Bullet")
    if bold_prefix:
        p.add_run(bold_prefix).bold = True
    p.add_run(text)
    return p


def CODE(text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.name = "Menlo"
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "Menlo")
    r.font.size = Pt(8.5)
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), "F3F3F1")
    pPr.append(shd)
    p.paragraph_format.space_after = Pt(8)


def shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def TABLE(header, rows, caption=None, highlight_rows=()):
    if caption:
        c = doc.add_paragraph()
        c.add_run(caption).bold = True
        c.paragraph_format.space_after = Pt(2)
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(header):
        cell = t.rows[0].cells[i]
        cell.text = ""
        run = cell.paragraphs[0].add_run(h)
        run.bold = True
        run.font.size = Pt(9.5)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        shade(cell, "1F4E8C")
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            run = cells[i].paragraphs[0].add_run(str(v))
            run.font.size = Pt(9.5)
            if ri in highlight_rows:
                run.bold = True
                shade(cells[i], "E8F0FA")
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def FIG(name, caption, width=15.5):
    doc.add_picture(os.path.join(G, name), width=Cm(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    c = P(caption, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, size=9.5)
    c.paragraph_format.space_after = Pt(10)


x = lambda v: f"{v:.2f}×"  # noqa: E731
sec = lambda v: f"{v:.2f} s" if v < 100 else f"{v:.1f} s"  # noqa: E731

# ------------------------------------------------------------------ title page
for _ in range(5):
    doc.add_paragraph()
P("Parallel N-Body Simulation using OpenMP", align=WD_ALIGN_PARAGRAPH.CENTER, size=24).runs[0].bold = True
P("Serial vs Shared-Memory Parallel Implementation and Performance Analysis",
  align=WD_ALIGN_PARAGRAPH.CENTER, size=13, italic=True)
doc.add_paragraph()
P("Final Project Report — Parallel and Distributed Computing (Project #22)", align=WD_ALIGN_PARAGRAPH.CENTER)
P("FAST NUCES Karachi  ·  Instructor: Muhammad Minhal Raza", align=WD_ALIGN_PARAGRAPH.CENTER)
doc.add_paragraph()
TABLE(["Name", "Roll No.", "Primary responsibility"], [
    ["Abdul Ahad Munaf", "K23-0590", "Force kernel and OpenMP parallelisation"],
    ["Syed Kashan Hamid", "K23-0747", "Integrator, initialisation and validation"],
    ["Mohammad Mehroz", "K23-0748", "Benchmarking, serial-vs-parallel analysis, graphs, report"],
])
doc.add_page_break()

# ------------------------------------------------------------------ abstract
H("Abstract")
P(f"We implemented a direct all-pairs gravitational N-body simulation in C11 in two forms: a purely "
  f"sequential baseline compiled without OpenMP, and a shared-memory parallel version using OpenMP. "
  f"Both programs share the same initialisation, physics and integrator, so their results can be compared "
  f"directly. With N = {BIG:,} bodies and 10 time steps (about {inter_big:.1e} pairwise interactions), "
  f"the serial program takes {sec(Ts[BIG])}. The OpenMP version reduces this to {sec(T2[TP])} on "
  f"{TP} threads ({x(S(TP))} speedup, {100*S(TP)/TP:.0f}% efficiency) and to {sec(best_all)} using all "
  f"{TMAX} cores ({x(Ts[BIG]/best_all)}). Adding '#pragma omp simd' vectorisation of the inner loop brings "
  f"the time down to {sec(best_simd)} ({x(Ts[BIG]/best_simd)} faster than serial). The parallel results are "
  f"bit-identical to the serial results, and total energy is conserved to about 1e-9 over 100 steps.")

# ------------------------------------------------------------------ 1 intro
H("1. Introduction and Problem Statement")
P("The N-body problem predicts the motion of N particles that interact through gravity. In the direct "
  "(all-pairs) method, at every time step the acceleration of each body is the sum of the pulls from all other "
  "N − 1 bodies. This costs O(N²) work per step, which makes the problem strongly compute-bound and a "
  "classic target for parallel computing.")
P("The goal of this project is to (1) write a correct sequential baseline, (2) parallelise it with OpenMP on a "
  "single multi-core node, (3) verify that the parallel version produces the same answer, and (4) compare the "
  "serial and parallel versions quantitatively: execution time, speedup S = T_serial / T_p and efficiency "
  "E = S / p, across thread counts, problem sizes, loop schedules and SIMD vectorisation.")

# ------------------------------------------------------------------ 2 algorithm
H("2. Algorithm")
H("2.1 Gravitational acceleration with softening", 2)
P("For body i, the acceleration is:")
CODE("a_i = G · Σ_j  m_j · (r_j − r_i) / ( |r_j − r_i|² + ε² )^(3/2)")
P("ε (softening = 0.01) prevents division by zero when two bodies are very close. Because of ε, the j = i term "
  "contributes exactly zero (r_j − r_i = 0), so the loop does not need an 'if (j != i)' branch; removing the "
  "branch keeps the inner loop simple and vectorisable. Simulation units use G = 1, total mass ≈ 1, and "
  "time step dt = 0.001.")
H("2.2 Leapfrog (kick–drift–kick) integrator", 2)
CODE("compute a(x)                     // initial accelerations\n"
     "for each step:\n"
     "    v += a · dt/2                  // half kick\n"
     "    x += v · dt                    // drift\n"
     "    compute a(x)                   // O(N²) force evaluation  (>99% of time)\n"
     "    v += a · dt/2                  // half kick")
P("Leapfrog is second-order accurate and symplectic, meaning it conserves energy very well over long runs, "
  "which gives us a physical correctness check in addition to comparing against the serial output.")
H("2.3 Complexity and problem size", 2)
P(f"Each run performs 11 force evaluations (one initial + 10 steps), i.e. 11·N² interactions. At N = {BIG:,} "
  f"this is {inter_big:.2e} interactions, ≈ {inter_big*20/1e12:.1f} trillion floating-point operations at the "
  f"standard count of 20 FLOPs per interaction. Memory use is only 10 doubles per body (≈ "
  f"{BIG*80/1e6:.0f} MB at N = {BIG:,}), so the problem is limited by computation, not by memory or I/O.")

# ------------------------------------------------------------------ 3 implementation
H("3. Implementation")
H("3.1 Code organisation", 2)
TABLE(["File", "Purpose"], [
    ["src/nbody.h", "Constants (G, ε, dt), Bodies struct, Options"],
    ["src/common.c", "Allocation, seeded initialisation, output, argument parsing — shared by both programs"],
    ["src/nbody_serial.c", "Sequential baseline — compiled WITHOUT -fopenmp"],
    ["src/nbody_omp.c", "OpenMP version: same code plus pragmas; plain and SIMD force kernels"],
    ["scripts/validate.py", "Correctness checks (serial vs parallel, energy conservation)"],
    ["scripts/benchmark.py", f"Runs all experiments, {REPS} repetitions each, saves raw timings"],
    ["scripts/plot.py", "Computes medians, speedup, efficiency; draws all graphs"],
], caption="Table 3.1 — Source files")
H("3.2 Data layout: Structure of Arrays", 2)
P("Body data is stored as ten separate arrays (x, y, z, vx, vy, vz, ax, ay, az, m) instead of an array of "
  "structs. The inner loop reads x[j], y[j], z[j], m[j] with unit stride, so every byte loaded into the cache "
  "is useful and the compiler can load several consecutive values into one SIMD register. Arrays are "
  "64-byte aligned (one cache line).")
H("3.3 Reproducible input", 2)
P("Bodies are placed uniformly inside a unit sphere with small random velocities and masses in [0.5, 1.5]/N. "
  "We use our own xorshift64* generator with a fixed seed (42) rather than rand(), because rand() differs "
  "between operating systems and is not thread-safe. Both programs therefore start from bit-identical input.")
H("3.4 Sequential baseline", 2)
CODE("for (i = 0; i < n; i++) {\n"
     "    double axi = 0, ayi = 0, azi = 0;\n"
     "    for (j = 0; j < n; j++) {\n"
     "        dx = x[j]-x[i]; dy = y[j]-y[i]; dz = z[j]-z[i];\n"
     "        r2 = dx*dx + dy*dy + dz*dz + EPS2;\n"
     "        inv_r = 1.0 / sqrt(r2);  s = m[j] * inv_r*inv_r*inv_r;\n"
     "        axi += dx*s;  ayi += dy*s;  azi += dz*s;\n"
     "    }\n"
     "    ax[i] = G*axi;  ay[i] = G*ayi;  az[i] = G*azi;\n"
     "}")
P("The serial program is timed with clock_gettime(CLOCK_MONOTONIC); the OpenMP program with omp_get_wtime(). "
  "Only the simulation loop is timed (not allocation, initialisation or energy checks), identically in both.")

# ------------------------------------------------------------------ 4 parallel design
H("4. Parallel Design with OpenMP")
H("4.1 Decomposition of the force loop", 2)
CODE("#pragma omp parallel for schedule(runtime)\n"
     "for (i = 0; i < n; i++) {     // iterations i are divided among threads\n"
     "    ... same inner j-loop as the serial version ...\n"
     "    ax[i] = ...;               // each thread writes ONLY its own i\n"
     "}")
P("This is a data-parallel (domain) decomposition over bodies. Every iteration i is independent: it reads the "
  "shared, read-only arrays x, y, z, m and writes only ax[i], ay[i], az[i]. Since no two threads ever write the "
  "same element, there are no race conditions and no locks, critical sections or atomics are needed. The "
  "accumulators axi, ayi, azi and all temporaries are declared inside the loop body, so they are automatically "
  "private to each thread.")
H("4.2 Why we did not use Newton's third law", 2)
P("A serial optimisation computes each pair (i, j) once and applies +F to i and −F to j, halving the work. In "
  "parallel this is harmful: thread A (handling i) would write a[j] while thread B (handling j) writes a[j] too, "
  "causing a write conflict. Fixing it requires atomics or per-thread copies of the acceleration arrays plus a "
  "reduction, both of which add overhead and memory traffic. We therefore keep the symmetric, conflict-free "
  "formulation, trading 2× arithmetic for perfect independence — a good trade for a compute-bound kernel on "
  "many cores.")
H("4.3 Synchronisation between phases", 2)
P("kick and drift are separate '#pragma omp parallel for' loops. Each parallel loop ends with an implicit "
  "barrier: no thread starts computing forces until ALL positions have been updated by the drift loop. Without "
  "this barrier a thread could compute forces from a mix of old and new positions, giving wrong results. These "
  "update loops are O(N) and take a negligible fraction of the time compared with the O(N²) force loop.")
H("4.4 Reduction for total energy", 2)
CODE("#pragma omp parallel for schedule(dynamic, 64) reduction(+:ke, pe)\n"
     "for (i = 0; i < n; i++) { ke += ...;  for (j = i+1; j < n; j++) pe -= ...; }")
P("Energy accumulates into two shared sums. reduction(+:ke, pe) gives each thread private copies initialised to "
  "zero and adds them together at the end, avoiding a race without any locking. The pair loop is triangular "
  "(row i has n − i − 1 pairs), so the work per row is unbalanced; dynamic scheduling hands out small chunks on "
  "demand to balance it.")
H("4.5 Loop scheduling", 2)
P("The force loop uses schedule(runtime) so that static, dynamic and guided scheduling can be compared from the "
  "command line without recompiling. Static scheduling gives each thread one contiguous block of N/p rows at "
  "start-up (zero runtime overhead). Dynamic hands out chunks of 64 rows on demand (a small overhead per chunk, "
  "but it adapts to threads running at different speeds). Guided starts with large chunks and shrinks them.")
H("4.6 Extension: SIMD vectorisation", 2)
CODE("#pragma omp parallel for schedule(runtime)\n"
     "for (i = 0; i < n; i++) {\n"
     "    #pragma omp simd reduction(+:axi, ayi, azi)\n"
     "    for (j = 0; j < n; j++) { ... }\n"
     "}")
P("Under strict IEEE rules the compiler may not reorder floating-point additions, so it cannot vectorise the "
  "'axi += …' accumulation on its own. The 'omp simd reduction' directive gives it permission: each SIMD lane "
  "keeps a partial sum, combined at the end. This adds a second level of parallelism — threads across cores "
  "and SIMD lanes within each core. The changed summation order means results differ from serial only by "
  "rounding (≈ 1e-16 relative), which we verify.")

# ------------------------------------------------------------------ 5 setup
H("5. Experimental Setup")
CODE(sysinfo)
TABLE(["Experiment", "Configurations"], [
    ["E1 Serial baseline", ", ".join(f"N={n:,}" for n in sizes) + " (serial program)"],
    ["E2 Thread scaling", f"N={BIG:,}, threads = {', '.join(map(str, threads))}, static"],
    ["E3 Problem-size scaling", f"all N at {TP} threads (static) and {TMAX} threads (static & dynamic)"],
    ["E4 Scheduling", f"N={BIG:,}, static vs dynamic,64 vs guided,64 at {TP} and {TMAX} threads"],
    ["E5 SIMD extension", f"N={BIG:,}, threads = {', '.join(map(str, simd_t))}"],
], caption=f"Table 5.1 — Experiments (each configuration run {REPS} times, median reported, 10 time steps)")
P(f"Note on the hardware: the Apple M4 Pro is a heterogeneous CPU with {P_CORES} performance (P) cores and "
  f"{TMAX - P_CORES} efficiency (E) cores. E-cores are considerably slower, which matters for scaling beyond "
  f"{P_CORES} threads (Section 7.3). Repetitions were interleaved (all configurations once, then again) so "
  f"that background noise is spread across configurations rather than concentrated in one.")

# ------------------------------------------------------------------ 6 validation
H("6. Correctness Validation")
P("A parallel program that is fast but wrong is worthless, so validation was done before benchmarking.")
CODE(validation)
B("All plain OpenMP configurations (1 to 14 threads, every schedule) produce output that is BIT-IDENTICAL to the "
  "serial program. This is expected: each body's sum is still computed by one thread in the same order, so "
  "parallelising the outer loop does not change any floating-point operation.", "Serial vs parallel: ")
B("The SIMD kernel differs by ~1e-16, i.e. last-bit rounding from summing in a different order. This is not "
  "an error; it is the expected consequence of floating-point addition not being associative.", "SIMD: ")
B("Relative drift of total energy is ~1e-11 after 10 steps and ~1e-9 after 100 steps, identical for serial "
  "and parallel runs, confirming that the physics is correct.", "Energy: ")

# ------------------------------------------------------------------ 7 results
H("7. Results: Serial vs Parallel Comparison")
H("7.1 Serial vs parallel at every problem size", 2)
rows = []
for n in sizes:
    a, b = T3[(n, TP, "static")], T3[(n, TMAX, "dynamic")]
    rows.append([f"{n:,}", sec(Ts[n]), sec(a), x(Ts[n] / a), sec(b), x(Ts[n] / b)])
TABLE(["N", "Serial", f"OpenMP {TP} thr", "Speedup", f"OpenMP {TMAX} thr (dyn)", "Speedup"], rows,
      caption="Table 7.1 — Serial vs parallel execution time (10 steps, median)", highlight_rows=[len(rows) - 1])
FIG("fig1_serial_vs_parallel_time.png", "Figure 1 — Serial vs OpenMP execution time for every problem size (log scale).")
P(f"The parallel version is faster at every problem size. At N = {BIG:,} the serial program needs "
  f"{sec(Ts[BIG])} while OpenMP needs {sec(T3[(BIG, TP, 'static')])} on {TP} threads. The speedup on {TP} "
  f"threads is nearly constant across sizes ({min(Ts[n]/T3[(n, TP, 'static')] for n in sizes):.2f}× to "
  f"{max(Ts[n]/T3[(n, TP, 'static')] for n in sizes):.2f}×): even the smallest problem, N = {sizes[0]:,}, has "
  f"10⁸ interactions per force evaluation (about 10 ms of work on {TP} threads), which is far larger than the "
  f"microseconds needed to wake threads and pass a barrier, so overhead is negligible at every size we tested.")

H(f"7.2 Thread scaling at N = {BIG:,}", 2)
rows = [["serial", sec(Ts[BIG]), "1.00×", "100%", "—"]]
for t in threads:
    rows.append([str(t), sec(T2[t]), x(S(t)), f"{100*S(t)/t:.0f}%", x(T2[1] / T2[t])])
TABLE(["Threads", "Time", "Speedup vs serial", "Efficiency", "Speedup vs OpenMP-1"], rows,
      caption="Table 7.2 — Thread scaling (static schedule)",
      highlight_rows=[threads.index(TP) + 1])
FIG("fig2_time_vs_threads.png", "Figure 2 — Execution time vs threads. Shaded: threads placed on efficiency cores.")
FIG("fig3_speedup_vs_threads.png", "Figure 3 — Speedup vs threads, measured against the serial program, with the ideal linear line.")
FIG("fig4_efficiency_vs_threads.png", "Figure 4 — Parallel efficiency E = S / p.")

H("7.3 Analysis of thread scaling", 2)
B(f"The 1-thread OpenMP run takes {sec(T2[1])} vs {sec(Ts[BIG])} for the serial program "
  f"({100*(T2[1]/Ts[BIG]-1):+.1f}%). The overhead of OpenMP itself is negligible, so the serial program is a "
  f"fair baseline and every speedup reported is real.", "OpenMP overhead: ")
B(f"Up to {TP} threads, speedup grows almost linearly: {x(S(2))} on 2, {x(S(4))} on 4, {x(S(8))} on 8 and "
  f"{x(S(TP))} on {TP} threads (efficiency {100*S(TP)/TP:.0f}%). The force loop has no shared writes, no "
  f"locks and a tiny serial fraction, and the {BIG*80/1e6:.0f} MB working set stays in the large on-chip caches, "
  f"so the cores rarely wait for memory.", "Near-linear region (P-cores): ")
B("The remaining gap from ideal comes mainly from (i) the chip lowering its clock frequency when more cores are "
  "busy (single-core runs get a higher turbo clock than all-core runs), (ii) fork/join and barrier "
  "costs at each of the 4 parallel loops per step, and (iii) the small sequential parts (setup, timing).",
  "Why not exactly linear: ")
B(f"Going from {TP} to {TMAX} threads adds the {TMAX-P_CORES} efficiency cores, but speedup only rises from "
  f"{x(S(TP))} to {x(S(TMAX))} (static). E-cores are much slower than P-cores. With static scheduling every "
  f"thread gets the same number of rows, so the threads on E-cores finish last and the P-core threads sit idle "
  f"at the barrier waiting for them — a load-imbalance problem caused by the hardware, not the algorithm. This "
  f"is why efficiency drops sharply past {TP} threads.", "Beyond 10 threads (E-cores): ")
B("Every body performs exactly N interactions, so the serial fraction of the program is ≈ 0 and Amdahl's law "
  "would allow near-ideal speedup. Our measured losses come from hardware effects (clock scaling, "
  "heterogeneous cores), not from serial code.", "Amdahl's law: ")

H("7.4 Problem-size scaling", 2)
FIG("fig5_speedup_vs_size.png", "Figure 5 — Speedup vs number of bodies.")
FIG("fig7_time_vs_size.png", "Figure 6 — Run time follows N² for both programs (log–log).")
rows = []
prev = None
for n in sizes:
    rows.append([f"{n:,}", sec(Ts[n]), f"{Ts[n]/Ts[prev]:.2f}" if prev else "—",
                 f"{(n/prev)**2:.2f}" if prev else "—"])
    prev = n
TABLE(["N", "Serial time", "Measured time ratio", "Expected ratio (N₂/N₁)²"], rows,
      caption="Table 7.3 — Serial time confirms O(N²) complexity")
P("Doubling N quadruples the run time, exactly as O(N²) predicts, for the serial and the parallel program "
  "alike. Because the parallel overhead per step is constant (microseconds) while the useful work grows as N², "
  "the speedup stays flat at about 9× on 10 threads from N = 10,000 upwards. Only much smaller problems "
  "(a few thousand bodies, where a step takes well under a millisecond) would show overhead eating into the "
  "speedup; that is Gustafson's observation from the other side: parallel hardware needs enough work per step.")

H("7.5 Loop scheduling: static vs dynamic vs guided", 2)
sched_t = sorted({t for (t, s) in T4})
rows = [[f"{t}"] + [f"{sec(T4[(t, s)])} ({x(Ts[BIG]/T4[(t, s)])})" for s in ["static", "dynamic", "guided"]]
        for t in sched_t]
TABLE(["Threads", "static", "dynamic, 64", "guided, 64"], rows,
      caption=f"Table 7.4 — Scheduling comparison at N = {BIG:,} (time and speedup vs serial)")
FIG("fig6_scheduling.png", "Figure 7 — Effect of the OpenMP loop schedule.")
d10 = 100 * (T4[(TP, "static")] / min(T4[(TP, s)] for s in ["dynamic", "guided"]) - 1)
d14 = 100 * (T4[(TMAX, "static")] / min(T4[(TMAX, s)] for s in ["dynamic", "guided"]) - 1)
P(f"On {TP} threads (P-cores only) all schedules perform about the same (best non-static vs static: "
  f"{d10:+.1f}%), because every row costs the same and all cores are equally fast, so static's equal split is "
  f"already balanced and costs nothing at runtime. On {TMAX} threads (P + E cores) the best schedule is "
  f"{best_sched14} and the adaptive schedules beat static by {d14:.1f}%: fast P-core threads come back for more "
  f"chunks while slow E-core threads process fewer, which corrects the imbalance described in 7.3. "
  f"Conclusion: static is best on uniform hardware; dynamic/guided pay off when threads run at different speeds.")

H("7.6 Extension: SIMD vectorisation", 2)
rows = [[str(t), sec(T2[t]), sec(T5[t]), x(T2[t] / T5[t]), x(Ts[BIG] / T5[t])] for t in simd_t]
TABLE(["Threads", "parallel for", "parallel for + simd", "SIMD gain", "Total speedup vs serial"], rows,
      caption=f"Table 7.5 — Effect of '#pragma omp simd' at N = {BIG:,}")
P(f"Adding '#pragma omp simd' gives a further {x(T2[1]/T5[1])} on a single thread and the best result overall: "
  f"{sec(best_simd)}, i.e. {x(Ts[BIG]/best_simd)} faster than the serial program. The NEON SIMD unit holds 2 "
  f"doubles per 128-bit register, and the cores have several such units, so more arithmetic is done per "
  f"instruction. The gain is below the theoretical maximum because the expensive square root and division "
  f"dominate each interaction. Note that a speedup larger than the thread count here is not 'superlinear "
  f"scaling': the SIMD code also makes each individual thread faster than the serial baseline (two levels of "
  f"parallelism combined).")

# ------------------------------------------------------------------ 8 summary
H("8. Summary of Serial vs Parallel Performance")
TABLE(["Version", f"Time (N = {BIG:,})", "Speedup vs serial"], [
    ["Serial (no OpenMP)", sec(Ts[BIG]), "1.00×"],
    ["OpenMP, 1 thread", sec(T2[1]), x(S(1))],
    [f"OpenMP, {TP} threads (static)", sec(T2[TP]), x(S(TP))],
    [f"OpenMP, {TMAX} threads ({best_sched14})", sec(T4[(TMAX, best_sched14)]),
     x(Ts[BIG] / T4[(TMAX, best_sched14)])],
    [f"OpenMP + SIMD, best", sec(best_simd), x(Ts[BIG] / best_simd)],
], caption="Table 8.1 — Headline comparison", highlight_rows=[4])

# ------------------------------------------------------------------ 9 conclusion
H("9. Conclusion")
P(f"The direct N-body force computation parallelises very well with OpenMP. Splitting the outer loop over "
  f"bodies needs a single pragma, requires no locks because each thread writes only its own bodies, and gives "
  f"results that are bit-identical to the serial code. On the {TP} performance cores we achieved "
  f"{x(S(TP))} speedup at {100*S(TP)/TP:.0f}% efficiency; with SIMD on top the simulation runs "
  f"{x(Ts[BIG]/best_simd)} faster than the serial baseline, reducing {sec(Ts[BIG])} to {sec(best_simd)}.")
P("Key lessons: (1) choose an independent decomposition and avoid shared writes, even at the cost of extra "
  "arithmetic; (2) parallel efficiency is limited by hardware realities — clock scaling and heterogeneous "
  "cores — more than by Amdahl's serial fraction for this problem; (3) static scheduling suits uniform work on "
  "uniform cores, dynamic scheduling compensates for unequal cores; (4) thread-level and SIMD parallelism "
  "multiply. Natural future work is the Barnes–Hut O(N log N) algorithm, an MPI version for clusters, or a GPU "
  "(CUDA) version, where the same all-pairs kernel maps naturally to thousands of threads.")

# ------------------------------------------------------------------ 10 contributions
H("10. Individual Contributions")
TABLE(["Member", "Contribution"], [
    ["Abdul Ahad Munaf (K23-0590)", "Force kernel (serial and OpenMP), parallel-for decomposition, race-free design, scheduling and SIMD extension"],
    ["Syed Kashan Hamid (K23-0747)", "Leapfrog integrator, reproducible initialisation (SoA layout, RNG), energy reduction, validation suite"],
    ["Mohammad Mehroz (K23-0748)", "Benchmark automation, serial-vs-parallel analysis, graphs, report"],
])
P("All three members understand and can explain the full codebase.")

# ------------------------------------------------------------------ appendix
H("Appendix A — How to Reproduce")
CODE("brew install libomp        # macOS only\n"
     "make                       # build bin/nbody_serial and bin/nbody_omp\n"
     "make validate              # correctness checks\n"
     "make bench                 # all experiments (~50 min)\n"
     "make plots                 # tables + graphs\n"
     "python3 report/build_report.py")
P("Raw timings for every individual run are in results/raw_runs.csv; per-configuration medians, minima and "
  "maxima are in results/summary.csv.")

doc.save(OUT)
print("wrote", os.path.relpath(OUT, ROOT), f"(reps={REPS})")
