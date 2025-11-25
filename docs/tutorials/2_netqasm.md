# Tutorial 2: NetQASM

In this section we go into details of NetQASM and its role for writing applications that can be simulated using SquidASM. We explain the NetQASMConnection object and the importance of `connection.flush()`.

## NetQASM Language

NetQASM is an instruction set architecture that allows one to interface with quantum network processing units (QNPU) and run applications on a quantum network. Its name refers to it being a **net**work **q**uantum **asm**embly language.

As an assembly language, it looks similar to classical assembly languages. It is also similar to OpenQASM, which is a quantum computing assembly language.

### Example NetQASM Code

An example of NetQASM code from the [paper introducing NetQASM](https://pure.tudelft.nl/ws/portalfiles/portal/131483787/Dahlberg_2022_Quantum_Sci._Technol._7_035023.pdf):

```
array 10 @0                   // array for writing EPR results to
array 1 @1                    // array with virtual IDs for entangled qubits
store 0 @1 [0]                // set virtual ID of the only generated qubit to 0
array 20 @2                   // array for holding EPR request parameters
store 0 @2[0]                 // set request type to 0 (Create and Keep)
store 1 @2 [1]                // set number of requested EPR pairs to 1
create epr (1,0) 1 2 0        // send command to create EPR pair
wait_all @0 [0:10]            // wait until results for first pair (10 elements) are available
set Q0 0
meas Q0 M0                    // measure the entangled qubit
qfree Q0
ret reg M0                    // return measurement outcome
```

### User Programming Model

Users are not expected to directly create NetQASM routines. The NetQASM SDK allows one to construct a routine programmatically via Python. However, this programmatic construction may cause some confusion.

When you execute commands like:

```python
q = (yield from epr_socket.create_keep(1))[0]
q.H()
result = q.measure()
```

You might expect that the EPR pair is immediately generated and measured. **This is not the case!**

These commands only register these actions to the "queue" of the NetQASM SDK for the current node. The actual compilation and transmission of these instructions occur only when you call `connection.flush()`.

## The NetQASM Connection

The NetQASM connection is the central interaction point for a program. The connection is responsible for:

1. **Compiling** Python SDK instructions into NetQASM code
2. **Transmitting** the compiled code to the QNPU
3. **Executing** the instructions on the QNPU
4. **Collecting** the results

### Connection Object

The object is called `connection` in this tutorial, but is a `BaseNetQASMConnection` type object. The name "connection" refers to the fact that the host and QNPU are not the same device, so the NetQASMConnection object represents the link and the ability of the host to send instructions to the QNPU.

### Inspecting Compiled Subroutines

The NetQASM SDK provides methods to compile and inspect instructions before sending them to the QNPU:

```python
# Compile instructions to subroutine
subroutine = connection.compile()
print(f"Subroutine:\n\n{subroutine}\n")

# Send subroutine to QNPU
yield from connection.commit_subroutine(subroutine)
```

### Example Output

When you compile Alice's program from the Basics tutorial, you get output like:

```
Subroutine
NetQASM version: (0, 10)
App ID: 0
 LN | HLN | CMD
   0    () set R1 10
   1    () array R1 @0
   2    () set R1 1
   3    () array R1 @1
   4    () set R1 0
   ....
  20    () set R8 2
  21    () set R9 0
  22    () create_epr R1 R2 R7 R8 R9
   ....
  44    () jmp 39
  45    () wait_all @0[R3:R5]
  46    () set R1 0
   ....
  56    () set Q0 0
  57    () h Q0
  58    () set Q0 0
  59    () meas Q0 M0
  60    () qfree Q0
  61    () set R1 0
  62    () store M0 @3[R1]
   ....
```

### Important Note on Connection References

For a user, it could be that little direct interaction happens with the `connection` object other than `connection.flush()` and initialization for local qubits `local_qubit = Qubit(connection)`. However, the connection is actually the central interaction point for a program.

When a command on a qubit or EPR socket is invoked, it forwards these instructions (with some ID of the object attached) to the `connection`. Thus all these objects have a reference to `connection` in their backend, and why qubit initialization requires the `connection` object.

## Future Objects

An important consequence of the instruction queue model is that all instructions and their results have not happened before the subroutine is sent to the QNPU.

Therefore, the output variable `result` of a measure operation does not yet contain the result of the measurement after `result = qubit.measure()` has been executed in the Python code. `result` only has a value after `yield from connection.flush()` is executed.

### Dealing with Futures

To handle this situation, the output of `qubit.measure()` is a `netqasm.sdk.future.Future` object. These objects behave like a placeholder or pointer before the flush, but as a normal integer after the flush.

Due to this, many operations using a `Future` object will cause an error if done before a flush:

```python
# This will cause an error!
@classmethod
def meta(cls) -> ProgramMeta:
    return ProgramMeta(name="Alice")

def run(self, context: ProgramContext) -> Generator:
    connection = context.connection
    
    q = Qubit(connection)
    q.X()
    result = q.measure()
    
    # These will all fail with AttributeError
    if result == 1:  # ERROR: Can't use Future in if statement
        pass
    
    x = result + 1   # ERROR: Can't do arithmetic with Future
    
    print(result)    # ERROR: Can't print Future properly
    
    # yield from connection.flush()  # This line would fix it!
```

Attempting to execute this code results in:

```
AttributeError: 'NoneType' object has no attribute 'get_array_part'
```

### Future Restrictions Before Flush

The following operations are **not** permitted with Future objects before a flush:

- Using Future in native Python `if`, `for`, or `while` statements
- Arithmetic operations on Futures
- Direct printing or string conversion
- Comparisons in conditional expressions
- Using Futures in functions expecting concrete values

## Control Flow with Futures

Native Python control flow statements do not translate into the NetQASM routine sent to the QNPU. For example:

```python
# This does NOT work as expected
result = q.measure()
if result == 1:  # This is evaluated in Python, not in the QNPU
    q.X()
```

To create NetQASM routines with control flow, special methods in the NetQASM SDK must be used. The most common is `if_eq(a, b, body)`, which is a method of the `BaseNetQASMConnection` object.

### Example: Conditional Operations

```python
def conditional_operation(connection, q):
    result = q.measure()
    
    # Define the body of the conditional
    def body():
        q.X()
        q.H()
    
    # Execute body only if result == 1
    yield from connection.if_eq(result, 1, body)
    yield from connection.flush()
```

For more details on control flow operations, consult the [NetQASM SDK tutorial](https://netqasm.readthedocs.io/en/latest/quickstart/using-sdk.html#simple-classical-logic).

## Unsupported Features

### Important Warning

The NetQASM language supports many features, such as specifying the measurement basis in a measurement, but **not all of these features are currently supported in SquidASM**. It is advisable to be careful when using features not shown in this tutorial.

Examples of potentially unsupported features:

- Measurement basis specification (only computational basis supported)
- Advanced control flow constructs
- Specialized qubit rotations with uncommon parameters
- Features added in recent NetQASM versions

When in doubt, test your code with simple examples first and refer to the SquidASM examples in `examples/tutorial` for patterns that are known to work.

## Common Patterns

### Pattern 1: EPR Creation and Measurement

```python
def pattern_epr_create_measure(epr_socket, connection):
    # Create EPR pair
    q = (yield from epr_socket.create_keep(1))[0]
    
    # Apply gates
    q.H()
    q.Z()
    
    # Measure
    result = q.measure()
    
    # Get result
    yield from connection.flush()
    
    return result
```

### Pattern 2: Multiple Qubits with Gates

```python
def pattern_multi_qubit(connection):
    q0 = Qubit(connection)
    q1 = Qubit(connection)
    
    # Initialize and entangle
    q0.X()
    q1.X()
    q0.H()
    q0.cnot(q1)
    
    # Measure both
    r0 = q0.measure()
    r1 = q1.measure()
    
    yield from connection.flush()
    
    return r0, r1
```

### Pattern 3: EPR Receive and Measure

```python
def pattern_epr_receive_measure(epr_socket, connection):
    # Wait for and receive EPR pair
    q = (yield from epr_socket.recv_keep(1))[0]
    
    # Apply operations
    q.H()
    
    # Measure
    result = q.measure()
    
    # Get result
    yield from connection.flush()
    
    return result
```

## Summary

In this section you learned:

- **NetQASM** is an instruction set architecture for quantum network programming
- The **instruction queue model** where operations are queued and executed on `flush()`
- **Future objects** are placeholders for measurement results that only become concrete values after flushing
- **Control flow** with Futures requires special SDK methods like `if_eq()`
- How to **compile and inspect** subroutines before execution
- **Patterns** for common operations like EPR creation and multi-qubit gates
- **Restrictions** on what operations are supported in SquidASM

The next section will explain how to run simulations, get output from programs, and use logging for debugging.
