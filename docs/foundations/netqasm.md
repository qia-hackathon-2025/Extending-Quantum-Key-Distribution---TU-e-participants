# Foundations: NetQASM and Quantum Programming

Understanding the quantum programming language underlying SquidASM applications.

---

## What is NetQASM?

NetQASM is a **Network Quantum Assembly Language** designed for programming quantum network processing units (QNPU).

### Design Philosophy

- **Assembly-like**: Low-level control over quantum operations
- **Network-aware**: Explicit entanglement and remote operations
- **Hardware-agnostic**: Same code runs on different QNPU implementations
- **Compiled**: Applications compile to NetQASM before execution

### NetQASM vs OpenQASM

| Feature | NetQASM | OpenQASM |
|---------|---------|----------|
| **Target** | Quantum networks (distributed) | Quantum computers (centralized) |
| **Entanglement** | Native, explicit | Not supported |
| **Communication** | Built-in (remote ops) | Not applicable |
| **Control Flow** | NetQASM-based | Native classical control |
| **Gates** | Device-dependent | Universal set |

---

## The Instruction Queue Model

The most important concept for understanding NetQASM in SquidASM.

### How Instructions Work

When you write:

```python
qubit.H()
qubit.X()
result = qubit.measure()
```

These operations don't execute immediately. Instead:

1. **H() call**: Registers "apply Hadamard to qubit" in connection queue
2. **X() call**: Registers "apply X to qubit" in connection queue
3. **measure() call**: Registers "measure qubit" and returns a `Future`

### The Flush Operation

```python
yield from connection.flush()
```

This triggers:

1. **Compilation**: All queued instructions → NetQASM code
2. **Transmission**: Send compiled code to QNPU
3. **Execution**: QNPU executes the subroutine
4. **Result Collection**: Results written to shared memory
5. **Future Resolution**: `Future` objects get actual values

### Why Queue Instructions?

```
Why not execute immediately?
└─ Physical constraint: Host and QNPU are separate devices
   └─ Communication latency between host and quantum device
   └─ Batch compilation is more efficient
   └─ Enables atomic execution of subroutines
```

### Visualization

```
Time →

Application:  H   X   measure  |  flush()      |  print(result)
              │   │   │         │               │
Connection:   ├───┴───┴─────────┤               │
              Queue state:      │ Compile & send│ Receive & resolve
              [H, X, measure]   │               │
                                │               │
QNPU:                           ├─ Execute ────┤
                                ├─ Measure ────┤
                                └─ Return ─────┤
```

---

## Future Objects

The key to understanding delayed execution.

### What is a Future?

A placeholder for a value that will exist after `flush()`:

```python
# Before flush
result = qubit.measure()  # result is a Future object
print(type(result))       # <class 'netqasm.sdk.future.Future'>
print(result)             # <Future>  (not a number!)

# After flush
yield from connection.flush()
print(int(result))        # 0 or 1 (now a number)
```

### Future Restrictions

Before `flush()`, cannot:

```python
# ❌ WRONG - Cannot use in Python if statement
result = qubit.measure()
if int(result) == 0:  # Error! int(result) fails
    pass

# ❌ WRONG - Cannot print
result = qubit.measure()
print(result)  # Prints "<Future>" not the value

# ❌ WRONG - Cannot use in arithmetic
result = qubit.measure()
value = result + 1  # Error! Can't add to Future
```

### After Flush

After `yield from connection.flush()`:

```python
result = qubit.measure()
yield from connection.flush()

# NOW safe to use as normal integer
if int(result) == 0:
    print("Measured 0")
else:
    print("Measured 1")

measurements = [int(result) for result in [m1, m2, m3]]
```

---

## Control Flow with Futures

NetQASM requires special handling for conditional logic.

### The Problem

Cannot use native Python `if/for/while` with Futures:

```python
# ❌ WRONG
qubit = Qubit(connection)
result = qubit.measure()
if result == 0:  # Won't work! result is Future
    qubit.X()

yield from connection.flush()
```

### The Solution: NetQASM SDK Methods

Use SDK methods for control flow on Futures:

```python
from netqasm.sdk.qubit import Qubit

def run(self, context: ProgramContext):
    connection = context.connection
    qubit = Qubit(connection)
    
    # Get measurement result
    result = qubit.measure()
    
    # Define branches as separate functions
    def apply_x():
        qubit.X()
    
    def apply_y():
        qubit.Y()
    
    # Conditional execution based on Future
    connection.if_eq(result, 0, apply_x)
    connection.if_neq(result, 0, apply_y)
    
    yield from connection.flush()
```

### For Loops Before Flush

Similarly, cannot use Python `for` with unknown iteration count:

```python
# ❌ WRONG
measurements = [q.measure() for q in qubits]  # OK so far
for m in measurements:
    if int(m) == 0:  # Error! m is Future
        ...
```

### Solution: Flush First, Then Loop

```python
# ✅ CORRECT
measurements = [q.measure() for q in qubits]
yield from connection.flush()

# Now safe to iterate
for m in measurements:
    print(int(m))
```

---

## Subroutine Structure

### What is a Subroutine?

The compiled quantum code sent to the QNPU:

```
Subroutine (binary format)
├─ Metadata
│  ├─ NetQASM version
│  ├─ App ID
│  └─ Virtual qubit mapping
│
├─ Instructions
│  ├─ Load constants
│  ├─ Allocate memory arrays
│  ├─ Gate operations
│  ├─ Measurements
│  └─ Wait/synchronization
│
└─ Return
   └─ Measurement results
```

### Inspecting Subroutines

```python
def run(self, context: ProgramContext):
    connection = context.connection
    qubit = Qubit(connection)
    
    # Queue operations
    qubit.H()
    qubit.X()
    result = qubit.measure()
    
    # Compile without executing
    subroutine = connection.compile()
    
    # View the subroutine
    print(subroutine)
    # Output:
    # Subroutine
    # NetQASM version: (0, 10)
    # App ID: 0
    #  LN | HLN | CMD
    #   0    ()  set R1 10
    #   1    ()  array R1 @0
    #   ...
    #  20    ()  set Q0 0
    #  21    ()  h Q0
    #  22    ()  x Q0
    #  23    ()  meas Q0 M0
    #  ...
    
    # Now execute the compiled subroutine
    yield from connection.commit_subroutine(subroutine)
```

### Memory Arrays in Subroutines

Subroutines use memory arrays for:

```
@0: EPR generation results (10 elements per pair)
@1: Measurement results
@2: Intermediate values
@3: Custom data

Access: @array[start:end]
```

---

## Wait Operations

Synchronization points in NetQASM.

### EPR Pair Creation

When creating EPR pairs, the code must wait for completion:

```python
epr_socket = context.epr_sockets[("Bob", 1)]
qubits = epr_socket.create_keep(number=3)

# Behind the scenes:
# 1. Send EPR request to remote node
# 2. Wait for completion (could take time)
# 3. Map virtual qubits to physical qubits
# 4. Make qubits available to application

# Must flush before using qubits
yield from connection.flush()

# Now qubits are ready for operations
for q in qubits:
    q.H()
```

### Wait Operations in NetQASM

```netqasm
// Allocate results array
array 10 @0

// Send EPR request
create_epr (1,0) 1 2 0

// Wait for results to be available
wait_all @0[0:10]

// Now we can use the qubits
```

---

## The NetQASM-SquidASM Connection

### Flow from Application to QNPU

```
Python Application Code
    ↓
NetQASM SDK (qubit.H(), socket.create_keep(), etc.)
    ↓
Connection.flush()
    ↓
Compile to NetQASM proto format
    ↓
Send subroutine to QNOSHandler
    ↓
Decode and execute on QuantumProcessor
    ↓
Return results
    ↓
Resolve Futures with actual values
```

### What SquidASM Doesn't Support

Some NetQASM features are not yet supported in SquidASM:

- ❌ Custom measurement bases (non-Z basis) - limited support
- ❌ Arbitrary waveforms
- ❌ Some advanced control flow patterns
- ❌ Direct low-level NetQASM code

**Recommendation**: Stick to patterns shown in tutorials and documentation.

---

## Common NetQASM Patterns in SquidASM

### Pattern 1: Prepare, Measure, Return

```python
def run(self, context: ProgramContext):
    connection = context.connection
    
    # Prepare state
    qubit = Qubit(connection)
    qubit.H()
    qubit.Z()
    
    # Measure
    result = qubit.measure()
    
    # Flush and return
    yield from connection.flush()
    return {"result": int(result)}
```

