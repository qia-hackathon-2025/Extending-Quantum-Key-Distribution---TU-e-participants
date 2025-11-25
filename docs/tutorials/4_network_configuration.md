# Tutorial 4: Network Configuration

In this section the network configuration file and its options will be introduced. We will also show how to edit and generate network configurations to do parameter sweeps.

## Introduction to YAML

Before diving into network configuration, we introduce the YAML language briefly.

YAML is a human-readable data-serialization language similar to XML and JSON. The main difference is that YAML relies more on indentation for nesting, thus using significantly fewer special characters and improving human readability.

### Basic YAML Syntax

Key-value pairs create dictionaries:

```yaml
intro-text: Hello world
pi: 3.14

settings:
  alpha: 2.56
  beta: 78.2
```

Lists are created using the minus sign:

```yaml
famous-scientists:
  - Albert Einstein
  - Isaac Newton
  - Marie Curie
  - Enrico Fermi
```

This translates to the Python dictionary:

```python
{
    'intro-text': 'Hello world',
    'pi': 3.14,
    'settings': {
        'alpha': 2.56,
        'beta': 78.2
    },
    'famous-scientists': [
        'Albert Einstein',
        'Isaac Newton',
        'Marie Curie',
        'Enrico Fermi'
    ]
}
```

### YAML Anchors and Aliases

One useful feature of YAML is copying and pasting items using anchors and aliases:

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

By placing `&bob` after an item, you create an anchor with that tag. By using `*bob`, you reference (copy) that anchor. This helps avoid duplication.

## The Configuration File

### Basic Structure

A SquidASM network configuration requires three types of objects to be specified:

- **Stacks** - The end nodes of the network that run applications
- **Links** - Quantum connections between stacks for EPR pair generation
- **Clinks** - Classical links between stacks for message passing

### Minimal Perfect Configuration

Here's the simplest configuration without any noise:

```yaml
stacks:
  - name: Alice
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 5
      T1: 1000000.0
      T2: 1000000.0
      init_time: 100
      single_qubit_gate_time: 50
      two_qubit_gate_time: 200
      measure_time: 100
      single_qubit_gate_depolar_prob: 0.0
      two_qubit_gate_depolar_prob: 0.0
  
  - name: Bob
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 5
      T1: 1000000.0
      T2: 1000000.0
      init_time: 100
      single_qubit_gate_time: 50
      two_qubit_gate_time: 200
      measure_time: 100
      single_qubit_gate_depolar_prob: 0.0
      two_qubit_gate_depolar_prob: 0.0

links:
  - stack1: Alice
    stack2: Bob
    typ: perfect
    cfg: {}

clinks:
  - stack1: Alice
    stack2: Bob
    typ: instant
    cfg: {}
```

### Configuration Components

**Stacks** (end nodes):
- `name` - Node identifier (used in programs and run_simulation.py)
- `qdevice_typ` - Type of quantum device model (e.g., "generic", "nv")
- `qdevice_cfg` - Settings specific to the device type

**Links** (quantum connections):
- `stack1`, `stack2` - Names of the nodes to connect
- `typ` - Link model type (e.g., "perfect", "depolarise", "heralded")
- `cfg` - Settings specific to the link type

**Clinks** (classical connections):
- `stack1`, `stack2` - Names of the nodes to connect
- `typ` - Classical link type (e.g., "instant", "default")
- `cfg` - Settings specific to the link type

## Stack Types

### Generic Quantum Device

The generic quantum device is an idealized model with basic noise models but lacking peculiarities of specific physical systems.

#### Noise Sources

The generic QDevice has two broad sources of noise:

1. **Decoherence over time** - Modeled using:
   - `T1` - Energy/longitudinal relaxation time
   - `T2` - Dephasing/transverse relaxation time
   - These affect qubits kept in memory

2. **Gate operation noise** - Modeled using randomly applied Pauli gates:
   - `single_qubit_gate_depolar_prob` - Probability of Pauli gate after single-qubit operation
   - `two_qubit_gate_depolar_prob` - Probability of Pauli gate after two-qubit operation

#### Timing Parameters

All times are in nanoseconds:

- `init_time` - Qubit initialization time
- `single_qubit_gate_time` - Single-qubit gate duration
- `two_qubit_gate_time` - Two-qubit gate duration
- `measure_time` - Measurement duration

#### Configuration Example

```yaml
stacks:
  - name: Alice
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 5
      T1: 1000000.0
      T2: 800000.0
      init_time: 100
      single_qubit_gate_time: 50
      two_qubit_gate_time: 200
      measure_time: 100
      single_qubit_gate_depolar_prob: 0.01
      two_qubit_gate_depolar_prob: 0.05
```

### NV (Nitrogen-Vacancy) Quantum Device

