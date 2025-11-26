# squidasm.util Package

The `squidasm.util` package provides utility functions and pre-built routines for common quantum network operations.

## Overview

```
squidasm.util/
├── util.py            # General utilities
├── routines.py        # Common quantum routines
└── qkd_routine.py     # QKD-specific implementations
```

## General Utilities

### util.py Functions

```python
from squidasm.util.util import (
    create_two_node_network,
    create_complete_graph_network,
    get_qubit_state,
    get_fidelity,
)
```

### create_two_node_network()

Create a simple two-node network configuration.

```python
from squidasm.util.util import create_two_node_network
from squidasm.run.stack.config import (
    DepolariseLinkConfig,
    DefaultCLinkConfig,
)

# Create with default settings
config = create_two_node_network(
    node_names=["Alice", "Bob"]
)

# Create with custom link configurations
config = create_two_node_network(
    node_names=["Alice", "Bob"],
    link_cfg=DepolariseLinkConfig(
        fidelity=0.95,
        t_cycle=10.0,
        prob_success=0.8
    ),
    clink_cfg=DefaultCLinkConfig(delay=1000.0),
    num_qubits=5
)
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `node_names` | List[str] | Names for the two nodes |
| `link_cfg` | LinkConfig | Quantum link configuration |
| `clink_cfg` | CLinkConfig | Classical link configuration |
| `num_qubits` | int | Qubits per node |
| `qdevice_typ` | str | Device type ("generic" or "nv") |

### create_complete_graph_network()

Create a fully connected network with arbitrary number of nodes.

```python
from squidasm.util.util import create_complete_graph_network

# Create 4-node fully connected network
config = create_complete_graph_network(
    node_names=["Alice", "Bob", "Charlie", "Diana"],
    link_cfg=DepolariseLinkConfig(fidelity=0.9),
    clink_cfg=DefaultCLinkConfig(delay=500.0),
    num_qubits=3
)

# The result has:
# - 4 stacks (one per node)
# - 6 quantum links (all pairs connected)
# - 6 classical links (all pairs connected)
```

### get_qubit_state()

Retrieve the current state of a qubit (for debugging/analysis).

```python
from squidasm.util.util import get_qubit_state

# Note: This is typically used during simulation for debugging
# Not available in actual quantum hardware

def run(self, context: ProgramContext):
    q = Qubit(connection)
    q.H()
    
    # Get state before measurement (simulation only)
    # Returns density matrix or state vector
    state = get_qubit_state(q)
    logger.debug(f"Qubit state: {state}")
    
    result = q.measure()
    connection.flush()
```

### get_fidelity()

Calculate fidelity between two quantum states.

```python
from squidasm.util.util import get_fidelity
import numpy as np

# Example: Calculate fidelity with ideal Bell state
ideal_bell = np.array([1, 0, 0, 1]) / np.sqrt(2)
measured_state = get_qubit_state(q1, q2)  # Two-qubit state

fidelity = get_fidelity(ideal_bell, measured_state)
print(f"Fidelity with |Φ+⟩: {fidelity:.4f}")
```

## Common Routines

### routines.py

Pre-built quantum routines for common operations.

```python
from squidasm.util.routines import (
    teleportation_sender,
    teleportation_receiver,
    create_ghz_state,
    bell_measurement,
)
```

### teleportation_sender()

Perform the sender side of quantum teleportation.

```python
from squidasm.util.routines import teleportation_sender

def run(self, context: ProgramContext):
    epr_socket = context.epr_sockets["Bob"]
    csocket = context.csockets["Bob"]
    connection = context.connection
    
    # Create state to teleport
    q_data = Qubit(connection)
    q_data.H()
    q_data.T()  # Some state to teleport
    
    # Get EPR qubit
    q_epr = epr_socket.create_keep()[0]
    
    # Perform teleportation protocol
    m1, m2 = teleportation_sender(q_data, q_epr, connection)
    
    # Send corrections
    csocket.send(f"{m1},{m2}")
    
    return {"corrections": (m1, m2)}
```

### teleportation_receiver()

Perform the receiver side of quantum teleportation.

```python
from squidasm.util.routines import teleportation_receiver

def run(self, context: ProgramContext):
    epr_socket = context.epr_sockets["Alice"]
    csocket = context.csockets["Alice"]
    connection = context.connection
    
    # Receive EPR qubit
    q_epr = epr_socket.recv_keep()[0]
    
    # Receive corrections
    msg = yield from csocket.recv()
    m1, m2 = map(int, msg.split(","))
    
    # Apply corrections
    teleportation_receiver(q_epr, m1, m2, connection)
    
    # q_epr now holds the teleported state
    result = q_epr.measure()
    connection.flush()
    
    return {"result": int(result)}
