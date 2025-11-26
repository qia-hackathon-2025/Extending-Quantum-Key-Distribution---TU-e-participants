# Tutorial 1: Basics

This tutorial covers the fundamental concepts you need to know to get started with SquidASM.

## Overview

SquidASM is a high-level interface for simulating quantum network applications using the NetSquid simulator. The core workflow involves:

1. **Writing a Program** - Subclass `Program` to define your quantum network application
2. **Configuring a Network** - Use YAML or Python to define network topology
3. **Running Simulations** - Execute programs across multiple network nodes

## Writing Your First Program

Every SquidASM application starts by defining a `Program`. Each node in your network runs a program that can:

- Create and manipulate qubits
- Generate entanglement with remote nodes
- Send and receive classical messages

### The Program Class

Here's the basic structure of a SquidASM program:

```python
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta

class MyProgram(Program):
    PEER_NAME = "Partner"  # Name of the remote node
    
    @property
    def meta(self) -> ProgramMeta:
        """Define program metadata including qubit requirements."""
        return ProgramMeta(
            name="my_program",
            csockets=[self.PEER_NAME],    # Classical sockets needed
            epr_sockets=[self.PEER_NAME], # EPR sockets needed
            max_qubits=2                   # Maximum qubits this program will use
        )
    
    def run(self, context: ProgramContext):
        """Main program logic - executed on the quantum network node."""
        # Access the network connection
        connection = context.connection
        
        # Access classical socket for messaging
        csocket = context.csockets[self.PEER_NAME]
        
        # Access EPR socket for entanglement
        epr_socket = context.epr_sockets[self.PEER_NAME]
        
        # Your quantum program logic here
        return {}
```

### Key Components Explained

#### ProgramMeta

