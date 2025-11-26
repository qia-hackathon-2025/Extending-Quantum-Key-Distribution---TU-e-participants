# Tutorial 7: Fidelity Constraints

This tutorial demonstrates using **fidelity constraints** for EPR pair generation, based on `squidasm/examples/advanced/fidelity_constraint/example_fidelity.py`.

## Overview

In real quantum networks, EPR pairs have imperfect fidelity due to:
- Channel noise
- Decoherence during storage
- Imperfect operations

**Fidelity constraints** allow applications to request EPR pairs meeting minimum quality requirements.

## The Problem

Without fidelity constraints:
- Application receives whatever EPR pairs are available
- Quality may vary significantly
- Protocol correctness may depend on fidelity

With fidelity constraints:
- Application specifies minimum acceptable fidelity
- Network layer retries until constraint is met
- Application guaranteed minimum quality

## Fidelity Constraint Parameters

The EPR socket supports these fidelity parameters:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `min_fidelity_all_at_end` | All pairs must have this fidelity when last pair arrives | None |
| `max_tries` | Maximum generation attempts | No limit |

### Understanding `min_fidelity_all_at_end`

When multiple EPR pairs are requested:
1. Early pairs may decohere while waiting for later pairs
2. `min_fidelity_all_at_end` ensures all pairs meet the threshold when the **last pair** is generated
3. This accounts for decoherence during multi-pair generation

## Implementation

### Client Program with Fidelity Constraint

```python
from __future__ import annotations
import math
from typing import Any, Dict, Generator

from pydynaa import EventExpression
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta


class ClientProgram(Program):
    PEER = "server"

    def __init__(
        self,
        alpha: float,
        beta: float,
        trap: bool,
        dummy: int,
        theta1: float,
        theta2: float,
        r1: int,
        r2: int,
    ):
        self._alpha = alpha
        self._beta = beta
        self._trap = trap
        self._dummy = dummy
        self._theta1 = theta1
        self._theta2 = theta2
        self._r1 = r1
        self._r2 = r2

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="client_program",
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=2,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]

        # Request EPR pairs with fidelity constraint
        eprs = epr_socket.create_keep(
            number=2,
            min_fidelity_all_at_end=70,  # 70% fidelity minimum
            max_tries=20,                 # Retry up to 20 times
        )

        m0 = eprs[0].measure()
        m1 = eprs[1].measure()

        yield from conn.flush()

        return {"m0": int(m0), "m1": int(m1)}
```

### Server Program

```python
class ServerProgram(Program):
    PEER = "client"

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="server_program",
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=2,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]

        # Must match client's fidelity constraint
        eprs = epr_socket.recv_keep(
            number=2,
            min_fidelity_all_at_end=70,
            max_tries=20,
        )

        m0 = eprs[0].measure()
        m1 = eprs[1].measure()

        yield from conn.flush()

        return {"m0": int(m0), "m1": int(m1)}
```

### Key Points

1. **Both sides must specify the same constraint** - Client and server must agree on fidelity requirements
2. **max_tries prevents infinite loops** - If quality can't be achieved, generation fails
3. **Fidelity is in percent** - 70 means 70%, not 0.70

## Configuration for Noisy Links

```yaml
qdevice_cfg: &qdevice_cfg
  num_qubits: 2
  num_comm_qubits: 2
  T1: 1.e+6            # Shorter coherence (1 ms instead of 100 ms)
  T2: 1.e+6
  init_time: 1.e+4
  single_qubit_gate_time: 1.e+3
  two_qubit_gate_time: 1.e+5
  measurement_time: 1.e+4

stacks:
  - name: client
    qdevice_typ: generic
    qdevice_cfg: 
      <<: *qdevice_cfg
  - name: server
    qdevice_typ: generic
    qdevice_cfg: 
      <<: *qdevice_cfg

links:
  - stack1: client
    stack2: server
    typ: heralded
    cfg:
      length: 100
      p_loss_length: 0.2
      dark_count_probability: 0.001  # Non-zero dark counts
      detector_efficiency: 0.9       # Imperfect detection
      visibility: 0.95               # Reduced visibility
```

## Running the Simulation

