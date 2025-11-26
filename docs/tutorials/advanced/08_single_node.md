# Tutorial 8: Single Node Operations

This tutorial demonstrates **single node** quantum operations without network communication, based on `squidasm/examples/advanced/single_node/example_single_node.py`.

## Overview

While SquidASM is designed for quantum networks, it also supports single-node operations:
- Local quantum algorithms
- Testing qubit operations
- Understanding the instruction stack
- Debugging without network complexity

## Use Cases

| Scenario | Why Single Node? |
|----------|------------------|
| Algorithm development | Test gates without network overhead |
| Debugging | Isolate quantum logic from network issues |
| Education | Learn qubit operations first |
| Benchmarking | Measure gate performance |

## Basic Single Node Program

### Simple Qubit Operations

```python
from typing import Any, Dict, Generator
from netqasm.sdk.qubit import Qubit

from pydynaa import EventExpression
from squidasm.run.stack.config import (
    GenericQDeviceConfig, 
    StackConfig, 
    StackNetworkConfig
)
from squidasm.run.stack.run import run
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta


class SingleNodeProgram(Program):
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="single_node_program",
            csockets=[],           # No classical sockets
            epr_sockets=[],        # No EPR sockets
            max_qubits=1,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection

        # Create a local qubit (not via EPR)
        q = Qubit(conn)
        
        # Apply some gates
        q.X()           # Flip to |1⟩
        q.H()           # Create superposition
        q.rot_Z(angle=3.14159/4)  # Z rotation
        
        # Measure
        m = q.measure()
        
        yield from conn.flush()

        return {"measurement": int(m)}
```

### Configuration (No Links)

```python
if __name__ == "__main__":
    from squidasm.sim.stack.common import LogManager
    LogManager.set_log_level("WARNING")

    # Single node configuration
    node = StackConfig(
        name="node",
        qdevice_typ="generic",
        qdevice_cfg=GenericQDeviceConfig.perfect_config(),
    )
    
    # Network with no links
    cfg = StackNetworkConfig(
        stacks=[node],
        links=[]  # No quantum links
    )

    results = run(cfg, {"node": SingleNodeProgram()}, num_times=100)
    
    # Analyze results
    measurements = [r["measurement"] for r in results[0]]
    num_zeros = sum(1 for m in measurements if m == 0)
    num_ones = sum(1 for m in measurements if m == 1)
    
    print(f"Results: {num_zeros} zeros, {num_ones} ones")
    print(f"Expected: ~50/50 due to H gate")
```

## Using Raw NetQASM Subroutines

For advanced control, you can write raw NetQASM assembly:

### Raw Subroutine Example

```python
from netqasm.lang.parsing.text import parse_text_protosubroutine


# NetQASM assembly code
SUBRT = """
# NETQASM 1.0
# APPID 0
array 1 @0          # Create result array
set Q0 0            # Set qubit register
qalloc Q0           # Allocate qubit
init Q0             # Initialize to |0⟩
x Q0                # Apply X gate
meas Q0 M0          # Measure
qfree Q0            # Free qubit
store M0 @0[0]      # Store result
ret_arr @0          # Return array
"""


class RawSubroutineProgram(Program):
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="raw_program",
            csockets=[],
            epr_sockets=[],
            max_qubits=1,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        conn = context.connection

        # Parse and commit raw subroutine
        subrt = parse_text_protosubroutine(SUBRT)
        yield from conn.commit_protosubroutine(subrt)

        # Get result from shared memory
        result = conn.shared_memory.get_array(0)
        
        return {"result": result[0] if result else None}
```

### Understanding the Subroutine

```nasm
# NETQASM 1.0       # Version declaration
# APPID 0           # Application ID

array 1 @0          # Allocate array of size 1 at address @0
set Q0 0            # Set qubit virtual ID to 0
qalloc Q0           # Request qubit from processor
init Q0             # Initialize qubit to |0⟩
x Q0                # Apply X gate (flip to |1⟩)
meas Q0 M0          # Measure qubit, store in M0
qfree Q0            # Release qubit back to processor
store M0 @0[0]      # Store M0 in array @0 at index 0
ret_arr @0          # Return array @0 to application
```

### Key Instructions