The `meta` property (note: it's a `@property`, not a `@staticmethod`) returns a `ProgramMeta` object that describes:

- **`name`**: Identifier for the program
- **`csockets`**: List of node names for classical communication
- **`epr_sockets`**: List of node names for EPR pair generation
- **`max_qubits`**: Maximum number of qubits your program will use simultaneously (important for resource allocation)

#### ProgramContext

When `run()` is called, it receives a `ProgramContext` providing:

- **`connection`**: The NetQASM connection for quantum operations
- **`csockets`**: Dictionary mapping peer names to classical sockets
- **`epr_sockets`**: Dictionary mapping peer names to EPR sockets
- **`app_config`**: Application-specific configuration data

### Accessing Sockets

Sockets are accessed using the peer node name as the key:

```python
# Correct way to access sockets
csocket = context.csockets[self.PEER_NAME]     # Using the peer name directly
epr_socket = context.epr_sockets[self.PEER_NAME]

# Example with explicit name
csocket = context.csockets["Bob"]
epr_socket = context.epr_sockets["Alice"]
```

## Working with Qubits

### Creating Local Qubits

To create and manipulate a local qubit:

```python
from netqasm.sdk.qubit import Qubit

def run(self, context: ProgramContext):
    connection = context.connection
    
    # Create a new qubit (initialized to |0⟩)
    q = Qubit(connection)
    
    # Apply quantum gates
    q.H()      # Hadamard gate: |0⟩ → |+⟩
    q.X()      # Pauli-X gate (NOT)
    q.Y()      # Pauli-Y gate
    q.Z()      # Pauli-Z gate
    q.T()      # T gate
    q.S()      # S gate
    
    # Rotations (angle in units of π/16)
    q.rot_X(n=8, d=1)  # Rotate around X axis: n * π / (2^d)
    q.rot_Y(n=4, d=2)  # Rotate around Y axis
    q.rot_Z(n=2, d=0)  # Rotate around Z axis
    
    # Two-qubit gates
    q2 = Qubit(connection)
    q.cnot(q2)   # CNOT with q as control, q2 as target
    q.cphase(q2) # Controlled-Z gate
    
    # Measurement
    result = q.measure()
    
    # Flush to execute all operations
    connection.flush()
    
    # Access measurement result (after flush)
    outcome = int(result)
    return {"measurement": outcome}
```

### Creating Bell Pairs

To create entanglement with a remote node:

```python
def run(self, context: ProgramContext):
    connection = context.connection
    epr_socket = context.epr_sockets[self.PEER_NAME]
    
    # Create an EPR pair - returns the local qubit
    q_entangled = epr_socket.create_keep()[0]
    
    # Or receive an EPR pair initiated by remote node
    q_received = epr_socket.recv_keep()[0]
    
    # The qubits are now entangled in the |Φ+⟩ Bell state
    result = q_entangled.measure()
    connection.flush()
    
    return {"result": int(result)}
```

## Classical Communication

Classical sockets allow you to send messages between nodes:

```python
def run(self, context: ProgramContext):
    csocket = context.csockets[self.PEER_NAME]
    
    # Send a message (string)
    csocket.send("Hello from Alice!")
    
    # Receive a message
    message = yield from csocket.recv()
    
    # Send structured data (will be converted to string)
    csocket.send(str(42))
    
    return {"received": message}
```

**Important**: Use `yield from` when receiving classical messages, as this is an asynchronous operation.

## Complete Example: Quantum Teleportation

Here's a complete example showing Alice teleporting a qubit state to Bob:

### Alice's Program

```python
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from netqasm.sdk.qubit import Qubit

class AliceProgram(Program):
    PEER_NAME = "Bob"
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="alice_teleport",
            csockets=[self.PEER_NAME],
            epr_sockets=[self.PEER_NAME],
            max_qubits=2
        )
    
    def run(self, context: ProgramContext):
        connection = context.connection
        csocket = context.csockets[self.PEER_NAME]
        epr_socket = context.epr_sockets[self.PEER_NAME]
        
        # Create the qubit to teleport (in state |+⟩)
        q_to_send = Qubit(connection)
        q_to_send.H()
        
        # Create EPR pair with Bob
        q_entangled = epr_socket.create_keep()[0]
        
        # Teleportation circuit
        q_to_send.cnot(q_entangled)
        q_to_send.H()
        
        # Measure both qubits
        m1 = q_to_send.measure()
        m2 = q_entangled.measure()
        connection.flush()
        
        # Send corrections to Bob
        csocket.send(f"{int(m1)},{int(m2)}")
        
        return {"m1": int(m1), "m2": int(m2)}
```

### Bob's Program

```python
class BobProgram(Program):
    PEER_NAME = "Alice"
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="bob_teleport",
            csockets=[self.PEER_NAME],
            epr_sockets=[self.PEER_NAME],
            max_qubits=1
        )
    
    def run(self, context: ProgramContext):
        connection = context.connection
        csocket = context.csockets[self.PEER_NAME]
        epr_socket = context.epr_sockets[self.PEER_NAME]
        
        # Receive EPR pair from Alice
        q_received = epr_socket.recv_keep()[0]
        
        # Receive classical corrections
        msg = yield from csocket.recv()
        m1, m2 = msg.split(",")
        
        # Apply corrections
        if int(m2) == 1:
            q_received.X()
        if int(m1) == 1:
            q_received.Z()
        
        # Measure the teleported qubit
        result = q_received.measure()
        connection.flush()
        
        return {"teleported_measurement": int(result)}
```

## Running the Simulation

To run your programs, you need to configure a network and execute the simulation:

```python
from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run

# Load network configuration from YAML
config = StackNetworkConfig.from_file("config.yaml")

# Run the simulation
results = run(
    config=config,
    programs={"Alice": AliceProgram(), "Bob": BobProgram()},
    num_times=1
)

# Process results
alice_results, bob_results = results
print(f"Alice: {alice_results}")
print(f"Bob: {bob_results}")
```

### Network Configuration (config.yaml)

```yaml
stacks:
  - name: Alice
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 2
  - name: Bob
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 2

links:
  - stack1: Alice
    stack2: Bob
    typ: depolarise
    cfg:
      fidelity: 0.95
      t_cycle: 10

clinks:
  - stack1: Alice
    stack2: Bob
```

## Key Takeaways

1. **Always use `@property`** for the `meta` method, not `@staticmethod`
2. **Access sockets by peer name**: `context.csockets["Bob"]` not `context.csockets[("Bob", 0)]`
3. **Specify `max_qubits`** in `ProgramMeta` for proper resource allocation
4. **Use `yield from`** for receiving classical messages
5. **Call `connection.flush()`** before reading measurement results
6. **EPR operations return lists**: Use `[0]` to get the first qubit

## Next Steps

- [Tutorial 2: NetQASM](2_netqasm.md) - Learn about the underlying instruction set
- [Tutorial 3: Simulation Control](3_simulation_control.md) - Advanced simulation features
- [Tutorial 4: Network Configuration](4_network_configuration.md) - Detailed network setup
