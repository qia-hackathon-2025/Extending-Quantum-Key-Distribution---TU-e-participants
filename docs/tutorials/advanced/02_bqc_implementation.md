# Tutorial 2: BQC Implementation

This tutorial provides a complete implementation of the Blind Quantum Computation protocol in SquidASM, based on `squidasm/examples/advanced/bqc/example_bqc.py`.

## Prerequisites

- Understanding of [BQC theory](01_bqc_introduction.md)
- Familiarity with [SquidASM basics](../1_basics.md)
- Knowledge of [EPR sockets](../../foundations/epr_sockets.md)

## Implementation Overview

The BQC protocol requires two programs:

| Program | Role | Capabilities |
|---------|------|--------------|
| `ClientProgram` | Delegator | Limited quantum (RSP only), classical processing |
| `ServerProgram` | Executor | Full quantum operations |

## Client Program

### Class Structure

```python
from __future__ import annotations
import math
from typing import Any, Dict, Generator

from pydynaa import EventExpression
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from squidasm.sim.stack.csocket import ClassicalSocket


class ClientProgram(Program):
    PEER = "server"

    def __init__(
        self,
        alpha: float,      # Computation parameter
        beta: float,       # Computation parameter
        trap: bool,        # Is this a trap round?
        dummy: int,        # Which qubit is dummy (1 or 2) in trap
        theta1: float,     # Random hiding angle 1
        theta2: float,     # Random hiding angle 2
        r1: int,           # Random bit 1
        r2: int,           # Random bit 2
    ):
        self._alpha = alpha
        self._beta = beta
        self._trap = trap
        self._dummy = dummy
        self._theta1 = theta1
        self._theta2 = theta2
        self._r1 = r1
        self._r2 = r2
```

### Program Metadata

```python
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="client_program",
            csockets=[self.PEER],      # Need classical socket to server
            epr_sockets=[self.PEER],   # Need EPR socket to server
            max_qubits=2,              # Need 2 qubits for RSP
        )
```

### The Run Method

The client's `run` method implements Remote State Preparation:

```python
    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]
        csocket: ClassicalSocket = context.csockets[self.PEER]

        # ========================================
        # Remote State Preparation for qubit 2
        # ========================================
        epr1 = epr_socket.create_keep()[0]

        if self._trap and self._dummy == 2:
            # Trap round: prepare dummy state (just measure)
            p2 = epr1.measure(store_array=False)
        else:
            # Computation round: prepare rotated state
            epr1.rot_Z(angle=self._theta2)
            epr1.H()
            p2 = epr1.measure(store_array=False)

        # ========================================
        # Remote State Preparation for qubit 1
        # ========================================
        epr2 = epr_socket.create_keep()[0]

        if self._trap and self._dummy == 1:
            # Trap round: prepare dummy state
            p1 = epr2.measure(store_array=False)
        else:
            # Computation round: prepare rotated state
            epr2.rot_Z(angle=self._theta1)
            epr2.H()
            p1 = epr2.measure(store_array=False)

        yield from conn.flush()

        p1 = int(p1)
        p2 = int(p2)
```

### Computing Measurement Angles

The client computes the measurement angles, hiding the actual computation:

```python
        # ========================================
        # Compute and send first measurement angle
        # ========================================
        if self._trap and self._dummy == 2:
            # Trap: no computation encoding
            delta1 = -self._theta1 + (p1 + self._r1) * math.pi
        else:
            # Encode alpha in the angle
            delta1 = self._alpha - self._theta1 + (p1 + self._r1) * math.pi
        
        csocket.send_float(delta1)

        # ========================================
        # Receive m1, compute second angle
        # ========================================
        m1 = yield from csocket.recv_int()
        
        if self._trap and self._dummy == 1:
            delta2 = -self._theta2 + (p2 + self._r2) * math.pi
        else:
            # Encode beta, accounting for m1 outcome
            delta2 = (
                math.pow(-1, (m1 + self._r1)) * self._beta
                - self._theta2
                + (p2 + self._r2) * math.pi
            )
        
        csocket.send_float(delta2)

        return {"p1": p1, "p2": p2}
```

### Understanding the Angle Computation

The formula `delta1 = alpha - theta1 + (p1 + r1) * π` achieves:

1. **`alpha`**: Encodes the actual computation
2. **`-theta1`**: Compensates for the RSP rotation
3. **`(p1 + r1) * π`**: Corrects for measurement outcome and adds randomness

