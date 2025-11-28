# Performance Optimization

This guide covers techniques for optimizing SquidASM simulation performance.

## Overview

SquidASM simulation performance depends on:

1. **Configuration complexity** - Number of nodes, qubits, operations
2. **Noise model** - More detailed models take longer
3. **Number of iterations** - Statistical significance vs. speed
4. **Code efficiency** - Protocol implementation choices

## Profiling Simulations

### Basic Timing

```python
import time
from squidasm.run.stack.run import run

start = time.time()
results = run(config=config, programs=programs, num_times=100)
elapsed = time.time() - start

print(f"Total time: {elapsed:.2f}s")
print(f"Per iteration: {elapsed/100:.3f}s")
```

### Detailed Profiling

```python
import cProfile
import pstats

def run_simulation():
    return run(config=config, programs=programs, num_times=100)

# Profile the simulation
profiler = cProfile.Profile()
profiler.enable()
results = run_simulation()
profiler.disable()

# Print statistics
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20 functions
```

### Memory Profiling

```python
import tracemalloc

tracemalloc.start()

results = run(config=config, programs=programs, num_times=100)

current, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()

print(f"Current memory: {current / 1024 / 1024:.1f} MB")
print(f"Peak memory: {peak / 1024 / 1024:.1f} MB")
```

## Configuration Optimization

### 1. Minimize Qubit Count

```yaml
# Slower: More qubits than needed
qdevice_cfg:
  num_qubits: 100

# Faster: Only what's needed
qdevice_cfg:
  num_qubits: 5
```

Each qubit increases state space exponentially for entangled systems.

### 2. Use Appropriate Link Types

```yaml
# Fastest: No noise modeling
links:
  - stack1: Alice
    stack2: Bob
    typ: perfect

# Medium: Simple noise model
links:
  - stack1: Alice
    stack2: Bob
    typ: depolarise
    cfg:
      fidelity: 0.95

# Slowest: Detailed physical model
links:
  - stack1: Alice
    stack2: Bob
    typ: heralded
    cfg:
      p_create: 0.1
      p_success: 0.5
```

### 3. Use Perfect Links for Development

```python
# Development configuration
dev_config = """
stacks:
  - name: Alice
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 3
      T1: 1e15
      T2: 1e15
      single_qubit_gate_depolar_prob: 0.0
      two_qubit_gate_depolar_prob: 0.0

links:
  - stack1: Alice
    stack2: Bob
    typ: perfect

clinks:
  - stack1: Alice
    stack2: Bob
    typ: instant
"""

# Production configuration with noise
prod_config = """
# ... full noise parameters
"""
```

### 4. Generic vs NV Devices

```yaml
# Faster: Generic device
qdevice_typ: generic

# Slower: NV-specific physics
qdevice_typ: nv
```

NV devices model additional physical effects (electron-carbon interactions).

## Code Optimization

### 1. Batch Operations Before Flush

```python
# Slower: Many flushes
for _ in range(10):
    qubit.H()
    yield from context.connection.flush()

# Faster: Batch then flush
for _ in range(10):
    qubit.H()
yield from context.connection.flush()
```

Each `flush()` is a synchronization point with overhead.

### 2. Efficient EPR Creation

```python
# Slower: Create one at a time
qubits = []
for _ in range(5):
    q = epr_socket.create_keep()[0]
    qubits.append(q)
    yield from context.connection.flush()

# Faster: Create multiple at once
qubits = epr_socket.create_keep(number=5)
yield from context.connection.flush()
```

### 3. Minimize Classical Communication

```python
# Slower: Many small messages
for bit in bits:
    csocket.send(str(bit))
    yield from context.connection.flush()

# Faster: One message
csocket.send(''.join(str(b) for b in bits))
yield from context.connection.flush()
```

### 4. Pre-compute What You Can

```python
# Slower: Compute basis choices during simulation
import random

class SlowProgram(Program):
    def run(self, context):
        bases = [random.choice([0, 1]) for _ in range(1000)]
        # ...

# Faster: Pre-compute before simulation
class FastProgram(Program):
    def __init__(self, num_rounds=1000):
        self.bases = [random.choice([0, 1]) for _ in range(num_rounds)]
    
    def run(self, context):
        # Use pre-computed bases
        # ...
```

## Iteration Optimization

### Adaptive Sampling

```python
def run_with_adaptive_sampling(config, programs, target_std_err=0.01, max_iterations=10000):
    """Run until statistical precision is achieved."""
    results = []
    batch_size = 100
    
    while len(results) < max_iterations:
        # Run batch
        batch = run(config=config, programs=programs, num_times=batch_size)
        results.extend(batch)
        
        # Calculate statistics
        values = [r[0]['value'] for r in results]
        mean = sum(values) / len(values)
        variance = sum((v - mean)**2 for v in values) / len(values)
        std_err = (variance / len(values))**0.5
        
        print(f"N={len(results)}, mean={mean:.4f}, std_err={std_err:.4f}")
        
        if std_err < target_std_err:
            print(f"Target precision reached with {len(results)} samples")
            break
    
    return results
```

### Parallel Sweeps (External)

For parameter sweeps, use multiprocessing:

