# SquidASM Tutorial Index

Step-by-step practical guides for building quantum network applications with SquidASM.

## Tutorial Sections

### [Overview](./0_overview.md)
**Getting Started with SquidASM**

Introduction and navigation for the tutorial:
- Welcome and prerequisites
- Three-file application structure
- Learning paths and organization
- How to run examples

*Estimated time: 10 minutes*

### [Section 1: Basics](./1_basics.md)
**Introducing fundamental operations**

Learn the basics of:
- Program structure and requirements
- Classical socket communication
- EPR pair generation
- Local qubit operations
- Basic measurements and gates

*Estimated time: 30 minutes*
*Example*: examples/tutorial/1_Basics

### [Section 2: NetQASM Programming](./2_netqasm.md)
**Understanding quantum instruction compilation**

Deep dive into:
- NetQASM language and instruction queues
- The flush operation and compiled code
- Future objects and delayed execution
- Control flow with Futures
- Common patterns and best practices

*Estimated time: 25 minutes*
*Examples*: examples/tutorial/2.1_NetQASM-language, examples/tutorial/2.2_Future-objects

### [Section 3: Simulation Control](./3_simulation_control.md)
**Running and analyzing simulations**

Learn how to:
- Execute simulations with the `run()` function
- Implement the Program interface
- Process program output and results
- Set up logging and debugging
- Analyzing simulation results

*Estimated time: 25 minutes*
*Examples*: examples/tutorial/3.1_output, examples/tutorial/3.2_logging

### [Section 4: Network Configuration](./4_network_configuration.md)
**Configuring networks and devices**

Master:
- YAML configuration files
- Network topology setup
- Device models (Generic, NV)
- Link types and fidelity models
- Classical link configuration
- Multi-node networks
- Dynamic configuration for parameter studies

*Estimated time: 30 minutes*
*Examples*: examples/tutorial/4.1_YAML, examples/tutorial/4.2_network-configuration

### [Section 5: Multi-Node Applications](./5_multi_node.md)
**Building applications across 3+ nodes**

Explore:
- Three-node network configuration
- Complex communication patterns
- Multiple EPR and classical sockets
- Entanglement swapping protocol
- Coordinating operations across nodes

*Estimated time: 25 minutes*
*Example*: examples/tutorial/4.3_multi-node

### [Section 6: Parameter Sweeping](./6_parameter_sweeping.md)
**Studying algorithm performance across parameters**

Study:
- Single and multi-parameter sweeps
- Programmatic configuration modification
- Batch simulation runs
- Result aggregation and analysis
- Visualization with matplotlib
- Parallel execution for large sweeps

*Estimated time: 20 minutes*
*Example*: examples/tutorial/4.4_parameter-sweeping

### [Appendix: Terminology](./appendix_terminology.md)
**Glossary of SquidASM and quantum network terms**

Quick reference for:
- Technical terms
- Component definitions
- Acronyms
- Common concepts

*Reference*: Always available

---

## Recommended Learning Paths

### Path 1: Complete Beginner (3 hours)
1. [Overview](./0_overview.md) - 10 min
2. [Basics](./1_basics.md) - 30 min
3. [NetQASM Programming](./2_netqasm.md) - 25 min
4. [Simulation Control](./3_simulation_control.md) - 25 min
5. [Network Configuration](./4_network_configuration.md) - 30 min
6. Build your first application - 40 min

### Path 2: Building Real Applications (3.5 hours)
1. [Basics](./1_basics.md) - 30 min
2. [Simulation Control](./3_simulation_control.md) - 25 min
3. [Network Configuration](./4_network_configuration.md) - 30 min
4. [Multi-Node Applications](./5_multi_node.md) - 25 min
5. [Parameter Sweeping](./6_parameter_sweeping.md) - 20 min
6. Build a complete application - 50 min

### Path 3: Advanced Topics (2.5 hours)
1. [NetQASM Programming](./2_netqasm.md) - 25 min
2. [Multi-Node Applications](./5_multi_node.md) - 25 min
3. [Parameter Sweeping](./6_parameter_sweeping.md) - 20 min
4. [Foundations: EPR Sockets](../foundations/epr_sockets.md) - 30 min
5. [Foundations: Classical Communication](../foundations/classical_communication.md) - 30 min
6. Build an advanced application - 35 min

---

## Example Applications

Each tutorial section includes complete, working examples. Key examples:

### Two-Node Bell Test
*Location*: [Basics](./1_basics.md)

```python
# Create EPR pairs and verify entanglement
alice_epr = epr_socket.create_keep()[0]
bob_epr = epr_socket.recv_keep()[0]

alice_epr.measure()
bob_epr.measure()
# Both qubits should show perfect correlation
```

### Quantum Teleportation
*Location*: [Multi-Node Applications](./5_multi_node.md)

```python
# Teleport a qubit from Alice to Bob
# Uses Bell measurement for teleportation
# Demonstrates coordinated quantum operations
```

### QKD Protocol
*Location*: [Simulation Control](./3_simulation_control.md)

```python
# Secure key distribution using quantum states
# Shows classical-quantum coordination
# Demonstrates output analysis
```