For `delta2`, the `(-1)^(m1 + r1) * beta` term implements the measurement-dependent correction required by MBQC.

## Server Program

### Class Structure

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
```

### The Run Method

The server receives EPR pairs and performs operations:

```python
    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]
        csocket: ClassicalSocket = context.csockets[self.PEER]

        # ========================================
        # Receive EPR pairs (in order: epr1, epr2)
        # ========================================
        epr1 = epr_socket.recv_keep()[0]
        epr2 = epr_socket.recv_keep()[0]
        
        # Create cluster state with CZ gate
        epr2.cphase(epr1)

        yield from conn.flush()
```

### Measurement Phase

```python
        # ========================================
        # First measurement round
        # ========================================
        delta1 = yield from csocket.recv_float()

        epr2.rot_Z(angle=delta1)
        epr2.H()
        m1 = epr2.measure(store_array=False)
        
        yield from conn.flush()
        m1 = int(m1)
        csocket.send_int(m1)

        # ========================================
        # Second measurement round
        # ========================================
        delta2 = yield from csocket.recv_float()

        epr1.rot_Z(angle=delta2)
        epr1.H()
        m2 = epr1.measure(store_array=False)
        
        yield from conn.flush()
        m2 = int(m2)

        return {"m1": m1, "m2": m2}
```

## Network Configuration

The configuration file `config.yaml`:

```yaml
qdevice_cfg: &qdevice_cfg
  num_qubits: 2
  num_comm_qubits: 2
  T1: 1.e+8          # Long coherence time
  T2: 1.e+8
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
  
link_cfg: &link_cfg
  length: 100
  p_loss_length: 0.2
  dark_count_probability: 0
  detector_efficiency: 1
  visibility: 1

links:
  - stack1: client
    stack2: server
    typ: heralded
    cfg:
      <<: *link_cfg

clinks:
  - stack1: client
    stack2: server
    typ: default
    cfg:
      delay: 0.5
```

### Configuration Notes

- **Heralded link**: Realistic EPR generation with physical model
- **Generic device**: Supports arbitrary rotations
- **Classical delay**: 0.5 ns latency

## Running Computation Rounds

```python
import os
from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager

PI = math.pi
PI_OVER_2 = math.pi / 2


