# Tutorial 3: BQC on NV Hardware

This tutorial demonstrates how to adapt the Blind Quantum Computation protocol for **NV center** hardware constraints, based on `squidasm/examples/advanced/bqc/example_bqc_nv.py`.

## Overview

NV (Nitrogen-Vacancy) centers in diamond are a leading physical platform for quantum networks. However, they have significant constraints compared to idealized quantum devices:

| Constraint | Impact |
|------------|--------|
| Sequential EPR generation | Can only create one EPR pair at a time |
| Limited qubit memory | Communication qubit used for entanglement |
| Measurement on electron only | Carbon qubits require SWAP operations |
| Gate set restrictions | Not all gates are native |

## The Challenge

In the generic BQC implementation, we write:

```python
# Generic implementation
epr1 = epr_socket.create_keep()[0]
# ... operations on epr1 ...
epr2 = epr_socket.create_keep()[0]
# ... operations on epr2 ...
```

On NV hardware, this doesn't work because:
1. Both EPR pairs use the same communication qubit
2. We can't hold multiple EPR qubits simultaneously in the simple case
3. Operations must complete before the next EPR generation

## Solution: Sequential EPR with Post-Routines

The key technique is using **`post_routine`** callbacks that execute immediately after each EPR pair is created:

```python
def post_create(connection, qubit, index):
    """Called after each EPR pair is created."""
    # Process qubit immediately while it's available
    # index tells us which pair this is (0, 1, 2, ...)
```

## NV-Adapted Client Program

### Modified Create Pattern

```python
from netqasm.sdk.connection import BaseNetQASMConnection
from netqasm.sdk.futures import Future, RegFuture
from netqasm.sdk.qubit import Qubit


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
        # Same as before
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
```

### The Post-Routine Pattern

```python
    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]
        csocket: ClassicalSocket = context.csockets[self.PEER]

        # Create array to store measurement outcomes
        outcomes = conn.new_array(length=2)

        # Define post-creation routine
        def post_create(_: BaseNetQASMConnection, q: Qubit, index: RegFuture):
            """
            Called immediately after each EPR pair is created.
            
            Args:
                _: Connection (not used in this case)
                q: The created qubit
                index: Which pair this is (0 or 1)
            """
            # Process qubit 0 (corresponds to theta2)
            with index.if_eq(0):
                if not (self._trap and self._dummy == 2):
                    q.rot_Z(angle=self._theta2)
                    q.H()

            # Process qubit 1 (corresponds to theta1)
            with index.if_eq(1):
                if not (self._trap and self._dummy == 1):
                    q.rot_Z(angle=self._theta1)
                    q.H()
            
            # Store measurement in outcomes array
            q.measure(future=outcomes.get_future_index(index))

        # Create both EPR pairs sequentially with post-processing
        epr_socket.create_keep(2, sequential=True, post_routine=post_create)

        yield from conn.flush()
```

### Key Differences from Generic Version

| Aspect | Generic | NV |
|--------|---------|-----|
| EPR creation | Two separate `create_keep()[0]` calls | Single `create_keep(2, sequential=True)` |
| Qubit processing | After creation | In `post_routine` callback |
| Measurement storage | Individual `Future` objects | Shared `Array` |
| Conditional logic | Python `if` statements | `index.if_eq()` context managers |

### Extracting Results

```python
        # Extract results from array
        p1 = int(outcomes.get_future_index(1))  # Second qubit
        p2 = int(outcomes.get_future_index(0))  # First qubit

        # Rest is same as generic version
        if self._trap and self._dummy == 2:
            delta1 = -self._theta1 + (p1 + self._r1) * math.pi
        else:
            delta1 = self._alpha - self._theta1 + (p1 + self._r1) * math.pi
        csocket.send_float(delta1)

        m1 = yield from csocket.recv_int()
        if self._trap and self._dummy == 1:
            delta2 = -self._theta2 + (p2 + self._r2) * math.pi
        else:
            delta2 = (
                math.pow(-1, (m1 + self._r1)) * self._beta
                - self._theta2
                + (p2 + self._r2) * math.pi
            )
        csocket.send_float(delta2)

        return {"p1": p1, "p2": p2}
```

