# API Reference Documentation

Complete API documentation for SquidASM components and utilities.

## Core API

### [Program Interface and Lifecycle](./program_interface.md)
Writing programs that run on quantum network nodes.

**Topics**:
- `Program` abstract base class
- `ProgramMeta` - declaring program requirements
- `ProgramContext` - accessing runtime resources
- Program lifecycle (initialization, execution, cleanup)
- Design patterns (parameterized programs, conditional logic, multi-peer)
- Common mistakes and best practices

### [ProgramContext and Network Stack](./context_and_stack.md)
Understanding the runtime context and internal network architecture.

**Topics**:
- ProgramContext resource hierarchy
- Classical socket dictionary
- EPR socket dictionary
- Host component and protocol
- QNodeOS (QNOS) layer components
- StackNode and StackNetwork
- Data flow from program to quantum device
- Error handling and validation
- Performance considerations
- Debugging and introspection

### [Configuration Guide](./configuration.md)
Configuring networks, devices, and links.

**Topics**:
- Network configuration structure
- Stack configuration and device models
  - Generic QDevice (idealized, universal gates)
  - NV QDevice (realistic, limited gates)
- Quantum link types
  - Perfect links (no noise)
  - Depolarise links (simple noise model)
  - Heralded links (sophisticated midpoint model)
- Classical link types
  - Instant links (zero latency)
  - Default links (configurable delay)
- Complete configuration examples
- Best practices and utility functions

### [Running Simulations](./running_simulations.md)
Executing simulations and managing results.

**Topics**:
- `run()` function API
- Configuration and program parameters
- Execution modes (concurrent vs sequential)
- Results structure and access patterns
- `LogManager` for structured logging
  - Setting log levels
  - Creating loggers
  - Redirecting to files
  - Log message format
- Classical Socket API
  - Send/recv methods
  - Type handling
  - Blocking semantics
- Pre-built quantum routines
  - Teleportation
  - Distributed gates
  - GHZ state creation
  - Measurement utilities
- EPR Socket API (from NetQASM SDK)
- Qubit operations and gates

## Reference Tables

### Socket Methods

| Method | Type | Blocking | Returns |
|--------|------|----------|---------|
| `csocket.send(msg)` | Classical | No | None |
| `csocket.send_int(n)` | Classical | No | None |
| `csocket.recv()` | Classical | Yes* | str |
| `csocket.recv_int()` | Classical | Yes* | int |
| `epr.create_keep()` | EPR | No | List[Qubit] |
| `epr.recv_keep()` | EPR | Yes** | List[Qubit] |
| `epr.create_measure()` | EPR | No | Future[] |
| `epr.recv_measure()` | EPR | Yes** | Future[] |

*Requires `yield from`
**Requires `yield from`

### Gate Methods

| Method | Type | Applies To |
|--------|------|-----------|
| `qubit.X()`, `Y()`, `Z()` | Pauli | Single |
| `qubit.H()` | Hadamard | Single |
| `qubit.T()`, `S()`, `K()` | Special | Single |
| `qubit.rot_X(n,d)` | Rotation | Single |
| `qubit.cnot(target)` | Two-qubit | Two |
| `qubit.cphase(target)` | Two-qubit | Two |
| `qubit.measure()` | Measurement | Single |

### Configuration Objects

| Class | File | Purpose |
|-------|------|---------|
| `StackNetworkConfig` | `config.py` | Complete network specification |
| `StackConfig` | `config.py` | Individual node configuration |
| `GenericQDeviceConfig` | `config.py` | Generic device parameters |
| `NVQDeviceConfig` | `config.py` | NV device parameters |
| `LinkConfig` | `config.py` | Quantum link specification |
| `DepolariseLinkConfig` | `config.py` | Depolarise noise model |
| `HeraldedLinkConfig` | `config.py` | Heralded link model |
| `CLinkConfig` | `config.py` | Classical link specification |
| `DefaultCLinkConfig` | `config.py` | Default link with delay |

## Modules Overview

### squidasm.sim.stack
Internal simulation components.

- **program.py**: `Program`, `ProgramMeta`, `ProgramContext`
- **stack.py**: `StackNode`, `NodeStack`, `StackNetwork`
- **host.py**: `HostComponent`, `HostProtocol`
- **qnos.py**: `QNOSComponent`, `QNOSProtocol`
- **processor.py**: Quantum instruction execution
- **netstack.py**: Network stack for EPR generation
- **connection.py**: `QnosConnection` (NetQASM interface)
- **csocket.py**: `ClassicalSocket` (message passing)
- **common.py**: `LogManager` (logging)

