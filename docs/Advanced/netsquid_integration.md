# NetSquid Integration

This guide explains how SquidASM integrates with NetSquid and how to access NetSquid's advanced features directly.

## Overview

SquidASM is built on top of **NetSquid**, a discrete-event quantum network simulator. Understanding this integration enables:

1. **Custom noise models** - Define physics beyond built-in options
2. **Advanced analysis** - Access detailed quantum state information
3. **Custom components** - Extend the simulation framework
4. **Hybrid simulations** - Mix SquidASM protocols with NetSquid features

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Your Protocol                        │
│                   (Program class)                       │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                     SquidASM                            │
│         (High-level quantum network API)                │
│  ┌──────────────┐  ┌─────────────┐  ┌───────────────┐  │
│  │    Program   │  │ProgramContext│  │StackNetworkCfg│  │
│  │   Interface  │  │   & Stack   │  │  & run()      │  │
│  └──────────────┘  └─────────────┘  └───────────────┘  │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                     NetQASM                             │
│         (Instruction set for quantum networks)          │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                     NetSquid                            │
│         (Discrete-event quantum simulation)             │
│  ┌──────────────┐  ┌─────────────┐  ┌───────────────┐  │
│  │   Qubits &   │  │   Network   │  │     Noise     │  │
│  │   States     │  │   Channels  │  │    Models     │  │
│  └──────────────┘  └─────────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Accessing NetSquid Qubits

### From SquidASM Qubits

```python
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
import netsquid as ns
from netsquid.qubits import qubitapi as qapi

class InspectionProgram(Program):
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="inspector",
            csockets=["Bob"],
            epr_sockets=["Bob"]
        )
    
    def run(self, context: ProgramContext):
        epr_socket = context.epr_sockets["Bob"]
        
        # Create EPR pair through SquidASM
        qubit = epr_socket.create_keep()[0]
        yield from context.connection.flush()
        
        # Access underlying NetSquid qubit
        # Note: This requires understanding SquidASM internals
        # and may change between versions
        
        return {"result": "inspected"}
```

### Direct Qubit State Analysis

```python
import netsquid as ns
from netsquid.qubits import qubitapi as qapi

def analyze_qubit_state(ns_qubit):
    """Analyze a NetSquid qubit's state."""
    
    # Get density matrix
    dm = qapi.reduced_dm(ns_qubit)
    print(f"Density matrix:\n{dm}")
    
    # Calculate fidelity with |0⟩
    fid_0 = qapi.fidelity(ns_qubit, ns.s0, squared=True)
    print(f"Fidelity with |0⟩: {fid_0:.4f}")
    
    # Calculate fidelity with |1⟩
    fid_1 = qapi.fidelity(ns_qubit, ns.s1, squared=True)
    print(f"Fidelity with |1⟩: {fid_1:.4f}")
    
    # Calculate fidelity with |+⟩
    fid_plus = qapi.fidelity(ns_qubit, ns.h0, squared=True)
    print(f"Fidelity with |+⟩: {fid_plus:.4f}")
    
    return dm

def analyze_bell_pair(qubit_a, qubit_b):
    """Analyze fidelity with Bell states."""
    
    # Bell states
    bell_states = {
        'Φ+': ns.b00,  # (|00⟩ + |11⟩)/√2
        'Φ-': ns.b01,  # (|00⟩ - |11⟩)/√2
        'Ψ+': ns.b10,  # (|01⟩ + |10⟩)/√2
        'Ψ-': ns.b11,  # (|01⟩ - |10⟩)/√2
    }
    
    for name, bell in bell_states.items():
        fid = qapi.fidelity([qubit_a, qubit_b], bell, squared=True)
        print(f"Fidelity with |{name}⟩: {fid:.4f}")
```

## Custom Noise Models

### Creating Custom Noise

NetSquid provides several noise model types:

```python
from netsquid.components.models import DepolarNoiseModel, DephaseNoiseModel
from netsquid.components.models import T1T2NoiseModel, FibreDelayModel
import netsquid.components.instructions as instr

# Depolarizing noise
depolar_model = DepolarNoiseModel(depolar_rate=0.01)

# Dephasing noise
dephase_model = DephaseNoiseModel(dephase_rate=0.005)

# T1/T2 decoherence
t1t2_model = T1T2NoiseModel(T1=1e6, T2=5e5)
```

### Custom Physical Channel Model

```python
from netsquid.components.models import FibreDelayModel, FibreLossModel
from netsquid.components import QuantumChannel
import numpy as np

class CustomLossModel:
    """Custom loss model for quantum channel."""
    
    def __init__(self, loss_per_km=0.2, base_loss=0.1):
        self.loss_per_km = loss_per_km  # dB/km
        self.base_loss = base_loss      # dB
    
    def calculate_loss(self, distance_km):
        """Calculate total loss probability."""
        total_loss_db = self.base_loss + self.loss_per_km * distance_km
        transmission = 10 ** (-total_loss_db / 10)
        return 1 - transmission  # Loss probability

# Create channel with custom model
def create_custom_channel(name, length_km, custom_loss_model):
    """Create a quantum channel with custom loss."""
    
    # Standard delay model (speed of light in fiber)
    delay_model = FibreDelayModel(c=200000)  # km/s
    
    # Built-in loss model
    loss_model = FibreLossModel(
        p_loss_init=custom_loss_model.base_loss,
        p_loss_length=custom_loss_model.loss_per_km
    )
    
    channel = QuantumChannel(
        name=name,
        length=length_km,
        models={
            "delay_model": delay_model,
            "quantum_loss_model": loss_model
        }
    )
    
    return channel
```

### Custom Gate Noise

```python
from netsquid.components.models import QuantumErrorModel
from netsquid.qubits import operators as ops
import numpy as np

class CustomGateNoise(QuantumErrorModel):
    """Custom noise model for quantum gates."""
    
    def __init__(self, error_prob, coherent_error_angle=0):
        super().__init__()
        self.error_prob = error_prob
        self.coherent_angle = coherent_error_angle
    
    def error_operation(self, qubits, delta_time=0, **kwargs):
        """Apply noise after gate operation."""
        
        for qubit in qubits:
            # Random Pauli error with probability
            if np.random.random() < self.error_prob:
                pauli = np.random.choice(['X', 'Y', 'Z'])
                if pauli == 'X':
                    ops.X | qubit
                elif pauli == 'Y':
                    ops.Y | qubit
                else:
                    ops.Z | qubit
            
            # Small coherent rotation error (systematic)
            if self.coherent_angle != 0:
                ops.Rz(self.coherent_angle) | qubit
```

## Simulation Time Control

### Accessing Simulation Time

```python
import netsquid as ns

# Current simulation time (nanoseconds)
current_time = ns.sim_time()
print(f"Current simulation time: {current_time} ns")

# Reset simulation
ns.sim_reset()

# Run simulation for specific time
ns.sim_run(duration=1000)  # Run for 1000 ns
```

### Time-Based Analysis

```python
def time_protocol_phases(context, epr_socket, csocket):
    """Measure time spent in each protocol phase."""
    import netsquid as ns
    
    times = {}
    
    # Phase 1: EPR generation
    t_start = ns.sim_time()
    qubit = epr_socket.create_keep()[0]
    yield from context.connection.flush()
    times['epr_generation'] = ns.sim_time() - t_start
    
    # Phase 2: Local operations
    t_start = ns.sim_time()
    qubit.H()
    qubit.rot_Z(angle=3.14159/4)
    yield from context.connection.flush()
    times['local_ops'] = ns.sim_time() - t_start
    
    # Phase 3: Classical communication
    t_start = ns.sim_time()
    csocket.send("message")
    yield from context.connection.flush()
    times['classical_comm'] = ns.sim_time() - t_start
    
    # Phase 4: Measurement
    t_start = ns.sim_time()
    result = qubit.measure()
    yield from context.connection.flush()
    times['measurement'] = ns.sim_time() - t_start
    
    return times
```

