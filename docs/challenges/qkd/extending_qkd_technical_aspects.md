# Technical Design: Extending QKD Implementation

This document outlines the technical architecture and implementation details for extending the basic BB84 QKD protocol in SquidASM. It translates the theoretical requirements into concrete Python classes, data structures, and SquidASM API calls.

## 1. Architecture Overview

The solution should be modular, separating the core QKD logic (state distribution) from the classical post-processing steps. We will extend the existing `QkdProgram` structure and introduce helper classes for each stage of the post-processing pipeline.

### Module Structure
```python
# Proposed file structure
hackathon_challenge/
├── protocol.py          # Main Alice/Bob programs (extends QkdProgram)
├── reconciliation.py    # Cascade protocol implementation
├── privacy.py           # Privacy amplification (Toeplitz)
├── auth.py              # Authenticated socket wrapper
└── util.py              # Hashing and math utilities
```

## 2. Classical Communication & Authentication

The challenge requires authenticated public channels. In SquidASM, classical communication is handled via `ClassicalSocket`. We will implement a wrapper class `AuthenticatedSocket` that transparently handles message signing and verification using HMAC.

### 2.1. AuthenticatedSocket Wrapper

This class wraps a standard `ClassicalSocket` and a shared secret key (simulating the pre-shared key required for QKD).

**Key Components:**
*   **HMAC-SHA256**: Used for message integrity and authenticity.
*   **Serialization**: Messages must be deterministically serialized before signing.

```python
import hmac
import hashlib
import pickle
from squidasm.sim.stack.csocket import ClassicalSocket

class AuthenticatedSocket:
    def __init__(self, socket: ClassicalSocket, key: bytes):
        self.socket = socket
        self.key = key

    def send_structured(self, msg: StructuredMessage):
        # 1. Serialize payload
        payload_bytes = pickle.dumps(msg.payload)
        
        # 2. Compute HMAC
        signature = hmac.new(self.key, payload_bytes, hashlib.sha256).digest()
        
        # 3. Wrap in a container message
        # We send a tuple: (original_msg, signature)
        envelope = StructuredMessage(msg.header, (msg.payload, signature))
        self.socket.send_structured(envelope)

    def recv_structured(self) -> Generator[EventExpression, None, StructuredMessage]:
        # 1. Receive envelope
        envelope = yield from self.socket.recv_structured()
        payload, signature = envelope.payload
        
        # 2. Verify HMAC
        payload_bytes = pickle.dumps(payload)
        expected_signature = hmac.new(self.key, payload_bytes, hashlib.sha256).digest()
        
        if not hmac.compare_digest(signature, expected_signature):
            raise SecurityError("Authentication failed: Invalid signature")
            
        # 3. Return original message structure
        return StructuredMessage(envelope.header, payload)
```

**Integration:**
In `AliceProgram` and `BobProgram`, replace direct `csocket` usage with `AuthenticatedSocket`.

## 3. Step 1: Key Reconciliation (Cascade Protocol)

We will implement the **Cascade** protocol. This requires an interactive exchange of parity bits.

### 3.1. Data Structures
We need efficient bit manipulation. `numpy.array` (dtype=uint8) or Python's `bitarray` (if available) are suitable. Given the environment, `numpy` is preferred.

```python
import numpy as np

@dataclass
class CascadeBlock:
    indices: List[int]  # Indices of bits in this block
    parity: int         # 0 or 1
```

### 3.2. The `CascadeReconciliator` Class

This class manages the state of the reconciliation process.

**Methods:**
*   `run_pass(pass_index, block_size)`: Executes one pass of Cascade.
*   `binary_search(block_indices)`: The BINARY primitive to locate errors.
*   `compute_parity(indices)`: Helper to XOR bits at given indices.

**Protocol Flow (Alice):**
1.  **Shuffle**: Apply permutation for the current pass (using a seeded RNG so Bob matches).
2.  **Partition**: Split key into blocks of size $k$.
3.  **Send Parities**: Compute parity for each block and send list to Bob.
4.  **Handle Corrections**: Wait for Bob to report error locations (if any) found via Binary Search.
5.  **Backtrack**: If a bit flips, check previous passes for newly exposed odd parities.

**Protocol Flow (Bob):**
1.  **Shuffle & Partition**: Match Alice's permutation and blocking.
2.  **Receive Parities**: Get Alice's parity map.
3.  **Compare**: Compute local parities. Identify blocks with mismatch.
4.  **Binary Search**: For each mismatching block, interactively narrow down the error.
    *   *SquidASM Note*: This involves a loop of `send`/`yield from recv` calls inside the `binary_search` method.
5.  **Correct**: Flip the erroneous bit.
6.  **Backtrack**: Recursively fix errors in previous passes.

### 3.3. SquidASM Implementation Details

The `binary_search` is the most communication-intensive part.

