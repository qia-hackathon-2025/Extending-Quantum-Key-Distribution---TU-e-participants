# Tutorial 9: Custom NetQASM Subroutines

This tutorial covers **hand-written NetQASM assembly** for maximum control over quantum operations, based on `squidasm/examples/advanced/link_layer_custom_subrt/`.

## Overview

While the Python SDK is convenient, hand-written NetQASM assembly provides:
- Fine-grained control over instruction sequence
- Complex loop structures and conditionals
- Direct array manipulation
- Maximum performance for well-understood protocols
- Integration with external tools

## When to Use Custom Subroutines

| Scenario | Recommendation |
|----------|----------------|
| Rapid prototyping | Use Python SDK |
| Standard protocols | Use Python SDK |
| Performance-critical | Custom subroutines |
| Complex flow control | Custom subroutines |
| Tight memory control | Custom subroutines |
| External code generation | Custom subroutines |

## NetQASM Assembly Language

### File Structure

```nasm
# NETQASM 1.0       # Version declaration (required)
# APPID 0           # Application ID (required)

# DEFINE name value  # Preprocessor definitions
# DEFINE loop_idx R0
# DEFINE arr_size 10

start:              # Entry point label
    instruction1
    instruction2
    ret_arr @0      # Return arrays to application
```

### Register Types

NetQASM has four register types:

| Register | Name | Purpose |
|----------|------|---------|
| `R0`-`R15` | General | Integer values, loop counters |
| `C0`-`C15` | Classical | Classical computation results |
| `Q0`-`Q15` | Qubit | Virtual qubit IDs |
| `M0`-`M15` | Measurement | Measurement outcomes |

### Basic Instructions

```nasm
# Value operations
set R0 42           # R0 = 42
add R2 R0 R1        # R2 = R0 + R1
sub R2 R0 R1        # R2 = R0 - R1

# Memory operations
array 10 @0         # Allocate array of size 10 at address 0
store R0 @0[5]      # Store R0 at @0[5]
load R0 @0[5]       # Load @0[5] into R0
undef @0[5]         # Undefine @0[5] (for waiting)

# Control flow
jmp LABEL           # Unconditional jump
beq R0 10 LABEL     # Jump if R0 == 10
bne R0 10 LABEL     # Jump if R0 != 10
blt R0 10 LABEL     # Jump if R0 < 10
```

### Qubit Operations

```nasm
# Qubit lifecycle
qalloc Q0           # Allocate physical qubit
init Q0             # Initialize to |0⟩
qfree Q0            # Release qubit

# Single-qubit gates
x Q0                # Pauli X
y Q0                # Pauli Y
z Q0                # Pauli Z
h Q0                # Hadamard
s Q0                # S gate (√Z)
t Q0                # T gate (√S)

# Rotations: angle = n * π / 2^d
rot_x Q0 1 1        # X rotation by π/2 (n=1, d=1)
rot_y Q0 3 1        # Y rotation by 3π/2 (n=3, d=1)
rot_z Q0 1 2        # Z rotation by π/4 (n=1, d=2)

# Two-qubit gates
cnot Q0 Q1          # CNOT with Q0 control
cz Q0 Q1            # CZ gate

# Measurement
meas Q0 M0          # Measure Q0, store in M0
```

### EPR Operations

```nasm
# Create EPR pair (initiator)
create_epr(remote_node_id, epr_socket_id) virt_ids_arr args_arr results_arr

# Receive EPR pair (responder)
recv_epr(remote_node_id, epr_socket_id) virt_ids_arr results_arr

# Wait for EPR results
wait_all @results[start:end]
```

## Example: CHSH Protocol

This example implements a CHSH Bell test with multiple measurement bases.

### Client Code (`client.nqasm`)

