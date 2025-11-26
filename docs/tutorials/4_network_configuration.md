# Tutorial 4: Network Configuration

In this section the network configuration file and its options will be introduced. We will also show how to edit and generate network configurations for parameter sweeps.

## Introduction to YAML

YAML is a human-readable data-serialization language. It relies on indentation for nesting, using fewer special characters than XML or JSON.

### Basic YAML Syntax

```yaml
# Key-value pairs create dictionaries
intro-text: Hello world
pi: 3.14

settings:
  alpha: 2.56
  beta: 78.2

# Lists use the minus sign
famous-scientists:
  - Albert Einstein
  - Isaac Newton
  - Marie Curie
```

This translates to Python:

```python
{
    'intro-text': 'Hello world',
    'pi': 3.14,
    'settings': {'alpha': 2.56, 'beta': 78.2},
    'famous-scientists': ['Albert Einstein', 'Isaac Newton', 'Marie Curie']
}
```

### YAML Anchors and Aliases

Avoid duplication using anchors (`&name`) and aliases (`*name`):

```yaml
bob-owner: &bob
  name: Bob
  address: Fermi street 10

cars:
  - type: Audi
    owner: *bob
  - type: Porsche
    owner: *bob
```

## The Configuration File

### Basic Structure

A SquidASM network configuration has three components:

- **Stacks** - End nodes that run applications
- **Links** - Quantum connections for EPR pair generation
- **Clinks** - Classical links for message passing

### Minimal Configuration

```yaml
stacks:
  - name: Alice
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 5
  
  - name: Bob
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 5

links:
  - stack1: Alice
    stack2: Bob
    typ: perfect

clinks:
  - stack1: Alice
    stack2: Bob
```

## Stack Configuration

### StackConfig Fields

Each stack requires:

- `name` - Node identifier (used in programs and run_simulation.py)
- `qdevice_typ` - Quantum device type: `"generic"` or `"nv"`
- `qdevice_cfg` - Device-specific configuration parameters

Optional fields:
- `app` - Application configuration accessible via `context.app_config`

### Generic Quantum Device

The generic device is an idealized model with configurable noise parameters.

#### Full Configuration

```yaml
stacks:
  - name: Alice
    qdevice_typ: generic
    qdevice_cfg:
      # Required
      num_qubits: 5
      
      # Decoherence (nanoseconds)
      T1: 1000000.0           # Longitudinal relaxation time
      T2: 800000.0            # Transverse relaxation time
      
      # Timing (nanoseconds)
      init_time: 100          # Qubit initialization time
      single_qubit_gate_time: 50
      two_qubit_gate_time: 200
      measure_time: 100
      
      # Gate noise (probability of depolarization)
      single_qubit_gate_depolar_prob: 0.01
      two_qubit_gate_depolar_prob: 0.05
```

#### GenericQDeviceConfig Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `num_qubits` | int | Number of qubits in the device |
| `T1` | float | Energy relaxation time (ns) |
| `T2` | float | Dephasing time (ns) |
| `init_time` | float | Initialization duration (ns) |
| `single_qubit_gate_time` | float | Single-qubit gate duration (ns) |
| `two_qubit_gate_time` | float | Two-qubit gate duration (ns) |
| `measure_time` | float | Measurement duration (ns) |
| `single_qubit_gate_depolar_prob` | float | Depolarization probability per single-qubit gate |
| `two_qubit_gate_depolar_prob` | float | Depolarization probability per two-qubit gate |

### NV (Nitrogen-Vacancy) Quantum Device

The NV device models nitrogen-vacancy centers in diamond with physically-motivated constraints.

#### Physical Characteristics

- **One electron qubit** (primary/communication qubit)
- **Multiple carbon qubits** (memory qubits)
- **No direct carbon-carbon interactions** - Must go through electron
- **Native gate limitations** - No direct Hadamard; requires multiple rotations

#### NV Configuration