```

### bell_measurement()

Perform a Bell state measurement on two qubits.

```python
from squidasm.util.routines import bell_measurement

def run(self, context: ProgramContext):
    connection = context.connection
    
    # Get two qubits (from EPR pairs, local creation, etc.)
    q1 = epr_socket1.recv_keep()[0]
    q2 = epr_socket2.recv_keep()[0]
    
    # Perform Bell measurement
    # Returns measurement outcomes that identify the Bell state
    m1, m2 = bell_measurement(q1, q2, connection)
    
    # m1, m2 determine which Bell state:
    # (0, 0) -> |Φ+⟩
    # (0, 1) -> |Ψ+⟩
    # (1, 0) -> |Φ-⟩
    # (1, 1) -> |Ψ-⟩
```

### create_ghz_state()

Create a GHZ state across multiple qubits.

```python
from squidasm.util.routines import create_ghz_state

def run(self, context: ProgramContext):
    connection = context.connection
    
    # Create 3-qubit GHZ state: (|000⟩ + |111⟩)/√2
    qubits = create_ghz_state(connection, num_qubits=3)
    
    # Measure all qubits
    results = [q.measure() for q in qubits]
    connection.flush()
    
    # Results should be either all 0 or all 1
    return {"results": [int(r) for r in results]}
```

## QKD Routines

### qkd_routine.py

Implementations for Quantum Key Distribution protocols.

```python
from squidasm.util.qkd_routine import (
    BB84Sender,
    BB84Receiver,
    E91Sender,
    E91Receiver,
    estimate_qber,
    privacy_amplification,
)
```

### BB84 Protocol

#### BB84Sender

```python
from squidasm.util.qkd_routine import BB84Sender

class AliceQKD(Program):
    PEER_NAME = "Bob"
    
    def __init__(self, key_length: int = 100):
        self.key_length = key_length
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="alice_bb84",
            csockets=[self.PEER_NAME],
            epr_sockets=[self.PEER_NAME],
            max_qubits=1
        )
    
    def run(self, context: ProgramContext):
        sender = BB84Sender(
            csocket=context.csockets[self.PEER_NAME],
            epr_socket=context.epr_sockets[self.PEER_NAME],
            connection=context.connection
        )
        
        # Run BB84 protocol
        raw_key, bases = yield from sender.run(self.key_length)
        
        # Sifting phase (keep matching bases)
        bob_bases = yield from context.csockets[self.PEER_NAME].recv()
        sifted_key = [
            raw_key[i] 
            for i in range(len(raw_key)) 
            if bases[i] == bob_bases[i]
        ]
        
        return {"sifted_key": sifted_key}
```

#### BB84Receiver

```python
from squidasm.util.qkd_routine import BB84Receiver

class BobQKD(Program):
    PEER_NAME = "Alice"
    
    def __init__(self, key_length: int = 100):
        self.key_length = key_length
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="bob_bb84",
            csockets=[self.PEER_NAME],
            epr_sockets=[self.PEER_NAME],
            max_qubits=1
        )
    
    def run(self, context: ProgramContext):
        receiver = BB84Receiver(
            csocket=context.csockets[self.PEER_NAME],
            epr_socket=context.epr_sockets[self.PEER_NAME],
            connection=context.connection
        )
        
        # Run BB84 protocol
        raw_key, bases = yield from receiver.run(self.key_length)
        
        # Send bases for sifting
        context.csockets[self.PEER_NAME].send(bases)
        
        # Receive Alice's bases
        alice_bases = yield from context.csockets[self.PEER_NAME].recv()
        sifted_key = [
            raw_key[i] 
            for i in range(len(raw_key)) 
            if bases[i] == alice_bases[i]
        ]
        
        return {"sifted_key": sifted_key}
```

### E91 Protocol

Entanglement-based QKD protocol.

```python
from squidasm.util.qkd_routine import E91Sender, E91Receiver

class AliceE91(Program):
    def run(self, context: ProgramContext):
        e91 = E91Sender(
            csocket=context.csockets["Bob"],
            epr_socket=context.epr_sockets["Bob"],
            connection=context.connection
        )
        
        # Run E91 protocol
        result = yield from e91.run(num_pairs=100)
        
        return result
