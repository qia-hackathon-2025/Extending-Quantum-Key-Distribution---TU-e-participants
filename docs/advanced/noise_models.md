# Noise Models

This guide explains how to configure and understand noise models in SquidASM simulations.

## Overview

SquidASM simulates three categories of noise:

1. **Gate noise** - Errors during quantum operations
2. **Decoherence** - Qubits losing information over time
3. **Link noise** - Imperfect entanglement generation

## Gate Noise

### Depolarizing Noise Model

Gate noise is modeled using **depolarizing noise**: after each gate, a random Pauli error may occur.

```
After gate application:
  - With probability (1-p): No error
  - With probability p/3: Apply X error
  - With probability p/3: Apply Y error
  - With probability p/3: Apply Z error
```

### Configuration

```yaml
stacks:
  - name: Alice
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 5
      # Gate noise probabilities
      single_qubit_gate_depolar_prob: 0.001  # 0.1% per single-qubit gate
      two_qubit_gate_depolar_prob: 0.01      # 1% per two-qubit gate
```

### Impact on Operations

| Operation | Noise Source | Error Probability |
|-----------|--------------|-------------------|
| H, X, Y, Z | `single_qubit_gate_depolar_prob` | p |
| T, S | `single_qubit_gate_depolar_prob` | p |
| rot_X, rot_Y, rot_Z | `single_qubit_gate_depolar_prob` | p |
| CNOT, CZ | `two_qubit_gate_depolar_prob` | p |

### Example: Gate Noise Impact

```python
# No noise
single_qubit_gate_depolar_prob: 0.0

# Typical lab quality
single_qubit_gate_depolar_prob: 0.001

# Noisy device
single_qubit_gate_depolar_prob: 0.01

# Very noisy
single_qubit_gate_depolar_prob: 0.05
```

## Decoherence

### T1 and T2 Times

**T1 (longitudinal relaxation)**: Time for energy decay (|1⟩ → |0⟩)

**T2 (transverse relaxation)**: Time for phase coherence loss

Constraint: T2 ≤ 2 × T1

```yaml
qdevice_cfg:
  T1: 1000000.0    # 1 ms in nanoseconds
  T2: 800000.0     # 0.8 ms in nanoseconds
```

### When Decoherence Applies

Decoherence affects qubits **waiting in memory**:

```python
# Timeline example:
t=0:     q created (no decoherence yet)
t=100:   Gate applied (gate noise, no decoherence)
t=100-500: Qubit waiting (DECOHERENCE APPLIED)
t=500:   Measurement (measurement noise)
```

### Decoherence Formula

After time $t$ in memory:

**T1 decay** (amplitude damping):
$$P(\text{decay}) = 1 - e^{-t/T_1}$$

**T2 dephasing**:
$$P(\text{dephase}) = 1 - e^{-t/T_2}$$

### Configuration for Different Scenarios

```yaml
# Perfect (no decoherence)
T1: 1e15
T2: 1e15

# Good trapped-ion system
T1: 1e9      # ~1 second
T2: 1e8      # ~100 ms

# Typical NV center
T1: 26e6     # ~26 ms
T2: 2.2e6    # ~2.2 ms

# Superconducting qubit
T1: 50000    # ~50 μs
T2: 30000    # ~30 μs
```

## Link Noise

### Depolarise Link Model

The simplest noise model for EPR pair generation:

```yaml
links:
  - stack1: Alice
    stack2: Bob
    typ: depolarise
    cfg:
      fidelity: 0.95      # EPR pair fidelity
      t_cycle: 10.0       # Time per attempt (ns)
      prob_success: 0.8   # Success probability
```

### Fidelity Impact

**Fidelity** measures how close the generated state is to the ideal Bell state:

| Fidelity | Description |
|----------|-------------|
| 1.0 | Perfect |Φ+⟩ Bell state |
| 0.95 | Excellent, typical lab |
| 0.90 | Good, realistic networks |
| 0.85 | Moderate noise |
| 0.75 | High noise |
| 0.50 | Random state (useless) |

### Heralded Link Model

More physically realistic model based on double-click protocol:

```yaml
links:
  - stack1: Alice
    stack2: Bob
    typ: heralded
    cfg:
      p_create: 0.1      # Photon creation probability
      p_success: 0.5     # BSM success probability
      t_create: 100.0    # Attempt time (ns)
```

## NV Device Noise

### NV-Specific Noise Sources

NV centers have different noise sources for electron and carbon qubits:

```yaml
stacks:
  - name: Alice
    qdevice_typ: nv
    qdevice_cfg:
      num_qubits: 2
      
      # Decoherence
      T1: 26000000.0           # 26 ms
      T2: 2200000.0            # 2.2 ms
      
      # Initialization noise
      electron_init_depolar_prob: 0.01
      carbon_init_depolar_prob: 0.01
      
      # Gate noise
      electron_single_qubit_depolar_prob: 0.002
      carbon_z_rot_depolar_prob: 0.002
      ec_gate_depolar_prob: 0.01    # Electron-carbon interaction
      
      # Measurement errors
      prob_error_0: 0.01    # P(measure 0 | state is 1)
      prob_error_1: 0.01    # P(measure 1 | state is 0)
```

### NV vs Generic Noise

| Noise Type | Generic | NV |
|------------|---------|-----|
| Gate noise | Single param | Electron vs carbon |
| Two-qubit | Any pair | Electron-carbon only |
| Measurement | None | prob_error_0/1 |
| Native gates | All | Limited set |

