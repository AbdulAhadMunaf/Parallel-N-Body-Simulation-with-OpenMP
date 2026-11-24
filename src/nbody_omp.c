/*
 * nbody_omp.c — OpenMP (shared-memory) PARALLEL version.
 *
 * Same physics, same initial data, same integrator as nbody_serial.c.
 * The only differences are the OpenMP pragmas, marked "OMP:" below.
 *
 * Parallelisation strategy
 *  1. Force loop: '#pragma omp parallel for' over the OUTER loop (bodies i).
 *     Each thread owns a disjoint set of i values and writes only ax[i],
 *     ay[i], az[i] for those i. Every thread only READS x, y, z, m.
 *     => no data races, no locks, no atomics needed.
 *  2. We deliberately do NOT use Newton's 3rd law (computing pair (i,j) once
 *     and updating both i and j). That halves the arithmetic, but two threads
 *     could then write a[j] at the same time -> race, needing atomics/locks.
 *  3. kick/drift loops are parallelised separately. The implicit barrier at
 *     the end of each 'parallel for' guarantees that ALL positions are updated
 *     before ANY thread starts computing forces from them.
 *  4. Energy uses 'reduction(+:...)' — each thread keeps a private partial
 *     sum and OpenMP combines them at the end.
 */
#include "nbody.h"

#include <math.h>
#include <omp.h>
#include <stdio.h>

/* ---- Kernel A: plain parallel-for (same inner loop as the serial code) ---- */
static void compute_accel(Bodies *b)
{
    const size_t n = b->n;
    const double *restrict x = b->x, *restrict y = b->y, *restrict z = b->z;
    const double *restrict m = b->m;
    double *restrict ax = b->ax, *restrict ay = b->ay, *restrict az = b->az;

    /* OMP: schedule(runtime) lets us pick static/dynamic/guided from the
     * command line (omp_set_schedule) without recompiling. */
    #pragma omp parallel for schedule(runtime)
    for (size_t i = 0; i < n; i++) {
        const double xi = x[i], yi = y[i], zi = z[i];
        double axi = 0.0, ayi = 0.0, azi = 0.0;   /* private: declared inside loop */
        for (size_t j = 0; j < n; j++) {
            const double dx = x[j] - xi;
            const double dy = y[j] - yi;
            const double dz = z[j] - zi;
            const double r2 = dx * dx + dy * dy + dz * dz + EPS2;
            const double inv_r  = 1.0 / sqrt(r2);
            const double inv_r3 = inv_r * inv_r * inv_r;
            const double s = m[j] * inv_r3;
            axi += dx * s;
            ayi += dy * s;
            azi += dz * s;
        }
        ax[i] = G_CONST * axi;
        ay[i] = G_CONST * ayi;
        az[i] = G_CONST * azi;
    }
}

/* ---- Kernel B (extension): parallel-for + '#pragma omp simd' inner loop ----
 * Without permission the compiler may not reorder floating-point additions,
 * so it cannot vectorise the "axi += ..." accumulation. 'omp simd reduction'
 * gives that permission: each SIMD lane keeps its own partial sum, and the
 * lanes are added at the end. Results differ from serial only by rounding
 * (~1e-15 relative) because the summation order changes. */
static void compute_accel_simd(Bodies *b)
{
    const size_t n = b->n;
    const double *restrict x = b->x, *restrict y = b->y, *restrict z = b->z;
    const double *restrict m = b->m;
    double *restrict ax = b->ax, *restrict ay = b->ay, *restrict az = b->az;

    #pragma omp parallel for schedule(runtime)
    for (size_t i = 0; i < n; i++) {
        const double xi = x[i], yi = y[i], zi = z[i];
        double axi = 0.0, ayi = 0.0, azi = 0.0;
        #pragma omp simd reduction(+:axi, ayi, azi)
        for (size_t j = 0; j < n; j++) {
            const double dx = x[j] - xi;
            const double dy = y[j] - yi;
            const double dz = z[j] - zi;
            const double r2 = dx * dx + dy * dy + dz * dz + EPS2;
            const double inv_r  = 1.0 / sqrt(r2);
            const double inv_r3 = inv_r * inv_r * inv_r;
            const double s = m[j] * inv_r3;
            axi += dx * s;
            ayi += dy * s;
            azi += dz * s;
        }
        ax[i] = G_CONST * axi;
        ay[i] = G_CONST * ayi;
        az[i] = G_CONST * azi;
    }
}

