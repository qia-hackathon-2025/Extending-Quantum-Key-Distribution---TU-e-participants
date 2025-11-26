# Tutorial 5: GHZ State Creation

This tutorial demonstrates creating **GHZ (Greenberger-Horne-Zeilinger) states** across multiple network nodes, based on `squidasm/examples/advanced/ghz/example_ghz.py`.

## Overview

A GHZ state is a maximally entangled state of $n$ qubits:

$$|GHZ_n\rangle = \frac{1}{\sqrt{2}}\left(|0\rangle^{\otimes n} + |1\rangle^{\otimes n}\right)$$

For 3 qubits: $|GHZ_3\rangle = \frac{1}{\sqrt{2}}\left(|000\rangle + |111\rangle\right)$

## Why GHZ States?

GHZ states are fundamental resources for:
- **Quantum secret sharing**
- **Quantum voting protocols**
- **Distributed quantum computing**
- **Quantum sensing**

### Key Property

When measured in the same basis, all qubits give the same outcome:
- Either all 0s OR all 1s
- 50% probability each

## The Protocol

### Chain Architecture

GHZ creation uses a **chain** topology:

```
Node₀ ←EPR→ Node₁ ←EPR→ Node₂ ←EPR→ ... ←EPR→ Nodeₙ₋₁
(start)    (middle)    (middle)           (end)
```

### Algorithm

1. **Start node**: Wait for signal, create EPR with next node
2. **Middle nodes**: 
   - Receive EPR from previous node
   - Create EPR with next node
   - Merge states with CNOT + measurement
   - Send correction to next node
3. **End node**: Receive EPR, apply corrections

### State Evolution

```
Initial: |Φ⁺⟩₀₁ ⊗ |Φ⁺⟩₁₂ = (|00⟩+|11⟩)(|00⟩+|11⟩)/2

After middle node CNOT + measure:
- If m=0: |000⟩ + |111⟩ (GHZ)
- If m=1: |001⟩ + |110⟩ (needs X correction)
```

## Implementation

### The GHZ Program

```python
from typing import List
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from squidasm.util.routines import create_ghz


class GHZProgram(Program):
    def __init__(self, name: str, node_names: List[str]):
        self.name = name
        self.node_names = node_names
        # Peers are all other nodes in the chain
        self.peer_names = [peer for peer in self.node_names if peer != self.name]

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="tutorial_program",
            csockets=self.peer_names,
            epr_sockets=self.peer_names,
            max_qubits=2,
        )

    def run(self, context: ProgramContext):
        connection = context.connection

        # Determine position in chain
        i = self.node_names.index(self.name)
        
        # Initialize socket references
        down_epr_socket = None
        up_epr_socket = None
        down_socket = None
        up_socket = None

        # Set up "down" connection (to previous node)
        if i > 0:
            down_name = self.node_names[i - 1]
            down_epr_socket = context.epr_sockets[down_name]
            down_socket = context.csockets[down_name]
        
        # Set up "up" connection (to next node)
        if i < len(self.node_names) - 1:
            up_name = self.node_names[i + 1]
            up_epr_socket = context.epr_sockets[up_name]
            up_socket = context.csockets[up_name]

        # Create GHZ using utility routine
        qubit, m = yield from create_ghz(
            connection,
            down_epr_socket,
            up_epr_socket,
            down_socket,
            up_socket,
            do_corrections=True,  # Apply corrections automatically
        )

        # Measure the final GHZ qubit
        q_measure = qubit.measure()
        yield from connection.flush()

        return {"name": self.name, "result": int(q_measure)}
```

### Understanding Node Roles

| Position | Role | Down Socket | Up Socket |
|----------|------|-------------|-----------|
| `i = 0` | Start | None | Yes |
| `0 < i < n-1` | Middle | Yes | Yes |
| `i = n-1` | End | Yes | None |

## The `create_ghz` Utility

The heavy lifting is done by `squidasm.util.routines.create_ghz`:

