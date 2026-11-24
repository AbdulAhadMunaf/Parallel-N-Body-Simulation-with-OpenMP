/*
 * nbody.h — shared definitions for the serial and OpenMP N-body programs.
 *
 * Data layout: Structure-of-Arrays (SoA). Each physical quantity lives in its
 * own contiguous array, so the inner force loop streams through x[], y[], z[],
 * m[] with unit stride. This is cache friendly and lets the compiler vectorise.
 */
#ifndef NBODY_H
#define NBODY_H

#include <stddef.h>
#include <stdint.h>

/* ---- Physical / numerical constants (same for both programs) ---- */
#define G_CONST   1.0        /* gravitational constant (simulation units)   */
#define SOFTENING 0.01       /* epsilon: avoids 1/0 when two bodies overlap */
#define EPS2      (SOFTENING * SOFTENING)
#define DT        0.001      /* time step                                   */
#define DEFAULT_SEED 42u
#define FLOPS_PER_INTERACTION 20.0 /* standard count used for all-pairs N-body */

typedef struct {
    size_t n;
    double *x,  *y,  *z;     /* positions     */
    double *vx, *vy, *vz;    /* velocities    */
    double *ax, *ay, *az;    /* accelerations */
    double *m;               /* masses        */
} Bodies;

/* Common command-line options */
typedef struct {
    size_t   n;              /* number of bodies                 */
    int      steps;          /* number of time steps             */
    unsigned seed;           /* RNG seed (reproducible input)    */
    int      threads;        /* OpenMP threads (0 = default)     */
    int      schedule;       /* 0 = static, 1 = dynamic, 2 = guided */
    int      chunk;          /* chunk size for dynamic/guided    */
    int      simd;           /* 1 = use #pragma omp simd kernel  */
    int      energy;         /* 1 = compute energy before/after  */
    const char *out;         /* optional binary output of final positions */
} Options;

/* common.c */
Bodies  bodies_alloc(size_t n);
void    bodies_free(Bodies *b);
void    bodies_init(Bodies *b, unsigned seed);
void    bodies_write(const Bodies *b, const char *path);
Options parse_args(int argc, char **argv, const char *prog);

#endif
