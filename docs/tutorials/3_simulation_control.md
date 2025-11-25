# Tutorial 3: Simulation Control

In this section we explain the `run_simulation.py` file and the interface that programs in `application.py` must adhere to. We also cover ways to get output results from the program and logging.

The first sections will use the example `examples/tutorial/1_Basics` for code snippets.

## Basic run_simulation.py

The `examples/tutorial/1_Basics/run_simulation.py` file contains the minimal requirements to run a simulation:

```python
from application import AliceProgram, BobProgram

from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run

# import network configuration from file
cfg = StackNetworkConfig.from_file("config.yaml")

# Create instances of programs to run
alice_program = AliceProgram()
bob_program = BobProgram()

# Run the simulation. Programs argument is a mapping of network node labels to programs to run on that node
run(config=cfg, programs={"Alice": alice_program, "Bob": bob_program}, num_times=1)
```

### Components

In the `run_simulation.py` file:

1. **Import programs** - Import the `AliceProgram` and `BobProgram` classes
2. **Load configuration** - Load the network configuration from a YAML file into a variable
3. **Create instances** - Create instances of the programs
4. **Map programs to nodes** - Use a Python dictionary mapping node names to program instances
5. **Run simulation** - Pass both the network configuration and node-program mapping to the `run()` function

### Important Note

The node names are used in multiple locations across the various files. All the names must match for the simulation to work:

- Node names in `config.yaml` (under `stacks`)
- Node names in program socket declarations (e.g., `self.PEER_NAME = "Bob"`)
- Node names in the `programs` dictionary in `run_simulation.py`

### Program Class Flexibility

There is no restriction that the program classes must be different per node; only the instances need to be different. Instead of using different classes, it is possible to use a single class and set a flag in one of the program instances that defines its role in the application.

## Program Interface

The largest difference with the NetQASM SDK are the interface requirements that programs must adhere to. Programs must have two requirements:

1. A `meta()` method that returns a `ProgramMeta` object
2. A `run()` method that accepts a `ProgramContext` object

### The Program Abstract Base Class

```python
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from typing import Generator

class Program:
    """Abstract base class for quantum network applications."""
    
    @staticmethod
    def meta() -> ProgramMeta:
        """Declare program requirements (sockets, etc.)."""
        raise NotImplementedError
    
    def run(self, context: ProgramContext) -> Generator:
        """Execute the program."""
        raise NotImplementedError
```

### ProgramMeta and ProgramContext

The `ProgramMeta` object declares what the program needs, and the `ProgramContext` provides those resources.

For example, if the `ProgramMeta` declares:

```python
@staticmethod
def meta() -> ProgramMeta:
    return ProgramMeta(
        name="Alice",
        csockets=["Bob"],  # Need classical socket to Bob
        epr_sockets=[("Bob", 1)],  # Need EPR socket with Bob for 1 pair
    )
```

Then inside the `run()` method, you can access these resources:

```python
def run(self, context: ProgramContext) -> Generator:
    csocket = context.csockets["Bob"]  # Classical socket to Bob
    epr_socket = context.epr_sockets[("Bob", 0)]  # EPR socket to Bob
    connection = context.connection  # NetQASM connection
    
    # Use these resources...
```

### Example Program

Here's the `AliceProgram` from the basics tutorial:

```python
class AliceProgram(Program):
    PEER_NAME = "Bob"
    
    @staticmethod
    def meta() -> ProgramMeta:
        return ProgramMeta(
            name="Alice",
            csockets=[AliceProgram.PEER_NAME],
            epr_sockets=[(AliceProgram.PEER_NAME, 1)],
        )
    
    def run(self, context: ProgramContext) -> Generator:
        csocket = context.csockets[AliceProgram.PEER_NAME]
        epr_socket = context.epr_sockets[(AliceProgram.PEER_NAME, 0)]
        connection = context.connection
        
        # Send classical message
        csocket.send("Hello")
        
        # Create and measure EPR pair
        q = (yield from epr_socket.create_keep(1))[0]
        q.H()
        result = q.measure()
        yield from connection.flush()
        
        print(f"Alice measures local EPR qubit: {result}")
```

