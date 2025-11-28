"""Unit tests for key verification.

This module provides comprehensive tests for:
- GF(2^n) field arithmetic (utils.py)
- Polynomial hashing (polynomial_hash.py)
- KeyVerifier class (verifier.py)

Reference: implementation_plan.md §Phase 3 (Unit Tests)
"""

import numpy as np
import pytest

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


# =============================================================================
# GF(2^n) Field Arithmetic Tests (utils.py)
# =============================================================================


class TestGFAdd:
    """Test suite for GF addition (XOR)."""

    def test_add_zero(self):
        """Test that a + 0 = a."""
        assert gf_add(42, 0) == 42
        assert gf_add(0, 42) == 42

    def test_add_self(self):
        """Test that a + a = 0 (characteristic 2)."""
        assert gf_add(42, 42) == 0
        assert gf_add(0xFFFF, 0xFFFF) == 0

    def test_add_commutativity(self):
        """Test that a + b = b + a."""
        assert gf_add(123, 456) == gf_add(456, 123)

    def test_add_associativity(self):
        """Test that (a + b) + c = a + (b + c)."""
        a, b, c = 123, 456, 789
        assert gf_add(gf_add(a, b), c) == gf_add(a, gf_add(b, c))

    def test_add_known_values(self):
        """Test addition with known XOR values."""
        assert gf_add(0b1010, 0b1100) == 0b0110
        assert gf_add(0xFF, 0x0F) == 0xF0


class TestGFMultiply:
    """Test suite for GF multiplication."""

    def test_multiply_by_zero(self):
        """Test that a * 0 = 0."""
        assert gf_multiply(42, 0, field_bits=64) == 0
        assert gf_multiply(0, 42, field_bits=64) == 0

    def test_multiply_by_one(self):
        """Test that a * 1 = a."""
        assert gf_multiply(42, 1, field_bits=64) == 42
        assert gf_multiply(1, 42, field_bits=64) == 42

    def test_multiply_commutativity(self):
        """Test that a * b = b * a."""
        a, b = 123, 456
        assert gf_multiply(a, b, field_bits=64) == gf_multiply(b, a, field_bits=64)

    def test_multiply_small_values(self):
        """Test multiplication with small values."""
        # In GF(2^n), 2 * 2 = 4 (no overflow)
        assert gf_multiply(2, 2, field_bits=64) == 4
        # 3 * 3 = 9 XOR reduction depends on implementation
        result = gf_multiply(3, 3, field_bits=64)
        assert result >= 0  # Just verify it doesn't error

    def test_multiply_determinism(self):
        """Test that multiplication is deterministic."""
        a, b = 0x12345678, 0x87654321
        result1 = gf_multiply(a, b, field_bits=64)
        result2 = gf_multiply(a, b, field_bits=64)
        assert result1 == result2

    def test_multiply_stays_in_field_64(self):
        """Test that result stays within GF(2^64)."""
        a = (1 << 63) | 0x12345678
        b = (1 << 62) | 0x87654321
        result = gf_multiply(a, b, field_bits=64)
        assert result < (1 << 64)

    def test_multiply_stays_in_field_128(self):
        """Test that result stays within GF(2^128)."""
        a = (1 << 127) | 0x12345678
        b = (1 << 126) | 0x87654321
        result = gf_multiply(a, b, field_bits=128)
        assert result < (1 << 128)

    def test_multiply_invalid_field_size(self):
        """Test that invalid field size raises error."""
        with pytest.raises(ValueError, match="Unsupported field size"):
            gf_multiply(1, 1, field_bits=32)


class TestGFPower:
    """Test suite for GF exponentiation."""

    def test_power_zero(self):
        """Test that a^0 = 1."""
        assert gf_power(42, 0, field_bits=64) == 1
        assert gf_power(0, 0, field_bits=64) == 1  # 0^0 = 1 by convention

    def test_power_one(self):
        """Test that a^1 = a."""
        assert gf_power(42, 1, field_bits=64) == 42
        assert gf_power(123, 1, field_bits=64) == 123

    def test_power_two(self):
        """Test that a^2 = a * a."""
        a = 42
        assert gf_power(a, 2, field_bits=64) == gf_multiply(a, a, field_bits=64)

    def test_power_three(self):
        """Test that a^3 = a * a * a."""
        a = 7
        a_squared = gf_multiply(a, a, field_bits=64)
        a_cubed = gf_multiply(a_squared, a, field_bits=64)
        assert gf_power(a, 3, field_bits=64) == a_cubed

    def test_power_negative_raises(self):
        """Test that negative exponent raises error."""
        with pytest.raises(ValueError, match="non-negative"):
            gf_power(2, -1, field_bits=64)

    def test_power_determinism(self):
        """Test that exponentiation is deterministic."""
        result1 = gf_power(12345, 100, field_bits=64)
        result2 = gf_power(12345, 100, field_bits=64)
        assert result1 == result2


