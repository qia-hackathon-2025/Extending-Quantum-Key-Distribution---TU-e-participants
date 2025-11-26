# squidasm.run Package

The `squidasm.run` package provides the infrastructure for configuring and executing SquidASM simulations.

## Overview

```
squidasm.run/
├── stack/
│   ├── config.py      # Configuration classes
│   ├── run.py         # Main run function
│   └── build.py       # Network building utilities
├── singlethread/
│   └── run.py         # Single-threaded execution
└── multithread/
    └── run.py         # Multi-threaded execution
```

## Main Entry Point: run()

The `run()` function is the primary interface for executing simulations.

### Function Signature

```python
from squidasm.run.stack.run import run

def run(
    config: StackNetworkConfig,
    programs: Dict[str, Program],
    num_times: int = 1,
) -> List[List[Dict[str, Any]]]:
    """Execute a SquidASM simulation.
    
    Args:
        config: Network configuration specifying topology and parameters
        programs: Mapping of node names to Program instances
        num_times: Number of times to run the simulation
        
    Returns:
        List of results, one list per node, each containing
        dictionaries returned by program.run() for each iteration.
    """
```

### Basic Usage

```python
from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run

# Load configuration
config = StackNetworkConfig.from_file("config.yaml")

# Create programs
alice_program = AliceProgram()
bob_program = BobProgram()

# Run simulation
results = run(
    config=config,
    programs={"Alice": alice_program, "Bob": bob_program},
    num_times=100
)

# Process results
alice_results, bob_results = results
for i, (a_res, b_res) in enumerate(zip(alice_results, bob_results)):
    print(f"Iteration {i}: Alice={a_res}, Bob={b_res}")
```

### Return Value Structure

```python
# results structure:
# [
#     [  # Node 0 (Alice) results
#         {"key": value, ...},  # Iteration 0
#         {"key": value, ...},  # Iteration 1
#         ...
#     ],
#     [  # Node 1 (Bob) results
#         {"key": value, ...},  # Iteration 0
#         {"key": value, ...},  # Iteration 1
#         ...
#     ],
# ]
```

## Configuration Classes

### StackNetworkConfig

The main configuration class that holds the complete network specification.

```python
from squidasm.run.stack.config import StackNetworkConfig

class StackNetworkConfig:
    """Complete network configuration.
    
    Attributes:
        stacks: List of StackConfig for each node
        links: List of LinkConfig for quantum connections
        clinks: List of CLinkConfig for classical connections
    """
```

#### Loading from YAML

```python
# From file
config = StackNetworkConfig.from_file("config.yaml")

# From string
yaml_str = """
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
"""
config = StackNetworkConfig.from_yaml(yaml_str)
```

#### Creating Programmatically

```python
from squidasm.run.stack.config import (
    StackNetworkConfig,
    StackConfig,
    GenericQDeviceConfig,
    LinkConfig,
    DepolariseLinkConfig,
    CLinkConfig,
)

# Create stacks
alice = StackConfig(
    name="Alice",
    qdevice_typ="generic",
    qdevice_cfg=GenericQDeviceConfig(
        num_qubits=5,
        T1=1e6,
        T2=8e5,
    )
)

bob = StackConfig(
    name="Bob",
    qdevice_typ="generic",
    qdevice_cfg=GenericQDeviceConfig(num_qubits=5)
)

# Create link
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
    typ="instant"
)

# Assemble configuration
config = StackNetworkConfig(
    stacks=[alice, bob],
    links=[link],
    clinks=[clink]
)
```

### StackConfig

Configuration for a single network node.

```python
from squidasm.run.stack.config import StackConfig

class StackConfig:
    """Configuration for a single network stack (node).
    
    Attributes:
        name (str): Node identifier
        qdevice_typ (str): Device type ("generic" or "nv")
        qdevice_cfg: Device-specific configuration
        app (Dict): Optional application configuration
    """
```

#### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | str | Yes | Unique node identifier |
| `qdevice_typ` | str | Yes | "generic" or "nv" |
| `qdevice_cfg` | QDeviceConfig | Yes | Device parameters |
| `app` | Dict | No | Application configuration |

