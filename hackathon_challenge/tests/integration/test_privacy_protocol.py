"""Integration tests for privacy amplification protocol.

This module tests the complete privacy amplification workflow including
QBER estimation, key length calculation, and Toeplitz-based hashing.

Tests simulate realistic QKD scenarios where Alice and Bob need to
transform a reconciled key into a shorter but fully secret key.

Reference: implementation_plan.md §Phase 4 (Integration Tests)
"""

import random
from typing import List, Tuple

import numpy as np
import pytest

from hackathon_challenge.privacy.entropy import (
    QBER_THRESHOLD,
    KeyLengthEstimate,
    binary_entropy,
    compute_final_key_length,
    compute_final_key_length_detailed,
    is_qber_secure,
    secrecy_capacity,
)
from hackathon_challenge.privacy.estimation import (
    QBEREstimate,
    compute_confidence_interval,
    estimate_qber_detailed,
    estimate_qber_from_cascade,
    estimate_qber_from_sample,
    is_qber_acceptable,
)
from hackathon_challenge.privacy.amplifier import (
    AmplificationResult,
    PrivacyAmplifier,
    apply_privacy_amplification,
)
from hackathon_challenge.privacy.utils import (
    generate_toeplitz_seed,
    validate_toeplitz_seed,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def realistic_qkd_scenario() -> dict:
    """Create a realistic QKD scenario with parameters."""
    return {
        "sifted_key_length": 10000,
        "qber": 0.05,
        "leakage_ec": 500,
        "leakage_ver": 64,
        "epsilon_sec": 1e-12,
    }


@pytest.fixture
def low_qber_scenario() -> dict:
    """Scenario with very low QBER (ideal conditions)."""
    return {
        "sifted_key_length": 10000,
        "qber": 0.01,
        "leakage_ec": 200,
        "leakage_ver": 64,
        "epsilon_sec": 1e-12,
    }


@pytest.fixture
def high_qber_scenario() -> dict:
    """Scenario with high QBER (near threshold)."""
    return {
        "sifted_key_length": 10000,
        "qber": 0.10,
        "leakage_ec": 800,
        "leakage_ver": 64,
        "epsilon_sec": 1e-12,
    }


@pytest.fixture
def above_threshold_scenario() -> dict:
    """Scenario with QBER above security threshold."""
    return {
        "sifted_key_length": 10000,
        "qber": 0.15,
        "leakage_ec": 1000,
        "leakage_ver": 64,
        "epsilon_sec": 1e-12,
    }


def generate_reconciled_key_pair(
    length: int,
    qber: float,
    rng_seed: int = 42,
) -> Tuple[List[int], List[int]]:
    """Generate a pair of reconciled keys with specified residual error rate.

    Parameters
    ----------
    length : int
        Key length.
    qber : float
        Residual error rate (should be very small after reconciliation).
    rng_seed : int
        Random seed for reproducibility.

    Returns
    -------
    Tuple[List[int], List[int]]
        (alice_key, bob_key) pair.

    Notes
    -----
    In a real QKD system, after reconciliation the keys should be identical.
    Here we simulate a small residual error rate for testing purposes.
    """
    rng = random.Random(rng_seed)
    alice_key = [rng.randint(0, 1) for _ in range(length)]

    # Bob's key differs at random positions based on QBER
    bob_key = alice_key.copy()
    num_errors = int(length * qber)
    error_positions = rng.sample(range(length), min(num_errors, length))
    for pos in error_positions:
        bob_key[pos] = 1 - bob_key[pos]

    return alice_key, bob_key


# =============================================================================
# End-to-End Protocol Tests
# =============================================================================


class TestCompletePrivacyAmplificationProtocol:
    """Test complete privacy amplification protocol flow."""

    def test_full_protocol_success(self, realistic_qkd_scenario):
        """Test successful completion of full protocol."""
        params = realistic_qkd_scenario

        # Step 1: Generate reconciled keys (identical in practice)
        alice_key = [random.randint(0, 1) for _ in range(params["sifted_key_length"])]
        bob_key = alice_key.copy()  # After successful reconciliation

        # Step 2: Estimate QBER (from reconciliation data)
        qber_estimate = estimate_qber_detailed(
            total_bits=params["sifted_key_length"],
            sample_errors=int(params["qber"] * params["sifted_key_length"] * 0.1),
            cascade_errors=int(params["qber"] * params["sifted_key_length"] * 0.9),
        )

        assert qber_estimate.is_secure

        # Step 3: Compute expected key length
        expected_length = compute_final_key_length(
            reconciled_length=len(alice_key),
            qber=params["qber"],
            leakage_ec=params["leakage_ec"],
            leakage_ver=params["leakage_ver"],
            epsilon_sec=params["epsilon_sec"],
        )

        assert expected_length > 0

        # Step 4: Generate shared Toeplitz seed
        shared_seed = generate_toeplitz_seed(
            len(alice_key), expected_length, rng_seed=12345
        )

        # Step 5: Both parties apply privacy amplification
        amplifier = PrivacyAmplifier(epsilon_sec=params["epsilon_sec"])

        alice_secret = amplifier.amplify(alice_key, shared_seed, expected_length)
        bob_secret = amplifier.amplify(bob_key, shared_seed, expected_length)

        # Step 6: Verify both parties have identical keys
        assert alice_secret == bob_secret
        assert len(alice_secret) == expected_length

    def test_protocol_with_amplify_with_result(self, realistic_qkd_scenario):
        """Test protocol using high-level amplify_with_result interface."""
        params = realistic_qkd_scenario

        # Generate key
        key = [random.randint(0, 1) for _ in range(params["sifted_key_length"])]

        # Apply privacy amplification with full result
        result = apply_privacy_amplification(
            key=key,
            qber=params["qber"],
            leakage_ec=params["leakage_ec"],
            leakage_ver=params["leakage_ver"],
            epsilon_sec=params["epsilon_sec"],
        )

        # Verify result
        assert result.success
        assert len(result.secret_key) == result.output_length
        assert result.input_length == len(key)
        assert 0 < result.compression_ratio < 1
        assert result.qber == params["qber"]

    def test_protocol_aborts_high_qber(self, above_threshold_scenario):
        """Test that protocol aborts when QBER exceeds threshold."""
        params = above_threshold_scenario

        key = [random.randint(0, 1) for _ in range(params["sifted_key_length"])]

        result = apply_privacy_amplification(
            key=key,
            qber=params["qber"],
            leakage_ec=params["leakage_ec"],
            leakage_ver=params["leakage_ver"],
        )

        assert not result.success
        assert len(result.secret_key) == 0
        assert "threshold" in result.error_message.lower()


class TestAliceBobSynchronization:
    """Test that Alice and Bob remain synchronized throughout protocol."""

    def test_identical_output_same_seed(self):
        """Test that Alice and Bob get identical keys with same seed."""
        key_length = 5000
        alice_key = [random.randint(0, 1) for _ in range(key_length)]
        bob_key = alice_key.copy()

        output_length = 2000
        shared_seed = generate_toeplitz_seed(key_length, output_length, rng_seed=42)

        alice_amp = PrivacyAmplifier(rng_seed=42)
        bob_amp = PrivacyAmplifier(rng_seed=42)

        alice_secret = alice_amp.amplify(alice_key, shared_seed, output_length)
        bob_secret = bob_amp.amplify(bob_key, shared_seed, output_length)

        assert alice_secret == bob_secret

    def test_different_output_different_seed(self):
        """Test that different seeds produce different outputs."""
        key = [random.randint(0, 1) for _ in range(5000)]
        output_length = 2000

        seed1 = generate_toeplitz_seed(len(key), output_length, rng_seed=42)
        seed2 = generate_toeplitz_seed(len(key), output_length, rng_seed=43)

        amplifier = PrivacyAmplifier()
        result1 = amplifier.amplify(key, seed1, output_length)
        result2 = amplifier.amplify(key, seed2, output_length)

        assert result1 != result2

    def test_residual_errors_produce_different_keys(self):
        """Test that residual errors in reconciliation lead to different final keys."""
        key_length = 5000
        alice_key = [random.randint(0, 1) for _ in range(key_length)]

        # Bob's key has one bit error (undetected by verification)
        bob_key = alice_key.copy()
        bob_key[2500] = 1 - bob_key[2500]

        output_length = 2000
        shared_seed = generate_toeplitz_seed(key_length, output_length, rng_seed=42)

        amplifier = PrivacyAmplifier()
        alice_secret = amplifier.amplify(alice_key, shared_seed, output_length)
        bob_secret = amplifier.amplify(bob_key, shared_seed, output_length)

        # Keys should differ due to amplification spreading errors
        assert alice_secret != bob_secret


class TestQBERImpactOnKeyLength:
    """Test the impact of QBER on final key length."""

    def test_key_length_vs_qber_relationship(self):
        """Test that key length decreases with increasing QBER."""
        input_length = 10000
        leakage_ec = 500
        leakage_ver = 64

        qber_values = [0.01, 0.03, 0.05, 0.07, 0.09]
        lengths = []

        for qber in qber_values:
            length = compute_final_key_length(
                reconciled_length=input_length,
                qber=qber,
                leakage_ec=leakage_ec,
                leakage_ver=leakage_ver,
            )
            lengths.append(length)

        # Each length should be less than the previous
        for i in range(len(lengths) - 1):
            assert lengths[i] > lengths[i + 1], (
                f"Length at QBER={qber_values[i]} ({lengths[i]}) "
                f"should be > length at QBER={qber_values[i+1]} ({lengths[i+1]})"
            )

    def test_key_length_at_threshold(self):
        """Test key length behavior at security threshold."""
        input_length = 10000

        # Just below threshold
        length_below = compute_final_key_length(
            reconciled_length=input_length,
            qber=0.109,
            leakage_ec=500,
            leakage_ver=64,
        )

        # At threshold
        length_at = compute_final_key_length(
            reconciled_length=input_length,
            qber=0.11,
            leakage_ec=500,
            leakage_ver=64,
        )

        assert length_below > 0
        assert length_at == 0

    def test_efficiency_vs_input_length(self):
        """Test compression efficiency for different input lengths."""
        qber = 0.05
        leakage_ec = 500
        leakage_ver = 64

        input_lengths = [1000, 5000, 10000, 50000]
        efficiencies = []

        for n in input_lengths:
            output_length = compute_final_key_length(
                reconciled_length=n,
                qber=qber,
                leakage_ec=leakage_ec,
                leakage_ver=leakage_ver,
            )
            efficiency = output_length / n if output_length > 0 else 0
            efficiencies.append(efficiency)

        # Efficiency should improve with larger keys (fixed overhead amortized)
        for i in range(len(efficiencies) - 1):
            if efficiencies[i] > 0 and efficiencies[i + 1] > 0:
                assert efficiencies[i + 1] >= efficiencies[i] - 0.01  # Allow small tolerance


class TestQBEREstimationIntegration:
    """Test QBER estimation integration with privacy amplification."""

    def test_estimation_from_cascade_data(self):
        """Test QBER estimation using Cascade reconciliation data."""
        total_bits = 10000
        sample_errors = 50  # 0.5% from sampling
        cascade_errors = 450  # 4.5% from Cascade

        qber = estimate_qber_from_cascade(total_bits, sample_errors, cascade_errors)

        assert qber == pytest.approx(0.05, abs=1e-10)
        assert is_qber_acceptable(qber)

    def test_detailed_estimation_for_decision(self):
        """Test using detailed estimation for protocol decisions."""
        estimate = estimate_qber_detailed(
            total_bits=10000,
            sample_errors=50,
            cascade_errors=450,
        )

        # Use confidence interval for conservative decision
        if estimate.confidence_interval[1] < QBER_THRESHOLD:
            # Safe to proceed
            key_length = compute_final_key_length(
                reconciled_length=10000,
                qber=estimate.qber,
                leakage_ec=500,
                leakage_ver=64,
            )
            assert key_length > 0
        else:
            # May need to abort
            pass

    def test_sample_based_vs_cascade_based_estimation(self):
        """Compare sample-based and Cascade-based QBER estimates."""
        # Sample-based estimation (before reconciliation)
        alice_sample = [0, 1, 0, 1, 0, 1, 0, 1, 0, 1] * 100
        bob_sample = alice_sample.copy()
        # Introduce 5% errors
        for i in range(50):
            bob_sample[i * 20] = 1 - bob_sample[i * 20]

        sample_qber = estimate_qber_from_sample(alice_sample, bob_sample)

        # Cascade-based estimation (after reconciliation)
        cascade_qber = estimate_qber_from_cascade(
            total_bits=10000,
            sample_errors=50,
            cascade_errors=450,
        )

        assert sample_qber == pytest.approx(0.05, abs=0.01)
        assert cascade_qber == pytest.approx(0.05, abs=0.01)


class TestSecurityProperties:
    """Test security properties of privacy amplification."""

    def test_output_entropy(self):
        """Test that output has high entropy (appears random)."""
        key = [random.randint(0, 1) for _ in range(10000)]

        result = apply_privacy_amplification(
            key=key,
            qber=0.05,
            leakage_ec=500,
            leakage_ver=64,
        )

        if result.success:
            # Count zeros and ones
            zeros = result.secret_key.count(0)
            ones = result.secret_key.count(1)
            total = zeros + ones

            # Should be approximately balanced (within 10%)
            balance = min(zeros, ones) / max(zeros, ones)
            assert balance > 0.8, f"Unbalanced output: {zeros} zeros, {ones} ones"

    def test_independence_from_input_pattern(self):
        """Test that output doesn't reveal input pattern."""
        output_length = 2000
        seed = generate_toeplitz_seed(5000, output_length, rng_seed=42)
        amplifier = PrivacyAmplifier()

        # Try different inputs with varying structure
        random.seed(42)
        random_key = [random.randint(0, 1) for _ in range(5000)]
        alternating = [i % 2 for i in range(5000)]
        blocks = [0] * 2500 + [1] * 2500

        result_random = amplifier.amplify(random_key, seed, output_length)
        result_alt = amplifier.amplify(alternating, seed, output_length)
        result_blocks = amplifier.amplify(blocks, seed, output_length)

        # Results should be different
        assert result_random != result_alt
        assert result_random != result_blocks
        assert result_alt != result_blocks

        # Random input should have reasonable balance
        zeros = result_random.count(0)
        ones = result_random.count(1)
        balance = min(zeros, ones) / max(zeros, ones) if max(zeros, ones) > 0 else 0
        assert balance > 0.5, f"Random input output too unbalanced: {zeros} zeros, {ones} ones"

        # Note: All-zeros/all-ones inputs produce deterministic outputs based on seed
        # This is expected behavior - the Toeplitz matrix multiplication of zeros is zeros
        # Real reconciled keys are never all-zeros/all-ones

    def test_toeplitz_seed_security(self):
        """Test that seed must be shared securely for protocol to work."""
        key = [random.randint(0, 1) for _ in range(5000)]
        output_length = 2000

        amplifier = PrivacyAmplifier()

        # Alice's seed (should be shared with Bob)
        alice_seed = generate_toeplitz_seed(len(key), output_length, rng_seed=42)

        # Eve guesses a different seed
        eve_seed = generate_toeplitz_seed(len(key), output_length, rng_seed=999)

        alice_result = amplifier.amplify(key, alice_seed, output_length)
        eve_result = amplifier.amplify(key, eve_seed, output_length)

        # Eve's result differs significantly
        matches = sum(a == e for a, e in zip(alice_result, eve_result))
        match_rate = matches / output_length

        # Should be close to 0.5 (random guessing)
        assert 0.4 < match_rate < 0.6, f"Match rate {match_rate} suggests correlation"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_minimum_viable_key_length(self):
        """Test protocol with minimum viable key length."""
        # Very short key - may not produce output
        key = [random.randint(0, 1) for _ in range(200)]

        result = apply_privacy_amplification(
            key=key,
            qber=0.05,
            leakage_ec=50,
            leakage_ver=32,
        )

        # Small key with overhead may result in zero output
        if result.success:
            assert len(result.secret_key) > 0
        else:
            assert result.output_length == 0

    def test_zero_leakage(self):
        """Test protocol with no information leakage."""
        key = [random.randint(0, 1) for _ in range(10000)]

        result = apply_privacy_amplification(
            key=key,
            qber=0.05,
            leakage_ec=0,
            leakage_ver=0,
        )

        # Should have maximum possible output
        assert result.success
        expected_max = int(len(key) * secrecy_capacity(0.05))
        assert result.output_length > expected_max - 100

    def test_high_leakage(self):
        """Test protocol with high information leakage."""
        key = [random.randint(0, 1) for _ in range(10000)]

        result = apply_privacy_amplification(
            key=key,
            qber=0.05,
            leakage_ec=5000,  # 50% leakage
            leakage_ver=1000,
        )

        # High leakage should result in small or zero output
        assert result.output_length < 2000

    def test_different_security_parameters(self):
        """Test with different security parameters."""
        key = [random.randint(0, 1) for _ in range(10000)]

        result_high_sec = apply_privacy_amplification(
            key=key,
            qber=0.05,
            leakage_ec=500,
            leakage_ver=64,
            epsilon_sec=1e-15,  # Higher security
        )

        result_low_sec = apply_privacy_amplification(
            key=key,
            qber=0.05,
            leakage_ec=500,
            leakage_ver=64,
            epsilon_sec=1e-6,  # Lower security
        )

        # Higher security should produce shorter key
        assert result_high_sec.output_length < result_low_sec.output_length


class TestRealisticScenarios:
    """Test with realistic QKD scenarios."""

    def test_ideal_channel_scenario(self, low_qber_scenario):
        """Test ideal channel with minimal errors."""
        params = low_qber_scenario
        key = [random.randint(0, 1) for _ in range(params["sifted_key_length"])]

        result = apply_privacy_amplification(
            key=key,
            qber=params["qber"],
            leakage_ec=params["leakage_ec"],
            leakage_ver=params["leakage_ver"],
        )

        assert result.success
        # Low QBER should give good compression ratio
        assert result.compression_ratio > 0.8

    def test_noisy_channel_scenario(self, high_qber_scenario):
        """Test noisy channel near threshold."""
        params = high_qber_scenario
        key = [random.randint(0, 1) for _ in range(params["sifted_key_length"])]

        result = apply_privacy_amplification(
            key=key,
            qber=params["qber"],
            leakage_ec=params["leakage_ec"],
            leakage_ver=params["leakage_ver"],
        )

        # Near threshold - may still succeed but with low compression
        if result.success:
            assert result.compression_ratio < 0.5

    def test_eavesdropping_detection_scenario(self, above_threshold_scenario):
        """Test detection of potential eavesdropping (high QBER)."""
        params = above_threshold_scenario

        # High QBER indicates potential eavesdropping
        assert not is_qber_secure(params["qber"])

        # Detailed estimation for logging
        estimate = estimate_qber_detailed(
            total_bits=params["sifted_key_length"],
            sample_errors=int(params["qber"] * params["sifted_key_length"]),
            cascade_errors=0,
        )

        assert not estimate.is_secure
        assert estimate.confidence_interval[0] > QBER_THRESHOLD

    def test_multiple_rounds_scenario(self):
        """Test multiple rounds of key generation."""
        results = []
        for round_num in range(5):
            key = [random.randint(0, 1) for _ in range(5000)]
            qber = 0.03 + 0.01 * random.random()  # 3-4%

            result = apply_privacy_amplification(
                key=key,
                qber=qber,
                leakage_ec=250,
                leakage_ver=64,
            )

            results.append(result)

        # All rounds should succeed
        assert all(r.success for r in results)

        # Output lengths should be similar
        lengths = [r.output_length for r in results]
        avg_length = sum(lengths) / len(lengths)
        for length in lengths:
            assert abs(length - avg_length) < 0.2 * avg_length


class TestProtocolDeterminism:
    """Test deterministic behavior of protocol."""

    def test_reproducibility_with_seed(self):
        """Test that protocol is reproducible with fixed seed."""
        key = [random.randint(0, 1) for _ in range(5000)]

        # First run
        amp1 = PrivacyAmplifier(epsilon_sec=1e-12, rng_seed=42)
        result1 = amp1.amplify_with_result(key, 0.05, 250, 64)

        # Second run with same seed
        amp2 = PrivacyAmplifier(epsilon_sec=1e-12, rng_seed=42)
        result2 = amp2.amplify_with_result(key, 0.05, 250, 64)

        assert result1.secret_key == result2.secret_key
        assert result1.toeplitz_seed == result2.toeplitz_seed

    def test_variability_without_seed(self):
        """Test that protocol varies without fixed seed."""
        key = [random.randint(0, 1) for _ in range(5000)]

        results = []
        for _ in range(5):
            amp = PrivacyAmplifier(epsilon_sec=1e-12, rng_seed=None)
            result = amp.amplify_with_result(key, 0.05, 250, 64)
            if result.success:
                results.append(tuple(result.secret_key))

        # Results should be different
        assert len(set(results)) > 1