## Classical Link Noise

### Delayed Communication

```yaml
clinks:
  - stack1: Alice
    stack2: Bob
    typ: default
    cfg:
      delay: 1000.0    # 1000 ns = 1 μs delay
```

### Impact on Protocols

Classical delay affects:
- Total protocol time
- Decoherence during wait
- Timing-sensitive protocols

```python
# Example: 1 μs delay with T2=100 μs
# Qubit waits during classical message = 1% dephasing
```

## Configuring Noise Scenarios

### Perfect Configuration (Testing)

```yaml
stacks:
  - name: Alice
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 5
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
```

### Realistic Lab Configuration

```yaml
stacks:
  - name: Alice
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 5
      T1: 1000000.0
      T2: 500000.0
      init_time: 100
      single_qubit_gate_time: 50
      two_qubit_gate_time: 200
      measure_time: 100
      single_qubit_gate_depolar_prob: 0.001
      two_qubit_gate_depolar_prob: 0.01

links:
  - stack1: Alice
    stack2: Bob
    typ: depolarise
    cfg:
      fidelity: 0.95
      t_cycle: 100.0
      prob_success: 0.5

clinks:
  - stack1: Alice
    stack2: Bob
    typ: default
    cfg:
      delay: 10000.0    # 10 μs for metropolitan distance
```

### Noisy Network Configuration

```yaml
stacks:
  - name: Alice
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 5
      T1: 100000.0
      T2: 50000.0
      single_qubit_gate_depolar_prob: 0.01
      two_qubit_gate_depolar_prob: 0.05

links:
  - stack1: Alice
    stack2: Bob
    typ: depolarise
    cfg:
      fidelity: 0.80
      t_cycle: 1000.0
      prob_success: 0.1
```

## Analyzing Noise Effects

### Parameter Sweep Example

```python
import numpy as np
import matplotlib.pyplot as plt
from squidasm.run.stack.config import StackNetworkConfig, DepolariseLinkConfig
from squidasm.run.stack.run import run

# Sweep fidelity
fidelities = np.arange(0.5, 1.0, 0.05)
error_rates = []

config = StackNetworkConfig.from_file("config.yaml")

for fidelity in fidelities:
    config.links[0].cfg.fidelity = fidelity
    
    results = run(
        config=config,
        programs={"Alice": AliceProgram(), "Bob": BobProgram()},
        num_times=100
    )
    
    error_rate = calculate_error_rate(results)
    error_rates.append(error_rate)

plt.plot(fidelities, error_rates, 'o-')
plt.xlabel('Link Fidelity')
plt.ylabel('Protocol Error Rate')
plt.title('Error Rate vs Link Fidelity')
plt.savefig('noise_sweep.png')
```

### Noise Budget Analysis

```python
def analyze_noise_contributions(config, programs, num_trials=1000):
    """Analyze contributions of different noise sources."""
    
    results = {}
    
    # Baseline: all noise
    results['all_noise'] = run_and_measure(config, programs, num_trials)
    
    # Remove gate noise
    cfg_no_gate = config.copy()
    cfg_no_gate.stacks[0].qdevice_cfg.single_qubit_gate_depolar_prob = 0
    cfg_no_gate.stacks[0].qdevice_cfg.two_qubit_gate_depolar_prob = 0
    results['no_gate_noise'] = run_and_measure(cfg_no_gate, programs, num_trials)
    
    # Remove decoherence
    cfg_no_T = config.copy()
    cfg_no_T.stacks[0].qdevice_cfg.T1 = 1e15
    cfg_no_T.stacks[0].qdevice_cfg.T2 = 1e15
    results['no_decoherence'] = run_and_measure(cfg_no_T, programs, num_trials)
    
    # Remove link noise
    cfg_perfect_link = config.copy()
    cfg_perfect_link.links[0].cfg.fidelity = 1.0
    results['perfect_link'] = run_and_measure(cfg_perfect_link, programs, num_trials)
    
    # Calculate contributions
    gate_contribution = results['all_noise'] - results['no_gate_noise']
    T_contribution = results['all_noise'] - results['no_decoherence']
    link_contribution = results['all_noise'] - results['perfect_link']
    
    return {
        'total_error': results['all_noise'],
        'gate_contribution': gate_contribution,
        'decoherence_contribution': T_contribution,
        'link_contribution': link_contribution
    }
```

## Best Practices

### 1. Start Perfect, Add Noise

```python
# Development workflow:
# 1. Test with perfect configuration
# 2. Add one noise source at a time
# 3. Identify breaking points
# 4. Optimize for realistic noise
```

### 2. Match Real Hardware

```python
# When possible, use measured parameters from real devices
# NV center typical values:
T1 = 26e6  # 26 ms (measured)
T2 = 2.2e6  # 2.2 ms (measured)
```

### 3. Consider All Timing

```python
# Total decoherence = sum of all wait times
# EPR generation: ~100 ns - 10 μs
# Classical communication: varies by distance
# Gate operations: 10-1000 ns
```

### 4. Document Assumptions

```python
"""
Noise parameters for this simulation:
- Based on: [reference to paper/device]
- T1, T2: Measured values from [source]
- Gate fidelity: [value] from [source]
- Link fidelity: Estimated based on [assumptions]
"""
```

## See Also

- [Network Configuration](../tutorials/4_network_configuration.md) - Configuration tutorial
- [Parameter Sweeping](../tutorials/6_parameter_sweeping.md) - Systematic analysis
- [Debugging](debugging.md) - Diagnosing noise issues
