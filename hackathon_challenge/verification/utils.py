"""Galois Field utilities for polynomial hashing.

This module implements arithmetic operations in GF(2^n), specifically
targeting GF(2^64) and GF(2^128) for universal hashing.

Reference:
- implementation_plan.md §Phase 3
- extending_qkd_theorethical_aspects.md §3.2

Notes
-----
GF(2^n) arithmetic uses carry-less multiplication (XOR instead of addition)
and reduction modulo an irreducible polynomial.

Common irreducible polynomials:
- GF(2^64):  x^64 + x^4 + x^3 + x + 1  (0x1B in reduced form)
- GF(2^128): x^128 + x^7 + x^2 + x + 1 (0x87 in reduced form)
"""

from typing import List

import numpy as np

# Irreducible polynomial for GF(2^64): x^64 + x^4 + x^3 + x + 1
# When we reduce, we use the "feedback" bits: x^4 + x^3 + x + 1 = 0x1B
GF64_MODULUS: int = 0x1B

# Irreducible polynomial for GF(2^128): x^128 + x^7 + x^2 + x + 1
# Feedback bits: x^7 + x^2 + x + 1 = 0x87
GF128_MODULUS: int = 0x87

# Standard field sizes
GF64_SIZE: int = 64
GF128_SIZE: int = 128


def gf_multiply(a: int, b: int, field_bits: int = 128) -> int:
    """Multiply two elements in GF(2^n).

    Parameters
    ----------
    a : int
        First element (must be < 2^field_bits).
    b : int
        Second element (must be < 2^field_bits).
    field_bits : int, optional
        Field size in bits (default 128 for GF(2^128)).

    Returns
    -------
    int
        Product a * b in GF(2^n).

    Notes
    -----
    Implements Russian peasant multiplication (shift-and-XOR) with
    reduction modulo the field's irreducible polynomial.

    In GF(2^n):
    - Addition is XOR
    - Multiplication uses shift-and-conditional-XOR
    - Reduction happens when result exceeds field size

    Examples
    --------
    >>> gf_multiply(3, 7, field_bits=64)  # Small example in GF(2^64)
    9
    """
    if field_bits == 64:
        modulus = GF64_MODULUS
    elif field_bits == 128:
        modulus = GF128_MODULUS
    else:
        raise ValueError(f"Unsupported field size: {field_bits}")

    result = 0
    mask = (1 << field_bits) - 1  # Mask for field_bits bits

    # Russian peasant multiplication
    while b:
        # If low bit of b is set, add a to result
        if b & 1:
            result ^= a

        # Shift b right (divide by x)
        b >>= 1

        # Shift a left (multiply by x)
        carry = a >> (field_bits - 1)  # Check if MSB will overflow
        a = (a << 1) & mask  # Shift and mask

        # If there was overflow, reduce by XORing with modulus
        if carry:
            a ^= modulus

    return result


def gf_power(base: int, exponent: int, field_bits: int = 128) -> int:
    """Compute base^exponent in GF(2^n) using square-and-multiply.

    Parameters
    ----------
    base : int
        Base element.
    exponent : int
        Non-negative exponent.
    field_bits : int, optional
        Field size in bits (default 128).

    Returns
    -------
    int
        base^exponent in GF(2^n).

    Raises
    ------
    ValueError
        If exponent is negative.

    Examples
    --------
    >>> gf_power(2, 0, field_bits=64)  # x^0 = 1
    1
    >>> gf_power(2, 1, field_bits=64)  # x^1 = 2
    2
    """
    if exponent < 0:
        raise ValueError("Exponent must be non-negative")

    if exponent == 0:
        return 1

    result = 1

    # Square-and-multiply algorithm
    while exponent > 0:
        # If current bit is set, multiply result by base
        if exponent & 1:
            result = gf_multiply(result, base, field_bits)

        # Square the base
        base = gf_multiply(base, base, field_bits)

        # Move to next bit
        exponent >>= 1

    return result


def gf_add(a: int, b: int) -> int:
    """Add two elements in GF(2^n).

    Parameters
    ----------
    a : int
        First element.
    b : int
        Second element.

    Returns
    -------
    int
        Sum a + b in GF(2^n), which is simply XOR.

    Notes
    -----
    In GF(2^n), addition is XOR: a + b = a ^ b
    This is the same as subtraction: a - b = a ^ b
    """
    return a ^ b


