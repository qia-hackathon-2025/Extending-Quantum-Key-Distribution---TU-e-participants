# Program Interface and Lifecycle

## Overview

All SquidASM applications are built around the `Program` abstract base class. Programs represent the code running on individual nodes and must implement two key requirements: a `meta` property and a `run` method.

This document explains the program interface, lifecycle, and patterns for writing robust SquidASM applications.

---

## The Program Abstract Base Class

Located in `squidasm/sim/stack/program.py`:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

class Program(ABC):
    """Base class for all SquidASM programs."""
    
    @property
    @abstractmethod
    def meta(self) -> 'ProgramMeta':
        """Return metadata about program requirements."""
        pass
    
    @abstractmethod
    def run(self, context: 'ProgramContext'):
        """Execute the program."""
        pass
```

---

## ProgramMeta: Declaring Requirements

`ProgramMeta` is a dataclass that specifies everything a program needs to execute.

### Definition

```python
@dataclass
class ProgramMeta:
    name: str                              # Program name (e.g., "Alice")
    csockets: List[str] = field(default_factory=list)        # Peer names for classical sockets
    epr_sockets: List[Tuple[str, int]] = field(default_factory=list)  # (peer_name, virt_id) pairs
    max_qubits: int = 5                    # Maximum local qubits needed
```

### Parameters Explained

- **name**: Identifier for this program (should match node name in config)
- **csockets**: List of peer node names requiring classical sockets
  - Example: `["Bob", "Charlie"]` means classical connection to both nodes
  - Order doesn't matter, sockets accessible via `context.csockets[peer_name]`
- **epr_sockets**: List of (peer_name, virt_id) tuples for entanglement
  - `peer_name`: Remote node to generate EPR pairs with
  - `virt_id`: Virtual socket ID for distinguishing multiple sockets with same peer
  - Example: `[("Bob", 1), ("Charlie", 2)]` creates two separate EPR sockets
- **max_qubits**: Maximum number of local qubits needed (memory allocation)

### Example: Two-Node Application

```python
class AliceProgram(Program):
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="Alice",
            csockets=["Bob"],              # Need classical communication with Bob
            epr_sockets=[("Bob", 1)],      # Need EPR socket with Bob
            max_qubits=5                   # Need up to 5 qubits locally
        )

class BobProgram(Program):
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="Bob",
            csockets=["Alice"],
            epr_sockets=[("Alice", 1)],
            max_qubits=5
        )
```

### Example: Multi-Node Application

```python
class AliceProgram(Program):
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="Alice",
            csockets=["Bob", "Charlie"],
            epr_sockets=[("Bob", 1), ("Charlie", 2)],
            max_qubits=10
        )
```

---

## ProgramContext: Runtime Resources

`ProgramContext` is passed to the `run()` method and provides access to all necessary resources.

### Definition

```python
class ProgramContext:
    @property
    def csockets(self) -> Dict[str, ClassicalSocket]:
        """Classical sockets to peers declared in meta."""
        pass
    
    @property
    def epr_sockets(self) -> Dict[Tuple[str, int], EPRSocket]:
        """EPR sockets keyed by (peer_name, virt_id)."""
        pass
    
    @property
    def connection(self) -> BaseNetQASMConnection:
        """NetQASM connection for quantum operations."""
        pass
```

### Accessing Resources

```python
def run(self, context: ProgramContext):
    # Unpack sockets and connection
    csocket = context.csockets["Bob"]
    epr_socket = context.epr_sockets[("Bob", 1)]
    connection = context.connection
    
    # Use in program...
    yield from ...
```

### Socket Types

- **ClassicalSocket**: Send/receive classical messages
  - Methods: `send(msg)`, `send_int(n)`, `recv()`, `recv_int()`
  - All `recv_*` methods require `yield from`
  
- **EPRSocket**: Generate entangled pairs
  - Methods: `create_keep()`, `create_measure()`, `recv_keep()`, `recv_measure()`
  - Creator and receiver must coordinate (implicit via socket ID)

- **Connection**: Execute quantum operations
  - Methods: `flush()`, `commit_subroutine()`, etc.
  - Required for all quantum gate and measurement operations

---

## Program Lifecycle

### Initialization Phase

```python
class MyProgram(Program):
    def __init__(self, param1, param2):
        """Programs can accept initialization parameters."""
        self.param1 = param1
        self.param2 = param2
    
    @property
    def meta(self) -> ProgramMeta:
        """Called by simulator to get resource requirements."""
        return ProgramMeta(name="MyNode", max_qubits=5)
