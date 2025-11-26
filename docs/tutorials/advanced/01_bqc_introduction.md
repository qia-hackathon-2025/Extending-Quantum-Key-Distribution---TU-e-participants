# Tutorial 1: Blind Quantum Computation - Introduction

This tutorial introduces the theoretical foundations of Blind Quantum Computation (BQC), a cryptographic protocol that enables a client with limited quantum capabilities to delegate computation to a powerful quantum server while keeping the computation private.

## Overview

**Blind Quantum Computation** addresses a fundamental problem in quantum computing: How can a user with minimal quantum resources perform quantum computations using a powerful remote quantum computer, without revealing what computation is being performed?

## The Problem

Consider this scenario:
- **Alice (Client)**: Has limited quantum hardware (can only prepare single qubits and measure)
- **Bob (Server)**: Has a powerful quantum computer with multi-qubit operations
- **Goal**: Alice wants Bob to perform a quantum computation without Bob learning:
  - What the computation is
  - What the inputs are
  - What the outputs are

## Theoretical Background

### Measurement-Based Quantum Computing (MBQC)

BQC is built on the **Measurement-Based Quantum Computing** model, where computation proceeds as follows:

1. **Prepare**: Create a highly entangled resource state (cluster state)
2. **Compute**: Perform single-qubit measurements in specific bases
3. **Correct**: Apply classical corrections based on measurement outcomes

The key insight is that the choice of measurement bases encodes the computation.

#### Cluster State

A 1D cluster state on $n$ qubits:

$$|\text{cluster}\rangle = \prod_{i=1}^{n-1} CZ_{i,i+1} |+\rangle^{\otimes n}$$

Where $|+\rangle = \frac{1}{\sqrt{2}}(|0\rangle + |1\rangle)$ and $CZ$ is the controlled-Z gate.

### Remote State Preparation (RSP)

RSP allows Alice to prepare a quantum state on Bob's device using entanglement:

1. Alice and Bob share an EPR pair: $|\Phi^+\rangle = \frac{1}{\sqrt{2}}(|00\rangle + |11\rangle)$
2. Alice measures her qubit in a rotated basis
3. Bob's qubit collapses to a corresponding state

**Protocol**:
```
Alice                          Bob
  |                              |
  |←─── EPR pair (|Φ+⟩) ────────→|
  |                              |
  | Measure in basis             | Has state |ψ⟩
  | Z(θ)|+⟩                      | = Z(θ + mπ)|+⟩
  |                              |
```

The measurement outcome $m \in \{0, 1\}$ introduces a phase flip that Alice knows but can compensate for later.

### The BQC Protocol

The BQC protocol combines RSP with MBQC:

1. **State Preparation**: Alice uses RSP to prepare rotated states on Bob's device
2. **Entanglement**: Bob creates the cluster state by applying CZ gates
3. **Measurement**: Bob measures in bases Alice specifies (with hidden offsets)
4. **Classical Processing**: Alice processes outcomes, hidden behind random offsets

## The Effective Computation

In this example, the **Effective Computation (EC)** is:

$$\text{EC} = H \cdot R_z(\beta) \cdot H \cdot R_z(\alpha) |+\rangle$$

Followed by measurement in the Z-basis.

This is equivalent to preparing the state:

$$Z^{m_1} H R_z(\beta) H R_z(\alpha) |+\rangle$$

where $m_1$ is an intermediate measurement outcome.

### Circuit Representation

```
|+⟩ ─── Rz(α) ─── H ─── Rz(β) ─── H ─── M ───→ m₂
```

The final measurement outcome $m_2$ depends on $\alpha$ and $\beta$.

## BQC Protocol Diagram

```
Client (Alice)                     Server (Bob)
     │                                  │
     │     EPR pair 1                   │
     │◄────────────────────────────────►│
     │                                  │
     │  Measure: Rz(θ₂)H, get p₂       │  Has: Z^p₂·Rz(θ₂)|+⟩
     │                                  │
     │     EPR pair 2                   │
     │◄────────────────────────────────►│
     │                                  │
     │  Measure: Rz(θ₁)H, get p₁       │  Has: Z^p₁·Rz(θ₁)|+⟩
     │                                  │
     │                                  │  Apply CZ between qubits
     │                                  │
     │  Compute δ₁ = α - θ₁ + (p₁+r₁)π │
     │─────────────────────────────────►│
     │                                  │  Measure in basis δ₁
     │◄─────────────────────────────────│  Send m₁
     │                                  │
     │  Compute δ₂ based on m₁          │
     │─────────────────────────────────►│
     │                                  │  Measure in basis δ₂
     │                                  │  Get m₂ = EC result
     │                                  │
```

## Security Analysis

### Why is it Blind?

Bob sees:
- Random states from RSP (hidden by θ values)
- Measurement angles (hidden by θ offsets and random r values)
- Measurement outcomes (uniformly random due to θ)

Bob cannot determine:
- The actual computation (α, β are hidden)
- Input or output values

### Trap Rounds

To verify Bob's honesty, Alice can run **trap rounds**:

1. Alice prepares a "dummy" state (not used in computation)
2. If Bob is honest, measurement outcomes must satisfy certain correlations
3. Deviation indicates cheating

## Protocol Parameters

| Parameter | Description | Range |
|-----------|-------------|-------|
| α | First rotation angle | [0, 2π) |
| β | Second rotation angle | [0, 2π) |
| θ₁ | Random hiding angle 1 | {0, π/4, π/2, ..., 7π/4} |
| θ₂ | Random hiding angle 2 | {0, π/4, π/2, ..., 7π/4} |
| r₁ | Random bit for extra hiding | {0, 1} |
| r₂ | Random bit for extra hiding | {0, 1} |

## Expected Measurement Statistics

For the effective computation with different (α, β):

| α | β | P(m₂ = 0) | P(m₂ = 1) |
|---|---|-----------|-----------|
| 0 | 0 | 1.0 | 0.0 |
| π | 0 | 0.0 | 1.0 |
| π/2 | 0 | 0.5 | 0.5 |
| π/2 | π/2 | 0.0 | 1.0 |

## Mathematical Details

### State Evolution

Starting state: $|+\rangle$

After $R_z(\alpha)$:
$$R_z(\alpha)|+\rangle = \frac{1}{\sqrt{2}}(|0\rangle + e^{i\alpha}|1\rangle)$$

After $H$:
$$H \cdot R_z(\alpha)|+\rangle = \cos(\alpha/2)|0\rangle + i\sin(\alpha/2)|1\rangle$$

The full computation gives:
$$|\psi\rangle = H R_z(\beta) H R_z(\alpha) |+\rangle$$

### Measurement Probability

The probability of measuring 0:
$$P(0) = |\langle 0|\psi\rangle|^2$$

This depends on α and β in a complex way that defines the computation.

## Next Steps

In the [next tutorial](02_bqc_implementation.md), we'll implement this protocol in SquidASM, showing:
- Client and Server program structure
- EPR pair creation and measurement
- Classical communication for measurement angles
- Computation and trap round execution

## References

1. Broadbent, A., Fitzsimons, J., & Kashefi, E. (2009). "Universal Blind Quantum Computation"
2. Fitzsimons, J. (2017). "Private quantum computation: an introduction to blind quantum computing"
3. Raussendorf, R., & Briegel, H. J. (2001). "A One-Way Quantum Computer"

## See Also

- [BQC Implementation](02_bqc_implementation.md) - Code implementation
- [NetQASM Foundations](../../foundations/netqasm.md) - Programming model
- [EPR Sockets](../../foundations/epr_sockets.md) - Entanglement generation
