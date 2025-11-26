# squidasm.sim Package

The `squidasm.sim` package provides the high-level simulation interface including the `Program` base class, context objects, and stack components.

## Overview

```
squidasm.sim/
├── stack/
│   ├── program.py     # Program, ProgramMeta, ProgramContext
│   ├── stack.py       # Stack component coordination
│   ├── host.py        # Host-side application logic
│   ├── qnos.py        # Quantum Node OS wrapper
│   ├── common.py      # Shared utilities, LogManager
│   └── globals.py     # Global simulation data
└── csocket.py         # Classical socket implementation
```

## Program Interface

### Program Base Class

The `Program` class is the abstract base that all SquidASM applications must inherit from.

```python
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from typing import Generator, Dict, Any

class Program:
    """Abstract base class for quantum network applications.
    
    Users must implement:
    - meta: Property returning ProgramMeta
    - run: Method containing application logic
    """
    
    @property
    def meta(self) -> ProgramMeta:
        """Return program metadata.
        
        IMPORTANT: This is a @property, not a @staticmethod.
        """
        raise NotImplementedError
    
    def run(self, context: ProgramContext) -> Generator[None, None, Dict[str, Any]]:
        """Execute the program logic.
        
        Args:
            context: Provides access to sockets and connection
            
        Returns:
            Dictionary of results to be collected after simulation
        """
        raise NotImplementedError
```

### Implementing a Program

```python
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from netqasm.sdk.qubit import Qubit

class MyProgram(Program):
    """Example quantum network application."""
    
    PEER_NAME = "Bob"
    
    def __init__(self, num_rounds: int = 1):
        """Initialize with parameters.
        
        Args:
            num_rounds: Number of EPR rounds to perform
        """
        self.num_rounds = num_rounds
    
    @property
    def meta(self) -> ProgramMeta:
        """Declare program requirements."""
        return ProgramMeta(
            name="my_program",
            csockets=[self.PEER_NAME],
            epr_sockets=[self.PEER_NAME],
            max_qubits=2
        )
    
    def run(self, context: ProgramContext):
        """Execute the quantum application."""
        connection = context.connection
        csocket = context.csockets[self.PEER_NAME]
        epr_socket = context.epr_sockets[self.PEER_NAME]
        
        results = []
        for _ in range(self.num_rounds):
            # Create EPR pair
            q = epr_socket.create_keep()[0]
            q.H()
            m = q.measure()
            connection.flush()
            results.append(int(m))
        
        return {"measurements": results}
```

## ProgramMeta

The `ProgramMeta` class declares what resources a program needs.

```python
from squidasm.sim.stack.program import ProgramMeta

class ProgramMeta:
    """Metadata describing program requirements.
    
    Attributes:
        name (str): Program identifier
        csockets (List[str]): Peer names for classical sockets
        epr_sockets (List[str]): Peer names for EPR sockets
        max_qubits (int): Maximum qubits used simultaneously
    """
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | str | Yes | Unique program identifier |
| `csockets` | List[str] | No | Peer names for classical communication |
| `epr_sockets` | List[str] | No | Peer names for entanglement |
| `max_qubits` | int | No | Maximum concurrent qubits |

### Examples

```python
# Minimal metadata
ProgramMeta(name="simple")

# With classical socket only
ProgramMeta(
    name="classical_only",
    csockets=["Bob"]
)

# Full specification
ProgramMeta(
    name="full_program",
    csockets=["Bob", "Charlie"],
    epr_sockets=["Bob"],
    max_qubits=3
)
```

### Why max_qubits Matters

```python
# The max_qubits field affects resource allocation:
# 1. Memory allocation in the simulated quantum device
# 2. Error checking for qubit availability
# 3. Performance optimization

# If you use more qubits than declared, you may get:
# RuntimeError: No qubit available in quantum device

# Best practice: Set to actual maximum concurrent usage
@property
def meta(self) -> ProgramMeta:
    return ProgramMeta(
        name="bell_state",
        epr_sockets=["Bob"],
        max_qubits=2  # We use 1 EPR qubit + 1 local qubit
    )
```

## ProgramContext

The `ProgramContext` provides access to network resources during program execution.

```python
from squidasm.sim.stack.program import ProgramContext

class ProgramContext:
    """Runtime context providing access to network resources.
    
    Attributes:
        connection: NetQASM connection for quantum operations
        csockets: Dictionary of classical sockets (peer_name -> socket)
        epr_sockets: Dictionary of EPR sockets (peer_name -> socket)
        app_config: Application configuration from YAML
    """