## NetSquid Components

### Understanding the Stack

SquidASM creates these NetSquid components internally:

```python
# Conceptual structure (simplified)

class QuantumProcessor:
    """Holds qubits and executes operations."""
    qubits: List[Qubit]
    noise_model: NoiseModel

class QuantumChannel:
    """Transmits qubits between nodes."""
    delay_model: DelayModel
    loss_model: LossModel

class ClassicalChannel:
    """Transmits classical messages."""
    delay: float

class Node:
    """Network node with quantum processor."""
    qprocessor: QuantumProcessor
    
class Network:
    """Collection of nodes and channels."""
    nodes: Dict[str, Node]
    channels: List[Channel]
```

### Accessing Components After Build

```python
from squidasm.run.stack.build import build_network

# Build the network
network, stacks = build_network(config)

# Access NetSquid components
for name, stack in stacks.items():
    # Each stack has access to:
    # - host: Host processor
    # - qnodeos: Quantum node operating system
    # - netstack: Network stack for EPR
    # - qdevice: Quantum device/processor
    
    print(f"Stack: {name}")
    print(f"  Components available: {dir(stack)}")
```

## Custom EPR Generation

### Understanding the Link Models

```python
# SquidASM link types map to NetSquid implementations:

# typ: perfect
# - Instant, perfect Bell pairs
# - No noise, no loss, no delay

# typ: depolarise  
# - Bell pairs with depolarizing noise
# - Configurable fidelity
# - Simple model for quick testing

# typ: heralded
# - Physical model of heralded entanglement
# - Double-click protocol simulation
# - More accurate timing
```

### Custom Link Implementation

```python
from netsquid.components import QuantumChannel, ClassicalChannel
from netsquid.components.models import FibreDelayModel
from netsquid.qubits import qubitapi as qapi
from netsquid.qubits import operators as ops
import numpy as np

def create_custom_epr_pair(fidelity=1.0, target_state='phi_plus'):
    """Create EPR pair with specific fidelity and state."""
    
    # Create ideal Bell state
    if target_state == 'phi_plus':
        q1, q2 = qapi.create_qubits(2)
        qapi.operate(q1, ops.H)
        qapi.operate([q1, q2], ops.CNOT)
    elif target_state == 'phi_minus':
        q1, q2 = qapi.create_qubits(2)
        qapi.operate(q1, ops.H)
        qapi.operate([q1, q2], ops.CNOT)
        qapi.operate(q2, ops.Z)
    # ... other Bell states
    
    # Apply depolarizing noise to reduce fidelity
    if fidelity < 1.0:
        depolar_prob = (1 - fidelity) * 4/3  # Werner state formula
        for q in [q1, q2]:
            if np.random.random() < depolar_prob:
                pauli = np.random.choice(['I', 'X', 'Y', 'Z'])
                if pauli == 'X':
                    qapi.operate(q, ops.X)
                elif pauli == 'Y':
                    qapi.operate(q, ops.Y)
                elif pauli == 'Z':
                    qapi.operate(q, ops.Z)
    
    return q1, q2
```

## Advanced State Analysis

### Tomography Helper

