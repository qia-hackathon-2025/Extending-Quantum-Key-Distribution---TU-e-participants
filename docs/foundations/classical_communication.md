# Foundations: Classical Communication

Understanding message passing between quantum network nodes.

---

## Classical Sockets Overview

Classical sockets provide point-to-point communication channels for sending and receiving classical information (bits) between nodes.

### What is a Classical Socket?

A classical socket represents an **open connection to a peer node**:

- **One-directional per socket**: One socket for sending, another for receiving
- **Point-to-point**: Connects two specific nodes
- **Ordered**: Messages sent first are received first (FIFO)
- **Reliable**: Messages are not lost (in simulation)
- **Latency**: Configurable delay per message

### Network Configuration

Classical links are specified in network configuration:

```yaml
clinks:
  - stack1: Alice
    stack2: Bob
    typ: instant        # Or "default" with delay
    cfg:
      # Configuration (if needed)
```

---

## Classical Socket API

### ClassicalSocket Methods

Located in `squidasm.sim.stack.csocket`:

```python
class ClassicalSocket:
    """Point-to-point classical communication."""
    
    def send(self, msg: str) -> None:
        """Send a string message.
        
        Non-blocking. Message is queued immediately.
        """
    
    def send_int(self, value: int) -> None:
        """Send an integer.
        
        Convenience method for integer transmission.
        """
    
    def recv(self):
        """Receive a string message.
        
        Blocking - requires yield from.
        Waits until message arrives.
        """
    
    def recv_int(self):
        """Receive an integer.
        
        Blocking - requires yield from.
        """
```

### Sending Messages

```python
def run(self, context: ProgramContext):
    csocket = context.csockets["Alice"]
    
    # Send string
    csocket.send("Hello Alice")
    
    # Send integer
    csocket.send_int(42)
    
    # Send multiple messages - all queued immediately
    for i in range(10):
        csocket.send_int(i)
    
    # Non-blocking - program continues immediately
    print("Message sent!")
```

### Receiving Messages

```python
def run(self, context: ProgramContext):
    csocket = context.csockets["Bob"]
    
    # Receive string - BLOCKING
    message = yield from csocket.recv()
    print(f"Received: {message}")
    
    # Receive integer
    value = yield from csocket.recv_int()
    print(f"Value: {value}")
    
    # Receive multiple in sequence
    values = []
    for i in range(10):
        v = yield from csocket.recv_int()
        values.append(v)
```

### Key Semantics

1. **send() is non-blocking**: Returns immediately
2. **recv() is blocking**: Pauses execution until message arrives
3. **recv() requires `yield from`**: Async/await pattern
4. **Order preserved**: First sent = first received (FIFO)
5. **Type matching**: Use `send_int()` with `recv_int()`, etc.

---

## Classical Link Types

### Instant Link (Zero Latency)

```yaml
clinks:
  - stack1: Alice
    stack2: Bob
    typ: instant
```

**Behavior**: Messages transmitted with zero simulation time delay.

**Use Cases**:
- Testing logic without latency effects
- Assuming perfect classical channels
- Debugging network protocols

```python
# Example timing
Alice: send_int(42)  # t=1000 ns
Bob: yield from recv_int()  # Returns immediately at t=1000 ns
```

### Default Link (Configurable Delay)

```yaml
clinks:
  - stack1: Alice
    stack2: Bob
    typ: default
    cfg:
      delay: 1000.0  # Nanoseconds
```

**Behavior**: Fixed latency for each message.

**Parameters**:
- **delay**: One-way transmission delay in nanoseconds
  - 1000 ns = 1 microsecond
  - 100,000 ns = 100 microseconds
  - Models fiber distance: distance (m) / 2e5 = delay (ns)

```python
# Example with 1000 ns delay
Alice: send_int(42)         # t=1000 ns
Bob: yield from recv_int()  # Receives at t=2000 ns (1000 ns delay)
```

---

## Synchronization and Ordering

### Send-Receive Pairing

Must coordinate send/receive operations:

```python
class AliceProgram(Program):
    def run(self, context):
        csocket = context.csockets["Bob"]
        
        # Alice sends, then waits for response
        csocket.send("Request")
        response = yield from csocket.recv()

class BobProgram(Program):
    def run(self, context):
        csocket = context.csockets["Alice"]
        
        # Bob receives, then responds
        message = yield from csocket.recv()
        csocket.send("Response")
```

### Deadlock Prevention

**Rule**: Must have symmetric protocol design.

```python
# ❌ WRONG - Will deadlock!
class AliceProgram(Program):
    def run(self, context):
        csocket = context.csockets["Bob"]
        message = yield from csocket.recv()  # Waiting for Bob

class BobProgram(Program):
    def run(self, context):
        csocket = context.csockets["Alice"]
        message = yield from csocket.recv()  # Also waiting for Alice
        # Neither sends - DEADLOCK!
```

```python
# ✅ CORRECT - Symmetric protocol
class AliceProgram(Program):
    def run(self, context):
        csocket = context.csockets["Bob"]
        csocket.send("Data from Alice")
        response = yield from csocket.recv()

class BobProgram(Program):
    def run(self, context):
        csocket = context.csockets["Alice"]
        message = yield from csocket.recv()
        csocket.send("Data from Bob")
```

### Message Ordering (FIFO)

Messages are strictly ordered:

```python
def alice_run(self, context):
    csocket = context.csockets["Bob"]
    csocket.send_int(1)
    csocket.send_int(2)
    csocket.send_int(3)

def bob_run(self, context):
    csocket = context.csockets["Alice"]
    m1 = yield from csocket.recv_int()  # 1
    m2 = yield from csocket.recv_int()  # 2
    m3 = yield from csocket.recv_int()  # 3
    
    assert m1 == 1 and m2 == 2 and m3 == 3  # Always true
```

---

## Common Communication Patterns

### Pattern 1: Simple Request-Response

```python
class ClientProgram(Program):
    @property
    def meta(self):
        return ProgramMeta(name="Client", csockets=["Server"])
    
    def run(self, context):
        csocket = context.csockets["Server"]
        
        # Send request
        csocket.send_int(42)
        
        # Wait for response
        response = yield from csocket.recv_int()
        
        return {"response": response}

class ServerProgram(Program):
    @property
    def meta(self):
        return ProgramMeta(name="Server", csockets=["Client"])
    
    def run(self, context):
        csocket = context.csockets["Client"]
        
        # Wait for request
        request = yield from csocket.recv_int()
        
        # Process and send response
        response = request * 2
        csocket.send_int(response)
        
        return {}
```

### Pattern 2: Broadcasting Data

For multi-node networks, send to multiple peers:

```python
class PublisherProgram(Program):
    @property
    def meta(self):
        return ProgramMeta(name="Publisher", csockets=["Sub1", "Sub2", "Sub3"])
    
    def run(self, context):
        sockets = context.csockets
        
        data = 12345
        
        # Send to all subscribers
        sockets["Sub1"].send_int(data)
        sockets["Sub2"].send_int(data)
        sockets["Sub3"].send_int(data)

class SubscriberProgram(Program):
    def __init__(self, name):
        self.my_name = name
        self.pub_name = "Publisher"
    
    @property
    def meta(self):
        return ProgramMeta(name=self.my_name, csockets=[self.pub_name])
    
    def run(self, context):
        csocket = context.csockets[self.pub_name]
        data = yield from csocket.recv_int()
        return {"data": data}

# Usage
programs = {
    "Publisher": PublisherProgram(),
    "Sub1": SubscriberProgram("Sub1"),
    "Sub2": SubscriberProgram("Sub2"),
    "Sub3": SubscriberProgram("Sub3"),
}
```

### Pattern 3: Coordinating Quantum Operations

Combining EPR sockets with classical sockets for Bell measurements:

```python
class MeasurerProgram(Program):
    """Performs Bell measurement and sends results."""
    
    @property
    def meta(self):
        return ProgramMeta(
            name="Measurer",
            epr_sockets=[("NodeA", 1), ("NodeB", 2)],
            csockets=["NodeA", "NodeB"]
        )
    
    def run(self, context):
        # Get EPR qubits
        q_a = context.epr_sockets[("NodeA", 1)].recv_keep()[0]
        q_b = context.epr_sockets[("NodeB", 2)].create_keep()[0]
        
        # Bell measurement
        q_a.cnot(q_b)
        q_a.H()
        m1 = q_a.measure()
        m2 = q_b.measure()
        
        yield from context.connection.flush()
        
        # Send measurement results for correction
        context.csockets["NodeA"].send_int(int(m1))
        context.csockets["NodeA"].send_int(int(m2))

class CorrectionProgram(Program):
    """Receives Bell measurement results and applies corrections."""
    
    @property
    def meta(self):
        return ProgramMeta(
            name="NodeA",
            epr_sockets=[("Measurer", 1)],
            csockets=["Measurer"]
        )
    
    def run(self, context):
        # Get EPR qubit
        qubit = context.epr_sockets[("Measurer", 1)].create_keep()[0]
        
        # Wait for measurement results
        m1 = yield from context.csockets["Measurer"].recv_int()
        m2 = yield from context.csockets["Measurer"].recv_int()
        
        # Apply corrections
        if int(m1) == 1:
            qubit.X()
        if int(m2) == 1:
            qubit.Z()
        
        yield from context.connection.flush()
        
        return {"m1": m1, "m2": m2}
```

---

## Data Types and Encoding

### Supported Types

```python
# String messages
csocket.send("Hello World")
message = yield from csocket.recv()

# Integers
csocket.send_int(42)
value = yield from csocket.recv_int()

# Custom data via encoding
import json
data = {"key": "value", "number": 123}
csocket.send(json.dumps(data))
received = yield from csocket.recv()
parsed = json.loads(received)
```

### Encoding Complex Data

For complex data structures:

```python
import json

def alice_run(self, context):
    csocket = context.csockets["Bob"]
    
    # Complex data
    measurements = [0, 1, 1, 0, 1]
    config = {"fidelity": 0.95, "attempts": 1000}
    
    # Encode as JSON
    data = {"measurements": measurements, "config": config}
    csocket.send(json.dumps(data))

def bob_run(self, context):
    csocket = context.csockets["Alice"]
    
    # Decode JSON
    message = yield from csocket.recv()
    data = json.loads(message)
    
    measurements = data["measurements"]
    config = data["config"]
```

---

## Performance Considerations

### Send is Fast

```python
# Non-blocking - very fast
for i in range(1000):
    csocket.send_int(i)  # All queued immediately
# Program continues instantly
```

### Recv is Blocking

```python
# This pauses execution until message arrives
value = yield from csocket.recv_int()
# Execution resumes only when message is received
```

### Batching vs Sequential

```python
# ✅ EFFICIENT: Batch sends
for i in range(100):
    csocket.send_int(i)  # Fast - all non-blocking

# ❌ INEFFICIENT: Send and wait for each response
for i in range(100):
    csocket.send_int(i)
    response = yield from csocket.recv_int()  # Blocks each time
```

### Latency Impact

With configurable delays:

```yaml
clinks:
  - stack1: Alice
    stack2: Bob
    typ: default
    cfg:
      delay: 10000.0  # 10 microseconds per message
```

For 100 messages:
- Instant link: Total classical time = ~0
- 10 µs delay: Total time = ~1 millisecond (100 × 10 µs)

Consider using fewer, larger messages when latency is significant.

---

## Debugging Classical Communication

### Logging Socket Operations

```python
from squidasm.sim.stack.common import LogManager

logger = LogManager.get_stack_logger("MyProgram")

def run(self, context):
    csocket = context.csockets["Peer"]
    
    logger.info("About to send message")
    csocket.send_int(42)
    logger.info("Message sent")
    
    logger.info("Waiting for response")
    response = yield from csocket.recv_int()
    logger.info(f"Received: {response}")
```

### Checking Socket Availability

```python
def run(self, context):
    # Check what sockets are available
    print(f"Available sockets: {list(context.csockets.keys())}")
    
    if "Bob" in context.csockets:
        socket = context.csockets["Bob"]
    else:
        logger.error("Bob socket not available!")
```

### Common Issues

**Issue**: `KeyError` when accessing socket