The NV center features a more advanced, physically-motivated model. It describes a system with one electron qubit and one or more carbon qubits, with a topology that forbids direct carbon-to-carbon interactions.

#### Physical Constraints

The NV device:
- Always has **one electron qubit** (primary qubit)
- Can have multiple **carbon qubits** (secondary qubits)
- Does not support direct carbon-to-carbon interactions
- Has fewer native gates than the generic device

#### Gate Limitations

- **No native Hadamard gate** - Implemented using multiple XY or YZ rotations
- **Measurement only on electron qubit** - Carbon qubits measured indirectly
- **Electron-carbon limited** - Interactions only between electron and carbon qubits

These constraints affect program execution. Though the same gate operations can be used in the program, they execute differently and may incur additional noise.

#### Noise Parameters

All noise except decoherence is modeled using random Pauli matrices:

- `electron_init_depolar_prob` - Noise during electron initialization
- `carbon_init_depolar_prob` - Noise during carbon initialization
- `electron_single_qubit_depolar_prob` - Noise for electron single-qubit operations
- `carbon_z_rot_depolar_prob` - Noise for carbon single-qubit operations
- `ec_gate_depolar_prob` - Noise for electron-carbon interactions
- `prob_error_0` - Measurement error: measuring |1⟩ as |0⟩
- `prob_error_1` - Measurement error: measuring |0⟩ as |1⟩

#### Configuration Example

```yaml
stacks:
  - name: Alice
    qdevice_typ: nv
    qdevice_cfg:
      num_qubits: 2
      T1: 26000000.0
      T2: 2200000.0
      electron_init_depolar_prob: 0.01
      carbon_init_depolar_prob: 0.01
      electron_single_qubit_depolar_prob: 0.002
      carbon_z_rot_depolar_prob: 0.002
      ec_gate_depolar_prob: 0.01
      prob_error_0: 0.01
      prob_error_1: 0.01
      init_time: 100
      carbon_rot_z: 200
      electron_rot_x: 50
      electron_rot_y: 50
      electron_rot_z: 200
      ec_controlled_dir_x: 500
      ec_controlled_dir_y: 500
      measure: 1000
```

### Decoherence Note

Decoherence using `T1` and `T2` is only applied to qubits idle in memory. When a qubit participates in an active operation (initialization, gate, measurement), it is subject to the operation-specific noise parameters instead.

## Link Types

### Perfect Link

A perfect link with no noise. Ideal for testing applications without noise effects.

```yaml
links:
  - stack1: Alice
    stack2: Bob
    typ: perfect
    cfg: {}
```

### Depolarise Link

A simple model where EPR pairs are generated with noise controlled by fidelity.

Parameters:

- `fidelity` - How well entangled the EPR pairs are (0.0 to 1.0)
- `t_cycle` - Time for a single EPR generation attempt (nanoseconds)
- `prob_success` - Probability of successful EPR generation per attempt

```yaml
links:
  - stack1: Alice
    stack2: Bob
    typ: depolarise
    cfg:
      fidelity: 0.9
      t_cycle: 10.0
      prob_success: 0.8
```

### Heralded Link

Uses a physically-motivated model where nodes are connected via fiber to a midpoint station with a Bell-state measurement detector. Both nodes repeatedly send entangled photons, and on successful measurement, the midpoint signals both nodes.