**Compiled NetQASM**:
```netqasm
set Q0 0        # Initialize qubit 0
h Q0            # Apply Hadamard
z Q0            # Apply Z
meas Q0 M0      # Measure to register M0
ret reg M0      # Return measurement result
```

### Pattern 2: Multi-Qubit Entanglement

```python
def run(self, context: ProgramContext):
    epr_socket = context.epr_sockets[("Alice", 1)]
    connection = context.connection
    
    # Create EPR pairs
    qubits = epr_socket.create_keep(number=2)
    
    # Apply operations
    qubits[0].H()
    qubits[0].cnot(qubits[1])
    
    # Measure
    results = [q.measure() for q in qubits]
    
    yield from connection.flush()
    return {"results": [int(r) for r in results]}
```

### Pattern 3: Conditional Operations

```python
def run(self, context: ProgramContext):
    connection = context.connection
    qubit = Qubit(connection)
    
    result = qubit.measure()
    
    # Conditional gate based on measurement
    def apply_correction():
        qubit.X()
    
    connection.if_eq(result, 1, apply_correction)
    
    yield from connection.flush()
```

---

## Performance Considerations

### Compilation Overhead

Large subroutines take longer to compile:

```python
# ✅ EFFICIENT: Batch operations
qubits = [Qubit(connection) for _ in range(100)]
for q in qubits:
    q.H()

yield from connection.flush()  # Single compilation


# ❌ INEFFICIENT: Multiple flushes
for _ in range(100):
    qubit = Qubit(connection)
    qubit.H()
    yield from connection.flush()  # 100 compilations!
```

### Execution Time

Time in subroutine depends on:
- Gate operations (10-100 ns each)
- Measurements (100-500 ns)
- EPR generation (1-100 µs)
- Decoherence (T1/T2 dependent)

### Memory Usage

Arrays in subroutine:
- Small arrays (<100 elements): negligible
- Large arrays (>10,000): can impact performance

---

## Debugging NetQASM Code

### Print Compiled Subroutine

```python
subroutine = connection.compile()
print(f"Subroutine:\n{subroutine}")
```

### Enable Detailed Logging

```python
from squidasm.sim.stack.common import LogManager

LogManager.set_log_level("DEBUG")
LogManager.log_to_file("netqasm.log")

# Run simulation - detailed logs will show subroutine execution
results = run(config=cfg, programs=programs, num_times=1)
```

### Log File Output

```
DEBUG:44000.0 ns:Stack.Handler:Compiling subroutine
DEBUG:44000.0 ns:Stack.Handler:Subroutine...
DEBUG:44000.0 ns:Stack.Processor:Executing set Q0 0
DEBUG:44000.0 ns:Stack.Processor:Executing h Q0
DEBUG:44000.0 ns:Stack.Processor:Executing meas Q0 M0
DEBUG:44000.0 ns:Stack.Handler:Subroutine completed
```

---

## Connection Methods Reference

### Basic Operations

```python
connection = context.connection

# Create local qubit
qubit = Qubit(connection)

# Flush operations
yield from connection.flush()

# Compile without executing
subroutine = connection.compile()

# Execute pre-compiled subroutine
yield from connection.commit_subroutine(subroutine)
```

### Control Flow Methods

```python
# Conditional execution
connection.if_eq(future_value, constant, body_function)
connection.if_neq(future_value, constant, body_function)

# Looping
for i in range(n):  # Native Python loop is OK
    qubit.H()

# Note: Cannot loop on Future count
results = [q.measure() for q in qubits]
yield from connection.flush()
for result in results:  # Loop after flush is OK
    print(int(result))
```

---

## References and Further Reading

- [NetQASM GitHub](https://github.com/QuTech-Delft/netqasm)
- [NetQASM SDK Documentation](https://netqasm.readthedocs.io/)
- [NetQASM Paper](https://pure.tudelft.nl/ws/portalfiles/portal/131483787/Dahlberg_2022_Quantum_Sci._Technol._7_035023.pdf)

---

## Next Steps

- [EPR Sockets and Entanglement](./epr_sockets.md) - Generating entangled pairs
- [Classical Communication](./classical_communication.md) - Message passing
- [Program Interface](../api/program_interface.md) - Writing complete programs
