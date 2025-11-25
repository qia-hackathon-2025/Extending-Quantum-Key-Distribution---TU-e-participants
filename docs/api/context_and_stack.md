# ProgramContext and Network Stack

Detailed exploration of the runtime context and internal network stack architecture.

---

## ProgramContext Internals

`ProgramContext` is the gateway for programs to access all runtime resources and interact with the quantum network.

### Resource Hierarchy

```
ProgramContext
├── csockets: Dict[str, ClassicalSocket]
│   ├── Socket to Peer1
│   ├── Socket to Peer2
│   └── Socket to PeerN
│
├── epr_sockets: Dict[(str, int), EPRSocket]
│   ├── (Peer1, 1) → EPRSocket
│   ├── (Peer1, 2) → EPRSocket
│   ├── (Peer2, 1) → EPRSocket
│   └── (PeerN, M) → EPRSocket
│
└── connection: BaseNetQASMConnection
    └── Link to local QNPU (QnosConnection)
```

### Classical Socket Dictionary

Sockets are keyed by peer name (string):

```python
def run(self, context: ProgramContext):
    alice_socket = context.csockets["Alice"]  # str key
    bob_socket = context.csockets["Bob"]
```

Access patterns:

```python
# List all connected peers
for peer_name, socket in context.csockets.items():
    socket.send(f"Hello from {peer_name}")

# Get specific socket
bob_messages = yield from context.csockets["Bob"].recv()
```

### EPR Socket Dictionary

Sockets are keyed by (peer_name, virt_id) tuple:

```python
def run(self, context: ProgramContext):
    # First socket with Alice
    epr1 = context.epr_sockets[("Alice", 1)]
    
    # Second socket with Alice (different virtual ID)
    epr2 = context.epr_sockets[("Alice", 2)]
    
    # Socket with Bob
    epr_bob = context.epr_sockets[("Bob", 1)]
```

Access patterns:

```python
# Iterate all EPR sockets
for (peer, virt_id), epr_socket in context.epr_sockets.items():
    qubit = epr_socket.create_keep()[0]
    # ...
```

### Connection (NetQASM Interface)

The connection object forwards all quantum instructions:

```python
def run(self, context: ProgramContext):
    connection = context.connection
    
    # Local qubit operations register with connection
    qubit = Qubit(connection)
    qubit.H()
    qubit.X()
    result = qubit.measure()
    
    # EPR operations also register with connection
    epr_socket = context.epr_sockets[("Alice", 1)]
    epr_qubit = epr_socket.create_keep()[0]
    epr_qubit.measure()
    
    # Everything executes on flush
    yield from connection.flush()
```

---

## Host Component and Layer

Located in `squidasm/sim/stack/host.py`, the Host is the first level of program execution above the application code.

### HostComponent

NetSquid component that embeds the program and manages its lifecycle:

```
HostComponent
├── Program instance
├── Shared Memory (for qubit state and results)
├── Classical Sockets (to peer hosts)
└── EPR Sockets (to peer QNPUs)
```

### HostProtocol

Event-driven protocol managing:

```python
class HostProtocol(Protocol):
    """Manages program execution and resource lifecycle."""
    
    # Lifecycle phases:
    # 1. Setup: Initialize sockets and memory
    # 2. Execution: Run program.run(context)
    # 3. Collection: Gather return dictionary
    # 4. Cleanup: Reset state for next iteration
```

Key responsibilities:

1. **Program Invocation**: Calls `program.run(context)` with proper context
2. **Socket Management**: Creates and maintains classical/EPR sockets
3. **Memory Management**: Allocates memory for qubits and results
4. **Error Handling**: Catches exceptions, logs, reports errors
5. **Result Collection**: Gathers return values from programs

### Context Creation

When `program.run()` is called, the Host provides:

```python
context = ProgramContext(
    csockets={
        "Bob": socket_to_bob,
        "Charlie": socket_to_charlie,
    },
    epr_sockets={
        ("Bob", 1): epr_socket_bob_1,
        ("Charlie", 2): epr_socket_charlie_2,
    },
    connection=qnos_connection
)

# Program receives this context
yield from program.run(context)
```

---

## QNodeOS (QNOS) Layer

Located in `squidasm/sim/stack/qnos.py`, QNodeOS handles local quantum operations and entanglement management.

### QNOS Components

```
QNodeOS
├── Handler
│   ├── NetQASM Connection
│   ├── Instruction Queue
│   └── Result Memory
│
├── Processor
│   ├── Quantum Gate Executor
│   ├── Measurement Handler
│   └── Qubit Memory
│
└── Netstack
    ├── EPR Manager
    ├── Entanglement Protocol
    └── Remote Node Interface
```

### Handler

Manages communication between Host and Processor:

```
Host                          QNOS Handler                      Processor
  │                                │                                │
  ├─ Register instructions ───────→│                                │
  │                                ├─ Compile to NetQASM code ─────→│
  │                                │                                │
  │                                │ ← Execute on quantum device ───│
  │                                │                                │
  │ ←─ Retrieve results ───────────│                                │
```

