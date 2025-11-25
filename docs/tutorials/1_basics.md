# Tutorial 1: Basics

In this section you will be introduced to the basics of sending and receiving both classical and quantum information, as well as the first steps of writing programs and manipulating Qubits.

This chapter of the tutorial takes the user through the example `examples/tutorial/1_Basics`. This chapter will focus only on the `application.py` file.

## Running the Example

To run this example, first make the example directory the active directory:

```bash
cd examples/tutorial/1_Basics
```

Afterwards run the simulation using:

```bash
python3 run_simulation.py
```

All examples are fully functional and can be executed immediately.

## Application Basics

### Programs vs Applications

In this section we will explain the basics of writing an application for SquidASM. We define separate meanings to program and application:

- **Program**: The code running on a single node
- **Application**: The complete set of programs to achieve a specific purpose

For example, BQC (Blind Quantum Computing) is an application, but it consists of two programs: one program for the client and another for the server.

In this tutorial we will be creating an `AliceProgram` and a `BobProgram` that will run on Alice and Bob nodes respectively.

### Program Structure

Both the Alice and Bob program start with an unpacking of a `ProgramContext` object into:

- `csocket` (a classical socket)
- `epr_socket` (an EPR socket)
- `connection` (a NetQASM connection)

Here's the basic structure of `AliceProgram`:

```python
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta

class AliceProgram(Program):
    PEER_NAME = "Bob"
    
    @staticmethod
    def meta() -> ProgramMeta:
        return ProgramMeta(
            name="Alice",
            csockets=[AliceProgram.PEER_NAME],
            epr_sockets=[(AliceProgram.PEER_NAME, 1)],
        )
    
    def run(self, context: ProgramContext) -> Generator:
        csocket = context.csockets[self.PEER_NAME]
        epr_socket = context.epr_sockets[(self.PEER_NAME, 0)]
        connection = context.connection
        
        # Program logic here
```

### Understanding the Context

Three key concepts in SquidASM programs:

1. **Host and QNPU**: The program runs on a host (classical computer) which is connected to a Quantum Network Processing Unit (QNPU) responsible for local qubit operations and EPR pair generation with remote nodes.

2. **NetQASM Connection**: The variable `connection` represents the NetQASM connection between the host and QNPU. It is used to communicate all instructions regarding qubit operations and entanglement generation.

3. **Classical Socket**: The `csocket` is a classical socket that represents an endpoint for sending and receiving data across a network to the socket of another node. Note that the socket connects to one specific other node. The classical socket can be used to send classical information to the host of another node.

4. **EPR Socket**: The `epr_socket` is a socket for generating entangled qubits on both nodes. Behind the scenes, the communication requests are sent to the quantum network processing unit.

```
┌─────────────────────────────────────────────────────────────┐
│ Application Layer (Program)                                 │
│ ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│ │ Classical    │  │ EPR Socket   │  │ Qubit Ops    │        │
│ │ Socket       │  │              │  │ via          │        │
│ │              │  │              │  │ Connection   │        │
│ └──────────────┘  └──────────────┘  └──────────────┘        │
└──────────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────────┐
│ Host (Classical Computer)                                    │
└──────────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────────┐
│ NetQASM Connection                                           │
└──────────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────────┐
│ QNPU (Quantum Network Processing Unit)                       │
│ ┌──────────────┐  ┌──────────────┐                          │
│ │ Local Qubits │  │ EPR Gen      │                          │
│ │ & Gates      │  │ with Remote  │                          │
│ └──────────────┘  └──────────────┘                          │
└──────────────────────────────────────────────────────────────┘
```

**Important Note**: Most NetQASM objects, such as qubits and EPR sockets, are initialized using a NetQASM connection and they store this NetQASM connection reference internally. These objects then forward instructions to a NetQASM connection behind the scenes.

## Sending Classical Information

Classical information is sent via the `Socket` object from `netqasm.sdk`. The Socket objects represent an open connection to a peer.

### Alice's Side (Sending)

Sending a classical message to a peer is done by using the `send()` method of the classical socket:

```python
# Alice sends a message
csocket.send("Hello")
print("Alice sends message: Hello")
```

### Bob's Side (Receiving)

For Bob to receive the message, he must be waiting for a classical message at the same time using the `recv()` method:

```python
# Bob receives a message
message = yield from csocket.recv()
print(f"Bob receives message {message}")
```

**Important**: It is mandatory to include the `yield from` keywords when receiving messages for the application to work with SquidASM.

### Expected Output

Running the simulation should result in:

```
Alice sends message: Hello
Bob receives message: Hello
```