```

### Setup Phase

```
1. Simulator reads meta from all programs
2. Simulator validates:
   - Network has required links (classical and quantum)
   - Node names match
   - Max qubits ≤ device capacity
3. Simulator creates sockets and connection
4. Simulator passes ProgramContext to run()
```

### Execution Phase

```python
    def run(self, context: ProgramContext):
        """Called once per iteration to execute the program."""
        csocket = context.csockets["Bob"]
        connection = context.connection
        
        # Phase 1: Setup
        # Create qubits, initialize EPR requests
        
        # Phase 2: Quantum operations
        # Apply gates, queue measurements
        
        # Phase 3: Synchronization
        # Flush instructions, await results
        
        # Phase 4: Classical communication
        # Send/receive results
        
        # Phase 5: Return results
        return {"measurement": ...}
```

### Cleanup Phase

```
1. Program returns (or yields final value)
2. Any unconsumed values are discarded
3. Results dictionary is collected
4. Quantum state is reset
5. Next iteration begins
```

---

## Complete Example: Bell State Measurement

```python
from squidasm.sim.stack.program import Program, ProgramMeta, ProgramContext
from netqasm.sdk.qubit import Qubit

class AliceProgram(Program):
    """Create EPR pair, measure both qubits."""
    
    def __init__(self):
        pass
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="Alice",
            epr_sockets=[("Bob", 1)],
            csockets=["Bob"],
            max_qubits=5
        )
    
    def run(self, context: ProgramContext):
        # Get resources
        epr_socket = context.epr_sockets[("Bob", 1)]
        csocket = context.csockets["Bob"]
        connection = context.connection
        
        # Create EPR pair
        epr_qubit = epr_socket.create_keep()[0]
        
        # Apply Hadamard to local qubit
        epr_qubit.H()
        
        # Measure both qubits
        alice_result = epr_qubit.measure()
        
        # Flush all instructions to QNPU
        yield from connection.flush()
        
        # Send measurement result to Bob
        csocket.send_int(int(alice_result))
        
        # Receive Bob's result
        bob_result = yield from csocket.recv_int()
        
        # Return data for analysis
        return {
            "alice_measurement": int(alice_result),
            "bob_measurement": bob_result
        }


class BobProgram(Program):
    """Receiver: wait for EPR pair and measure."""
    
    def __init__(self):
        pass
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="Bob",
            epr_sockets=[("Alice", 1)],
            csockets=["Alice"],
            max_qubits=5
        )
    
    def run(self, context: ProgramContext):
        # Get resources
        epr_socket = context.epr_sockets[("Alice", 1)]
        csocket = context.csockets["Alice"]
        connection = context.connection
        
        # Wait for EPR pair
        epr_qubit = epr_socket.recv_keep()[0]
        
        # Apply Hadamard to local qubit
        epr_qubit.H()
        
        # Measure qubit
        bob_result = epr_qubit.measure()
        
        # Flush all instructions to QNPU
        yield from connection.flush()
        
        # Receive Alice's measurement
        alice_result = yield from csocket.recv_int()
        
        # Send Bob's measurement result
        csocket.send_int(int(bob_result))
        
        # Return data for analysis
        return {
            "alice_measurement": alice_result,
            "bob_measurement": int(bob_result)
        }
```

---

## Design Patterns

### Pattern 1: Parameterized Programs

Initialize programs with application-specific parameters:

```python
class EPRGeneratorProgram(Program):
    """Generate multiple EPR pairs and measure them."""
    
    def __init__(self, num_pairs: int, apply_hadamard: bool):
        self.num_pairs = num_pairs
        self.apply_hadamard = apply_hadamard
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="Generator",
            epr_sockets=[("Receiver", 1)],
            max_qubits=10
        )
    
    def run(self, context: ProgramContext):
        epr_socket = context.epr_sockets[("Receiver", 1)]
        connection = context.connection
        results = []
        
        for i in range(self.num_pairs):
            qubit = epr_socket.create_keep()[0]
            if self.apply_hadamard:
                qubit.H()
            result = qubit.measure()
            yield from connection.flush()
            results.append(int(result))
        
        return {"measurements": results}
```

### Pattern 2: Conditional Logic with NetQASM

Cannot use native Python `if` before flush. Use NetQASM SDK methods:

```python
def run(self, context: ProgramContext):
    connection = context.connection
    
    # Get measurement result
    qubit = Qubit(connection)
    result = qubit.measure()
    yield from connection.flush()
    
    # NOW safe to use Python if
    if int(result) == 0:
        # Process result == 0
        pass
    else:
        # Process result == 1
        pass