Key operations:

```python
class QNOSHandler:
    """Manages instruction compilation and execution."""
    
    def queue_instruction(self, instruction):
        """Add instruction to compilation queue."""
        pass
    
    def flush_instructions(self):
        """Compile and execute queued instructions."""
        pass
    
    def get_result(self, address):
        """Retrieve result from memory."""
        pass
```

### Processor

Executes compiled NetQASM instructions on the quantum device:

```
Compiled Subroutine
        ↓
[Decode NetQASM]
        ↓
[Execute on QuantumProcessor]
        ↓
[Maintain qubit state]
        ↓
[Write results to memory arrays]
```

Features:

- Maintains qubit state in simulator
- Applies quantum gates with noise
- Stores measurement results
- Tracks qubit memory allocation

### Netstack

Manages entanglement generation:

```
Application: epr_socket.create_keep()
        ↓
[Register request with Netstack]
        ↓
[Send request to peer node's Netstack]
        ↓
[Run entanglement generation protocol]
        ↓
[Qubit becomes available to application]
```

Key features:

- **Asynchronous**: EPR generation happens in background
- **Bidirectional**: Handles both creation and reception
- **Protocol**: Implements Entanglement Generation Protocol (EGP)
- **Mapping**: Virtual qubit IDs → Physical qubits

---

## StackNode: Complete Node Representation

Located in `squidasm/sim/stack/stack.py`, StackNode represents a complete quantum network node.

### Components

```
StackNode (NetSquid Component)
│
├── HostComponent
│   └── HostProtocol (runs programs)
│
├── QNodeOS
│   ├── Handler
│   ├── Processor (with QuantumProcessor)
│   ├── Netstack
│   └── QNOSProtocol
│
└── QuantumProcessor (NetSquid)
    ├── Quantum state matrix
    ├── Gate operators
    ├── Noise models
    └── Measurement simulator
```

### StackNode as a Composite Component

```python
class StackNode(QDeviceNode):
    """NetSquid component containing Host, QNOS, and Quantum Device."""
    
    @property
    def host_comp(self) -> HostComponent:
        """Access to Host component."""
        return self._host_comp
    
    @property
    def qnos_comp(self) -> QNOSComponent:
        """Access to QNodeOS component."""
        return self._qnos_comp
    
    @property
    def qdevice(self) -> QuantumProcessor:
        """Access to quantum device."""
        return self._qdevice
```

---

## StackNetwork: Complete Network

The `StackNetwork` class assembles all nodes with connections.

### Structure

```
StackNetwork (NetSquid Network)
│
├── Nodes (Dict[str, StackNode])
│   ├── "Alice" → StackNode
│   ├── "Bob" → StackNode
│   └── "Charlie" → StackNode
│
├── Quantum Links (Dict[(str,str), QuantumLink])
│   ├── ("Alice", "Bob") → EPRLink
│   ├── ("Bob", "Charlie") → EPRLink
│   └── ("Alice", "Charlie") → EPRLink
│
├── Classical Links (Dict[(str,str), ClassicalLink])
│   ├── ("Alice", "Bob") → ClassicalLink
│   ├── ("Bob", "Charlie") → ClassicalLink
│   └── ("Alice", "Charlie") → ClassicalLink
│
└── Global State
    ├── Simulation time
    ├── Quantum device connections
    └── Classical message queues
```

### Creating a Network

```python
from squidasm.run.stack.build import build_stack_network
from squidasm.run.stack.config import StackNetworkConfig

config = StackNetworkConfig.from_file("config.yaml")
stack_network = build_stack_network(config)

# Access nodes
alice_node = stack_network.nodes["Alice"]
bob_node = stack_network.nodes["Bob"]

# Run programs
programs = {"Alice": alice_prog, "Bob": bob_prog}
results = run(config=config, programs=programs)
```

---

## Data Flow: From Program to Quantum Device

### Complete Execution Path

```
Application Code
│
├─ qubit.H()                    [Queue with connection]
├─ qubit.X()
├─ result = qubit.measure()      [Return Future]
│
├─ yield from connection.flush() [Trigger compilation and execution]
│         │
│         ├→ QnosConnection.flush()
│         │         │
│         │         ├→ Compile instructions to NetQASM
│         │         │
│         │         └→ Send to QNOS Handler
│         │                 │
│         │                 ├→ Decode NetQASM
│         │                 │
│         │                 ├→ Processor.execute()
│         │                 │         │
│         │                 │         └→ QuantumProcessor
│         │                 │             ├─ Apply gates to state
│         │                 │             ├─ Measure (sample distribution)
│         │                 │             └─ Write results to memory
│         │                 │
│         │                 └→ Return results
│         │
│         └→ Resolve Future with measurement value
│
├─ print(int(result))            [Now has numeric value]
└─ ...continue program...
```