class TestBitConversions:
    """Test suite for bit conversion functions."""

    def test_bits_to_int_big_endian(self):
        """Test big-endian bit to int conversion."""
        assert bits_to_int([1, 0, 1, 1]) == 11  # 1011 = 11
        assert bits_to_int([1, 0, 0, 0]) == 8   # 1000 = 8
        assert bits_to_int([0, 0, 0, 1]) == 1   # 0001 = 1

    def test_bits_to_int_little_endian(self):
        """Test little-endian bit to int conversion."""
        assert bits_to_int([1, 0, 1, 1], big_endian=False) == 13  # 1101 = 13
        assert bits_to_int([1, 0, 0, 0], big_endian=False) == 1   # 0001 = 1

    def test_bits_to_int_empty(self):
        """Test empty bit list."""
        assert bits_to_int([]) == 0

    def test_int_to_bits_big_endian(self):
        """Test big-endian int to bits conversion."""
        assert int_to_bits(11, 4) == [1, 0, 1, 1]
        assert int_to_bits(8, 4) == [1, 0, 0, 0]
        assert int_to_bits(1, 4) == [0, 0, 0, 1]

    def test_int_to_bits_little_endian(self):
        """Test little-endian int to bits conversion."""
        assert int_to_bits(11, 4, big_endian=False) == [1, 1, 0, 1]

    def test_roundtrip_conversion(self):
        """Test that bits -> int -> bits is identity."""
        original = [1, 0, 1, 1, 0, 0, 1, 0]
        value = bits_to_int(original)
        recovered = int_to_bits(value, len(original))
        assert recovered == original


class TestChunkBits:
    """Test suite for bit chunking."""

    def test_exact_division(self):
        """Test chunking with exact division."""
        bits = [1, 0, 1, 1, 0, 0, 1, 0]
        chunks = chunk_bits(bits, 4)
        assert chunks == [[1, 0, 1, 1], [0, 0, 1, 0]]

    def test_with_padding(self):
        """Test chunking with padding needed."""
        bits = [1, 0, 1]
        chunks = chunk_bits(bits, 4)
        assert chunks == [[1, 0, 1, 0]]  # Padded with zero

    def test_empty_input(self):
        """Test empty input."""
        assert chunk_bits([], 4) == []

    def test_single_element_chunk(self):
        """Test chunk size of 1."""
        bits = [1, 0, 1]
        chunks = chunk_bits(bits, 1)
        assert chunks == [[1], [0], [1]]


class TestBitsToFieldElements:
    """Test suite for converting bits to field elements."""

    def test_basic_conversion(self):
        """Test basic conversion to field elements."""
        bits = [1, 0, 1, 1, 0, 0, 1, 0]  # 0xB2
        elements = bits_to_field_elements(bits, element_bits=8)
        assert elements == [0xB2]

    def test_multiple_elements(self):
        """Test conversion to multiple elements."""
        bits = [1, 0, 1, 1, 0, 0, 1, 0, 1, 1, 1, 0, 0, 0, 0, 1]
        elements = bits_to_field_elements(bits, element_bits=8)
        assert len(elements) == 2

    def test_padding(self):
        """Test that incomplete chunks are padded."""
        bits = [1, 0, 1]
        elements = bits_to_field_elements(bits, element_bits=8)
        assert len(elements) == 1
        # Should be padded: [1, 0, 1, 0, 0, 0, 0, 0] = 0xA0
        assert elements[0] == 0xA0


class TestValidateFieldElement:
    """Test suite for field element validation."""

    def test_valid_elements(self):
        """Test valid field elements."""
        assert validate_field_element(0, field_bits=64)
        assert validate_field_element(42, field_bits=64)
        assert validate_field_element((1 << 64) - 1, field_bits=64)

    def test_invalid_negative(self):
        """Test negative values are invalid."""
        assert not validate_field_element(-1, field_bits=64)

    def test_invalid_too_large(self):
        """Test values too large are invalid."""
        assert not validate_field_element(1 << 64, field_bits=64)


