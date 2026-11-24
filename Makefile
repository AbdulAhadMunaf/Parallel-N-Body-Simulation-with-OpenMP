# Parallel N-Body Simulation (OpenMP) — build file
#   make            build both programs (bin/nbody_serial, bin/nbody_omp)
#   make run        quick demo: serial vs 1/max threads at N=20000
#   make validate   check parallel == serial and energy conservation
#   make bench      full benchmark (takes ~30-40 min at N=100000)
#   make plots      regenerate graphs from results/
#   make clean

UNAME := $(shell uname -s)
CFLAGS := -O3 -std=c11 -Wall -Wextra
LDLIBS := -lm

ifeq ($(UNAME),Darwin)
  # Apple clang has no built-in OpenMP runtime: use Homebrew's libomp
  # (install with: brew install libomp)
  CC       ?= clang
  LIBOMP   := $(shell brew --prefix libomp 2>/dev/null || echo /opt/homebrew/opt/libomp)
  OMPFLAGS := -Xpreprocessor -fopenmp -I$(LIBOMP)/include
  OMPLIBS  := -L$(LIBOMP)/lib -lomp
else
  # Linux: gcc ships OpenMP (libgomp)
  CC       := gcc
  OMPFLAGS := -fopenmp
  OMPLIBS  := -fopenmp
endif

all: bin/nbody_serial bin/nbody_omp

# The serial baseline is compiled WITHOUT OpenMP on purpose.
bin/nbody_serial: src/nbody_serial.c src/common.c src/nbody.h | bin
	$(CC) $(CFLAGS) -o $@ src/nbody_serial.c src/common.c $(LDLIBS)

bin/nbody_omp: src/nbody_omp.c src/common.c src/nbody.h | bin
	$(CC) $(CFLAGS) $(OMPFLAGS) -o $@ src/nbody_omp.c src/common.c $(OMPLIBS) $(LDLIBS)

bin:
	mkdir -p bin

run: all
	./bin/nbody_serial -n 20000 -s 10
	./bin/nbody_omp    -n 20000 -s 10 -t 1
	./bin/nbody_omp    -n 20000 -s 10

validate: all
	python3 scripts/validate.py

bench: all
	python3 scripts/benchmark.py

plots:
	python3 scripts/plot.py

clean:
	rm -rf bin results/tmp

.PHONY: all run validate bench plots clean
