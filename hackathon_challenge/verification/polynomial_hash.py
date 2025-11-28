"""Polynomial hashing over finite fields.

This module implements universal polynomial hashing over GF(2^n) for
key verification in QKD protocols.

Reference:
- implementation_plan.md §Phase 3
- extending_qkd_theorethical_aspects.md §3.2 (Polynomial Hashing)

Notes
-----
The polynomial hash function is defined as:
    H_r(K) = Σ_{i=1}^L m_i * r^{L-i+1} mod p

where:
- K = (m_1, m_2, ..., m_L) is the key split into field elements
- r is a random evaluation point (salt)
- p is the field modulus (implicit in GF(2^n))

This is an ε-almost universal hash family with collision probability:
    P[H_r(K_A) = H_r(K_B) | K_A ≠ K_B] ≤ L / |F|

where |F| = 2^n is the field size.
"""

from typing import List, Optional

import numpy as np

from hackathon_challenge.verification.utils import (
    GF64_SIZE,
    GF128_SIZE,
    bits_to_field_elements,
    bits_to_int,
    gf_add,
    gf_multiply,
    gf_power,
    generate_random_field_element,
)


def compute_polynomial_hash(
    key: List[int],
    salt: int,
    field_bits: int = 64,
    element_bits: Optional[int] = None,
) -> int:
    """Compute polynomial hash over GF(2^n).

    Parameters
    ----------
    key : List[int]
        Key bits to hash (list of 0s and 1s).
    salt : int
        Random salt (evaluation point r). Must be non-zero.
    field_bits : int, optional
        Field size for arithmetic (default 64 for GF(2^64)).
    element_bits : int, optional
        Bits per field element. Defaults to field_bits.

    Returns
    -------
    int
        Hash tag in GF(2^n).

    Raises
    ------
    ValueError
        If key is empty or salt is zero.

    Notes
    -----
    Implements the polynomial evaluation:
        H_r(K) = m_1 * r^L + m_2 * r^{L-1} + ... + m_L * r^1

    Using Horner's method for efficient evaluation:
        H_r(K) = r * (r * (r * m_1 + m_2) + m_3) + ... + m_L)

    This reduces the number of multiplications from O(L^2) to O(L).

    Examples
    --------
    >>> key = [1, 0, 1, 1, 0, 0, 1, 0]
    >>> salt = 0x12345678
    >>> tag = compute_polynomial_hash(key, salt, field_bits=64)
    """
    if not key:
        raise ValueError("Key cannot be empty")
    if salt == 0:
        raise ValueError("Salt must be non-zero")

    if element_bits is None:
        element_bits = field_bits

    # Convert key bits to field elements
    elements = bits_to_field_elements(key, element_bits)

    if not elements:
        return 0

    # Use Horner's method for polynomial evaluation
    # H = m_1 * r^L + m_2 * r^{L-1} + ... + m_L * r
    # Horner: H = r * (r * (... r * (r * m_1 + m_2) + m_3) ...) + m_L)
    result = elements[0]

    for i in range(1, len(elements)):
        # result = result * r + m_i
        result = gf_multiply(result, salt, field_bits)
        result = gf_add(result, elements[i])

    # Final multiplication by r (to ensure r^1 minimum power)
    result = gf_multiply(result, salt, field_bits)

    return result


def compute_polynomial_hash_with_length(
    key: List[int],
    salt: int,
    field_bits: int = 64,
    element_bits: Optional[int] = None,
) -> int:
    """Compute polynomial hash with length encoding for security.

    Parameters
    ----------
    key : List[int]
        Key bits to hash.
    salt : int
        Random salt (evaluation point).
    field_bits : int, optional
        Field size for arithmetic (default 64).
    element_bits : int, optional
        Bits per field element. Defaults to field_bits.

    Returns
    -------
    int
        Hash tag including length encoding.

    Notes
    -----
    This variant appends the key length as an additional field element,
    providing protection against length-extension attacks. The formula is:
        H_r(K) = m_1 * r^{L+1} + m_2 * r^L + ... + m_L * r^2 + |K| * r

    For fixed-length QKD blocks this may be omitted, but it's good practice.
    """
    if not key:
        raise ValueError("Key cannot be empty")
    if salt == 0:
        raise ValueError("Salt must be non-zero")

    if element_bits is None:
        element_bits = field_bits

    # Convert key bits to field elements
    elements = bits_to_field_elements(key, element_bits)

    # Append length as final element (mod field size to ensure it fits)
    key_length = len(key) & ((1 << element_bits) - 1)
    elements.append(key_length)

    # Use Horner's method
    result = elements[0]
    for i in range(1, len(elements)):
        result = gf_multiply(result, salt, field_bits)
        result = gf_add(result, elements[i])

    # Final multiplication by r
    result = gf_multiply(result, salt, field_bits)

    return result


def generate_hash_salt(
    field_bits: int = 64, rng: Optional[np.random.Generator] = None
) -> int:
    """Generate a random salt for polynomial hashing.

    Parameters
    ----------
    field_bits : int, optional
        Field size in bits (default 64).
    rng : np.random.Generator, optional
        Random number generator. Uses default if None.

    Returns
    -------
    int
        Random non-zero salt suitable for use with compute_polynomial_hash.
    """
    return generate_random_field_element(field_bits, rng)


def verify_hash(
    key: List[int],
    salt: int,
    expected_tag: int,
    field_bits: int = 64,
    element_bits: Optional[int] = None,
) -> bool:
    """Verify a polynomial hash tag.

    Parameters
    ----------
    key : List[int]
        Key bits to verify.
    salt : int
        Salt used for original hash.
    expected_tag : int
        Expected hash tag.
    field_bits : int, optional
        Field size (default 64).
    element_bits : int, optional
        Bits per field element.

    Returns
    -------
    bool
        True if computed hash matches expected tag.
    """
    computed_tag = compute_polynomial_hash(key, salt, field_bits, element_bits)
    return computed_tag == expected_tag


def collision_probability(key_length: int, field_bits: int = 64) -> float:
    """Calculate the theoretical collision probability.

    Parameters
    ----------
    key_length : int
        Length of key in bits.
    field_bits : int, optional
        Field size in bits (default 64).

    Returns
    -------
    float
        Upper bound on collision probability.

    Notes
    -----
    For a polynomial of degree L over a field of size |F| = 2^n,
    the collision probability is bounded by L / |F|.

    According to the Schwartz-Zippel lemma, a non-zero polynomial
    of degree L over a field has at most L roots.
    """
    # Number of field elements in key
    num_elements = (key_length + field_bits - 1) // field_bits
    field_size = 2 ** field_bits

    return num_elements / field_size


def minimum_tag_bits_for_security(
    key_length: int, target_collision_prob: float
) -> int:
    """Calculate minimum tag bits for a target collision probability.

    Parameters
    ----------
    key_length : int
        Length of key in bits.
    target_collision_prob : float
        Desired maximum collision probability.

    Returns
    -------
    int
        Minimum number of tag bits needed.

    Examples
    --------
    >>> minimum_tag_bits_for_security(10000, 1e-12)
    77  # Approximately
    """
    # Collision prob = L / 2^n, so 2^n >= L / prob
    # n >= log2(L / prob) = log2(L) - log2(prob)
    import math

    num_elements = key_length  # Conservative: assume 1 element per bit
    required = math.log2(num_elements) - math.log2(target_collision_prob)
    return int(math.ceil(required))
