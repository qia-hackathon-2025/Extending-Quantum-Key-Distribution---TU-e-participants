# Tutorial 6: Link Layer Operations

This tutorial explores direct link layer operations for EPR pair generation, based on `squidasm/examples/advanced/link_layer/`.

## Overview

The **link layer** provides the fundamental service of creating entanglement between nodes. Understanding link layer operations is essential for:
- High-throughput protocols
- Custom EPR generation patterns
- Performance optimization

## EPR Generation Modes

SquidASM supports two main modes:

| Mode | Method | Returns | Best For |
|------|--------|---------|----------|
| **Create-Keep** | `create_keep()` / `recv_keep()` | Qubit handles | Processing qubits locally |
| **Create-Measure** | `create_measure()` / `recv_measure()` | Measurement results | Direct measurement protocols |

## Create-Measure Pattern

The `create_measure` pattern is optimal when you only need measurement outcomes, not qubit manipulation.

### Example: Direct Measurement Protocol

```python
from typing import Any, Dict, Generator
from pydynaa import EventExpression
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta


class ClientProgram(Program):
    PEER = "server"

    def __init__(self, basis: str, num_pairs: int):
        self._basis = basis
        self._num_pairs = num_pairs

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="client_program",
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=1,  # Only need 1 qubit at a time
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]

        # Request multiple EPR pairs with immediate measurement
        results = epr_socket.create_measure(number=self._num_pairs)

        yield from conn.flush()

        # Extract measurement outcomes
        outcomes = [int(r.measurement_outcome) for r in results]

        return outcomes
```

### Server Side

```python
class ServerProgram(Program):
    PEER = "client"

    def __init__(self, basis: str, num_pairs: int):
        self._basis = basis
        self._num_pairs = num_pairs

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="server_program",
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=1,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]

        # Receive EPR pairs with immediate measurement
        results = epr_socket.recv_measure(number=self._num_pairs)

        yield from conn.flush()

        outcomes = [int(r.measurement_outcome) for r in results]

        return outcomes
```

### Running and Verifying

```python
import os
from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager


if __name__ == "__main__":
    LogManager.set_log_level("WARNING")

    cfg = StackNetworkConfig.from_file(
        os.path.join(os.path.dirname(__file__), "config.yaml")
    )

    num_pairs = 10

    client_program = ClientProgram(basis="Z", num_pairs=num_pairs)
    server_program = ServerProgram(basis="Z", num_pairs=num_pairs)

    client_results, server_results = run(
        cfg, 
        {"client": client_program, "server": server_program}, 
        num_times=1
    )

    # Verify correlation
    for i, (client_result, server_result) in enumerate(
        zip(client_results, server_results)
    ):
        print(f"run {i}:")
        client_outcomes = [r for r in client_result]
        server_outcomes = [r for r in server_result]
        print(f"client: {client_outcomes}")
        print(f"server: {server_outcomes}")
        
        # Perfect correlations expected with perfect config
        assert client_outcomes == server_outcomes
```

### Expected Output

```
run 0:
client: [1, 0, 0, 1, 1, 0, 0, 1, 0, 1]
server: [1, 0, 0, 1, 1, 0, 0, 1, 0, 1]
```

## Create-Keep with Post-Routine

For more complex operations, use `create_keep` with sequential processing:

### Basis Selection Pattern

```python
class ClientProgram(Program):
    PEER = "server"

    def __init__(self, basis: str, num_pairs: int):
        self._basis = basis
        self._num_pairs = num_pairs

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="client_program",
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=1,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]

        # Create array for outcomes
        outcomes = conn.new_array(self._num_pairs)

        def post_create(conn, q, pair):
            """Process each qubit immediately after creation."""
            # Get array entry for this pair
            array_entry = outcomes.get_future_index(pair)
            
            # Apply basis rotation if needed
            if self._basis == "X":
                q.H()
            elif self._basis == "Y":
                q.K()  # K gate: Rz(-π/2)·H
            # Z basis: no rotation needed
            
            # Measure and store in array
            q.measure(array_entry)

        # Create EPR pairs sequentially
        epr_socket.create_keep(
            number=self._num_pairs,
            sequential=True,
            post_routine=post_create,
        )

        yield from conn.flush()

        return outcomes
```

### Server Side with Post-Routine

```python
class ServerProgram(Program):
    PEER = "client"

    def __init__(self, basis: str, num_pairs: int):
        self._basis = basis
        self._num_pairs = num_pairs

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="server_program",
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=1,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]

        outcomes = conn.new_array(self._num_pairs)

        def post_create(conn, q, pair):
            array_entry = outcomes.get_future_index(pair)
            if self._basis == "X":
                q.H()
            elif self._basis == "Y":
                q.K()
            q.measure(array_entry)

        # Receive EPR pairs
        epr_socket.recv_keep(
            number=self._num_pairs,
            sequential=True,
            post_routine=post_create,
        )

        yield from conn.flush()

        return outcomes
```

## Configuration

### Link Configuration

