# Tutorial 6: Parameter Sweeping

Often you'll want to simulate not a single network configuration but a range of parameters. This section shows how to modify network configurations inside `run_simulation.py` and how to import components of the network to support this modification.

## Basic Parameter Sweeping

### Example: Varying Link Fidelity

Suppose you have an application that generates EPR pairs and measures them after applying a Hadamard gate. Your goal is to:

1. Modify the network configuration to use a depolarise link
2. Vary the fidelity of the link
3. Track how the error rate changes

Here's how to set up the sweep in `run_simulation.py`:

```python
from application import AliceProgram, BobProgram
from squidasm.run.stack.config import (
    DepolariseLinkConfig,
    LinkConfig,
    StackNetworkConfig,
)
from squidasm.run.stack.run import run
import numpy as np
from matplotlib import pyplot

# Load base configuration
cfg = StackNetworkConfig.from_file("config.yaml")

# Load depolarise link configuration from a separate file
depolarise_config = DepolariseLinkConfig.from_file("depolarise_link_config.yaml")

# Create a depolarise link object
link = LinkConfig(
    stack1="Alice",
    stack2="Bob",
    typ="depolarise",
    cfg=depolarise_config
)

# Replace the original link(s) with the depolarise link
cfg.links = [link]

# Define the range of fidelities to test
fidelity_list = np.arange(0.5, 1.0, step=0.05)
error_rate_results = []

# Iterate over each fidelity value
for fidelity in fidelity_list:
    # Update the fidelity for this iteration
    depolarise_config.fidelity = fidelity
    
    # Set program parameters
    epr_rounds = 10
    alice_program = AliceProgram(num_epr_rounds=epr_rounds)
    bob_program = BobProgram(num_epr_rounds=epr_rounds)
    
    # Run the simulation
    simulation_iterations = 20
    results_alice, results_bob = run(
        config=cfg,
        programs={"Alice": alice_program, "Bob": bob_program},
        num_times=simulation_iterations,
    )
    
    # Process results to calculate error rate
    errors = 0
    total = 0
    for i in range(simulation_iterations):
        alice_measurements = results_alice[i]["measurements"]
        bob_measurements = results_bob[i]["measurements"]
        
        errors += sum(am != bm for am, bm in zip(alice_measurements, bob_measurements))
        total += len(alice_measurements)
    
    error_rate = errors / total if total > 0 else 0
    error_rate_results.append((fidelity, error_rate))
    
    print(f"Fidelity: {fidelity:.2f}, Error rate: {error_rate * 100:.1f}%")

# Visualize results
fidelities = [x[0] for x in error_rate_results]
errors = [x[1] for x in error_rate_results]

pyplot.figure(figsize=(8, 6))
pyplot.plot(fidelities, errors, 'o-', linewidth=2, markersize=8)
pyplot.xlabel('Link Fidelity', fontsize=12)
pyplot.ylabel('Error Rate', fontsize=12)
pyplot.title('EPR Pair Error Rate vs Link Fidelity', fontsize=14)
pyplot.grid(True, alpha=0.3)
pyplot.tight_layout()
pyplot.savefig('output_error_vs_fidelity.png', dpi=150)
pyplot.show()
```

### Loading Link Configuration from File

The link configuration can be stored separately:

**`depolarise_link_config.yaml`**:

```yaml
fidelity: 0.9
t_cycle: 10.0
prob_success: 0.8
```

Load it in Python:

```python
depolarise_config = DepolariseLinkConfig.from_file("depolarise_link_config.yaml")
```

Alternatively, create it directly in Python:

```python
# Create configuration directly without a file
depolarise_config = DepolariseLinkConfig(
    fidelity=0.9,
    t_cycle=10.0,
    prob_success=0.8
)
```

## Multi-Parameter Sweeping

You can vary multiple parameters simultaneously:

```python
from itertools import product

# Define ranges for multiple parameters
fidelities = np.arange(0.5, 1.0, step=0.1)
prob_successes = np.arange(0.5, 1.0, step=0.1)

results = {}

# Sweep over all combinations
for fidelity, prob_success in product(fidelities, prob_successes):
    depolarise_config.fidelity = fidelity
    depolarise_config.prob_success = prob_success
    
    # Run simulation and collect results
    alice_program = AliceProgram(num_epr_rounds=10)
    bob_program = BobProgram(num_epr_rounds=10)
    
    results_alice, results_bob = run(
        config=cfg,
        programs={"Alice": alice_program, "Bob": bob_program},
        num_times=20,
    )
    
    # Calculate error rate
    errors = sum(
        sum(results_alice[i]["measurements"][j] != results_bob[i]["measurements"][j]
            for j in range(len(results_alice[i]["measurements"])))
        for i in range(len(results_alice))
    )
    total = sum(len(results_alice[i]["measurements"]) for i in range(len(results_alice)))
    error_rate = errors / total
    
    results[(fidelity, prob_success)] = error_rate
    
    print(f"Fidelity: {fidelity:.2f}, Prob Success: {prob_success:.2f}, "
          f"Error rate: {error_rate * 100:.1f}%")

# Visualize as a heatmap
import matplotlib.pyplot as plt

fidelity_vals = sorted(set(k[0] for k in results.keys()))
prob_success_vals = sorted(set(k[1] for k in results.keys()))

data = np.array([
    [results[(f, p)] for p in prob_success_vals]
    for f in fidelity_vals
])

plt.imshow(data, aspect='auto', origin='lower', cmap='RdYlGn_r')
plt.colorbar(label='Error Rate')
plt.xlabel('Probability of Success')
plt.ylabel('Fidelity')
plt.xticks(range(len(prob_success_vals)), [f"{p:.1f}" for p in prob_success_vals])
plt.yticks(range(len(fidelity_vals)), [f"{f:.1f}" for f in fidelity_vals])
plt.tight_layout()
plt.savefig('output_sweep_heatmap.png', dpi=150)
plt.show()
```

## Sweeping Application Parameters

You can also vary parameters in your programs:

```python
# Sweep over number of EPR pairs
epr_rounds_list = [5, 10, 20, 50, 100]
results = []

for epr_rounds in epr_rounds_list:
    alice_program = AliceProgram(num_epr_rounds=epr_rounds)
    bob_program = BobProgram(num_epr_rounds=epr_rounds)
    
    results_alice, results_bob = run(
        config=cfg,
        programs={"Alice": alice_program, "Bob": bob_program},
        num_times=20,
    )
    
    # Calculate average measurements per round
    avg_measurements = sum(
        len(results_alice[i]["measurements"])
        for i in range(len(results_alice))
    ) / len(results_alice)
    
    # Calculate error rate
    errors = sum(
        sum(results_alice[i]["measurements"][j] != results_bob[i]["measurements"][j]
            for j in range(len(results_alice[i]["measurements"])))
        for i in range(len(results_alice))
    )
    total = sum(len(results_alice[i]["measurements"]) for i in range(len(results_alice)))
    error_rate = errors / total
    
    results.append({
        'epr_rounds': epr_rounds,
        'error_rate': error_rate,
        'avg_measurements': avg_measurements
    })
    
    print(f"EPR Rounds: {epr_rounds}, Error rate: {error_rate * 100:.1f}%")

# Visualize
rounds = [r['epr_rounds'] for r in results]
errors = [r['error_rate'] for r in results]

plt.figure(figsize=(10, 6))
plt.plot(rounds, errors, 'o-', linewidth=2, markersize=8)
plt.xlabel('Number of EPR Rounds', fontsize=12)
plt.ylabel('Error Rate', fontsize=12)
plt.title('Error Rate vs Number of EPR Rounds', fontsize=14)
plt.xscale('log')
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('output_epr_rounds_sweep.png', dpi=150)
plt.show()
```

## Sweeping Network Configuration Parameters

You can vary parameters in the network itself:

```python
# Sweep over classical link delay
delays = np.logspace(0, 4, 10)  # 1 to 10000 ns
latencies = []

for delay in delays:
    # Create classical link with varying delay
    clink = CLinkConfig(
        stack1="Alice",
        stack2="Bob",
        typ="default",
        cfg=DefaultCLinkConfig(delay=delay),
    )
    cfg.clinks = [clink]
    
    # Run simulation
    alice_program = AliceProgram()
    bob_program = BobProgram()
    
    results_alice, results_bob = run(
        config=cfg,
        programs={"Alice": alice_program, "Bob": bob_program},
        num_times=10,
    )
    
    # Measure something (could be execution time, etc.)
    latencies.append((delay, results_alice[0].get('execution_time', 0)))

# Visualize
delays_vals = [x[0] for x in latencies]
times = [x[1] for x in latencies]

plt.figure(figsize=(10, 6))
plt.semilogx(delays_vals, times, 'o-', linewidth=2, markersize=8)
plt.xlabel('Classical Link Delay (ns)', fontsize=12)
plt.ylabel('Total Execution Time (ns)', fontsize=12)
plt.title('Execution Time vs Classical Link Delay', fontsize=14)
plt.grid(True, alpha=0.3, which='both')
plt.tight_layout()
plt.savefig('output_delay_sweep.png', dpi=150)
plt.show()
```

