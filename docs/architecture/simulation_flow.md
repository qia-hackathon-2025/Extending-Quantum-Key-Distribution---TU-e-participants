# Simulation Flow

This document describes how SquidASM simulations are built and executed, from configuration loading to result collection.

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Code                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ config.yaml │  │ Programs    │  │ run_simulation.py       │  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │
└─────────┼────────────────┼─────────────────────┼────────────────┘
          │                │                     │
          ▼                ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                     squidasm.run.stack                           │
│  ┌─────────────────┐  ┌────────────────┐  ┌─────────────────┐   │
│  │ StackNetworkCfg │  │ build_network()│  │ run()           │   │
│  └────────┬────────┘  └───────┬────────┘  └────────┬────────┘   │
└───────────┼───────────────────┼────────────────────┼────────────┘
            │                   │                    │
            ▼                   ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                     squidasm.sim.stack                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐     │
│  │ Stack    │  │ Host     │  │ QNos     │  │ Program      │     │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘     │
└───────┼─────────────┼─────────────┼───────────────┼─────────────┘
        │             │             │               │
        ▼             ▼             ▼               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     squidasm.nqasm                               │
│  ┌──────────────┐  ┌─────────────────┐  ┌───────────────────┐   │
│  │ QNodeOS      │  │ NetworkStack    │  │ NetSquidExecutor  │   │
│  └──────┬───────┘  └────────┬────────┘  └─────────┬─────────┘   │
└─────────┼───────────────────┼─────────────────────┼─────────────┘
          │                   │                     │
          ▼                   ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                       NetSquid                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐    │
│  │ Network      │  │ Connections  │  │ QuantumProcessor    │    │
│  └──────────────┘  └──────────────┘  └─────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Phase 1: Configuration Loading

### 1.1 Parse YAML Configuration

```python
from squidasm.run.stack.config import StackNetworkConfig

# Load from file
config = StackNetworkConfig.from_file("config.yaml")

# Internal flow:
# 1. Read YAML file
# 2. Parse into Python dictionaries
# 3. Validate structure
# 4. Create typed config objects (StackConfig, LinkConfig, etc.)
```

### 1.2 Configuration Validation

The configuration classes perform validation:

```python
class StackNetworkConfig:
    def __post_init__(self):
        # Validate stack names are unique
        names = [s.name for s in self.stacks]
        assert len(names) == len(set(names)), "Duplicate stack names"
        
        # Validate links reference existing stacks
        for link in self.links:
            assert link.stack1 in names, f"Unknown stack: {link.stack1}"
            assert link.stack2 in names, f"Unknown stack: {link.stack2}"
```

### Configuration Object Hierarchy

```
StackNetworkConfig
├── stacks: List[StackConfig]
│   ├── name: str
│   ├── qdevice_typ: str
│   ├── qdevice_cfg: GenericQDeviceConfig | NVQDeviceConfig
│   └── app: Dict[str, Any]
├── links: List[LinkConfig]
│   ├── stack1, stack2: str
│   ├── typ: str
│   └── cfg: DepolariseLinkConfig | HeraldedLinkConfig | ...
└── clinks: List[CLinkConfig]
    ├── stack1, stack2: str
    ├── typ: str
    └── cfg: DefaultCLinkConfig | ...
```

## Phase 2: Network Building

### 2.1 Create NetSquid Network

```python
from squidasm.run.stack.build import build_network

# Build creates:
# - NetSquid Network object
# - Stack objects for each node
# - Quantum and classical connections

network, stacks = build_network(config)
```

### 2.2 Stack Construction

Each stack contains multiple components:

```python
def build_stack(name: str, stack_config: StackConfig) -> Stack:
    """Build a single network stack."""
    
    # 1. Create quantum device based on type
    if stack_config.qdevice_typ == "generic":
        qdevice = create_generic_qdevice(stack_config.qdevice_cfg)
    elif stack_config.qdevice_typ == "nv":
        qdevice = create_nv_qdevice(stack_config.qdevice_cfg)
    
    # 2. Create QNodeOS (quantum operating system)
    qnos = QNodeOS(name, qdevice)
    
    # 3. Create Host (application runner)
    host = Host(name, qnos)
    
    # 4. Assemble into Stack
    stack = Stack(name, host, qnos, qdevice)
    
    return stack
```