### GenericQDeviceConfig

Configuration for the generic quantum device model.

```python
from squidasm.run.stack.config import GenericQDeviceConfig

class GenericQDeviceConfig:
    """Configuration for generic quantum device.
    
    All time parameters are in nanoseconds.
    """
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `num_qubits` | int | - | Number of qubits (required) |
| `T1` | float | ∞ | Longitudinal relaxation time (ns) |
| `T2` | float | ∞ | Transverse relaxation time (ns) |
| `init_time` | float | 0 | Initialization duration (ns) |
| `single_qubit_gate_time` | float | 0 | Single-qubit gate duration (ns) |
| `two_qubit_gate_time` | float | 0 | Two-qubit gate duration (ns) |
| `measure_time` | float | 0 | Measurement duration (ns) |
| `single_qubit_gate_depolar_prob` | float | 0 | Depolarization per single-qubit gate |
| `two_qubit_gate_depolar_prob` | float | 0 | Depolarization per two-qubit gate |

#### Example

```python
config = GenericQDeviceConfig(
    num_qubits=5,
    T1=1_000_000,      # 1 ms
    T2=800_000,        # 0.8 ms
    init_time=100,
    single_qubit_gate_time=50,
    two_qubit_gate_time=200,
    measure_time=100,
    single_qubit_gate_depolar_prob=0.001,
    two_qubit_gate_depolar_prob=0.01,
)
```

### NVQDeviceConfig

Configuration for the NV center quantum device model.

```python
from squidasm.run.stack.config import NVQDeviceConfig

class NVQDeviceConfig:
    """Configuration for NV center quantum device.
    
    Models nitrogen-vacancy centers in diamond with
    one electron qubit and multiple carbon qubits.
    """
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `num_qubits` | int | Total qubits (1 electron + carbons) |
| `T1`, `T2` | float | Decoherence times (ns) |
| `electron_init_depolar_prob` | float | Electron initialization noise |
| `carbon_init_depolar_prob` | float | Carbon initialization noise |
| `electron_single_qubit_depolar_prob` | float | Electron gate noise |
| `carbon_z_rot_depolar_prob` | float | Carbon rotation noise |
| `ec_gate_depolar_prob` | float | Electron-carbon gate noise |
| `prob_error_0`, `prob_error_1` | float | Measurement errors |

### LinkConfig

Configuration for quantum links between nodes.

```python
from squidasm.run.stack.config import LinkConfig

class LinkConfig:
    """Configuration for a quantum link.
    
    Attributes:
        stack1 (str): First node name
        stack2 (str): Second node name
        typ (str): Link type ("perfect", "depolarise", "heralded")
        cfg: Link-specific configuration
    """
```

### DepolariseLinkConfig

```python
from squidasm.run.stack.config import DepolariseLinkConfig

class DepolariseLinkConfig:
    """Depolarising noise model for EPR generation.
    
    Attributes:
        fidelity (float): Fidelity of generated EPR pairs (0-1)
        t_cycle (float): Time per generation attempt (ns)
        prob_success (float): Success probability per attempt
    """
```

#### Example

```python
config = DepolariseLinkConfig(
    fidelity=0.95,
    t_cycle=10.0,
    prob_success=0.8
)
```

### HeraldedLinkConfig

```python
from squidasm.run.stack.config import HeraldedLinkConfig

class HeraldedLinkConfig:
    """Heralded entanglement generation model.
    
    Based on the double-click protocol where nodes send
    photons to a midpoint Bell-state measurement station.
    """
```

### CLinkConfig

Configuration for classical links between nodes.

```python
from squidasm.run.stack.config import CLinkConfig

class CLinkConfig:
    """Configuration for a classical link.
    
    Attributes:
        stack1 (str): First node name
        stack2 (str): Second node name
        typ (str): Link type ("instant" or "default")
        cfg: Link-specific configuration
    """
```

### DefaultCLinkConfig

```python
from squidasm.run.stack.config import DefaultCLinkConfig

class DefaultCLinkConfig:
    """Classical link with fixed delay.
    
    Attributes:
        delay (float): Message delay in nanoseconds
    """
```

## Build Module

