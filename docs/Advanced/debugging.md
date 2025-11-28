# Debugging SquidASM Simulations

This guide covers techniques for debugging quantum network simulations in SquidASM.

## Overview

Debugging quantum network simulations requires understanding:

1. **Classical debugging** - Logic errors, configuration issues
2. **Quantum state inspection** - What's happening to qubits
3. **Timing analysis** - When events occur in simulation
4. **Logging configuration** - Capturing detailed execution traces

## Logging Configuration

### Setting Log Levels

SquidASM uses Python's standard logging module:

```python
import logging
from squidasm.run.stack.run import run

# Set global log level
logging.basicConfig(level=logging.DEBUG)

# Or configure specific loggers
logging.getLogger("squidasm").setLevel(logging.DEBUG)
logging.getLogger("netqasm").setLevel(logging.INFO)
logging.getLogger("netsquid").setLevel(logging.WARNING)
```

### Logger Hierarchy

```
squidasm                    # Top-level SquidASM
├── squidasm.sim            # Simulation components
│   ├── squidasm.sim.stack  # Stack simulation
│   └── squidasm.sim.glob   # Global simulation
├── squidasm.run            # Runtime components
└── squidasm.nqasm          # NetQASM backend

netqasm                     # NetQASM SDK
netsquid                    # NetSquid simulator
pydynaa                     # Event scheduling
```

### Detailed Execution Tracing

```python
import logging
import sys

# Create handler with detailed formatting
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
))

# Configure all quantum-related loggers
for logger_name in ['squidasm', 'netqasm', 'netsquid']:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
```

### Log to File

```python
import logging

logging.basicConfig(
    filename='simulation.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

## Print Debugging

### Strategic Print Statements

```python
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta

class DebugAliceProgram(Program):
    PEER_NAME = "Bob"
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="debug_alice",
            csockets=[self.PEER_NAME],
            epr_sockets=[self.PEER_NAME]
        )
    
    def run(self, context: ProgramContext):
        print(f"[Alice] Starting program")
        print(f"[Alice] Available csockets: {list(context.csockets.keys())}")
        print(f"[Alice] Available epr_sockets: {list(context.epr_sockets.keys())}")
        
        epr_socket = context.epr_sockets[self.PEER_NAME]
        print(f"[Alice] EPR socket obtained")
        
        # Create EPR pair
        print(f"[Alice] Requesting EPR pair...")
        qubit = epr_socket.create_keep()[0]
        print(f"[Alice] EPR pair created, qubit ID: {qubit.qubit_id}")
        
        # Measure
        print(f"[Alice] Measuring qubit...")
        result = qubit.measure()
        yield from context.connection.flush()
        
        print(f"[Alice] Measurement result: {int(result)}")
        
        return {"measurement": int(result)}
```

### Timestamped Prints

```python
import time

start_time = time.time()

def debug_print(node, message):
    elapsed = time.time() - start_time
    print(f"[{elapsed:.3f}s] [{node}] {message}")

class TimedProgram(Program):
    def run(self, context: ProgramContext):
        debug_print("Alice", "Program starting")
        # ... operations
        debug_print("Alice", "EPR created")
```

## Common Issues and Solutions

### Issue 1: EPR Socket Not Found

**Symptom:**
```
KeyError: 'Bob'
```

**Debug:**
```python
print(f"Available EPR sockets: {context.epr_sockets.keys()}")
```

**Common Causes:**
1. Peer name mismatch (case-sensitive)
2. Missing peer in `epr_sockets` in `ProgramMeta`
3. No link configured between nodes

**Solution:**
```python
# Verify peer name matches exactly
PEER_NAME = "Bob"  # Must match config.yaml

@property
def meta(self) -> ProgramMeta:
    return ProgramMeta(
        name="alice",
        csockets=[self.PEER_NAME],  # Include peer
        epr_sockets=[self.PEER_NAME]  # Include peer
    )

# Access with same name
epr_socket = context.epr_sockets[self.PEER_NAME]
```

### Issue 2: Program Never Completes

**Symptom:**
Simulation hangs indefinitely

**Debug:**
```python
# Add timeout to run
results = run(
    config=config,
    programs=programs,
    num_times=1
)