## Creating EPR Pairs Between Nodes

Creating an EPR pair follows a similar pattern as classical communication: Alice must register a request using `create_keep()` to generate an EPR pair, while Bob needs to be listening to such a request using `recv_keep()`.

### Alice's Side (Creating)

```python
# Request to create an EPR pair
q = (yield from epr_socket.create_keep(1))[0]

# Apply Hadamard gate
q.H()

# Measure the qubit
result = q.measure()

# Send to QNPU and get results
yield from connection.flush()

print(f"Alice measures local EPR qubit: {result}")
```

### Bob's Side (Receiving)

```python
# Wait for and receive EPR pair
q = (yield from epr_socket.recv_keep(1))[0]

# Apply Hadamard gate
q.H()

# Measure the qubit
result = q.measure()

# Send to QNPU and get results
yield from connection.flush()

print(f"Bob measures local EPR qubit: {result}")
```

### EPR Pair Properties

Both `create_keep()` and `recv_keep()` return a list of qubits, so we select the local EPR qubit using `[0]`.

By default the request only creates a single EPR pair, but a request for multiple EPR pairs may be placed using `create_keep(number=n)`.

### Expected Output

Running the simulation results in either:

```
Alice measures local EPR qubit: 0
Bob measures local EPR qubit: 0
```

or:

```
Alice measures local EPR qubit: 1
Bob measures local EPR qubit: 1
```

**Note**: The EPR pairs as presented to the application are in the state $\ket{\Phi^+} = \frac{1}{\sqrt{2}}(\ket{00} + \ket{11})$. Behind the scenes the EPR pair might have been initially generated in a different Bell state, but by applying the appropriate Pauli gates on both nodes, the state will be transformed into the $\ket{\Phi^+}$ state.

## Creating Local Qubits

It is possible to request and use local qubits without generating entanglement with a remote node. This is done by initializing a `Qubit` object from `netqasm.sdk.qubit`.

This initialization requires the user to pass the NetQASM connection, as instructions need to be sent to the QNPU that a particular qubit is reset and marked as in use. We can use the `Qubit` object to create an EPR pair with both qubits on the same node:

```python
from netqasm.sdk.qubit import Qubit

# Create two local qubits
q0 = Qubit(connection)
q1 = Qubit(connection)

# Initialize the qubits
q0.X()
q1.X()

# Apply Hadamard to first qubit to entangle them (CNOT-like operation)
q0.H()
q0.cnot(q1)

# Measure both qubits
m0 = q0.measure()
m1 = q1.measure()

# Send to QNPU and get results
yield from connection.flush()

print(f"Alice measures local qubits: {m0}, {m1}")
```

### Result

The result of this code segment is either:

```
Alice measures local qubits: 0, 0
```

or:

```
Alice measures local qubits: 1, 1
```

## Qubit Gates

The `Qubit` object supports a large selection of operations:

### Single Qubit Gates

- **Pauli gates**: `X()`, `Y()`, `Z()`
- **Clifford gates**: `T()`, `H()`, `K()`, `S()`

### Qubit Rotations

- **Rotation operators**: `rot_X(n, d)`, `rot_Y(n, d)`, `rot_Z(n, d)`
  - These specify the magnitude of rotation via parameters n and d: $\frac{n\pi}{2^d}$
  - For example, `rot_Z(1, 2)` rotates by $\frac{\pi}{4}$

### Multi-Qubit Operations

- **CNOT**: `cnot(target)` - Control-NOT gate where the control qubit is the qubit invoking the operation
- **CPhase**: `cphase(target)` - Controlled-Phase gate

### Using Gates

```python
q = Qubit(connection)

# Single qubit gates
q.X()          # Pauli X
q.Y()          # Pauli Y
q.Z()          # Pauli Z
q.H()          # Hadamard
q.S()          # S gate
q.T()          # T gate

# Rotations
q.rot_X(3, 2)  # Rotate around X by 3π/4
q.rot_Y(1, 2)  # Rotate around Y by π/4
q.rot_Z(1, 1)  # Rotate around Z by π/2

# Multi-qubit operations
q.cnot(q_target)    # CNOT
q.cphase(q_target)  # Controlled Phase
```

## Summary

In this section you learned:

- How to structure a basic SquidASM program with programs and applications
- How to access classical sockets, EPR sockets, and the NetQASM connection from ProgramContext
- How to send and receive classical messages
- How to generate and measure EPR pairs
- How to create and manipulate local qubits
- How to apply quantum gates to qubits

The next section will explain the NetQASM language in more detail, particularly the concept of instruction queues and Future objects.
