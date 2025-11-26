# Tutorial 10: Precompilation and Templates

This tutorial covers **precompilation** and **template-based subroutines** for optimized execution, based on `squidasm/examples/advanced/precompilation/example_bqc_5_4_precompiled.py`.

## Overview

Precompilation separates instruction compilation from execution, enabling:
- **Faster execution**: Compile once, run many times
- **Template parameters**: Late binding of values received at runtime
- **Optimized instruction sequences**: Apply transformations at compile time
- **Reduced latency**: Critical for time-sensitive protocols

## Standard vs Precompiled Execution

### Standard Execution

```
┌─────────────────────────────────────────────────────────┐
│                    Standard Execution                   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Python SDK  ──▶  Build Instructions  ──▶  Execute     │
│                        │                        │       │
│                   (happens at                   │       │
│                    runtime)                     │       │
│                        │                        │       │
│                        ▼                        ▼       │
│                   [Subroutine]  ──────▶  [Results]      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Precompiled Execution

```
┌─────────────────────────────────────────────────────────┐
│                  Precompiled Execution                   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Phase 1: Compile                                       │
│  ─────────────────                                      │
│  Python SDK  ──▶  conn.compile()  ──▶  [Subroutine]     │
│                                             │           │
│                                             │ (stored)  │
│  Phase 2: Execute                           ▼           │
│  ────────────────                           │           │
│  [Runtime value]  ──▶  instantiate()  ──▶  [Filled]     │
│                                             │           │
│                                             ▼           │
│                   commit_subroutine()  ──▶  [Results]   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Templates

Templates are placeholders for values determined at runtime:

```python
from netqasm.lang.operand import Template

# Create a template parameter
delta1_template = Template("delta1")

# Use in rotation (value filled in later)
qubit.rot_Z(n=delta1_template, d=4)
```

### Template Resolution

```python
# Receive actual value
delta1 = yield from csocket.recv_float()

# Convert float to rotation encoding
from netqasm.sdk.toolbox.state_prep import get_angle_spec_from_float
nds = get_angle_spec_from_float(delta1)
rot_num = nds[0][0] if nds else 0

# Instantiate template with actual value
subroutine.instantiate(
    app_id=conn.app_id,
    arguments={"delta1": rot_num}
)
```

## BQC with Precompilation

This example implements BQC Stage 5.4 with precompiled server operations.

### Protocol Overview

```
Client                                    Server
───────                                   ──────
1. Create EPR                             1. Receive EPR
2. Prepare state                          
3. Measure                                
4. Calculate delta1                       
5. Send delta1 ───────────────────────▶   
                                          2. [Precompiled] Rotate by delta1
                                          3. [Precompiled] Measure
```

### Client Program

The client operates normally (no precompilation needed):

```python
from __future__ import annotations

import math
from typing import Any, Dict, Generator

from pydynaa import EventExpression
from squidasm.sim.stack.csocket import ClassicalSocket
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta


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

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]
        csocket: ClassicalSocket = context.csockets[self.PEER]

        # Standard EPR and state preparation
        epr = epr_socket.create_keep()[0]
        epr.rot_Z(angle=self._theta1)
        epr.H()
        p1 = epr.measure(store_array=False)

        # Compile and execute
        subroutine = conn.compile()
        yield from conn.commit_subroutine(subroutine)
        p1 = int(p1)

        # Calculate measurement angle
        delta1 = self._alpha - self._theta1 + (p1 + self._r1) * math.pi

        # Send to server
        csocket.send_float(delta1)

        return {"p1": p1}
```

### Server Program with Precompilation

The server precompiles operations before receiving the angle:

```python
from netqasm.lang.operand import Template
from netqasm.sdk.toolbox.state_prep import get_angle_spec_from_float


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
        csocket: ClassicalSocket = context.csockets[self.PEER]

        # === Phase 1: Receive EPR ===
        epr = epr_socket.recv_keep()[0]
        
        # Compile EPR reception
        subroutine1 = conn.compile()
        yield from conn.commit_subroutine(subroutine1)

        # === Phase 2: Precompile operations with template ===
        # Create template for rotation angle
        delta1_template = Template("delta1")

        # Define operations using template
        epr.rot_Z(n=delta1_template, d=4)  # Rotation uses template
        epr.H()
        m2 = epr.measure(store_array=False)

        # Compile WITHOUT executing
        subroutine2 = conn.compile()

        # === Phase 3: Receive actual value and instantiate ===
        # Now wait for the actual value
        delta1 = yield from csocket.recv_float()

        # Convert float angle to rotation encoding
        nds = get_angle_spec_from_float(delta1)
        if len(nds) == 0:
            rot_num = 0
        else:
            assert len(nds) == 1
            rot_num, _ = nds[0]

        # Fill in template with actual value
        subroutine2.instantiate(
            app_id=conn.app_id,
            arguments={"delta1": rot_num}
        )

        # === Phase 4: Execute with filled template ===
        yield from conn.commit_subroutine(subroutine2)
        m2 = int(m2)

        return {"m2": m2}
```

