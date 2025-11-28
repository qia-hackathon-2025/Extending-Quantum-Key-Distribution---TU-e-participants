# QKD Extension: Technical Implementation

This module implements an extended Quantum Key Distribution (QKD) protocol based on the BB84 scheme, incorporating post-processing stages required for practical key generation with information-theoretic security guarantees.

For theoretical background, see [Theoretical Aspects](../docs/challenges/qkd/extending_qkd_theorethical_aspects.md).

## Architecture Overview

The implementation follows a modular design with clear separation of concerns. Each component corresponds to a stage in the QKD post-processing pipeline.

```
hackathon_challenge/
├── core/              # Protocol orchestration
├── auth/              # Authentication layer
├── reconciliation/    # Error correction (Cascade)
├── verification/      # Key verification (Polynomial hashing)
├── privacy/           # Privacy amplification (Toeplitz hashing)
├── configs/           # YAML configuration files
├── scripts/           # Execution and analysis scripts
├── tests/             # Unit and integration tests
├── utils/             # Logging and result utilities
└── results/           # Simulation output files
```

## Core Components

### core/ - Protocol Orchestration

The main QKD protocol implementation integrating all post-processing stages.

| File | Description |
|:-----|:------------|
| `protocol.py` | `AliceProgram` and `BobProgram` classes extending SquidASM's `Program`. Implements the complete BB84 pipeline: EPR distribution, basis sifting, QBER estimation, reconciliation, verification, and privacy amplification. |
| `base.py` | Base classes and `QKDResult` dataclass for protocol state management. |
| `constants.py` | Protocol constants including `QBER_THRESHOLD` (0.11), `SECURITY_PARAMETER`, and message identifiers. |

### auth/ - Authentication Layer

Provides information-theoretically secure message authentication.

| File | Description |
|:-----|:------------|
| `socket.py` | `AuthenticatedSocket` wrapper around SquidASM's `Socket`. Adds HMAC tags to all transmitted messages using a pre-shared key. |
| `wegman_carter.py` | Wegman-Carter MAC implementation using polynomial evaluation over GF(2^128). |
| `exceptions.py` | Authentication-specific exception classes (`AuthenticationError`, `TagMismatchError`). |

### reconciliation/ - Error Correction

Implements the Cascade protocol for interactive information reconciliation.

| File | Description |
|:-----|:------------|
| `cascade.py` | Full Cascade implementation with configurable passes and backtracking. |
| `simple_cascade.py` | `SimpleCascadeReconciliator` - lightweight Cascade variant for typical QBER scenarios. |
| `binary_search.py` | The BINARY primitive for locating single-bit errors via recursive bisection. Complexity: O(log k) bits disclosed per error. |
| `history.py` | `PassHistory` dataclass for tracking block parities across passes (enables backtracking). |
| `utils.py` | Block permutation and parity computation utilities. |

### verification/ - Key Verification

Universal hash-based verification to confirm key equality after reconciliation.

| File | Description |
|:-----|:------------|
| `verifier.py` | `KeyVerifier` class orchestrating the verification protocol between Alice and Bob. |
| `polynomial_hash.py` | Polynomial evaluation over GF(2^n) for universal hashing. Collision probability bounded by L/q (Schwartz-Zippel). |
| `utils.py` | GF(2^n) arithmetic utilities. |

### privacy/ - Privacy Amplification

Extracts a shorter, secure key from the reconciled key using Toeplitz hashing.

| File | Description |
|:-----|:------------|
| `amplifier.py` | `PrivacyAmplifier` implementing Toeplitz matrix multiplication for 2-universal hashing. |
| `entropy.py` | `compute_final_key_length()` based on QBER, leakage, and security parameter. Implements the Shor-Preskill bound. |
| `estimation.py` | QBER estimation from Cascade correction statistics. |
| `utils.py` | Toeplitz seed generation and matrix construction. |

## Protocol Flow

The complete QKD protocol executes in the following stages:

1. **Quantum Phase**: Alice and Bob generate EPR pairs and measure in random bases (Z or X).
2. **Basis Sifting**: Parties exchange basis choices and discard mismatched measurements.
3. **QBER Estimation**: A subset of sifted bits is compared to estimate the quantum bit error rate.
4. **Cascade Reconciliation**: Interactive error correction using multi-pass parity checks with backtracking.
5. **Hash Verification**: Polynomial hashing confirms key equality (collision probability < 2^-64).
6. **Privacy Amplification**: Toeplitz hashing compresses the key, removing Eve's information.

If QBER exceeds the threshold (11% for BB84), the protocol aborts.

## Configuration

Configuration is managed through YAML files in `configs/`.

### Base Configuration (configs/base.yaml)

Defines default parameters inherited by all scenarios:

```yaml
simulation:
  num_runs: 5
  log_level: "WARNING"
  output_format: "both"  # json, csv, or both

epr:
  num_pairs: 500
  num_test_bits: null    # Auto: num_pairs // 4

cascade:
  seed: 42
  num_passes: 4
  initial_block_size: null  # Auto-computed from QBER

thresholds:
  qber_abort: 0.11
  min_key_length: 50
```

### Scenario Configurations (configs/scenarios/)

Scenario-specific overrides for different experimental conditions:

| Scenario | Description |
|:---------|:------------|
| `low_noise.yaml` | QBER approximately 2%, typical fiber channel |
| `medium_noise.yaml` | QBER approximately 5%, standard test conditions |
| `high_noise.yaml` | QBER approximately 10%, near abort threshold |
| `threshold_test.yaml` | QBER approximately 11%, boundary condition testing |
| `quick_test.yaml` | Minimal parameters for rapid validation |

## Dependencies

The implementation requires:

- `squidasm >= 0.11.0` - Quantum network simulation
- `netqasm >= 0.14.0` - Quantum assembly abstraction
- `numpy >= 1.23.0` - Numerical operations
- `scipy >= 1.9.0` - Scientific computing
- `pyyaml >= 6.0` - Configuration parsing

## Testing

Unit tests are located in `tests/` and can be executed with pytest:

```bash
pytest hackathon_challenge/tests/ -v
pytest --cov=hackathon_challenge --cov-report=html
```

## References

- Brassard, G., and Salvail, L. (1994). Secret-Key Reconciliation by Public Discussion.
- Shor, P. W., and Preskill, J. (2000). Simple Proof of Security of the BB84 Quantum Key Distribution Protocol.
- Krawczyk, H. (1994). LFSR-based Hashing and Authentication.
