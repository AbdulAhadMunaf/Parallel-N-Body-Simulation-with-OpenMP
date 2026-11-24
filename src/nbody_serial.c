/*
 * nbody_serial.c — SEQUENTIAL baseline (compiled WITHOUT -fopenmp).
 *
 * This is the reference T_serial used for every speedup number:
 *      Speedup S(p) = T_serial / T_parallel(p),  Efficiency E(p) = S(p) / p
 *
 * Algorithm per time step (leapfrog, kick-drift-kick):
 *      v += a * dt/2          (half kick)
 *      x += v * dt            (drift)
 *      a  = forces(x)         (O(N^2) all-pairs)  <-- >99% of the run time
 *      v += a * dt/2          (half kick)
 */
#define _POSIX_C_SOURCE 199309L
#include "nbody.h"

#include <math.h>
#include <stdio.h>
#include <time.h>

static double wall_time(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + 1e-9 * (double)ts.tv_nsec;
}

/*
 * All-pairs gravitational acceleration.
 * The j == i term is NOT skipped: dx = dy = dz = 0, so it contributes exactly
 * zero (the softening keeps r2 > 0). This removes a branch from the hot loop.
 */
static void compute_accel(Bodies *b)
{
    const size_t n = b->n;
    const double *restrict x = b->x, *restrict y = b->y, *restrict z = b->z;
    const double *restrict m = b->m;
    double *restrict ax = b->ax, *restrict ay = b->ay, *restrict az = b->az;

    for (size_t i = 0; i < n; i++) {
        const double xi = x[i], yi = y[i], zi = z[i];
        double axi = 0.0, ayi = 0.0, azi = 0.0;
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
    for (size_t i = 0; i < b->n; i++) {
        b->vx[i] += b->ax[i] * h;
        b->vy[i] += b->ay[i] * h;
        b->vz[i] += b->az[i] * h;
    }
}

static void drift(Bodies *b, double h)
{
    for (size_t i = 0; i < b->n; i++) {
        b->x[i] += b->vx[i] * h;
        b->y[i] += b->vy[i] * h;
        b->z[i] += b->vz[i] * h;
    }
}

/* Total energy = kinetic + potential (pairs i<j). O(N^2), validation only. */
static double total_energy(const Bodies *b)
{
    double ke = 0.0, pe = 0.0;
    for (size_t i = 0; i < b->n; i++) {
        ke += 0.5 * b->m[i] * (b->vx[i] * b->vx[i] + b->vy[i] * b->vy[i] + b->vz[i] * b->vz[i]);
        for (size_t j = i + 1; j < b->n; j++) {
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
    Bodies b = bodies_alloc(o.n);
    bodies_init(&b, o.seed);

    double e0 = 0.0, e1 = 0.0;
    if (o.energy) e0 = total_energy(&b);

    const double t0 = wall_time();
    compute_accel(&b);                      /* initial accelerations */
    for (int s = 0; s < o.steps; s++) {
        kick(&b, 0.5 * DT);
        drift(&b, DT);
        compute_accel(&b);
        kick(&b, 0.5 * DT);
    }
    const double elapsed = wall_time() - t0;

    if (o.energy) e1 = total_energy(&b);
    if (o.out) bodies_write(&b, o.out);

    /* steps + 1 force evaluations (one extra for the initial accelerations) */
    const double inter = (double)o.n * (double)o.n * (double)(o.steps + 1);
    const double gflops = inter * FLOPS_PER_INTERACTION / elapsed * 1e-9;
    const double drift_rel = o.energy ? fabs((e1 - e0) / e0) : 0.0;

    printf("Serial N-body | N=%zu steps=%d\n", o.n, o.steps);
    printf("  time            : %.4f s\n", elapsed);
    printf("  interactions/s  : %.3e\n", inter / elapsed);
    printf("  GFLOP/s         : %.2f\n", gflops);
    if (o.energy)
        printf("  energy          : E0=%.10e  E1=%.10e  rel.drift=%.3e\n", e0, e1, drift_rel);
    /* machine-readable line parsed by scripts/benchmark.py */
    printf("CSV,serial,%zu,%d,1,none,0,0,%.6f,%.6e,%.4f,%.3e\n",
           o.n, o.steps, elapsed, inter / elapsed, gflops, drift_rel);

    bodies_free(&b);
    return 0;
}
