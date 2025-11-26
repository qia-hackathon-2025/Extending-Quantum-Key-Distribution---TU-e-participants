# Tutorial 3: Simulation Control

In this section we explain the `run_simulation.py` file and the interface that programs in `application.py` must adhere to. We also cover ways to get output results from the program, application configuration, and logging.

## Basic run_simulation.py

The minimal `run_simulation.py` file contains:

```python
from application import AliceProgram, BobProgram

from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run

# Load network configuration from file
cfg = StackNetworkConfig.from_file("config.yaml")

# Create instances of programs to run
alice_program = AliceProgram()
bob_program = BobProgram()

# Run the simulation
# Programs argument maps network node labels to programs
run(config=cfg, programs={"Alice": alice_program, "Bob": bob_program}, num_times=1)
```

### Components

1. **Import programs** - Import the `AliceProgram` and `BobProgram` classes
2. **Load configuration** - Load the network configuration from YAML into a variable
3. **Create instances** - Create instances of the programs
4. **Map programs to nodes** - Dictionary mapping node names to program instances
5. **Run simulation** - Pass configuration and program mapping to `run()`

### Important Note: Name Consistency

Node names must match across all files:

- Node names in `config.yaml` (under `stacks`)
- Node names in program socket declarations (`self.PEER_NAME = "Bob"`)
- Node names in the `programs` dictionary in `run_simulation.py`

## Program Interface

Programs must subclass `Program` and implement two requirements:

1. A `meta` **property** that returns a `ProgramMeta` object
2. A `run()` method that accepts a `ProgramContext` object

### The Program Base Class

```python
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from typing import Generator, Dict, Any

class MyProgram(Program):
    """Example quantum network application."""
    
    @property
    def meta(self) -> ProgramMeta:
        """Declare program requirements (sockets, qubits, etc.)."""
        return ProgramMeta(
            name="my_program",
            csockets=["Bob"],          # Classical sockets needed
            epr_sockets=["Bob"],       # EPR sockets needed
            max_qubits=2               # Maximum qubits used
        )
    
    def run(self, context: ProgramContext) -> Generator[None, None, Dict[str, Any]]:
        """Execute the program."""
        # Implementation here
        return {}
```

**Important**: The `meta` method is a `@property`, not a `@staticmethod`. This allows accessing instance attributes like `self.PEER_NAME`.

### ProgramMeta Fields

The `ProgramMeta` object declares program requirements:

```python
@property
def meta(self) -> ProgramMeta:
    return ProgramMeta(
        name="alice",           # Program identifier
        csockets=["Bob"],       # List of peer names for classical sockets
        epr_sockets=["Bob"],    # List of peer names for EPR sockets
        max_qubits=2            # Maximum qubits this program uses
    )
```

**Important**: Always specify `max_qubits` for proper resource allocation in the simulator.

### ProgramContext Resources

The `ProgramContext` provides access to network resources:

```python
def run(self, context: ProgramContext):
    # NetQASM connection for quantum operations
    connection = context.connection
    
    # Classical socket - accessed by peer name
    csocket = context.csockets["Bob"]
    
    # EPR socket - accessed by peer name (not tuple!)
    epr_socket = context.epr_sockets["Bob"]
    
    # Application configuration (from config or run parameters)
    app_config = context.app_config
```

### Socket Access Pattern

Sockets are accessed using the peer name as a string key:

```python
# Correct way
csocket = context.csockets[self.PEER_NAME]
epr_socket = context.epr_sockets[self.PEER_NAME]

# NOT like this (incorrect tuple access)
# epr_socket = context.epr_sockets[("Bob", 0)]  # Wrong!
```

### Complete Example Program

