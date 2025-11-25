# Foundations: EPR Sockets and Entanglement Generation

Understanding quantum entanglement generation in SquidASM.

---

## Entanglement Generation Overview

EPR (Einstein-Podolsky-Rosen) sockets handle creation and distribution of quantum entangled pairs between nodes.

### What is EPR?

EPR stands for Einstein-Podolsky-Rosen. In this context, an "EPR pair" refers to a **maximally entangled two-qubit state**:

$$|\Phi^+\rangle = \frac{1}{\sqrt{2}}(|00\rangle + |11\rangle)$$

This state has the property that:
- Measuring one qubit instantly determines the outcome of measuring the other
- Both qubits are correlated (both measure 0 or both measure 1)
- Perfect for quantum network applications (teleportation, distributed gates, etc.)

### Bell States

Quantum networks can generate four Bell states:

$$|\Phi^+\rangle = \frac{1}{\sqrt{2}}(|00\rangle + |11\rangle) \quad \text{(Same parity)}$$

$$|\Phi^-\rangle = \frac{1}{\sqrt{2}}(|00\rangle - |11\rangle) \quad \text{(Same parity)}$$

$$|\Psi^+\rangle = \frac{1}{\sqrt{2}}(|01\rangle + |10\rangle) \quad \text{(Different parity)}$$

$$|\Psi^-\rangle = \frac{1}{\sqrt{2}}(|01\rangle - |10\rangle) \quad \text{(Different parity)}$$

**In SquidASM**: All pairs are delivered as $|\Phi^+\rangle$. If a different state is generated, automatic Pauli corrections are applied.

---

## EPR Socket API

### Creating EPR Pairs: Creator Side

The node initiating EPR pair creation:

```python
from netqasm.sdk.socket import EPRSocket

def run(self, context: ProgramContext):
    epr_socket = context.epr_sockets[("Bob", 1)]
    
    # Create one EPR pair
    qubits = epr_socket.create_keep()
    local_qubit = qubits[0]  # Local half of the pair
    
    # Create multiple pairs
    qubits = epr_socket.create_keep(number=5)
    
    # Now qubit is virtual - operations register with connection
    local_qubit.H()
    local_qubit.measure()
    
    yield from context.connection.flush()
```

**Return Value**: `List[Qubit]` of length = number of pairs

### Receiving EPR Pairs: Receiver Side

The node receiving the entangled pairs:

```python
def run(self, context: ProgramContext):
    epr_socket = context.epr_sockets[("Alice", 1)]
    
    # Wait for and receive one EPR pair
    qubits = epr_socket.recv_keep()
    remote_qubit = qubits[0]
    
    # Wait for and receive multiple pairs
    qubits = epr_socket.recv_keep(number=5)
    
    # Operations on received qubits
    remote_qubit.H()
    remote_qubit.measure()
    
    yield from context.connection.flush()
```

**Blocking**: The `recv_keep()` call blocks until the creator has generated the pair.

### Key Parameters

#### Socket ID (virt_id)

Multiple EPR sockets with the same peer require different IDs:

```python
@property
def meta(self) -> ProgramMeta:
    return ProgramMeta(
        epr_sockets=[
            ("Alice", 1),  # First socket with Alice
            ("Alice", 2),  # Second socket with Alice
            ("Bob", 1),    # First socket with Bob
        ]
    )

def run(self, context: ProgramContext):
    socket1 = context.epr_sockets[("Alice", 1)]
    socket2 = context.epr_sockets[("Alice", 2)]
    socket_bob = context.epr_sockets[("Bob", 1)]
    
    # Each socket is independent
```

**Important**: Creator and receiver must use matching socket IDs.

#### Number of Pairs

```python
# Single pair (default)
qubits = epr_socket.create_keep()         # Returns list of 1 qubit
qubits = epr_socket.create_keep(number=1)

# Multiple pairs
qubits = epr_socket.create_keep(number=10)  # Returns list of 10 qubits
```

**Return**: Always a list, even for single pairs.

---

## EPR Socket Modes

### Create and Keep

Pair is created and both nodes keep their local halves:

```python
def alice_run(self, context: ProgramContext):
    epr_socket = context.epr_sockets[("Bob", 1)]
    qubit = epr_socket.create_keep()[0]  # Alice has a qubit
    qubit.H()
    yield from context.connection.flush()

def bob_run(self, context: ProgramContext):
    epr_socket = context.epr_sockets[("Alice", 1)]
    qubit = epr_socket.recv_keep()[0]   # Bob has a qubit
    qubit.H()
    yield from context.connection.flush()
```

**Use Cases**:
- Bell state measurement
- Entanglement swapping
- Distributed operations
- Quantum key distribution

### Create and Measure

Pair is created and immediately measured on both nodes:

```python
def alice_run(self, context: ProgramContext):
    epr_socket = context.epr_sockets[("Bob", 1)]
    results = epr_socket.create_measure()  # Alice measures immediately
    yield from context.connection.flush()
    alice_m1, alice_m2 = int(results[0]), int(results[1])

def bob_run(self, context: ProgramContext):
    epr_socket = context.epr_sockets[("Alice", 1)]
    results = epr_socket.recv_measure()   # Bob measures immediately
    yield from context.connection.flush()
    bob_m1, bob_m2 = int(results[0]), int(results[1])
```

**Return**: Measurement results (not qubits)

**Use Cases**:
- Quantum randomness generation
- Bell test experiments
- Simple correlation studies

---

## Network Aspects of Entanglement

### Quantum Link Configuration

EPR generation is configured in the network configuration:

```yaml
links:
  - stack1: Alice
    stack2: Bob
    typ: depolarise
    cfg:
      fidelity: 0.95        # Quality of entanglement
      t_cycle: 10.0         # Time per attempt (ns)
      prob_success: 0.95    # Success probability
```

This link controls:
- Success/failure of EPR generation
- Quality (fidelity) of generated pairs
- Time required for generation

### Asynchronous Generation

EPR generation happens in the background:

```python
def run(self, context: ProgramContext):
    epr_socket = context.epr_sockets[("Bob", 1)]
    
    # Request EPR pairs - this is fast (just queues request)
    qubits = epr_socket.create_keep(number=100)
    
    # Actual generation happens asynchronously
    # while main program continues
    
    yield from context.connection.flush()
    
    # After flush, qubits are ready
```

### Virtual to Physical Mapping

EPR pairs use virtual qubit IDs that are mapped to physical qubits:

```
Virtual Qubit 0  ──→ Physical Qubit 3
Virtual Qubit 1  ──→ Physical Qubit 1
Virtual Qubit 2  ──→ Physical Qubit 5
```

This mapping:
- Happens transparently to the application
- Allows virtual qubit count > physical qubit count
- Depends on device capacity and configuration

---

## Synchronization with EPR Sockets

### Two-Node EPR Coordination

The create/receive pattern ensures synchronization:

```
Timeline:

Alice                           Bob
  │                               │
  ├─ epr_socket.create_keep() ─→─│ epr_socket.recv_keep()
  │  [Request queued]            │ [Listening]
  │                              │
  ├─ [EPR generation protocol]   │
  │  [Background process]        │
  │  [Duration: t_cycle]         │
  │                              │
  ├─ [EPR pair ready] ←──────────┤ [EPR pair ready]
  │  [Qubit available]           │ [Qubit available]
  │                              │
  └─ [Operations on qubit] ······ └─ [Operations on qubit]
```

### Blocking Semantics

```python
def alice_run(self, context: ProgramContext):
    epr_socket = context.epr_sockets[("Bob", 1)]
    qubits = epr_socket.create_keep()
    # Returns immediately - no blocking
    
    # Qubit operations are queued
    qubits[0].H()
    qubits[0].measure()
    
    # Flush causes all queued operations + EPR prep to execute
    yield from context.connection.flush()

def bob_run(self, context: ProgramContext):
    epr_socket = context.epr_sockets[("Alice", 1)]
    
    # This blocks until Alice sends EPR request
    qubits = epr_socket.recv_keep()
    
    # Same operations
    qubits[0].H()
    qubits[0].measure()
    
    yield from context.connection.flush()
```

### Deadlock Considerations

**Safe pattern**: Both sides must agree on EPR socket usage.

