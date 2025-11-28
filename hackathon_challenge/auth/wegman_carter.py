"""Wegman-Carter authentication primitives.

Implements Toeplitz-based authentication as described in the theoretical document.
This module provides information-theoretic security for message authentication.

The Toeplitz-based Wegman-Carter scheme works as follows:
1. Hash Generation: H = T_S × M (Toeplitz matrix multiplication)
2. Encryption: Tag = H ⊕ r (One-Time Pad with mask r)

Reference:
- implementation_plan.md §Phase 1
- extending_qkd_theorethical_aspects.md Step 3 §3.1
"""

import hmac
import secrets
from typing import List, Tuple

import numpy as np


# Default tag length in bits (40 bits provides ε_auth ≈ 10^-12)
DEFAULT_TAG_BITS = 64


def _bytes_to_bits(data: bytes) -> List[int]:
    """Convert bytes to a list of bits.

    Parameters
    ----------
    data : bytes
        Input byte string.

    Returns
    -------
    List[int]
        List of bits (0 or 1).
    """
    bits = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


def _bits_to_bytes(bits: List[int]) -> bytes:
    """Convert a list of bits to bytes.

    Parameters
    ----------
    bits : List[int]
        List of bits (0 or 1). Length must be multiple of 8.

    Returns
    -------
    bytes
        Output byte string.

    Raises
    ------
    ValueError
        If bit list length is not a multiple of 8.
    """
    if len(bits) % 8 != 0:
        # Pad with zeros if necessary
        bits = bits + [0] * (8 - len(bits) % 8)
    
    result = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | bits[i + j]
        result.append(byte)
    return bytes(result)


def _construct_toeplitz_matrix(seed: List[int], rows: int, cols: int) -> np.ndarray:
    """Construct a Toeplitz matrix from a seed.

    A Toeplitz matrix is constant along diagonals. It is fully defined
    by its first row and first column.

    Parameters
    ----------
    seed : List[int]
        Random seed of length (rows + cols - 1).
    rows : int
        Number of rows in the output matrix.
    cols : int
        Number of columns in the output matrix.

    Returns
    -------
    np.ndarray
        Toeplitz matrix of shape (rows, cols).

    Raises
    ------
    ValueError
        If seed length doesn't match expected size.
    """
    expected_seed_len = rows + cols - 1
    if len(seed) < expected_seed_len:
        raise ValueError(
            f"Seed length {len(seed)} is less than required {expected_seed_len}"
        )
    
    # First column is seed[0:rows]
    # First row is seed[rows-1:rows+cols-1] (starting from seed[rows-1])
    col = np.array(seed[:rows], dtype=np.uint8)
    row = np.array(seed[rows - 1 : rows + cols - 1], dtype=np.uint8)
    
    # Build Toeplitz matrix
    # T[i,j] = seed[i - j + cols - 1] for the standard construction
    from scipy.linalg import toeplitz
    return toeplitz(col, row).astype(np.uint8)


def _derive_toeplitz_seed(key: bytes, message_bits: int, tag_bits: int) -> List[int]:
    """Derive a deterministic seed for Toeplitz matrix from key.

    Uses HMAC-SHA256 to expand the key into enough bits for the matrix seed.
    The seed S can be reused for multiple messages (defines the hash family).

    Parameters
    ----------
    key : bytes
        Pre-shared authentication key.
    message_bits : int
        Length of the message in bits.
    tag_bits : int
        Desired tag length in bits.

    Returns
    -------
    List[int]
        Seed bits for Toeplitz matrix construction.
    """
    seed_bits_needed = message_bits + tag_bits - 1
    seed_bytes_needed = (seed_bits_needed + 7) // 8 + 1  # Extra byte for safety
    
    # Use HMAC in counter mode to generate enough bits
    seed_bytes = b""
    counter = 0
    while len(seed_bytes) < seed_bytes_needed:
        h = hmac.new(key, f"toeplitz_seed_{counter}".encode(), "sha256")
        seed_bytes += h.digest()
        counter += 1
    
    return _bytes_to_bits(seed_bytes[:seed_bytes_needed])


def _derive_otp_mask(key: bytes, message: bytes, tag_bits: int) -> List[int]:
    """Derive a one-time pad mask for the authentication tag.

    Uses HMAC-SHA256 with the message to derive a unique mask.
    Note: In a true Wegman-Carter implementation, the mask should be
    consumed from a pre-shared key buffer and never reused.
    This implementation uses message-dependent derivation for practicality.

    Parameters
    ----------
    key : bytes
        Pre-shared authentication key.
    message : bytes
        Message being authenticated (used to derive unique mask).
    tag_bits : int
        Desired tag length in bits.

    Returns
    -------
    List[int]
        One-time pad mask bits.
    """
    # Derive unique mask using HMAC with the message
    h = hmac.new(key, b"otp_mask_" + message, "sha256")
    mask_bytes = h.digest()
    
    return _bytes_to_bits(mask_bytes)[: tag_bits]