```yaml
stacks:
  - name: Alice
    qdevice_typ: nv
    qdevice_cfg:
      num_qubits: 2              # 1 electron + n carbons
      
      # Decoherence
      T1: 26000000.0             # Much longer than generic
      T2: 2200000.0
      
      # Initialization noise
      electron_init_depolar_prob: 0.01
      carbon_init_depolar_prob: 0.01
      
      # Gate noise
      electron_single_qubit_depolar_prob: 0.002
      carbon_z_rot_depolar_prob: 0.002
      ec_gate_depolar_prob: 0.01
      
      # Measurement errors
      prob_error_0: 0.01         # P(measure 0 | state is 1)
      prob_error_1: 0.01         # P(measure 1 | state is 0)
      
      # Timing (nanoseconds)
      init_time: 100
      carbon_rot_z: 200
      electron_rot_x: 50
      electron_rot_y: 50
      electron_rot_z: 200
      ec_controlled_dir_x: 500
      ec_controlled_dir_y: 500
      measure: 1000
```

#### NVQDeviceConfig Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `num_qubits` | int | Total qubits (1 electron + n carbons) |
| `T1`, `T2` | float | Decoherence times (ns) |
| `electron_init_depolar_prob` | float | Electron init noise |
| `carbon_init_depolar_prob` | float | Carbon init noise |
| `electron_single_qubit_depolar_prob` | float | Electron gate noise |
| `carbon_z_rot_depolar_prob` | float | Carbon Z rotation noise |
| `ec_gate_depolar_prob` | float | Electron-carbon interaction noise |
| `prob_error_0`, `prob_error_1` | float | Measurement error probabilities |

### Generic vs NV: Key Differences

| Aspect | Generic | NV |
|--------|---------|-----|
| Native Hadamard | Yes | No (decomposed) |
| Direct two-qubit gates | Any pair | Electron-carbon only |
| Measurement | Any qubit | Electron only (direct) |
| Physical realism | Idealized | More realistic |
| Typical T2 | ~1 ms | ~2 ms |

## Link Configuration

### LinkConfig Fields

```yaml
links:
  - stack1: Alice          # First node
    stack2: Bob            # Second node
    typ: depolarise        # Link type
    cfg:                   # Type-specific config
      fidelity: 0.95
```

### Perfect Link

No noise, instantaneous EPR generation. Use for testing application logic.

```yaml
links:
  - stack1: Alice
    stack2: Bob
    typ: perfect
```

### Depolarise Link

Simple noise model with configurable fidelity.

```yaml
links:
  - stack1: Alice
    stack2: Bob
    typ: depolarise
    cfg:
      fidelity: 0.95       # EPR pair fidelity (0.0-1.0)
      t_cycle: 10.0        # Time per generation attempt (ns)
      prob_success: 0.8    # Success probability per attempt
```

#### DepolariseLinkConfig Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `fidelity` | float | Fidelity of generated EPR pairs |
| `t_cycle` | float | Duration of each attempt (ns) |
| `prob_success` | float | Probability of success per attempt |

### Heralded Link

Physically-motivated model based on the double-click protocol. Models fiber connections to a midpoint Bell-state measurement station.

```yaml
links:
  - stack1: Alice
    stack2: Bob
    typ: heralded
    cfg:
      p_create: 0.1        # Photon creation probability
      p_success: 0.5       # BSM success probability
      t_create: 100.0      # Attempt duration (ns)
```

## Classical Link Configuration

### CLinkConfig Fields

```yaml
clinks:
  - stack1: Alice
    stack2: Bob
    typ: default
    cfg:
      delay: 1000.0
```

### Instant Link

Zero-latency classical communication.

```yaml
clinks:
  - stack1: Alice
    stack2: Bob
    typ: instant
```

### Default Link

Classical communication with fixed delay.

```yaml
clinks:
  - stack1: Alice
    stack2: Bob
    typ: default
    cfg:
      delay: 1000.0        # Delay in nanoseconds
```

## Application Configuration

Include application-specific configuration in the stack definition:

```yaml
stacks:
  - name: Alice
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 5
    app:
      role: sender
      num_rounds: 100
      threshold: 0.95
```

Access in your program:

```python
def run(self, context: ProgramContext):
    role = context.app_config.get("role", "default")
    num_rounds = context.app_config.get("num_rounds", 1)
```