```

### Accessing Resources

```python
def run(self, context: ProgramContext):
    # NetQASM connection
    connection = context.connection
    
    # Classical socket to peer
    csocket = context.csockets["Bob"]  # Key is peer name (string)
    
    # EPR socket to peer
    epr_socket = context.epr_sockets["Bob"]  # Key is peer name (string)
    
    # Application configuration (from YAML)
    role = context.app_config.get("role", "default")
    threshold = context.app_config.get("threshold", 0.9)
```

### Socket Access Pattern

**Important**: Sockets are accessed by peer name as a string, not a tuple.

```python
# Correct
csocket = context.csockets["Bob"]
epr_socket = context.epr_sockets["Bob"]

# INCORRECT - Old/wrong pattern
# csocket = context.csockets[("Bob", 0)]  # Wrong!
# epr_socket = context.epr_sockets[("Bob", 0)]  # Wrong!
```

## Classical Sockets

Classical sockets enable message passing between nodes.

### Sending Messages

```python
def run(self, context: ProgramContext):
    csocket = context.csockets["Bob"]
    
    # Send string message
    csocket.send("Hello, Bob!")
    
    # Send numeric data (converted to string)
    csocket.send(str(42))
    
    # Send structured data
    import json
    data = {"key": "value", "numbers": [1, 2, 3]}
    csocket.send(json.dumps(data))
```

### Receiving Messages

```python
def run(self, context: ProgramContext):
    csocket = context.csockets["Alice"]
    
    # Receive message (use yield from!)
    message = yield from csocket.recv()
    
    # Parse numeric data
    number = int(yield from csocket.recv())
    
    # Parse structured data
    import json
    data = json.loads(yield from csocket.recv())
```

**Important**: Always use `yield from` when receiving messages, as this is an asynchronous operation.

## EPR Sockets

EPR sockets manage entanglement generation between nodes.

### Creating EPR Pairs

```python
def run(self, context: ProgramContext):
    epr_socket = context.epr_sockets["Bob"]
    connection = context.connection
    
    # Create one EPR pair (returns list)
    qubits = epr_socket.create_keep()
    q = qubits[0]  # Get the single qubit
    
    # Create multiple EPR pairs
    qubits = epr_socket.create_keep(number=5)
    for q in qubits:
        # Process each qubit...
        pass
```

### Receiving EPR Pairs

```python
def run(self, context: ProgramContext):
    epr_socket = context.epr_sockets["Alice"]
    connection = context.connection
    
    # Receive one EPR pair
    qubits = epr_socket.recv_keep()
    q = qubits[0]
    
    # Receive multiple EPR pairs
    qubits = epr_socket.recv_keep(number=5)
```

### EPR Operations

| Method | Description |
|--------|-------------|
| `create_keep()` | Create EPR pair, keep local qubit |
| `recv_keep()` | Receive EPR pair, keep local qubit |
| `create()` | Create and immediately measure |
| `recv()` | Receive and immediately measure |

## Stack Components

### Stack

The `Stack` class coordinates the components of a network node.

```python
from squidasm.sim.stack.stack import Stack

class Stack:
    """Coordinates network node components.
    
    Components:
    - Host: Runs application programs
    - QNodeOS: Quantum operating system
    - QDevice: Quantum processor
    - Connections: Links to other nodes
    """
```

### Host

The `Host` class runs application-level code.

```python
from squidasm.sim.stack.host import Host

class Host:
    """Application host for quantum network node.
    
    Responsibilities:
    - Execute Program.run() method
    - Manage socket connections
    - Coordinate with QNodeOS
    """
```

### QNos (Quantum Node OS Wrapper)

```python
from squidasm.sim.stack.qnos import QNos

class QNos:
    """Wrapper around QNodeOS for the simulation.
    
    Provides higher-level interface to:
    - Application registration
    - Memory management
    - Subroutine execution
    """
```

## LogManager

The `LogManager` class provides logging utilities.

```python
from squidasm.sim.stack.common import LogManager

class LogManager:
    """Centralized logging management for SquidASM.
    
    Methods:
        set_log_level(level): Set global log level
        get_stack_logger(name): Get logger for a component
        log_to_file(filename): Redirect logs to file
    """
```

### Usage

```python
from squidasm.sim.stack.common import LogManager

# Set global log level
LogManager.set_log_level("DEBUG")  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Log to file
LogManager.log_to_file("simulation.log")