The `build` module (`squidasm.run.stack.build`) provides utilities for constructing network components.

### build_network()

```python
from squidasm.run.stack.build import build_network

def build_network(
    config: StackNetworkConfig
) -> Tuple[Network, Dict[str, Stack]]:
    """Build NetSquid network from configuration.
    
    Args:
        config: Network configuration
        
    Returns:
        Tuple of (NetSquid Network, mapping of node names to Stacks)
    """
```

### build_stack()

```python
from squidasm.run.stack.build import build_stack

def build_stack(
    name: str,
    stack_config: StackConfig
) -> Stack:
    """Build a single network stack.
    
    Args:
        name: Node identifier
        stack_config: Stack configuration
        
    Returns:
        Configured Stack object
    """
```

## Execution Modes

### Single-threaded Execution

Default mode, suitable for most simulations.

```python
from squidasm.run.singlethread.run import run as run_singlethread

results = run_singlethread(
    config=config,
    programs=programs,
    num_times=100
)
```

### Multi-threaded Execution

For complex simulations that benefit from parallelism.

```python
from squidasm.run.multithread.run import run as run_multithread

results = run_multithread(
    config=config,
    programs=programs,
    num_times=100
)
```

### When to Use Each Mode

| Mode | Use Case |
|------|----------|
| Single-threaded | Most simulations, debugging, simple networks |
| Multi-threaded | Large networks, many iterations, independent trials |

## Configuration File Format

### Complete YAML Example

```yaml
# config.yaml - Complete SquidASM network configuration

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
      single_qubit_gate_depolar_prob: 0.001
      two_qubit_gate_depolar_prob: 0.01
    app:
      role: sender
      num_rounds: 10
  
  - name: Bob
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 5
      T1: 1000000.0
      T2: 800000.0
      init_time: 100
      single_qubit_gate_time: 50
      two_qubit_gate_time: 200
      measure_time: 100
    app:
      role: receiver
      num_rounds: 10

links:
  - stack1: Alice
    stack2: Bob
    typ: depolarise
    cfg:
      fidelity: 0.95
      t_cycle: 10.0
      prob_success: 0.8

clinks:
  - stack1: Alice
    stack2: Bob
    typ: default
    cfg:
      delay: 1000.0
```

### Using YAML Anchors

```yaml
# Reusable configurations
default_qdevice: &default_qdevice
  num_qubits: 5
  T1: 1000000.0
  T2: 800000.0
  init_time: 100
  single_qubit_gate_time: 50
  two_qubit_gate_time: 200
  measure_time: 100

stacks:
  - name: Alice
    qdevice_typ: generic
    qdevice_cfg:
      <<: *default_qdevice
      # Can override specific values
      num_qubits: 10
  
  - name: Bob
    qdevice_typ: generic
    qdevice_cfg: *default_qdevice
  
  - name: Charlie
    qdevice_typ: generic
    qdevice_cfg: *default_qdevice
```

## Error Handling

### Configuration Errors

```python
try:
    config = StackNetworkConfig.from_file("config.yaml")
except FileNotFoundError:
    print("Configuration file not found")
except yaml.YAMLError as e:
    print(f"YAML parsing error: {e}")
except ValueError as e:
    print(f"Invalid configuration: {e}")
```

### Runtime Errors

```python
try:
    results = run(config=config, programs=programs, num_times=100)
except KeyError as e:
    print(f"Missing node in programs dict: {e}")
except RuntimeError as e:
    print(f"Simulation error: {e}")
```

### Common Issues

| Error | Cause | Solution |
|-------|-------|----------|
| `KeyError: 'Alice'` | Node name mismatch | Ensure names match in config and programs dict |
| `ValueError: num_qubits` | Missing required field | Add num_qubits to qdevice_cfg |
| `TypeError: NoneType` | Empty configuration section | Check YAML indentation |

## See Also

- [StackNetworkConfig Reference](configuration.md) - Detailed configuration options
- [squidasm.nqasm Package](nqasm_package.md) - Low-level execution
- [squidasm.sim Package](sim_package.md) - Program interface
- [Tutorial 4: Network Configuration](../tutorials/4_network_configuration.md) - Configuration tutorial