| Instruction | Description |
|-------------|-------------|
| `array n @a` | Allocate array of n elements at address a |
| `set Q0 n` | Set qubit register Q0 to virtual ID n |
| `qalloc Q0` | Allocate physical qubit for Q0 |
| `init Q0` | Initialize Q0 to \|0⟩ |
| `x/y/z Q0` | Apply Pauli gate |
| `h Q0` | Apply Hadamard |
| `rot_x/y/z Q0 n d` | Rotate by n*π/(2^d) |
| `meas Q0 M0` | Measure Q0, store in M0 |
| `qfree Q0` | Release qubit |
| `store R @a[i]` | Store register in array |
| `ret_arr @a` | Return array to application |

## NV Device Single Node

Single node works with NV devices too:

```python
from squidasm.run.stack.config import NVQDeviceConfig


class NVSingleNodeProgram(Program):
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="nv_single_node",
            csockets=[],
            epr_sockets=[],
            max_qubits=2,  # Electron + 1 carbon
        )

    def run(self, context: ProgramContext):
        conn = context.connection

        # On NV: Q0 is electron, Q1+ are carbons
        electron = Qubit(conn)  # Gets electron
        carbon = Qubit(conn)    # Gets carbon
        
        # Entangle electron and carbon
        electron.H()
        electron.cnot(carbon)  # On NV, this is actually a controlled rotation
        
        # Measure
        m_electron = electron.measure()
        m_carbon = carbon.measure()
        
        yield from conn.flush()
        
        return {
            "electron": int(m_electron),
            "carbon": int(m_carbon)
        }


if __name__ == "__main__":
    node = StackConfig(
        name="nv_node",
        qdevice_typ="nv",  # NV device
        qdevice_cfg=NVQDeviceConfig.perfect_config(),
    )
    
    cfg = StackNetworkConfig(stacks=[node], links=[])
    
    results = run(cfg, {"nv_node": NVSingleNodeProgram()}, num_times=100)
    
    # Should see correlated results due to entanglement
    for r in results[0][:10]:
        print(f"Electron: {r['electron']}, Carbon: {r['carbon']}")
```

## Combining SDK and Raw Subroutines

You can mix SDK operations with raw subroutines:

```python
class HybridProgram(Program):
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="hybrid_program",
            csockets=[],
            epr_sockets=[],
            max_qubits=1,
        )

    def run(self, context: ProgramContext):
        conn = context.connection

        # SDK operations
        q = Qubit(conn)
        q.H()
        m1 = q.measure()
        
        # Flush SDK operations
        yield from conn.flush()
        
        print(f"SDK measurement: {int(m1)}")

        # Raw subroutine for more operations
        raw_subrt = """
# NETQASM 1.0
# APPID 0
array 1 @0
set Q0 0
qalloc Q0
init Q0
h Q0
meas Q0 M0
qfree Q0
store M0 @0[0]
ret_arr @0
"""
        subrt = parse_text_protosubroutine(raw_subrt)
        yield from conn.commit_protosubroutine(subrt)
        
        raw_result = conn.shared_memory.get_array(0)
        print(f"Raw measurement: {raw_result[0]}")

        return {"sdk": int(m1), "raw": raw_result[0]}
```

## Use Case: Gate Testing

### Test Specific Gates