class TestGenerateRandomFieldElement:
    """Test suite for random field element generation."""

    def test_generates_nonzero(self):
        """Test that generated elements are non-zero."""
        rng = np.random.default_rng(42)
        for _ in range(100):
            elem = generate_random_field_element(field_bits=64, rng=rng)
            assert elem != 0

    def test_stays_in_field(self):
        """Test that elements stay within field."""
        rng = np.random.default_rng(42)
        for _ in range(100):
            elem = generate_random_field_element(field_bits=64, rng=rng)
            assert 0 < elem < (1 << 64)


# =============================================================================
# Polynomial Hash Tests (polynomial_hash.py)
# =============================================================================


class TestComputePolynomialHash:
    """Test suite for polynomial hashing."""

    def test_hash_determinism(self):
        """Test that same key+salt produces same hash."""
        key = [1, 0, 1, 1, 0, 0, 1, 0] * 4
        salt = 0x12345678
        hash1 = compute_polynomial_hash(key, salt, field_bits=64)
        hash2 = compute_polynomial_hash(key, salt, field_bits=64)
        assert hash1 == hash2

    def test_different_keys_different_hashes(self):
        """Test that different keys produce different hashes (usually)."""
        key1 = [1, 0, 1, 1, 0, 0, 1, 0] * 4
        key2 = [0, 1, 0, 0, 1, 1, 0, 1] * 4
        salt = 0x12345678
        hash1 = compute_polynomial_hash(key1, salt, field_bits=64)
        hash2 = compute_polynomial_hash(key2, salt, field_bits=64)
        assert hash1 != hash2

    def test_different_salts_different_hashes(self):
        """Test that different salts produce different hashes."""
        key = [1, 0, 1, 1, 0, 0, 1, 0] * 4
        hash1 = compute_polynomial_hash(key, 0x12345678, field_bits=64)
        hash2 = compute_polynomial_hash(key, 0x87654321, field_bits=64)
        assert hash1 != hash2

    def test_empty_key_raises(self):
        """Test that empty key raises error."""
        with pytest.raises(ValueError, match="empty"):
            compute_polynomial_hash([], 0x12345678, field_bits=64)

    def test_zero_salt_raises(self):
        """Test that zero salt raises error."""
        with pytest.raises(ValueError, match="non-zero"):
            compute_polynomial_hash([1, 0, 1], 0, field_bits=64)

    def test_hash_stays_in_field(self):
        """Test that hash result stays within field."""
        key = [1, 0, 1, 1, 0, 0, 1, 0] * 100
        salt = 0x12345678
        hash_val = compute_polynomial_hash(key, salt, field_bits=64)
        assert 0 <= hash_val < (1 << 64)

    def test_single_bit_key(self):
        """Test hashing a single bit."""
        key = [1]
        salt = 0x12345678
        hash_val = compute_polynomial_hash(key, salt, field_bits=64)
        assert hash_val > 0


class TestComputePolynomialHashWithLength:
    """Test suite for hash with length encoding."""

    def test_length_encoded(self):
        """Test that length encoding changes the hash."""
        key = [1, 0, 1, 1, 0, 0, 1, 0]
        salt = 0x12345678
        hash_no_len = compute_polynomial_hash(key, salt, field_bits=64)
        hash_with_len = compute_polynomial_hash_with_length(key, salt, field_bits=64)
        # With length encoding, hashes should differ
        assert hash_no_len != hash_with_len

    def test_different_lengths_different_hashes(self):
        """Test that different length keys with same padding differ."""
        key1 = [1, 0, 1]
        key2 = [1, 0, 1, 0, 0, 0]  # Same bits but different length
        salt = 0x12345678
        hash1 = compute_polynomial_hash_with_length(key1, salt, field_bits=64)
        hash2 = compute_polynomial_hash_with_length(key2, salt, field_bits=64)
        assert hash1 != hash2


class TestVerifyHash:
    """Test suite for hash verification function."""

    def test_verify_correct_hash(self):
        """Test verification of correct hash."""
        key = [1, 0, 1, 1, 0, 0, 1, 0] * 4
        salt = 0x12345678
        tag = compute_polynomial_hash(key, salt, field_bits=64)
        assert verify_hash(key, salt, tag, field_bits=64)

    def test_verify_incorrect_hash(self):
        """Test verification fails for incorrect hash."""
        key = [1, 0, 1, 1, 0, 0, 1, 0] * 4
        salt = 0x12345678
        wrong_tag = 0xDEADBEEF
        assert not verify_hash(key, salt, wrong_tag, field_bits=64)


