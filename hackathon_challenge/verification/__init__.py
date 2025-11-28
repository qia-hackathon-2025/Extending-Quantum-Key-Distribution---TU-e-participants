"""Verification package for QKD key verification.

This package implements universal hash-based key verification using
polynomial hashing over GF(2^n).

Reference:
- implementation_plan.md §Phase 3
- extending_qkd_theorethical_aspects.md §3

Modules
-------
utils
    GF(2^n) field arithmetic operations.
polynomial_hash
    Polynomial hash function implementation.
verifier
    KeyVerifier class for the verification protocol.

Examples
--------
Local verification (for testing):

>>> from hackathon_challenge.verification import KeyVerifier
>>> verifier = KeyVerifier(tag_bits=64)
>>> key_a = [1, 0, 1, 1, 0, 0, 1, 0]
>>> key_b = [1, 0, 1, 1, 0, 0, 1, 0]
>>> result = verifier.verify_local(key_a, key_b)
>>> result.success
True

Network verification (in SquidASM program):

>>> # In Alice's program
>>> verifier = KeyVerifier(tag_bits=64)
>>> match = yield from verifier.verify(socket, key, is_alice=True)

>>> # In Bob's program
>>> verifier = KeyVerifier(tag_bits=64)
>>> match = yield from verifier.verify(socket, key, is_alice=False)
"""

from hackathon_challenge.verification.polynomial_hash import (
    collision_probability,
    compute_polynomial_hash,
    compute_polynomial_hash_with_length,
    generate_hash_salt,
    minimum_tag_bits_for_security,
    verify_hash,
)
from hackathon_challenge.verification.utils import (
    GF64_MODULUS,
    GF64_SIZE,
    GF128_MODULUS,
    GF128_SIZE,
    bits_to_field_elements,
    bits_to_int,
    chunk_bits,
    generate_random_field_element,
    gf_add,
    gf_multiply,
    gf_power,
    int_to_bits,
    validate_field_element,
)
from hackathon_challenge.verification.verifier import (
    KeyVerifier,
    VerificationResult,
    verify_keys_match,
)

__all__ = [
    # GF utilities
    "GF64_MODULUS",
    "GF64_SIZE",
    "GF128_MODULUS",
    "GF128_SIZE",
    "gf_multiply",
    "gf_power",
    "gf_add",
    "bits_to_int",
    "int_to_bits",
    "chunk_bits",
    "bits_to_field_elements",
    "validate_field_element",
    "generate_random_field_element",
    # Polynomial hashing
    "compute_polynomial_hash",
    "compute_polynomial_hash_with_length",
    "generate_hash_salt",
    "verify_hash",
    "collision_probability",
    "minimum_tag_bits_for_security",
    # Verifier
    "KeyVerifier",
    "VerificationResult",
    "verify_keys_match",
]
