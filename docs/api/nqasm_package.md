# squidasm.nqasm Package

The `squidasm.nqasm` package provides the low-level interface between NetQASM instructions and the NetSquid simulator. It implements the quantum network operating system (QNodeOS) and execution infrastructure.

## Overview

```
squidasm.nqasm/
├── qnodeos.py          # Quantum Node Operating System
├── netstack.py         # Network stack for EPR generation
├── output.py           # Output formatting utilities
└── executor/
    ├── __init__.py
    ├── base.py         # Base executor interface
    ├── subroutine.py   # Subroutine handler
    ├── shared_memory.py # Shared memory interface
    └── netsquidexecutor.py  # Main executor implementation
```

## QNodeOS

The `QNodeOS` class (`squidasm.nqasm.qnodeos`) simulates a quantum network operating system that manages application execution on a quantum network node.

### Class Definition

```python
from squidasm.nqasm.qnodeos import QNodeOS

class QNodeOS:
    """Quantum Node Operating System for SquidASM simulations.
    
    Manages:
    - Application registration and lifecycle
    - Memory allocation for quantum registers
    - NetQASM subroutine dispatch and execution
    - EPR generation coordination
    
    Attributes:
        name (str): Node identifier
        executor (NetSquidExecutor): The instruction executor
        netstack (NetworkStack): EPR generation coordinator
    """
```

### Key Methods

```python
# Register a new application
qnodeos.register_application(app_id: int, meta: ProgramMeta) -> None

# Handle incoming NetQASM subroutine
qnodeos.handle_request(app_id: int, subroutine: Subroutine) -> Generator

# Allocate virtual qubit memory
qnodeos.allocate_qubits(app_id: int, num_qubits: int) -> List[int]

# Release qubit memory
qnodeos.release_qubits(app_id: int, qubit_ids: List[int]) -> None
```

### Example Usage

```python
from squidasm.nqasm.qnodeos import QNodeOS
from netsquid.nodes import Node

# QNodeOS is typically created automatically during simulation setup
# but can be accessed for debugging:

def debug_qnodeos(context: ProgramContext):
    """Access QNodeOS for debugging (advanced usage)."""
    # Note: This is internal API and may change
    logger.debug(f"Node OS state: {context.connection._qnos}")
```

## NetworkStack

The `NetworkStack` class (`squidasm.nqasm.netstack`) manages entanglement generation between nodes.

### Class Definition

```python
from squidasm.nqasm.netstack import NetworkStack

class NetworkStack:
    """Network layer for EPR pair generation.
    
    Coordinates entanglement creation requests between nodes using
    the underlying physical layer (links).
    
    Attributes:
        node_name (str): Name of this node
        peer_nodes (Dict[str, NetworkStackPeer]): Connected peers
    """
```

### Key Methods

```python
# Request EPR pair creation with a peer
netstack.create_epr(
    peer_name: str,
    num_pairs: int,
    create_type: CreateType
) -> Generator[EPRResult]

# Receive EPR pair from a peer
netstack.recv_epr(
    peer_name: str,
    num_pairs: int
) -> Generator[EPRResult]
```

### EPR Creation Types

```python
from netqasm.sdk.epr_socket import EPRType

# Keep the qubit for further operations
EPRType.K  # or EPRType.CREATE_KEEP

# Measure immediately and return result
EPRType.M  # or EPRType.MEASURE_DIRECTLY

# Remote state preparation
EPRType.R  # or EPRType.REMOTE_STATE_PREP
```

## NetSquidExecutor

The `NetSquidExecutor` class (`squidasm.nqasm.executor.netsquidexecutor`) converts NetQASM instructions into NetSquid operations.

### Class Definition

```python
from squidasm.nqasm.executor.netsquidexecutor import NetSquidExecutor

class NetSquidExecutor:
    """Executes NetQASM instructions on the NetSquid simulator.
    
    This is the bridge between the high-level NetQASM instruction set
    and the low-level NetSquid quantum simulation.
    
    Responsibilities:
    - Parse and execute NetQASM instructions
    - Manage quantum memory (QDevice)
    - Coordinate with NetworkStack for EPR operations
    - Return execution results to the application
    
    Attributes:
        qdevice: The simulated quantum device
        subroutine_handler: Manages execution state
    """
```

### Instruction Categories

The executor handles these NetQASM instruction types:

| Category | Instructions | Description |
|----------|-------------|-------------|
| **Single-qubit gates** | `H`, `X`, `Y`, `Z`, `T`, `S` | Standard quantum gates |
| **Rotations** | `rot_X`, `rot_Y`, `rot_Z` | Parameterized rotations |
| **Two-qubit gates** | `CNOT`, `CZ` | Entangling operations |
| **Measurement** | `meas` | Computational basis measurement |
| **Memory** | `init`, `qfree` | Qubit allocation/deallocation |
| **EPR** | `create_epr`, `recv_epr` | Entanglement operations |
| **Classical** | `set`, `store`, `load` | Register operations |
| **Control** | `jmp`, `beq`, `bne` | Branching |

### Example: Instruction Execution Flow

```python
# When you write:
q = Qubit(connection)
q.H()
result = q.measure()
connection.flush()

# Internally:
# 1. SDK builds subroutine with instructions:
#    - init Q0
#    - h Q0
#    - meas Q0 M0
#
# 2. flush() sends to QNodeOS
#
# 3. QNodeOS dispatches to NetSquidExecutor
#
# 4. NetSquidExecutor executes each instruction:
#    - init: Allocate qubit in QDevice
#    - h: Apply Hadamard via NetSquid
#    - meas: Perform measurement, store result
#
# 5. Results returned to application
```

