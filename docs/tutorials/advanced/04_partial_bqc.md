# Tutorial 4: Partial BQC - Building Blocks

This tutorial breaks down Blind Quantum Computation into incremental steps, based on `squidasm/examples/advanced/partial_bqc/`. This approach helps understand each component before combining them.

## Overview

The partial BQC examples demonstrate three stages:
1. **5.2**: Local MBQC without blindness
2. **5.3**: Remote State Preparation only
3. **5.4**: Combined RSP + MBQC (partial blindness)

## Stage 1: Local MBQC (example_bqc_5_2.py)

### The Computation

First, let's implement the effective computation locally on the server, without any blindness:

$$EC = H \cdot R_z(\beta) \cdot H \cdot R_z(\alpha) |+\rangle$$

### Implementation

```python
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from squidasm.sim.stack.csocket import ClassicalSocket
from netqasm.sdk.qubit import Qubit


class ClientProgram(Program):
    """Client just sends computation parameters."""
    PEER = "server"

    def __init__(self, alpha: float, beta: float) -> None:
        self._alpha = alpha
        self._beta = beta

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="client_program",
            csockets=[self.PEER],
            epr_sockets=[self.PEER],  # Not used in this stage
            max_qubits=2,
        )

    def run(self, context: ProgramContext):
        csocket: ClassicalSocket = context.csockets[self.PEER]

        # Send alpha
        csocket.send_float(self._alpha)
        
        # Wait for intermediate result
        m1 = yield from csocket.recv_int()
        
        # Compute beta correction based on m1
        # In full MBQC, beta must be adjusted based on previous measurement
        beta = -self._beta if m1 == 1 else self._beta
        csocket.send_float(beta)

        return {}
```

### Server: Local MBQC

```python
class ServerProgram(Program):
    """Server performs the entire computation locally."""
    PEER = "client"

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="server_program",
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=2,
        )

    def run(self, context: ProgramContext):
        conn = context.connection
        csocket: ClassicalSocket = context.csockets[self.PEER]

        # Receive alpha
        alpha = yield from csocket.recv_float()

        # ========================================
        # Create local cluster state
        # ========================================
        electron = Qubit(conn)  # Qubit 1
        carbon = Qubit(conn)    # Qubit 2

        # Prepare |+⟩ states
        carbon.H()
        electron.H()
        
        # Entangle with CZ to create cluster
        electron.cphase(carbon)

        # ========================================
        # First measurement (encodes alpha)
        # ========================================
        electron.rot_Z(angle=alpha)
        electron.H()
        m1 = electron.measure(store_array=False)
        yield from conn.flush()
        m1 = int(m1)

        # Send m1 to client
        csocket.send_int(m1)

        # ========================================
        # Second measurement (encodes beta)
        # ========================================
        beta = yield from csocket.recv_float()

        carbon.rot_Z(angle=beta)
        carbon.H()
        m2 = carbon.measure(store_array=False)

        yield from conn.flush()
        m2 = int(m2)

        return {"m1": m1, "m2": m2}
```

### Configuration (Programmatic)

```python
from squidasm.run.stack.config import (
    GenericQDeviceConfig,
    LinkConfig,
    StackConfig,
    StackNetworkConfig,
)

client_stack = StackConfig(
    name="client",
    qdevice_typ="generic",
    qdevice_cfg=GenericQDeviceConfig.perfect_config(),
)
server_stack = StackConfig(
    name="server",
    qdevice_typ="generic",
    qdevice_cfg=GenericQDeviceConfig.perfect_config(),
)
link = LinkConfig(
    stack1="client",
    stack2="server",
    typ="perfect",  # Link not actually used in 5.2
)

cfg = StackNetworkConfig(stacks=[client_stack, server_stack], links=[link])
```

### What This Demonstrates

- MBQC structure: cluster state + measurements
- Classical feedback: beta depends on m1
- **Not blind**: Server knows alpha and beta

## Stage 2: Remote State Preparation (example_bqc_5_3.py)

### The Concept

Now we add Remote State Preparation: the client prepares a rotated state on the server using an EPR pair.

### Client: RSP

