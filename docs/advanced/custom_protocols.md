# Custom Protocols

This guide explains how to implement custom quantum network protocols in SquidASM.

## Protocol Structure

A quantum network protocol typically consists of:

1. **Multiple programs** - One for each participating node
2. **Shared state** - Agreement on protocol parameters
3. **Communication patterns** - Classical and quantum exchanges
4. **Error handling** - Dealing with imperfections

## Example: Custom QKD Protocol

### Protocol Design

Let's implement a simplified QKD protocol:

1. Alice generates random bits and bases
2. Alice encodes and sends qubits to Bob
3. Bob measures in random bases
4. They compare bases and extract key

### Alice's Program

```python
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from netqasm.sdk.qubit import Qubit
import random

class QKDAliceProgram(Program):
    """Alice's role in the QKD protocol."""
    
    PEER_NAME = "Bob"
    
    def __init__(self, key_length: int = 100):
        self.key_length = key_length
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="qkd_alice",
            csockets=[self.PEER_NAME],
            epr_sockets=[self.PEER_NAME],
            max_qubits=1
        )
    
    def run(self, context: ProgramContext):
        csocket = context.csockets[self.PEER_NAME]
        epr_socket = context.epr_sockets[self.PEER_NAME]
        connection = context.connection
        
        # Generate random bits and bases
        bits = [random.randint(0, 1) for _ in range(self.key_length)]
        bases = [random.randint(0, 1) for _ in range(self.key_length)]
        
        # Send qubits through EPR pairs
        for bit, basis in zip(bits, bases):
            # Create EPR pair
            q = epr_socket.create_keep()[0]
            
            # Encode bit
            if bit == 1:
                q.X()
            
            # Apply basis
            if basis == 1:
                q.H()  # Diagonal basis
            
            # Measure to "send" the state
            # (In real QKD, this would be direct transmission)
            m = q.measure()
            connection.flush()
        
        # Basis reconciliation
        csocket.send(",".join(map(str, bases)))
        bob_bases = yield from csocket.recv()
        bob_bases = list(map(int, bob_bases.split(",")))
        
        # Sift key
        sifted_key = [
            bits[i] for i in range(self.key_length)
            if bases[i] == bob_bases[i]
        ]
        
        return {
            "sifted_key": sifted_key,
            "sifted_length": len(sifted_key)
        }
```

### Bob's Program

```python
class QKDBobProgram(Program):
    """Bob's role in the QKD protocol."""
    
    PEER_NAME = "Alice"
    
    def __init__(self, key_length: int = 100):
        self.key_length = key_length
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="qkd_bob",
            csockets=[self.PEER_NAME],
            epr_sockets=[self.PEER_NAME],
            max_qubits=1
        )
    
    def run(self, context: ProgramContext):
        csocket = context.csockets[self.PEER_NAME]
        epr_socket = context.epr_sockets[self.PEER_NAME]
        connection = context.connection
        
        # Generate random measurement bases
        bases = [random.randint(0, 1) for _ in range(self.key_length)]
        measurements = []
        
        for basis in bases:
            # Receive EPR qubit
            q = epr_socket.recv_keep()[0]
            
            # Apply measurement basis
            if basis == 1:
                q.H()  # Diagonal basis
            
            # Measure
            m = q.measure()
            connection.flush()
            measurements.append(int(m))
        
        # Basis reconciliation
        alice_bases = yield from csocket.recv()
        alice_bases = list(map(int, alice_bases.split(",")))
        csocket.send(",".join(map(str, bases)))
        
        # Sift key
        sifted_key = [
            measurements[i] for i in range(self.key_length)
            if bases[i] == alice_bases[i]
        ]
        
        return {
            "sifted_key": sifted_key,
            "sifted_length": len(sifted_key)
        }
```

## Example: Entanglement Swapping Protocol

### Protocol Overview

Entanglement swapping extends entanglement range:

```
Alice <==> Relay <==> Bob

1. Alice-Relay share EPR pair
2. Relay-Bob share EPR pair
3. Relay performs Bell measurement
4. Alice-Bob become entangled
```

### Relay Program