```python
def create_ghz(
    connection: BaseNetQASMConnection,
    down_epr_socket: Optional[EPRSocket] = None,
    up_epr_socket: Optional[EPRSocket] = None,
    down_socket: Optional[Socket] = None,
    up_socket: Optional[Socket] = None,
    do_corrections: bool = False,
) -> Generator[None, None, Tuple[Qubit, int]]:
    """
    Create GHZ state across nodes in a chain.
    
    Returns:
        (qubit, measurement): The qubit in GHZ state and 
                             measurement outcome (0 if corrected)
    """
```

### Role Detection

```python
    if down_epr_socket is None and up_epr_socket is None:
        raise TypeError("Both sockets cannot be None")

    if down_epr_socket is None:
        role = _Role.start
    elif up_epr_socket is None:
        role = _Role.end
    else:
        role = _Role.middle
```

### Start Node Logic

```python
    if role == _Role.start:
        # Wait for signal from first middle/end node
        yield from up_socket.recv()
        # Create EPR pair upstream
        q = up_epr_socket.create_keep()[0]
        m = 0  # No measurement for start
```

### Middle Node Logic

```python
    elif role == _Role.middle:
        # Signal downstream that we're ready
        down_socket.send("")
        # Receive EPR from downstream
        q = down_epr_socket.recv_keep()[0]
        
        # Wait for upstream to be ready
        yield from up_socket.recv()
        # Create EPR upstream
        q_up = up_epr_socket.create_keep()[0]
        
        # Merge states: CNOT + measure
        q.cnot(q_up)
        m = q_up.measure()
```

### End Node Logic

```python
    elif role == _Role.end:
        # Signal downstream that we're ready
        down_socket.send("")
        # Receive EPR from downstream
        q = down_epr_socket.recv_keep()[0]
        m = 0  # No measurement for end
```

### Corrections

```python
    if do_corrections:
        if role == _Role.start:
            # Start sends "0" (no correction needed)
            up_socket.send(str(0))
        else:
            # Receive cumulative correction from downstream
            corr = yield from down_socket.recv()
            corr = int(corr)
            
            # Apply X if correction is 1
            if corr == 1:
                q.X()
            
            if role == _Role.middle:
                # Pass updated correction upstream
                corr = (corr + m) % 2  # XOR with our measurement
                up_socket.send(str(corr))
```

## Network Configuration

### Programmatic Complete Graph

```python
from netsquid_netbuilder.modules.clinks.default import DefaultCLinkConfig
from netsquid_netbuilder.modules.qlinks.perfect import PerfectQLinkConfig
from squidasm.util.util import create_complete_graph_network


num_nodes = 6
node_names = [f"Node_{i}" for i in range(num_nodes)]

cfg = create_complete_graph_network(
    node_names,
    "perfect",                              # Quantum link type
    PerfectQLinkConfig(state_delay=100),    # Link config
    clink_typ="default",                    # Classical link type
    clink_cfg=DefaultCLinkConfig(delay=100) # Classical config
)
```

### Why Complete Graph?

Although GHZ uses a chain, the `create_complete_graph_network` utility:
- Creates all pairwise connections
- Simplifies configuration for arbitrary topologies
- Allows different protocols without reconfiguration

## Running the Simulation

```python
from squidasm.run.stack.run import run


if __name__ == "__main__":
    num_nodes = 6
    node_names = [f"Node_{i}" for i in range(num_nodes)]

    cfg = create_complete_graph_network(
        node_names,
        "perfect",
        PerfectQLinkConfig(state_delay=100),
        clink_typ="default",
        clink_cfg=DefaultCLinkConfig(delay=100),
    )

    # Create programs for each node
    programs = {name: GHZProgram(name, node_names) for name in node_names}

    # Run simulation
    results = run(config=cfg, programs=programs, num_times=1)

    # Verify GHZ property
    reference_result = results[0][0]["result"]
    for node_result in results:
        node_result = node_result[0]
        print(f"{node_result['name']} measures: {node_result['result']}")
        assert node_result["result"] == reference_result  # All same!
```

### Expected Output

```
Node_0 measures: 0
Node_1 measures: 0
Node_2 measures: 0
Node_3 measures: 0
Node_4 measures: 0
Node_5 measures: 0
```

Or:

```
Node_0 measures: 1
Node_1 measures: 1
Node_2 measures: 1
Node_3 measures: 1
Node_4 measures: 1
Node_5 measures: 1
```

