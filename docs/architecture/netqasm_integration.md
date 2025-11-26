# NetQASM Integration

This document describes how NetQASM, the quantum network instruction set, integrates with SquidASM.

## What is NetQASM?

**NetQASM** (Network Quantum Assembly) is an instruction set architecture for quantum network applications. It provides:

- A low-level language for quantum operations
- An SDK for programmatic construction
- A standard interface between applications and quantum hardware

## NetQASM in SquidASM

SquidASM uses NetQASM as the interface between high-level Python programs and the NetSquid simulator.

```
┌──────────────────────────────────────────────────────────────┐
│                     User Python Code                          │
│  q = Qubit(connection)                                       │
│  q.H()                                                       │
│  result = q.measure()                                        │
└─────────────────────────────┬────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                      NetQASM SDK                              │
│  - Qubit class, EPRSocket class                              │
│  - Builds instruction sequences                              │
│  - Manages Future objects                                    │
└─────────────────────────────┬────────────────────────────────┘
                              │ compile()
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                   NetQASM Subroutine                          │
│  init Q0                                                     │
│  h Q0                                                        │
│  meas Q0 M0                                                  │
└─────────────────────────────┬────────────────────────────────┘
                              │ flush()
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                  SquidASM Executor                            │
│  - Parses NetQASM instructions                               │
│  - Converts to NetSquid operations                           │
│  - Returns results to SDK                                    │
└──────────────────────────────────────────────────────────────┘
```

## The Instruction Queue Model

### How It Works

NetQASM uses a **deferred execution model**. Operations are queued, not executed immediately.

```python
# These lines DON'T execute quantum operations immediately
q = Qubit(connection)    # Queue: [init Q0]
q.H()                    # Queue: [init Q0, h Q0]
result = q.measure()     # Queue: [init Q0, h Q0, meas Q0 M0]

# This line EXECUTES all queued operations
connection.flush()       # Actually runs init, h, meas on QNPU

# Now 'result' has an actual value
print(int(result))       # Works after flush
```

### Why Deferred Execution?

1. **Optimization**: Batch multiple operations for efficiency
2. **Network coordination**: Synchronize operations across nodes
3. **Hardware mapping**: Real quantum hardware works this way

### Future Objects

Before `flush()`, measurement results are `Future` objects:

```python
q = Qubit(connection)
q.H()
result = q.measure()

# Before flush: result is a Future (placeholder)
print(type(result))  # <class 'netqasm.sdk.future.Future'>
# print(int(result)) # Would cause error!

connection.flush()

# After flush: result has a value
print(type(result))  # Still Future, but now has value
print(int(result))   # Works: prints 0 or 1
```

## NetQASM Instruction Set

### Gate Instructions

| Instruction | Description | NetQASM | Python SDK |
|-------------|-------------|---------|------------|
| `init` | Initialize qubit | `init Q0` | `Qubit(conn)` |
| `h` | Hadamard | `h Q0` | `q.H()` |
| `x` | Pauli-X | `x Q0` | `q.X()` |
| `y` | Pauli-Y | `y Q0` | `q.Y()` |
| `z` | Pauli-Z | `z Q0` | `q.Z()` |
| `t` | T gate | `t Q0` | `q.T()` |
| `s` | S gate | `s Q0` | `q.S()` |
| `rot_x` | X rotation | `rot_x Q0 n d` | `q.rot_X(n, d)` |
| `rot_y` | Y rotation | `rot_y Q0 n d` | `q.rot_Y(n, d)` |
| `rot_z` | Z rotation | `rot_z Q0 n d` | `q.rot_Z(n, d)` |
| `cnot` | CNOT | `cnot Q0 Q1` | `q0.cnot(q1)` |
| `cz` | CZ | `cz Q0 Q1` | `q0.cphase(q1)` |
| `meas` | Measure | `meas Q0 M0` | `q.measure()` |
| `qfree` | Free qubit | `qfree Q0` | Automatic after measure |

### Rotation Angle Encoding

Rotation angles use integer encoding: $\theta = n \times \pi / 2^d$

```python
# Rotate by π/4 around X axis
q.rot_X(n=1, d=2)  # 1 * π / 2^2 = π/4

# Rotate by π/2 around Z axis
q.rot_Z(n=1, d=1)  # 1 * π / 2^1 = π/2

# Rotate by 3π/8 around Y axis
q.rot_Y(n=3, d=3)  # 3 * π / 2^3 = 3π/8
```

### EPR Instructions

| Instruction | Description | Python SDK |
|-------------|-------------|------------|
| `create_epr` | Create EPR pair | `epr_socket.create_keep()` |
| `recv_epr` | Receive EPR pair | `epr_socket.recv_keep()` |

### Control Flow Instructions

| Instruction | Description |
|-------------|-------------|
| `jmp` | Unconditional jump |
| `beq` | Branch if equal |
| `bne` | Branch if not equal |
| `blt` | Branch if less than |

## The Connection Object

### BaseNetQASMConnection

The connection manages the instruction queue and compilation:

```python
from netqasm.sdk.connection import BaseNetQASMConnection

class Connection(BaseNetQASMConnection):
    """Manages NetQASM instruction queue."""
    
    def __init__(self, name: str):
        self._builder = SubroutineBuilder()
        self._pending_futures: List[Future] = []
    
    def compile(self) -> Subroutine:
        """Compile queued instructions into a subroutine."""
        return self._builder.build()
    
    def flush(self):
        """Execute queued operations."""
        subroutine = self.compile()
        yield from self.commit_subroutine(subroutine)
        self._resolve_futures()
```

