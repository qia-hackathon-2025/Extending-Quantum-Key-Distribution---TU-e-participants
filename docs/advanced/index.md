# Advanced Topics

This section covers advanced usage of SquidASM for experienced users.

## Topics

### [Custom Protocols](custom_protocols.md)
Building sophisticated quantum network protocols.

- Protocol design principles
- Complete BB84 QKD implementation
- Entanglement distillation
- Multi-round protocols
- Testing and validation

### [Noise Models](noise_models.md)
Understanding and configuring simulation noise.

- Gate noise (depolarizing)
- Decoherence (T1/T2)
- Link noise and fidelity
- NV device-specific noise
- Noise budget analysis

### [Debugging](debugging.md)
Techniques for debugging quantum network simulations.

- Logging configuration
- Common issues and solutions
- Print debugging patterns
- Timing analysis
- Test-driven debugging

### [Performance Optimization](performance.md)
Making simulations run faster.

- Profiling simulations
- Configuration optimization
- Code optimization
- Memory management
- Benchmarking framework

### [NetSquid Integration](netsquid_integration.md)
Accessing NetSquid's low-level features.

- SquidASM-NetSquid architecture
- Qubit state inspection
- Custom noise models
- Simulation time control
- Hybrid simulations

## Quick Reference

### When to Use Each Topic

| Scenario | Recommended Topic |
|----------|-------------------|
| Building new protocol | [Custom Protocols](custom_protocols.md) |
| Understanding failures | [Debugging](debugging.md) |
| Simulations too slow | [Performance](performance.md) |
| Custom physics | [NetSquid Integration](netsquid_integration.md) |
| Noise analysis | [Noise Models](noise_models.md) |

### Common Advanced Patterns

#### Parameter Sweep with Analysis
```python
from squidasm.run.stack.run import run
import numpy as np

fidelities = np.arange(0.7, 1.0, 0.05)
for fidelity in fidelities:
    config.links[0].cfg.fidelity = fidelity
    results = run(config=config, programs=programs, num_times=100)
    analyze_results(fidelity, results)
```

#### Custom Logging
```python
import logging
logging.getLogger("squidasm").setLevel(logging.DEBUG)
```

#### State Inspection (NetSquid)
```python
from netsquid.qubits import qubitapi as qapi
dm = qapi.reduced_dm(qubit)  # Get density matrix
```

## Prerequisites

Before diving into advanced topics, ensure you understand:

- [Tutorial 1: Basics](../tutorials/1_basics.md) - Program structure
- [Tutorial 2: NetQASM](../tutorials/2_netqasm.md) - Instruction flow
- [Tutorial 4: Network Configuration](../tutorials/4_network_configuration.md) - Configuration system

## See Also

- [API Reference](../api/index.md) - Detailed API documentation
- [Architecture](../architecture/overview.md) - System design
- [Tutorials](../tutorials/index.md) - Step-by-step guides
