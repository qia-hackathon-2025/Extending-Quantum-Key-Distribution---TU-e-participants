# Tutorial 5: Multi-Node Networks

In this section we extend applications to networks with more than two nodes. Multi-node programs require declaring all peer connections in the `ProgramMeta` object.

## Network Configuration for Three Nodes

Extend `config.yaml` with additional stacks and links:

```yaml
stacks:
  - name: Alice
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 5
  
  - name: Bob
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 5
  
  - name: Charlie
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 5

links:
  - stack1: Alice
    stack2: Bob
    typ: perfect
  
  - stack1: Alice
    stack2: Charlie
    typ: perfect
  
  - stack1: Bob
    stack2: Charlie
    typ: perfect

clinks:
  - stack1: Alice
    stack2: Bob
  
  - stack1: Alice
    stack2: Charlie
  
  - stack1: Bob
    stack2: Charlie
```

**Note**: You don't need to connect every pair. Any topology works as long as programs don't use non-existent links.

## Multi-Node Program Structure

### Key Differences from Two-Node Programs

1. **Socket declaration**: List all peers in `csockets` and `epr_sockets`
2. **Socket access**: Use peer name as key (string, not tuple)
3. **Multiple connections**: Can interact with multiple peers in single `run()` method

### ProgramMeta for Multi-Node

```python
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta

class AliceProgram(Program):
    BOB_NAME = "Bob"
    CHARLIE_NAME = "Charlie"
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="alice",
            csockets=[self.BOB_NAME, self.CHARLIE_NAME],
            epr_sockets=[self.BOB_NAME, self.CHARLIE_NAME],
            max_qubits=3
        )
```

### Accessing Multiple Sockets

```python
def run(self, context: ProgramContext):
    # Access sockets by peer name (string key)
    csocket_bob = context.csockets[self.BOB_NAME]
    csocket_charlie = context.csockets[self.CHARLIE_NAME]
    
    epr_socket_bob = context.epr_sockets[self.BOB_NAME]
    epr_socket_charlie = context.epr_sockets[self.CHARLIE_NAME]
    
    connection = context.connection
```

## Example: Entanglement Swapping

A common multi-node protocol where:

1. **Alice-Bob** create an EPR pair
2. **Alice-Charlie** create another EPR pair
3. **Alice** performs Bell measurement on her two qubits
4. **Alice** sends corrections to Bob and Charlie
5. **Bob and Charlie** become entangled despite no direct link

### Alice Program (Swapper)

```python
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from netqasm.sdk.qubit import Qubit

class AliceProgram(Program):
    """Alice performs entanglement swapping."""
    BOB_NAME = "Bob"
    CHARLIE_NAME = "Charlie"
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="alice_swapper",
            csockets=[self.BOB_NAME, self.CHARLIE_NAME],
            epr_sockets=[self.BOB_NAME, self.CHARLIE_NAME],
            max_qubits=2
        )
    
    def run(self, context: ProgramContext):
        csocket_bob = context.csockets[self.BOB_NAME]
        csocket_charlie = context.csockets[self.CHARLIE_NAME]
        epr_socket_bob = context.epr_sockets[self.BOB_NAME]
        epr_socket_charlie = context.epr_sockets[self.CHARLIE_NAME]
        connection = context.connection
        
        # Create EPR pair with Bob
        q_bob = epr_socket_bob.create_keep()[0]
        
        # Create EPR pair with Charlie
        q_charlie = epr_socket_charlie.create_keep()[0]
        
        # Bell state measurement
        q_bob.cnot(q_charlie)
        q_bob.H()
        
        m1 = q_bob.measure()
        m2 = q_charlie.measure()
        
        connection.flush()
        
        # Send corrections to both
        csocket_bob.send(f"{int(m1)},{int(m2)}")
        csocket_charlie.send(f"{int(m1)},{int(m2)}")
        
        return {"m1": int(m1), "m2": int(m2)}
```