```python
import numpy as np
from netsquid.qubits import qubitapi as qapi
from netsquid.qubits import operators as ops

def single_qubit_tomography(qubit, num_measurements=1000):
    """Perform single-qubit state tomography."""
    
    # We need to measure in X, Y, Z bases multiple times
    # This is a simplified conceptual example
    
    results = {'X': [], 'Y': [], 'Z': []}
    
    # In practice, you'd create many copies and measure
    # Here we just show the measurement operators
    
    # Z-basis: standard measurement
    # X-basis: H then measure
    # Y-basis: S† then H then measure
    
    # Get density matrix directly (simulation advantage!)
    dm = qapi.reduced_dm(qubit)
    
    # Calculate Bloch vector from density matrix
    # ρ = (I + r·σ)/2
    # rx = Tr(ρ·X), ry = Tr(ρ·Y), rz = Tr(ρ·Z)
    
    pauli_x = np.array([[0, 1], [1, 0]])
    pauli_y = np.array([[0, -1j], [1j, 0]])
    pauli_z = np.array([[1, 0], [0, -1]])
    
    rx = np.real(np.trace(dm @ pauli_x))
    ry = np.real(np.trace(dm @ pauli_y))
    rz = np.real(np.trace(dm @ pauli_z))
    
    return {
        'density_matrix': dm,
        'bloch_vector': (rx, ry, rz),
        'purity': np.real(np.trace(dm @ dm))
    }

def entanglement_measure(qubit_a, qubit_b):
    """Calculate entanglement measures for two qubits."""
    
    # Get joint density matrix
    dm = qapi.reduced_dm([qubit_a, qubit_b])
    
    # Calculate partial trace (subsystem A)
    dm_a = np.trace(dm.reshape(2, 2, 2, 2), axis1=1, axis2=3)
    
    # Von Neumann entropy of subsystem
    eigenvalues = np.linalg.eigvalsh(dm_a)
    eigenvalues = eigenvalues[eigenvalues > 1e-10]  # Remove zeros
    entropy = -np.sum(eigenvalues * np.log2(eigenvalues))
    
    # Concurrence (for two qubits)
    # C = max(0, λ1 - λ2 - λ3 - λ4)
    # where λi are eigenvalues of sqrt(sqrt(ρ) * ρ̃ * sqrt(ρ))
    
    return {
        'entropy_of_entanglement': entropy,
        'density_matrix': dm,
        'subsystem_dm': dm_a
    }
```

## Hybrid Simulations

### Combining SquidASM with Direct NetSquid

```python
import netsquid as ns
from netsquid.qubits import qubitapi as qapi
from squidasm.run.stack.run import run
from squidasm.run.stack.config import StackNetworkConfig

def hybrid_simulation():
    """Run SquidASM protocol with NetSquid analysis."""
    
    # Standard SquidASM setup
    config = StackNetworkConfig.from_file("config.yaml")
    
    programs = {
        "Alice": AliceProgram(),
        "Bob": BobProgram()
    }
    
    # Run simulation
    results = run(config=config, programs=programs, num_times=100)
    
    # Post-simulation NetSquid analysis
    # (Note: quantum states are collapsed after measurement)
    print(f"Final simulation time: {ns.sim_time()} ns")
    
    # Reset for next experiment
    ns.sim_reset()
    
    return results
```

## Best Practices

### 1. Prefer SquidASM Abstractions

```python
# Good: Use SquidASM's high-level API
qubit = epr_socket.create_keep()[0]
qubit.H()
result = qubit.measure()

# Only drop to NetSquid for:
# - Custom noise models
# - State inspection (debugging)
# - Features not exposed by SquidASM
```

### 2. Mind Version Compatibility

```python
# NetSquid and SquidASM versions must be compatible
# Check documentation for version requirements

import netsquid
import squidasm

print(f"NetSquid version: {netsquid.__version__}")
print(f"SquidASM version: {squidasm.__version__}")
```

### 3. Use Simulation Time Correctly

```python
import netsquid as ns

# Simulation time is in nanoseconds
# Real time and simulation time are different

# This runs instantly in real time but advances simulation time:
ns.sim_run(duration=1e9)  # 1 second of simulation time
```

### 4. State Inspection is Non-Physical

```python
# In real quantum systems, you can't inspect state without measurement
# Simulation allows "cheating" for debugging and analysis

# Use this for:
# - Debugging
# - Understanding protocol behavior
# - Verifying implementations

# Don't use for:
# - Realistic protocol performance claims
# - Anything that would require state knowledge in reality
```

## See Also

- [Custom Protocols](custom_protocols.md) - Building protocols
- [Noise Models](noise_models.md) - Understanding noise
- [Architecture Overview](../architecture/overview.md) - System architecture
- [NetSquid Documentation](https://netsquid.org/documentation/) - Full NetSquid reference