```python
class ClientProgram(Program):
    PEER = "server"

    def __init__(self, theta1: float) -> None:
        self._theta1 = theta1

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="client_program",
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=2,
        )

    def run(self, context: ProgramContext):
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]

        # Create EPR pair
        epr = epr_socket.create_keep()[0]

        # Measure in rotated basis
        # This remotely prepares Z^p1 * Rz(theta1) |+⟩ on server
        epr.rot_Z(angle=self._theta1)
        epr.H()
        p1 = epr.measure(store_array=False)
        
        yield from conn.flush()

        p1 = int(p1)
        return {"p1": p1}
```

### Server: Receive RSP

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

    def run(self, context: ProgramContext):
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]

        # Receive EPR pair
        # State is Z^p1 * Rz(theta1) |+⟩
        epr = epr_socket.recv_keep()[0]

        # Measure in X basis
        epr.H()
        m2 = epr.measure(store_array=False)

        yield from conn.flush()

        m2 = int(m2)
        return {"m2": m2}
```

### Distribution Analysis

```python
import math

def get_distribution(cfg, num_times: int, theta1: float) -> None:
    client_program = ClientProgram(theta1=theta1)
    server_program = ServerProgram()

    _, server_results = run(
        cfg, {"client": client_program, "server": server_program}, num_times
    )

    m2s = [result["m2"] for result in server_results]
    num_zeros = len([m for m in m2s if m == 0])
    frac0 = round(num_zeros / num_times, 2)
    frac1 = 1 - frac0
    print(f"theta1: {theta1} -> dist (0, 1) = ({frac0}, {frac1})")


# Test different angles
get_distribution(cfg, num_times=100, theta1=0)
# Output: theta1: 0 -> dist (0, 1) = (0.5, 0.5)

get_distribution(cfg, num_times=100, theta1=math.pi)
# Output: theta1: pi -> dist (0, 1) = (0.5, 0.5)
```

### What This Demonstrates

- RSP protocol: client prepares state on server
- EPR pair consumption for state preparation
- Distribution depends on theta1 (hidden from server)

## Stage 3: Combined RSP + MBQC (example_bqc_5_4.py)

### The Protocol

Now we combine RSP with part of the MBQC computation, achieving partial blindness.

### Client: RSP + Angle Computation

```python
import math


class ClientProgram(Program):
    PEER = "server"

    def __init__(self, alpha: float, theta1: float, r1: int):
        self._theta1 = theta1
        self._alpha = alpha
        self._r1 = r1

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="client_program",
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=2,
        )

    def run(self, context: ProgramContext):
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]
        csocket: ClassicalSocket = context.csockets[self.PEER]

        # ========================================
        # Remote State Preparation
        # ========================================
        epr = epr_socket.create_keep()[0]

        epr.rot_Z(angle=self._theta1)
        epr.H()
        p1 = epr.measure(store_array=False)

        yield from conn.flush()
        p1 = int(p1)

        # ========================================
        # Compute measurement angle with blindness
        # ========================================
        # delta1 encodes alpha but is hidden by theta1 and randomness
        delta1 = self._alpha - self._theta1 + (p1 + self._r1) * math.pi

        csocket.send_float(delta1)

        return {"p1": p1}
```

### Server: Receive and Measure

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

    def run(self, context: ProgramContext):
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]
        csocket: ClassicalSocket = context.csockets[self.PEER]

        # Receive EPR pair
        epr = epr_socket.recv_keep()[0]
        yield from conn.flush()

        # Receive measurement angle from client
        delta1 = yield from csocket.recv_float()

        # Measure in client-specified basis
        epr.rot_Z(angle=delta1)
        epr.H()
        m2 = epr.measure(store_array=False)

        yield from conn.flush()
        m2 = int(m2)

        return {"m2": m2}
```

### Analysis: Alpha Encoding

