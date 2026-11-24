/*
 * common.c — code shared by BOTH the serial and the OpenMP program:
 * memory allocation, reproducible initialisation, output, argument parsing.
 *
 * Because both executables use exactly this initialisation, they start from
 * bit-identical input, which is what makes the serial-vs-parallel validation
 * meaningful.
 */
#include "nbody.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static double *alloc_array(size_t n)
{
    /* 64-byte alignment = one cache line; helps SIMD loads. */
    void *p = NULL;
    size_t bytes = ((n * sizeof(double) + 63) / 64) * 64;
    if (posix_memalign(&p, 64, bytes) != 0) {
        fprintf(stderr, "out of memory allocating %zu doubles\n", n);
        exit(1);
    }
    memset(p, 0, bytes);
    return (double *)p;
}

Bodies bodies_alloc(size_t n)
{
    Bodies b;
    b.n  = n;
    b.x  = alloc_array(n); b.y  = alloc_array(n); b.z  = alloc_array(n);
    b.vx = alloc_array(n); b.vy = alloc_array(n); b.vz = alloc_array(n);
    b.ax = alloc_array(n); b.ay = alloc_array(n); b.az = alloc_array(n);
    b.m  = alloc_array(n);
    return b;
}

void bodies_free(Bodies *b)
{
    free(b->x);  free(b->y);  free(b->z);
    free(b->vx); free(b->vy); free(b->vz);
    free(b->ax); free(b->ay); free(b->az);
    free(b->m);
}

/*
 * Tiny portable PRNG (xorshift64*). We do NOT use rand(): its output differs
 * between macOS and Linux, and it is not thread-safe. With our own generator
 * the input is identical on every machine for a given seed.
 */
static uint64_t rng_state;
static double rng_uniform(void) /* in [0, 1) */
{
    rng_state ^= rng_state >> 12;
    rng_state ^= rng_state << 25;
    rng_state ^= rng_state >> 27;
    return (double)((rng_state * 2685821657736338717ULL) >> 11) * (1.0 / 9007199254740992.0);
}

/*
 * Bodies are placed uniformly inside a unit sphere, given small random
 * velocities, and masses in [0.5, 1.5] scaled so that the total mass is ~1.
 */
void bodies_init(Bodies *b, unsigned seed)
{
    rng_state = 0x9E3779B97F4A7C15ULL ^ (uint64_t)seed;
    if (rng_state == 0) rng_state = 1;
    const double mscale = 1.0 / (double)b->n;

    for (size_t i = 0; i < b->n; i++) {
        double px, py, pz, r2;
        do { /* rejection sampling: uniform point in the unit sphere */
            px = 2.0 * rng_uniform() - 1.0;
            py = 2.0 * rng_uniform() - 1.0;
            pz = 2.0 * rng_uniform() - 1.0;
            r2 = px * px + py * py + pz * pz;
        } while (r2 > 1.0);
        b->x[i] = px; b->y[i] = py; b->z[i] = pz;
        b->vx[i] = 0.05 * (2.0 * rng_uniform() - 1.0);
        b->vy[i] = 0.05 * (2.0 * rng_uniform() - 1.0);
        b->vz[i] = 0.05 * (2.0 * rng_uniform() - 1.0);
        b->m[i]  = (0.5 + rng_uniform()) * mscale;
        b->ax[i] = b->ay[i] = b->az[i] = 0.0;
    }
}

/* Final state dump used by scripts/validate.py: n, then x,y,z,vx,vy,vz. */
void bodies_write(const Bodies *b, const char *path)
{
    FILE *f = fopen(path, "wb");
    if (!f) { perror(path); exit(1); }
    uint64_t n = b->n;
    fwrite(&n, sizeof n, 1, f);
    fwrite(b->x,  sizeof(double), b->n, f);
    fwrite(b->y,  sizeof(double), b->n, f);
    fwrite(b->z,  sizeof(double), b->n, f);
    fwrite(b->vx, sizeof(double), b->n, f);
    fwrite(b->vy, sizeof(double), b->n, f);
    fwrite(b->vz, sizeof(double), b->n, f);
    fclose(f);
}

static void usage(const char *prog)
{
    fprintf(stderr,
        "Usage: %s [options]\n"
        "  -n N         number of bodies            (default 100000)\n"
        "  -s STEPS     number of time steps        (default 10)\n"
        "  -r SEED      random seed                 (default 42)\n"
        "  -t THREADS   OpenMP threads              (OpenMP build only)\n"
        "  -S SCHED     static | dynamic | guided   (OpenMP build only)\n"
        "  -c CHUNK     chunk size for dynamic/guided (default 64)\n"
        "  -v           use '#pragma omp simd' inner loop (OpenMP build only)\n"
        "  -e           compute total energy before and after (validation)\n"
        "  -o FILE      write final positions/velocities to FILE\n",
        prog);
    exit(1);
}

Options parse_args(int argc, char **argv, const char *prog)
{
    Options o = { 100000, 10, DEFAULT_SEED, 0, 0, 64, 0, 0, NULL };
    for (int i = 1; i < argc; i++) {
        const char *a = argv[i];
        const char *next = (i + 1 < argc) ? argv[i + 1] : NULL;
        if      (!strcmp(a, "-n") && next) { o.n = (size_t)strtoull(next, NULL, 10); i++; }
        else if (!strcmp(a, "-s") && next) { o.steps = atoi(next); i++; }
        else if (!strcmp(a, "-r") && next) { o.seed = (unsigned)strtoul(next, NULL, 10); i++; }
        else if (!strcmp(a, "-t") && next) { o.threads = atoi(next); i++; }
        else if (!strcmp(a, "-c") && next) { o.chunk = atoi(next); i++; }
        else if (!strcmp(a, "-o") && next) { o.out = next; i++; }
        else if (!strcmp(a, "-S") && next) {
            if      (!strcmp(next, "static"))  o.schedule = 0;
            else if (!strcmp(next, "dynamic")) o.schedule = 1;
            else if (!strcmp(next, "guided"))  o.schedule = 2;
            else usage(prog);
            i++;
        }
        else if (!strcmp(a, "-v")) o.simd = 1;
        else if (!strcmp(a, "-e")) o.energy = 1;
        else usage(prog);
    }
    if (o.n < 2 || o.steps < 1 || o.chunk < 1) usage(prog);
    return o;
}