```python
# ✅ SAFE: Symmetric socket declaration
class AliceProgram(Program):
    @property
    def meta(self):
        return ProgramMeta(epr_sockets=[("Bob", 1)])
    
    def run(self, context):
        epr = context.epr_sockets[("Bob", 1)]
        qubits = epr.create_keep()

class BobProgram(Program):
    @property
    def meta(self):
        return ProgramMeta(epr_sockets=[("Alice", 1)])
    
    def run(self, context):
        epr = context.epr_sockets[("Alice", 1)]
        qubits = epr.recv_keep()


# ❌ WRONG: Asymmetric sockets (would deadlock)
class AliceProgram(Program):
    @property
    def meta(self):
        return ProgramMeta(epr_sockets=[("Bob", 1)])
    
    def run(self, context):
        # Bob not declaring socket - deadlock!
        ...
```

---

## Bell State Measurements

Measuring entangled pairs in the Bell basis allows entanglement swapping.

### Theory

Bell measurement of qubits $q_1$ and $q_2$:

$$\text{CNOT}(q_1, q_2); \text{H}(q_1); \text{Measure}(q_1, q_2)$$

The two measurement results correspond to:
- $(0,0)$ → state was $|\Phi^+\rangle$
- $(0,1)$ → state was $|\Psi^+\rangle$
- $(1,0)$ → state was $|\Phi^-\rangle$
- $(1,1)$ → state was $|\Psi^-\rangle$

### Implementation

```python
def run(self, context: ProgramContext):
    epr_socket1 = context.epr_sockets[("NodeA", 1)]
    epr_socket2 = context.epr_sockets[("NodeB", 1)]
    connection = context.connection
    
    # Get two EPR qubits from different sources
    q1 = epr_socket1.create_keep()[0]
    q2 = epr_socket2.recv_keep()[0]
    
    # Bell measurement: CNOT + H + measure
    q1.cnot(q2)
    q1.H()
    
    m1 = q1.measure()
    m2 = q2.measure()
    
    yield from connection.flush()
    
    # Send results to other nodes for correction
    csocket_a = context.csockets["NodeA"]
    csocket_a.send_int(int(m1))
    csocket_a.send_int(int(m2))
```

---

## Entanglement Swapping

Creating entanglement between distant nodes.

### Two-Hop Swapping

```
Initial:  Alice ─── Charlie ─── Bob

Pairs:
  Alice ═ Charlie (via link A-C)
  Charlie ═ Bob   (via link C-B)

After swapping:
  Alice ═══════════ Bob

Method: Bell measurement by Charlie on its qubits
```

### Implementation

```python
class AliceProgram(Program):
    @property
    def meta(self):
        return ProgramMeta(epr_sockets=[("Charlie", 1)])
    
    def run(self, context):
        epr = context.epr_sockets[("Charlie", 1)]
        qubit = epr.create_keep()[0]
        # Wait for correction
        csocket = context.csockets["Charlie"]
        m1 = yield from csocket.recv_int()
        m2 = yield from csocket.recv_int()
        # Apply corrections if needed
        if m1 == 1:
            qubit.X()
        if m2 == 1:
            qubit.Z()
        yield from context.connection.flush()

class CharlieProgram(Program):
    @property
    def meta(self):
        return ProgramMeta(
            epr_sockets=[("Alice", 1), ("Bob", 2)],
            csockets=["Alice", "Bob"]
        )
    
    def run(self, context):
        # Get EPR qubits from both sides
        q1 = context.epr_sockets[("Alice", 1)].recv_keep()[0]
        q2 = context.epr_sockets[("Bob", 2)].create_keep()[0]
        
        # Bell measurement
        q1.cnot(q2)
        q1.H()
        m1 = q1.measure()
        m2 = q2.measure()
        
        yield from context.connection.flush()
        
        # Send measurement results for correction
        context.csockets["Alice"].send_int(int(m1))
        context.csockets["Alice"].send_int(int(m2))

class BobProgram(Program):
    @property
    def meta(self):
        return ProgramMeta(epr_sockets=[("Charlie", 2)])
    
    def run(self, context):
        epr = context.epr_sockets[("Charlie", 2)]
        qubit = epr.recv_keep()[0]
        # Qubit is now entangled with Alice (at distance)
        yield from context.connection.flush()
```

---

## Multi-Pair Operations

Generating many EPR pairs efficiently.

### Batched Generation