### 2.3 Link Construction

```python
def build_link(link_config: LinkConfig, stacks: Dict[str, Stack]):
    """Build quantum link between two stacks."""
    
    stack1 = stacks[link_config.stack1]
    stack2 = stacks[link_config.stack2]
    
    if link_config.typ == "perfect":
        connection = PerfectQuantumConnection(stack1, stack2)
    elif link_config.typ == "depolarise":
        connection = DepolariseConnection(
            stack1, stack2,
            fidelity=link_config.cfg.fidelity,
            t_cycle=link_config.cfg.t_cycle
        )
    elif link_config.typ == "heralded":
        connection = HeraldedConnection(stack1, stack2, link_config.cfg)
    
    return connection
```

### Build Process Flow

```
StackNetworkConfig
        │
        ▼
┌───────────────────┐
│   build_network() │
└─────────┬─────────┘
          │
    ┌─────┴─────┐
    ▼           ▼
┌─────────┐  ┌─────────┐
│ build_  │  │ build_  │
│ stack() │  │ link()  │
└────┬────┘  └────┬────┘
     │            │
     ▼            ▼
┌─────────┐  ┌─────────────┐
│ Stack   │  │ Connection  │
│ objects │  │ objects     │
└────┬────┘  └──────┬──────┘
     │              │
     └──────┬───────┘
            ▼
     ┌──────────────┐
     │   Network    │
     │   (NetSquid) │
     └──────────────┘
```

## Phase 3: Program Registration

### 3.1 Map Programs to Stacks

```python
# User provides mapping
programs = {
    "Alice": alice_program,
    "Bob": bob_program,
}

# Internal registration
for node_name, program in programs.items():
    stack = stacks[node_name]
    stack.host.register_program(program)
```

### 3.2 Register Program Resources

```python
def register_program(self, program: Program):
    """Register program and allocate resources."""
    
    # Get program metadata
    meta = program.meta
    
    # Register classical sockets
    for peer_name in meta.csockets:
        self.create_csocket(peer_name)
    
    # Register EPR sockets
    for peer_name in meta.epr_sockets:
        self.create_epr_socket(peer_name)
    
    # Reserve qubit memory
    self.qnos.allocate_memory(meta.max_qubits)
```

## Phase 4: Simulation Execution

### 4.1 Initialize Discrete-Event Simulation

```python
import netsquid as ns

def run_simulation():
    # Reset NetSquid simulation
    ns.sim_reset()
    
    # Initialize all components
    for stack in stacks.values():
        stack.start()
    
    # Schedule program execution
    for node_name, program in programs.items():
        ns.sim_engine().schedule_event(
            time=0,
            entity=stacks[node_name].host,
            handler=stacks[node_name].host.run_program
        )
```

### 4.2 Event-Driven Execution

NetSquid uses discrete-event simulation:

```
Time    Event                           Handler
────────────────────────────────────────────────────
0       Program start (Alice)           Host.run_program
0       Program start (Bob)             Host.run_program
100     Gate operation complete         Executor.handle_gate
110     EPR request (Alice)             NetworkStack.create_epr
110     EPR request (Bob)               NetworkStack.recv_epr
500     EPR generation complete         NetworkStack.deliver_epr
510     Measurement complete            Executor.handle_measurement
520     Classical message sent          CSocket.send
1520    Classical message received      CSocket.recv
1530    Program complete (Bob)          Host.finish_program
1540    Program complete (Alice)        Host.finish_program
```

### 4.3 Program Execution Flow