### Memory and State Management

```
Qubit Memory (Processor)
│
├─ Virtual Qubit 0 → Physical Qubit 3
├─ Virtual Qubit 1 → Physical Qubit 1
└─ Virtual Qubit 2 → Physical Qubit 5

Result Memory (Arrays)
│
├─ @0[10]: EPR pair creation results
├─ @1[20]: Measurement results
└─ @2[15]: Intermediate values
```

---

## Multi-Node Communication

### Classical Socket Flow

```
Alice Host                              Bob Host
    │                                       │
    ├─ socket.send(msg) ──────────────────→├─ yield from socket.recv()
    │    [Queued message]                   │    [Blocked, waiting]
    │                                       │
    └─ [Classical link transmits]          │
         [Delay: t_cycle]                  │
                                           ├─ [Receive and unblock]
                                           └─ Continue...
```

### EPR Socket Flow

```
Alice QNOS Netstack              Bob QNOS Netstack
    │                                   │
    ├─ epr_socket.create() ────────────→├─ epr_socket.recv_keep()
    │    [Request queued]                │    [Listening]
    │                                   │
    ├─ [Entanglement Protocol]         │
    │  (Background execution)           │
    │                                   │
    ├─ [EPR pair created]              ├─ [EPR pair received]
    │  [Local qubit available]         │  [Local qubit available]
    │                                   │
    └─ [Continue with EPR qubit] ····· └─ [Continue with EPR qubit]
```

---

## Error Handling and State Consistency

### Program Execution Validation

Before running programs, the simulator validates:

```python
def validate_program_meta(program: Program, config: StackNetworkConfig):
    meta = program.meta
    
    # Check node name matches
    assert meta.name in config.node_names
    
    # Check required classical sockets have links
    for peer_name in meta.csockets:
        assert config.has_clink(meta.name, peer_name)
    
    # Check required EPR sockets have quantum links
    for peer_name, virt_id in meta.epr_sockets:
        assert config.has_qlink(meta.name, peer_name)
    
    # Check qubit count
    assert meta.max_qubits <= config.get_stack(meta.name).qdevice_cfg.num_qubits
```

### Runtime Error Scenarios

1. **Missing socket**: KeyError when accessing non-existent socket
2. **Meta mismatch**: Fails at setup phase if resources unavailable
3. **Future access error**: AttributeError if Future accessed improperly
4. **Program exception**: Caught and logged, results invalidated
5. **Quantum device error**: Unlikely in simulator, would be state inconsistency

---

## Performance Considerations

### What's Fast

- Message passing (classical sockets) - O(message size)
- Instruction queuing - O(1)
- EPR request registration - O(1)
- Program context setup - O(sockets count)

### What's Slow

- Connection.flush() - O(instruction count)
  - Compilation time
  - Quantum simulation time
  - Grows with circuit depth and qubit count
- Measurement in large systems - O(2^qubit_count)
  - Unless using specific measurement basis

### Optimization Tips

```python
# Good: Batch operations
for i in range(100):
    qubits.append(Qubit(connection))
    qubits[-1].H()

yield from connection.flush()  # Single flush


# Less efficient: Multiple flushes
for i in range(100):
    qubit = Qubit(connection)
    qubit.H()
    yield from connection.flush()  # 100 flushes!
```

---

## Debugging and Introspection

### Logging Context Events

```python
from squidasm.sim.stack.common import LogManager

logger = LogManager.get_stack_logger("MyNode")

def run(self, context: ProgramContext):
    logger.debug(f"Classical sockets available: {list(context.csockets.keys())}")
    logger.debug(f"EPR sockets available: {list(context.epr_sockets.keys())}")
    
    csocket = context.csockets["Alice"]
    logger.info(f"Sending message via {csocket}")
```

### Inspecting Compiled Code

```python
def run(self, context: ProgramContext):
    connection = context.connection
    
    qubit = Qubit(connection)
    qubit.H()
    qubit.X()
    
    # Inspect compiled subroutine
    subroutine = connection.compile()
    logger.debug(f"Compiled subroutine:\n{subroutine}")
    
    # Execute the subroutine
    yield from connection.commit_subroutine(subroutine)
```

### Checking Network Configuration

```python
from squidasm.run.stack.config import StackNetworkConfig

cfg = StackNetworkConfig.from_file("config.yaml")

# List all nodes
print("Nodes:", [s.name for s in cfg.stacks])

# List all links
for link in cfg.links:
    print(f"Quantum link: {link.stack1} ↔ {link.stack2} ({link.typ})")

for clink in cfg.clinks:
    print(f"Classical link: {clink.stack1} ↔ {clink.stack2} ({clink.typ})")
```

---

## Next Steps

- [Program Interface](./program_interface.md) - Program structure
- [Architecture Overview](../architecture/overview.md) - System design
- [NetQASM Foundations](../foundations/netqasm.md) - Quantum programming