## Loading Configuration

### From YAML File

```python
from squidasm.run.stack.config import StackNetworkConfig

cfg = StackNetworkConfig.from_file("config.yaml")
```

### Programmatically

```python
from squidasm.run.stack.config import (
    StackNetworkConfig,
    StackConfig,
    GenericQDeviceConfig,
    LinkConfig,
    DepolariseLinkConfig,
    CLinkConfig,
)

# Create stack configurations
alice_cfg = StackConfig(
    name="Alice",
    qdevice_typ="generic",
    qdevice_cfg=GenericQDeviceConfig(
        num_qubits=5,
        T1=1e6,
        T2=8e5,
        init_time=100,
        single_qubit_gate_time=50,
        two_qubit_gate_time=200,
        measure_time=100,
        single_qubit_gate_depolar_prob=0.01,
        two_qubit_gate_depolar_prob=0.05,
    ),
)

bob_cfg = StackConfig(
    name="Bob",
    qdevice_typ="generic",
    qdevice_cfg=GenericQDeviceConfig(
        num_qubits=5,
        T1=1e6,
        T2=8e5,
    ),
)

# Create links
link = LinkConfig(
    stack1="Alice",
    stack2="Bob",
    typ="depolarise",
    cfg=DepolariseLinkConfig(
        fidelity=0.95,
        t_cycle=10.0,
        prob_success=0.8,
    ),
)

clink = CLinkConfig(
    stack1="Alice",
    stack2="Bob",
    typ="instant",
)

# Create network configuration
network_cfg = StackNetworkConfig(
    stacks=[alice_cfg, bob_cfg],
    links=[link],
    clinks=[clink],
)
```

## Parameter Sweeping

### Modifying Configuration at Runtime

```python
from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run
import numpy as np

# Load base configuration
cfg = StackNetworkConfig.from_file("config.yaml")

# Sweep over fidelity values
fidelities = np.arange(0.5, 1.0, 0.05)
results = []

for fidelity in fidelities:
    # Modify link fidelity
    cfg.links[0].cfg.fidelity = fidelity
    
    # Run simulation
    alice_results, bob_results = run(
        config=cfg,
        programs={"Alice": alice_program, "Bob": bob_program},
        num_times=100,
    )
    
    # Calculate metrics
    error_rate = calculate_error_rate(alice_results, bob_results)
    results.append((fidelity, error_rate))

# Plot results
import matplotlib.pyplot as plt
plt.plot([r[0] for r in results], [r[1] for r in results])
plt.xlabel('Link Fidelity')
plt.ylabel('Error Rate')
plt.savefig('fidelity_sweep.png')
```

### Multi-Parameter Sweeps

```python
import itertools

T1_values = [1e5, 1e6, 1e7]
fidelity_values = [0.8, 0.9, 0.95]

for T1, fidelity in itertools.product(T1_values, fidelity_values):
    # Update configuration
    cfg.stacks[0].qdevice_cfg.T1 = T1
    cfg.stacks[1].qdevice_cfg.T1 = T1
    cfg.links[0].cfg.fidelity = fidelity
    
    # Run and collect results
    results = run(config=cfg, programs=programs, num_times=50)
```

## Configuration Validation

The configuration classes perform validation:

```python
try:
    cfg = StackNetworkConfig.from_file("config.yaml")
except Exception as e:
    print(f"Configuration error: {e}")
```

Common validation errors:
- Missing required fields (`num_qubits`)
- Invalid parameter values (negative times, probability > 1)
- Mismatched node names between stacks and links

## Summary

In this section you learned:

- **YAML syntax** for configuration files
- **Stack configuration** for generic and NV devices with all parameters
- **Link types**: perfect, depolarise, and heralded
- **Classical link types**: instant and default
- **Application configuration** via the `app` field
- **Programmatic configuration** creation
- **Parameter sweeping** techniques

## Next Steps

- [Tutorial 5: Multi-Node Networks](5_multi_node.md) - Networks with more than two nodes
- [Tutorial 6: Parameter Sweeping](6_parameter_sweeping.md) - Advanced parameter studies