```python
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from netqasm.sdk.qubit import Qubit

class AliceProgram(Program):
    PEER_NAME = "Bob"
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="alice",
            csockets=[self.PEER_NAME],
            epr_sockets=[self.PEER_NAME],
            max_qubits=2
        )
    
    def run(self, context: ProgramContext):
        csocket = context.csockets[self.PEER_NAME]
        epr_socket = context.epr_sockets[self.PEER_NAME]
        connection = context.connection
        
        # Send classical message
        csocket.send("Hello")
        
        # Create and measure EPR pair
        q = epr_socket.create_keep()[0]
        q.H()
        result = q.measure()
        connection.flush()
        
        return {"result": int(result)}
```

## Application Configuration

You can pass configuration data to your programs at runtime using `app_config`:

### Defining Application Configuration

In your YAML configuration file, add an `app` section to each stack:

```yaml
stacks:
  - name: Alice
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 2
    app:
      role: "sender"
      num_rounds: 10
      
  - name: Bob
    qdevice_typ: generic
    qdevice_cfg:
      num_qubits: 2
    app:
      role: "receiver"
      num_rounds: 10
```

### Accessing Application Configuration

In your program, access the configuration via `context.app_config`:

```python
def run(self, context: ProgramContext):
    # Access application configuration
    app_config = context.app_config
    
    role = app_config.get("role", "default")
    num_rounds = app_config.get("num_rounds", 1)
    
    if role == "sender":
        # Sender logic
        pass
    else:
        # Receiver logic
        pass
```

### Benefits of app_config

- **Separation of concerns**: Keep configuration separate from code
- **Reusable programs**: Same program class can behave differently based on config
- **Parameter sweeping**: Easy to vary parameters across runs

## Getting Output from Programs

### Return Dictionary

Programs return results via a dictionary at the end of the `run()` method:

```python
def run(self, context: ProgramContext):
    # ... program logic ...
    
    result = q.measure()
    connection.flush()
    
    # Return results dictionary
    return {
        "measurement": int(result),
        "timestamp": context.connection.get_simulation_time()
    }
```

### Accessing Results in run_simulation.py

```python
from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run

cfg = StackNetworkConfig.from_file("config.yaml")

alice_program = AliceProgram()
bob_program = BobProgram()

# Run simulation multiple times
results = run(
    config=cfg,
    programs={"Alice": alice_program, "Bob": bob_program},
    num_times=10
)

# Results structure: List[List[Dict]]
# results[node_index][iteration_index] = returned dictionary
alice_results, bob_results = results

# Process results
for i, (alice_r, bob_r) in enumerate(zip(alice_results, bob_results)):
    print(f"Iteration {i}: Alice={alice_r['measurement']}, Bob={bob_r['measurement']}")
```

### Result Structure

The return of `run()` is `List[List[Dict]]`:

- **Outer list**: One entry per node (Alice, Bob, etc.) in order
- **Inner list**: One entry per iteration
- **Dictionary**: The returned dictionary from each program

### Important: Convert Futures

Always convert `Future` objects to native Python types before returning:

```python
# Good: Convert futures to int
return {"measurements": [int(m) for m in measurements]}

# Avoid: May cause issues
return {"measurements": measurements}  # Contains Future objects
```

## Global Simulation Data

For sharing data between programs or accessing simulation state, use `GlobalSimData`:

```python
from squidasm.sim.stack.globals import GlobalSimData

class MyProgram(Program):
    def run(self, context: ProgramContext):
        # Access global simulation data
        sim_data = GlobalSimData.get_instance()
        
        # Access the simulation network
        network = sim_data.get_network()
        
        # Access node-specific data
        node_data = sim_data.get_node_data("Alice")
```

## Protocol Hooks

SquidASM provides hooks for customizing protocol behavior during simulation.

### Pre/Post Hooks

You can define functions that run before or after specific events:

```python
from squidasm.run.stack.run import run

def pre_simulation_hook():
    """Called before each simulation iteration."""
    print("Starting new iteration")

def post_simulation_hook():
    """Called after each simulation iteration."""
    print("Iteration complete")

results = run(
    config=cfg,
    programs=programs,
    num_times=10,
    # Hooks can be passed to customize behavior
)
```