This model is based on the [double-click model](https://arxiv.org/abs/2207.10579) from recent quantum repeater research.

```yaml
links:
  - stack1: Alice
    stack2: Bob
    typ: heralded
    cfg:
      p_create: 0.1
      p_success: 0.5
      t_create: 100.0
```

## Classical Link Types

### Instant Link

Classical communication with zero latency. Messages arrive instantaneously.

```yaml
clinks:
  - stack1: Alice
    stack2: Bob
    typ: instant
    cfg: {}
```

### Default Link

Classical communication delayed by a specified amount.

Parameters:

- `delay` - Fixed delay for all messages (nanoseconds)

```yaml
clinks:
  - stack1: Alice
    stack2: Bob
    typ: default
    cfg:
      delay: 1000.0
```

## Multi-Node Networks

SquidASM can simulate networks with more than two nodes. Simply extend the configuration with additional stacks and links:

```yaml
stacks:
  - name: Alice
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 5
      T1: 1000000.0
      T2: 1000000.0
      init_time: 100
      single_qubit_gate_time: 50
      two_qubit_gate_time: 200
      measure_time: 100
      single_qubit_gate_depolar_prob: 0.0
      two_qubit_gate_depolar_prob: 0.0
  
  - name: Bob
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 5
      T1: 1000000.0
      T2: 1000000.0
      init_time: 100
      single_qubit_gate_time: 50
      two_qubit_gate_time: 200
      measure_time: 100
      single_qubit_gate_depolar_prob: 0.0
      two_qubit_gate_depolar_prob: 0.0
  
  - name: Charlie
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 5
      T1: 1000000.0
      T2: 1000000.0
      init_time: 100
      single_qubit_gate_time: 50
      two_qubit_gate_time: 200
      measure_time: 100
      single_qubit_gate_depolar_prob: 0.0
      two_qubit_gate_depolar_prob: 0.0

links:
  - stack1: Alice
    stack2: Bob
    typ: perfect
    cfg: {}
  
  - stack1: Alice
    stack2: Charlie
    typ: perfect
    cfg: {}
  
  - stack1: Bob
    stack2: Charlie
    typ: perfect
    cfg: {}

clinks:
  - stack1: Alice
    stack2: Bob
    typ: instant
    cfg: {}
  
  - stack1: Alice
    stack2: Charlie
    typ: instant
    cfg: {}
  
  - stack1: Bob
    stack2: Charlie
    typ: instant
    cfg: {}
```

**Note**: While the example connects Charlie to both Alice and Bob, this is not mandatory as long as the application doesn't attempt to use a non-existent link.

## Parameter Sweeping

Often you'll want to simulate a range of parameters. This section shows how to modify network configurations programmatically.

### Example: Varying Link Fidelity

Suppose you want to test EPR pair generation with varying fidelity and plot the error rate:

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

# Load depolarise link configuration
depolarise_config = DepolariseLinkConfig.from_file("depolarise_link_config.yaml")

# Create a depolarise link object
link = LinkConfig(stack1="Alice", stack2="Bob", typ="depolarise", cfg=depolarise_config)

# Replace the link from YAML file
cfg.links = [link]

# Sweep over fidelity values
fidelity_list = np.arange(0.5, 1.0, step=0.05)
error_rate_results = []

for fidelity in fidelity_list:
    # Update fidelity for this iteration
    depolarise_config.fidelity = fidelity
    
    # Set program parameters
    epr_rounds = 10
    alice_program = AliceProgram(num_epr_rounds=epr_rounds)
    bob_program = BobProgram(num_epr_rounds=epr_rounds)
    
    # Run simulation
    results_alice, results_bob = run(
        config=cfg,
        programs={"Alice": alice_program, "Bob": bob_program},
        num_times=20,
    )
    
    # Calculate error rate for this fidelity
    errors = sum(
        sum(results_alice[i]["measurements"][j] != results_bob[i]["measurements"][j]
            for j in range(len(results_alice[i]["measurements"])))
        for i in range(len(results_alice))
    )
    total = sum(len(results_alice[i]["measurements"]) for i in range(len(results_alice)))
    error_rate = errors / total
    
    error_rate_results.append((fidelity, error_rate))
    print(f"Fidelity: {fidelity:.2f}, Error rate: {error_rate * 100:.1f}%")

# Plot results
fidelities = [x[0] for x in error_rate_results]
errors = [x[1] for x in error_rate_results]

pyplot.plot(fidelities, errors, 'o-')
pyplot.xlabel('Link Fidelity')
pyplot.ylabel('Error Rate')
pyplot.title('EPR Pair Error Rate vs Link Fidelity')
pyplot.savefig('output_error_vs_fidelity.png')
pyplot.show()
```

### Creating Configurations Programmatically

You don't need to always load from YAML. You can create configurations in Python:

```python
from squidasm.run.stack.config import (
    GenericQDeviceConfig,
    StackConfig,
    DepolariseLinkConfig,
    LinkConfig,
    DefaultCLinkConfig,
    CLinkConfig,
    StackNetworkConfig,
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
        init_time=100,
        single_qubit_gate_time=50,
        two_qubit_gate_time=200,
        measure_time=100,
        single_qubit_gate_depolar_prob=0.01,
        two_qubit_gate_depolar_prob=0.05,
    ),
)

# Create links
link = LinkConfig(
    stack1="Alice",
    stack2="Bob",
    typ="depolarise",
    cfg=DepolariseLinkConfig(fidelity=0.9, t_cycle=10.0, prob_success=0.8),
)

clink = CLinkConfig(
    stack1="Alice",
    stack2="Bob",
    typ="default",
    cfg=DefaultCLinkConfig(delay=1000.0),
)

# Create network
network_cfg = StackNetworkConfig(
    stacks=[alice_cfg, bob_cfg],
    links=[link],
    clinks=[clink],
)
```

## Summary

In this section you learned:

- **YAML syntax** for configuration files
- **Network components**: stacks, links, and clinks
- **Stack types**: generic device and NV device with their specific parameters
- **Link types**: perfect, depolarise, and heralded with different noise models
- **Classical link types**: instant and default with different latencies
- How to configure **multi-node networks**
- How to perform **parameter sweeping** for performance analysis
- How to create configurations **programmatically** in Python

The next sections will cover multi-node application development and advanced parameter sweeping techniques.
