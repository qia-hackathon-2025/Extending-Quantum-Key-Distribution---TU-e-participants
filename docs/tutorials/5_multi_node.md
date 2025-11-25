# Tutorial 5: Multi-Node Networks

In this section we extend applications to networks with more than two nodes. Writing programs for networks with more than two nodes requires registering each of the nodes for which a connection is used in the `ProgramMeta` object.

## Network Configuration for Three Nodes

To create a network with three nodes, extend the `config.yaml` with additional stacks and links:

```yaml
stacks:
  - name: Alice
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 5
      T1: 1000000.0
      T2: 1000000.0
      init_time: 100
      single_qubit_gate_time: 50
      two_qubit_gate_time: 200
      measure_time: 100
      single_qubit_gate_depolar_prob: 0.0
      two_qubit_gate_depolar_prob: 0.0
  
  - name: Bob
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 5
      T1: 1000000.0
      T2: 1000000.0
      init_time: 100
      single_qubit_gate_time: 50
      two_qubit_gate_time: 200
      measure_time: 100
      single_qubit_gate_depolar_prob: 0.0
      two_qubit_gate_depolar_prob: 0.0
  
  - name: Charlie
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 5
      T1: 1000000.0
      T2: 1000000.0
      init_time: 100
      single_qubit_gate_time: 50
      two_qubit_gate_time: 200
      measure_time: 100
      single_qubit_gate_depolar_prob: 0.0
      two_qubit_gate_depolar_prob: 0.0

links:
  - stack1: Alice
    stack2: Bob
    typ: perfect
    cfg: {}
  
  - stack1: Alice
    stack2: Charlie
    typ: perfect
    cfg: {}
  
  - stack1: Bob
    stack2: Charlie
    typ: perfect
    cfg: {}

clinks:
  - stack1: Alice
    stack2: Bob
    typ: instant
    cfg: {}
  
  - stack1: Alice
    stack2: Charlie
    typ: instant
    cfg: {}
  
  - stack1: Bob
    stack2: Charlie
    typ: instant
    cfg: {}
```

**Note**: You don't have to connect every pair of nodes. As long as the application doesn't attempt to use a non-existent link, any topology is valid.

## Multi-Node Applications

### Example: Entanglement Swapping

A common multi-node protocol is entanglement swapping. In this protocol:

1. **Alice and Bob** create an EPR pair
2. **Alice and Charlie** create another EPR pair
3. **Alice** performs a Bell state measurement on her two qubits (one from each EPR pair)
4. **Alice** sends the measurement results to Charlie
5. **Bob and Charlie** are now entangled

### Alice Program (Intermediate Node)

