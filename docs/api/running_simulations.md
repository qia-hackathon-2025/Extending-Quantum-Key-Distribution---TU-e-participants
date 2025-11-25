# API Reference: Simulation and Utilities

Complete API documentation for running simulations and utility functions.

---

## Running Simulations

The `run()` function is the main entry point for executing SquidASM simulations.

### Function Signature

Located in `squidasm.run.stack.run`:

```python
def run(
    config: Union[NetworkConfig, StackNetworkConfig],
    programs: Dict[str, Program],
    num_times: int = 1,
    linear: bool = False
) -> List[List[Dict[str, Any]]]:
    """
    Run a SquidASM simulation.
    
    Args:
        config: Network configuration (YAML or programmatic)
        programs: Dict mapping node names to Program instances
        num_times: Number of iterations to run
        linear: If True, run programs sequentially; if False, run concurrently
    
    Returns:
        List[List[Dict]]: Results organized as [node][iteration] → return dict
    
    Raises:
        ValueError: If node names don't match configuration
        RuntimeError: If program execution fails
    """
```

### Parameters Explained

#### config: StackNetworkConfig

Network configuration specifying:
- Node names and quantum device parameters
- Quantum and classical links
- Noise models and gate times

```python
# Load from YAML
config = StackNetworkConfig.from_file("config.yaml")

# Or create programmatically
config = StackNetworkConfig(
    stacks=[alice_stack, bob_stack],
    links=[quantum_link],
    clinks=[classical_link]
)
```

#### programs: Dict[str, Program]

Maps node names to program instances:

```python
programs = {
    "Alice": AliceProgram(param1=10),
    "Bob": BobProgram(param2=20)
}
```

**Important**: Node names must match configuration exactly.

#### num_times: int (default=1)

Number of iterations to run:

```python
# Single iteration
results = run(config=cfg, programs=programs, num_times=1)

# Multiple iterations (for averaging, statistical analysis)
results = run(config=cfg, programs=programs, num_times=100)
```

Each iteration:
- Resets quantum state to |0⟩
- Runs all programs from start
- Collects return values independently

#### linear: bool (default=False)

Execution mode:

```python
# Concurrent execution (default, faster)
results = run(config=cfg, programs=programs, linear=False)

# Sequential execution (useful for debugging)
results = run(config=cfg, programs=programs, linear=True)
```

- **linear=False**: Programs run concurrently (like real networks)
  - Better performance
  - Easier to debug timing issues
- **linear=True**: Programs run sequentially
  - Slower
  - Simpler execution model
  - For testing single-node behavior

### Return Value: Results Structure

```python
results: List[List[Dict[str, Any]]]
```

Nested structure:

```
results[node_index][iteration_index][return_key] = value

# Example:
# results[0] = Alice's results (list of dicts)
# results[0][0] = Alice's result from iteration 0
# results[0][0]["measurement"] = Alice's measurement value from iteration 0

# results[1] = Bob's results (list of dicts)
# results[1][0] = Bob's result from iteration 0
```

### Accessing Results

```python
results = run(config=cfg, programs=programs, num_times=100)

# Results are organized by node then iteration
alice_results = results[0]  # All Alice results
bob_results = results[1]    # All Bob results

# Iterate iterations
for iteration in range(100):
    alice_data = alice_results[iteration]
    bob_data = bob_results[iteration]
    
    # Access return dictionary keys
    alice_measurement = alice_data["measurement"]
    bob_measurement = bob_data["measurement"]
    
    print(f"Iteration {iteration}: Alice={alice_measurement}, Bob={bob_measurement}")
```

### Complete Example

```python
from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run

# Configuration
cfg = StackNetworkConfig.from_file("config.yaml")

# Programs
alice = AliceProgram()
bob = BobProgram()

# Run simulation
programs = {"Alice": alice, "Bob": bob}
results = run(config=cfg, programs=programs, num_times=100)

# Analyze results
alice_measurements = [r["measurement"] for r in results[0]]
bob_measurements = [r["measurement"] for r in results[1]]

# Calculate correlation
correlation = sum(
    a == b for a, b in zip(alice_measurements, bob_measurements)
) / len(alice_measurements)

print(f"Correlation: {correlation:.2%}")
```