```python
PI = math.pi
PI_OVER_2 = math.pi / 2


def get_distribution(cfg, num_times: int, alpha: float, theta1: float, r1: int = 0):
    client_program = ClientProgram(alpha=alpha, theta1=theta1, r1=r1)
    server_program = ServerProgram()

    _, server_results = run(
        cfg, {"client": client_program, "server": server_program}, num_times
    )

    m2s = [result["m2"] for result in server_results]
    num_zeros = len([m for m in m2s if m == 0])
    frac0 = round(num_zeros / num_times, 2)
    frac1 = 1 - frac0
    print(f"dist (0, 1) = ({frac0}, {frac1})")


# alpha=0: expect all 0s
get_distribution(cfg, num_times=100, alpha=0, theta1=0)
# Output: dist (0, 1) = (1.0, 0.0)

# alpha=π: expect all 1s
get_distribution(cfg, num_times=100, alpha=PI, theta1=0)
# Output: dist (0, 1) = (0.0, 1.0)

# alpha=π/2: expect 50/50
get_distribution(cfg, num_times=100, alpha=PI_OVER_2, theta1=0)
# Output: dist (0, 1) = (0.5, 0.5)
```

### What This Demonstrates

- RSP provides first level of hiding
- Angle computation hides alpha from server
- Server only sees delta1, not alpha or theta1 separately

## Building Blocks Summary

### Progression

```
┌─────────────────────────────────────────────────────────────────┐
│ Stage 5.2: Local MBQC                                           │
│                                                                 │
│ Client → α,β → Server                                          │
│                                                                 │
│ Server: |+⟩|+⟩ → CZ → Meas(α) → Meas(β) → m1,m2               │
│                                                                 │
│ No blindness: Server knows α,β                                 │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ Stage 5.3: Remote State Preparation                             │
│                                                                 │
│ Client ←EPR→ Server                                            │
│ Client: Meas(θ₁) → p₁                                          │
│ Server: Has Z^p₁·Rz(θ₁)|+⟩                                     │
│                                                                 │
│ Partial blindness: Server doesn't know θ₁                      │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ Stage 5.4: RSP + Angle Encoding                                 │
│                                                                 │
│ Client ←EPR→ Server                                            │
│ Client: Meas(θ₁)→p₁, compute δ₁=α-θ₁+(p₁+r₁)π                 │
│ Server: Meas(δ₁) → m₂                                          │
│                                                                 │
│ Better blindness: Server sees δ₁, not α                        │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ Full BQC: Two RSP + Two Measurements                            │
│                                                                 │
│ (See Tutorial 02)                                               │
│                                                                 │
│ Full blindness: Server learns nothing about computation         │
└─────────────────────────────────────────────────────────────────┘
```

## Key Insights

### 1. Separating Concerns

Each stage isolates one aspect:
- **5.2**: MBQC structure
- **5.3**: RSP mechanism
- **5.4**: Angle hiding

### 2. The Hiding Formula

```python
delta = alpha - theta + (p + r) * pi
```

- `alpha`: What we want to compute (hidden)
- `theta`: Random offset (hidden from server)
- `p`: RSP measurement outcome (known to both, random)
- `r`: Extra randomness (hidden from server)

The server only sees `delta`, which is uniformly random.

### 3. Classical Correction

The `(-1)^(m1 + r1) * beta` term in full BQC:
- Depends on previous measurement outcome
- Implements MBQC's adaptive measurements
- Hidden by the same technique

## Running the Examples

```bash
cd squidasm/examples/advanced/partial_bqc

# Run stage 5.2
python example_bqc_5_2.py

# Run stage 5.3
python example_bqc_5_3.py

# Run stage 5.4
python example_bqc_5_4.py
```

## Exercises

### Exercise 1: Verify Angle Hiding

Modify 5.4 to print `delta1` on both client and server. Verify that:
- Client computes the correct `delta1`
- Server receives the same `delta1`
- `delta1` reveals nothing about `alpha` alone

### Exercise 2: Add Random Hiding

In 5.4, set `theta1` to a random value. Verify that results are still correct but `delta1` is random.

### Exercise 3: Extend to Full BQC

Starting from 5.4, add:
- Second EPR pair and RSP
- CZ gate between qubits
- Second measurement round with feedback

## Next Steps

- [GHZ State Creation](05_ghz_states.md) - Multi-node entanglement
- [BQC Implementation](02_bqc_implementation.md) - Full BQC code
- [Precompilation](10_precompilation.md) - Optimize BQC execution

## See Also

- [BQC Introduction](01_bqc_introduction.md) - Theory background
- [BQC on NV Hardware](03_bqc_nv_hardware.md) - Hardware constraints
- [NetQASM Foundations](../../foundations/netqasm.md) - Programming model