```python
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from typing import Generator

class AliceProgram(Program):
    BOB_NAME = "Bob"
    CHARLIE_NAME = "Charlie"
    
    @staticmethod
    def meta() -> ProgramMeta:
        return ProgramMeta(
            name="Alice",
            csockets=[AliceProgram.BOB_NAME, AliceProgram.CHARLIE_NAME],
            epr_sockets=[
                (AliceProgram.BOB_NAME, 1),      # EPR with Bob
                (AliceProgram.CHARLIE_NAME, 1),  # EPR with Charlie
            ],
        )
    
    def run(self, context: ProgramContext) -> Generator:
        csocket_bob = context.csockets[self.BOB_NAME]
        csocket_charlie = context.csockets[self.CHARLIE_NAME]
        epr_socket_bob = context.epr_sockets[(self.BOB_NAME, 0)]
        epr_socket_charlie = context.epr_sockets[(self.CHARLIE_NAME, 0)]
        connection = context.connection
        
        # Create EPR pair with Bob
        q_bob = (yield from epr_socket_bob.create_keep(1))[0]
        
        # Create EPR pair with Charlie
        q_charlie = (yield from epr_socket_charlie.create_keep(1))[0]
        
        # Perform Bell state measurement (CNOT + measure both)
        q_bob.cnot(q_charlie)
        result_bob = q_bob.measure()
        result_charlie = q_charlie.measure()
        
        yield from connection.flush()
        
        # Send measurement results to Charlie
        csocket_charlie.send(int(result_bob))
        csocket_charlie.send(int(result_charlie))


class AliceProgram(Program):
    BOB_NAME = "Bob"
    CHARLIE_NAME = "Charlie"
    
    @staticmethod
    def meta() -> ProgramMeta:
        return ProgramMeta(
            name="Alice",
            csockets=[AliceProgram.CHARLIE_NAME],  # Only need to send to Charlie
            epr_sockets=[
                (AliceProgram.BOB_NAME, 1),      # EPR with Bob
                (AliceProgram.CHARLIE_NAME, 1),  # EPR with Charlie
            ],
        )
    
    def run(self, context: ProgramContext) -> Generator:
        csocket_charlie = context.csockets[self.CHARLIE_NAME]
        epr_socket_bob = context.epr_sockets[(self.BOB_NAME, 0)]
        epr_socket_charlie = context.epr_sockets[(self.CHARLIE_NAME, 0)]
        connection = context.connection
        
        # Create EPR pair with Bob
        q_bob = (yield from epr_socket_bob.create_keep(1))[0]
        
        # Create EPR pair with Charlie
        q_charlie = (yield from epr_socket_charlie.create_keep(1))[0]
        
        # Perform Bell state measurement (CNOT + measure both)
        q_bob.cnot(q_charlie)
        result_bob = q_bob.measure()
        result_charlie_meas = q_charlie.measure()
        
        yield from connection.flush()
        
        # Send measurement results to Charlie
        csocket_charlie.send(int(result_bob))
        csocket_charlie.send(int(result_charlie_meas))
```

### Bob Program (Passive Receiver)

```python
class BobProgram(Program):
    ALICE_NAME = "Alice"
    
    @staticmethod
    def meta() -> ProgramMeta:
        return ProgramMeta(
            name="Bob",
            csockets=[],  # No classical sockets needed
            epr_sockets=[(BobProgram.ALICE_NAME, 1)],  # Only EPR with Alice
        )
    
    def run(self, context: ProgramContext) -> Generator:
        epr_socket_alice = context.epr_sockets[(self.ALICE_NAME, 0)]
        connection = context.connection
        
        # Wait for EPR pair from Alice
        q_alice = (yield from epr_socket_alice.recv_keep(1))[0]
        
        # At this point, q_alice is entangled with Alice's qubit from the Alice-Bob pair
        # After Alice's Bell measurement, Charlie will apply corrections
        
        yield from connection.flush()
        
        # Store qubit reference for later use
        self.qubit = q_alice
```

### Charlie Program (Correction)

```python
class CharlieProgram(Program):
    ALICE_NAME = "Alice"
    
    @staticmethod
    def meta() -> ProgramMeta:
        return ProgramMeta(
            name="Charlie",
            csockets=[CharlieProgram.ALICE_NAME],  # Receive corrections from Alice
            epr_sockets=[(CharlieProgram.ALICE_NAME, 1)],
        )
    
    def run(self, context: ProgramContext) -> Generator:
        csocket_alice = context.csockets[self.ALICE_NAME]
        epr_socket_alice = context.epr_sockets[(self.ALICE_NAME, 0)]
        connection = context.connection
        
        # Wait for EPR pair from Alice
        q_alice = (yield from epr_socket_alice.recv_keep(1))[0]
        
        yield from connection.flush()
        
        # Receive Bell measurement results from Alice
        result_alice_bob = yield from csocket_alice.recv()
        result_alice_charlie = yield from csocket_alice.recv()
        
        # Apply corrections based on Alice's measurement results
        if result_alice_charlie == 1:
            q_alice.Z()
        if result_alice_bob == 1:
            q_alice.X()
        
        # Now q_alice is entangled with Bob's qubit (which is still held by Bob)
        yield from connection.flush()
```