static void kick(Bodies *b, double h)
{
    const long n = (long)b->n;
    #pragma omp parallel for schedule(static)          /* OMP */
    for (long i = 0; i < n; i++) {
        b->vx[i] += b->ax[i] * h;
        b->vy[i] += b->ay[i] * h;
        b->vz[i] += b->az[i] * h;
    }
}

static void drift(Bodies *b, double h)
{
    const long n = (long)b->n;
    #pragma omp parallel for schedule(static)          /* OMP */
    for (long i = 0; i < n; i++) {
        b->x[i] += b->vx[i] * h;
        b->y[i] += b->vy[i] * h;
        b->z[i] += b->vz[i] * h;
    }
}

static double total_energy(const Bodies *b)
{
    double ke = 0.0, pe = 0.0;
    const long n = (long)b->n;
    /* OMP: reduction gives each thread a private ke/pe, summed at the end.
     * dynamic schedule because row i has (n - i - 1) pairs -> triangular,
     * unbalanced work; static would leave the first threads with most work. */
    #pragma omp parallel for schedule(dynamic, 64) reduction(+:ke, pe)
    for (long i = 0; i < n; i++) {
        ke += 0.5 * b->m[i] * (b->vx[i] * b->vx[i] + b->vy[i] * b->vy[i] + b->vz[i] * b->vz[i]);
        for (long j = i + 1; j < n; j++) {
            const double dx = b->x[j] - b->x[i];
            const double dy = b->y[j] - b->y[i];
            const double dz = b->z[j] - b->z[i];
            pe -= G_CONST * b->m[i] * b->m[j] / sqrt(dx * dx + dy * dy + dz * dz + EPS2);
        }
    }
    return ke + pe;
}

int main(int argc, char **argv)
{
    Options o = parse_args(argc, argv, argv[0]);
    if (o.threads > 0) omp_set_num_threads(o.threads);

    static const char *sched_name[] = { "static", "dynamic", "guided" };
    if (o.schedule == 0)      omp_set_schedule(omp_sched_static, 0);   /* 0 = n/p blocks */
    else if (o.schedule == 1) omp_set_schedule(omp_sched_dynamic, o.chunk);
    else                      omp_set_schedule(omp_sched_guided, o.chunk);

    Bodies b = bodies_alloc(o.n);
    bodies_init(&b, o.seed);
    const int nthreads = omp_get_max_threads();

    double e0 = 0.0, e1 = 0.0;
    if (o.energy) e0 = total_energy(&b);

    void (*accel)(Bodies *) = o.simd ? compute_accel_simd : compute_accel;

    const double t0 = omp_get_wtime();
    accel(&b);
    for (int s = 0; s < o.steps; s++) {
        kick(&b, 0.5 * DT);
        drift(&b, DT);
        accel(&b);
        kick(&b, 0.5 * DT);
    }
    const double elapsed = omp_get_wtime() - t0;

    if (o.energy) e1 = total_energy(&b);
    if (o.out) bodies_write(&b, o.out);

    const double inter = (double)o.n * (double)o.n * (double)(o.steps + 1);
    const double gflops = inter * FLOPS_PER_INTERACTION / elapsed * 1e-9;
    const double drift_rel = o.energy ? fabs((e1 - e0) / e0) : 0.0;
    const int chunk = (o.schedule == 0) ? 0 : o.chunk;

    printf("OpenMP N-body | N=%zu steps=%d threads=%d schedule=%s chunk=%d simd=%s\n",
           o.n, o.steps, nthreads, sched_name[o.schedule], chunk, o.simd ? "on" : "off");
    printf("  time            : %.4f s\n", elapsed);
    printf("  interactions/s  : %.3e\n", inter / elapsed);
    printf("  GFLOP/s         : %.2f\n", gflops);
    if (o.energy)
        printf("  energy          : E0=%.10e  E1=%.10e  rel.drift=%.3e\n", e0, e1, drift_rel);
    printf("CSV,%s,%zu,%d,%d,%s,%d,%d,%.6f,%.6e,%.4f,%.3e\n",
           o.simd ? "omp_simd" : "omp", o.n, o.steps, nthreads, sched_name[o.schedule],
           chunk, o.simd, elapsed, inter / elapsed, gflops, drift_rel);

    bodies_free(&b);
    return 0;
}