def bits_to_int(bits: List[int], big_endian: bool = True) -> int:
    """Convert a list of bits to an integer.

    Parameters
    ----------
    bits : List[int]
        List of bits (0 or 1).
    big_endian : bool, optional
        If True, first bit is MSB (default True).

    Returns
    -------
    int
        Integer representation of the bits (native Python int).

    Examples
    --------
    >>> bits_to_int([1, 0, 1, 1])  # Big-endian: 1011 = 11
    11
    >>> bits_to_int([1, 0, 1, 1], big_endian=False)  # Little-endian: 1101 = 13
    13
    """
    result = 0
    if big_endian:
        for bit in bits:
            # Ensure bit is native Python int to avoid numpy type issues
            result = (result << 1) | (int(bit) & 1)
    else:
        for i, bit in enumerate(bits):
            result |= (int(bit) & 1) << i
    return result


def int_to_bits(value: int, num_bits: int, big_endian: bool = True) -> List[int]:
    """Convert an integer to a list of bits.

    Parameters
    ----------
    value : int
        Integer to convert.
    num_bits : int
        Number of bits in output.
    big_endian : bool, optional
        If True, first bit is MSB (default True).

    Returns
    -------
    List[int]
        List of bits.

    Examples
    --------
    >>> int_to_bits(11, 4)  # 11 = 1011
    [1, 0, 1, 1]
    >>> int_to_bits(11, 4, big_endian=False)
    [1, 1, 0, 1]
    """
    bits = []
    for _ in range(num_bits):
        bits.append(value & 1)
        value >>= 1

    if big_endian:
        bits.reverse()

    return bits


def chunk_bits(bits: List[int], chunk_size: int) -> List[List[int]]:
    """Split a bit list into chunks of specified size.

    Parameters
    ----------
    bits : List[int]
        List of bits to split.
    chunk_size : int
        Size of each chunk.

    Returns
    -------
    List[List[int]]
        List of bit chunks. Last chunk may be zero-padded.

    Examples
    --------
    >>> chunk_bits([1, 0, 1, 1, 0, 0, 1, 0], 4)
    [[1, 0, 1, 1], [0, 0, 1, 0]]
    >>> chunk_bits([1, 0, 1], 4)  # Padded with zeros
    [[1, 0, 1, 0]]
    """
    if not bits:
        return []

    chunks = []
    for i in range(0, len(bits), chunk_size):
        chunk = bits[i : i + chunk_size]
        # Pad last chunk with zeros if needed
        if len(chunk) < chunk_size:
            chunk = chunk + [0] * (chunk_size - len(chunk))
        chunks.append(chunk)

    return chunks


def bits_to_field_elements(
    bits: List[int], element_bits: int = 64
) -> List[int]:
    """Convert a bit list to field elements.

    Parameters
    ----------
    bits : List[int]
        List of bits (key bits).
    element_bits : int, optional
        Bits per field element (default 64).

    Returns
    -------
    List[int]
        List of field elements.

    Notes
    -----
    The key is split into chunks of element_bits and each chunk
    is converted to an integer field element.
    """
    chunks = chunk_bits(bits, element_bits)
    return [bits_to_int(chunk) for chunk in chunks]


def validate_field_element(value: int, field_bits: int = 128) -> bool:
    """Check if a value is a valid field element.

    Parameters
    ----------
    value : int
        Value to check.
    field_bits : int, optional
        Field size in bits (default 128).

    Returns
    -------
    bool
        True if value is valid (0 <= value < 2^field_bits).
    """
    return 0 <= value < (1 << field_bits)


def generate_random_field_element(
    field_bits: int = 128, rng: np.random.Generator = None
) -> int:
    """Generate a random non-zero field element.

    Parameters
    ----------
    field_bits : int, optional
        Field size in bits (default 128).
    rng : np.random.Generator, optional
        Random number generator. Uses default if None.

    Returns
    -------
    int
        Random non-zero element in GF(2^n).
    """
    if rng is None:
        rng = np.random.default_rng()

    # Generate random bits and convert to integer
    # Ensure non-zero result
    while True:
        bits = rng.integers(0, 2, size=field_bits).tolist()
        value = bits_to_int(bits)
        if value != 0:
            return value
