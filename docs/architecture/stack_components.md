# Stack Components

This document describes the internal components of a SquidASM network stack and their relationships.

## Stack Overview

A **Stack** represents a complete network node in SquidASM. Each stack contains:

```
┌─────────────────────────────────────────────────────────────┐
│                         Stack                                │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                      Host                            │    │
│  │  - Runs application programs                        │    │
│  │  - Manages sockets (classical & EPR)               │    │
│  │  - Coordinates with QNodeOS                        │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                  │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                    QNodeOS                           │    │
│  │  - Quantum Node Operating System                    │    │
│  │  - Dispatches subroutines to executor              │    │
│  │  - Manages memory allocation                        │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                  │
│          ┌────────────────┼────────────────┐                │
│          ▼                ▼                ▼                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ NetworkStack │  │   Executor   │  │    QDevice   │      │
│  │ (EPR layer)  │  │  (NetQASM)   │  │  (Physical)  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Host

The **Host** represents the classical computer that runs application programs.

### Responsibilities

1. **Program execution**: Runs `Program.run()` methods
2. **Socket management**: Creates and manages communication sockets
3. **Context creation**: Builds `ProgramContext` for programs
4. **Result collection**: Gathers return values from programs

### Key Interfaces

```python
class Host:
    """Application host for a quantum network node."""
    
    def __init__(self, name: str, qnos: QNos):
        self.name = name
        self.qnos = qnos
        self.csockets: Dict[str, CSocket] = {}
        self.epr_sockets: Dict[str, EPRSocket] = {}
    
    def register_program(self, program: Program) -> None:
        """Register a program and allocate its resources."""
        meta = program.meta
        
        # Create classical sockets
        for peer in meta.csockets:
            self.csockets[peer] = CSocket(self.name, peer)
        
        # Create EPR sockets
        for peer in meta.epr_sockets:
            self.epr_sockets[peer] = EPRSocket(self.name, peer)
    
    def create_context(self) -> ProgramContext:
        """Create execution context for the program."""
        return ProgramContext(
            connection=self.qnos.connection,
            csockets=self.csockets,
            epr_sockets=self.epr_sockets,
            app_config=self.app_config
        )
    
    def run_program(self, program: Program) -> Dict[str, Any]:
        """Execute a program and return its result."""
        context = self.create_context()
        return yield from program.run(context)
```

### Host Lifecycle

```
1. Initialization
   - Create Host with reference to QNodeOS
   - Initialize empty socket dictionaries

2. Program Registration
   - Parse ProgramMeta
   - Create required sockets
   - Allocate qubit memory in QNodeOS

3. Execution
   - Create ProgramContext
   - Execute program.run()
   - Handle yields (flush, recv)
   - Collect return value

4. Cleanup
   - Release sockets
   - Free qubit memory
```

## QNodeOS (Quantum Node Operating System)

The **QNodeOS** simulates the operating system managing quantum resources.

### Responsibilities

1. **Application management**: Track running applications
2. **Memory allocation**: Assign virtual qubit IDs
3. **Subroutine dispatch**: Send NetQASM code to executor
4. **EPR coordination**: Interface with NetworkStack

### Key Interfaces

```python
class QNodeOS:
    """Quantum Network Operating System."""
    
    def __init__(self, name: str, qdevice: QDevice):
        self.name = name
        self.executor = NetSquidExecutor(qdevice)
        self.netstack = NetworkStack(name)
        self.memory_manager = MemoryManager(qdevice.num_qubits)
    
    def allocate_qubits(self, app_id: int, num_qubits: int) -> List[int]:
        """Allocate virtual qubit IDs for an application."""
        return self.memory_manager.allocate(app_id, num_qubits)
    
    def handle_subroutine(self, app_id: int, subroutine: Subroutine):
        """Execute a NetQASM subroutine."""
        # Dispatch to executor
        result = yield from self.executor.execute(subroutine)
        return result
    
    def handle_epr_request(self, app_id: int, request: EPRRequest):
        """Handle EPR generation request."""
        return yield from self.netstack.process_request(request)