def computation_round(
    cfg: StackNetworkConfig,
    num_times: int = 1,
    alpha: float = 0.0,
    beta: float = 0.0,
    theta1: float = 0.0,
    theta2: float = 0.0,
) -> None:
    """Run BQC computation rounds."""
    
    client_program = ClientProgram(
        alpha=alpha,
        beta=beta,
        trap=False,       # Not a trap round
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

    # Analyze results
    m2s = [result["m2"] for result in server_results]
    num_zeros = len([m for m in m2s if m == 0])
    frac0 = round(num_zeros / num_times, 2)
    frac1 = 1 - frac0
    print(f"dist (0, 1) = ({frac0}, {frac1})")
```

### Expected Results

```python
# Identity computation: always get 0
computation_round(cfg, num_times=100, alpha=0, beta=0)
# Output: dist (0, 1) = (1.0, 0.0)

# Bit flip: always get 1
computation_round(cfg, num_times=100, alpha=PI, beta=0)
# Output: dist (0, 1) = (0.0, 1.0)

# Hadamard: 50/50
computation_round(cfg, num_times=100, alpha=PI_OVER_2, beta=0)
# Output: dist (0, 1) = (0.5, 0.5)

# Full rotation: always get 1
computation_round(cfg, num_times=100, alpha=PI_OVER_2, beta=PI_OVER_2)
# Output: dist (0, 1) = (0.0, 1.0)
```

## Running Trap Rounds

Trap rounds verify server honesty:

```python
def trap_round(
    cfg: StackNetworkConfig,
    num_times: int = 1,
    alpha: float = 0.0,
    beta: float = 0.0,
    theta1: float = 0.0,
    theta2: float = 0.0,
    dummy: int = 1,      # Which qubit is the dummy
) -> None:
    """Run trap rounds to verify server honesty."""
    
    client_program = ClientProgram(
        alpha=alpha,
        beta=beta,
        trap=True,       # This is a trap round
        dummy=dummy,
        theta1=theta1,
        theta2=theta2,
        r1=0,
        r2=0,
    )
    server_program = ServerProgram()

    client_results, server_results = run(
        cfg, 
        {"client": client_program, "server": server_program}, 
        num_times=num_times
    )

    # Extract results
    p1s = [result["p1"] for result in client_results]
    p2s = [result["p2"] for result in client_results]
    m1s = [result["m1"] for result in server_results]
    m2s = [result["m2"] for result in server_results]

    # Check trap conditions
    if dummy == 1:
        # When qubit 1 is dummy, p1 should equal m2
        num_fails = len([(p, m) for (p, m) in zip(p1s, m2s) if p != m])
    else:
        # When qubit 2 is dummy, p2 should equal m1
        num_fails = len([(p, m) for (p, m) in zip(p2s, m1s) if p != m])

    frac_fail = round(num_fails / num_times, 2)
    print(f"fail rate: {frac_fail}")
```

### Trap Round Logic

In a trap round:
- The "dummy" qubit is measured directly without rotation
- If the server is honest, specific correlations must hold
- With perfect devices: fail rate = 0.0

## Complete Main Script

```python
if __name__ == "__main__":
    num_times = 100
    LogManager.set_log_level("WARNING")

    cfg_file = os.path.join(os.path.dirname(__file__), "config.yaml")
    cfg = StackNetworkConfig.from_file(cfg_file)

    # Run computation
    print("Computation round (α=π/2, β=π/2):")
    computation_round(cfg, num_times, alpha=PI_OVER_2, beta=PI_OVER_2)
    
    # Verify honesty
    print("\nTrap round (dummy=1):")
    trap_round(cfg, num_times, dummy=1)
    
    print("\nTrap round (dummy=2):")
    trap_round(cfg, num_times, dummy=2)
```

## Protocol Flow Diagram

```
Time
  │
  │  Client                          Server
  │    │                               │
  ▼    │  ┌──────────────────────────┐ │
  1    │──│ create_keep() EPR pair 1 │─│→ recv_keep()
       │  └──────────────────────────┘ │
       │                               │
  2    │  rot_Z(θ₂), H, measure → p₂  │  Has epr1
       │                               │
  3    │  ┌──────────────────────────┐ │
       │──│ create_keep() EPR pair 2 │─│→ recv_keep()
       │  └──────────────────────────┘ │
       │                               │
  4    │  rot_Z(θ₁), H, measure → p₁  │  Has epr2
       │                               │
       │  flush()                      │
       │                               │  cphase(epr1, epr2)
       │                               │  flush()
       │                               │
  5    │  Compute δ₁                   │
       │─────── send_float(δ₁) ───────→│
       │                               │  rot_Z(δ₁), H, measure → m₁
       │                               │  flush()
       │◄────── send_int(m₁) ─────────│
       │                               │
  6    │  Compute δ₂                   │
       │─────── send_float(δ₂) ───────→│
       │                               │  rot_Z(δ₂), H, measure → m₂
       │                               │  flush()
       │                               │
  7    │  Return {p1, p2}             │  Return {m1, m2}
       ▼                               ▼
```

## Key Implementation Points

### 1. Order of EPR Creation

```python
# Client creates first (initiator)
epr1 = epr_socket.create_keep()[0]
epr2 = epr_socket.create_keep()[0]

# Server receives in same order
epr1 = epr_socket.recv_keep()[0]
epr2 = epr_socket.recv_keep()[0]
```

### 2. Flush Timing

```python
# Flush after all quantum operations before classical comm
epr1.rot_Z(angle=theta)
epr1.H()
p = epr1.measure()
yield from conn.flush()  # Execute quantum ops

# Now safe to use measurement result
csocket.send_int(int(p))
```

### 3. Generator Pattern

```python
def run(self, context) -> Generator[EventExpression, None, Dict]:
    # Must yield from blocking operations
    m1 = yield from csocket.recv_int()
    yield from conn.flush()
    
    # Return results at end
    return {"result": int(m1)}
```

## Next Steps

- [BQC on NV Hardware](03_bqc_nv_hardware.md) - Adapt for constrained hardware
- [Partial BQC](04_partial_bqc.md) - Build up the protocol step by step
- [Debugging](../../advanced/debugging.md) - Troubleshoot implementations

## See Also

- [BQC Introduction](01_bqc_introduction.md) - Theory background
- [Classical Communication](../../foundations/classical_communication.md) - Socket details
- [EPR Sockets](../../foundations/epr_sockets.md) - Entanglement generation