# Check if programs are yielding properly
def run(self, context):
    print("Step 1")
    result = some_operation()
    print("Step 2 - about to flush")
    yield from context.connection.flush()  # Must yield from flush!
    print("Step 3 - flush complete")
```

**Common Causes:**
1. Missing `yield from` before `flush()`
2. Deadlock: both nodes waiting for each other
3. Missing classical synchronization

**Solution:**
```python
# Always yield from flush
yield from context.connection.flush()

# Ensure proper synchronization
# Alice sends first, Bob receives first (or vice versa)
```

### Issue 3: Qubit Index Out of Range

**Symptom:**
```
RuntimeError: Qubit index out of range
```

**Debug:**
```python
print(f"Device num_qubits: {config.stacks[0].qdevice_cfg.num_qubits}")
print(f"Qubits requested: {num_qubits_needed}")
```

**Solution:**
```yaml
# Increase num_qubits in config
qdevice_cfg:
  num_qubits: 10  # Must be >= qubits used simultaneously
```

### Issue 4: Classical Socket Not Found

**Symptom:**
```
KeyError: 'Bob'  # When accessing csockets
```

**Debug:**
```python
print(f"Available csockets: {context.csockets.keys()}")
```

**Solution:**
```python
@property
def meta(self) -> ProgramMeta:
    return ProgramMeta(
        name="alice",
        csockets=[self.PEER_NAME],  # Must list classical socket peers
        epr_sockets=[self.PEER_NAME]
    )
```

### Issue 5: Results All Zero or Random

**Symptom:**
Results don't match expected quantum correlations

**Debug:**
```python
# Check configuration
print(f"Link fidelity: {config.links[0].cfg.fidelity}")
print(f"Gate noise: {config.stacks[0].qdevice_cfg.single_qubit_gate_depolar_prob}")

# Run with perfect config to verify logic
config.links[0].cfg.fidelity = 1.0
config.stacks[0].qdevice_cfg.single_qubit_gate_depolar_prob = 0.0
```

**Common Causes:**
1. High noise levels
2. Incorrect gate operations
3. Wrong measurement bases

### Issue 6: Configuration Parse Error

**Symptom:**
```
yaml.YAMLError: ...
```

**Debug:**
```python
# Validate YAML structure
import yaml
with open("config.yaml") as f:
    try:
        config = yaml.safe_load(f)
        print("YAML is valid")
        print(f"Keys: {config.keys()}")
    except yaml.YAMLError as e:
        print(f"YAML error: {e}")
```

**Solution:**
Check for:
- Incorrect indentation
- Missing colons
- Tab characters (use spaces)

## Inspecting Quantum States

### Using NetSquid Directly

```python
import netsquid as ns
from netsquid.qubits import qubitapi as qapi

def inspect_qubit_state(qubit):
    """Print the current state of a qubit."""
    # Get the NetSquid qubit
    ns_qubit = qubit.qubit
    
    # Get density matrix
    dm = qapi.reduced_dm(ns_qubit)
    print(f"Density matrix:\n{dm}")
    
    # Get fidelity with |0⟩
    fidelity_0 = qapi.fidelity(ns_qubit, ns.s0, squared=True)
    print(f"Fidelity with |0⟩: {fidelity_0:.3f}")
```

### Checking EPR Fidelity

```python
def check_epr_fidelity(qubit_a, qubit_b):
    """Check fidelity of EPR pair with ideal Bell state."""
    import netsquid as ns
    from netsquid.qubits import qubitapi as qapi
    
    # Get the qubits
    ns_qa = qubit_a.qubit
    ns_qb = qubit_b.qubit
    
    # Ideal Bell state |Φ+⟩
    bell = ns.b00
    
    # Calculate fidelity
    fidelity = qapi.fidelity([ns_qa, ns_qb], bell, squared=True)
    print(f"EPR fidelity: {fidelity:.3f}")
    return fidelity
```

## Timing Analysis

### Simulation Time Tracking

```python
import netsquid as ns

