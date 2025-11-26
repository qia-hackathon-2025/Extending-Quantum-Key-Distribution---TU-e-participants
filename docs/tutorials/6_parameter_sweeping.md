# Tutorial 6: Parameter Sweeping

This section shows how to systematically vary parameters in your simulations for performance analysis and optimization.

## Basic Parameter Sweeping

### Example: Varying Link Fidelity

```python
from application import AliceProgram, BobProgram
from squidasm.run.stack.config import (
    StackNetworkConfig,
    DepolariseLinkConfig,
    LinkConfig,
)
from squidasm.run.stack.run import run
import numpy as np
import matplotlib.pyplot as plt

# Load base configuration
cfg = StackNetworkConfig.from_file("config.yaml")

# Create depolarise link (will modify fidelity)
depolarise_config = DepolariseLinkConfig(
    fidelity=0.9,
    t_cycle=10.0,
    prob_success=0.8
)

link = LinkConfig(
    stack1="Alice",
    stack2="Bob",
    typ="depolarise",
    cfg=depolarise_config
)
cfg.links = [link]

# Sweep over fidelity values
fidelities = np.arange(0.5, 1.0, step=0.05)
results = []

for fidelity in fidelities:
    # Update configuration
    depolarise_config.fidelity = fidelity
    
    # Create programs
    alice_program = AliceProgram(num_rounds=10)
    bob_program = BobProgram(num_rounds=10)
    
    # Run simulation
    alice_results, bob_results = run(
        config=cfg,
        programs={"Alice": alice_program, "Bob": bob_program},
        num_times=50
    )
    
    # Calculate error rate
    errors = 0
    total = 0
    for a_res, b_res in zip(alice_results, bob_results):
        a_meas = a_res["measurements"]
        b_meas = b_res["measurements"]
        errors += sum(a != b for a, b in zip(a_meas, b_meas))
        total += len(a_meas)
    
    error_rate = errors / total if total > 0 else 0
    results.append((fidelity, error_rate))
    print(f"Fidelity: {fidelity:.2f}, Error rate: {error_rate:.2%}")

# Plot results
fids = [r[0] for r in results]
errs = [r[1] for r in results]

plt.figure(figsize=(8, 6))
plt.plot(fids, errs, 'o-', linewidth=2, markersize=8)
plt.xlabel('Link Fidelity')
plt.ylabel('Error Rate')
plt.title('EPR Pair Error Rate vs Link Fidelity')
plt.grid(True, alpha=0.3)
plt.savefig('fidelity_sweep.png', dpi=150)
plt.show()
```

## Configuration Classes

### DepolariseLinkConfig

```python
from squidasm.run.stack.config import DepolariseLinkConfig

# Create directly
config = DepolariseLinkConfig(
    fidelity=0.95,
    t_cycle=10.0,
    prob_success=0.8
)

# Or load from file
config = DepolariseLinkConfig.from_file("link_config.yaml")
```

### GenericQDeviceConfig

```python
from squidasm.run.stack.config import GenericQDeviceConfig

qdevice_config = GenericQDeviceConfig(
    num_qubits=5,
    T1=1e6,
    T2=8e5,
    init_time=100,
    single_qubit_gate_time=50,
    two_qubit_gate_time=200,
    measure_time=100,
    single_qubit_gate_depolar_prob=0.01,
    two_qubit_gate_depolar_prob=0.05
)
```

## Multi-Parameter Sweeping

Use `itertools.product` for sweeping multiple parameters:

```python
from itertools import product

# Define parameter ranges
fidelities = [0.8, 0.9, 0.95, 0.99]
t_cycles = [5, 10, 50, 100]
prob_successes = [0.5, 0.8, 0.95]

results = {}

for fidelity, t_cycle, prob in product(fidelities, t_cycles, prob_successes):
    # Update configuration
    depolarise_config.fidelity = fidelity
    depolarise_config.t_cycle = t_cycle
    depolarise_config.prob_success = prob
    
    # Run simulation
    alice_results, bob_results = run(
        config=cfg,
        programs={"Alice": AliceProgram(), "Bob": BobProgram()},
        num_times=20
    )
    
    # Store results
    error_rate = calculate_error_rate(alice_results, bob_results)
    results[(fidelity, t_cycle, prob)] = error_rate
    
    print(f"F={fidelity}, t={t_cycle}, p={prob}: {error_rate:.2%}")

# Create heatmap for fixed prob_success
prob = 0.8
data = np.zeros((len(fidelities), len(t_cycles)))
for i, f in enumerate(fidelities):
    for j, t in enumerate(t_cycles):
        data[i, j] = results[(f, t, prob)]

plt.imshow(data, aspect='auto', origin='lower', cmap='RdYlGn_r')
plt.colorbar(label='Error Rate')
plt.xticks(range(len(t_cycles)), t_cycles)
plt.yticks(range(len(fidelities)), fidelities)
plt.xlabel('t_cycle (ns)')
plt.ylabel('Fidelity')
plt.title(f'Error Rate (prob_success={prob})')
plt.savefig('heatmap.png')
```