```

### QBER Estimation

Calculate Quantum Bit Error Rate from sample measurements.

```python
from squidasm.util.qkd_routine import estimate_qber

def analyze_qkd_results(alice_key, bob_key, sample_size=50):
    """Estimate QBER from sifted keys."""
    
    # Use subset for estimation (don't use for final key)
    alice_sample = alice_key[:sample_size]
    bob_sample = bob_key[:sample_size]
    
    qber = estimate_qber(alice_sample, bob_sample)
    
    print(f"Estimated QBER: {qber:.2%}")
    
    # Security threshold (typically ~11% for BB84)
    if qber > 0.11:
        print("Warning: QBER too high, possible eavesdropper!")
        return None
    
    # Remaining bits form the key
    final_key = alice_key[sample_size:]
    return final_key
```

### Privacy Amplification

Reduce information leakage through hashing.

```python
from squidasm.util.qkd_routine import privacy_amplification

def generate_secure_key(sifted_key, qber):
    """Generate final secure key with privacy amplification."""
    
    # Calculate how much to compress based on QBER
    # Higher QBER requires more compression
    compression_factor = calculate_compression(qber)
    
    # Apply privacy amplification (e.g., universal hashing)
    secure_key = privacy_amplification(
        sifted_key,
        final_length=len(sifted_key) // compression_factor
    )
    
    return secure_key
```

## Utility Classes

### ResultCollector

Helper for collecting and processing simulation results.

```python
from squidasm.util.util import ResultCollector

# Collect results from multiple runs
collector = ResultCollector()

for i in range(100):
    alice_results, bob_results = run(config, programs, num_times=1)
    collector.add(alice_results[0], bob_results[0])

# Analyze
stats = collector.compute_statistics()
print(f"Mean error rate: {stats['mean_error_rate']:.2%}")
print(f"Std dev: {stats['std_error_rate']:.4f}")
```

### TimingAnalyzer

Analyze simulation timing.

```python
from squidasm.util.util import TimingAnalyzer

def run(self, context: ProgramContext):
    analyzer = TimingAnalyzer()
    
    analyzer.mark("start")
    
    # EPR generation
    q = epr_socket.create_keep()[0]
    analyzer.mark("epr_created")
    
    # Operations
    q.H()
    result = q.measure()
    connection.flush()
    analyzer.mark("operations_done")
    
    timing = analyzer.get_report()
    return {
        "result": int(result),
        "timing": timing
    }
```

## Best Practices

### 1. Use Pre-built Routines

```python
# Instead of implementing teleportation manually
# Use the utility routines:
from squidasm.util.routines import teleportation_sender, teleportation_receiver
```

### 2. Calculate QBER for Security Analysis

```python
# Always estimate QBER in QKD implementations
qber = estimate_qber(alice_sample, bob_sample)
if qber > THRESHOLD:
    abort_protocol()
```

### 3. Use Network Generators for Testing

```python
# Quick network setup for testing
config = create_two_node_network(["Alice", "Bob"])

# Parameterized setup for sweeps
for fidelity in [0.8, 0.9, 0.95]:
    config = create_two_node_network(
        ["Alice", "Bob"],
        link_cfg=DepolariseLinkConfig(fidelity=fidelity)
    )
    run_simulation(config, ...)
```

## Module Reference

### squidasm.util.util

| Function | Description |
|----------|-------------|
| `create_two_node_network()` | Create simple two-node network |
| `create_complete_graph_network()` | Create fully connected network |
| `get_qubit_state()` | Get qubit state (simulation only) |
| `get_fidelity()` | Calculate state fidelity |

### squidasm.util.routines

| Function | Description |
|----------|-------------|
| `teleportation_sender()` | Teleportation sending protocol |
| `teleportation_receiver()` | Teleportation receiving protocol |
| `bell_measurement()` | Bell state measurement |
| `create_ghz_state()` | Create GHZ entangled state |

### squidasm.util.qkd_routine

| Class/Function | Description |
|----------------|-------------|
| `BB84Sender` | BB84 protocol sender |
| `BB84Receiver` | BB84 protocol receiver |
| `E91Sender` | E91 protocol sender |
| `E91Receiver` | E91 protocol receiver |
| `estimate_qber()` | Calculate QBER |
| `privacy_amplification()` | Privacy amplification hash |

## See Also

- [squidasm.sim Package](sim_package.md) - Program interface
- [Tutorial 1: Basics](../tutorials/1_basics.md) - Basic operations
- [Advanced Topics](../advanced/index.md) - Custom protocol implementation