```

For more complex control flow before flush, use NetQASM SDK:

```python
def run(self, context: ProgramContext):
    connection = context.connection
    qubit = Qubit(connection)
    
    result = qubit.measure()
    
    # Define branches as separate functions
    def if_zero():
        qubit.X()
    
    def if_one():
        qubit.Y()
    
    # Use SDK method for conditional
    connection.if_eq(result, 0, if_zero)
    
    yield from connection.flush()
```

### Pattern 3: Multi-Peer Communication

```python
class DistributedProgram(Program):
    """Coordinate with multiple peers."""
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="Central",
            csockets=["Left", "Right"],
            epr_sockets=[("Left", 1), ("Right", 2)],
            max_qubits=20
        )
    
    def run(self, context: ProgramContext):
        left_cs = context.csockets["Left"]
        right_cs = context.csockets["Right"]
        left_epr = context.epr_sockets[("Left", 1)]
        right_epr = context.epr_sockets[("Right", 2)]
        connection = context.connection
        
        # Generate EPR with both peers
        left_qubit = left_epr.create_keep()[0]
        right_qubit = right_epr.create_keep()[0]
        
        # Bell measurement on EPR qubits
        left_qubit.cnot(right_qubit)
        m1 = left_qubit.measure()
        m2 = right_qubit.measure()
        
        yield from connection.flush()
        
        # Send corrections to right peer
        left_cs.send_int(int(m1))
        right_cs.send_int(int(m2))
        
        return {
            "m1": int(m1),
            "m2": int(m2)
        }
```

---

## Common Mistakes and Solutions

### Mistake 1: Using Future Before Flush

```python
# ❌ WRONG
result = qubit.measure()
if int(result) == 0:  # Error! result is still a Future
    pass

# ✅ CORRECT
result = qubit.measure()
yield from connection.flush()
if int(result) == 0:  # Now result has a value
    pass
```

### Mistake 2: Forgetting yield from recv()

```python
# ❌ WRONG
message = csocket.recv()  # Returns a future, not the message

# ✅ CORRECT
message = yield from csocket.recv()  # Blocks until message arrives
```

### Mistake 3: Socket Mismatch

```python
# ❌ WRONG - Declared "Bob" but accessing "Charlie"
@property
def meta(self):
    return ProgramMeta(csockets=["Bob"])

def run(self, context):
    csocket = context.csockets["Charlie"]  # KeyError!

# ✅ CORRECT
@property
def meta(self):
    return ProgramMeta(csockets=["Charlie"])

def run(self, context):
    csocket = context.csockets["Charlie"]  # OK
```

### Mistake 4: Unmatched EPR Socket IDs

```python
# ❌ WRONG - Creator uses id=1, receiver uses id=2
class CreatorProgram(Program):
    @property
    def meta(self):
        return ProgramMeta(epr_sockets=[("Receiver", 1)])

class ReceiverProgram(Program):
    @property
    def meta(self):
        return ProgramMeta(epr_sockets=[("Creator", 2)])  # Wrong ID!

# ✅ CORRECT - Both use same ID
class CreatorProgram(Program):
    @property
    def meta(self):
        return ProgramMeta(epr_sockets=[("Receiver", 1)])

class ReceiverProgram(Program):
    @property
    def meta(self):
        return ProgramMeta(epr_sockets=[("Creator", 1)])  # Matches!
```

---

## Best Practices

### 1. Declare All Requirements in Meta

Don't create dependencies dynamically. The simulator needs to validate before execution.

### 2. Use Meaningful Program Names

Program names should match node names in configuration:

```python
@property
def meta(self) -> ProgramMeta:
    return ProgramMeta(name="Alice")  # Must match config
```

### 3. Handle All Flush Operations

Every quantum operation sequence must end with a flush:

```python
qubit.H()
qubit.X()
result = qubit.measure()
yield from connection.flush()  # Don't forget!
```

### 4. Convert Futures to Native Types Before Processing

```python
# ✅ GOOD
measurements = [int(m) for m in future_list]
for m in measurements:
    process(m)

# ❌ AVOID
for m in future_list:  # Unexpected behavior with Future objects
    process(int(m))
```

### 5. Use Logging for Debugging

See [Logging documentation](../foundations/logging.md) for details.

```python
from squidasm.sim.stack.common import LogManager

logger = LogManager.get_stack_logger("AliceProgram")
logger.info(f"Measurement result: {int(result)}")
```

---

## Next Steps

- [ProgramContext and Network Stack](./context_and_stack.md) - Detailed context internals
- [Configuration Guide](./configuration.md) - Network and device setup
- [Tutorials](../tutorials/1_basics.md) - Step-by-step examples