## NV-Adapted Server Program

The server is simpler because it doesn't need complex conditional logic in the post-routine:

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
        csocket: ClassicalSocket = context.csockets[self.PEER]

        # Receive both EPR pairs
        epr1, epr2 = epr_socket.recv_keep(2)
        
        # Create cluster state
        epr2.cphase(epr1)

        yield from conn.flush()

        # Rest is same as generic version
        delta1 = yield from csocket.recv_float()

        epr2.rot_Z(angle=delta1)
        epr2.H()
        m1 = epr2.measure(store_array=False)
        yield from conn.flush()

        m1 = int(m1)
        csocket.send_int(m1)

        delta2 = yield from csocket.recv_float()

        epr1.rot_Z(angle=delta2)
        epr1.H()
        m2 = epr1.measure(store_array=False)
        yield from conn.flush()

        m2 = int(m2)
        return {"m1": m1, "m2": m2}
```

## NV Configuration

The NV configuration file `config_nv.yaml`:

```yaml
qdevice_cfg: &qdevice_cfg
  num_qubits: 2         # 1 electron + 1 carbon
  num_comm_qubits: 1    # Only electron communicates
  T1: 1.e+8
  T2: 1.e+8
  # NV-specific timing
  init_time: 1.e+4
  single_qubit_gate_time: 1.e+3
  two_qubit_gate_time: 1.e+5
  measurement_time: 1.e+4

stacks:
  - name: client
    qdevice_typ: nv      # NV device type
    qdevice_cfg: 
      <<: *qdevice_cfg
  - name: server
    qdevice_typ: nv      # NV device type
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

### Using Perfect NV Config Programmatically

```python
import netsquid as ns
from squidasm.run.stack.config import NVQDeviceConfig, StackNetworkConfig

if __name__ == "__main__":
    num_times = 100
    LogManager.set_log_level("WARNING")

    # Use density matrix formalism for NV simulation
    ns.set_qstate_formalism(ns.qubits.qformalism.QFormalism.DM)

    cfg_file = os.path.join(os.path.dirname(__file__), "config_nv.yaml")
    cfg = StackNetworkConfig.from_file(cfg_file)
    
    # Override with perfect NV configuration
    cfg.stacks[0].qdevice_cfg = NVQDeviceConfig.perfect_config()
    cfg.stacks[1].qdevice_cfg = NVQDeviceConfig.perfect_config()

    trap_round(cfg=cfg, num_times=num_times, dummy=2)
```

## Understanding `post_routine`

### Function Signature

```python
def post_routine(
    connection: BaseNetQASMConnection,
    qubit: Qubit,
    index: RegFuture
):
    """
    Callback executed after each EPR pair creation.
    
    Args:
        connection: The NetQASM connection
        qubit: The created EPR qubit
        index: Future containing the pair index (0, 1, 2, ...)
    """
```

### Conditional Logic with `if_eq`

Since `index` is a `RegFuture` (not a Python int), we can't use normal Python conditionals:

```python
# WRONG - index is a Future, not an int
if index == 0:
    qubit.H()

# CORRECT - use context manager
with index.if_eq(0):
    qubit.H()
```

The `if_eq` context manager compiles to NetQASM conditional instructions.

### Storing Results in Arrays

```python
# Create array for outcomes
outcomes = conn.new_array(length=num_pairs)

def post_routine(conn, q, index):
    # Get future index into array
    array_slot = outcomes.get_future_index(index)
    # Store measurement result
    q.measure(future=array_slot)
```

## Sequential vs Parallel EPR

### Sequential Mode (NV Required)

```python
# EPR pairs created one at a time
# Each pair processed before next begins
epr_socket.create_keep(
    number=2,
    sequential=True,      # One at a time
    post_routine=process  # Process immediately
)
```