### Inspecting Compiled Code

```python
def run(self, context: ProgramContext):
    connection = context.connection
    
    q = Qubit(connection)
    q.H()
    q.X()
    result = q.measure()
    
    # Compile without executing
    subroutine = connection.compile()
    
    # Print the NetQASM code
    print(f"NetQASM version: {subroutine.version}")
    print(f"App ID: {subroutine.app_id}")
    print("\nInstructions:")
    for i, instr in enumerate(subroutine.instructions):
        print(f"  {i:3d}: {instr}")
    
    # Now execute
    yield from connection.commit_subroutine(subroutine)
    
    return {"result": int(result)}
```

Output:
```
NetQASM version: (0, 10)
App ID: 0

Instructions:
    0: set Q0 0
    1: init Q0
    2: h Q0
    3: x Q0
    4: meas Q0 M0
    5: qfree Q0
```

## Control Flow with NetQASM

### Python Control Flow Doesn't Work

```python
# This does NOT work as expected!
q = Qubit(connection)
q.H()
result = q.measure()

# This if-statement runs in Python BEFORE flush
# 'result' is a Future, not 0 or 1
if result == 1:  # ERROR: Can't evaluate Future
    q2.X()
```

### Using NetQASM Control Flow

```python
# Correct: Use SDK methods for conditional operations

def run(self, context: ProgramContext):
    connection = context.connection
    
    q1 = Qubit(connection)
    q2 = Qubit(connection)
    
    q1.H()
    result = q1.measure()
    
    # Define what to do if result == 1
    def apply_x():
        q2.X()
    
    # This creates NetQASM branch instructions
    connection.if_eq(result, 1, apply_x)
    
    m2 = q2.measure()
    connection.flush()
    
    return {"m1": int(result), "m2": int(m2)}
```

### Available Control Flow Methods

```python
# If result equals value
connection.if_eq(future, value, body_fn)

# If result not equals value
connection.if_ne(future, value, body_fn)

# Loop constructs
connection.loop(count, body_fn)
```

## SquidASM Executor

### NetSquidExecutor

The executor converts NetQASM to NetSquid operations:

```python
class NetSquidExecutor:
    """Executes NetQASM on NetSquid simulator."""
    
    def execute_instruction(self, instr, handler):
        opcode = instr.opcode
        
        if opcode == OpCode.INIT:
            return self._execute_init(instr, handler)
        elif opcode == OpCode.H:
            return self._execute_h(instr, handler)
        elif opcode == OpCode.MEAS:
            return self._execute_meas(instr, handler)
        # ... more opcodes
    
    def _execute_h(self, instr, handler):
        """Execute Hadamard gate."""
        qubit_id = handler.get_qubit(instr.operands[0])
        
        # Create NetSquid gate program
        program = QuantumProgram()
        program.apply(INSTR_H, qubit_ids=[qubit_id])
        
        # Execute on quantum processor
        self.processor.execute_program(program)
        
        # Wait for completion (advances simulation time)
        yield self.await_program()
```

### Instruction Mapping

| NetQASM | NetSquid Operation |
|---------|-------------------|
| `h Q0` | `INSTR_H` on position 0 |
| `x Q0` | `INSTR_X` on position 0 |
| `cnot Q0 Q1` | `INSTR_CNOT` on positions 0, 1 |
| `meas Q0 M0` | `INSTR_MEASURE` on position 0 |

### Timing

Each instruction takes simulation time based on device configuration:

```python
# From GenericQDeviceConfig
single_qubit_gate_time: 50    # 50 ns per single-qubit gate
two_qubit_gate_time: 200      # 200 ns per two-qubit gate
measure_time: 100             # 100 ns per measurement
init_time: 100                # 100 ns per initialization
```

## SubroutineHandler

Manages execution state during subroutine execution:

```python
class SubroutineHandler:
    """Tracks execution state of a subroutine."""
    
    def __init__(self, subroutine: Subroutine):
        self.subroutine = subroutine
        self.pc = 0  # Program counter
        self.registers = {}  # Classical registers
        self.mregisters = {}  # Measurement registers
        self.arrays = {}  # Array storage
    
    def current_instruction(self) -> Instruction:
        return self.subroutine.instructions[self.pc]
    
    def advance(self):
        self.pc += 1
    
    def jump(self, target: int):
        self.pc = target
    
    def finished(self) -> bool:
        return self.pc >= len(self.subroutine.instructions)
```

## Limitations

### Unsupported Features

Some NetQASM features are not fully supported in SquidASM:

| Feature | Status | Notes |
|---------|--------|-------|
| Measurement basis | Partial | Only computational basis |
| Post-selection | Limited | Basic support |
| Complex control flow | Limited | Simple if/loop only |
| Multiple subroutines | Supported | Via multiple flush |

### Debugging Tips

```python
# Enable NetQASM logging
import logging
logging.getLogger("netqasm").setLevel(logging.DEBUG)

# Inspect subroutine before execution
subroutine = connection.compile()
for instr in subroutine.instructions:
    print(instr)

# Check Future state
print(f"Future resolved: {result._value is not None}")
```

## See Also

- [Simulation Flow](simulation_flow.md) - How simulations execute
- [Stack Components](stack_components.md) - Component descriptions
- [squidasm.nqasm Package](../api/nqasm_package.md) - API reference
- [NetQASM Documentation](https://netqasm.readthedocs.io/) - Official NetQASM docs
