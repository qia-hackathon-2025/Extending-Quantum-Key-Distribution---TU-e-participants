# Advanced Tutorials

This section provides in-depth tutorials based on the advanced examples in the SquidASM repository. Each tutorial covers both the theoretical foundations and practical implementation details.

## Overview

These advanced tutorials assume familiarity with:
- Basic SquidASM programming ([Tutorial 1: Basics](../1_basics.md))
- NetQASM instruction flow ([Tutorial 2: NetQASM](../2_netqasm.md))
- Network configuration ([Tutorial 4: Network Configuration](../4_network_configuration.md))

## Tutorial List

### Blind Quantum Computation (BQC)

| Tutorial | Description | Key Concepts |
|----------|-------------|--------------|
| [1. BQC Introduction](01_bqc_introduction.md) | Theoretical foundations of Blind Quantum Computation | MBQC, RSP, computational security |
| [2. BQC Implementation](02_bqc_implementation.md) | Full BQC protocol implementation | Client-server, trap rounds |
| [3. BQC on NV Hardware](03_bqc_nv_hardware.md) | BQC adapted for NV center constraints | Sequential EPR, post_routine |
| [4. Partial BQC](04_partial_bqc.md) | Step-by-step BQC construction | Building blocks approach |

### Distributed Quantum States

| Tutorial | Description | Key Concepts |
|----------|-------------|--------------|
| [5. GHZ State Creation](05_ghz_states.md) | Multi-node GHZ state preparation | Chain protocols, corrections |
| [6. Link Layer Operations](06_link_layer.md) | Direct EPR generation patterns | create_measure, create_keep |

### Low-Level Programming

| Tutorial | Description | Key Concepts |
|----------|-------------|--------------|
| [7. Fidelity Constraints](07_fidelity_constraints.md) | EPR generation with quality requirements | min_fidelity_all_at_end |
| [8. Single Node Operations](08_single_node.md) | Local quantum operations without networking | Raw subroutines |
| [9. Custom Subroutines](09_custom_subroutines.md) | Hand-written NetQASM assembly | Advanced optimization |
| [10. Precompilation](10_precompilation.md) | Compile-then-execute patterns | Template parameters |

## Learning Paths

### Path 1: Cryptographic Protocols
For implementing secure quantum protocols:
1. [BQC Introduction](01_bqc_introduction.md)
2. [BQC Implementation](02_bqc_implementation.md)
3. [Fidelity Constraints](07_fidelity_constraints.md)

### Path 2: Distributed Computing
For multi-node quantum algorithms:
1. [GHZ State Creation](05_ghz_states.md)
2. [Link Layer Operations](06_link_layer.md)
3. [Partial BQC](04_partial_bqc.md)

### Path 3: Performance Optimization
For maximizing simulation efficiency:
1. [BQC on NV Hardware](03_bqc_nv_hardware.md)
2. [Custom Subroutines](09_custom_subroutines.md)
3. [Precompilation](10_precompilation.md)

## Prerequisites

Before starting these tutorials, ensure you have:

```bash
# SquidASM installed
pip install squidasm

# Or development installation
git clone https://github.com/QuTech-Delft/squidasm.git
cd squidasm
pip install -e .
```

## Running the Examples

All examples can be found in `squidasm/examples/advanced/`:

```bash
cd squidasm/examples/advanced

# Run BQC example
python bqc/example_bqc.py

# Run GHZ example
python ghz/example_ghz.py

# Run link layer example
python link_layer/example_link_layer_md.py
```

## Quick Reference

### Common Imports

```python
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run
```

### Configuration Patterns

```python
# Load from file
cfg = StackNetworkConfig.from_file("config.yaml")

# Programmatic creation
from squidasm.run.stack.config import (
    StackConfig, LinkConfig, GenericQDeviceConfig
)

cfg = StackNetworkConfig(
    stacks=[client_stack, server_stack],
    links=[link]
)
```

### Execution Patterns

```python
# Run simulation
results = run(
    config=cfg,
    programs={"node1": Program1(), "node2": Program2()},
    num_times=100
)
```

## See Also

- [Basic Tutorials](../index.md) - Foundational concepts
- [API Reference](../../api/index.md) - Detailed API documentation
- [Architecture](../../architecture/overview.md) - System design
- [Advanced Topics](../../advanced/index.md) - Debugging, performance, etc.