### Bob Program

```python
class BobProgram(Program):
    """Bob receives entanglement via Alice."""
    ALICE_NAME = "Alice"
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="bob_receiver",
            csockets=[self.ALICE_NAME],
            epr_sockets=[self.ALICE_NAME],
            max_qubits=1
        )
    
    def run(self, context: ProgramContext):
        csocket_alice = context.csockets[self.ALICE_NAME]
        epr_socket_alice = context.epr_sockets[self.ALICE_NAME]
        connection = context.connection
        
        # Receive EPR pair from Alice
        q = epr_socket_alice.recv_keep()[0]
        
        # Receive corrections from Alice
        msg = yield from csocket_alice.recv()
        m1, m2 = msg.split(",")
        
        # Apply Pauli corrections for entanglement swapping
        if int(m2) == 1:
            q.X()
        
        # Now entangled with Charlie
        result = q.measure()
        connection.flush()
        
        return {"result": int(result)}
```

### Charlie Program

```python
class CharlieProgram(Program):
    """Charlie receives entanglement via Alice."""
    ALICE_NAME = "Alice"
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="charlie_receiver",
            csockets=[self.ALICE_NAME],
            epr_sockets=[self.ALICE_NAME],
            max_qubits=1
        )
    
    def run(self, context: ProgramContext):
        csocket_alice = context.csockets[self.ALICE_NAME]
        epr_socket_alice = context.epr_sockets[self.ALICE_NAME]
        connection = context.connection
        
        # Receive EPR pair from Alice
        q = epr_socket_alice.recv_keep()[0]
        
        # Receive corrections from Alice
        msg = yield from csocket_alice.recv()
        m1, m2 = msg.split(",")
        
        # Apply Pauli corrections for entanglement swapping
        if int(m1) == 1:
            q.Z()
        
        # Now entangled with Bob
        result = q.measure()
        connection.flush()
        
        return {"result": int(result)}
```

## Running Multi-Node Simulations

```python
from application import AliceProgram, BobProgram, CharlieProgram
from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run

# Load configuration
cfg = StackNetworkConfig.from_file("config.yaml")

# Create program instances
alice_program = AliceProgram()
bob_program = BobProgram()
charlie_program = CharlieProgram()

# Map programs to nodes
programs = {
    "Alice": alice_program,
    "Bob": bob_program,
    "Charlie": charlie_program,
}

# Run simulation
results = run(
    config=cfg,
    programs=programs,
    num_times=100
)

# Results for each node
alice_results, bob_results, charlie_results = results

# Verify entanglement swapping worked
correlations = sum(
    1 for i in range(len(bob_results))
    if bob_results[i]["result"] == charlie_results[i]["result"]
)
print(f"Bob-Charlie correlation: {correlations/len(bob_results):.2%}")
```

## Common Multi-Node Patterns

### Pattern 1: Star Topology

Central hub communicates with multiple peripheral nodes:

```
    Node1
      |
Node4-Hub-Node2
      |
    Node3
```

```python
class HubProgram(Program):
    PEERS = ["Node1", "Node2", "Node3", "Node4"]
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="hub",
            csockets=self.PEERS,
            epr_sockets=self.PEERS,
            max_qubits=4
        )
    
    def run(self, context: ProgramContext):
        # Create EPR pairs with all peers
        qubits = {}
        for peer in self.PEERS:
            epr_socket = context.epr_sockets[peer]
            qubits[peer] = epr_socket.create_keep()[0]
        
        # Process all qubits...
        context.connection.flush()
        return {}
```

### Pattern 2: Linear Chain (Repeater)

Extend entanglement range through intermediate nodes:

```
Alice -- Bob -- Charlie -- Diana
```