```python
class Host:
    def run_program(self, program: Program, context: ProgramContext):
        """Execute a single program."""
        
        # Create generator from program.run()
        generator = program.run(context)
        
        # Execute generator, handling yields
        try:
            result = None
            while True:
                # Advance generator
                yielded = generator.send(result)
                
                if isinstance(yielded, CSocketRecv):
                    # Wait for classical message
                    result = yield from self.await_classical(yielded)
                elif isinstance(yielded, FlushRequest):
                    # Execute queued quantum operations
                    result = yield from self.execute_flush(yielded)
                else:
                    result = None
                    
        except StopIteration as e:
            # Program completed, return result
            return e.value
```

### 4.4 NetQASM Execution

```python
class NetSquidExecutor:
    def execute_subroutine(self, subroutine: Subroutine):
        """Execute a NetQASM subroutine."""
        
        handler = SubroutineHandler(subroutine)
        
        while not handler.finished():
            instr = handler.current_instruction()
            
            # Execute instruction
            if instr.is_gate():
                yield from self.execute_gate(instr, handler)
            elif instr.is_measurement():
                yield from self.execute_measurement(instr, handler)
            elif instr.is_epr():
                yield from self.execute_epr(instr, handler)
            elif instr.is_classical():
                self.execute_classical(instr, handler)
            
            handler.advance()
```

## Phase 5: Result Collection

### 5.1 Collect Program Results

```python
def collect_results(stacks, programs, num_iterations):
    """Collect results from all program executions."""
    
    results = [[] for _ in programs]
    
    for iteration in range(num_iterations):
        # Run one simulation
        run_once()
        
        # Collect results from each program
        for i, node_name in enumerate(programs.keys()):
            result = stacks[node_name].host.get_program_result()
            results[i].append(result)
        
        # Reset for next iteration
        ns.sim_reset()
    
    return results
```

### 5.2 Result Structure

```python
# Return structure: List[List[Dict]]
# Outer list: One entry per node
# Inner list: One entry per iteration
# Dict: Program's return value

results = run(config, programs, num_times=100)
# results[0] = Alice's results (list of 100 dicts)
# results[1] = Bob's results (list of 100 dicts)

for iteration in range(100):
    alice_result = results[0][iteration]  # Dict from Alice's return
    bob_result = results[1][iteration]    # Dict from Bob's return
```

## Timing and Synchronization

### Simulation Time vs Real Time

```
Simulation Time (ns)    Event
─────────────────────────────────────────
0                       Programs start
100                     Gate operation
500                     EPR generated
1000                    Measurement done
2000                    Programs end

Total simulation time: 2000 ns
Actual wall time: ~0.5 seconds
```

### Synchronization Points

Programs synchronize through:

1. **EPR operations**: `create_keep()` waits for partner's `recv_keep()`
2. **Classical messages**: `recv()` waits for partner's `send()`
3. **Flush operations**: `flush()` executes queued operations

```python
# Alice                          # Bob
epr_socket.create_keep()         epr_socket.recv_keep()
# ↓ EPR synchronization ↓        # ↓ EPR synchronization ↓
csocket.send("done")             msg = yield from csocket.recv()
# ↓ Classical sync ↓             # ↓ Classical sync ↓
```

## Error Handling

### Runtime Errors

```python
def run_safe(config, programs, num_times):
    """Run with error handling."""
    try:
        return run(config, programs, num_times)
    except SimulationError as e:
        logger.error(f"Simulation error: {e}")
        raise
    except TimeoutError as e:
        logger.error(f"Timeout waiting for: {e}")
        raise
```

### Common Error Sources

| Error | Cause | Solution |
|-------|-------|----------|
| Deadlock | Mismatched send/recv | Check communication patterns |
| Memory error | Too many qubits | Increase num_qubits or reduce max_qubits |
| Timeout | EPR generation failure | Check link configuration |

## See Also

- [Stack Components](stack_components.md) - Detailed component descriptions
- [NetQASM Integration](netqasm_integration.md) - NetQASM execution details
- [squidasm.run Package](../api/run_package.md) - API documentation