## Key Concepts

### `conn.compile()`

Compiles pending operations into a subroutine without executing:

```python
# Queue some operations
qubit.H()
qubit.X()

# Compile into subroutine
subroutine = conn.compile()

# Operations are NOT executed yet
```

### `conn.commit_subroutine()`

Executes a compiled subroutine:

```python
yield from conn.commit_subroutine(subroutine)
# Now operations are executed
```

### `subroutine.instantiate()`

Fills template parameters with actual values:

```python
subroutine.instantiate(
    app_id=conn.app_id,
    arguments={"param_name": value}
)
```

### Rotation Encoding

Rotations are encoded as: angle = n × π / 2^d

```python
from netqasm.sdk.toolbox.state_prep import get_angle_spec_from_float

# Convert float angle to (n, d) encoding
angle = math.pi / 4
nds = get_angle_spec_from_float(angle)
# nds = [(1, 2)]  # 1 × π / 2² = π/4

# Use in instantiation
rot_num = nds[0][0]  # n value
```

## Use Cases

### 1. Latency-Critical Communication

When waiting for classical communication, precompile next operations:

```python
# Precompile while waiting
subroutine = conn.compile()  # Fast

# Blocking receive (slow network)
value = yield from csocket.recv_int()

# Instantiate and execute (fast)
subroutine.instantiate(app_id=conn.app_id, arguments={"val": value})
yield from conn.commit_subroutine(subroutine)
```

### 2. Repeated Protocols

For protocols executed many times with same structure:

```python
class RepeatedProtocol(Program):
    def __init__(self, num_rounds: int):
        self._num_rounds = num_rounds
        self._subroutine = None  # Cache compiled subroutine

    def run(self, context):
        conn = context.connection
        
        # Compile once
        if self._subroutine is None:
            # Define operations with templates
            angle_template = Template("angle")
            qubit = Qubit(conn)
            qubit.rot_Z(n=angle_template, d=4)
            qubit.measure()
            self._subroutine = conn.compile()
        
        results = []
        for i in range(self._num_rounds):
            # Get angle for this round
            angle = self.get_angle(i)
            nds = get_angle_spec_from_float(angle)
            rot_num = nds[0][0] if nds else 0
            
            # Reuse compiled subroutine
            subrt_copy = self._subroutine.copy()
            subrt_copy.instantiate(
                app_id=conn.app_id,
                arguments={"angle": rot_num}
            )
            yield from conn.commit_subroutine(subrt_copy)
            results.append(...)
        
        return {"results": results}
```

### 3. Conditional Compilation

Compile different paths and choose at runtime:

```python
def run(self, context):
    conn = context.connection
    qubit = context.epr_sockets["peer"].recv_keep()[0]
    
    # Precompile both paths
    # Path A: Measure in X
    qubit_copy = qubit  # Note: real implementation needs proper handling
    qubit_copy.H()
    qubit_copy.measure()
    subroutine_x = conn.compile()
    
    # Path B: Measure in Z
    qubit.measure()
    subroutine_z = conn.compile()
    
    # Receive choice
    basis = yield from csocket.recv_int()
    
    # Execute chosen path
    if basis == 0:
        yield from conn.commit_subroutine(subroutine_x)
    else:
        yield from conn.commit_subroutine(subroutine_z)
```

## Running the Example

```python
import math

from squidasm.run.stack.config import (
    GenericQDeviceConfig,
    LinkConfig,
    StackConfig,
    StackNetworkConfig,
)
from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager


def get_distribution(
    cfg: StackNetworkConfig,
    num_times: int,
    alpha: float,
    theta1: float,
    r1: int = 0,
) -> None:
    client_program = ClientProgram(alpha=alpha, theta1=theta1, r1=r1)
    server_program = ServerProgram()

    _, server_results = run(
        cfg, 
        {"client": client_program, "server": server_program}, 
        num_times
    )

    m2s = [result["m2"] for result in server_results]
    num_zeros = len([m for m in m2s if m == 0])
    frac0 = round(num_zeros / num_times, 2)
    frac1 = 1 - frac0
    print(f"Distribution (0, 1) = ({frac0}, {frac1})")


if __name__ == "__main__":
    LogManager.set_log_level("WARNING")

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
    link = LinkConfig(stack1="client", stack2="server", typ="perfect")

    cfg = StackNetworkConfig(
        stacks=[client_stack, server_stack], 
        links=[link]
    )

    # Test different parameter combinations
    get_distribution(cfg, num_times=100, alpha=0, theta1=0)
    get_distribution(cfg, num_times=100, alpha=math.pi/2, theta1=0)
    get_distribution(cfg, num_times=100, alpha=0, theta1=math.pi/4)
```