### Parameter Optimization
*Location*: [Parameter Sweeping](./6_parameter_sweeping.md)

```python
# Study algorithm performance over:
# - Link fidelities (0.8 to 1.0)
# - Network distances (10 to 100 km)
# - Device noise levels
```

---

## Tutorial Features

### Code Examples
- **Complete**: Full, runnable examples
- **Annotated**: Comments explain each part
- **Progressive**: Builds from simple to complex
- **Correct**: Tested and verified

### Conceptual Explanations
- **Clear**: No assumed advanced knowledge
- **Detailed**: Explains the "why"
- **Illustrated**: Includes diagrams and flows
- **Connected**: Links to reference documentation

### Practical Guidance
- **Do's and Don'ts**: Best practices
- **Common Mistakes**: Troubleshooting
- **Performance Tips**: Optimization hints
- **Debugging**: How to find issues

---

## Quick Reference

### Most Common Operations

```python
# Create EPR pair
qubit = epr_socket.create_keep()[0]

# Apply gate
qubit.H()

# Measure
result = qubit.measure()

# Execute
yield from connection.flush()

# Use result
print(int(result))

# Send message
csocket.send_int(data)

# Receive message
data = yield from csocket.recv_int()
```

### Configuration Template

```yaml
stacks:
  - name: Alice
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 10

links:
  - stack1: Alice
    stack2: Bob
    typ: depolarise
    cfg:
      fidelity: 0.95

clinks:
  - stack1: Alice
    stack2: Bob
    typ: instant
```

### Running a Simulation

```python
cfg = StackNetworkConfig.from_file("config.yaml")
programs = {"Alice": AliceProgram(), "Bob": BobProgram()}
results = run(config=cfg, programs=programs, num_times=100)
```

---

## Topics by Category

### Quantum Operations
- [Basics - Local Qubits](./1_basics.md#creating-local-qubits)
- [Basics - Qubit Gates](./1_basics.md#qubit-gates)
- [NetQASM - Subroutines](./2_netqasm.md#subroutine-structure)

### Communication
- [Basics - Classical Sockets](./1_basics.md#sending-classical-information)
- [NetQASM - Timing](./2_netqasm.md#wait-operations)
- [Multi-Node - Patterns](./5_multi_node.md)

### Network Setup
- [Configuration - YAML](./4_network_configuration.md#yaml)
- [Configuration - Devices](./4_network_configuration.md#quantum-device-models)
- [Configuration - Links](./4_network_configuration.md#link-configuration)

### Analysis
- [Output - Results](./3_simulation_control.md#program-output)
- [Output - Logging](./3_simulation_control.md#logging)
- [Parameter Sweep - Analysis](./6_parameter_sweeping.md)

## Time to Complete Each Section

| Tutorial | Time | Level | Examples |
|----------|------|-------|----------|
| Overview | 10 min | Beginner | N/A |
| Basics | 30 min | Beginner | 1_Basics |
| NetQASM | 25 min | Beginner | 2.1, 2.2 |
| Simulation Control | 25 min | Intermediate | 3.1, 3.2 |
| Network Config | 30 min | Intermediate | 4.1, 4.2 |
| Multi-Node | 25 min | Intermediate | 4.3 |
| Parameter Sweep | 20 min | Advanced | 4.4 |
| **Total** | **165 min** | **~2.75 hours** | **9 examples** |

---

## Quick Navigation

**Just Starting?** → [Overview](./0_overview.md)

**Want to Build Fast?** → [Basics](./1_basics.md) → [Simulation Control](./3_simulation_control.md) → [Network Configuration](./4_network_configuration.md)

**Need Deep Understanding?** → [Architecture Overview](../architecture/overview.md) → [Basics](./1_basics.md) → [NetQASM](./2_netqasm.md)

**Ready for Advanced?** → [Multi-Node Applications](./5_multi_node.md) → [Parameter Sweeping](./6_parameter_sweeping.md)

---

## Prerequisites

- Python 3.8+ installed
- Basic Python knowledge
- Understanding of quantum mechanics concepts
- SquidASM installed

See [Architecture Overview](../architecture/overview.md) for quick background.

---

## Next Steps After Tutorials

1. **Real Applications**: Build your own quantum network application
2. **Advanced Topics**: Study [Context and Stack](../api/context_and_stack.md)
3. **API Reference**: Explore [complete API docs](../api/index.md)
4. **Foundations**: Deepen understanding with [conceptual guides](../foundations/index.md)

---

## Get Help

**During tutorials**:
- Check code comments for explanations
- Reference [Terminology](./appendix_terminology.md) for terms
- Look at complete code examples

**After tutorials**:
- Review [Common Mistakes](../api/program_interface.md#common-mistakes-and-solutions)
- Check [Debugging Guide](../api/context_and_stack.md#debugging-and-introspection)
- Consult [API Reference](../api/index.md)

---

**Estimated Total Time**: 2-3 hours for complete learning path

Start with [Basics Tutorial](./1_basics.md) or [Architecture Overview](../architecture/overview.md).