```python
import os
import math
import netsquid as ns
from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager


PI = math.pi
PI_OVER_2 = math.pi / 2


def run_app(
    cfg: StackNetworkConfig,
    num_times: int = 1,
    alpha: float = 0.0,
    beta: float = 0.0,
    theta1: float = 0.0,
    theta2: float = 0.0,
) -> None:
    client_program = ClientProgram(
        alpha=alpha,
        beta=beta,
        trap=False,
        dummy=-1,
        theta1=theta1,
        theta2=theta2,
        r1=0,
        r2=0,
    )
    server_program = ServerProgram()

    _, server_results = run(
        cfg, 
        {"client": client_program, "server": server_program}, 
        num_times=num_times
    )
    
    print(f"Completed {num_times} runs")
    for i, result in enumerate(server_results[:5]):
        print(f"  Run {i}: m0={result['m0']}, m1={result['m1']}")


if __name__ == "__main__":
    num_times = 1
    LogManager.set_log_level("WARNING")
    
    # Use density matrix formalism for accurate fidelity
    ns.set_qstate_formalism(ns.qubits.qformalism.QFormalism.DM)

    cfg_file = os.path.join(os.path.dirname(__file__), "config.yaml")
    cfg = StackNetworkConfig.from_file(cfg_file)

    run_app(cfg, num_times, alpha=PI_OVER_2, beta=PI_OVER_2)
```

## How Fidelity Constraints Work

### The Algorithm

```
┌─────────────────────────────────────────────────────────────────┐
│ EPR Generation with Fidelity Constraint                         │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ attempt = 0           │
              └───────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ Generate n EPR pairs  │◄─────────────────────┐
              └───────────────────────┘                       │
                          │                                   │
                          ▼                                   │
              ┌───────────────────────┐                       │
              │ Wait for all pairs    │                       │
              └───────────────────────┘                       │
                          │                                   │
                          ▼                                   │
              ┌───────────────────────┐                       │
              │ Check fidelity of     │                       │
              │ ALL pairs             │                       │
              └───────────────────────┘                       │
                          │                                   │
              ┌───────────┴───────────┐                       │
              │                       │                       │
              ▼                       ▼                       │
    ┌─────────────────┐     ┌─────────────────┐              │
    │ All ≥ threshold │     │ Any < threshold │              │
    └─────────────────┘     └─────────────────┘              │
              │                       │                       │
              │                       ▼                       │
              │             ┌─────────────────┐              │
              │             │ attempt += 1    │              │
              │             └─────────────────┘              │
              │                       │                       │
              │             ┌─────────┴─────────┐            │
              │             │                   │            │
              │             ▼                   ▼            │
              │   ┌─────────────────┐ ┌─────────────────┐   │
              │   │ attempt ≤ max   │ │ attempt > max   │   │
              │   └─────────────────┘ └─────────────────┘   │
              │             │                   │            │
              │             │                   ▼            │
              │             │         ┌─────────────────┐   │
              │             │         │ Raise Error     │   │
              │             │         └─────────────────┘   │
              │             │                               │
              │             └───────────────────────────────┘
              │
              ▼
    ┌─────────────────┐
    │ Return EPRs     │
    └─────────────────┘
```

### Fidelity Estimation

The network layer estimates fidelity based on:
1. **Time since generation** - Decoherence reduces fidelity
2. **Link noise model** - Initial fidelity from generation
3. **T1/T2 parameters** - Device coherence times

## Understanding Fidelity Decay

### Bell State Fidelity

For a Bell state $|\Phi^+\rangle$ undergoing dephasing:

$$F(t) = \frac{1}{2}\left(1 + e^{-t/T_2}\right)$$

After time $t$ with $T_2$ coherence:
- $t = 0$: $F = 1.0$ (perfect)
- $t = T_2$: $F \approx 0.68$
- $t = 2T_2$: $F \approx 0.57$

### Multi-Pair Scenario

When requesting multiple pairs:
```
Time
  │
  │  First pair generated ───────────────────────► First pair used
  │  F = F_init                                    F = F_final
  │      │                                             │
  │      ▼                                             │
  │  Waiting...                                        │
  │      │                                             │
  │      ▼                                             │
  │  Second pair generated ──────────────────────► Second pair used
  │  F = F_init                                    F = F_final
  │
  ▼
```