## Sweeping Device Parameters

### Varying T1/T2 Decoherence

```python
T1_values = [1e5, 1e6, 1e7, 1e8]  # ns
T2_values = [1e4, 1e5, 1e6, 1e7]  # ns

results = {}

for T1, T2 in product(T1_values, T2_values):
    if T2 > T1:
        continue  # T2 cannot exceed T1
    
    # Update device configuration for both nodes
    cfg.stacks[0].qdevice_cfg.T1 = T1
    cfg.stacks[0].qdevice_cfg.T2 = T2
    cfg.stacks[1].qdevice_cfg.T1 = T1
    cfg.stacks[1].qdevice_cfg.T2 = T2
    
    # Run simulation
    alice_results, bob_results = run(
        config=cfg,
        programs={"Alice": AliceProgram(), "Bob": BobProgram()},
        num_times=50
    )
    
    error_rate = calculate_error_rate(alice_results, bob_results)
    results[(T1, T2)] = error_rate
```

### Varying Gate Noise

```python
depolar_probs = [0.0, 0.001, 0.005, 0.01, 0.05, 0.1]

for prob in depolar_probs:
    cfg.stacks[0].qdevice_cfg.single_qubit_gate_depolar_prob = prob
    cfg.stacks[0].qdevice_cfg.two_qubit_gate_depolar_prob = prob * 5
    cfg.stacks[1].qdevice_cfg.single_qubit_gate_depolar_prob = prob
    cfg.stacks[1].qdevice_cfg.two_qubit_gate_depolar_prob = prob * 5
    
    # Run and collect results...
```

## Sweeping Application Parameters

Vary parameters passed to your programs:

```python
# Sweep number of EPR rounds
round_counts = [5, 10, 20, 50, 100, 200]

for num_rounds in round_counts:
    alice_program = AliceProgram(num_rounds=num_rounds)
    bob_program = BobProgram(num_rounds=num_rounds)
    
    results = run(
        config=cfg,
        programs={"Alice": alice_program, "Bob": bob_program},
        num_times=20
    )
    # Analyze results...
```

## Sweeping Classical Link Delays

```python
from squidasm.run.stack.config import CLinkConfig, DefaultCLinkConfig

delays = np.logspace(0, 6, 20)  # 1 ns to 1 ms

for delay in delays:
    clink = CLinkConfig(
        stack1="Alice",
        stack2="Bob",
        typ="default",
        cfg=DefaultCLinkConfig(delay=delay)
    )
    cfg.clinks = [clink]
    
    # Run and measure execution time or other metrics...
```

## Organizing Results

### Using DataFrames

```python
import pandas as pd

# Collect results in a list of dictionaries
data = []

for fidelity in fidelities:
    depolarise_config.fidelity = fidelity
    
    alice_results, bob_results = run(
        config=cfg,
        programs={"Alice": AliceProgram(), "Bob": BobProgram()},
        num_times=50
    )
    
    error_rate = calculate_error_rate(alice_results, bob_results)
    
    data.append({
        'fidelity': fidelity,
        'error_rate': error_rate,
        'num_iterations': 50,
        'timestamp': pd.Timestamp.now()
    })

# Create DataFrame
df = pd.DataFrame(data)

# Save to CSV
df.to_csv('sweep_results.csv', index=False)

# Analysis
print(df.describe())
print(f"Minimum error at fidelity: {df.loc[df['error_rate'].idxmin(), 'fidelity']}")
```

### Saving Intermediate Results

```python
import json
import os

results_file = 'sweep_checkpoint.json'

# Load existing results if resuming
if os.path.exists(results_file):
    with open(results_file, 'r') as f:
        results = json.load(f)
else:
    results = {}

for fidelity in fidelities:
    # Skip already computed
    if str(fidelity) in results:
        continue
    
    # Run simulation...
    error_rate = compute_error_rate(...)
    
    # Save checkpoint
    results[str(fidelity)] = error_rate
    with open(results_file, 'w') as f:
        json.dump(results, f)
```

## Statistical Analysis

### Computing Confidence Intervals

