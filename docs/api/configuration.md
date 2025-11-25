# Configuration Guide

Complete guide to configuring SquidASM networks, devices, and links.

## Overview

SquidASM network configurations control:
- **Network topology**: Which nodes are connected
- **Node hardware**: Qubit count, noise parameters, gate types
- **Quantum links**: EPR pair generation models and fidelity
- **Classical links**: Message passing latency

Configurations support both:
- **YAML files**: Human-readable, persistent storage
- **Python objects**: Programmatic creation for parameter sweeps

---

## Quick Start: Configuration Structure

```yaml
stacks:
  - name: Alice
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 5
      T1: 10e6
      T2: 10e6

  - name: Bob
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 5
      T1: 10e6
      T2: 10e6

links:
  - stack1: Alice
    stack2: Bob
    typ: depolarise
    cfg:
      fidelity: 0.95
      t_cycle: 10.0
      prob_success: 1.0

clinks:
  - stack1: Alice
    stack2: Bob
    typ: instant
```

---

## Stack Configuration

Specifies node hardware and quantum device model.

### StackConfig Class

```python
from squidasm.run.stack.config import StackConfig

class StackConfig:
    name: str                  # Node name (e.g., "Alice")
    qdevice_typ: str          # Device type: "generic" or "nv"
    qdevice_cfg: Dict[str, Any]  # Device-specific configuration
```

### Creating Stacks

#### From YAML

```yaml
stacks:
  - name: Alice
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 5
      T1: 10e6
      T2: 10e6
      init_time: 10.0
      single_qubit_gate_time: 10.0
      two_qubit_gate_time: 20.0
      measure_time: 100.0
      single_qubit_gate_depolar_prob: 0.0
      two_qubit_gate_depolar_prob: 0.0
```

#### Programmatically

```python
from squidasm.run.stack.config import StackConfig, GenericQDeviceConfig

cfg = StackConfig(
    name="Alice",
    qdevice_typ="generic",
    qdevice_cfg=GenericQDeviceConfig(
        num_qubits=5,
        T1=10e6,
        T2=10e6
    )
)
```

#### Using Convenience Methods

```python
# Perfect (noiseless) generic device
alice_config = StackConfig.perfect_generic_config("Alice")

# Perfect NV device
bob_config = StackConfig.perfect_nv_config("Bob")
```

---

## Quantum Device Models

### Generic QDevice

Idealized quantum device model suitable for most applications.

#### Native Gates
- Single qubit: X, Y, Z, H, T, S, K
- Rotations: Rot_X, Rot_Y, Rot_Z
- Two qubit: CNOT, CZ

#### Noise Sources
1. **Decoherence**: T1 (energy relaxation) and T2 (dephasing)
2. **Gate depolarization**: Random Pauli gate applied with probability

#### Configuration Parameters

```python
class GenericQDeviceConfig:
    num_qubits: int = 5
    T1: float = 10e6          # Nanoseconds (default: 10 microseconds)
    T2: float = 10e6          # Nanoseconds
    init_time: float = 10.0    # Nanoseconds
    single_qubit_gate_time: float = 10.0
    two_qubit_gate_time: float = 20.0
    measure_time: float = 100.0
    single_qubit_gate_depolar_prob: float = 0.0
    two_qubit_gate_depolar_prob: float = 0.0
```

#### Examples

```yaml
# Perfect device (no noise)
qdevice_typ: generic
qdevice_cfg:
  num_qubits: 10

# Noisy device with decoherence
qdevice_typ: generic
qdevice_cfg:
  num_qubits: 5
  T1: 30e6              # 30 microseconds
  T2: 20e6              # 20 microseconds
  single_qubit_gate_depolar_prob: 0.01
  two_qubit_gate_depolar_prob: 0.05

# Custom gate times
qdevice_typ: generic
qdevice_cfg:
  num_qubits: 5
  init_time: 50.0
  single_qubit_gate_time: 20.0
  two_qubit_gate_time: 100.0
  measure_time: 500.0
```

### NV (Nitrogen-Vacancy) QDevice

Realistic model for nitrogen-vacancy centers with electron and carbon qubits.

#### Architecture
- **1 electron qubit**: Can be measured, participates in all operations
- **N-1 carbon qubits**: Cannot be measured directly, limited coupling