The first pair decoheres while waiting for the second!

## Practical Considerations

### Choosing Fidelity Thresholds

| Protocol | Typical Minimum Fidelity |
|----------|-------------------------|
| Entanglement verification | 50% (above classical) |
| Simple QKD | 70-80% |
| BQC | 80-90% |
| Fault-tolerant protocols | 90%+ |

### Trade-offs

```
Higher fidelity requirement:
  ✓ Better protocol performance
  ✗ More retries needed
  ✗ Higher latency
  ✗ Lower throughput

Lower fidelity requirement:
  ✓ Faster generation
  ✓ Higher throughput
  ✗ More errors in protocol
```

### Choosing max_tries

```python
# Conservative: many retries, guaranteed success
eprs = epr_socket.create_keep(
    number=2,
    min_fidelity_all_at_end=90,
    max_tries=100  # Many retries
)

# Aggressive: fewer retries, may fail
eprs = epr_socket.create_keep(
    number=2,
    min_fidelity_all_at_end=90,
    max_tries=5  # Few retries
)
```

## Example: Adaptive Fidelity Requirements

```python
class AdaptiveProgram(Program):
    """Adapt fidelity requirement based on protocol phase."""
    
    def run(self, context):
        conn = context.connection
        epr_socket = context.epr_sockets["peer"]
        
        # Phase 1: Initial exchange (lower quality OK)
        initial_eprs = epr_socket.create_keep(
            number=10,
            min_fidelity_all_at_end=60,
            max_tries=5
        )
        
        yield from conn.flush()
        
        # Process initial EPRs...
        
        # Phase 2: Critical operation (high quality needed)
        critical_eprs = epr_socket.create_keep(
            number=2,
            min_fidelity_all_at_end=90,
            max_tries=50
        )
        
        yield from conn.flush()
        
        # Use critical EPRs for important operation
        return {"phase1": len(initial_eprs), "phase2": len(critical_eprs)}
```

## Error Handling

### Handling Generation Failure

```python
def run(self, context):
    conn = context.connection
    epr_socket = context.epr_sockets["peer"]
    
    try:
        eprs = epr_socket.create_keep(
            number=2,
            min_fidelity_all_at_end=95,
            max_tries=10
        )
        yield from conn.flush()
        return {"success": True, "count": len(eprs)}
    except Exception as e:
        # Handle generation failure
        return {"success": False, "error": str(e)}
```

## Performance Impact

### Simulation Time vs Fidelity

| min_fidelity | Avg. Tries | Simulation Time |
|--------------|------------|-----------------|
| 50% | ~1 | Fast |
| 70% | ~2-3 | Medium |
| 90% | ~5-10 | Slow |
| 99% | ~50+ | Very slow |

*Values depend heavily on link configuration*

### Optimizing for Performance

```python
# Use NetsQuid's density matrix formalism for accurate fidelity
import netsquid as ns
ns.set_qstate_formalism(ns.qubits.qformalism.QFormalism.DM)

# Match fidelity requirements to actual needs
# Don't over-specify
```

## Exercises

### Exercise 1: Fidelity Sweep

Run simulations with different fidelity thresholds and plot:
- Success rate vs. fidelity threshold
- Average tries vs. fidelity threshold

### Exercise 2: Coherence Time Impact

Vary T2 in configuration and observe:
- How fidelity requirements affect throughput
- At what T2 does high-fidelity generation become impractical

### Exercise 3: Protocol Correctness

Implement a simple protocol (e.g., teleportation) and measure:
- Success rate vs. fidelity threshold
- Optimal fidelity for your specific protocol

## Next Steps

- [Single Node Operations](08_single_node.md) - Local operations
- [Custom Subroutines](09_custom_subroutines.md) - Low-level control
- [Noise Models](../../advanced/noise_models.md) - Understanding noise

## See Also

- [Link Layer Operations](06_link_layer.md) - EPR generation basics
- [Configuration](../../api/configuration.md) - Network setup
- [Performance](../../advanced/performance.md) - Optimization techniques