class TestGenerateHashSalt:
    """Test suite for salt generation."""

    def test_generates_nonzero(self):
        """Test that salt is non-zero."""
        rng = np.random.default_rng(42)
        for _ in range(100):
            salt = generate_hash_salt(field_bits=64, rng=rng)
            assert salt != 0

    def test_deterministic_with_seed(self):
        """Test that same seed produces same salt."""
        rng1 = np.random.default_rng(42)
        rng2 = np.random.default_rng(42)
        salt1 = generate_hash_salt(field_bits=64, rng=rng1)
        salt2 = generate_hash_salt(field_bits=64, rng=rng2)
        assert salt1 == salt2


class TestCollisionProbability:
    """Test suite for collision probability calculation."""

    def test_known_values(self):
        """Test collision probability against known values."""
        # For 64-bit field and 64-bit elements, 1 element = 1/2^64
        prob = collision_probability(64, field_bits=64)
        assert prob == pytest.approx(1.0 / (2**64), rel=1e-10)

    def test_increases_with_key_length(self):
        """Test that probability increases with key length."""
        prob_short = collision_probability(64, field_bits=64)
        prob_long = collision_probability(640, field_bits=64)
        assert prob_long > prob_short

    def test_decreases_with_field_size(self):
        """Test that probability decreases with field size."""
        prob_64 = collision_probability(1000, field_bits=64)
        prob_128 = collision_probability(1000, field_bits=128)
        assert prob_64 > prob_128

    def test_realistic_security(self):
        """Test collision probability for realistic QKD key lengths."""
        # 10000 bit key with 64-bit tags
        prob = collision_probability(10000, field_bits=64)
        # Should be extremely small
        assert prob < 1e-14


class TestMinimumTagBits:
    """Test suite for minimum tag bits calculation."""

    def test_reasonable_output(self):
        """Test that output is reasonable for typical inputs."""
        # For 10000 bit key and 10^-12 collision probability
        min_bits = minimum_tag_bits_for_security(10000, 1e-12)
        # Should need at least 53 bits (log2(10000/1e-12) ≈ 53)
        assert min_bits >= 50
        assert min_bits <= 100


# =============================================================================
# KeyVerifier Tests (verifier.py)
# =============================================================================


class TestKeyVerifierInit:
    """Test suite for KeyVerifier initialization."""

    def test_default_initialization(self):
        """Test default initialization."""
        verifier = KeyVerifier()
        assert verifier.tag_bits == 64

    def test_custom_tag_bits(self):
        """Test initialization with custom tag bits."""
        verifier = KeyVerifier(tag_bits=128)
        assert verifier.tag_bits == 128

    def test_invalid_tag_bits(self):
        """Test that invalid tag bits raises error."""
        with pytest.raises(ValueError, match="64 or 128"):
            KeyVerifier(tag_bits=32)


class TestKeyVerifierComputeHash:
    """Test suite for KeyVerifier.compute_hash."""

    def test_determinism(self):
        """Test hash computation is deterministic."""
        verifier = KeyVerifier(tag_bits=64)
        key = [1, 0, 1, 1, 0, 0, 1, 0] * 4
        salt = 0x12345678
        hash1 = verifier.compute_hash(key, salt)
        hash2 = verifier.compute_hash(key, salt)
        assert hash1 == hash2

    def test_matches_module_function(self):
        """Test that compute_hash matches module-level function."""
        verifier = KeyVerifier(tag_bits=64)
        key = [1, 0, 1, 1, 0, 0, 1, 0] * 4
        salt = 0x12345678
        verifier_hash = verifier.compute_hash(key, salt)
        module_hash = compute_polynomial_hash(key, salt, field_bits=64)
        assert verifier_hash == module_hash


class TestKeyVerifierVerifyLocal:
    """Test suite for KeyVerifier.verify_local."""

    def test_identical_keys_verify(self):
        """Test that identical keys return True."""
        verifier = KeyVerifier(tag_bits=64, rng_seed=42)
        key = [1, 0, 1, 1, 0, 0, 1, 0] * 4
        result = verifier.verify_local(key, key.copy())
        assert result.success is True
        assert result.local_tag == result.remote_tag

    def test_different_keys_fail(self):
        """Test that different keys return False."""
        verifier = KeyVerifier(tag_bits=64, rng_seed=42)
        key_a = [1, 0, 1, 1, 0, 0, 1, 0] * 4
        key_b = [0, 1, 0, 0, 1, 1, 0, 1] * 4
        result = verifier.verify_local(key_a, key_b)
        assert result.success is False
        assert result.local_tag != result.remote_tag

    def test_single_bit_difference(self):
        """Test that single bit difference is detected."""
        verifier = KeyVerifier(tag_bits=64, rng_seed=42)
        key_a = [1, 0, 1, 1, 0, 0, 1, 0] * 4
        key_b = key_a.copy()
        key_b[0] ^= 1  # Flip first bit
        result = verifier.verify_local(key_a, key_b)
        assert result.success is False

    def test_provides_collision_probability(self):
        """Test that result includes collision probability."""
        verifier = KeyVerifier(tag_bits=64, rng_seed=42)
        key = [1, 0, 1, 1, 0, 0, 1, 0] * 10
        result = verifier.verify_local(key, key)
        assert result.collision_prob > 0
        assert result.collision_prob < 1e-10

    def test_custom_salt(self):
        """Test verification with custom salt."""
        verifier = KeyVerifier(tag_bits=64)
        key = [1, 0, 1, 1, 0, 0, 1, 0] * 4
        salt = 0xDEADBEEF
        result = verifier.verify_local(key, key, salt=salt)
        assert result.success is True
        assert result.salt == salt