```python
class BobProgram(Program):
    """Middle node in a chain."""
    LEFT = "Alice"
    RIGHT = "Charlie"
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="bob_repeater",
            csockets=[self.LEFT, self.RIGHT],
            epr_sockets=[self.LEFT, self.RIGHT],
            max_qubits=2
        )
    
    def run(self, context: ProgramContext):
        epr_left = context.epr_sockets[self.LEFT]
        epr_right = context.epr_sockets[self.RIGHT]
        connection = context.connection
        
        # Receive from left, create to right
        q_left = epr_left.recv_keep()[0]
        q_right = epr_right.create_keep()[0]
        
        # Swap entanglement
        q_left.cnot(q_right)
        q_left.H()
        m1 = q_left.measure()
        m2 = q_right.measure()
        connection.flush()
        
        # Send corrections in both directions
        context.csockets[self.LEFT].send(f"{int(m1)},{int(m2)}")
        context.csockets[self.RIGHT].send(f"{int(m1)},{int(m2)}")
        
        return {"m1": int(m1), "m2": int(m2)}
```

### Pattern 3: GHZ State Distribution

Create multi-party entanglement:

```python
class AliceProgram(Program):
    """Create GHZ state shared with Bob and Charlie."""
    PEERS = ["Bob", "Charlie"]
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="alice_ghz",
            csockets=self.PEERS,
            epr_sockets=self.PEERS,
            max_qubits=3
        )
    
    def run(self, context: ProgramContext):
        connection = context.connection
        
        # Create local qubit for GHZ
        q_local = Qubit(connection)
        q_local.H()  # Put in |+⟩
        
        # Create EPR pairs with each peer
        epr_qubits = []
        for peer in self.PEERS:
            epr_socket = context.epr_sockets[peer]
            q = epr_socket.create_keep()[0]
            epr_qubits.append(q)
        
        # Entangle local qubit with EPR qubits to create GHZ
        for q_epr in epr_qubits:
            q_local.cnot(q_epr)
        
        # Measure and distribute results...
        m_local = q_local.measure()
        connection.flush()
        
        return {"measurement": int(m_local)}
```

## Third-Party Communication

Sometimes Node A needs to communicate with Node C through Node B:

```python
class RelayProgram(Program):
    """Bob relays messages between Alice and Charlie."""
    ALICE = "Alice"
    CHARLIE = "Charlie"
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="bob_relay",
            csockets=[self.ALICE, self.CHARLIE],
            epr_sockets=[],  # No quantum communication
            max_qubits=0
        )
    
    def run(self, context: ProgramContext):
        cs_alice = context.csockets[self.ALICE]
        cs_charlie = context.csockets[self.CHARLIE]
        
        # Receive from Alice
        msg = yield from cs_alice.recv()
        
        # Forward to Charlie
        cs_charlie.send(msg)
        
        # Receive response from Charlie
        response = yield from cs_charlie.recv()
        
        # Forward back to Alice
        cs_alice.send(response)
        
        return {"relayed": True}
```

## Partial Connectivity

Programs only need sockets for nodes they communicate with:

```python
# Bob only talks to Alice, not Charlie
class BobProgram(Program):
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="bob",
            csockets=["Alice"],      # Only Alice
            epr_sockets=["Alice"],   # Only Alice
            max_qubits=1
        )
```

Ensure your network configuration has the necessary links:

```yaml
links:
  - stack1: Alice
    stack2: Bob
    typ: perfect
  # No Bob-Charlie link needed if Bob doesn't communicate with Charlie
```

## Summary

In this section you learned:

- How to **configure multi-node networks** in YAML
- **Socket declaration** for multiple peers in ProgramMeta
- **Socket access by peer name** (string key, not tuple)
- **Entanglement swapping** as a practical multi-node example
- Common **network topologies** (star, chain, mesh)
- **Third-party communication** and relay patterns
- **Partial connectivity** for sparse networks

## Next Steps

- [Tutorial 6: Parameter Sweeping](6_parameter_sweeping.md) - Systematic performance analysis
- [API Reference](../api/index.md) - Detailed API documentation