## Protocol Flow Diagram

```
Time
  │
  │   Node_0        Node_1        Node_2        Node_3
  │   (start)       (middle)      (middle)      (end)
  │     │             │             │             │
  ▼     │◄── "" ─────│             │             │
       │◄── "" ─────────────────────│             │
       │◄── "" ──────────────────────────────────│
       │             │             │             │
  1    │ create_keep │             │             │
       │────────────►│ recv_keep   │             │
       │             │             │             │
  2    │             │ create_keep │             │
       │             │────────────►│ recv_keep   │
       │             │             │             │
  3    │             │             │ create_keep │
       │             │             │────────────►│ recv_keep
       │             │             │             │
  4    │             │ CNOT+meas   │             │
       │             │────m₁──────►│ CNOT+meas   │
       │             │             │────m₂──────►│
       │             │             │             │
  5    │─── "0" ────►│             │             │
       │             │─corr₁──────►│             │
       │             │             │─corr₂──────►│
       │             │             │             │
  6    │             │ X if c=1    │ X if c=1    │ X if c=1
       │             │             │             │
       ▼             ▼             ▼             ▼
       GHZ state distributed across all nodes
```

## Mathematical Analysis

### Initial State (3 nodes)

After EPR pairs are created:

$$|\psi_0\rangle = |\Phi^+\rangle_{01} \otimes |\Phi^+\rangle_{12}$$

$$= \frac{1}{2}(|00\rangle + |11\rangle)_{01} \otimes (|00\rangle + |11\rangle)_{12}$$

$$= \frac{1}{2}(|000\rangle + |011\rangle + |100\rangle + |111\rangle)_{012}$$

### After CNOT at Node 1

CNOT from qubit 1 to qubit 1' (the second EPR qubit):

$$|\psi_1\rangle = \frac{1}{2}(|000\rangle + |011\rangle + |110\rangle + |101\rangle)$$

### After Measurement

Measuring qubit 1 in Z basis:
- **m=0**: $|00\rangle_0 + |11\rangle_2 \otimes |0\rangle_1 = |GHZ\rangle$
- **m=1**: $|01\rangle + |10\rangle$ → Apply X to get $|00\rangle + |11\rangle$

## Scaling Analysis

| Nodes | EPR Pairs | Messages | Time (perfect) |
|-------|-----------|----------|----------------|
| 2 | 1 | 2 | O(1) |
| 3 | 2 | 4 | O(1) |
| n | n-1 | 2(n-1) | O(1) (parallel) |

The protocol is efficient because:
- EPR generation can be pipelined
- Each node only needs 2 qubits
- Classical corrections are O(1) bits

## Exercises

### Exercise 1: Verify Correlations

Run 1000 iterations and verify:
- All nodes always agree
- 50% chance of all 0s, 50% all 1s

### Exercise 2: Different Bases

Modify to measure in X basis:
```python
qubit.H()  # Rotate to X basis
q_measure = qubit.measure()
```

Verify still perfect correlation.

### Exercise 3: Add Noise

Change to depolarise link:
```python
cfg = create_complete_graph_network(
    node_names,
    "depolarise",
    DepolariseLinkConfig(fidelity=0.95),
    ...
)
```

Measure degradation in correlation.

## Common Issues

### Issue: Deadlock

**Symptom**: Simulation hangs

**Cause**: Nodes waiting for signals in wrong order

**Solution**: Ensure start node waits for signals before creating EPR

### Issue: Wrong Correlations

**Symptom**: Nodes don't agree

**Cause**: Missing corrections or wrong measurement basis

**Solution**: Set `do_corrections=True` and verify basis

## Next Steps

- [Link Layer Operations](06_link_layer.md) - Direct EPR patterns
- [Multi-Node Tutorial](../5_multi_node.md) - General multi-node programming
- [Performance](../../advanced/performance.md) - Scaling optimization

## See Also

- [EPR Sockets](../../foundations/epr_sockets.md) - Entanglement generation
- [Classical Communication](../../foundations/classical_communication.md) - Coordination
- [squidasm.util.routines](../../api/util_package.md) - Utility functions