---

## Logging System

The `LogManager` class provides structured logging with simulation timestamps.

### LogManager API

Located in `squidasm.sim.stack.common`:

```python
from squidasm.sim.stack.common import LogManager

class LogManager:
    """Manage logging for SquidASM simulations."""
    
    @staticmethod
    def set_log_level(level: str) -> None:
        """Set global log level.
        
        Args:
            level: One of "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
        """
    
    @staticmethod
    def get_stack_logger(name: str):
        """Get a logger instance.
        
        Args:
            name: Logger name (appears in log messages)
        
        Returns:
            Logger instance with methods: debug(), info(), warning(), error(), critical()
        """
    
    @staticmethod
    def log_to_file(filepath: str) -> None:
        """Redirect logs to file.
        
        Args:
            filepath: Path to log file
        """
```

### Setting Log Levels

```python
from squidasm.sim.stack.common import LogManager

# Global log level
LogManager.set_log_level("DEBUG")    # Most verbose
LogManager.set_log_level("INFO")     # Default
LogManager.set_log_level("WARNING")  # Less verbose
LogManager.set_log_level("ERROR")    # Only errors
LogManager.set_log_level("CRITICAL") # Only critical
```

**Log Levels (Severity)**:
1. **DEBUG**: Detailed information for debugging
2. **INFO**: General informational messages
3. **WARNING**: Warning messages (default)
4. **ERROR**: Error conditions
5. **CRITICAL**: Critical failures

Lower levels filter out messages. Setting to "INFO" shows INFO, WARNING, ERROR, CRITICAL but not DEBUG.

### Creating Loggers

```python
from squidasm.sim.stack.common import LogManager

# Get logger for your program
logger = LogManager.get_stack_logger("AliceProgram")

def run(self, context: ProgramContext):
    logger.debug("Starting program execution")
    logger.info("About to measure qubit")
    logger.warning("Link fidelity is low (0.8)")
    logger.error("Failed to create EPR pair")
    logger.critical("Quantum device is offline")
```

### Log Message Format

```
LEVEL:SIMTIME ns:LOGGER_NAME:MESSAGE

Example:
INFO:44000.0 ns:Stack.AliceProgram:Measured qubits: 0 1
DEBUG:44050.0 ns:Stack.Handler:Executing subroutine
WARNING:44100.0 ns:Stack.Netstack:EPR pair fidelity below threshold
```

**Components**:
- **LEVEL**: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **SIMTIME**: Simulation time in nanoseconds
- **LOGGER_NAME**: Logger identifier
- **MESSAGE**: Log message

### File Logging

```python
from squidasm.sim.stack.common import LogManager

# Redirect logs to file
LogManager.log_to_file("simulation.log")

# Set level
LogManager.set_log_level("DEBUG")

# Run simulation
results = run(config=cfg, programs=programs, num_times=1)

# Log file contains all output
```

### Example: Logging in Programs

```python
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.program import Program, ProgramMeta, ProgramContext

class MyProgram(Program):
    def __init__(self):
        self.logger = LogManager.get_stack_logger("MyProgram")
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(name="MyNode", max_qubits=5)
    
    def run(self, context: ProgramContext):
        self.logger.info("Program started")
        
        connection = context.connection
        qubit = Qubit(connection)
        
        self.logger.debug("Applying Hadamard gate")
        qubit.H()
        
        result = qubit.measure()
        yield from connection.flush()
        
        self.logger.info(f"Measurement result: {int(result)}")
        
        return {"result": int(result)}
```

---

## Classical Socket API

The `ClassicalSocket` class handles message passing between nodes.

### Socket Methods

Located in `squidasm.sim.stack.csocket`:

```python
class ClassicalSocket:
    """Send and receive classical messages."""
    
    def send(self, msg: str) -> None:
        """Send a string message.
        
        Args:
            msg: Message string to send
        """
    
    def send_int(self, value: int) -> None:
        """Send an integer.
        
        Args:
            value: Integer value to send
        """
    
    def recv(self):
        """Receive a string message.
        
        Yields:
            Message string
        
        Usage:
            message = yield from socket.recv()
        """
    
    def recv_int(self):
        """Receive an integer.
        
        Yields:
            Integer value
        
        Usage:
            value = yield from socket.recv_int()
        """
```

### Usage Examples

```python
def run(self, context: ProgramContext):
    socket = context.csockets["Bob"]
    
    # Send messages
    socket.send("Hello Bob")
    socket.send_int(42)
    
    # Receive messages (blocking)
    message = yield from socket.recv()      # Waits for message
    value = yield from socket.recv_int()    # Waits for integer
    
    print(f"Received: {message}, {value}")
```

### Key Points

- **send()**: Non-blocking, message is queued
- **recv()**: Blocking, requires `yield from`, waits for message
- **Type specific**: Use `send_int()` with `recv_int()`, etc.
- **Order preserved**: Messages sent first are received first

---

## Utility Functions

Located in `squidasm.util.util`:

### Network Creation Functions

```python
from squidasm.util.util import (
    create_two_node_network,
    create_complete_graph_network
)

# Simple two-node network
config = create_two_node_network(
    node_names=["Alice", "Bob"],
    qdevice_typ="generic",
    link_typ="perfect"
)

# Multi-node complete graph
config = create_complete_graph_network(
    node_names=["Alice", "Bob", "Charlie"],
    qdevice_typ="generic",
    link_typ="depolarise",
    qdevice_cfg=GenericQDeviceConfig(num_qubits=10)
)
```

### Quantum State Inspection

```python
from squidasm.util.util import get_qubit_state, get_reference_state
import numpy as np

# Get qubit state (simulation only)
state = get_qubit_state(qubit, node_name="Alice", full_state=False)
# Returns: density matrix (vector form)

# Full state matrix
full_state_matrix = get_qubit_state(qubit, "Alice", full_state=True)

# Reference state on Bloch sphere
phi = np.pi / 4
theta = np.pi / 6
ref_state = get_reference_state(phi, theta)
```

---

## Pre-built Quantum Routines

Located in `squidasm.util.routines` and `squidasm.util.qkd_routine`:

### Teleportation

```python
from squidasm.util.routines import teleport_send, teleport_recv

# Sender
def alice_run(self, context):
    qubit = prepare_qubit(context)
    yield from teleport_send(qubit, context, "Bob")
    return {}

# Receiver
def bob_run(self, context):
    teleported_qubit = yield from teleport_recv(context, "Alice")
    result = teleported_qubit.measure()
    yield from context.connection.flush()
    return {"measurement": int(result)}
```

### Distributed Gates

```python
from squidasm.util.routines import (
    distributed_CNOT_control,
    distributed_CNOT_target,
    distributed_CPhase_control,
    distributed_CPhase_target
)

# Control qubit on this node
def control_run(self, context):
    qubit = create_epr(context, "Target")
    yield from distributed_CNOT_control(context, "Target", qubit)
    # Target qubit is now CNOT applied

# Target qubit on this node
def target_run(self, context):
    qubit = create_epr(context, "Control")
    yield from distributed_CNOT_target(context, "Control", qubit)
    # Control qubit applied CNOT to this qubit
```

### GHZ State Creation

```python
from squidasm.util.routines import create_ghz

# Multi-node GHZ state
def start_node_run(self, context):
    # Only has up_epr_socket
    qubit, results = yield from create_ghz(
        context.connection,
        context.epr_sockets[("Middle", 1)],
        None,  # No down socket
        do_corrections=True
    )

def middle_node_run(self, context):
    # Has both sockets
    qubit, results = yield from create_ghz(
        context.connection,
        context.epr_sockets[("Start", 1)],
        context.epr_sockets[("End", 1)],
        do_corrections=True
    )

def end_node_run(self, context):
    # Only has down_epr_socket
    qubit, results = yield from create_ghz(
        context.connection,
        None,  # No up socket
        context.epr_sockets[("Middle", 1)],
        do_corrections=True
    )
```