```python
def run(self, context: ProgramContext):
    epr_socket = context.epr_sockets[("Bob", 1)]
    connection = context.connection
    
    # Request many pairs at once
    qubits = epr_socket.create_keep(number=100)
    
    # Apply same operation to all
    for q in qubits:
        q.H()
    
    # Single flush - efficient!
    yield from connection.flush()
    
    # Measure all
    results = [q.measure() for q in qubits]
    yield from connection.flush()
    
    measurements = [int(r) for r in results]
    return {"measurements": measurements}
```

### Sequential Generation

For very large numbers or memory constraints:

```python
def run(self, context: ProgramContext):
    epr_socket = context.epr_sockets[("Bob", 1)]
    connection = context.connection
    
    all_measurements = []
    
    # Generate in batches
    for batch in range(10):
        qubits = epr_socket.create_keep(number=10)
        
        for q in qubits:
            q.H()
        
        results = [q.measure() for q in qubits]
        yield from connection.flush()
        
        all_measurements.extend([int(r) for r in results])
    
    return {"measurements": all_measurements}
```

---

## EPR Performance and Fidelity

### Fidelity Impact

EPR pair fidelity degrades due to:

1. **Photon losses**: Not all photons reach destination
2. **Detection errors**: Imperfect detectors
3. **Decoherence**: Qubits decay before delivery
4. **Gate errors**: Corrections may introduce errors

Lower fidelity → noisier correlations:

```
Fidelity = 1.0:  Measurements perfectly correlated (0,0) or (1,1)
Fidelity = 0.95: 95% chance of correct correlation
Fidelity = 0.8:  Random walk, hard to use
```

### Success Probability

Not all generation attempts succeed:

```python
# With prob_success = 0.8
epr_socket.create_keep(number=100)

# Expected successful: 80 pairs
# Failed: 20 pairs (no qubit generated)
```

Handling failures:

```python
def run(self, context: ProgramContext):
    epr_socket = context.epr_sockets[("Bob", 1)]
    connection = context.connection
    
    # Request more pairs to account for failures
    total_requested = 100
    expected_success = int(100 * 0.8)  # 80% success
    
    qubits = epr_socket.create_keep(number=total_requested)
    
    # Use only the valid qubits
    valid_qubits = [q for q in qubits if q is not None]
    
    yield from connection.flush()
```

---

## Common EPR Patterns

### Pattern 1: Simple Bell Test

```python
def alice_run(self, context):
    epr = context.epr_sockets[("Bob", 1)]
    q = epr.create_keep()[0]
    q.H()
    m = q.measure()
    yield from context.connection.flush()
    context.csockets["Bob"].send_int(int(m))

def bob_run(self, context):
    epr = context.epr_sockets[("Alice", 1)]
    q = epr.recv_keep()[0]
    q.H()
    m = q.measure()
    yield from context.connection.flush()
    alice_m = yield from context.csockets["Alice"].recv_int()
    
    # Both should have same measurement
    correlation = int(m) == alice_m
    return {"correlation": correlation}
```

### Pattern 2: Quantum Teleportation

```python
def sender_run(self, context):
    # Teleport a qubit to receiver
    epr = context.epr_sockets[("Receiver", 1)]
    teleport_q = prepare_qubit()
    epr_q = epr.create_keep()[0]
    
    # Bell measurement
    teleport_q.cnot(epr_q)
    teleport_q.H()
    m1 = teleport_q.measure()
    m2 = epr_q.measure()
    yield from context.connection.flush()
    
    # Send corrections
    context.csockets["Receiver"].send_int(int(m1))
    context.csockets["Receiver"].send_int(int(m2))

def receiver_run(self, context):
    epr = context.epr_sockets[("Sender", 1)]
    q = epr.recv_keep()[0]
    
    # Wait for correction
    m1 = yield from context.csockets["Sender"].recv_int()
    m2 = yield from context.csockets["Sender"].recv_int()
    
    # Apply corrections
    if m2 == 1:
        q.Z()
    if m1 == 1:
        q.X()
    
    yield from context.connection.flush()
```

---

## Next Steps

- [Classical Communication](./classical_communication.md) - Message passing
- [NetQASM Programming](./netqasm.md) - Quantum operations
- [Teleportation Tutorial](../tutorials/applications_teleport.md) - Detailed example