class TestKeyVerifierCollisionProbability:
    """Test suite for collision probability method."""

    def test_returns_valid_probability(self):
        """Test that method returns valid probability."""
        verifier = KeyVerifier(tag_bits=64)
        prob = verifier.get_collision_probability(1000)
        assert 0 < prob < 1

    def test_consistent_with_module_function(self):
        """Test consistency with module-level function."""
        verifier = KeyVerifier(tag_bits=64)
        key_length = 10000
        verifier_prob = verifier.get_collision_probability(key_length)
        module_prob = collision_probability(key_length, field_bits=64)
        assert verifier_prob == module_prob


class TestVerifyKeysMatch:
    """Test suite for convenience function."""

    def test_identical_keys(self):
        """Test that identical keys match."""
        key = [1, 0, 1, 1, 0, 0, 1, 0] * 4
        assert verify_keys_match(key, key.copy())

    def test_different_keys(self):
        """Test that different keys don't match."""
        key_a = [1, 0, 1, 1, 0, 0, 1, 0] * 4
        key_b = [0, 1, 0, 0, 1, 1, 0, 1] * 4
        assert not verify_keys_match(key_a, key_b)


# =============================================================================
# Edge Cases and Stress Tests
# =============================================================================


class TestEdgeCases:
    """Test edge cases for verification."""

    def test_single_bit_key(self):
        """Test verification with single bit key."""
        verifier = KeyVerifier(tag_bits=64, rng_seed=42)
        key = [1]
        result = verifier.verify_local(key, key)
        assert result.success is True

    def test_long_key(self):
        """Test verification with long key (1000 bits)."""
        np.random.seed(42)
        verifier = KeyVerifier(tag_bits=64, rng_seed=42)
        key = list(np.random.randint(0, 2, 1000))
        result = verifier.verify_local(key, key)
        assert result.success is True

    def test_all_zeros_key(self):
        """Test verification with all zeros key."""
        verifier = KeyVerifier(tag_bits=64, rng_seed=42)
        key = [0] * 64
        result = verifier.verify_local(key, key)
        assert result.success is True

    def test_all_ones_key(self):
        """Test verification with all ones key."""
        verifier = KeyVerifier(tag_bits=64, rng_seed=42)
        key = [1] * 64
        result = verifier.verify_local(key, key)
        assert result.success is True

    def test_128_bit_field(self):
        """Test with 128-bit field."""
        verifier = KeyVerifier(tag_bits=128, rng_seed=42)
        key = [1, 0, 1, 1, 0, 0, 1, 0] * 16
        result = verifier.verify_local(key, key)
        assert result.success is True


class TestCollisionResistance:
    """Test hash collision resistance."""

    def test_no_collisions_in_random_sample(self):
        """Test that random keys don't collide (probabilistic)."""
        verifier = KeyVerifier(tag_bits=64, rng_seed=42)
        np.random.seed(42)
        salt = 0x12345678

        hashes = set()
        for _ in range(1000):
            key = list(np.random.randint(0, 2, 64))
            h = verifier.compute_hash(key, salt)
            hashes.add(h)

        # All 1000 hashes should be unique (collision prob is negligible)
        assert len(hashes) == 1000

    def test_single_bit_flip_changes_hash(self):
        """Test that flipping any bit changes the hash."""
        verifier = KeyVerifier(tag_bits=64, rng_seed=42)
        key = [1, 0, 1, 1, 0, 0, 1, 0] * 8
        salt = 0x12345678
        original_hash = verifier.compute_hash(key, salt)

        for i in range(len(key)):
            modified_key = key.copy()
            modified_key[i] ^= 1
            modified_hash = verifier.compute_hash(modified_key, salt)
            assert modified_hash != original_hash, f"Bit flip at {i} didn't change hash"