## SubroutineHandler

The `SubroutineHandler` class (`squidasm.nqasm.executor.subroutine`) manages the execution state of a NetQASM subroutine.

### Class Definition

```python
from squidasm.nqasm.executor.subroutine import SubroutineHandler

class SubroutineHandler:
    """Manages subroutine execution state.
    
    Tracks:
    - Program counter (instruction pointer)
    - Classical registers (R0-R15)
    - Measurement registers (M0-M15)
    - Array storage for results
    - Branch targets for control flow
    
    Attributes:
        subroutine (Subroutine): The NetQASM subroutine
        pc (int): Program counter
        registers (Dict[str, int]): Classical register values
        arrays (Dict[int, Array]): Array storage
    """
```

### Key Methods

```python
# Get current instruction
handler.current_instruction() -> ICmd

# Advance to next instruction
handler.advance() -> None

# Jump to target address
handler.jump(target: int) -> None

# Read register value
handler.get_register(name: str) -> int

# Write register value
handler.set_register(name: str, value: int) -> None

# Read array element
handler.get_array_element(array_id: int, index: int) -> int

# Write array element
handler.set_array_element(array_id: int, index: int, value: int) -> None
```

### Register Naming

| Register Type | Names | Purpose |
|---------------|-------|---------|
| General | R0-R15 | General purpose integers |
| Measurement | M0-M15 | Measurement outcomes |
| Qubit | Q0-Q15 | Virtual qubit identifiers |

## SharedMemory

The `SharedMemory` class (`squidasm.nqasm.executor.shared_memory`) provides the interface between application memory and executor storage.

### Class Definition

```python
from squidasm.nqasm.executor.shared_memory import SharedMemory

class SharedMemory:
    """Shared memory for application-executor communication.
    
    Allows applications to read results written by the executor
    (e.g., measurement outcomes, EPR generation info).
    """
```

### Usage Pattern

```python
# The SDK's Future objects use SharedMemory internally
result = q.measure()  # Returns a Future

# Before flush: result.value is None (in SharedMemory)
# After flush: result.value is the actual measurement (0 or 1)

connection.flush()
print(int(result))  # Now accessible
```

## Output Module

The `output` module (`squidasm.nqasm.output`) provides utilities for formatting and displaying execution results.

### Functions

```python
from squidasm.nqasm.output import format_subroutine, format_result

# Pretty-print a subroutine
formatted = format_subroutine(subroutine)
print(formatted)

# Format execution results
result_str = format_result(app_id, result_dict)
```

## Advanced Usage

### Inspecting Execution

For debugging, you can inspect the compiled subroutine:

```python
def run(self, context: ProgramContext):
    connection = context.connection
    
    # Build some operations
    q = Qubit(connection)
    q.H()
    q.X()
    result = q.measure()
    
    # Compile without executing
    subroutine = connection.compile()
    
    # Inspect the compiled code
    print("Compiled subroutine:")
    print(f"  Version: {subroutine.version}")
    print(f"  App ID: {subroutine.app_id}")
    print(f"  Instructions: {len(subroutine.instructions)}")
    
    for i, instr in enumerate(subroutine.instructions):
        print(f"    {i}: {instr}")
    
    # Now execute
    yield from connection.commit_subroutine(subroutine)
    
    return {"result": int(result)}
```

### Custom Instruction Handling

The executor can be extended (advanced usage):

```python
# Note: This is internal API and may change between versions
from squidasm.nqasm.executor.netsquidexecutor import NetSquidExecutor

class CustomExecutor(NetSquidExecutor):
    """Custom executor with additional logging."""
    
    def execute_instruction(self, instr):
        self.logger.debug(f"Executing: {instr}")
        result = super().execute_instruction(instr)
        self.logger.debug(f"Result: {result}")
        return result
```

## Integration with NetSquid

The nqasm package integrates with NetSquid components:

```
Application Layer (Python SDK)
         ↓
    NetQASM SDK
         ↓
    [Compile to Subroutine]
         ↓
    QNodeOS
         ↓
    NetSquidExecutor
         ↓
    NetSquid QDevice/QuantumProcessor
         ↓
    Physical Simulation
```

### NetSquid Components Used

- **QuantumProcessor**: Simulates gate execution with noise
- **QDevice**: Manages quantum memory
- **QuantumMemory**: Physical qubit storage
- **EntangledConnection**: EPR generation channels

## Error Handling

Common errors in the nqasm layer:

### RuntimeError: No qubit available

```python
# Cause: Requesting more qubits than available
# Solution: Increase num_qubits in qdevice_cfg or reduce max_qubits in ProgramMeta

qdevice_cfg:
  num_qubits: 10  # Increase this
```

### ValueError: Invalid virtual qubit ID

```python
# Cause: Using a qubit that was freed or never allocated
# Solution: Check qubit lifecycle

q = Qubit(connection)
q.measure()  # This frees the qubit
# q.H()  # Error! Qubit already freed
```

### TimeoutError: EPR generation

```python
# Cause: EPR request couldn't complete
# Solution: Check link configuration and increase timeout if needed
```

## See Also

- [squidasm.run Package](run_package.md) - Simulation execution
- [squidasm.sim Package](sim_package.md) - High-level simulation components
- [NetQASM Integration](../architecture/netqasm_integration.md) - How NetQASM works in SquidASM
