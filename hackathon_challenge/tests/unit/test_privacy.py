"""Unit tests for privacy amplification.

This module contains comprehensive tests for all privacy amplification
components including binary entropy, QBER estimation, key length calculation,
and Toeplitz-based privacy amplification.

Reference: implementation_plan.md §Phase 4 (Unit Tests)
"""

import math
import random

import numpy as np
import pytest
from scipy import stats

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
from hackathon_challenge.privacy.estimation import (
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
from hackathon_challenge.privacy.amplifier import (
    AmplificationResult,
    PrivacyAmplifier,
    apply_privacy_amplification,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_key() -> list:
    """Generate a sample key for testing."""
    random.seed(42)
    return [random.randint(0, 1) for _ in range(1000)]


@pytest.fixture
def small_key() -> list:
    """Generate a small key for quick tests."""
    return [0, 1, 1, 0, 1, 0, 0, 1, 1, 1, 0, 1, 0, 1, 0, 0]


@pytest.fixture
def deterministic_amplifier() -> PrivacyAmplifier:
    """Create a deterministic amplifier for reproducible tests."""
    return PrivacyAmplifier(epsilon_sec=1e-12, rng_seed=42)


# =============================================================================
# Binary Entropy Tests
# =============================================================================


class TestBinaryEntropy:
    """Test suite for binary entropy function."""

    def test_entropy_at_half(self):
        """Test that h(0.5) = 1.0 (maximum entropy)."""
        assert binary_entropy(0.5) == pytest.approx(1.0, abs=1e-10)

    def test_entropy_at_zero(self):
        """Test that h(0) = 0 (no uncertainty)."""
        assert binary_entropy(0.0) == 0.0

    def test_entropy_at_one(self):
        """Test that h(1) = 0 (no uncertainty)."""
        assert binary_entropy(1.0) == 0.0

    def test_entropy_known_values(self):
        """Test entropy against known values."""
        # h(0.1) ≈ 0.469
        assert binary_entropy(0.1) == pytest.approx(0.4689955935892812, abs=1e-6)
        # h(0.01) ≈ 0.0808
        assert binary_entropy(0.01) == pytest.approx(0.08079313589591118, abs=1e-6)
        # h(0.11) - compute actual value
        assert binary_entropy(0.11) == pytest.approx(0.499915958164528, abs=1e-6)

    def test_entropy_symmetry(self):
        """Test that h(p) = h(1-p)."""
        for p in [0.1, 0.2, 0.3, 0.4]:
            assert binary_entropy(p) == pytest.approx(binary_entropy(1 - p), abs=1e-10)

    def test_entropy_monotonicity(self):
        """Test that h(p) increases from 0 to 0.5."""
        values = [0.1, 0.2, 0.3, 0.4, 0.5]
        entropies = [binary_entropy(p) for p in values]
        for i in range(len(entropies) - 1):
            assert entropies[i] < entropies[i + 1]

    def test_entropy_invalid_negative(self):
        """Test that negative probabilities raise error."""
        with pytest.raises(ValueError, match="must be in"):
            binary_entropy(-0.1)

    def test_entropy_invalid_greater_than_one(self):
        """Test that p > 1 raises error."""
        with pytest.raises(ValueError, match="must be in"):
            binary_entropy(1.1)

    def test_entropy_boundary_near_zero(self):
        """Test entropy at very small p values."""
        # Should approach 0 as p → 0
        assert binary_entropy(1e-10) == pytest.approx(0.0, abs=1e-8)
        assert binary_entropy(1e-6) < 0.001

    def test_entropy_boundary_near_one(self):
        """Test entropy at p values very close to 1."""
        # Should approach 0 as p → 1
        assert binary_entropy(1 - 1e-10) == pytest.approx(0.0, abs=1e-8)


class TestBinaryEntropyDerivative:
    """Test suite for binary entropy derivative."""

    def test_derivative_at_half(self):
        """Test that h'(0.5) = 0 (maximum point)."""
        assert binary_entropy_derivative(0.5) == pytest.approx(0.0, abs=1e-10)

    def test_derivative_sign_below_half(self):
        """Test that h'(p) > 0 for p < 0.5."""
        for p in [0.1, 0.2, 0.3, 0.4]:
            assert binary_entropy_derivative(p) > 0

    def test_derivative_sign_above_half(self):
        """Test that h'(p) < 0 for p > 0.5."""
        for p in [0.6, 0.7, 0.8, 0.9]:
            assert binary_entropy_derivative(p) < 0

    def test_derivative_boundary_error(self):
        """Test that derivative at boundaries raises error."""
        with pytest.raises(ValueError):
            binary_entropy_derivative(0.0)
        with pytest.raises(ValueError):
            binary_entropy_derivative(1.0)


class TestInverseBinaryEntropy:
    """Test suite for inverse binary entropy function."""

    def test_inverse_at_zero(self):
        """Test inverse at h=0."""
        assert inverse_binary_entropy(0.0, "lower") == pytest.approx(0.0, abs=1e-10)
        assert inverse_binary_entropy(0.0, "upper") == pytest.approx(1.0, abs=1e-10)

    def test_inverse_at_one(self):
        """Test inverse at h=1."""
        assert inverse_binary_entropy(1.0, "lower") == pytest.approx(0.5, abs=1e-10)
        assert inverse_binary_entropy(1.0, "upper") == pytest.approx(0.5, abs=1e-10)

    def test_inverse_roundtrip_lower(self):
        """Test that inverse(h(p)) = p for p < 0.5."""
        for p in [0.05, 0.1, 0.2, 0.3, 0.4]:
            h = binary_entropy(p)
            recovered = inverse_binary_entropy(h, "lower")
            assert recovered == pytest.approx(p, abs=1e-8)

    def test_inverse_roundtrip_upper(self):
        """Test that inverse(h(p)) = p for p > 0.5."""
        for p in [0.6, 0.7, 0.8, 0.9, 0.95]:
            h = binary_entropy(p)
            recovered = inverse_binary_entropy(h, "upper")
            assert recovered == pytest.approx(p, abs=1e-8)

    def test_inverse_invalid_entropy(self):
        """Test that invalid entropy values raise error."""
        with pytest.raises(ValueError):
            inverse_binary_entropy(-0.1)
        with pytest.raises(ValueError):
            inverse_binary_entropy(1.5)

    def test_inverse_invalid_branch(self):
        """Test that invalid branch raises error."""
        with pytest.raises(ValueError):
            inverse_binary_entropy(0.5, "middle")


class TestSecrecyCapacity:
    """Test suite for secrecy capacity function."""

    def test_capacity_at_zero_qber(self):
        """Test that capacity is 1 at QBER = 0."""
        assert secrecy_capacity(0.0) == pytest.approx(1.0, abs=1e-10)

    def test_capacity_at_half(self):
        """Test that capacity is 0 at QBER = 0.5."""
        assert secrecy_capacity(0.5) == pytest.approx(0.0, abs=1e-10)

    def test_capacity_above_half(self):
        """Test that capacity is 0 for QBER > 0.5."""
        assert secrecy_capacity(0.6) == 0.0
        assert secrecy_capacity(1.0) == 0.0

    def test_capacity_at_threshold(self):
        """Test capacity at security threshold (11%)."""
        # At 11%, capacity ≈ 0.5 (roughly)
        cap = secrecy_capacity(0.11)
        assert cap == pytest.approx(1 - binary_entropy(0.11), abs=1e-10)
        assert 0.4 < cap < 0.6

    def test_capacity_negative_qber(self):
        """Test that negative QBER raises error."""
        with pytest.raises(ValueError):
            secrecy_capacity(-0.1)

    def test_capacity_decreases_with_qber(self):
        """Test that capacity decreases as QBER increases."""
        qbers = [0.01, 0.05, 0.1, 0.2, 0.3, 0.4]
        capacities = [secrecy_capacity(q) for q in qbers]
        for i in range(len(capacities) - 1):
            assert capacities[i] > capacities[i + 1]


class TestIsQberSecure:
    """Test suite for QBER security check."""

    def test_secure_below_threshold(self):
        """Test that QBER below threshold is secure."""
        assert is_qber_secure(0.05) is True
        assert is_qber_secure(0.10) is True
        assert is_qber_secure(0.109) is True

    def test_insecure_at_threshold(self):
        """Test that QBER at threshold is not secure."""
        assert is_qber_secure(0.11) is False

    def test_insecure_above_threshold(self):
        """Test that QBER above threshold is not secure."""
        assert is_qber_secure(0.12) is False
        assert is_qber_secure(0.5) is False

    def test_secure_at_zero(self):
        """Test that QBER = 0 is secure."""
        assert is_qber_secure(0.0) is True

    def test_custom_threshold(self):
        """Test with custom threshold."""
        assert is_qber_secure(0.05, threshold=0.04) is False
        assert is_qber_secure(0.05, threshold=0.06) is True


class TestSecurityMargin:
    """Test suite for security margin calculation."""

    def test_default_epsilon(self):
        """Test security margin with default epsilon."""
        margin = compute_security_margin(1e-12)
        # 2 * log2(1e12) ≈ 2 * 39.86 ≈ 79.73
        assert margin == pytest.approx(79.726, abs=0.01)

    def test_larger_epsilon(self):
        """Test that larger epsilon gives smaller margin."""
        margin_small = compute_security_margin(1e-12)
        margin_large = compute_security_margin(1e-6)
        assert margin_large < margin_small

    def test_epsilon_bounds(self):
        """Test that invalid epsilon raises error."""
        with pytest.raises(ValueError):
            compute_security_margin(0.0)
        with pytest.raises(ValueError):
            compute_security_margin(-0.1)
        with pytest.raises(ValueError):
            compute_security_margin(1.5)


# =============================================================================
# Key Length Calculation Tests
# =============================================================================


class TestKeyLengthCalculation:
    """Test suite for final key length calculation."""

    def test_positive_length_low_qber(self):
        """Test that valid QBER produces positive key length."""
        length = compute_final_key_length(
            reconciled_length=10000,
            qber=0.05,
            leakage_ec=500,
            leakage_ver=64,
            epsilon_sec=1e-12,
        )
        assert length > 0
        assert length < 10000  # Must be compressed

    def test_zero_length_high_qber(self):
        """Test that high QBER produces zero key length."""
        length = compute_final_key_length(
            reconciled_length=10000,
            qber=0.12,  # Above threshold
            leakage_ec=500,
            leakage_ver=64,
        )
        assert length == 0

    def test_zero_length_at_threshold(self):
        """Test key length at exact threshold."""
        length = compute_final_key_length(
            reconciled_length=10000,
            qber=0.11,  # At threshold
            leakage_ec=500,
            leakage_ver=64,
        )
        assert length == 0  # Not secure

    def test_length_decreases_with_qber(self):
        """Test that key length decreases as QBER increases."""
        qbers = [0.01, 0.03, 0.05, 0.07, 0.09]
        lengths = [
            compute_final_key_length(10000, q, 500, 64)
            for q in qbers
        ]
        for i in range(len(lengths) - 1):
            assert lengths[i] > lengths[i + 1]

    def test_length_decreases_with_leakage(self):
        """Test that key length decreases with more leakage."""
        base = compute_final_key_length(10000, 0.05, 0, 0)
        with_ec = compute_final_key_length(10000, 0.05, 1000, 0)
        with_ver = compute_final_key_length(10000, 0.05, 0, 64)
        assert base > with_ec
        assert base > with_ver

    def test_length_increases_with_input(self):
        """Test that key length increases with input length."""
        length_small = compute_final_key_length(5000, 0.05, 250, 64)
        length_large = compute_final_key_length(10000, 0.05, 500, 64)
        assert length_large > length_small

    def test_zero_input_length(self):
        """Test with zero input length."""
        length = compute_final_key_length(0, 0.05, 0, 0)
        assert length == 0

    def test_invalid_parameters(self):
        """Test that invalid parameters raise errors."""
        with pytest.raises(ValueError):
            compute_final_key_length(-100, 0.05, 0, 0)
        with pytest.raises(ValueError):
            compute_final_key_length(1000, -0.1, 0, 0)
        with pytest.raises(ValueError):
            compute_final_key_length(1000, 0.6, 0, 0)
        with pytest.raises(ValueError):
            compute_final_key_length(1000, 0.05, -10, 0)

    def test_efficiency_factor(self):
        """Test efficiency factor reduces key length."""
        full = compute_final_key_length(10000, 0.05, 500, 64, efficiency_factor=1.0)
        half = compute_final_key_length(10000, 0.05, 500, 64, efficiency_factor=0.5)
        assert half < full


class TestKeyLengthDetailed:
    """Test suite for detailed key length calculation."""

    def test_detailed_result_structure(self):
        """Test that detailed result has all fields."""
        result = compute_final_key_length_detailed(
            reconciled_length=10000,
            qber=0.05,
            leakage_ec=500,
            leakage_ver=64,
        )
        assert isinstance(result, KeyLengthEstimate)
        assert result.final_length >= 0
        assert result.raw_length > 0
        assert result.secrecy_capacity > 0
        assert result.total_leakage > 0
        assert result.is_secure is True
        assert result.qber == 0.05

    def test_detailed_matches_simple(self):
        """Test that detailed and simple functions agree."""
        simple = compute_final_key_length(10000, 0.05, 500, 64)
        detailed = compute_final_key_length_detailed(10000, 0.05, 500, 64)
        assert simple == detailed.final_length

    def test_detailed_insecure_result(self):
        """Test detailed result for insecure QBER."""
        result = compute_final_key_length_detailed(10000, 0.15, 500, 64)
        assert result.final_length == 0
        assert result.is_secure is False
        assert result.qber == 0.15


# =============================================================================
# QBER Estimation Tests
# =============================================================================


class TestQBEREstimation:
    """Test suite for QBER estimation."""

    def test_perfect_sample(self):
        """Test QBER estimation with no errors."""
        alice = [0, 1, 0, 1, 0, 1, 0, 1]
        bob = [0, 1, 0, 1, 0, 1, 0, 1]
        assert estimate_qber_from_sample(alice, bob) == 0.0

    def test_all_errors(self):
        """Test QBER estimation with all errors."""
        alice = [0, 0, 0, 0]
        bob = [1, 1, 1, 1]
        assert estimate_qber_from_sample(alice, bob) == 1.0

    def test_half_errors(self):
        """Test QBER estimation with 50% errors."""
        alice = [0, 0, 1, 1]
        bob = [1, 1, 1, 1]
        assert estimate_qber_from_sample(alice, bob) == 0.5

    def test_known_error_rate(self):
        """Test QBER with known error pattern."""
        alice = [0, 1, 0, 1, 0, 1, 0, 1, 0, 1]
        bob = [1, 1, 0, 1, 0, 1, 0, 1, 0, 1]  # First bit different
        assert estimate_qber_from_sample(alice, bob) == 0.1

    def test_empty_sample_error(self):
        """Test that empty sample raises error."""
        with pytest.raises(ValueError):
            estimate_qber_from_sample([], [])

    def test_mismatched_lengths_error(self):
        """Test that mismatched lengths raise error."""
        with pytest.raises(ValueError):
            estimate_qber_from_sample([0, 1, 0], [0, 1])


class TestCountSampleErrors:
    """Test suite for sample error counting."""

    def test_no_errors(self):
        """Test counting with no errors."""
        assert count_sample_errors([0, 1, 0], [0, 1, 0]) == 0

    def test_all_errors(self):
        """Test counting with all errors."""
        assert count_sample_errors([0, 0, 0], [1, 1, 1]) == 3

    def test_some_errors(self):
        """Test counting with some errors."""
        assert count_sample_errors([0, 1, 0, 1], [0, 0, 1, 1]) == 2


class TestQBERFromCascade:
    """Test suite for combined QBER estimation."""

    def test_combined_estimation(self):
        """Test that sample + cascade errors are combined correctly."""
        qber = estimate_qber_from_cascade(
            total_bits=1000,
            sample_errors=30,
            cascade_errors=20,
        )
        assert qber == 0.05  # (30 + 20) / 1000

    def test_zero_errors(self):
        """Test with zero errors."""
        qber = estimate_qber_from_cascade(1000, 0, 0)
        assert qber == 0.0

    def test_invalid_total_bits(self):
        """Test that invalid total_bits raises error."""
        with pytest.raises(ValueError):
            estimate_qber_from_cascade(0, 5, 5)
        with pytest.raises(ValueError):
            estimate_qber_from_cascade(-100, 5, 5)

    def test_negative_errors(self):
        """Test that negative error counts raise error."""
        with pytest.raises(ValueError):
            estimate_qber_from_cascade(1000, -5, 0)
        with pytest.raises(ValueError):
            estimate_qber_from_cascade(1000, 0, -5)


class TestConfidenceInterval:
    """Test suite for confidence interval calculation."""

    def test_interval_contains_point_estimate(self):
        """Test that interval contains point estimate."""
        lower, upper = compute_confidence_interval(50, 1000, 0.95)
        point = 50 / 1000
        assert lower <= point <= upper

    def test_interval_width_increases_with_confidence(self):
        """Test that higher confidence gives wider interval."""
        ci_95 = compute_confidence_interval(50, 1000, 0.95)
        ci_99 = compute_confidence_interval(50, 1000, 0.99)
        width_95 = ci_95[1] - ci_95[0]
        width_99 = ci_99[1] - ci_99[0]
        assert width_99 > width_95

    def test_interval_width_decreases_with_sample_size(self):
        """Test that larger samples give narrower intervals."""
        ci_small = compute_confidence_interval(50, 500, 0.95)
        ci_large = compute_confidence_interval(100, 1000, 0.95)
        width_small = ci_small[1] - ci_small[0]
        width_large = ci_large[1] - ci_large[0]
        assert width_large < width_small

    def test_interval_at_zero_errors(self):
        """Test interval when no errors observed."""
        lower, upper = compute_confidence_interval(0, 1000, 0.95)
        assert lower == 0.0
        assert upper > 0.0

    def test_interval_at_all_errors(self):
        """Test interval when all bits are errors."""
        lower, upper = compute_confidence_interval(100, 100, 0.95)
        assert lower < 1.0
        assert upper == 1.0

    def test_invalid_parameters(self):
        """Test that invalid parameters raise errors."""
        with pytest.raises(ValueError):
            compute_confidence_interval(-5, 100, 0.95)
        with pytest.raises(ValueError):
            compute_confidence_interval(150, 100, 0.95)  # More errors than samples
        with pytest.raises(ValueError):
            compute_confidence_interval(50, 0, 0.95)


class TestQBERDetailed:
    """Test suite for detailed QBER estimation."""

    def test_detailed_result_structure(self):
        """Test that detailed result has all fields."""
        result = estimate_qber_detailed(1000, 30, 20)
        assert isinstance(result, QBEREstimate)
        assert result.qber == 0.05
        assert result.error_count == 50
        assert result.sample_size == 1000
        assert result.source == "combined"

    def test_sampling_only_source(self):
        """Test source is 'sampling' when no cascade errors."""
        result = estimate_qber_detailed(1000, 30, 0)
        assert result.source == "sampling"

    def test_security_check_secure(self):
        """Test is_secure for secure QBER."""
        result = estimate_qber_detailed(1000, 50, 0)  # 5%
        assert result.is_secure is True

    def test_security_check_insecure(self):
        """Test is_secure for high QBER."""
        result = estimate_qber_detailed(1000, 120, 0)  # 12%
        assert result.is_secure is False


class TestQBERAcceptable:
    """Test suite for QBER acceptability check."""

    def test_acceptable_qber(self):
        """Test that low QBER is acceptable."""
        assert is_qber_acceptable(0.05) is True

    def test_unacceptable_qber(self):
        """Test that high QBER is unacceptable."""
        assert is_qber_acceptable(0.15) is False

    def test_custom_threshold(self):
        """Test with custom threshold."""
        assert is_qber_acceptable(0.05, threshold=0.04) is False


class TestOptimalSampleSize:
    """Test suite for optimal sample size calculation."""

    def test_returns_positive(self):
        """Test that sample size is positive."""
        n = compute_optimal_sample_size(10000)
        assert n > 0

    def test_capped_at_total(self):
        """Test that sample size doesn't exceed total."""
        n = compute_optimal_sample_size(100, target_precision=0.001)
        assert n <= 100

    def test_minimum_size(self):
        """Test minimum sample size."""
        n = compute_optimal_sample_size(10000, target_precision=0.5)
        assert n >= 100  # Minimum threshold


# =============================================================================
# Toeplitz Utilities Tests
# =============================================================================


class TestComputeSeedLength:
    """Test suite for seed length calculation."""

    def test_basic_calculation(self):
        """Test basic seed length calculation."""
        assert compute_seed_length(100, 50) == 149  # 100 + 50 - 1

    def test_equal_lengths(self):
        """Test when input and output are equal."""
        assert compute_seed_length(100, 100) == 199

    def test_minimum_output(self):
        """Test with minimum output length."""
        assert compute_seed_length(100, 1) == 100

    def test_invalid_lengths(self):
        """Test that invalid lengths raise errors."""
        with pytest.raises(ValueError):
            compute_seed_length(0, 50)
        with pytest.raises(ValueError):
            compute_seed_length(50, 0)
        with pytest.raises(ValueError):
            compute_seed_length(50, 100)  # Output > input


class TestGenerateToeplitzSeed:
    """Test suite for Toeplitz seed generation."""

    def test_correct_length(self):
        """Test that generated seed has correct length."""
        seed = generate_toeplitz_seed(100, 50)
        assert len(seed) == 149

    def test_binary_values(self):
        """Test that seed contains only 0s and 1s."""
        seed = generate_toeplitz_seed(100, 50)
        assert all(bit in (0, 1) for bit in seed)

    def test_deterministic_with_seed(self):
        """Test deterministic generation with RNG seed."""
        seed1 = generate_toeplitz_seed(100, 50, rng_seed=42)
        seed2 = generate_toeplitz_seed(100, 50, rng_seed=42)
        assert seed1 == seed2

    def test_different_with_different_seed(self):
        """Test different output with different RNG seed."""
        seed1 = generate_toeplitz_seed(100, 50, rng_seed=42)
        seed2 = generate_toeplitz_seed(100, 50, rng_seed=43)
        assert seed1 != seed2


class TestToeplitzSeedStructured:
    """Test suite for structured Toeplitz seed."""

    def test_structured_seed_fields(self):
        """Test that structured seed has all fields."""
        seed = generate_toeplitz_seed_structured(100, 50, rng_seed=42)
        assert isinstance(seed, ToeplitzSeed)
        assert len(seed.bits) == 149
        assert seed.input_length == 100
        assert seed.output_length == 50
        assert seed.rng_seed == 42

    def test_first_column_property(self):
        """Test first_column property."""
        seed = generate_toeplitz_seed_structured(100, 50, rng_seed=42)
        assert len(seed.first_column) == 50  # Output length

    def test_first_row_property(self):
        """Test first_row property."""
        seed = generate_toeplitz_seed_structured(100, 50, rng_seed=42)
        assert len(seed.first_row) == 100  # Input length


class TestValidateToeplitzSeed:
    """Test suite for Toeplitz seed validation."""

    def test_valid_seed(self):
        """Test validation of valid seed."""
        seed = generate_toeplitz_seed(100, 50)
        assert validate_toeplitz_seed(seed, 100, 50) is True

    def test_wrong_length(self):
        """Test rejection of wrong length seed."""
        seed = [0, 1] * 50  # Length 100, not 149
        assert validate_toeplitz_seed(seed, 100, 50) is False

    def test_invalid_values(self):
        """Test rejection of non-binary values."""
        seed = [0, 1, 2] + [0] * 146
        assert validate_toeplitz_seed(seed, 100, 50) is False


class TestConstructToeplitzMatrix:
    """Test suite for Toeplitz matrix construction."""

    def test_matrix_dimensions(self):
        """Test that matrix has correct dimensions."""
        seed = generate_toeplitz_seed(10, 5, rng_seed=42)
        matrix = construct_toeplitz_matrix(seed, 5, 10)
        assert matrix.shape == (5, 10)

    def test_toeplitz_structure(self):
        """Test that matrix has Toeplitz structure (constant diagonals)."""
        seed = generate_toeplitz_seed(10, 5, rng_seed=42)
        matrix = construct_toeplitz_matrix(seed, 5, 10)
        # Check main diagonal is constant
        for i in range(min(4, 9)):
            assert matrix[i + 1, i + 1] == matrix[0, 0] or matrix.shape[0] <= 1

    def test_first_column_matches_seed(self):
        """Test that first column matches seed."""
        seed = generate_toeplitz_seed(10, 5, rng_seed=42)
        matrix = construct_toeplitz_matrix(seed, 5, 10)
        assert list(matrix[:, 0]) == seed[:5]

    def test_invalid_seed_length(self):
        """Test that wrong seed length raises error."""
        seed = [0, 1] * 5  # Wrong length
        with pytest.raises(ValueError):
            construct_toeplitz_matrix(seed, 5, 10)


class TestConstructToeplitzMatrixNumpy:
    """Test suite for pure NumPy Toeplitz construction."""

    def test_correct_dimensions(self):
        """Test that NumPy version produces correct dimensions."""
        seed = generate_toeplitz_seed(10, 5, rng_seed=42)
        numpy_matrix = construct_toeplitz_matrix_numpy(seed, 5, 10)
        assert numpy_matrix.shape == (5, 10)

    def test_correct_dtype(self):
        """Test that result has correct dtype."""
        seed = generate_toeplitz_seed(10, 5, rng_seed=42)
        matrix = construct_toeplitz_matrix_numpy(seed, 5, 10)
        assert matrix.dtype == np.uint8

    def test_toeplitz_property(self):
        """Test that matrix has Toeplitz property (constant diagonals)."""
        seed = generate_toeplitz_seed(10, 5, rng_seed=42)
        matrix = construct_toeplitz_matrix_numpy(seed, 5, 10)
        # Each diagonal should be constant
        for d in range(-4, 10):
            diagonal = np.diag(matrix, d)
            if len(diagonal) > 1:
                assert all(diagonal == diagonal[0]), f"Diagonal {d} not constant"


class TestToeplitzMultiply:
    """Test suite for Toeplitz matrix multiplication."""

    def test_multiplication_mod_2(self):
        """Test that multiplication is performed mod 2."""
        matrix = np.array([[1, 1], [1, 0]], dtype=np.uint8)
        vector = np.array([1, 1], dtype=np.uint8)
        result = toeplitz_multiply(matrix, vector)
        # [1*1 + 1*1, 1*1 + 0*1] = [2, 1] mod 2 = [0, 1]
        np.testing.assert_array_equal(result, [0, 1])

    def test_result_binary(self):
        """Test that result contains only 0s and 1s."""
        seed = generate_toeplitz_seed(10, 5, rng_seed=42)
        matrix = construct_toeplitz_matrix(seed, 5, 10)
        vector = np.array([1, 0, 1, 0, 1, 0, 1, 0, 1, 0], dtype=np.uint8)
        result = toeplitz_multiply(matrix, vector)
        assert all(r in (0, 1) for r in result)


class TestExtractToeplitzComponents:
    """Test suite for component extraction."""

    def test_correct_lengths(self):
        """Test that extracted components have correct lengths."""
        seed = generate_toeplitz_seed(10, 5, rng_seed=42)
        col, row = extract_toeplitz_components(seed, 5, 10)
        assert len(col) == 5  # num_rows
        assert len(row) == 10  # num_cols

    def test_components_from_seed(self):
        """Test that components match seed."""
        seed = generate_toeplitz_seed(10, 5, rng_seed=42)
        col, row = extract_toeplitz_components(seed, 5, 10)
        assert col == seed[:5]


class TestBitsBytes:
    """Test suite for bit/byte conversion."""

    def test_bits_to_bytes_roundtrip(self):
        """Test that bits_to_bytes and bytes_to_bits are inverses."""
        original = [1, 0, 1, 1, 0, 0, 1, 0]  # 8 bits
        converted = bits_to_bytes(original)
        recovered = bytes_to_bits(converted, len(original))
        assert recovered == original

    def test_bits_to_bytes_value(self):
        """Test specific bit pattern."""
        bits = [1, 0, 1, 1, 0, 0, 1, 0]  # 0b10110010 = 178
        result = bits_to_bytes(bits)
        assert result == bytes([178])

    def test_bytes_to_bits_value(self):
        """Test specific byte value."""
        data = bytes([178])  # 0b10110010
        bits = bytes_to_bits(data)
        assert bits == [1, 0, 1, 1, 0, 0, 1, 0]

    def test_padding(self):
        """Test that non-multiple-of-8 bits are padded."""
        bits = [1, 0, 1]  # 3 bits
        result = bits_to_bytes(bits)
        assert len(result) == 1


# =============================================================================
# Privacy Amplifier Tests
# =============================================================================


class TestPrivacyAmplifier:
    """Test suite for PrivacyAmplifier class."""

    def test_initialization(self):
        """Test amplifier initialization."""
        amp = PrivacyAmplifier()
        assert amp.epsilon_sec == 1e-12

    def test_initialization_custom_epsilon(self):
        """Test amplifier with custom epsilon."""
        amp = PrivacyAmplifier(epsilon_sec=1e-6)
        assert amp.epsilon_sec == 1e-6

    def test_invalid_epsilon(self):
        """Test that invalid epsilon raises error."""
        with pytest.raises(ValueError):
            PrivacyAmplifier(epsilon_sec=0)
        with pytest.raises(ValueError):
            PrivacyAmplifier(epsilon_sec=2)

    def test_compute_output_length(self, deterministic_amplifier):
        """Test output length computation."""
        length = deterministic_amplifier.compute_output_length(
            input_length=10000,
            qber=0.05,
            leakage_ec=500,
            leakage_ver=64,
        )
        assert length > 0
        assert length < 10000

    def test_generate_seed(self, deterministic_amplifier):
        """Test seed generation."""
        seed = deterministic_amplifier.generate_seed(100, 50)
        assert len(seed) == 149
        assert all(bit in (0, 1) for bit in seed)


class TestAmplify:
    """Test suite for amplify method."""

    def test_output_length(self, small_key, deterministic_amplifier):
        """Test that output has requested length."""
        seed = generate_toeplitz_seed(len(small_key), 8, rng_seed=42)
        result = deterministic_amplifier.amplify(small_key, seed, 8)
        assert len(result) == 8

    def test_binary_output(self, small_key, deterministic_amplifier):
        """Test that output contains only binary values."""
        seed = generate_toeplitz_seed(len(small_key), 8, rng_seed=42)
        result = deterministic_amplifier.amplify(small_key, seed, 8)
        assert all(bit in (0, 1) for bit in result)

    def test_deterministic(self, small_key, deterministic_amplifier):
        """Test that same seed produces same output."""
        seed = generate_toeplitz_seed(len(small_key), 8, rng_seed=42)
        result1 = deterministic_amplifier.amplify(small_key, seed, 8)
        result2 = deterministic_amplifier.amplify(small_key, seed, 8)
        assert result1 == result2

    def test_different_keys_different_output(self, deterministic_amplifier):
        """Test that different keys produce different outputs."""
        key1 = [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1]
        key2 = [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0]
        seed = generate_toeplitz_seed(16, 8, rng_seed=42)
        result1 = deterministic_amplifier.amplify(key1, seed, 8)
        result2 = deterministic_amplifier.amplify(key2, seed, 8)
        assert result1 != result2

    def test_empty_key_error(self, deterministic_amplifier):
        """Test that empty key raises error."""
        with pytest.raises(ValueError):
            deterministic_amplifier.amplify([], [0, 1, 0], 2)

    def test_invalid_output_length(self, small_key, deterministic_amplifier):
        """Test that invalid output length raises error."""
        seed = generate_toeplitz_seed(len(small_key), 8, rng_seed=42)
        with pytest.raises(ValueError):
            deterministic_amplifier.amplify(small_key, seed, 0)
        with pytest.raises(ValueError):
            deterministic_amplifier.amplify(small_key, seed, 100)  # > input length

    def test_invalid_seed_length(self, small_key, deterministic_amplifier):
        """Test that wrong seed length raises error."""
        seed = [0, 1, 0]  # Too short
        with pytest.raises(ValueError):
            deterministic_amplifier.amplify(small_key, seed, 8)


class TestAmplifyWithResult:
    """Test suite for amplify_with_result method."""

    def test_successful_amplification(self, sample_key, deterministic_amplifier):
        """Test successful amplification with result."""
        result = deterministic_amplifier.amplify_with_result(
            key=sample_key,
            qber=0.05,
            leakage_ec=50,
            leakage_ver=64,
        )
        assert isinstance(result, AmplificationResult)
        assert result.success is True
        assert len(result.secret_key) > 0
        assert len(result.secret_key) == result.output_length
        assert result.input_length == len(sample_key)
        assert 0 < result.compression_ratio < 1

    def test_failure_high_qber(self, sample_key, deterministic_amplifier):
        """Test failure due to high QBER."""
        result = deterministic_amplifier.amplify_with_result(
            key=sample_key,
            qber=0.15,  # Above threshold
            leakage_ec=50,
            leakage_ver=64,
        )
        assert result.success is False
        assert len(result.secret_key) == 0
        assert "threshold" in result.error_message.lower()

    def test_with_provided_seed(self, sample_key, deterministic_amplifier):
        """Test amplification with pre-shared seed."""
        # First compute the output length
        output_length = deterministic_amplifier.compute_output_length(
            len(sample_key), 0.05, 50, 64
        )
        seed = generate_toeplitz_seed(len(sample_key), output_length, rng_seed=123)

        result = deterministic_amplifier.amplify_with_result(
            key=sample_key,
            qber=0.05,
            leakage_ec=50,
            leakage_ver=64,
            toeplitz_seed=seed,
        )
        assert result.success is True
        assert result.toeplitz_seed == seed


class TestAmplifyFixedLength:
    """Test suite for amplify_fixed_length method."""

    def test_returns_tuple(self, small_key, deterministic_amplifier):
        """Test that method returns (key, seed) tuple."""
        result = deterministic_amplifier.amplify_fixed_length(small_key, 8)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert len(result[0]) == 8  # Secret key
        assert len(result[1]) == len(small_key) + 8 - 1  # Seed

    def test_with_provided_seed(self, small_key, deterministic_amplifier):
        """Test with provided seed."""
        seed = generate_toeplitz_seed(len(small_key), 8, rng_seed=42)
        result_key, result_seed = deterministic_amplifier.amplify_fixed_length(
            small_key, 8, toeplitz_seed=seed
        )
        assert result_seed == seed


class TestApplyPrivacyAmplification:
    """Test suite for convenience function."""

    def test_convenience_function(self, sample_key):
        """Test that convenience function works."""
        result = apply_privacy_amplification(
            key=sample_key,
            qber=0.05,
            leakage_ec=50,
            leakage_ver=64,
        )
        assert isinstance(result, AmplificationResult)
        assert result.success is True

    def test_custom_epsilon(self, sample_key):
        """Test with custom security parameter."""
        result = apply_privacy_amplification(
            key=sample_key,
            qber=0.05,
            leakage_ec=50,
            leakage_ver=64,
            epsilon_sec=1e-6,
        )
        assert result.security_parameter == 1e-6


# =============================================================================
# Integration-style Unit Tests
# =============================================================================


class TestPrivacyAmplificationIntegration:
    """Integration-style tests for privacy amplification flow."""

    def test_full_flow_low_qber(self):
        """Test complete flow with low QBER."""
        # Generate "reconciled" key
        random.seed(42)
        key = [random.randint(0, 1) for _ in range(5000)]

        # Apply privacy amplification
        amplifier = PrivacyAmplifier(epsilon_sec=1e-12, rng_seed=42)
        result = amplifier.amplify_with_result(
            key=key,
            qber=0.03,
            leakage_ec=200,
            leakage_ver=64,
        )

        assert result.success is True
        assert len(result.secret_key) > 0
        assert result.compression_ratio > 0.5  # Low QBER = good compression

    def test_full_flow_moderate_qber(self):
        """Test complete flow with moderate QBER."""
        random.seed(42)
        key = [random.randint(0, 1) for _ in range(5000)]

        amplifier = PrivacyAmplifier(epsilon_sec=1e-12, rng_seed=42)
        result = amplifier.amplify_with_result(
            key=key,
            qber=0.08,
            leakage_ec=400,
            leakage_ver=64,
        )

        assert result.success is True
        assert len(result.secret_key) > 0
        assert result.compression_ratio < 0.5  # Higher QBER = more compression

    def test_consistent_output_same_inputs(self):
        """Test that same inputs produce same outputs."""
        key = [0, 1] * 500

        amp1 = PrivacyAmplifier(rng_seed=42)
        amp2 = PrivacyAmplifier(rng_seed=42)

        result1 = amp1.amplify_with_result(key, 0.05, 50, 64)
        result2 = amp2.amplify_with_result(key, 0.05, 50, 64)

        assert result1.secret_key == result2.secret_key

    def test_key_compression_ratio_bounds(self):
        """Test that compression ratio is reasonable."""
        key = [random.randint(0, 1) for _ in range(10000)]

        for qber in [0.01, 0.03, 0.05, 0.07, 0.09]:
            result = apply_privacy_amplification(
                key=key,
                qber=qber,
                leakage_ec=500,
                leakage_ver=64,
            )
            if result.success:
                # Compression ratio should be related to secrecy capacity
                expected_max = 1 - binary_entropy(qber)
                assert result.compression_ratio < expected_max + 0.1


class TestStatisticalProperties:
    """Test statistical properties of privacy amplification."""

    def test_output_uniformity_chi_square(self):
        """Test that output bits are approximately uniform."""
        key = [random.randint(0, 1) for _ in range(10000)]
        amplifier = PrivacyAmplifier(rng_seed=None)  # Random seed

        # Collect many output bits
        all_bits = []
        for _ in range(10):
            result = amplifier.amplify_with_result(key, 0.05, 100, 64)
            if result.success:
                all_bits.extend(result.secret_key)

        if len(all_bits) > 100:
            # Chi-square test for uniformity
            zeros = all_bits.count(0)
            ones = all_bits.count(1)
            total = zeros + ones
            expected = total / 2

            chi_square = ((zeros - expected) ** 2 + (ones - expected) ** 2) / expected
            # For 1 degree of freedom, chi-square < 6.63 at 99% confidence
            assert chi_square < 10  # Conservative threshold

    def test_different_keys_produce_different_outputs(self):
        """Test that different keys produce different outputs."""
        # Use non-deterministic amplifier for variety
        amplifier = PrivacyAmplifier(rng_seed=None)

        outputs = set()
        for i in range(20):
            # Generate distinctly different keys
            random.seed(i * 1000)
            key = [random.randint(0, 1) for _ in range(1000)]
            result = amplifier.amplify_with_result(key, 0.05, 50, 64)
            if result.success:
                outputs.add(tuple(result.secret_key))

        # With random seeds, all outputs should be different
        assert len(outputs) >= 10