```

### Memory Management

```
Virtual Qubit Space          Physical Qubit Space
┌──────────────────┐         ┌──────────────────┐
│ App 1: Q0, Q1    │ ───────▶│ Physical Q0, Q1  │
├──────────────────┤         ├──────────────────┤
│ App 2: Q0, Q1, Q2│ ───────▶│ Physical Q2,Q3,Q4│
└──────────────────┘         └──────────────────┘

Each application sees its own virtual address space (Q0, Q1, ...)
QNodeOS maps these to physical qubits in the QDevice
```

## NetworkStack

The **NetworkStack** handles entanglement generation with remote nodes.

### Responsibilities

1. **EPR request handling**: Process create/recv requests
2. **Link coordination**: Interface with quantum links
3. **Result delivery**: Return EPR outcomes to applications

### Key Interfaces

```python
class NetworkStack:
    """Network layer for EPR generation."""
    
    def __init__(self, name: str):
        self.name = name
        self.peers: Dict[str, PeerInfo] = {}
        self.pending_requests: Dict[int, EPRRequest] = {}
    
    def register_peer(self, peer_name: str, link: QuantumLink):
        """Register a connected peer."""
        self.peers[peer_name] = PeerInfo(peer_name, link)
    
    def create_epr(self, peer: str, num_pairs: int) -> List[EPRQubit]:
        """Create EPR pairs with a peer."""
        request = EPRCreateRequest(peer, num_pairs)
        return yield from self._process_create(request)
    
    def recv_epr(self, peer: str, num_pairs: int) -> List[EPRQubit]:
        """Receive EPR pairs from a peer."""
        request = EPRRecvRequest(peer, num_pairs)
        return yield from self._process_recv(request)
```

### EPR Generation Flow

```
Alice (create)                    Bob (recv)
─────────────────────────────────────────────────
1. App calls create_keep()        1. App calls recv_keep()
         │                                 │
         ▼                                 ▼
2. NetworkStack.create_epr()      2. NetworkStack.recv_epr()
         │                                 │
         └─────────┬───────────────────────┘
                   ▼
         3. Link generates EPR pair
              │              │
              ▼              ▼
         4. Qubit to        4. Qubit to
            Alice's            Bob's
            QDevice            QDevice
              │              │
              ▼              ▼
         5. Return to       5. Return to
            Alice's app        Bob's app
```

## NetSquidExecutor

The **NetSquidExecutor** executes NetQASM instructions on the NetSquid simulator.

### Responsibilities

1. **Instruction parsing**: Decode NetQASM instructions
2. **Gate execution**: Apply quantum gates via NetSquid
3. **Measurement**: Perform measurements and store results
4. **State management**: Track registers and arrays

### Key Interfaces

```python
class NetSquidExecutor:
    """Executes NetQASM instructions on NetSquid."""
    
    def __init__(self, qdevice: QDevice):
        self.qdevice = qdevice
        self.processor = qdevice.processor
    
    def execute(self, subroutine: Subroutine) -> ExecutionResult:
        """Execute a complete subroutine."""
        handler = SubroutineHandler(subroutine)
        
        while not handler.finished():
            instr = handler.current_instruction()
            yield from self._execute_instruction(instr, handler)
            handler.advance()
        
        return handler.get_result()
    
    def _execute_instruction(self, instr: Instruction, handler: SubroutineHandler):
        """Execute a single instruction."""
        if instr.opcode == OpCode.H:
            yield from self._execute_hadamard(instr, handler)
        elif instr.opcode == OpCode.CNOT:
            yield from self._execute_cnot(instr, handler)
        elif instr.opcode == OpCode.MEAS:
            yield from self._execute_measure(instr, handler)
        # ... more instruction types
```

### Gate Execution

```python
def _execute_hadamard(self, instr: Instruction, handler: SubroutineHandler):
    """Execute Hadamard gate."""
    qubit_id = handler.get_qubit(instr.operands[0])
    
    # Apply gate through NetSquid processor
    self.processor.execute_program(
        program=HadamardProgram(qubit_id),
        qubit_mapping={0: qubit_id}
    )
    
    # Wait for gate completion (simulation time)
    yield self.await_program(self.processor)