### squidasm.run.stack
Simulation execution and setup.

- **config.py**: All configuration classes
- **run.py**: `run()` function
- **build.py**: Network construction utilities

### squidasm.util
Utility functions and pre-built routines.

- **util.py**: Network creation helpers (`create_two_node_network`, `create_complete_graph_network`)
- **routines.py**: Pre-built quantum routines (teleportation, distributed gates, GHZ)
- **qkd_routine.py**: QKD-specific routines

### squidasm.nqasm
NetQASM integration.

- **multithread.py**: Multi-threaded execution
- **netstack.py**: Network stack implementation

## Quick Start Examples

### Two-Node Network

```python
from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run

cfg = StackNetworkConfig.from_file("config.yaml")
programs = {"Alice": AliceProgram(), "Bob": BobProgram()}
results = run(config=cfg, programs=programs, num_times=100)
```

### Accessing Results

```python
results = run(config=cfg, programs=programs, num_times=100)

alice_results = results[0]  # All iterations for Alice
bob_results = results[1]    # All iterations for Bob

for iteration in range(100):
    alice_data = alice_results[iteration]
    bob_data = bob_results[iteration]
    # Process data...
```

### Logging

```python
from squidasm.sim.stack.common import LogManager

LogManager.set_log_level("DEBUG")
LogManager.log_to_file("simulation.log")

results = run(config=cfg, programs=programs, num_times=1)
# Check simulation.log for detailed logs
```

### Creating Programs

```python
from squidasm.sim.stack.program import Program, ProgramMeta, ProgramContext

class MyProgram(Program):
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="MyNode",
            csockets=["Peer"],
            epr_sockets=[("Peer", 1)],
            max_qubits=10
        )
    
    def run(self, context: ProgramContext):
        csocket = context.csockets["Peer"]
        epr = context.epr_sockets[("Peer", 1)]
        connection = context.connection
        
        # Quantum operations
        qubit = epr.create_keep()[0]
        qubit.H()
        result = qubit.measure()
        yield from connection.flush()
        
        # Classical communication
        csocket.send_int(int(result))
        
        return {"measurement": int(result)}
```

### Network Configuration

```yaml
stacks:
  - name: Alice
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 10
      T1: 30e6
      T2: 20e6

  - name: Bob
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 10
      T1: 30e6
      T2: 20e6

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

## API Organization

```
API Documentation
├── Program Interface
│   ├── Program and ProgramMeta
│   ├── ProgramContext
│   └── Lifecycle and patterns
│
├── Context and Stack
│   ├── Runtime resources
│   ├── Host and QNOS layers
│   ├── Data flow
│   └── Debugging
│
├── Configuration
│   ├── Network setup
│   ├── Device models
│   ├── Link models
│   └── Examples
│
└── Running Simulations
    ├── Simulation execution
    ├── Logging system
    ├── Socket APIs
    ├── Utilities
    └── Pre-built routines
```

## Next Steps

- **Getting Started**: [Program Interface](./program_interface.md)
- **Architecture**: [System Overview](../architecture/overview.md)
- **Concepts**: [Foundations](../foundations/index.md)
- **Examples**: [Tutorials](../tutorials/index.md)

## Common Queries

**How do I...?**

- **Run a simulation**: [Running Simulations](./running_simulations.md#running-simulations)
- **Write a program**: [Program Interface](./program_interface.md)
- **Configure a network**: [Configuration Guide](./configuration.md)
- **Create EPR pairs**: See [Foundations: EPR Sockets](../foundations/epr_sockets.md)
- **Send messages**: See [Foundations: Classical Communication](../foundations/classical_communication.md)
- **Debug issues**: [Context and Stack - Debugging](./context_and_stack.md#debugging-and-introspection)

**What is...?**

- **Future**: [Foundations: NetQASM](../foundations/netqasm.md#future-objects)
- **EPR pair**: [Foundations: EPR](../foundations/epr_sockets.md#what-is-epr)
- **QNPU**: [Architecture Overview](../architecture/overview.md#core-components)
- **Subroutine**: [Foundations: NetQASM](../foundations/netqasm.md#subroutine-structure)