#### Native Gates
- Single qubit rotations: Rot_X, Rot_Y, Rot_Z (applied to all qubits)
- Electron-carbon controlled gates: CXDIR, CYDIR
- No carbon-to-carbon gates
- No direct electron-to-carbon CNOT

#### Noise Sources
1. **Decoherence**: Only while idle (T1, T2)
2. **Initialization errors**: Different for electron and carbon
3. **Gate depolarization**: Different for each gate type
4. **Measurement errors**: Electron qubit readout fidelity

#### Configuration Parameters

```python
class NVQDeviceConfig:
    num_qubits: int = 2        # 1 electron + (N-1) carbon
    T1: float = 10e6           # Energy relaxation
    T2: float = 10e6           # Dephasing
    init_time: float = 10.0
    single_qubit_gate_time: float = 10.0
    ec_gate_time: float = 20.0  # Electron-carbon gate time
    measure_time: float = 100.0
    electron_init_depolar_prob: float = 0.0
    carbon_init_depolar_prob: float = 0.0
    electron_single_qubit_depolar_prob: float = 0.0
    carbon_z_rot_depolar_prob: float = 0.0
    ec_gate_depolar_prob: float = 0.0
    prob_error_0: float = 0.0   # Measure 1 when state is 0
    prob_error_1: float = 0.0   # Measure 0 when state is 1
```

#### Examples

```yaml
# Perfect NV device
qdevice_typ: nv
qdevice_cfg:
  num_qubits: 3          # 1 electron, 2 carbon qubits

# Realistic NV device
qdevice_typ: nv
qdevice_cfg:
  num_qubits: 3
  T1: 30e6
  T2: 20e6
  electron_init_depolar_prob: 0.01
  carbon_init_depolar_prob: 0.02
  ec_gate_depolar_prob: 0.05
  prob_error_0: 0.01     # 1% error rate on |0⟩
  prob_error_1: 0.02     # 2% error rate on |1⟩
```

#### Important Constraints

```python
# NV qubit indexing
# Qubit 0 = electron qubit
# Qubits 1..N-1 = carbon qubits

# When using NV in application code:
# - Can measure any qubit (SDK handles conversion)
# - Can apply any gate (SDK simulates missing gates)
# - But actual simulation only uses available operations
# - Double gate time if native gate unavailable (e.g., Hadamard on NV)
```

---

## Link Configuration

Specifies quantum link models for EPR pair generation.

### LinkConfig Class

```python
class LinkConfig:
    stack1: str           # First node
    stack2: str           # Second node
    typ: str             # Link type: "perfect", "depolarise", "heralded"
    cfg: Any             # Type-specific configuration
```

### Link Types

#### Perfect Link (No Noise)

No configuration needed:

```python
link = LinkConfig(
    stack1="Alice",
    stack2="Bob",
    typ="perfect"
)
```

Or in YAML:

```yaml
links:
  - stack1: Alice
    stack2: Bob
    typ: perfect
```

**Behavior**: Every EPR pair generation succeeds instantly with perfect fidelity.

#### Depolarise Link

Simple noise model: EPR pairs generated with reduced fidelity.

```python
from squidasm.run.stack.config import DepolariseLinkConfig

cfg = DepolariseLinkConfig(
    fidelity=0.95,          # Bell state fidelity
    t_cycle=10.0,           # Generation time (ns)
    prob_success=1.0        # Success per attempt
)

link = LinkConfig(
    stack1="Alice",
    stack2="Bob",
    typ="depolarise",
    cfg=cfg
)
```

Or in YAML:

```yaml
links:
  - stack1: Alice
    stack2: Bob
    typ: depolarise
    cfg:
      fidelity: 0.95
      t_cycle: 10.0
      prob_success: 1.0
```

**Parameters**:
- **fidelity**: Bell state fidelity (0-1)
  - 1.0 = perfect ⊙ state
  - < 1.0 = mixed with error states
- **t_cycle**: Time to attempt one EPR pair (ns)
  - Includes preparation, detection, communication
- **prob_success**: Probability each attempt succeeds (0-1)
  - 1.0 = deterministic generation
  - < 1.0 = failures requiring retries

**Use Cases**:
- Realistic fiber-based quantum links
- Quick parameter sweeps (just adjust fidelity)
- Testing robustness to link noise

#### Heralded Link (Double-Click Model)

