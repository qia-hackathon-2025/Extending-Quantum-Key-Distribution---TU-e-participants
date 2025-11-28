"""Toeplitz matrix utilities.

This module provides functions for generating and manipulating Toeplitz
matrices used in privacy amplification. Toeplitz matrices form a family
of 2-universal hash functions suitable for the Leftover Hash Lemma.

Reference:
- implementation_plan.md §Phase 4
- extending_qkd_theorethical_aspects.md §4.2

Notes
-----
A Toeplitz matrix has constant diagonals, meaning each descending diagonal
from left to right is constant. This structure allows:
1. Efficient storage: Only n + m - 1 values needed for n × m matrix
2. Efficient multiplication: O(n log n) using FFT
3. 2-universal hashing: Proven security for privacy amplification

The Leftover Hash Lemma guarantees that applying a random Toeplitz matrix
to a weakly random string produces a nearly uniform random string,
provided the output length is appropriate.
"""

import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np


@dataclass
class ToeplitzSeed:
    """Seed for constructing a Toeplitz matrix.

    Attributes
    ----------
    bits : List[int]
        Random bits defining the matrix (length = n + m - 1).
    input_length : int
        Number of columns (input key length).
    output_length : int
        Number of rows (output key length).
    rng_seed : Optional[int]
        Seed used for random generation (None if not reproducible).
    """

    bits: List[int]
    input_length: int
    output_length: int
    rng_seed: Optional[int] = None

    def __post_init__(self) -> None:
        """Validate seed after initialization."""
        expected_length = self.input_length + self.output_length - 1
        if len(self.bits) != expected_length:
            raise ValueError(
                f"Seed length must be {expected_length}, got {len(self.bits)}"
            )

    @property
    def first_column(self) -> List[int]:
        """Get first column of Toeplitz matrix."""
        return self.bits[: self.output_length]

    @property
    def first_row(self) -> List[int]:
        """Get first row of Toeplitz matrix."""
        # First element is shared between column and row
        return [self.bits[self.output_length - 1]] + self.bits[self.output_length :]


def compute_seed_length(input_length: int, output_length: int) -> int:
    """Compute required seed length for Toeplitz matrix.

    Parameters
    ----------
    input_length : int
        Length of input key.
    output_length : int
        Length of output key.

    Returns
    -------
    int
        Required seed length (input_length + output_length - 1).

    Raises
    ------
    ValueError
        If lengths are not positive or output > input.
    """
    if input_length <= 0:
        raise ValueError(f"Input length must be positive, got {input_length}")
    if output_length <= 0:
        raise ValueError(f"Output length must be positive, got {output_length}")
    if output_length > input_length:
        raise ValueError(
            f"Output length ({output_length}) cannot exceed input length ({input_length})"
        )

    return input_length + output_length - 1


def generate_toeplitz_seed(
    key_length: int,
    final_length: int,
    rng_seed: Optional[int] = None,
) -> List[int]:
    """Generate random seed for Toeplitz matrix.

    Parameters
    ----------
    key_length : int
        Length of input key.
    final_length : int
        Length of output key.
    rng_seed : int, optional
        Seed for random number generator. If None, uses system randomness.

    Returns
    -------
    List[int]
        Random seed bits (length = key_length + final_length - 1).

    Raises
    ------
    ValueError
        If lengths are invalid.

    Notes
    -----
    A Toeplitz matrix is fully defined by its first row and first column,
    requiring key_length + final_length - 1 bits total.

    When rng_seed is provided, the function is deterministic for testing.
    """
    seed_length = compute_seed_length(key_length, final_length)

    if rng_seed is not None:
        rng = random.Random(rng_seed)
        return [rng.randint(0, 1) for _ in range(seed_length)]
    else:
        return [random.randint(0, 1) for _ in range(seed_length)]


def generate_toeplitz_seed_structured(
    key_length: int,
    final_length: int,
    rng_seed: Optional[int] = None,
) -> ToeplitzSeed:
    """Generate structured Toeplitz seed with metadata.

    Parameters
    ----------
    key_length : int
        Length of input key.
    final_length : int
        Length of output key.
    rng_seed : int, optional
        Seed for random number generator.

    Returns
    -------
    ToeplitzSeed
        Structured seed with metadata.
    """
    bits = generate_toeplitz_seed(key_length, final_length, rng_seed)
    return ToeplitzSeed(
        bits=bits,
        input_length=key_length,
        output_length=final_length,
        rng_seed=rng_seed,
    )


def validate_toeplitz_seed(
    seed: List[int],
    key_length: int,
    final_length: int,
) -> bool:
    """Validate Toeplitz seed length and format.

    Parameters
    ----------
    seed : List[int]
        Seed bits to validate.
    key_length : int
        Expected input key length.
    final_length : int
        Expected output key length.

    Returns
    -------
    bool
        True if seed is valid, False otherwise.
    """
    expected_length = compute_seed_length(key_length, final_length)

    if len(seed) != expected_length:
        return False

    # Check all values are 0 or 1
    return all(bit in (0, 1) for bit in seed)