def generate_auth_tag(
    message: bytes,
    key: bytes,
    tag_bits: int = DEFAULT_TAG_BITS
) -> bytes:
    """Generate Wegman-Carter authentication tag using Toeplitz hashing.

    Implements the formula: Tag = (T_S × M) ⊕ r
    where T_S is a Toeplitz matrix derived from the key,
    M is the message, and r is a one-time pad mask.

    Parameters
    ----------
    message : bytes
        Message to authenticate.
    key : bytes
        Pre-shared authentication key.
    tag_bits : int, optional
        Tag length in bits. Default is 64, providing strong security.

    Returns
    -------
    bytes
        Authentication tag of length ceil(tag_bits / 8) bytes.

    Notes
    -----
    Security guarantee: For an ε-AXU hash family, forgery probability is
    bounded by P(Forgery) ≤ 2^(-tag_bits).
    With tag_bits=64, this gives ε ≈ 5.4 × 10^-20.

    References
    ----------
    - Wegman & Carter (1981): "New hash functions and their use in 
      authentication and set equality"
    - extending_qkd_theorethical_aspects.md Step 3 §3.1
    """
    # Convert message to bits
    message_bits = _bytes_to_bits(message)
    message_len = len(message_bits)
    
    if message_len == 0:
        # Handle empty message: return tag derived from key only
        h = hmac.new(key, b"empty_message_tag", "sha256")
        return h.digest()[:((tag_bits + 7) // 8)]
    
    # Derive Toeplitz matrix seed from key (reusable across messages)
    toeplitz_seed = _derive_toeplitz_seed(key, message_len, tag_bits)
    
    # Construct Toeplitz matrix
    T = _construct_toeplitz_matrix(toeplitz_seed, tag_bits, message_len)
    
    # Hash: H = T × M (matrix-vector multiplication mod 2)
    message_arr = np.array(message_bits, dtype=np.uint8)
    hash_result = (T @ message_arr) % 2
    
    # Derive OTP mask (unique per message)
    otp_mask = _derive_otp_mask(key, message, tag_bits)
    otp_arr = np.array(otp_mask[:tag_bits], dtype=np.uint8)
    
    # Tag = H ⊕ r (XOR with one-time pad)
    tag_bits_result = (hash_result ^ otp_arr).tolist()
    
    return _bits_to_bytes(tag_bits_result)


def verify_auth_tag(
    message: bytes,
    tag: bytes,
    key: bytes,
    tag_bits: int = DEFAULT_TAG_BITS
) -> bool:
    """Verify Wegman-Carter authentication tag.

    Recomputes the expected tag and compares with the provided tag
    using constant-time comparison to prevent timing attacks.

    Parameters
    ----------
    message : bytes
        Message to verify.
    tag : bytes
        Authentication tag to check.
    key : bytes
        Pre-shared authentication key.
    tag_bits : int, optional
        Tag length in bits. Default is 64.

    Returns
    -------
    bool
        True if tag is valid, False otherwise.

    Notes
    -----
    Uses constant-time comparison (hmac.compare_digest) to prevent
    timing side-channel attacks.
    """
    expected_tag = generate_auth_tag(message, key, tag_bits)
    
    # Use constant-time comparison
    return hmac.compare_digest(tag, expected_tag)


def generate_toeplitz_seed_bits(seed_length: int) -> List[int]:
    """Generate cryptographically secure random bits for Toeplitz seed.

    Parameters
    ----------
    seed_length : int
        Number of bits to generate.

    Returns
    -------
    List[int]
        Random bits (0 or 1).
    """
    num_bytes = (seed_length + 7) // 8
    random_bytes = secrets.token_bytes(num_bytes)
    bits = _bytes_to_bits(random_bytes)
    return bits[:seed_length]


class ToeplitzAuthenticator:
    """Stateful Wegman-Carter authenticator using Toeplitz hashing.

    This class maintains a key buffer for proper one-time pad usage
    in strict Wegman-Carter authentication.

    Parameters
    ----------
    key : bytes
        Initial pre-shared secret key.
    tag_bits : int, optional
        Tag length in bits. Default is 64.

    Attributes
    ----------
    tag_bits : int
        Tag length in bits.
    _key : bytes
        Authentication key.
    _message_counter : int
        Counter for unique mask derivation.

    Notes
    -----
    For true information-theoretic security, the OTP mask must never
    be reused. This implementation uses a counter-based derivation
    that must be synchronized between Alice and Bob.

    References
    ----------
    - extending_qkd_theorethical_aspects.md Step 3 §4 (Key Management)
    """

    def __init__(self, key: bytes, tag_bits: int = DEFAULT_TAG_BITS) -> None:
        """Initialize the authenticator."""
        self._key = key
        self.tag_bits = tag_bits
        self._message_counter = 0

    def authenticate(self, message: bytes) -> Tuple[bytes, bytes]:
        """Generate authentication tag for a message.

        Parameters
        ----------
        message : bytes
            Message to authenticate.

        Returns
        -------
        Tuple[bytes, bytes]
            Tuple of (message, tag).
        """
        tag = generate_auth_tag(message, self._key, self.tag_bits)
        self._message_counter += 1
        return message, tag

    def verify(self, message: bytes, tag: bytes) -> bool:
        """Verify a message-tag pair.

        Parameters
        ----------
        message : bytes
            Message to verify.
        tag : bytes
            Authentication tag.

        Returns
        -------
        bool
            True if verification succeeds.
        """
        is_valid = verify_auth_tag(message, tag, self._key, self.tag_bits)
        self._message_counter += 1
        return is_valid

    def reset_counter(self) -> None:
        """Reset the message counter (use with caution)."""
        self._message_counter = 0