Sophisticated model based on [arXiv:2207.10579](https://arxiv.org/abs/2207.10579):

```python
from squidasm.run.stack.config import HeraldedLinkConfig

cfg = HeraldedLinkConfig(
    # Photon generation parameters
    prob_node_success=0.6,          # Single node success
    
    # Detection parameters
    prob_bsm_success=0.8,           # Bell state measurement success
    
    # Heralding
    t_heralding=10.0,               # Time to herald (ns)
    
    # Fidelity parameters
    bsm_fidelity=0.95,
    # ... more parameters ...
)

link = LinkConfig(
    stack1="Alice",
    stack2="Bob",
    typ="heralded",
    cfg=cfg
)
```

**Behavior**:
- Nodes emit entangled photons
- Midpoint station performs Bell state measurement
- Heralding signal announces success
- Correlates success at both nodes

**Use Cases**:
- Realistic midpoint-based architectures
- Studying loss and detection efficiency
- Detailed noise modeling

---

## Classical Link Configuration

Specifies models for classical message passing.

### CLinkConfig Class

```python
class CLinkConfig:
    stack1: str           # First node
    stack2: str           # Second node
    typ: str             # Link type: "instant" or "default"
    cfg: Any             # Type-specific configuration (optional)
```

### Link Types

#### Instant CLink (Zero Latency)

No configuration:

```python
clink = CLinkConfig(
    stack1="Alice",
    stack2="Bob",
    typ="instant"
)
```

Or in YAML:

```yaml
clinks:
  - stack1: Alice
    stack2: Bob
    typ: instant
```

**Behavior**: Messages transmitted with zero delay (only simulation time advances between send and receive).

#### Default CLink (Configurable Delay)

```python
from squidasm.run.stack.config import DefaultCLinkConfig

cfg = DefaultCLinkConfig(
    delay=1000.0  # Nanoseconds
)

clink = CLinkConfig(
    stack1="Alice",
    stack2="Bob",
    typ="default",
    cfg=cfg
)
```

Or in YAML:

```yaml
clinks:
  - stack1: Alice
    stack2: Bob
    typ: default
    cfg:
      delay: 1000.0  # 1 microsecond
```

**Parameters**:
- **delay**: Fixed transmission delay in nanoseconds
  - 1000.0 = 1 microsecond
  - Accounts for fiber distance, speed of light in medium

---

## Network Configuration

The top-level `StackNetworkConfig` combines stacks, links, and clinks.

### StackNetworkConfig Class

```python
class StackNetworkConfig:
    stacks: List[StackConfig]           # Node configurations
    links: Optional[List[LinkConfig]]   # Quantum links
    clinks: Optional[List[CLinkConfig]] # Classical links
```

### Loading from YAML

```python
from squidasm.run.stack.config import StackNetworkConfig

cfg = StackNetworkConfig.from_file("config.yaml")
```

### Creating Programmatically

```python
from squidasm.run.stack.config import (
    StackNetworkConfig, StackConfig, GenericQDeviceConfig,
    LinkConfig, DepolariseLinkConfig,
    CLinkConfig, DefaultCLinkConfig
)

# Create nodes
alice = StackConfig.perfect_generic_config("Alice", num_qubits=5)
bob = StackConfig.perfect_generic_config("Bob", num_qubits=5)

# Create quantum link
link = LinkConfig(
    stack1="Alice",
    stack2="Bob",
    typ="depolarise",
    cfg=DepolariseLinkConfig(fidelity=0.95)
)

# Create classical link
clink = CLinkConfig(
    stack1="Alice",
    stack2="Bob",
    typ="default",
    cfg=DefaultCLinkConfig(delay=1000.0)
)

# Combine into network
cfg = StackNetworkConfig(
    stacks=[alice, bob],
    links=[link],
    clinks=[clink]
)
```

---

## Complete Configuration Examples

### Example 1: Perfect Two-Node Network

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
    typ: instant
```

### Example 2: Realistic Three-Node Network

```yaml
stacks:
  - name: Alice
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 10
      T1: 30e6
      T2: 20e6
      single_qubit_gate_depolar_prob: 0.01

  - name: Bob
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 10
      T1: 30e6
      T2: 20e6
      single_qubit_gate_depolar_prob: 0.01

  - name: Charlie
    qdevice_typ: nv
    qdevice_cfg:
      num_qubits: 3
      T1: 30e6
      T2: 20e6
      ec_gate_depolar_prob: 0.05

links:
  - stack1: Alice
    stack2: Bob
    typ: depolarise
    cfg:
      fidelity: 0.95
      t_cycle: 10.0
      prob_success: 0.95

  - stack1: Alice
    stack2: Charlie
    typ: depolarise
    cfg:
      fidelity: 0.9
      t_cycle: 10.0
      prob_success: 0.9

  - stack1: Bob
    stack2: Charlie
    typ: depolarise
    cfg:
      fidelity: 0.9
      t_cycle: 10.0
      prob_success: 0.9

clinks:
  - stack1: Alice
    stack2: Bob
    typ: default
    cfg:
      delay: 500.0

  - stack1: Alice
    stack2: Charlie
    typ: default
    cfg:
      delay: 1000.0

  - stack1: Bob
    stack2: Charlie
    typ: default
    cfg:
      delay: 1000.0
```

### Example 3: Parameter Sweep Template

```python
from squidasm.run.stack.config import (
    StackNetworkConfig, StackConfig, GenericQDeviceConfig,
    LinkConfig, DepolariseLinkConfig, CLinkConfig, DefaultCLinkConfig
)

def create_network(fidelity: float, distance: int):
    """Create network with configurable link fidelity and distance."""
    
    alice = StackConfig.perfect_generic_config("Alice", num_qubits=10)
    bob = StackConfig.perfect_generic_config("Bob", num_qubits=10)
    
    # Distance affects classical link latency
    # ~200,000 km/s in fiber = ~1 ns per 200 m
    classical_delay = distance / 200.0
    
    link = LinkConfig(
        stack1="Alice",
        stack2="Bob",
        typ="depolarise",
        cfg=DepolariseLinkConfig(fidelity=fidelity)
    )
    
    clink = CLinkConfig(
        stack1="Alice",
        stack2="Bob",
        typ="default",
        cfg=DefaultCLinkConfig(delay=classical_delay)
    )
    
    return StackNetworkConfig(
        stacks=[alice, bob],
        links=[link],
        clinks=[clink]
    )

# Use in parameter sweep
for fidelity in [0.8, 0.85, 0.9, 0.95, 0.99]:
    for distance in [100, 500, 1000]:
        cfg = create_network(fidelity, distance)
        results = run(config=cfg, programs=programs, num_times=100)
        # Analyze results...
```

---

## Configuration Best Practices

### 1. Use Realistic Time Parameters

- `T1`: ~1-100 microseconds (trapped ions to NV)
- `T2`: ~10-100 microseconds
- Gate times: ~1-100 nanoseconds
- Measurement: ~100-1000 nanoseconds

```yaml
# Realistic generic device
qdevice_typ: generic
qdevice_cfg:
  T1: 30e6              # 30 microseconds
  T2: 20e6              # 20 microseconds
  single_qubit_gate_time: 20.0  # 20 ns
  measure_time: 500.0   # 500 ns
```

### 2. Match Link Fidelity to Application

- Protocol-specific requirements:
  - Entanglement purification: 0.75+
  - Quantum teleportation: 0.8+
  - Bell test: 0.7+
  - QKDN: 0.85+

### 3. Use YAML for Configuration Storage

- Version control friendly
- Readable and maintainable
- Easy parameter documentation

### 4. Document Assumptions

```yaml
# Two-node entanglement distribution network
# - ~10 km fiber distance (50 ns classical latency)
# - Weak measurement assumption for quantum link

stacks:
  - name: Alice
    # Note: 10 qubit limit reflects hardware constraint
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 10

clinks:
  - stack1: Alice
    stack2: Bob
    typ: default
    cfg:
      delay: 50.0  # 10 km, ~200,000 km/s in fiber
```

---

## Utility Functions for Configuration

Located in `squidasm.util.util`:

```python
from squidasm.util.util import (
    create_two_node_network,
    create_complete_graph_network
)

# Simple two-node network
cfg = create_two_node_network()

# 3-node complete graph
cfg = create_complete_graph_network(
    node_names=["Alice", "Bob", "Charlie"],
    link_typ="depolarise",
    link_cfg=DepolariseLinkConfig(fidelity=0.95)
)
```

---

## Next Steps

- [Architecture Overview](../architecture/overview.md) - How configs are used
- [Running Simulations](./running_simulations.md) - Execute with configurations
- [Tutorials](../tutorials/4_network_configuration.md) - Configuration examples