### Parallel Mode (Generic Devices)

```python
# Multiple EPR pairs requested simultaneously
# All returned together (if enough qubits)
qubits = epr_socket.create_keep(number=2)  # Returns list
q1, q2 = qubits  # Unpack
```

## Timing Considerations

### NV Timing Diagram

```
Time
  │
  │  create_keep(2, sequential=True, post_routine=...)
  │
  ▼  ┌─────────────────────────────────────────────┐
  0  │ EPR Generation #1                           │
     │ (Uses electron qubit)                       │
     └─────────────────────────────────────────────┘
     │
     ▼ post_routine(conn, q1, index=0)
     │  - rot_Z, H, measure
     │  - Qubit freed
     │
     ┌─────────────────────────────────────────────┐
     │ EPR Generation #2                           │
     │ (Electron available again)                  │
     └─────────────────────────────────────────────┘
     │
     ▼ post_routine(conn, q2, index=1)
        - rot_Z, H, measure
        - Qubit freed
```

### Generic Timing Diagram

```
Time
  │
  │  create_keep()[0]
  │
  ▼  ┌─────────────────────────────────────────────┐
  0  │ EPR Generation #1                           │
     └─────────────────────────────────────────────┘
     │
     ▼ Qubit available
     │
     │  create_keep()[0]
     │
     ▼  ┌─────────────────────────────────────────────┐
     │  EPR Generation #2                           │
     └─────────────────────────────────────────────┘
     │
     ▼ Both qubits available
        - Can operate on both
        - Then measure
```

## Performance Comparison

| Metric | Generic | NV |
|--------|---------|-----|
| EPR per run | 2 parallel | 2 sequential |
| Memory qubits | 2+ | 1 electron + carbons |
| Gate flexibility | All gates | Restricted set |
| Code complexity | Simpler | Post-routines needed |
| Physical realism | Low | High |

## Best Practices for NV Programming

### 1. Always Use Sequential for Multiple EPR

```python
# Good: Sequential with post_routine
epr_socket.create_keep(n, sequential=True, post_routine=process)

# Bad: Trying to hold multiple communication qubits
q1 = epr_socket.create_keep()[0]
q2 = epr_socket.create_keep()[0]  # Overwrites q1 on NV!
```

### 2. Process Immediately in Post-Routine

```python
def post_routine(conn, q, idx):
    # Do all operations on q here
    q.rot_Z(angle=theta)
    q.H()
    q.measure(future=results.get_future_index(idx))
    # q will be freed after this
```

### 3. Use Arrays for Multiple Results

```python
# Pre-allocate array
results = conn.new_array(length=num_pairs)

# Store in post_routine
def post_routine(conn, q, idx):
    q.measure(future=results.get_future_index(idx))
```

### 4. Use Perfect Config for Testing

```python
from squidasm.run.stack.config import NVQDeviceConfig

# No noise, perfect operations
cfg.stacks[0].qdevice_cfg = NVQDeviceConfig.perfect_config()
```

## Common Errors

### Error: Communication Qubit Conflict

```
RuntimeError: Communication qubit already in use
```

**Cause**: Trying to create second EPR before processing first.

**Solution**: Use `sequential=True` with `post_routine`.

### Error: Invalid Gate on NV

```
RuntimeError: Gate not supported on NV device
```

**Cause**: Using non-native gates.

**Solution**: Check NV gate set, use decomposition if needed.

## Next Steps

- [Partial BQC](04_partial_bqc.md) - Build up BQC from components
- [Fidelity Constraints](07_fidelity_constraints.md) - EPR quality requirements
- [Noise Models](../../advanced/noise_models.md) - Understanding NV noise

## See Also

- [BQC Implementation](02_bqc_implementation.md) - Generic version
- [API: NVQDeviceConfig](../../api/run_package.md) - NV configuration
- [NetQASM Integration](../../architecture/netqasm_integration.md) - Instruction compilation