```yaml
qdevice_cfg: &qdevice_cfg
  num_qubits: 2
  num_comm_qubits: 2
  T1: 1.e+8
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

links:
  - stack1: client
    stack2: server
    typ: heralded
    cfg:
      length: 100
      p_loss_length: 0.2
      dark_count_probability: 0
      detector_efficiency: 1
      visibility: 1

clinks:
  - stack1: client
    stack2: server
    typ: default
    cfg:
      delay: 0.5
```

## Comparison: create_measure vs create_keep

### Performance

| Aspect | create_measure | create_keep + post_routine |
|--------|---------------|---------------------------|
| Qubit memory | Minimal | Minimal (sequential) |
| Flexibility | Z-basis only | Any basis |
| Code complexity | Simple | More complex |
| Best for | Raw correlation | Basis selection |

### When to Use Each

**Use `create_measure`:**
- Simple correlation checks
- Z-basis measurements only
- Maximum simplicity

**Use `create_keep` with `sequential=True`:**
- Custom measurement bases
- Operations before measurement
- NV or constrained hardware

## Basis Selection and Correlation

### Z-basis (default)

```python
# Both measure in Z-basis
client: basis="Z"
server: basis="Z"
# Result: Perfect correlation (same outcomes)
```

### X-basis

```python
# Both measure in X-basis
client: basis="X", apply H before measure
server: basis="X", apply H before measure
# Result: Perfect correlation
```

### Y-basis

```python
# Both measure in Y-basis
client: basis="Y", apply K before measure
server: basis="Y", apply K before measure
# Result: Perfect correlation
```

### Mixed Bases

```python
# Different bases
client: basis="Z"
server: basis="X"
# Result: No correlation (50/50 random)
```

## Advanced: EPR Result Structure

The `create_measure` result contains:

```python
class EPRMeasureResult:
    measurement_outcome: int  # 0 or 1
    generation_duration: float  # Time taken
    # ... other metadata
```

Accessing fields:

```python
results = epr_socket.create_measure(number=10)
yield from conn.flush()

for r in results:
    outcome = int(r.measurement_outcome)
    duration = r.generation_duration
    print(f"Outcome: {outcome}, Duration: {duration} ns")
```

## Throughput Optimization

### Batch Requests

```python
# Good: Request all pairs at once
results = epr_socket.create_measure(number=100)
yield from conn.flush()

# Bad: One at a time
for _ in range(100):
    result = epr_socket.create_measure(number=1)
    yield from conn.flush()  # Extra overhead per pair
```

### Minimize Flushes

```python
# Good: One flush for all operations
for i in range(10):
    q = epr_socket.create_keep()[0]
    q.H()
    q.measure()
yield from conn.flush()  # Single flush

# Bad: Flush per operation
for i in range(10):
    q = epr_socket.create_keep()[0]
    yield from conn.flush()  # Unnecessary
    q.H()
    q.measure()
    yield from conn.flush()  # Multiple flushes
```

## Error Handling

### Timeout Handling

```python
try:
    results = epr_socket.create_measure(number=10)
    yield from conn.flush()
except TimeoutError:
    print("EPR generation timed out")
    return {"error": "timeout"}
```

### Insufficient Qubits

```python
# Ensure config has enough qubits
@property
def meta(self) -> ProgramMeta:
    return ProgramMeta(
        name="program",
        max_qubits=10,  # Must match or exceed simultaneous qubits
        epr_sockets=["peer"],
        csockets=["peer"],
    )
```

## Exercise: QKD Key Generation

Build a simple QKD-style key generation:

```python
import random


class QKDClientProgram(Program):
    def __init__(self, num_bits: int):
        self.num_bits = num_bits
        # Pre-generate random bases
        self.bases = [random.choice(["Z", "X"]) for _ in range(num_bits)]
    
    def run(self, context: ProgramContext):
        conn = context.connection
        epr_socket = context.epr_sockets["server"]
        csocket = context.csockets["server"]
        
        outcomes = conn.new_array(self.num_bits)
        
        def post_create(conn, q, pair):
            # Apply basis rotation
            # Note: This is simplified; real implementation needs
            # conditional logic based on pre-selected basis
            array_entry = outcomes.get_future_index(pair)
            q.measure(array_entry)
        
        epr_socket.create_keep(
            number=self.num_bits,
            sequential=True,
            post_routine=post_create
        )
        
        yield from conn.flush()
        
        # Send bases for reconciliation
        csocket.send(",".join(self.bases))
        
        return {"outcomes": list(outcomes), "bases": self.bases}
```

## Next Steps

- [Fidelity Constraints](07_fidelity_constraints.md) - Quality requirements
- [Custom Subroutines](09_custom_subroutines.md) - Low-level optimization
- [Noise Models](../../advanced/noise_models.md) - Link noise effects

## See Also

- [EPR Sockets](../../foundations/epr_sockets.md) - Conceptual overview
- [NetQASM Integration](../../architecture/netqasm_integration.md) - Compilation flow
- [API: EPR Methods](../../api/sim_package.md) - Detailed API reference