## Logging

### Setting Up Logging

```python
from squidasm.sim.stack.common import LogManager

# Set the log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LogManager.set_log_level("INFO")

# Optional: Log to file
LogManager.log_to_file("simulation.log")
```

### Using Logger in Programs

```python
from squidasm.sim.stack.common import LogManager

class AliceProgram(Program):
    def run(self, context: ProgramContext):
        logger = LogManager.get_stack_logger("AliceProgram")
        
        logger.debug("Starting program")
        logger.info(f"Processing {self.num_rounds} rounds")
        logger.warning("EPR quality below threshold")
        logger.error("Failed to create EPR pair")
        logger.critical("Fatal error occurred")
```

### Log Levels

From highest to lowest severity:

1. **CRITICAL** - Fatal errors
2. **ERROR** - Non-fatal errors
3. **WARNING** - Potential issues
4. **INFO** - General information (default)
5. **DEBUG** - Detailed debugging

### Log Format

```
LEVEL:TIME:LOGGER_NAME:MESSAGE
```

Example:
```
INFO:44000.0 ns:Stack.AliceProgram:Starting EPR generation
WARNING:44000.0 ns:Stack.Netstack(Bob_netstack):waiting for result for pair 1
DEBUG:44000.0 ns:Stack.GenericProcessor(Alice_processor):Finished waiting
```

- **TIME** - Simulation time in nanoseconds
- **LOGGER_NAME** - Identifies the source component

## Advanced Run Options

The `run()` function accepts additional parameters:

```python
from squidasm.run.stack.run import run

results = run(
    config=cfg,                    # Network configuration
    programs=programs,             # Node-program mapping
    num_times=10,                  # Number of iterations
)
```

### Multithread vs Singlethread Execution

SquidASM supports different execution modes:

```python
# Singlethread execution (default)
from squidasm.run.singlethread.run import run as run_singlethread

# Multithread execution (for larger simulations)
from squidasm.run.multithread.run import run as run_multithread
```

The singlethread mode is simpler and sufficient for most use cases. Multithread mode can provide performance benefits for complex simulations.

## Example: Complete Simulation Script

```python
"""Complete simulation example with logging and results processing."""

from application import AliceProgram, BobProgram
from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager
import numpy as np

# Configure logging
LogManager.set_log_level("INFO")

# Load network configuration
cfg = StackNetworkConfig.from_file("config.yaml")

# Create programs with parameters
alice_program = AliceProgram(num_rounds=10)
bob_program = BobProgram(num_rounds=10)

# Run simulation
num_iterations = 100
results = run(
    config=cfg,
    programs={"Alice": alice_program, "Bob": bob_program},
    num_times=num_iterations
)

alice_results, bob_results = results

# Analyze results
alice_measurements = [r["measurements"] for r in alice_results]
bob_measurements = [r["measurements"] for r in bob_results]

# Calculate statistics
all_alice = [m for run in alice_measurements for m in run]
all_bob = [m for run in bob_measurements for m in run]

correlation = sum(a == b for a, b in zip(all_alice, all_bob)) / len(all_alice)
print(f"Correlation: {correlation:.2%}")
print(f"Total measurements: {len(all_alice)}")
```

## Summary

In this section you learned:

- How to structure **run_simulation.py** with program imports and configuration
- The **Program interface** with `@property def meta()` and `def run(context)`
- How to access **sockets by peer name** (not tuples)
- Using **app_config** for application configuration
- How to **return results** and process them after simulation
- Using **GlobalSimData** for simulation-wide data
- Configuring **logging** with LogManager
- **Log levels** and message format interpretation

## Next Steps

- [Tutorial 4: Network Configuration](4_network_configuration.md) - Detailed network setup
- [Tutorial 5: Multi-Node Networks](5_multi_node.md) - Networks with more than two nodes
- [Tutorial 6: Parameter Sweeping](6_parameter_sweeping.md) - Running parameter studies