### Multi-Node Note

While currently unsupported, for multi-node applications it would be required to specify the other node names for the classical and EPR sockets in `ProgramMeta`.

## Getting Output from Programs

To evaluate the performance of an application, we often run it for multiple iterations with possibly multiple parameters and network configurations. This section shows how to send output from a program to `run_simulation.py`.

### Example: EPR Fidelity Testing

In `examples/tutorial/3.1_output` we create an application that generates EPR pairs, applies a Hadamard gate, and measures them:

```python
class AliceProgram(Program):
    PEER_NAME = "Bob"
    
    def __init__(self, num_epr_rounds: int = 1):
        self.num_epr_rounds = num_epr_rounds
    
    @staticmethod
    def meta() -> ProgramMeta:
        return ProgramMeta(
            name="Alice",
            csockets=[AliceProgram.PEER_NAME],
            epr_sockets=[(AliceProgram.PEER_NAME, AliceProgram.num_epr_rounds)],
        )
    
    def run(self, context: ProgramContext) -> Generator:
        csocket = context.csockets[self.PEER_NAME]
        epr_socket = context.epr_sockets[(self.PEER_NAME, 0)]
        connection = context.connection
        
        measurements = []
        
        for i in range(self.num_epr_rounds):
            # Create EPR pair
            q = (yield from epr_socket.create_keep(1))[0]
            q.H()
            m = q.measure()
            yield from connection.flush()
            measurements.append(int(m))
        
        # Send Bob our measurements for comparison
        csocket.send(measurements)
        bob_measurements = yield from csocket.recv()
        
        # Return results
        return {"measurements": measurements}
```

The program for Bob is identical, except it uses `recv_keep()` instead of `create_keep()`.

### Accessing Results in run_simulation.py

The program may return a dictionary of various outputs at the end of the program using the `return` command. These dictionaries are returned to the `run_simulation.py` file as the return of the `run()` function.

```python
from application import AliceProgram, BobProgram
from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run
import numpy as np

# Load configuration
cfg = StackNetworkConfig.from_file("config.yaml")

# Set parameters
epr_rounds = 10
alice_program = AliceProgram(num_epr_rounds=epr_rounds)
bob_program = BobProgram(num_epr_rounds=epr_rounds)

# Run simulation multiple times
simulation_iterations = 20
results_alice, results_bob = run(
    config=cfg,
    programs={"Alice": alice_program, "Bob": bob_program},
    num_times=simulation_iterations,
)

# Process results
alice_measurements = [results_alice[i]["measurements"] for i in range(simulation_iterations)]
bob_measurements = [results_bob[i]["measurements"] for i in range(simulation_iterations)]

# Calculate error rate
errors = sum(
    sum(am != bm for am, bm in zip(alice_m, bob_m))
    for alice_m, bob_m in zip(alice_measurements, bob_measurements)
)
total = sum(len(m) for m in alice_measurements)
error_rate = errors / total

print(f"Average error rate: {error_rate * 100:.1f}% using {total} EPR requests")
```

### Result Structure

The return of the `run()` function is of type `List[List[Dict]]`:

- **First list** - Ordered per simulation node (Alice, Bob, etc.)
- **Second list** - Ordered by simulation iteration
- **Dictionary** - The dictionary returned by each program instance

### Important Note on Futures

Before returning any `Future` type objects, it is advisable to convert them to native Python integers or other native types. `Future` objects may cause unexpected behavior in various operations:

```python
# Good: Convert to int before returning
return {"measurements": [int(m) for m in measurements]}

# Avoid: Returning Future objects directly
return {"measurements": measurements}  # measurements contains Futures
```

## Logging

As more advanced applications are created and tested on networks that simulate noise and loss, it becomes inevitable that in some edge cases the application will return unexpected results or crash. Using logs helps in finding the cause.

### Logging Setup Example

To show the usage of logging, we use the example `examples/tutorial/3.2_logging`. This is a QKD-like application that sends a message of unknown size with encryption via EPR pairs.