## Parallel Sweeping

For large parameter sweeps, consider running simulations in parallel:

```python
from multiprocessing import Pool
from functools import partial

def run_simulation(fidelity, cfg, epr_rounds):
    """Helper function for parallel execution."""
    from application import AliceProgram, BobProgram
    from squidasm.run.stack.run import run
    
    # Update configuration for this fidelity
    cfg.links[0].cfg.fidelity = fidelity
    
    # Create and run programs
    alice_program = AliceProgram(num_epr_rounds=epr_rounds)
    bob_program = BobProgram(num_epr_rounds=epr_rounds)
    
    results_alice, results_bob = run(
        config=cfg,
        programs={"Alice": alice_program, "Bob": bob_program},
        num_times=20,
    )
    
    # Calculate error rate
    errors = sum(
        sum(results_alice[i]["measurements"][j] != results_bob[i]["measurements"][j]
            for j in range(len(results_alice[i]["measurements"])))
        for i in range(len(results_alice))
    )
    total = sum(len(results_alice[i]["measurements"]) for i in range(len(results_alice)))
    error_rate = errors / total
    
    return (fidelity, error_rate)

if __name__ == "__main__":
    # Load configuration
    cfg = StackNetworkConfig.from_file("config.yaml")
    
    # Define parameter range
    fidelities = np.arange(0.5, 1.0, step=0.05)
    
    # Run simulations in parallel
    with Pool(processes=4) as pool:
        run_func = partial(run_simulation, cfg=cfg, epr_rounds=10)
        results = pool.map(run_func, fidelities)
    
    # Plot results
    fidelities_result = [x[0] for x in results]
    errors = [x[1] for x in results]
    
    plt.plot(fidelities_result, errors, 'o-')
    plt.xlabel('Link Fidelity')
    plt.ylabel('Error Rate')
    plt.savefig('output_parallel_sweep.png')
    plt.show()
```

## Best Practices

### 1. Use Descriptive Naming

```python
# Good
high_fidelity_results = []
low_noise_config = cfg.copy()

# Avoid
results1 = []
cfg2 = cfg
```

### 2. Store Results Systematically

```python
# Good: Use dictionaries with meaningful keys
results = {
    'fidelity': fidelities,
    'error_rates': errors,
    'std_errors': standard_errors,
}

# Or use dataclasses
from dataclasses import dataclass

@dataclass
class SweepResult:
    parameter_value: float
    error_rate: float
    execution_time: float
```

### 3. Save Intermediate Results

```python
import json

# Save results as sweep progresses
for fidelity in fidelities:
    # ... run simulation ...
    
    # Save after each iteration
    with open('sweep_results.json', 'w') as f:
        json.dump(error_rate_results, f)
```

### 4. Document Your Sweeps

```python
"""
Sweep: Fidelity vs Error Rate
==============================
Configuration: Perfect links with perfect devices
Application: Bell state measurement with Hadamard
Parameters: Fidelity range [0.5, 0.95], step 0.05
Iterations: 20 per fidelity value
EPR Pairs per iteration: 10

Expected behavior: Error rate should decrease monotonically 
with increasing fidelity.
"""
```

## Summary

In this section you learned:

- How to **vary a single parameter** (e.g., link fidelity) and analyze results
- How to **multi-parameter sweep** using `itertools.product()`
- How to **sweep application parameters** like number of EPR pairs
- How to **sweep network parameters** like classical link delays
- How to use **parallel processing** for faster sweeps
- **Best practices** for organizing and storing results

Parameter sweeping is essential for:

- Understanding how noise affects protocol performance
- Optimizing network configurations
- Validating theoretical predictions against simulations
- Finding parameter regimes where protocols remain functional
- Benchmarking different implementations

The combination of SquidASM's flexible configuration system and Python's data analysis tools makes it straightforward to systematically explore the parameter space of quantum network protocols.