```

## QDevice (Quantum Device)

The **QDevice** represents the physical quantum processor.

### Responsibilities

1. **Qubit storage**: Physical quantum memory
2. **Gate operations**: Execute quantum gates with noise
3. **Decoherence**: Apply T1/T2 noise over time

### Device Types

#### Generic QDevice

```python
class GenericQDevice:
    """Idealized quantum device with configurable noise."""
    
    def __init__(self, config: GenericQDeviceConfig):
        self.num_qubits = config.num_qubits
        self.T1 = config.T1
        self.T2 = config.T2
        
        # Create NetSquid quantum processor
        self.processor = QuantumProcessor(
            num_positions=config.num_qubits,
            models={
                "T1": T1NoiseModel(config.T1),
                "T2": T2NoiseModel(config.T2),
                "gate_noise": DepolarizingNoiseModel(
                    config.single_qubit_gate_depolar_prob
                )
            }
        )
```

#### NV QDevice

```python
class NVQDevice:
    """NV center quantum device with physical constraints."""
    
    def __init__(self, config: NVQDeviceConfig):
        self.num_qubits = config.num_qubits
        
        # NV has one electron + multiple carbons
        self.electron_qubit = 0
        self.carbon_qubits = list(range(1, config.num_qubits))
        
        # Topology constraint: only electron-carbon interactions
        self.allowed_pairs = [(0, i) for i in self.carbon_qubits]
```

## Classical Sockets

**CSocket** provides classical communication between nodes.

### Implementation

```python
class CSocket:
    """Classical socket for message passing."""
    
    def __init__(self, local_name: str, peer_name: str):
        self.local = local_name
        self.peer = peer_name
        self.buffer: List[str] = []
    
    def send(self, message: str) -> None:
        """Send a message to the peer."""
        # Message is queued for delivery
        self._channel.send(message)
    
    def recv(self) -> Generator[None, None, str]:
        """Receive a message from the peer."""
        # Yield until message arrives
        while len(self.buffer) == 0:
            yield  # Wait for message
        return self.buffer.pop(0)
```

## EPR Sockets

**EPRSocket** provides entanglement generation with remote nodes.

### Implementation

```python
class EPRSocket:
    """EPR socket for entanglement generation."""
    
    def __init__(self, local_name: str, peer_name: str):
        self.local = local_name
        self.peer = peer_name
    
    def create_keep(self, number: int = 1) -> List[Qubit]:
        """Create EPR pairs and keep local qubits."""
        # Request EPR generation through NetworkStack
        qubits = yield from self._netstack.create_epr(
            self.peer, number, EPRType.CREATE_KEEP
        )
        return qubits
    
    def recv_keep(self, number: int = 1) -> List[Qubit]:
        """Receive EPR pairs initiated by peer."""
        qubits = yield from self._netstack.recv_epr(
            self.peer, number, EPRType.CREATE_KEEP
        )
        return qubits
```

## Component Interactions

### Quantum Operation Flow

```
User Code
    │
    │  q.H()
    ▼
NetQASM SDK
    │
    │  Build instruction
    ▼
Connection
    │
    │  Queue instruction
    ▼
Host (on flush)
    │
    │  compile() + commit_subroutine()
    ▼
QNodeOS
    │
    │  handle_subroutine()
    ▼
NetSquidExecutor
    │
    │  execute_hadamard()
    ▼
QDevice.processor
    │
    │  execute_program()
    ▼
NetSquid Quantum Memory
    │
    │  Physical state update
    ▼
Result back through stack
```

### EPR Generation Flow

```
Alice: create_keep()              Bob: recv_keep()
        │                                 │
        ▼                                 ▼
    EPRSocket                         EPRSocket
        │                                 │
        ▼                                 ▼
    NetworkStack ◄──── Link ────► NetworkStack
        │                                 │
        ▼                                 ▼
    QNodeOS                           QNodeOS
        │                                 │
        ▼                                 ▼
    QDevice                           QDevice
    (qubit allocated)                 (qubit allocated)
        │                                 │
        ▼                                 ▼
    Return qubit                      Return qubit
```

## See Also

- [Simulation Flow](simulation_flow.md) - How simulations execute
- [NetQASM Integration](netqasm_integration.md) - NetQASM execution details
- [squidasm.nqasm Package](../api/nqasm_package.md) - API reference