# Get logger in program
class MyProgram(Program):
    def run(self, context: ProgramContext):
        logger = LogManager.get_stack_logger("MyProgram")
        
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
```

### Log Format

```
LEVEL:TIME:LOGGER_NAME:MESSAGE
```

Example:
```
INFO:44000.0 ns:Stack.MyProgram:Processing iteration 5
DEBUG:44000.0 ns:Stack.NetSquidExecutor:Executing H gate on Q0
```

## GlobalSimData

Access global simulation state.

```python
from squidasm.sim.stack.globals import GlobalSimData

class GlobalSimData:
    """Global simulation data container.
    
    Provides access to:
    - Network topology
    - Node-specific data
    - Simulation parameters
    """
```

### Usage

```python
def run(self, context: ProgramContext):
    # Access global data (advanced usage)
    sim_data = GlobalSimData.get_instance()
    
    # Get network information
    network = sim_data.get_network()
    
    # Get node-specific data
    node_data = sim_data.get_node_data("Alice")
```

## Common Patterns

### Pattern 1: Simple Measurement

```python
class SimpleMeasure(Program):
    PEER_NAME = "Bob"
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="simple_measure",
            epr_sockets=[self.PEER_NAME],
            max_qubits=1
        )
    
    def run(self, context: ProgramContext):
        epr_socket = context.epr_sockets[self.PEER_NAME]
        connection = context.connection
        
        q = epr_socket.create_keep()[0]
        result = q.measure()
        connection.flush()
        
        return {"result": int(result)}
```

### Pattern 2: Teleportation

```python
class TeleportSender(Program):
    PEER_NAME = "Bob"
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="teleport_sender",
            csockets=[self.PEER_NAME],
            epr_sockets=[self.PEER_NAME],
            max_qubits=2
        )
    
    def run(self, context: ProgramContext):
        csocket = context.csockets[self.PEER_NAME]
        epr_socket = context.epr_sockets[self.PEER_NAME]
        connection = context.connection
        
        # Create state to teleport
        q_data = Qubit(connection)
        q_data.H()  # |+⟩ state
        
        # Get EPR qubit
        q_epr = epr_socket.create_keep()[0]
        
        # Bell measurement
        q_data.cnot(q_epr)
        q_data.H()
        m1 = q_data.measure()
        m2 = q_epr.measure()
        connection.flush()
        
        # Send corrections
        csocket.send(f"{int(m1)},{int(m2)}")
        
        return {"m1": int(m1), "m2": int(m2)}
```

### Pattern 3: Configurable Program

```python
class ConfigurableProgram(Program):
    def __init__(self, peer_name: str = "Bob", num_rounds: int = 1):
        self.peer_name = peer_name
        self.num_rounds = num_rounds
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="configurable",
            csockets=[self.peer_name],
            epr_sockets=[self.peer_name],
            max_qubits=1
        )
    
    def run(self, context: ProgramContext):
        # Use configuration from constructor
        # and/or from app_config
        config_rounds = context.app_config.get("num_rounds", self.num_rounds)
        
        results = []
        for _ in range(config_rounds):
            # ... perform operations ...
            pass
        
        return {"results": results}
```

## Error Handling

### Common Errors

```python
# KeyError: Socket not declared in meta
def run(self, context: ProgramContext):
    # This fails if "Charlie" not in csockets
    csocket = context.csockets["Charlie"]

# Solution: Declare all sockets in meta
@property
def meta(self) -> ProgramMeta:
    return ProgramMeta(
        name="program",
        csockets=["Bob", "Charlie"]  # Declare all peers
    )
```

```python
# RuntimeError: No qubit available
def run(self, context: ProgramContext):
    # Using more qubits than max_qubits
    qubits = [Qubit(connection) for _ in range(10)]

# Solution: Increase max_qubits
@property
def meta(self) -> ProgramMeta:
    return ProgramMeta(
        name="program",
        max_qubits=10
    )
```

```python
# AttributeError: Future has no value
def run(self, context: ProgramContext):
    q = Qubit(connection)
    result = q.measure()
    print(result)  # Error! result is Future, not value
    
# Solution: Flush before using result
def run(self, context: ProgramContext):
    q = Qubit(connection)
    result = q.measure()
    connection.flush()  # Execute operations
    print(int(result))  # Now it works
```

## See Also

- [squidasm.run Package](run_package.md) - Execution infrastructure
- [squidasm.nqasm Package](nqasm_package.md) - Low-level executor
- [Tutorial 1: Basics](../tutorials/1_basics.md) - Getting started
- [Tutorial 3: Simulation Control](../tutorials/3_simulation_control.md) - Advanced usage