```python
class RelayProgram(Program):
    """Relay node for entanglement swapping."""
    
    LEFT = "Alice"
    RIGHT = "Bob"
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="relay",
            csockets=[self.LEFT, self.RIGHT],
            epr_sockets=[self.LEFT, self.RIGHT],
            max_qubits=2
        )
    
    def run(self, context: ProgramContext):
        connection = context.connection
        epr_left = context.epr_sockets[self.LEFT]
        epr_right = context.epr_sockets[self.RIGHT]
        cs_left = context.csockets[self.LEFT]
        cs_right = context.csockets[self.RIGHT]
        
        # Receive EPR qubits from both sides
        q_left = epr_left.recv_keep()[0]
        q_right = epr_right.create_keep()[0]
        
        # Bell state measurement
        q_left.cnot(q_right)
        q_left.H()
        
        m1 = q_left.measure()
        m2 = q_right.measure()
        connection.flush()
        
        # Send corrections
        corrections = f"{int(m1)},{int(m2)}"
        cs_left.send(corrections)
        cs_right.send(corrections)
        
        return {"m1": int(m1), "m2": int(m2)}
```

### End Node Programs

```python
class AliceSwapProgram(Program):
    """Alice in entanglement swapping."""
    
    RELAY = "Relay"
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="alice_swap",
            csockets=[self.RELAY],
            epr_sockets=[self.RELAY],
            max_qubits=1
        )
    
    def run(self, context: ProgramContext):
        connection = context.connection
        epr_socket = context.epr_sockets[self.RELAY]
        csocket = context.csockets[self.RELAY]
        
        # Create EPR with relay
        q = epr_socket.create_keep()[0]
        
        # Wait for relay's corrections
        corrections = yield from csocket.recv()
        m1, m2 = map(int, corrections.split(","))
        
        # Apply corrections (optional, depends on protocol)
        if m2 == 1:
            q.Z()
        
        # Now q is entangled with Bob's qubit
        result = q.measure()
        connection.flush()
        
        return {"result": int(result)}


class BobSwapProgram(Program):
    """Bob in entanglement swapping."""
    
    RELAY = "Relay"
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="bob_swap",
            csockets=[self.RELAY],
            epr_sockets=[self.RELAY],
            max_qubits=1
        )
    
    def run(self, context: ProgramContext):
        connection = context.connection
        epr_socket = context.epr_sockets[self.RELAY]
        csocket = context.csockets[self.RELAY]
        
        # Receive EPR from relay
        q = epr_socket.recv_keep()[0]
        
        # Wait for relay's corrections
        corrections = yield from csocket.recv()
        m1, m2 = map(int, corrections.split(","))
        
        # Apply corrections
        if m1 == 1:
            q.X()
        
        # Now q is entangled with Alice's qubit
        result = q.measure()
        connection.flush()
        
        return {"result": int(result)}
```

## Example: Secret Sharing Protocol

### Protocol: (2,3) Secret Sharing

Split a secret among 3 parties where any 2 can reconstruct it.

```python
class DealerProgram(Program):
    """Dealer distributes secret shares."""
    
    PARTIES = ["Alice", "Bob", "Charlie"]
    
    def __init__(self, secret_bit: int):
        self.secret = secret_bit
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="dealer",
            csockets=self.PARTIES,
            epr_sockets=self.PARTIES,
            max_qubits=3
        )
    
    def run(self, context: ProgramContext):
        connection = context.connection
        
        # Create GHZ-like state for secret sharing
        # |000⟩ + |111⟩ for secret=0
        # |000⟩ - |111⟩ for secret=1
        
        qubits = []
        for party in self.PARTIES:
            epr_socket = context.epr_sockets[party]
            q = epr_socket.create_keep()[0]
            qubits.append(q)
        
        # Create entangled state
        qubits[0].H()
        for i in range(1, len(qubits)):
            qubits[0].cnot(qubits[i])
        
        # Encode secret
        if self.secret == 1:
            qubits[0].Z()
        
        # Measure and distribute shares
        shares = []
        for q in qubits:
            m = q.measure()
            connection.flush()
            shares.append(int(m))
        
        # Send classical part of share
        for i, party in enumerate(self.PARTIES):
            csocket = context.csockets[party]
            csocket.send(str(shares[i]))
        
        return {"shares_distributed": shares}
```

## Protocol Design Patterns

### Pattern 1: Request-Response