```python
from multiprocessing import Pool
import yaml

def run_single_config(params):
    """Run simulation with specific parameters."""
    fidelity, noise = params
    
    # Create config
    config = create_config(fidelity=fidelity, noise=noise)
    
    # Run
    results = run(config=config, programs=programs, num_times=100)
    
    # Return summary
    return {
        'fidelity': fidelity,
        'noise': noise,
        'mean': calculate_mean(results)
    }

# Parameter grid
params = [
    (f, n) 
    for f in [0.8, 0.9, 0.95, 0.99]
    for n in [0.0, 0.001, 0.01]
]

# Run in parallel
with Pool(4) as pool:
    results = pool.map(run_single_config, params)

print(results)
```

## Memory Optimization

### 1. Process Results Incrementally

```python
# Memory-heavy: Store all results
all_results = run(config=config, programs=programs, num_times=10000)
# all_results holds 10000 result dictionaries in memory

# Memory-efficient: Process in batches
def run_with_batch_processing(config, programs, total, batch_size=100):
    """Run in batches and aggregate statistics."""
    total_sum = 0
    total_count = 0
    
    for _ in range(total // batch_size):
        batch = run(config=config, programs=programs, num_times=batch_size)
        
        # Process batch immediately
        for result in batch:
            total_sum += result[0]['value']
            total_count += 1
        
        # Batch results can be garbage collected
    
    return total_sum / total_count
```

### 2. Clear NetSquid State

```python
import netsquid as ns

for i in range(num_experiments):
    # Reset simulator state
    ns.sim_reset()
    
    # Run experiment
    results = run(config=config, programs=programs, num_times=1)
    
    # Process results
    process(results)
```

### 3. Use Generators for Large Sweeps

```python
def parameter_sweep_generator(fidelities, noise_levels):
    """Generate results one at a time."""
    for fidelity in fidelities:
        for noise in noise_levels:
            config = create_config(fidelity, noise)
            result = run(config=config, programs=programs, num_times=100)
            yield (fidelity, noise, result)

# Use generator - only one result in memory at a time
for fidelity, noise, result in parameter_sweep_generator(fidelities, noise_levels):
    process_and_save(fidelity, noise, result)
```

## Benchmarking Framework

```python
import time
import statistics
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class BenchmarkResult:
    name: str
    iterations: int
    total_time: float
    times_per_iteration: List[float]
    
    @property
    def mean_time(self) -> float:
        return statistics.mean(self.times_per_iteration)
    
    @property
    def std_time(self) -> float:
        return statistics.stdev(self.times_per_iteration) if len(self.times_per_iteration) > 1 else 0
    
    def __str__(self) -> str:
        return (f"{self.name}: {self.iterations} iterations, "
                f"total={self.total_time:.2f}s, "
                f"mean={self.mean_time:.4f}s ± {self.std_time:.4f}s")

def benchmark_config(name: str, config, programs, num_iterations: int = 100) -> BenchmarkResult:
    """Benchmark a configuration."""
    times = []
    
    total_start = time.time()
    for _ in range(num_iterations):
        start = time.time()
        run(config=config, programs=programs, num_times=1)
        times.append(time.time() - start)
    total_time = time.time() - total_start
    
    return BenchmarkResult(
        name=name,
        iterations=num_iterations,
        total_time=total_time,
        times_per_iteration=times
    )

# Compare configurations
configs = {
    'perfect': perfect_config,
    'depolarise': depolarise_config,
    'heralded': heralded_config
}

results = {}
for name, config in configs.items():
    results[name] = benchmark_config(name, config, programs, num_iterations=50)
    print(results[name])
```

## Performance Tips Summary

### Configuration

| Optimization | Impact | Tradeoff |
|--------------|--------|----------|
| Perfect links | High | No noise data |
| Generic device | Medium | Less physical accuracy |
| Fewer qubits | High | Protocol limitations |
| Instant clinks | Low | No classical delay |

### Code

| Optimization | Impact | Tradeoff |
|--------------|--------|----------|
| Batch operations | High | None |
| Batch EPR creation | Medium | None |
| Pre-computation | Low-Medium | Memory |
| Minimize messages | Low | None |

### Execution

| Optimization | Impact | Tradeoff |
|--------------|--------|----------|
| Adaptive sampling | High | Complexity |
| Parallel sweeps | High | Setup complexity |
| Batch processing | Medium | Code complexity |
| Generator patterns | Low-Medium | Code complexity |

## Typical Performance Numbers

| Configuration | Operations | Time per iteration |
|---------------|------------|-------------------|
| Perfect, 2 nodes, 1 EPR | ~10 | ~1 ms |
| Depolarise, 2 nodes, 1 EPR | ~10 | ~5 ms |
| Heralded, 2 nodes, 1 EPR | ~10 | ~20 ms |
| Perfect, 3 nodes, teleportation | ~30 | ~5 ms |
| NV device, 2 nodes | ~10 | ~10 ms |

*Note: Actual times vary with hardware and specific operations.*

## See Also

- [Noise Models](noise_models.md) - Understanding noise tradeoffs
- [Debugging](debugging.md) - Diagnosing slow simulations
- [Parameter Sweeping](../tutorials/6_parameter_sweeping.md) - Efficient sweeps