### Measurement Utilities

```python
from squidasm.util.routines import measXY, remote_state_preparation

# Measure in XY plane
result = measXY(qubit, angle=np.pi/4)
yield from connection.flush()

# Remote state preparation
prepared_qubit = yield from remote_state_preparation(epr_socket, theta=np.pi/4)

# Receive remote preparation
received_qubit = yield from recv_remote_state_preparation(epr_socket)
```

### QKD Routines

```python
from squidasm.util.qkd_routine import (
    BB84_sender,
    BB84_receiver
)

# QKD simulation
# Details in dedicated QKD documentation
```

---

## EPR Socket API

The `EPRSocket` class (from NetQASM SDK) handles entanglement generation.

### Methods

```python
class EPRSocket:
    """Generate and receive entangled pairs."""
    
    def create_keep(self, number: int = 1) -> List[Qubit]:
        """Create and keep EPR pairs.
        
        Args:
            number: Number of pairs to create (default: 1)
        
        Returns:
            List of qubits (local half of pairs)
        """
    
    def create_measure(self, number: int = 1):
        """Create and immediately measure EPR pairs.
        
        Args:
            number: Number of pairs to create
        
        Yields:
            Measurement results
        """
    
    def recv_keep(self, number: int = 1) -> List[Qubit]:
        """Receive and keep EPR pairs.
        
        Args:
            number: Number of pairs to receive
        
        Returns:
            List of qubits (local half of pairs)
        """
    
    def recv_measure(self, number: int = 1):
        """Receive and immediately measure EPR pairs.
        
        Args:
            number: Number of pairs to receive
        
        Yields:
            Measurement results
        """
```

### Usage

```python
def run(self, context: ProgramContext):
    epr_socket = context.epr_sockets[("Bob", 1)]
    connection = context.connection
    
    # Create 5 EPR pairs
    qubits = epr_socket.create_keep(number=5)
    
    # Apply operations
    for qubit in qubits:
        qubit.H()
    
    # Measure
    results = [q.measure() for q in qubits]
    
    # Execute
    yield from connection.flush()
    
    # Access results
    measurements = [int(r) for r in results]
    return {"measurements": measurements}
```

---

## Qubit and Quantum Operations

The `Qubit` class (from NetQASM SDK) represents quantum bits.

### Qubit Creation

```python
from netqasm.sdk.qubit import Qubit

def run(self, context: ProgramContext):
    connection = context.connection
    
    # Create local qubit (initialized to |0⟩)
    qubit = Qubit(connection)
```

### Single-Qubit Gates

```python
qubit.X()           # Pauli X
qubit.Y()           # Pauli Y
qubit.Z()           # Pauli Z
qubit.H()           # Hadamard
qubit.T()           # T gate
qubit.S()           # S gate
qubit.K()           # K gate

# Parametric rotations (angle = n*π/2^d)
qubit.rot_X(n=2, d=2)  # Rotate π/2 around X
qubit.rot_Y(n=1, d=1)  # Rotate π/2 around Y
qubit.rot_Z(n=4, d=2)  # Rotate π around Z
```

### Two-Qubit Gates

```python
qubit1.cnot(qubit2)    # Control-NOT (q1 controls q2)
qubit1.cphase(qubit2)  # Control-Phase (q1 controls q2)
```

### Measurement

```python
result = qubit.measure()      # Returns Future
yield from connection.flush()  # Execute and resolve
print(int(result))             # Now is integer 0 or 1
```

---

## Next Steps

- [Program Interface](./program_interface.md) - Writing programs
- [Configuration](./configuration.md) - Network setup
- [Foundations](../foundations/index.md) - Conceptual guides