## Running Multi-Node Applications

In `run_simulation.py`, create instances of all programs and map them to nodes:

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
run(
    config=cfg,
    programs=programs,
    num_times=1,
)
```

## Key Differences in Multi-Node Applications

### Socket Declaration in ProgramMeta

Unlike two-node applications, multi-node applications must explicitly declare all peer nodes:

```python
@staticmethod
def meta() -> ProgramMeta:
    return ProgramMeta(
        name="Alice",
        csockets=["Bob", "Charlie"],  # All peers with classical sockets
        epr_sockets=[("Bob", 1), ("Charlie", 1)],  # All peers with EPR sockets
    )
```

### Accessing Multiple Sockets

Access sockets for each peer separately:

```python
def run(self, context: ProgramContext) -> Generator:
    csocket_bob = context.csockets["Bob"]
    csocket_charlie = context.csockets["Charlie"]
    
    epr_socket_bob = context.epr_sockets[("Bob", 0)]
    epr_socket_charlie = context.epr_sockets[("Charlie", 0)]
    
    # Use sockets normally...
```

### Optional Sockets

You don't need to declare sockets you won't use:

```python
# BobProgram doesn't send to Alice, so no classical socket needed
@staticmethod
def meta() -> ProgramMeta:
    return ProgramMeta(
        name="Bob",
        csockets=[],  # Empty if no classical communication
        epr_sockets=[("Alice", 1)],
    )
```

## Useful Helper Functions

For larger networks, consider using helper functions to create configurations:

```python
from squidasm.util import create_complete_graph_network, create_two_node_network

# Create a fully connected network with n nodes
network_cfg = create_complete_graph_network(
    node_names=["Alice", "Bob", "Charlie", "Diana"],
    link_cfg=DepolariseLinkConfig(fidelity=0.9),
    clink_cfg=DefaultCLinkConfig(delay=1000),
)

# Or create a simple two-node network
network_cfg = create_two_node_network(
    node_names=["Alice", "Bob"],
    link_cfg=PerfectLinkConfig(),
    clink_cfg=InstantCLinkConfig(),
)
```

## Common Multi-Node Patterns

### Pattern 1: Star Topology

One central node (hub) communicates with multiple peripheral nodes:

```python
# Hub program
hub_peers = ["Node1", "Node2", "Node3", "Node4"]

@staticmethod
def meta() -> ProgramMeta:
    return ProgramMeta(
        name="Hub",
        csockets=hub_peers,
        epr_sockets=[(peer, 1) for peer in hub_peers],
    )

# Peripheral programs (simplified)
@staticmethod
def meta() -> ProgramMeta:
    return ProgramMeta(
        name="Node1",
        csockets=["Hub"],
        epr_sockets=[("Hub", 1)],
    )
```

### Pattern 2: Linear Chain

Nodes arranged in a line, each communicating with neighbors:

```
Alice -- Bob -- Charlie -- Diana
```

```python
# Middle node (Bob)
@staticmethod
def meta() -> ProgramMeta:
    return ProgramMeta(
        name="Bob",
        csockets=["Alice", "Charlie"],
        epr_sockets=[("Alice", 1), ("Charlie", 1)],
    )
```

### Pattern 3: Relay Protocol

Pass quantum information through intermediate nodes to extend range.

## Summary

In this section you learned:

- How to **configure multi-node networks** in YAML
- How to write **multi-node programs** with multiple socket declarations
- How to **access multiple sockets** in `ProgramContext`
- The **entanglement swapping** protocol as a practical example
- How to **run multi-node simulations**
- **Helper functions** for creating network topologies
- Common **multi-node patterns** (star, chain, relay)

Multi-node applications are essential for quantum network protocols such as entanglement swapping, quantum key distribution, and distributed quantum computing.

The next section will cover parameter sweeping techniques for systematic performance analysis.