## Comparison: Standard vs Precompiled

### Standard BQC (without precompilation)

```python
def run(self, context):
    # ... receive EPR ...
    
    # Wait for angle (blocking)
    delta1 = yield from csocket.recv_float()
    
    # Now build and execute operations
    epr.rot_Z(angle=delta1)  # Builds instructions
    epr.H()                   # Builds instructions
    m = epr.measure()         # Builds instructions
    yield from conn.flush()   # Compiles AND executes
```

### Precompiled BQC

```python
def run(self, context):
    # ... receive EPR, compile first subroutine ...
    
    # Build operations with template BEFORE receiving angle
    delta1_template = Template("delta1")
    epr.rot_Z(n=delta1_template, d=4)
    epr.H()
    m = epr.measure()
    subroutine = conn.compile()  # Compile NOW
    
    # Wait for angle
    delta1 = yield from csocket.recv_float()
    
    # Fill in value and execute (fast!)
    subroutine.instantiate(app_id=conn.app_id, arguments={"delta1": rot_num})
    yield from conn.commit_subroutine(subroutine)
```

### Timing Diagram

```
Standard:
─────────
recv_float() ─────▶ [WAIT] ─────▶ build_ops() ─────▶ compile() ─────▶ execute()
                      │              │                   │               │
                      └──────────────┴───────────────────┴───────────────┘
                              Total Latency = T_wait + T_build + T_compile + T_exec

Precompiled:
────────────
                                        build_ops() ─────▶ compile()
                                              │                │
recv_float() ─────▶ [WAIT] ─────────────────┴────────────────┘
                      │                                   instantiate() ─▶ execute()
                      │                                        │               │
                      └────────────────────────────────────────┴───────────────┘
                              Total Latency = T_wait + T_instantiate + T_exec
                              (T_build and T_compile happen in parallel with wait!)
```

## Best Practices

### 1. Identify Templates Early

Plan which values will be runtime-determined:

```python
# Good: Clear separation
delta_template = Template("delta")
gamma_template = Template("gamma")

qubit.rot_Z(n=delta_template, d=4)
qubit.rot_X(n=gamma_template, d=4)
```

### 2. Compile Before Blocking Operations

```python
# Compile operations for AFTER the receive
# ... define operations ...
subroutine = conn.compile()

# Now block on receive
value = yield from csocket.recv_float()

# Quick instantiate and execute
subroutine.instantiate(...)
```

### 3. Handle Missing Angle Specs

```python
nds = get_angle_spec_from_float(angle)
if len(nds) == 0:
    # Angle is 0 or 2π (no rotation needed)
    rot_num = 0
elif len(nds) == 1:
    rot_num, denom = nds[0]
else:
    # Multiple terms - may need special handling
    raise ValueError(f"Complex angle: {angle}")
```

### 4. Copy Subroutines for Reuse

```python
# Original subroutine
original = conn.compile()

# For each use, make a copy
for value in values:
    subrt = original.copy()
    subrt.instantiate(app_id=conn.app_id, arguments={"param": value})
    yield from conn.commit_subroutine(subrt)
```

## Exercises

### Exercise 1: Multi-Template Protocol

Create a protocol with two template parameters that receives two values and uses both in rotations.

### Exercise 2: Conditional Template

Precompile operations where one template controls a conditional branch.

### Exercise 3: Performance Comparison

Benchmark standard vs precompiled execution for a 10-round protocol.

## Summary

Precompilation offers significant benefits:

| Aspect | Standard | Precompiled |
|--------|----------|-------------|
| Latency | Higher | Lower |
| Complexity | Simple | More complex |
| Memory | Lower | Higher (caches subroutines) |
| Best for | Simple protocols | Latency-critical protocols |

## Next Steps

- [BQC Introduction](01_bqc_introduction.md) - Protocol theory
- [Custom Subroutines](09_custom_subroutines.md) - Hand-written NetQASM
- [Architecture Overview](../../architecture/overview.md) - System design

## See Also

- [Partial BQC](04_partial_bqc.md) - BQC building blocks
- [Link Layer](06_link_layer.md) - EPR operations
- [NetQASM Foundations](../../foundations/netqasm.md) - Instruction encoding