```python
def binary_search_alice(self, socket, indices):
    # Recursive or iterative bisection
    current_indices = indices
    while len(current_indices) > 1:
        # Split
        mid = len(current_indices) // 2
        left_half = current_indices[:mid]
        
        # Send parity of left half
        p_left = self.compute_parity(left_half)
        socket.send_structured(StructuredMessage("BinaryParity", p_left))
        
        # Wait for Bob to tell us which half has the error
        # (In optimized Cascade, Bob drives this, Alice just answers)
        direction = (yield from socket.recv_structured()).payload
        
        if direction == 'LEFT':
            current_indices = left_half
        else:
            current_indices = current_indices[mid:]
```

**Optimization**: To reduce round-trips, Bob should drive the search. Alice sends the top-level parities. Bob detects a mismatch. Bob then asks Alice "Give me parity of first half of block X". Alice replies. Bob decides to go left or right.

## 4. Step 2: Verification (Polynomial Hashing)

After Cascade, we verify $K_A = K_B$ using polynomial hashing over a Galois Field or a large prime field.

### 4.1. Implementation Strategy
We can treat the key bits as coefficients of a polynomial $P(x)$ and evaluate it at a random point $x$.

**Math:**
$H(K) = \sum_{i=0}^{n-1} k_i \cdot x^i \pmod p$

Where $p$ is a large prime (e.g., $2^{127}-1$, a Mersenne prime) to ensure collision resistance.

```python
def poly_hash(key_bits: np.ndarray, x: int, prime: int) -> int:
    # Horner's method for polynomial evaluation
    h = 0
    for bit in reversed(key_bits):
        h = (h * x + int(bit)) % prime
    return h
```

**Protocol:**
1.  Alice generates a random $x$ and a random salt.
2.  Alice computes $h_A = \text{poly\_hash}(K_A, x, p)$.
3.  Alice sends $(x, h_A)$ to Bob (Authenticated!).
4.  Bob computes $h_B = \text{poly\_hash}(K_B, x, p)$.
5.  Bob verifies $h_A == h_B$.

## 5. Step 3: Privacy Amplification (Toeplitz Matrix)

We reduce the key length to eliminate Eve's partial information.

### 5.1. Calculating Safe Key Length
Using the formula from the theoretical docs:
$$ \ell_{sec} = n_{sift} [ 1 - h(QBER) - leak_{EC} ] - \text{safety\_margin} $$

*   $h(p)$: Binary entropy function.
*   $leak_{EC}$: Total bits exchanged during Cascade (parities + binary search steps).

### 5.2. Toeplitz Matrix Multiplication
We need to multiply a binary matrix $T$ ($\ell_{sec} \times n_{old}$) by the key vector $K_{old}$.

**Efficient Construction:**
A Toeplitz matrix is defined by its first row and first column.
$T_{i,j} = v_{i-j}$ for a vector $v$.

We can use `scipy.linalg.toeplitz` to construct it, but for large keys, full matrix multiplication is slow ($O(N^2)$).
*   **Hackathon Scope**: Since key sizes are likely small (< 10,000 bits), standard matrix multiplication using `numpy` is acceptable.
*   **Optimization**: Use `scipy.signal.fftconvolve` for $O(N \log N)$ multiplication if needed, but `np.matmul` modulo 2 is sufficient here.

```python
from scipy.linalg import toeplitz

def privacy_amplify(key: np.ndarray, seed: np.ndarray, new_length: int) -> np.ndarray:
    old_length = len(key)
    
    # Construct Toeplitz matrix from seed
    # Seed length must be old_length + new_length - 1
    col = seed[:new_length]
    row = seed[new_length-1:]
    
    T = toeplitz(col, row)
    
    # Matrix multiplication over GF(2)
    # T is (new_len, old_len), key is (old_len, 1)
    res = np.matmul(T, key) % 2
    return res.astype(int)
```

## 6. Integration Plan

### Phase 1: Setup
1.  Modify `AliceProgram` and `BobProgram` to accept a `shared_secret` in `__init__`.
2.  Wrap sockets with `AuthenticatedSocket`.

### Phase 2: Reconciliation
1.  After `_estimate_error_rate`, do not return `raw_key` immediately.
2.  Instantiate `CascadeReconciliator`.
3.  Run `reconcile(raw_key, estimated_qber)`.
4.  Track `bits_revealed` counter.

### Phase 3: Verification & Amplification
1.  Run `verify_keys()`. If fail -> Abort.
2.  Calculate `final_length` based on `bits_revealed` and `QBER`.
3.  Run `privacy_amplify()`.
4.  Return `final_secret_key`.

## 7. SquidASM Specific Considerations

*   **Yielding**: Every socket operation (`send`, `recv`) inside the helper classes must be properly yielded in the main `run` generator.
    *   *Pattern*: The helper methods should be generators (`def func(...) -> Generator...`).
    *   *Usage*: `result = yield from helper.func(...)`.
*   **Logging**: Use `LogManager` to trace the protocol steps, especially QBER and verification results.
*   **Simulation Config**: Ensure the `link_noise` in the simulation configuration is high enough to test Cascade (e.g., 0.05) but lower than the abort threshold (0.11).
