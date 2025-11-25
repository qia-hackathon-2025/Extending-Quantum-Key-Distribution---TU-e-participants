# Appendix: Terminology

This section provides definitions of key terms used throughout the SquidASM tutorial and documentation.

## Core Concepts

### Program
Part of an application, but refers to the code being executed on one node. For example, BQC (Blind Quantum Computing) is an application, but it consists of two programs: one program for the client and another for the server.

### Application
A collection of programs on multiple nodes working together to achieve a certain result. Examples include quantum key distribution (QKD), entanglement swapping, and blind quantum computing.

### Quantum Network Processing Unit (QNPU)
The software and device responsible for both operations on local qubits as well as creating EPR pairs with remote nodes. The software is sent instructions using the [NetQASM language](https://github.com/QuTech-Delft/netqasm). An example of the software is QNodeOS (Quantum Node Operating System).

### Host
The device running a program. This can be any type of classical computer. This is one of the highest layers of the stack of an end node. The host runs a quantum internet application by sending instructions to the Quantum Network Processing Unit (QNPU).

### NetQASM Connection
The link between the host and the QNPU. This connection is used to send quantum instructions from the host to the QNPU and to receive results back. In SquidASM programs, this is represented by the `connection` object.

## Socket Types

### Classical Socket
A point-to-point connection between two nodes for classical message passing. Classical sockets are unidirectional: one node sends messages while another node receives them. Messages are guaranteed to arrive in order and without loss, but may be delayed depending on the link configuration.

### EPR Socket
A socket for generating entangled qubit pairs between two nodes. EPR sockets handle the quantum coordination required to create Bell pairs between distant nodes. The socket provides an abstraction over the low-level quantum operations required for entanglement generation.

## Quantum States and Operations

### EPR Pair (Entangled Pair Request)
An entangled quantum state shared between two remote nodes. The default EPR pair provided by SquidASM is in the state $\ket{\Phi^+} = \frac{1}{\sqrt{2}}(\ket{00} + \ket{11})$, also known as a Bell pair.

### Bell State
A maximally entangled state of two qubits. There are four Bell states (two qubits, two bits):
- $\ket{\Phi^+} = \frac{1}{\sqrt{2}}(\ket{00} + \ket{11})$ - Both qubits same
- $\ket{\Phi^-} = \frac{1}{\sqrt{2}}(\ket{00} - \ket{11})$ - Both qubits same, phase
- $\ket{\Psi^+} = \frac{1}{\sqrt{2}}(\ket{01} + \ket{10})$ - Qubits opposite
- $\ket{\Psi^-} = \frac{1}{\sqrt{2}}(\ket{01} - \ket{10})$ - Qubits opposite, phase

### Qubit
The quantum analog of a classical bit. Can be in a superposition of |0⟩ and |1⟩ states. In SquidASM, qubits are represented by the `Qubit` class from the NetQASM SDK.

### Measurement
The quantum operation of observing a qubit, which projects it onto either the |0⟩ or |1⟩ state. In SquidASM, measurement is done using the `measure()` method of a Qubit.

### Future Object
A placeholder for a quantum measurement result that hasn't been computed yet. Future objects behave like the actual measurement result after a `connection.flush()` but are special objects before the flush. This allows the program to queue quantum operations before they're executed.

## Network Concepts

### Stack
An end node in the quantum network. A stack is where a program runs and includes both the host and the QNPU. Each stack has a unique name used to identify it in the network configuration and in program declarations.

### Link (Quantum Link)
A quantum communication channel between two stacks, used for generating EPR pairs. Links have configurable properties such as fidelity, generation time, and success probability. SquidASM supports several link models: perfect, depolarise, and heralded.

### Clink (Classical Link)
A classical communication channel between two stacks, used for sending classical messages. Clinks can have different latency characteristics: instant (zero delay) or default (configurable delay).

### Link Fidelity
A measure of how well an EPR pair is entangled. Fidelity ranges from 0 to 1, where 1 represents a perfect EPR pair. Lower fidelity means the generated pair is more noisy/depolarized.

## Noise Models

### Decoherence
The loss of quantum information over time. Modeled in SquidASM using T1 (energy relaxation) and T2 (phase relaxation) times. A qubit in memory decoheres at a rate determined by these times.

### Depolarisation
Random Pauli errors applied during quantum operations (gates, measurements, etc.). Each operation has a probability of applying a random Pauli error, reducing the fidelity of the quantum state.

### Generic Quantum Device
An idealized quantum processor model with basic noise sources (decoherence and depolarisation) but without physical constraints. Suitable for testing protocols without realistic noise.

### NV (Nitrogen-Vacancy) Quantum Device
A realistic quantum processor model based on NV centers in diamond. Features specific gate sets, topology constraints (electron and carbon qubits with limited interactions), and physically-motivated noise parameters.

## Control Flow and Timing

### Flush
The operation of compiling queued quantum instructions into a NetQASM subroutine and sending it to the QNPU for execution. In SquidASM, this is done with `yield from connection.flush()`. Results are only available after a flush.

### Subroutine
A sequence of quantum instructions compiled into NetQASM code ready to be sent to the QNPU. A program may execute multiple subroutines throughout its execution.

### Yield From
A Python keyword used to delegate to a generator function, commonly used in SquidASM to wait for asynchronous operations like receiving messages or flushing instructions.

## Common Protocols and Operations

### Entanglement Swapping
A protocol where Alice and Bob create an EPR pair, and Alice and Charlie create another EPR pair. Alice then performs a Bell measurement on her qubits, and the results are sent to Charlie. This causes Bob and Charlie to become entangled, extending the range of entanglement without direct quantum communication.

### Quantum Key Distribution (QKD)
A protocol for generating shared secret keys between two parties using quantum mechanics. The security is guaranteed by the laws of quantum mechanics rather than computational hardness.

### Blind Quantum Computing (BQC)
A protocol where a client sends quantum instructions to a server that performs computations without learning what the computation is. The client can verify the results without revealing the input or computation details.

### Bell State Measurement (BSM)
A quantum measurement that projects two qubits onto one of the four Bell basis states. Commonly used in teleportation, entanglement swapping, and other quantum protocols.

## Simulation-Specific Terms

### num_times
The number of independent simulation iterations to run. Results are accumulated across all iterations, useful for gathering statistics.

### ProgramMeta
A metadata object declaring what resources (sockets, connections) a program requires. Must be implemented by every program through the `meta()` static method.

### ProgramContext
An object containing all the resources (sockets, connections) provided to a program at runtime. Passed to the `run()` method of every program.

### StackNetworkConfig
The configuration object specifying the entire network topology, including all stacks, quantum links, classical links, and their parameters.

### GenericQDeviceConfig
Configuration object for the generic quantum device model, including noise parameters, timing, and number of qubits.

### DepolariseLinkConfig
Configuration object for the depolarise quantum link model, including fidelity, cycle time, and success probability.

### Logging Level
The minimum severity of log messages to display. Levels in order: DEBUG, INFO, WARNING, ERROR, CRITICAL. Setting a level filters out all less severe messages.

## Unit Conventions

### Nanoseconds (ns)
The standard time unit in SquidASM. Gate durations, link delays, T1, and T2 times are all specified in nanoseconds.

### Simulation Time vs Real Time
Simulation time is the virtual time inside the quantum network simulation, measured in nanoseconds. This is distinct from real (wall-clock) time, which is how long the simulation takes to execute on your computer.

## See Also

For more detailed explanations of these concepts, refer to:
- [Architecture Overview](../architecture/overview.md) - System design and interactions
- [Foundations: NetQASM](../foundations/netqasm.md) - Quantum programming model
- [Foundations: EPR Sockets](../foundations/epr_sockets.md) - Entanglement generation
- [Foundations: Classical Communication](../foundations/classical_communication.md) - Message passing
- [API Reference](../api/index.md) - Complete API documentation