```python
# ❌ WRONG - Didn't declare in meta
@property
def meta(self):
    return ProgramMeta(name="Alice")  # No csockets

def run(self, context):
    socket = context.csockets["Bob"]  # KeyError!

# ✅ CORRECT
@property
def meta(self):
    return ProgramMeta(name="Alice", csockets=["Bob"])
```

**Issue**: Program blocks waiting for message that never comes

```python
# Ensure both sides have matching protocol
class AliceProgram(Program):
    def run(self, context):
        # Alice sends first
        context.csockets["Bob"].send_int(42)

class BobProgram(Program):
    def run(self, context):
        # Bob receives first
        value = yield from context.csockets["Alice"].recv_int()
```

---

## Network Topologies

### Two-Node

```yaml
clinks:
  - stack1: Alice
    stack2: Bob
    typ: instant
```

```python
# Communication only between Alice and Bob
alice_sockets = {"Bob": socket_to_bob}
bob_sockets = {"Alice": socket_to_alice}
```

### Star Topology (Hub-Spoke)

```yaml
clinks:
  - stack1: Hub
    stack2: Node1
    typ: instant
  - stack1: Hub
    stack2: Node2
    typ: instant
  - stack1: Hub
    stack2: Node3
    typ: instant
```

```python
# Hub can communicate with all nodes
# Leaf nodes can only communicate with Hub
hub_sockets = {"Node1": ..., "Node2": ..., "Node3": ...}
node1_sockets = {"Hub": ...}
```

### Fully Connected (Mesh)

```yaml
clinks:
  - stack1: Alice
    stack2: Bob
    typ: instant
  - stack1: Alice
    stack2: Charlie
    typ: instant
  - stack1: Bob
    stack2: Charlie
    typ: instant
```

```python
# Every node can communicate with every other node
alice_sockets = {"Bob": ..., "Charlie": ...}
bob_sockets = {"Alice": ..., "Charlie": ...}
charlie_sockets = {"Alice": ..., "Bob": ...}
```

---

## Integration with Quantum Operations

Classical and quantum operations often work together:

```
EPR Generation        Classical Correction
      │                      ↑
      │    ┌─ Bell Measurement ─┐
      │    │                     │
    Qubit ─┴─ Qubit      Results  │
    Node1       Node2    Feedback  │
```

**Example**: Entanglement swapping requires both:

```python
# Quantum: Bell measurement
q1.cnot(q2)
q1.H()
m1 = q1.measure()
m2 = q2.measure()
yield from connection.flush()

# Classical: Send corrections
csocket.send_int(int(m1))
csocket.send_int(int(m2))
```

---

## Best Practices

### 1. Declare All Socket Requirements

```python
@property
def meta(self):
    # Declare all peers
    return ProgramMeta(
        name="MyNode",
        csockets=["PeerA", "PeerB", "PeerC"]
    )
```

### 2. Use `yield from` for recv()

```python
# ✅ CORRECT
message = yield from csocket.recv()

# ❌ WRONG - Will fail
message = csocket.recv()  # Returns coroutine, not message
```

### 3. Match send/recv Types

```python
# ✅ CORRECT - Type matching
csocket.send_int(42)
value = yield from csocket.recv_int()

# ❌ WRONG - Type mismatch
csocket.send_int(42)
message = yield from csocket.recv()  # Returns string, not int
```

### 4. Handle FIFO Ordering

```python
# Remember: FIFO ordering
# If you send: A, B, C
# You receive: A, B, C (in order)

csocket.send_int(1)
csocket.send_int(2)
csocket.send_int(3)

m1 = yield from csocket.recv_int()  # 1
m2 = yield from csocket.recv_int()  # 2
m3 = yield from csocket.recv_int()  # 3
```

### 5. Avoid Busy Waiting

```python
# ❌ WRONG - Busy waiting (wasted time)
while True:
    try:
        msg = receive_non_blocking()
        if msg:
            break
    except:
        pass

# ✅ CORRECT - Blocking receive
msg = yield from csocket.recv()  # Pauses until message arrives
```

---

## Next Steps

- [EPR Sockets](./epr_sockets.md) - Quantum communication
- [Program Interface](../api/program_interface.md) - Complete programs
- [Coordination Tutorial](../tutorials/2_netqasm.md) - Detailed examples