def construct_toeplitz_matrix(
    seed: List[int],
    num_rows: int,
    num_cols: int,
) -> np.ndarray:
    """Construct Toeplitz matrix from seed.

    Parameters
    ----------
    seed : List[int]
        Seed bits (length = num_cols + num_rows - 1).
    num_rows : int
        Number of rows (output length).
    num_cols : int
        Number of columns (input length).

    Returns
    -------
    np.ndarray
        Toeplitz matrix of shape (num_rows, num_cols).

    Raises
    ------
    ValueError
        If seed length doesn't match dimensions.

    Notes
    -----
    The matrix is constructed such that:
    - First column: seed[0:num_rows]
    - First row: seed[num_rows-1:num_rows+num_cols-1]
    """
    from scipy.linalg import toeplitz

    expected_length = num_cols + num_rows - 1
    if len(seed) != expected_length:
        raise ValueError(
            f"Seed length must be {expected_length}, got {len(seed)}"
        )

    # First column and first row for scipy.linalg.toeplitz
    col = seed[:num_rows]
    # First element of row is same as first element of col
    # So row starts from seed[num_rows-1]
    row_start = num_rows - 1
    row = seed[row_start : row_start + num_cols]

    return toeplitz(col, row).astype(np.uint8)


def construct_toeplitz_matrix_numpy(
    seed: List[int],
    num_rows: int,
    num_cols: int,
) -> np.ndarray:
    """Construct Toeplitz matrix using pure NumPy (no scipy dependency).

    Parameters
    ----------
    seed : List[int]
        Seed bits (length = num_cols + num_rows - 1).
    num_rows : int
        Number of rows.
    num_cols : int
        Number of columns.

    Returns
    -------
    np.ndarray
        Toeplitz matrix of shape (num_rows, num_cols).
    """
    expected_length = num_cols + num_rows - 1
    if len(seed) != expected_length:
        raise ValueError(
            f"Seed length must be {expected_length}, got {len(seed)}"
        )

    # Create indices for Toeplitz structure
    # T[i,j] = seed[i - j + num_cols - 1]
    rows, cols = np.ogrid[:num_rows, :num_cols]
    indices = rows - cols + num_cols - 1

    seed_array = np.array(seed, dtype=np.uint8)
    return seed_array[indices]


def toeplitz_multiply(
    matrix_or_seed: np.ndarray,
    vector: np.ndarray,
) -> np.ndarray:
    """Multiply Toeplitz matrix by vector modulo 2.

    Parameters
    ----------
    matrix_or_seed : np.ndarray
        Toeplitz matrix or seed array.
    vector : np.ndarray
        Input vector.

    Returns
    -------
    np.ndarray
        Result vector (mod 2).

    Notes
    -----
    Performs T × v mod 2 where T is the Toeplitz matrix.
    For large matrices, FFT-based multiplication would be more efficient.
    """
    result = matrix_or_seed @ vector
    return result % 2


def extract_toeplitz_components(
    seed: List[int],
    num_rows: int,
    num_cols: int,
) -> Tuple[List[int], List[int]]:
    """Extract first column and first row from Toeplitz seed.

    Parameters
    ----------
    seed : List[int]
        Toeplitz seed bits.
    num_rows : int
        Number of rows (output length).
    num_cols : int
        Number of columns (input length).

    Returns
    -------
    Tuple[List[int], List[int]]
        (first_column, first_row) of the Toeplitz matrix.
    """
    first_column = seed[:num_rows]
    first_row = seed[num_rows - 1 : num_rows - 1 + num_cols]
    return first_column, first_row


def bits_to_bytes(bits: List[int]) -> bytes:
    """Convert bit list to bytes.

    Parameters
    ----------
    bits : List[int]
        List of bits (0 or 1).

    Returns
    -------
    bytes
        Byte representation (MSB first within each byte).
    """
    # Pad to multiple of 8
    padded_length = ((len(bits) + 7) // 8) * 8
    padded_bits = bits + [0] * (padded_length - len(bits))

    byte_list = []
    for i in range(0, padded_length, 8):
        byte_val = 0
        for j in range(8):
            byte_val = (byte_val << 1) | padded_bits[i + j]
        byte_list.append(byte_val)

    return bytes(byte_list)


def bytes_to_bits(data: bytes, num_bits: Optional[int] = None) -> List[int]:
    """Convert bytes to bit list.

    Parameters
    ----------
    data : bytes
        Byte data.
    num_bits : int, optional
        Number of bits to extract. If None, extracts all bits.

    Returns
    -------
    List[int]
        List of bits.
    """
    bits = []
    for byte_val in data:
        for i in range(7, -1, -1):
            bits.append((byte_val >> i) & 1)

    if num_bits is not None:
        return bits[:num_bits]
    return bits