```nasm
# NETQASM 1.0
# APPID 0

# Register aliases
# DEFINE pair_index R1
# DEFINE loop_index R6
# DEFINE slice_start R2
# DEFINE slice_end R4

# Configuration
# DEFINE num_repetitions 2
# DEFINE num_reps_times_bases 24
# DEFINE num_bases 12
# DEFINE num_bas_times_ten 120

# Array addresses for fidelity 60
# DEFINE epr_results_60 2
# DEFINE virt_ids_60 3
# DEFINE epr_args_60 4

# Array addresses for fidelity 65
# DEFINE epr_results_65 5
# DEFINE virt_ids_65 6
# DEFINE epr_args_65 7

# Outcome arrays
# DEFINE outcomes_60 0
# DEFINE outcomes_65 1

start:
    // Allocate outcome arrays
    array $num_reps_times_bases @$outcomes_60
    array $num_reps_times_bases @$outcomes_65

    // Allocate EPR arrays for each fidelity setting
    array 20 @$epr_args_60
    array $num_bases @$virt_ids_60
    array $num_bas_times_ten @$epr_results_60

    array 20 @$epr_args_65
    array $num_bases @$virt_ids_65
    array $num_bas_times_ten @$epr_results_65

    // Configure create_epr arguments
    // @[0] = 0 -> Create and Keep type
    // @[1] = num_bases -> number of pairs
    store 0 @$epr_args_60[0]
    store $num_bases @$epr_args_60[1]
    store 0 @$epr_args_65[0]
    store $num_bases @$epr_args_65[1]

    // Initialize virtual IDs to 0 (reuse same qubit)
    set R0 0
LOOP_INIT:
    beq R0 $num_bases LOOP_INIT_END
    store 0 @$virt_ids_60[R0]
    store 0 @$virt_ids_65[R0]
    add R0 R0 1
    jmp LOOP_INIT
LOOP_INIT_END:

    // Main repetition loop
    set $loop_index 0
main_loop_START:
    beq $loop_index $num_repetitions main_loop_END

    // Reset results arrays before each repetition
    set C0 0
reset_START:
    beq C0 $num_bas_times_ten reset_END
    undef @$epr_results_60[C0]
    undef @$epr_results_65[C0]
    add C0 C0 1
    jmp reset_START
reset_END:

    // Issue EPR create request
    create_epr(1,0) $virt_ids_60 $epr_args_60 $epr_results_60

    // Process each pair
    set $pair_index 0
wait_loop_60_START:
    beq $pair_index $num_bases wait_loop_60_END

    // Calculate result slice boundaries
    // slice_start = pair_index * 10
    set $slice_start 0
    set R5 0
CALC_START:
    beq R5 10 CALC_START_END
    add $slice_start $slice_start $pair_index
    add R5 R5 1
    jmp CALC_START
CALC_START_END:
    // slice_end = (pair_index + 1) * 10
    add R3 $pair_index 1
    set $slice_end 0
    set R5 0
CALC_END:
    beq R5 10 CALC_END_END
    add $slice_end $slice_end R3
    add R5 R5 1
    jmp CALC_END
CALC_END_END:

    // Wait for this pair to be generated
    wait_all @$epr_results_60[$slice_start:$slice_end]
    load Q0 @$virt_ids_60[$pair_index]

    // Rotate to measurement basis based on pair index
    beq $pair_index 0 rot_X_60      // +X basis
    beq $pair_index 1 rot_Y_60      // +Y basis
    beq $pair_index 3 rot_X_60      
    beq $pair_index 4 rot_Y_60      
    beq $pair_index 6 rot_minus_X_60  // -X basis
    beq $pair_index 7 rot_minus_Y_60  // -Y basis
    beq $pair_index 8 rot_minus_Z_60  // -Z basis
    beq $pair_index 9 rot_minus_X_60
    beq $pair_index 10 rot_minus_Y_60
    beq $pair_index 11 rot_minus_Z_60
    jmp rot_END_60

rot_X_60:
    rot_y Q0 3 1       // Y(-π/2) rotates Z to X
    jmp rot_END_60
rot_Y_60:
    rot_x Q0 1 1       // X(π/2) rotates Z to Y
    jmp rot_END_60
rot_minus_X_60:
    rot_y Q0 1 1       // Y(π/2) rotates Z to -X
    jmp rot_END_60
rot_minus_Y_60:
    rot_x Q0 3 1       // X(-π/2) rotates Z to -Y
    jmp rot_END_60
rot_minus_Z_60:
    rot_x Q0 1 0       // X(π) rotates Z to -Z
    jmp rot_END_60
rot_END_60:

    // Measure and store
    meas Q0 M0
    qfree Q0

    // Calculate storage index: loop_index * num_bases + pair_index
    set C0 0
    set C1 0
    add C1 C1 $pair_index
calc_index_START:
    beq C0 $loop_index calc_index_END
    add C1 C1 $num_bases
    add C0 C0 1
    jmp calc_index_START
calc_index_END:
    store M0 @$outcomes_60[C1]

    add $pair_index $pair_index 1
    jmp wait_loop_60_START
wait_loop_60_END:

    // Repeat for second fidelity setting (similar code)
    // ... (abbreviated for clarity)

    add $loop_index $loop_index 1
    jmp main_loop_START
main_loop_END:

    // Return outcome arrays to application
    ret_arr @$outcomes_60
    ret_arr @$outcomes_65
```