```python
import math


class GateTestProgram(Program):
    def __init__(self, gate: str, angle: float = 0):
        self.gate = gate
        self.angle = angle

    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="gate_test",
            csockets=[],
            epr_sockets=[],
            max_qubits=1,
        )

    def run(self, context: ProgramContext):
        conn = context.connection
        q = Qubit(conn)
        
        # Apply specified gate
        if self.gate == "X":
            q.X()
        elif self.gate == "Y":
            q.Y()
        elif self.gate == "Z":
            q.Z()
        elif self.gate == "H":
            q.H()
        elif self.gate == "T":
            q.T()
        elif self.gate == "S":
            q.S()
        elif self.gate == "rot_X":
            q.rot_X(angle=self.angle)
        elif self.gate == "rot_Y":
            q.rot_Y(angle=self.angle)
        elif self.gate == "rot_Z":
            q.rot_Z(angle=self.angle)
        
        m = q.measure()
        yield from conn.flush()
        
        return {"result": int(m)}


def test_gate(gate: str, angle: float = 0, num_times: int = 1000):
    """Test a gate and report statistics."""
    node = StackConfig(
        name="test_node",
        qdevice_typ="generic",
        qdevice_cfg=GenericQDeviceConfig.perfect_config(),
    )
    cfg = StackNetworkConfig(stacks=[node], links=[])
    
    program = GateTestProgram(gate=gate, angle=angle)
    results = run(cfg, {"test_node": program}, num_times=num_times)
    
    measurements = [r["result"] for r in results[0]]
    p0 = sum(1 for m in measurements if m == 0) / num_times
    p1 = 1 - p0
    
    print(f"{gate}({angle:.2f}): P(0)={p0:.3f}, P(1)={p1:.3f}")


# Run tests
test_gate("X")       # Expected: P(0)=0, P(1)=1
test_gate("H")       # Expected: P(0)=0.5, P(1)=0.5
test_gate("rot_X", angle=math.pi/2)  # Expected: P(0)=0.5, P(1)=0.5
```

## Performance Measurement

### Timing Single Node Operations

```python
import time


def benchmark_operations():
    node = StackConfig(
        name="benchmark",
        qdevice_typ="generic",
        qdevice_cfg=GenericQDeviceConfig.perfect_config(),
    )
    cfg = StackNetworkConfig(stacks=[node], links=[])
    
    num_ops = 1000
    
    class BenchmarkProgram(Program):
        @property
        def meta(self):
            return ProgramMeta(
                name="bench",
                csockets=[],
                epr_sockets=[],
                max_qubits=1,
            )
        
        def run(self, context):
            conn = context.connection
            
            for _ in range(100):
                q = Qubit(conn)
                q.H()
                q.X()
                q.Y()
                q.Z()
                q.T()
                q.measure()
            
            yield from conn.flush()
            return {}
    
    start = time.time()
    results = run(cfg, {"benchmark": BenchmarkProgram()}, num_times=10)
    elapsed = time.time() - start
    
    total_gates = 10 * 100 * 6  # iterations * ops per iteration * gates per op
    print(f"Time: {elapsed:.2f}s")
    print(f"Gates/second: {total_gates/elapsed:.0f}")
```

## Debugging Single Node

### Enable Detailed Logging

```python
from squidasm.sim.stack.common import LogManager

LogManager.set_log_level("DEBUG")

# Run simulation - will see detailed execution logs
results = run(cfg, {"node": SingleNodeProgram()}, num_times=1)
```

### Inspect Intermediate State

```python
from netqasm.lang.ir import BreakpointAction


class DebugProgram(Program):
    @property
    def meta(self):
        return ProgramMeta(name="debug", csockets=[], epr_sockets=[], max_qubits=1)
    
    def run(self, context):
        conn = context.connection
        
        q = Qubit(conn)
        q.H()
        
        # Insert breakpoint to dump state
        conn.insert_breakpoint(BreakpointAction.DUMP_LOCAL_STATE)
        
        q.Z()
        
        # Another breakpoint
        conn.insert_breakpoint(BreakpointAction.DUMP_LOCAL_STATE)
        
        m = q.measure()
        yield from conn.flush()
        
        return {"result": int(m)}
```

## Exercises

### Exercise 1: Implement Grover Iteration

Create a single-node program that implements one Grover iteration for a 2-qubit search.

### Exercise 2: State Tomography

Write a program that performs state tomography on a single qubit by measuring in X, Y, and Z bases across multiple runs.

### Exercise 3: Gate Decomposition

Implement a complex gate (e.g., Toffoli) using only single-qubit and CNOT gates on 3 qubits.

## Next Steps

- [Custom Subroutines](09_custom_subroutines.md) - Advanced NetQASM programming
- [Precompilation](10_precompilation.md) - Optimize execution
- [NetQASM Integration](../../architecture/netqasm_integration.md) - Architecture details

## See Also

- [NetQASM Foundations](../../foundations/netqasm.md) - Instruction set overview
- [Tutorial 1: Basics](../1_basics.md) - Basic operations
- [Debugging](../../advanced/debugging.md) - Debugging techniques
