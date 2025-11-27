# QIA Hackathon 2025: Onboarding & Challenge Guide

Welcome to the QIA Hackathon 2025! This document serves as the primary entry point for team members working on the **Quantum Key Distribution (QKD)** and **Quantum Key Infrastructure (QKI)** challenges.

## 1. The Framework: SquidASM

**SquidASM** is the simulation framework we will be using. It allows us to simulate quantum networks, running applications that utilize quantum functionality (like entanglement generation and teleportation) on top of a simulated physical layer.

### Key Components
*   **Application Layer**: Python code that defines what Alice, Bob, and other nodes do. This is where we will work.
*   **NetQASM**: The low-level instruction set for quantum networks. SquidASM compiles our high-level Python commands into NetQASM instructions.
*   **Simulation Backend**: Simulates the physical qubits, fiber optics, and noise.

### Important Directories
*   `squidasm/squidasm/`: The core source code of the framework.
    *   `run/`: Components for running simulations.
    *   `sim/`: The simulation logic (network stack, quantum nodes).
*   `squidasm/examples/`: Example applications. Including **QKD** basic implementation

---

## 2. The Main Challenge: Extending QKD

**Goal:** Enhance an existing, basic implementation of the BB84 QKD protocol to make it secure and realistic.

The current implementation performs the quantum transmission (sending photons) and basis sifting (discarding mismatched bases). However, it lacks the crucial post-processing steps that make the key secure against errors and eavesdroppers.

### Your Tasks
1.  **Key Reconciliation**: Implement a protocol (like **Cascade**) to correct errors in the raw key so Alice and Bob share identical keys.
    *   *Theory:* Parity checks, binary search for errors, backtracking.
2.  **Verification**: Use hashing (e.g., Universal Hashing) to verify the keys are identical.
3.  **Privacy Amplification**: "Shrink" the key to remove information an eavesdropper might have gained during transmission or reconciliation.
4.  **Authentication**: Ensure the classical public channel used for reconciliation is authenticated.

### Relevant Documentation
*   **Challenge Description**: `qia-hackathon-2025/docs/challenges/qkd/extending_qkd_implementation.md`
*   **Theoretical Guide**: `qia-hackathon-2025/docs/challenges/qkd/extending_qkd_theorethical_aspects.md` (Contains math and algorithm details for Cascade and Hashing).

### Starting Point
*   Example implementation: `squidasm/examples/applications/qkd/`
    *   Look for the files defining Alice and Bob's program.
    *   Identify where the "Sifting" ends and where "Reconciliation" should begin.
*   Codebase: `qia-hackathon-2025/hackathon_challenge`

    *   all code relevant to the challenge should be developed here.
---

## 3. The Extended Challenge: QKI Network

**Goal:** Move beyond a single link (Alice-Bob) to a **Trusted Node Network**.

In the real world, quantum signals degrade over distance. To build a large network, we use intermediate nodes that decrypt and re-encrypt keys. This transforms the problem from pure physics to **Distributed Systems** and **Network Engineering**.

### Your Tasks
1.  **Key Management System (KMS)**: Create a system to track keys (IDs, status, peer) at each node.
2.  **Trusted Node Routing**: Implement "hop-by-hop" key forwarding.
    *   *Scenario:* Alice wants to send a key to Charlie via Bob.
    *   *Mechanism:* Alice $\to$ Bob (encrypt with $K_{AB}$), Bob $\to$ Charlie (decrypt, re-encrypt with $K_{BC}$).
3.  **Resource Management**: Handle "Key Exhaustion". If the QKD link is too slow, the application must wait.

### Relevant Documentation
*   **QKI Challenge**: `qia-hackathon-2025/docs/challenges/qkd/qki_challenge.md`

---

## 4. Workspace Navigation Map

A quick reference to where files are located in this workspace:

| Path | Description |
| :--- | :--- |
| `qia-hackathon-2025/docs/` | **Documentation Hub**. Start here. |
| `qia-hackathon-2025/docs/challenges/qkd/` | Specific docs for our track. |
| `squidasm/` | The simulator repository. |
| `squidasm/examples/applications/qkd/` | **Example**. The existing QKD implementation we must modify. |
| `squidasm/squidasm/` | Internal simulator code (reference only, usually). |
| `qia-hackathon-2025/hackathon_challenge/` | **Codebase**, all code relevant for the challenge must be implemented here |