### Server Code (`server.nqasm`)

The server uses `recv_epr` instead of `create_epr`:

```nasm
# NETQASM 1.0
# APPID 0

# Similar definitions...

start:
    // Allocate arrays...
    
    // Use recv_epr instead of create_epr
    recv_epr(0,0) $virt_ids_60 $epr_results_60

    // Rest similar to client...
    
    ret_arr @$outcomes_60
    ret_arr @$outcomes_65
```

### Python Integration

```python
import os
from typing import Any, Dict, Generator

from netqasm.lang.parsing.text import parse_text_protosubroutine
from pydynaa import EventExpression

from squidasm.run.stack.config import (
    LinkConfig, NVQDeviceConfig, StackConfig, StackNetworkConfig
)
from squidasm.run.stack.run import run
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta


# Load and parse subroutines at import time
client_subrt_path = os.path.join(os.path.dirname(__file__), "client.nqasm")
with open(client_subrt_path) as f:
    CLIENT_SUBRT = parse_text_protosubroutine(f.read())

server_subrt_path = os.path.join(os.path.dirname(__file__), "server.nqasm")
with open(server_subrt_path) as f:
    SERVER_SUBRT = parse_text_protosubroutine(server_subrt_path.read())


class ClientProgram(Program):
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="client_program",
            csockets=["server"],
            epr_sockets=["server"],
            max_qubits=1,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        # Execute the pre-parsed subroutine
        yield from context.connection.commit_protosubroutine(CLIENT_SUBRT)
        
        # Retrieve results from shared memory
        return {
            "fidelity_60": context.connection.shared_memory.get_array(0),
            "fidelity_65": context.connection.shared_memory.get_array(1),
        }


class ServerProgram(Program):
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="server_program",
            csockets=["client"],
            epr_sockets=["client"],
            max_qubits=1,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        yield from context.connection.commit_protosubroutine(SERVER_SUBRT)
        
        return {
            "fidelity_60": context.connection.shared_memory.get_array(0),
            "fidelity_65": context.connection.shared_memory.get_array(1),
        }


if __name__ == "__main__":
    from squidasm.sim.stack.common import LogManager
    LogManager.set_log_level("WARNING")

    client = StackConfig(
        name="client",
        qdevice_typ="nv",
        qdevice_cfg=NVQDeviceConfig.perfect_config(),
    )
    server = StackConfig(
        name="server",
        qdevice_typ="nv",
        qdevice_cfg=NVQDeviceConfig.perfect_config(),
    )
    link = LinkConfig(stack1="client", stack2="server", typ="perfect")

    cfg = StackNetworkConfig(stacks=[client, server], links=[link])

    results = run(
        cfg,
        {"client": ClientProgram(), "server": ServerProgram()},
        num_times=1
    )
    print(results)
```

## Key Concepts

### Array Slicing

EPR results use array slicing for efficient waiting:

```nasm
# Wait for results in slice [start:end)
wait_all @$epr_results[R2:R4]
```

Each EPR pair produces 10 result values, so:
- Pair 0: indices 0-9
- Pair 1: indices 10-19
- Pair n: indices n*10 to (n+1)*10-1

### Multiplication via Loops

NetQASM lacks multiply, so use repeated addition:

```nasm
# Calculate R4 = pair_index * 10
set R4 0
set R5 0
MULT_LOOP:
    beq R5 10 MULT_DONE
    add R4 R4 $pair_index
    add R5 R5 1
    jmp MULT_LOOP
MULT_DONE:
```

### Conditional Branching

Branch to different code paths based on values:

```nasm
    beq $pair_index 0 case_0
    beq $pair_index 1 case_1
    beq $pair_index 2 case_2
    jmp default_case

case_0:
    rot_x Q0 1 1
    jmp end_switch
case_1:
    rot_y Q0 1 1
    jmp end_switch
case_2:
    rot_z Q0 1 1
    jmp end_switch
default_case:
    // No rotation
end_switch:
```

### Result Array Reset

Before reusing arrays in loops, reset them:

```nasm
    set C0 0
reset_START:
    beq C0 $array_size reset_END
    undef @$array[C0]    # Mark as undefined
    add C0 C0 1
    jmp reset_START
reset_END:
```

This is critical for `wait_all` to work correctly in subsequent iterations.

## Rotation Encoding

Rotations use the formula: angle = n × π / 2^d

| Gate | Encoding | Angle |
|------|----------|-------|
| X(π/2) | `rot_x Q0 1 1` | 1×π/2 = π/2 |
| X(-π/2) | `rot_x Q0 3 1` | 3×π/2 = 3π/2 = -π/2 |
| X(π/4) | `rot_x Q0 1 2` | 1×π/4 = π/4 |
| X(π) | `rot_x Q0 1 0` | 1×π = π |

### Basis Rotation Reference

| Basis | Rotation | Code |
|-------|----------|------|
| +X | Y(-π/2) | `rot_y Q0 3 1` |
| +Y | X(π/2) | `rot_x Q0 1 1` |
| +Z | (none) | - |
| -X | Y(π/2) | `rot_y Q0 1 1` |
| -Y | X(-π/2) | `rot_x Q0 3 1` |
| -Z | X(π) | `rot_x Q0 1 0` |

## Advanced: Shared Memory Access

The Python application retrieves results via shared memory:

```python
# Get array at address 0
outcomes_60 = context.connection.shared_memory.get_array(0)

# Get array at address 1
outcomes_65 = context.connection.shared_memory.get_array(1)
```

Array addresses correspond to the `@N` notation in NetQASM:
- `array 10 @0` creates array accessible as `get_array(0)`
- `array 5 @1` creates array accessible as `get_array(1)`

## Comparing SDK vs Custom Subroutines

### SDK Approach

```python
def run(self, context: ProgramContext):
    outcomes = {}
    for fid in [60, 65]:
        outcomes[fid] = context.connection.new_array(24)
    
    with context.connection.loop(2):  # num_repetitions
        for fid in [60, 65]:
            def post_create(conn, q, pair):
                self._rotate_basis(q, basis="+X")
                array_entry = outcomes[fid].get_future_index(pair)
                q.measure(array_entry)
            
            context.epr_sockets["server"].create_keep(
                number=12,  # num_bases
                sequential=True,
                post_routine=post_create,
            )
    
    yield from context.connection.flush()
    return {k: list(v) for k, v in outcomes.items()}
```

### Custom Subroutine Approach

```python
def run(self, context: ProgramContext):
    yield from context.connection.commit_protosubroutine(CLIENT_SUBRT)
    return {
        "fidelity_60": context.connection.shared_memory.get_array(0),
        "fidelity_65": context.connection.shared_memory.get_array(1),
    }
```

Benefits:
- Full control over instruction sequence
- Can optimize for specific hardware
- Reproducible across implementations

## Debugging Custom Subroutines

### Syntax Validation

```python
from netqasm.lang.parsing.text import parse_text_protosubroutine

try:
    subrt = parse_text_protosubroutine(subrt_text)
    print("Parsed successfully")
    print(f"Instructions: {len(subrt.instructions)}")
except Exception as e:
    print(f"Parse error: {e}")
```

### Inspect Parsed Instructions

```python
subrt = parse_text_protosubroutine(subrt_text)
for i, instr in enumerate(subrt.instructions):
    print(f"{i}: {instr}")
```

### Enable Detailed Logging

```python
from squidasm.sim.stack.common import LogManager
LogManager.set_log_level("DEBUG")
```

## Exercises

### Exercise 1: Simple Bell Test

Write a NetQASM subroutine that:
1. Creates one EPR pair
2. Measures both qubits in Z basis
3. Returns both outcomes

### Exercise 2: Add a New Basis

Extend the CHSH example to support diagonal bases (X+Z)/√2.

### Exercise 3: Optimize Loop

Rewrite the multiplication loop using shift operations (if available) or explore alternative algorithms.

## Next Steps

- [Precompilation](10_precompilation.md) - Template-based subroutines
- [NetQASM Foundations](../../foundations/netqasm.md) - Full instruction reference
- [Architecture Overview](../../architecture/overview.md) - Stack integration

## See Also

- [Link Layer](06_link_layer.md) - EPR operations via SDK
- [Single Node](08_single_node.md) - Simpler subroutine examples
- [BQC Implementation](02_bqc_implementation.md) - SDK-based protocol