class TimingProgram(Program):
    def run(self, context: ProgramContext):
        t_start = ns.sim_time()
        print(f"[{ns.sim_time()}] Starting")
        
        # EPR generation
        qubit = epr_socket.create_keep()[0]
        yield from context.connection.flush()
        t_epr = ns.sim_time()
        print(f"[{ns.sim_time()}] EPR created (took {t_epr - t_start} ns)")
        
        # Local operations
        qubit.H()
        yield from context.connection.flush()
        t_ops = ns.sim_time()
        print(f"[{ns.sim_time()}] Operations done (took {t_ops - t_epr} ns)")
        
        # Measurement
        result = qubit.measure()
        yield from context.connection.flush()
        t_end = ns.sim_time()
        print(f"[{ns.sim_time()}] Measurement done (took {t_end - t_ops} ns)")
        
        print(f"Total time: {t_end - t_start} ns")
```

### Event Scheduling Analysis

```python
import netsquid as ns

# Before running
print(f"Simulation time before: {ns.sim_time()}")

results = run(config=config, programs=programs, num_times=1)

print(f"Simulation time after: {ns.sim_time()}")
```

## Test-Driven Debugging

### Unit Testing Programs

```python
import unittest
from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run

class TestMyProtocol(unittest.TestCase):
    def setUp(self):
        self.config = StackNetworkConfig.from_file("test_config.yaml")
    
    def test_basic_execution(self):
        """Test that program executes without error."""
        programs = {
            "Alice": AliceProgram(),
            "Bob": BobProgram()
        }
        results = run(config=self.config, programs=programs, num_times=1)
        self.assertIsNotNone(results)
    
    def test_correlation(self):
        """Test quantum correlation in results."""
        programs = {
            "Alice": AliceProgram(),
            "Bob": BobProgram()
        }
        results = run(config=self.config, programs=programs, num_times=100)
        
        # Count matching results
        matches = sum(
            1 for alice, bob in results
            if alice['bit'] == bob['bit']
        )
        
        # Should match with high probability for Bell state
        self.assertGreater(matches, 90)  # At least 90%

if __name__ == '__main__':
    unittest.main()
```

### Minimal Reproducible Example

When reporting bugs, create minimal examples:

```python
"""Minimal example demonstrating issue X."""
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run

# Minimal program
class MinimalAlice(Program):
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(name="alice", csockets=["Bob"], epr_sockets=["Bob"])
    
    def run(self, context: ProgramContext):
        # Minimal operations to reproduce issue
        yield from context.connection.flush()
        return {}

class MinimalBob(Program):
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(name="bob", csockets=["Alice"], epr_sockets=["Alice"])
    
    def run(self, context: ProgramContext):
        yield from context.connection.flush()
        return {}

# Minimal config (inline)
config_yaml = """
stacks:
  - name: Alice
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 1
  - name: Bob
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 1

links:
  - stack1: Alice
    stack2: Bob
    typ: perfect

clinks:
  - stack1: Alice
    stack2: Bob
    typ: instant
"""

import yaml
import tempfile
import os

# Write minimal config
with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
    f.write(config_yaml)
    config_path = f.name

try:
    config = StackNetworkConfig.from_file(config_path)
    results = run(
        config=config,
        programs={"Alice": MinimalAlice(), "Bob": MinimalBob()},
        num_times=1
    )
    print(f"Results: {results}")
finally:
    os.unlink(config_path)
```

## Debugging Checklist

### Before Running

- [ ] Config file exists and is valid YAML
- [ ] Node names match between config and programs
- [ ] `ProgramMeta` lists all required sockets
- [ ] `num_qubits` is sufficient
- [ ] Link types are correct

### During Execution

- [ ] All `flush()` calls have `yield from`
- [ ] Classical communication is synchronized
- [ ] EPR sockets accessed with correct peer name
- [ ] Results are collected before flush

### After Running

- [ ] Check if results are returned
- [ ] Verify correlation matches expectations
- [ ] Compare with perfect configuration
- [ ] Review logs for errors

## See Also

- [Noise Models](noise_models.md) - Understanding noise effects
- [Performance Optimization](performance.md) - Speeding up simulations
- [Custom Protocols](custom_protocols.md) - Protocol development