```python
class RequestorProgram(Program):
    def run(self, context: ProgramContext):
        csocket = context.csockets["Server"]
        
        # Send request
        csocket.send("REQUEST:data")
        
        # Wait for response
        response = yield from csocket.recv()
        
        return {"response": response}


class ResponderProgram(Program):
    def run(self, context: ProgramContext):
        csocket = context.csockets["Client"]
        
        # Wait for request
        request = yield from csocket.recv()
        
        # Process and respond
        result = self.process(request)
        csocket.send(f"RESPONSE:{result}")
        
        return {"handled": request}
```

### Pattern 2: Synchronized Measurement

```python
class SyncMeasureProgram(Program):
    def run(self, context: ProgramContext):
        # Create entanglement
        q = context.epr_sockets["Partner"].create_keep()[0]
        
        # Signal ready
        context.csockets["Partner"].send("READY")
        
        # Wait for partner ready
        yield from context.csockets["Partner"].recv()
        
        # Measure simultaneously (in simulation time)
        result = q.measure()
        context.connection.flush()
        
        return {"result": int(result)}
```

### Pattern 3: Multi-Round Protocol

```python
class MultiRoundProgram(Program):
    def __init__(self, num_rounds: int):
        self.num_rounds = num_rounds
    
    def run(self, context: ProgramContext):
        results = []
        
        for round_num in range(self.num_rounds):
            # Perform one round
            result = yield from self._do_round(context, round_num)
            results.append(result)
            
            # Synchronize between rounds
            context.csockets["Partner"].send(f"ROUND_{round_num}_DONE")
            yield from context.csockets["Partner"].recv()
        
        return {"all_results": results}
    
    def _do_round(self, context, round_num):
        # Round-specific logic
        pass
```

## Testing Custom Protocols

### Unit Testing

```python
import unittest
from squidasm.run.stack.config import StackNetworkConfig
from squidasm.run.stack.run import run

class TestCustomProtocol(unittest.TestCase):
    def setUp(self):
        self.config = StackNetworkConfig.from_file("test_config.yaml")
    
    def test_protocol_correctness(self):
        alice = CustomAliceProgram()
        bob = CustomBobProgram()
        
        results = run(
            config=self.config,
            programs={"Alice": alice, "Bob": bob},
            num_times=100
        )
        
        alice_results, bob_results = results
        
        # Verify protocol properties
        for a, b in zip(alice_results, bob_results):
            self.assertEqual(a["key"], b["key"])
    
    def test_protocol_with_noise(self):
        # Load noisy configuration
        noisy_config = StackNetworkConfig.from_file("noisy_config.yaml")
        
        results = run(
            config=noisy_config,
            programs={"Alice": alice, "Bob": bob},
            num_times=100
        )
        
        # Calculate error rate
        errors = self._count_errors(results)
        self.assertLess(errors, 0.15)  # Less than 15% error
```

### Integration Testing

```python
def test_end_to_end():
    """Full protocol integration test."""
    
    # Setup
    config = create_realistic_config()
    
    alice = ProtocolAlice(param1=value1)
    bob = ProtocolBob(param2=value2)
    
    # Run
    results = run(
        config=config,
        programs={"Alice": alice, "Bob": bob},
        num_times=1000
    )
    
    # Analyze
    success_rate = calculate_success_rate(results)
    fidelity = calculate_fidelity(results)
    
    print(f"Success rate: {success_rate:.2%}")
    print(f"Fidelity: {fidelity:.4f}")
    
    assert success_rate > 0.9
    assert fidelity > 0.85
```

## Best Practices

### 1. Clear State Management

```python
class WellDesignedProtocol(Program):
    def __init__(self):
        # Initialize all state
        self.round_results = []
        self.error_count = 0
    
    def run(self, context):
        # Reset per-run state
        self.round_results = []
        # ... protocol logic
```

### 2. Proper Error Handling

```python
def run(self, context):
    try:
        q = epr_socket.create_keep()[0]
    except Exception as e:
        logger.error(f"EPR creation failed: {e}")
        return {"error": str(e)}
```

### 3. Logging

```python
from squidasm.sim.stack.common import LogManager

class LoggingProtocol(Program):
    def run(self, context):
        logger = LogManager.get_stack_logger("MyProtocol")
        
        logger.info("Starting protocol")
        logger.debug(f"Parameters: {self.params}")
        
        # ... protocol logic
        
        logger.info("Protocol complete")
```

## See Also

- [Noise Models](noise_models.md) - Simulating realistic conditions
- [Debugging](debugging.md) - Debugging protocol issues
- [squidasm.sim Package](../api/sim_package.md) - API reference
