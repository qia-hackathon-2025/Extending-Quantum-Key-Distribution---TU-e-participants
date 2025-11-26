# SquidASM Comprehensive Markdown Documentation

Welcome to the SquidASM documentation. This comprehensive guide covers all aspects of building, configuring, and running quantum network applications using SquidASM.

## Overview

SquidASM is a **quantum network simulator** built on top of [NetSquid](https://netsquid.org/) that executes applications written using the [NetQASM SDK](https://github.com/QuTech-Delft/netqasm).

**Key Features**:
- NetQASM-compatible quantum programming
- Realistic simulation of quantum networks
- Modular, configurable architecture
- Multiple hardware device models
- Comprehensive noise simulation

## Quick Navigation

### For First-Time Users

1. **[Architecture Overview](./architecture/overview.md)** - Understand the system design
2. **[Program Interface](./api/program_interface.md)** - Learn how to write programs
3. **[Configuration Guide](./api/configuration.md)** - Set up a network
4. **[Tutorials](./tutorials/index.md)** - Work through practical examples

### For Specific Topics

- **Quantum Programming**: [NetQASM Foundations](./foundations/netqasm.md)
- **Entanglement**: [EPR Sockets](./foundations/epr_sockets.md)
- **Communication**: [Classical Sockets](./foundations/classical_communication.md)
- **Running Simulations**: [Simulation API](./api/running_simulations.md)
- **Debugging**: [Logging System](./api/running_simulations.md#logging-system)

### For Reference

- **[API Reference](./api/index.md)** - Function and class documentation
- **[Architecture Deep Dive](./architecture/overview.md)** - System internals
- **[Context and Stack](./api/context_and_stack.md)** - Runtime details

## Documentation Structure

### [Architecture](./architecture/overview.md)
System design and components.
- [Overview](./architecture/overview.md) - Layered architecture (Application, Host, QNOS, Device)
- [Simulation Flow](./architecture/simulation_flow.md) - Configuration → Build → Execute → Results
- [Stack Components](./architecture/stack_components.md) - Host, QNodeOS, Netstack, QDevice
- [NetQASM Integration](./architecture/netqasm_integration.md) - SDK → Compilation → Execution

### [API Reference](./api/index.md)
Function and class documentation.
- [Program Interface](./api/program_interface.md) - Writing programs
- [Configuration](./api/configuration.md) - Network setup
- [Running Simulations](./api/running_simulations.md) - Execution API
- **Package Documentation:**
  - [squidasm.sim](./api/sim_package.md) - Core simulation (Program, ProgramContext)
  - [squidasm.run](./api/run_package.md) - Configuration and execution
  - [squidasm.nqasm](./api/nqasm_package.md) - NetQASM backend
  - [squidasm.util](./api/util_package.md) - Utilities and helpers

### [Foundations](./foundations/index.md)
Conceptual guides for key systems.
- NetQASM and quantum programming
- EPR sockets and entanglement
- Classical communication
- Logging and debugging

### [Tutorials](./tutorials/index.md)
Step-by-step practical examples.
- Basic operations
- NetQASM programming
- Simulation control
- Network configuration
- Multi-node applications
- Parameter sweeping

### [Advanced Topics](./advanced/index.md)
In-depth guides for experienced users.
- [Custom Protocols](./advanced/custom_protocols.md) - Building QKD, distillation protocols
- [Noise Models](./advanced/noise_models.md) - Gate noise, decoherence, link fidelity
- [Debugging](./advanced/debugging.md) - Logging, common issues, troubleshooting
- [Performance](./advanced/performance.md) - Optimization and benchmarking
- [NetSquid Integration](./advanced/netsquid_integration.md) - Low-level access

## Key Concepts at a Glance

### Program Model

Every SquidASM application is built from individual **Programs** running on separate nodes:

```python
class AliceProgram(Program):
    @property
    def meta(self) -> ProgramMeta:
        # Declare what resources we need
        return ProgramMeta(
            name="Alice",
            csockets=["Bob"],           # Classical socket to Bob
            epr_sockets=[("Bob", 1)],   # EPR socket with Bob
            max_qubits=10               # Need 10 qubits
        )
    
    def run(self, context: ProgramContext):
        # Execute the program using provided resources
        csocket = context.csockets["Bob"]
        epr_socket = context.epr_sockets[("Bob", 1)]
        connection = context.connection
        
        # Quantum operations...
        # Classical communication...
        
        return {"results": ...}
```

### Asynchronous Execution

Quantum operations are **queued** until `flush()`:

```python
qubit.H()           # Queue Hadamard
qubit.measure()     # Queue measurement (returns Future)
yield from connection.flush()  # Execute all queued operations
```

### Network Coordination

Communication requires **explicit synchronization**:

```python
# Sender
csocket.send(message)  # Non-blocking

# Receiver
message = yield from csocket.recv()  # Blocking, waits for message
```

## File Organization

```
docs/markdown/
├── index.md                          # This file
│
├── architecture/
│   ├── overview.md                   # System design and components
│   ├── simulation_flow.md            # Execution pipeline
│   ├── stack_components.md           # Stack layer details
│   └── netqasm_integration.md        # NetQASM compilation flow
│
├── api/
│   ├── index.md                      # API documentation index
│   ├── program_interface.md          # Writing programs
│   ├── context_and_stack.md          # Runtime context internals
│   ├── configuration.md              # Network configuration
│   ├── running_simulations.md        # Execution and utilities
│   ├── sim_package.md                # squidasm.sim package docs
│   ├── run_package.md                # squidasm.run package docs
│   ├── nqasm_package.md              # squidasm.nqasm package docs
│   └── util_package.md               # squidasm.util package docs
│
├── foundations/
│   ├── index.md                      # Conceptual guides index
│   ├── netqasm.md                    # Quantum programming
│   ├── epr_sockets.md                # Entanglement generation
│   └── classical_communication.md    # Message passing
│
├── tutorials/
│   ├── index.md                      # Tutorial index
│   ├── 1_basics.md                   # Basic operations
│   ├── 2_netqasm.md                  # NetQASM programming
│   ├── 3_simulation_control.md       # Simulation control & output
│   ├── 4_network_configuration.md    # Network setup
│   ├── 5_multi_node.md               # Multi-node applications
│   ├── 6_parameter_sweeping.md       # Parameter studies
│   └── appendix_terminology.md       # Glossary
│
└── advanced/
    ├── index.md                      # Advanced topics index
    ├── custom_protocols.md           # Building custom protocols
    ├── noise_models.md               # Noise configuration guide
    ├── debugging.md                  # Debugging techniques
    ├── performance.md                # Performance optimization
    └── netsquid_integration.md       # NetSquid low-level access
```

## Common Workflows

### Getting Started

1. Read [Architecture Overview](./architecture/overview.md)
2. Follow [Program Interface Tutorial](./api/program_interface.md)
3. Create a simple two-node application
4. Run it with [Running Simulations](./api/running_simulations.md)

### Building an Application

1. Design your quantum algorithm
2. Decide on network topology (check [Configuration Guide](./api/configuration.md))
3. Write programs for each node
4. Configure the network
5. Run simulation and analyze results

### Debugging Issues

1. Enable logging with [LogManager](./api/running_simulations.md#logging-system)
2. Check [Context and Stack - Debugging](./api/context_and_stack.md#debugging-and-introspection)
3. Review relevant foundation concepts
4. Check tutorial examples

### Optimizing Performance

1. Review [Performance Considerations](./api/context_and_stack.md#performance-considerations)
2. Batch quantum operations (fewer flushes)
3. Consider link latencies in classical communication
4. Use appropriate device models

## Key Terms

| Term | Definition | Reference |
|------|-----------|-----------|
| **Program** | Code running on a single quantum network node | [API Ref](./api/program_interface.md) |
| **Application** | Collection of Programs working together | [Architecture](./architecture/overview.md) |
| **QNPU** | Quantum Network Processing Unit | [Architecture](./architecture/overview.md) |
| **NetQASM** | Quantum assembly language for networks | [Foundations](./foundations/netqasm.md) |
| **Future** | Placeholder for quantum operation result | [Foundations](./foundations/netqasm.md) |
| **EPR Pair** | Entangled two-qubit quantum state | [Foundations](./foundations/epr_sockets.md) |
| **Socket** | Connection for communication | [API Ref](./api/program_interface.md) |
| **Flush** | Execute all queued quantum operations | [Foundations](./foundations/netqasm.md) |

## Documentation Features

### Code Examples
Every concept includes practical code examples:

```python
# Real, runnable code patterns
qubit.H()
yield from connection.flush()
```

### Diagrams and Flows
Visual representations of complex concepts:

```
Application → NetQASM → QNPU → Quantum Device
```

### Cross-References
Links between related topics help navigation.

### Best Practices
Recommendations for writing robust applications.

### Common Mistakes
Troubleshooting guide with solutions.

## Additional Resources

### External Documentation
- [NetSquid Official Docs](https://netsquid.org/)
- [NetQASM SDK Docs](https://netqasm.readthedocs.io/)
- [NetQASM Paper](https://pure.tudelft.nl/ws/portalfiles/portal/131483787/Dahlberg_2022_Quantum_Sci._Technol._7_035023.pdf)

### Related Projects
- [QuTech-Delft/netqasm](https://github.com/QuTech-Delft/netqasm) - NetQASM SDK
- [QuTech-Delft/netsquid](https://github.com/QuTech-Delft/netsquid) - NetSquid simulator
- [QuTech-Delft/squidasm](https://github.com/QuTech-Delft/squidasm) - SquidASM repository

## Conventions

### Code Examples
- Python code uses SquidASM conventions
- YAML examples show configuration syntax
- Code marked with ✅ is correct
- Code marked with ❌ is wrong

### Terminology
- **Node**: A physical quantum network endpoint
- **Peer**: Another node in the network
- **Stack**: Complete node implementation (host + QNOS + device)
- **Quantum device**: Hardware model (generic or NV)

## Getting Help

### For Questions About:

- **API Usage**: Check [API Reference](./api/index.md)
- **Concepts**: Read [Foundations](./foundations/index.md)
- **Examples**: See [Tutorials](./tutorials/index.md)
- **Architecture**: Review [System Overview](./architecture/overview.md)

### For Issues:

1. Check [Debugging Guide](./api/context_and_stack.md#debugging-and-introspection)
2. Enable logging (see [Logging System](./api/running_simulations.md#logging-system))
3. Review [Common Mistakes](./api/program_interface.md#common-mistakes-and-solutions)
4. Check [GitHub Issues](https://github.com/QuTech-Delft/squidasm/issues)

## Document Status

This documentation was generated to provide comprehensive coverage of:

✅ Architecture and system design  
✅ API reference and usage  
✅ Foundational concepts  
✅ Complete tutorials  
✅ Configuration guide  
✅ Debugging and logging  

## Feedback and Contributions

To improve this documentation:
- Report issues on [GitHub](https://github.com/QuTech-Delft/squidasm)
- Suggest improvements in discussions
- Submit pull requests with enhancements

---

**Last Updated**: November 2025  
**Documentation Version**: 1.0  
**SquidASM Version**: Latest (develop branch)

Start with [Architecture Overview](./architecture/overview.md) or jump to [API Reference](./api/index.md) if you're already familiar with quantum networks.
