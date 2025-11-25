# Foundations Documentation Index

Conceptual guides for key SquidASM systems and quantum network concepts.

## Core Concepts

### [NetQASM and Quantum Programming](./netqasm.md)
Understanding the quantum instruction queue model and how quantum operations are compiled and executed.

**Topics**:
- NetQASM language and instruction model
- Instruction queuing and flush operations
- Future objects and delayed execution
- Control flow with Futures
- Subroutine structure and inspection
- Common patterns and debugging

### [EPR Sockets and Entanglement Generation](./epr_sockets.md)
Creating and managing quantum entangled pairs between nodes.

**Topics**:
- EPR pair basics and Bell states
- EPR socket API (create_keep, recv_keep)
- Socket ID management and virtual qubit mapping
- Synchronization and blocking semantics
- Bell state measurements
- Entanglement swapping
- Multi-pair operations and batching
- Performance and fidelity considerations

### [Classical Communication](./classical_communication.md)
Point-to-point classical message passing between nodes.

**Topics**:
- Classical socket API and send/recv semantics
- Link types (instant, configurable delay)
- Synchronization and deadlock prevention
- Message ordering (FIFO)
- Common communication patterns
- Data encoding and serialization
- Network topologies
- Integration with quantum operations

### [Logging System](./logging.md) *(Coming soon)*
Debugging and monitoring SquidASM simulations.

## Quick Reference

| Concept | Location | Key Points |
|---------|----------|-----------|
| **Quantum Operations** | NetQASM | Operations queued until `flush()` |
| **Measurement Results** | NetQASM | Returns `Future` objects |
| **Entanglement** | EPR Sockets | Sender uses `create_keep()`, receiver uses `recv_keep()` |
| **Classical Messages** | Classical Communication | Sender: `send()` (non-blocking), Receiver: `yield from recv()` (blocking) |
| **Synchronization** | All | Explicit coordination required between nodes |

## Learning Path

**New to SquidASM?**
1. Start with [NetQASM and Quantum Programming](./netqasm.md)
2. Learn about [EPR Sockets and Entanglement](./epr_sockets.md)
3. Understand [Classical Communication](./classical_communication.md)
4. Apply concepts in [Program Interface](../api/program_interface.md)

**Troubleshooting?**
1. Check [Logging System](./logging.md) for debugging
2. Review pattern sections in each foundation document
3. Look at [Tutorial Examples](../tutorials/index.md)

**Advanced Topics?**
1. [Context and Network Stack](../api/context_and_stack.md)
2. [Configuration Guide](../api/configuration.md)
3. [Architecture Overview](../architecture/overview.md)

---

## Common Mistakes and Solutions

### Mistake: Using Futures Before Flush
**Foundation**: [NetQASM - Future Objects](./netqasm.md#future-objects)

```python
# ❌ WRONG
result = qubit.measure()
if int(result) == 0:  # Error!

# ✅ CORRECT
result = qubit.measure()
yield from connection.flush()
if int(result) == 0:  # OK
```

### Mistake: Receiver Not Waiting for EPR
**Foundation**: [EPR Sockets - Synchronization](./epr_sockets.md#two-node-epr-coordination)

```python
# ❌ WRONG
alice_creates = epr_socket.create_keep()
bob_waits = epr_socket.recv_keep()  # Wrong! Different sockets

# ✅ CORRECT
# Declared in meta
epr_sockets=[("Alice", 1), ("Bob", 1)]

# Both use same socket ID
creator_qubits = context.epr_sockets[("Bob", 1)].create_keep()
receiver_qubits = context.epr_sockets[("Alice", 1)].recv_keep()
```

### Mistake: Classical Deadlock
**Foundation**: [Classical Communication - Synchronization](./classical_communication.md#deadlock-prevention)

```python
# ❌ WRONG - Both waiting!
alice: message = yield from socket.recv()
bob: message = yield from socket.recv()

# ✅ CORRECT - One sends, one receives
alice: socket.send("Hello")
bob: message = yield from socket.recv()
```

### Mistake: Forgetting yield from
**Foundation**: [Classical Communication - Receiving Messages](./classical_communication.md#receiving-messages)

```python
# ❌ WRONG - Returns coroutine
message = csocket.recv()

# ✅ CORRECT
message = yield from csocket.recv()
```

---

## Key Takeaways

### 1. Asynchronous Execution Model
- All quantum operations are **queued**, not executed immediately
- Must call `connection.flush()` to trigger compilation and execution
- Futures are placeholders that resolve after flush

### 2. Explicit Synchronization
- Sender/receiver pairs must be coordinated
- EPR creation requires matching socket declarations
- Classical messages require matching send/receive pairs

### 3. Blocking vs Non-Blocking
- **Non-blocking**: `send()` (queues immediately)
- **Blocking**: `yield from recv()`, `yield from connection.flush()`
- **Blocking requires yield from**: Asynchronous programming model

### 4. Network Awareness
- Programs are distributed across nodes
- All inter-node communication must be explicit (sockets)
- Timing matters (link latencies, gate times, etc.)

---

## References

- [Architecture Overview](../architecture/overview.md) - System design
- [API Documentation](../api/index.md) - Function and class references
- [Tutorial Examples](../tutorials/index.md) - Practical examples
- [Configuration Guide](../api/configuration.md) - Network setup