The `AliceProgram` uses logging by moving away from print statements to logger statements:

```python
from squidasm.sim.stack.common import LogManager

class AliceProgram(Program):
    def __init__(self, message: list):
        self.message = message
    
    def run(self, context: ProgramContext) -> Generator:
        logger = LogManager.get_stack_logger("AliceProgram")
        csocket = context.csockets["Bob"]
        epr_socket = context.epr_sockets[("Bob", 0)]
        connection = context.connection
        
        for bit in self.message:
            # Generate encryption bits via EPR
            q1, q2 = yield from epr_socket.create_keep(2)
            m1 = q1.measure()
            m2 = q2.measure()
            yield from connection.flush()
            
            # XOR with encryption bits
            encrypted_bit = bit ^ int(m1) ^ int(m2)
            continue_bit = 1  # Normal case
            
            logger.info(f"Measured qubits: {m1} {m2}")
            logger.info(f"Send bits: {encrypted_bit} {continue_bit}")
            
            # Send to Bob
            csocket.send(encrypted_bit)
            csocket.send(continue_bit)
```

### Log Levels

There are 5 levels of logging in order of highest to lowest severity:

1. **CRITICAL** - Critical errors that prevent operation
2. **ERROR** - Errors that occurred but operation can continue
3. **WARNING** - Warning messages about potential issues
4. **INFO** - General informational messages (default level)
5. **DEBUG** - Detailed debugging information

### Logger Methods

The logger object is obtained via:

```python
logger = LogManager.get_stack_logger("AliceProgram")
```

By initializing the logger with a string like `"AliceProgram"`, the logger is initialized as a sub-logger of that type. This sub-logger name will show up in the log messages.

Logger methods corresponding to each level:

```python
logger.critical("Critical message")
logger.error("Error message")
logger.warning("Warning message")
logger.info("Info message")
logger.debug("Debug message")
```

### Setting Log Level

In `run_simulation.py`, configure logging:

```python
from squidasm.sim.stack.common import LogManager

# Set the log level
LogManager.set_log_level("INFO")

# Optional: Log to file instead of terminal
LogManager.log_to_file("simulation.log")
```

The log level determines what messages will be logged. Setting it to `DEBUG` will enable all log messages. Other levels will disregard messages of a lower level (e.g., `INFO` level ignores `DEBUG` messages).

### Log Format

Messages are structured into four segments separated by `:` characters:

```
LEVEL:TIME:LOGGER_NAME:MESSAGE
```

Example output:

```
INFO:44000.0 ns:Stack.AliceProgram:Measured qubits: 0 1
WARNING:44000.0 ns:Stack.Netstack(Bob_netstack):waiting for result for pair 1
DEBUG:44000.0 ns:Stack.GenericProcessor(Alice_processor):Finished waiting for array slice
```

### Log Message Parts

- **LEVEL** - The logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **TIME** - The time in simulation (in nanoseconds, not real-world time)
- **LOGGER_NAME** - The sub-logger name (provides context)
- **MESSAGE** - The actual log message

### Example: Debugging with Logs

Here's output from the QKD example with an imperfect link (fidelity 0.9):

```
INFO:44000.0 ns:Stack.AliceProgram:Measured qubits: 0 1
INFO:44000.0 ns:Stack.AliceProgram:Send bits: 1 0
...
INFO:66000.0 ns:Stack.BobProgram:Measured qubits: 1 0
INFO:66000.0 ns:Stack.BobProgram:Received bits: 0 1
```

In this case, an EPR pair measurement resulted in different values for Alice and Bob, introducing an error. The logs help identify exactly where this happened.

## Summary

In this section you learned:

- How to structure `run_simulation.py` with program imports and configuration loading
- The **Program interface** with `meta()` and `run()` methods
- How to access sockets and connections via `ProgramContext`
- How to **return results** from programs and access them in `run_simulation.py`
- How to use **logging** to debug applications
- **Log levels** and how to configure logging
- How to interpret **log messages** with their format and timing information

The next section will explain network configuration, including how to specify stack types, link types, and how to perform parameter sweeping.
