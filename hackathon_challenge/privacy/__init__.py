"""Privacy amplification module for QKD post-processing.

This module provides components for the privacy amplification step in QKD,
which transforms a reconciled key (with potential information leakage to Eve)
into a shorter but cryptographically secure key.

Key Components
--------------
Entropy Functions (entropy.py):
    - binary_entropy: Binary entropy function h(p)
    - inverse_binary_entropy: Inverse of binary entropy
    - secrecy_capacity: Compute secrecy capacity 1 - h(QBER)
    - is_qber_secure: Check if QBER is below security threshold
    - compute_final_key_length: Devetak-Winter formula for final key length
    - compute_final_key_length_detailed: Detailed key length with breakdown

QBER Estimation (estimation.py):
    - estimate_qber_from_sample: Estimate QBER from bit comparison
    - estimate_qber_from_cascade: Estimate QBER from Cascade reconciliation data
    - estimate_qber_detailed: Detailed estimation with confidence intervals
    - compute_confidence_interval: Clopper-Pearson confidence interval
    - is_qber_acceptable: Check if QBER is acceptable

Toeplitz Utilities (utils.py):
    - generate_toeplitz_seed: Generate random seed for Toeplitz matrix
    - generate_toeplitz_seed_structured: Generate seed with metadata
    - validate_toeplitz_seed: Validate seed length and format
    - construct_toeplitz_matrix: Build Toeplitz matrix from seed
    - compute_seed_length: Calculate required seed length

Privacy Amplifier (amplifier.py):
    - PrivacyAmplifier: Main class for privacy amplification
    - apply_privacy_amplification: Convenience function for amplification
    - AmplificationResult: Result dataclass with full metadata

Example
-------
>>> from hackathon_challenge.privacy import (
...     PrivacyAmplifier,
...     compute_final_key_length,
...     estimate_qber_from_cascade,
... )
>>> # Estimate QBER from reconciliation data
>>> qber = estimate_qber_from_cascade(10000, 50, 450)  # 5%
>>> # Compute expected key length
>>> key_length = compute_final_key_length(10000, qber, 500, 64)
>>> # Apply privacy amplification
>>> amplifier = PrivacyAmplifier()
>>> result = amplifier.amplify_with_result(key, qber, 500, 64)

Reference
---------
- implementation_plan.md §Phase 4
- extending_qkd_theorethical_aspects.md §3, §4
"""

# Entropy functions
from hackathon_challenge.privacy.entropy import (
    DEFAULT_EPSILON_SEC,
    QBER_THRESHOLD,
    KeyLengthEstimate,
    binary_entropy,
    binary_entropy_derivative,
    compute_final_key_length,
    compute_final_key_length_detailed,
    compute_security_margin,
    inverse_binary_entropy,
    is_qber_secure,
    secrecy_capacity,
)

# QBER estimation functions
from hackathon_challenge.privacy.estimation import (
    DEFAULT_CONFIDENCE,
    QBEREstimate,
    compute_confidence_interval,
    compute_optimal_sample_size,
    count_sample_errors,
    estimate_qber_detailed,
    estimate_qber_from_cascade,
    estimate_qber_from_sample,
    estimate_qber_with_correction,
    is_qber_acceptable,
)

# Toeplitz utilities
from hackathon_challenge.privacy.utils import (
    ToeplitzSeed,
    bits_to_bytes,
    bytes_to_bits,
    compute_seed_length,
    construct_toeplitz_matrix,
    construct_toeplitz_matrix_numpy,
    extract_toeplitz_components,
    generate_toeplitz_seed,
    generate_toeplitz_seed_structured,
    toeplitz_multiply,
    validate_toeplitz_seed,
)

# Privacy amplifier
from hackathon_challenge.privacy.amplifier import (
    MSG_PA_COMPLETE,
    MSG_PA_SEED,
    AmplificationResult,
    PrivacyAmplifier,
    apply_privacy_amplification,
)


__all__ = [
    # Constants
    "DEFAULT_EPSILON_SEC",
    "DEFAULT_CONFIDENCE",
    "QBER_THRESHOLD",
    "MSG_PA_SEED",
    "MSG_PA_COMPLETE",
    # Dataclasses
    "KeyLengthEstimate",
    "QBEREstimate",
    "ToeplitzSeed",
    "AmplificationResult",
    # Entropy functions
    "binary_entropy",
    "binary_entropy_derivative",
    "inverse_binary_entropy",
    "secrecy_capacity",
    "is_qber_secure",
    "compute_security_margin",
    "compute_final_key_length",
    "compute_final_key_length_detailed",
    # QBER estimation
    "estimate_qber_from_sample",
    "count_sample_errors",
    "estimate_qber_from_cascade",
    "estimate_qber_detailed",
    "compute_confidence_interval",
    "is_qber_acceptable",
    "estimate_qber_with_correction",
    "compute_optimal_sample_size",
    # Toeplitz utilities
    "compute_seed_length",
    "generate_toeplitz_seed",
    "generate_toeplitz_seed_structured",
    "validate_toeplitz_seed",
    "construct_toeplitz_matrix",
    "construct_toeplitz_matrix_numpy",
    "toeplitz_multiply",
    "extract_toeplitz_components",
    "bits_to_bytes",
    "bytes_to_bits",
    # Privacy amplifier
    "PrivacyAmplifier",
    "apply_privacy_amplification",
]