```python
from scipy import stats

def run_with_statistics(cfg, programs, fidelity, num_iterations=100, num_runs=10):
    """Run multiple independent experiments and compute statistics."""
    error_rates = []
    
    for run in range(num_runs):
        alice_results, bob_results = run(
            config=cfg,
            programs=programs,
            num_times=num_iterations
        )
        error_rate = calculate_error_rate(alice_results, bob_results)
        error_rates.append(error_rate)
    
    mean = np.mean(error_rates)
    std = np.std(error_rates, ddof=1)
    ci = stats.t.interval(0.95, len(error_rates)-1, loc=mean, scale=std/np.sqrt(len(error_rates)))
    
    return {
        'mean': mean,
        'std': std,
        'ci_lower': ci[0],
        'ci_upper': ci[1]
    }

# Usage
for fidelity in fidelities:
    depolarise_config.fidelity = fidelity
    stats = run_with_statistics(cfg, programs, fidelity)
    print(f"F={fidelity:.2f}: {stats['mean']:.3f} ± {stats['std']:.3f}")
```

### Plotting with Error Bars

```python
means = [r['mean'] for r in results]
stds = [r['std'] for r in results]

plt.errorbar(fidelities, means, yerr=stds, fmt='o-', capsize=5)
plt.fill_between(fidelities, 
                  [m - s for m, s in zip(means, stds)],
                  [m + s for m, s in zip(means, stds)],
                  alpha=0.3)
plt.xlabel('Link Fidelity')
plt.ylabel('Error Rate')
plt.title('Error Rate vs Fidelity (with std dev)')
plt.savefig('error_bars.png')
```

## Utility Functions

### Helper for Error Rate Calculation

```python
def calculate_error_rate(alice_results, bob_results):
    """Calculate error rate from paired results."""
    errors = 0
    total = 0
    
    for a_res, b_res in zip(alice_results, bob_results):
        a_meas = a_res.get("measurements", [])
        b_meas = b_res.get("measurements", [])
        
        # Handle different array lengths
        min_len = min(len(a_meas), len(b_meas))
        errors += sum(a_meas[i] != b_meas[i] for i in range(min_len))
        total += min_len
    
    return errors / total if total > 0 else 0.0
```

### Helper for Configuration Updates

```python
def update_link_fidelity(cfg, fidelity):
    """Update link fidelity in configuration."""
    for link in cfg.links:
        if hasattr(link.cfg, 'fidelity'):
            link.cfg.fidelity = fidelity

def update_device_noise(cfg, single_qubit_prob, two_qubit_prob):
    """Update device noise parameters for all stacks."""
    for stack in cfg.stacks:
        if hasattr(stack.qdevice_cfg, 'single_qubit_gate_depolar_prob'):
            stack.qdevice_cfg.single_qubit_gate_depolar_prob = single_qubit_prob
            stack.qdevice_cfg.two_qubit_gate_depolar_prob = two_qubit_prob
```

## Best Practices

### 1. Document Your Sweeps

```python
"""
Parameter Sweep: Link Fidelity vs Error Rate
============================================
Date: 2025-01-15
Author: Your Name

Configuration:
- Device: Generic with T1=1e6, T2=8e5
- Link: Depolarise with t_cycle=10, prob_success=0.8
- Classical Link: Instant

Parameters:
- Fidelity range: [0.5, 0.95], step=0.05
- Iterations per fidelity: 50
- EPR rounds per iteration: 10

Expected: Error rate decreases monotonically with fidelity
"""
```

### 2. Use Meaningful Variable Names

```python
# Good
fidelity_sweep_results = []
error_rate_vs_fidelity = {}

# Avoid
results1 = []
data = {}
```

### 3. Validate Results

```python
# Sanity checks
assert all(0 <= r['error_rate'] <= 1 for r in results), "Invalid error rates"
assert len(results) == len(fidelities), "Missing results"

# Check monotonicity if expected
error_rates = [r['error_rate'] for r in sorted(results, key=lambda x: x['fidelity'])]
is_monotonic = all(error_rates[i] >= error_rates[i+1] 
                   for i in range(len(error_rates)-1))
if not is_monotonic:
    print("Warning: Error rate is not monotonically decreasing with fidelity")
```

## Summary

In this section you learned:

- **Single parameter sweeps** for link fidelity and other parameters
- **Multi-parameter sweeps** using `itertools.product`
- **Device parameter sweeps** for T1, T2, and gate noise
- **Application parameter sweeps** for program inputs
- **Organizing results** with DataFrames and checkpointing
- **Statistical analysis** with confidence intervals
- **Best practices** for documentation and validation

Parameter sweeping is essential for:
- Understanding protocol behavior under different conditions
- Optimizing network configurations
- Validating theoretical models
- Identifying parameter thresholds for protocol operation

## Next Steps

- [API Reference](../api/index.md) - Detailed API documentation
- [Advanced Topics](../advanced/index.md) - Custom protocols and noise models
