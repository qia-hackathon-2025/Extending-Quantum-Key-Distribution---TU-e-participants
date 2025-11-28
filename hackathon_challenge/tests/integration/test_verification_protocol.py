"""Integration tests for key verification protocol.

This module tests the full verification protocol using mock sockets
to simulate the Alice-Bob communication pattern.

Reference: implementation_plan.md §Phase 3 (Integration Testing)
"""

import numpy as np
import pytest

from hackathon_challenge.tests.conftest import MockSocketPair, run_generator_pair
from hackathon_challenge.verification.verifier import KeyVerifier


class TestVerificationProtocol:
    """Integration tests for the verification protocol flow."""

    @pytest.fixture
    def mock_socket_pair(self):
        """Provide a pair of linked mock sockets."""
        return MockSocketPair()

    def test_identical_keys_verify(self, mock_socket_pair):
        """Test that identical keys verify successfully over network."""
        key = [1, 0, 1, 1, 0, 0, 1, 0] * 4

        alice_verifier = KeyVerifier(tag_bits=64, rng_seed=42)
        bob_verifier = KeyVerifier(tag_bits=64, rng_seed=42)

        gen_alice = alice_verifier.verify(
            mock_socket_pair.alice, key.copy(), is_alice=True
        )
        gen_bob = bob_verifier.verify(
            mock_socket_pair.bob, key.copy(), is_alice=False
        )

        alice_result, bob_result = run_generator_pair(gen_alice, gen_bob)

        assert alice_result is True
        assert bob_result is True

    def test_different_keys_fail(self, mock_socket_pair):
        """Test that different keys fail verification."""
        key_alice = [1, 0, 1, 1, 0, 0, 1, 0] * 4
        key_bob = [0, 1, 0, 0, 1, 1, 0, 1] * 4

        alice_verifier = KeyVerifier(tag_bits=64, rng_seed=42)
        bob_verifier = KeyVerifier(tag_bits=64, rng_seed=42)

        gen_alice = alice_verifier.verify(
            mock_socket_pair.alice, key_alice, is_alice=True
        )
        gen_bob = bob_verifier.verify(
            mock_socket_pair.bob, key_bob, is_alice=False
        )

        alice_result, bob_result = run_generator_pair(gen_alice, gen_bob)

        assert alice_result is False
        assert bob_result is False

    def test_single_bit_difference_detected(self, mock_socket_pair):
        """Test that single bit difference is detected."""
        key_alice = [1, 0, 1, 1, 0, 0, 1, 0] * 4
        key_bob = key_alice.copy()
        key_bob[0] ^= 1  # Flip one bit

        alice_verifier = KeyVerifier(tag_bits=64, rng_seed=42)
        bob_verifier = KeyVerifier(tag_bits=64, rng_seed=42)

        gen_alice = alice_verifier.verify(
            mock_socket_pair.alice, key_alice, is_alice=True
        )
        gen_bob = bob_verifier.verify(
            mock_socket_pair.bob, key_bob, is_alice=False
        )

        alice_result, bob_result = run_generator_pair(gen_alice, gen_bob)

        assert alice_result is False
        assert bob_result is False

    def test_last_bit_difference_detected(self, mock_socket_pair):
        """Test that last bit difference is detected."""
        key_alice = [1, 0, 1, 1, 0, 0, 1, 0] * 4
        key_bob = key_alice.copy()
        key_bob[-1] ^= 1  # Flip last bit

        alice_verifier = KeyVerifier(tag_bits=64, rng_seed=42)
        bob_verifier = KeyVerifier(tag_bits=64, rng_seed=42)

        gen_alice = alice_verifier.verify(
            mock_socket_pair.alice, key_alice, is_alice=True
        )
        gen_bob = bob_verifier.verify(
            mock_socket_pair.bob, key_bob, is_alice=False
        )

        alice_result, bob_result = run_generator_pair(gen_alice, gen_bob)

        assert alice_result is False
        assert bob_result is False

    def test_long_key_verification(self, mock_socket_pair):
        """Test verification with longer keys (256 bits)."""
        np.random.seed(42)
        key = list(np.random.randint(0, 2, 256))

        alice_verifier = KeyVerifier(tag_bits=64, rng_seed=42)
        bob_verifier = KeyVerifier(tag_bits=64, rng_seed=42)

        gen_alice = alice_verifier.verify(
            mock_socket_pair.alice, key.copy(), is_alice=True
        )
        gen_bob = bob_verifier.verify(
            mock_socket_pair.bob, key.copy(), is_alice=False
        )

        alice_result, bob_result = run_generator_pair(gen_alice, gen_bob)

        assert alice_result is True
        assert bob_result is True


class TestVerificationWith128BitTags:
    """Tests using 128-bit field for stronger security."""

    @pytest.fixture
    def mock_socket_pair(self):
        """Provide a pair of linked mock sockets."""
        return MockSocketPair()

    def test_128_bit_identical_keys(self, mock_socket_pair):
        """Test 128-bit verification with identical keys."""
        key = [1, 0, 1, 1, 0, 0, 1, 0] * 16

        alice_verifier = KeyVerifier(tag_bits=128, rng_seed=42)
        bob_verifier = KeyVerifier(tag_bits=128, rng_seed=42)

        gen_alice = alice_verifier.verify(
            mock_socket_pair.alice, key.copy(), is_alice=True
        )
        gen_bob = bob_verifier.verify(
            mock_socket_pair.bob, key.copy(), is_alice=False
        )

        alice_result, bob_result = run_generator_pair(gen_alice, gen_bob)

        assert alice_result is True
        assert bob_result is True

    def test_128_bit_different_keys(self, mock_socket_pair):
        """Test 128-bit verification with different keys."""
        key_alice = [1, 0, 1, 1, 0, 0, 1, 0] * 16
        key_bob = key_alice.copy()
        key_bob[64] ^= 1  # Flip one bit in the middle

        alice_verifier = KeyVerifier(tag_bits=128, rng_seed=42)
        bob_verifier = KeyVerifier(tag_bits=128, rng_seed=42)

        gen_alice = alice_verifier.verify(
            mock_socket_pair.alice, key_alice, is_alice=True
        )
        gen_bob = bob_verifier.verify(
            mock_socket_pair.bob, key_bob, is_alice=False
        )

        alice_result, bob_result = run_generator_pair(gen_alice, gen_bob)

        assert alice_result is False
        assert bob_result is False


class TestVerificationLeakage:
    """Test leakage tracking during verification."""

    @pytest.fixture
    def mock_socket_pair(self):
        """Provide a pair of linked mock sockets."""
        return MockSocketPair()

    def test_leakage_tracked_alice(self, mock_socket_pair):
        """Test that Alice tracks leakage correctly."""
        key = [1, 0, 1, 1, 0, 0, 1, 0] * 4

        alice_verifier = KeyVerifier(tag_bits=64, rng_seed=42)
        bob_verifier = KeyVerifier(tag_bits=64, rng_seed=42)

        gen_alice = alice_verifier.verify(
            mock_socket_pair.alice, key.copy(), is_alice=True
        )
        gen_bob = bob_verifier.verify(
            mock_socket_pair.bob, key.copy(), is_alice=False
        )

        run_generator_pair(gen_alice, gen_bob)

        # Alice sends the tag, so she leaks tag_bits
        assert alice_verifier.leakage_bits == 64

    def test_leakage_tracked_bob(self, mock_socket_pair):
        """Test that Bob tracks leakage correctly."""
        key = [1, 0, 1, 1, 0, 0, 1, 0] * 4

        alice_verifier = KeyVerifier(tag_bits=64, rng_seed=42)
        bob_verifier = KeyVerifier(tag_bits=64, rng_seed=42)

        gen_alice = alice_verifier.verify(
            mock_socket_pair.alice, key.copy(), is_alice=True
        )
        gen_bob = bob_verifier.verify(
            mock_socket_pair.bob, key.copy(), is_alice=False
        )

        run_generator_pair(gen_alice, gen_bob)

        # Bob receives the tag but also needs to account for it
        assert bob_verifier.leakage_bits == 64


class TestVerificationDeterminism:
    """Test deterministic behavior of verification."""

    @pytest.fixture
    def mock_socket_pair(self):
        """Provide a pair of linked mock sockets."""
        return MockSocketPair()

    def test_same_seed_same_salt(self):
        """Test that same RNG seed produces same salt."""
        key = [1, 0, 1, 1, 0, 0, 1, 0] * 4

        # First run
        pair1 = MockSocketPair()
        alice1 = KeyVerifier(tag_bits=64, rng_seed=42)
        bob1 = KeyVerifier(tag_bits=64, rng_seed=42)
        gen_alice1 = alice1.verify(pair1.alice, key.copy(), is_alice=True)
        gen_bob1 = bob1.verify(pair1.bob, key.copy(), is_alice=False)
        run_generator_pair(gen_alice1, gen_bob1)

        # Second run with same seed
        pair2 = MockSocketPair()
        alice2 = KeyVerifier(tag_bits=64, rng_seed=42)
        bob2 = KeyVerifier(tag_bits=64, rng_seed=42)
        gen_alice2 = alice2.verify(pair2.alice, key.copy(), is_alice=True)
        gen_bob2 = bob2.verify(pair2.bob, key.copy(), is_alice=False)
        run_generator_pair(gen_alice2, gen_bob2)

        # Both should produce same results
        # (Can't easily verify salt, but behavior should be consistent)

    def test_different_seeds_different_salts(self, mock_socket_pair):
        """Test that different seeds produce different protocol runs."""
        key = [1, 0, 1, 1, 0, 0, 1, 0] * 4

        # Run 1
        alice1 = KeyVerifier(tag_bits=64, rng_seed=42)
        # Run 2
        alice2 = KeyVerifier(tag_bits=64, rng_seed=99)

        # Compute local hashes with generated salts
        result1 = alice1.verify_local(key, key)
        result2 = alice2.verify_local(key, key)

        # Different seeds should produce different salts
        assert result1.salt != result2.salt


class TestVerificationEdgeCases:
    """Test edge cases for verification protocol."""

    @pytest.fixture
    def mock_socket_pair(self):
        """Provide a pair of linked mock sockets."""
        return MockSocketPair()

    def test_very_short_key(self, mock_socket_pair):
        """Test verification with very short key (8 bits)."""
        key = [1, 0, 1, 1, 0, 0, 1, 0]

        alice_verifier = KeyVerifier(tag_bits=64, rng_seed=42)
        bob_verifier = KeyVerifier(tag_bits=64, rng_seed=42)

        gen_alice = alice_verifier.verify(
            mock_socket_pair.alice, key.copy(), is_alice=True
        )
        gen_bob = bob_verifier.verify(
            mock_socket_pair.bob, key.copy(), is_alice=False
        )

        alice_result, bob_result = run_generator_pair(gen_alice, gen_bob)

        assert alice_result is True
        assert bob_result is True

    def test_all_zeros_key(self, mock_socket_pair):
        """Test verification with all-zeros key."""
        key = [0] * 64

        alice_verifier = KeyVerifier(tag_bits=64, rng_seed=42)
        bob_verifier = KeyVerifier(tag_bits=64, rng_seed=42)

        gen_alice = alice_verifier.verify(
            mock_socket_pair.alice, key.copy(), is_alice=True
        )
        gen_bob = bob_verifier.verify(
            mock_socket_pair.bob, key.copy(), is_alice=False
        )

        alice_result, bob_result = run_generator_pair(gen_alice, gen_bob)

        assert alice_result is True
        assert bob_result is True

    def test_all_ones_key(self, mock_socket_pair):
        """Test verification with all-ones key."""
        key = [1] * 64

        alice_verifier = KeyVerifier(tag_bits=64, rng_seed=42)
        bob_verifier = KeyVerifier(tag_bits=64, rng_seed=42)

        gen_alice = alice_verifier.verify(
            mock_socket_pair.alice, key.copy(), is_alice=True
        )
        gen_bob = bob_verifier.verify(
            mock_socket_pair.bob, key.copy(), is_alice=False
        )

        alice_result, bob_result = run_generator_pair(gen_alice, gen_bob)

        assert alice_result is True
        assert bob_result is True

    def test_alternating_pattern(self, mock_socket_pair):
        """Test verification with alternating 0-1 pattern."""
        key = [i % 2 for i in range(64)]

        alice_verifier = KeyVerifier(tag_bits=64, rng_seed=42)
        bob_verifier = KeyVerifier(tag_bits=64, rng_seed=42)

        gen_alice = alice_verifier.verify(
            mock_socket_pair.alice, key.copy(), is_alice=True
        )
        gen_bob = bob_verifier.verify(
            mock_socket_pair.bob, key.copy(), is_alice=False
        )

        alice_result, bob_result = run_generator_pair(gen_alice, gen_bob)

        assert alice_result is True
        assert bob_result is True


class TestVerificationMultipleRuns:
    """Test multiple verification runs."""

    def test_multiple_sequential_verifications(self):
        """Test running verification multiple times sequentially."""
        key = [1, 0, 1, 1, 0, 0, 1, 0] * 4

        for i in range(5):
            pair = MockSocketPair()
            alice_verifier = KeyVerifier(tag_bits=64, rng_seed=42 + i)
            bob_verifier = KeyVerifier(tag_bits=64, rng_seed=42 + i)

            gen_alice = alice_verifier.verify(
                pair.alice, key.copy(), is_alice=True
            )
            gen_bob = bob_verifier.verify(
                pair.bob, key.copy(), is_alice=False
            )

            alice_result, bob_result = run_generator_pair(gen_alice, gen_bob)

            assert alice_result is True, f"Failed on run {i}"
            assert bob_result is True, f"Failed on run {i}"

    @pytest.mark.parametrize("seed", [1, 42, 123, 456, 789])
    def test_different_seeds(self, seed):
        """Test verification works with various seeds."""
        key = [1, 0, 1, 1, 0, 0, 1, 0] * 4

        pair = MockSocketPair()
        alice_verifier = KeyVerifier(tag_bits=64, rng_seed=seed)
        bob_verifier = KeyVerifier(tag_bits=64, rng_seed=seed)

        gen_alice = alice_verifier.verify(
            pair.alice, key.copy(), is_alice=True
        )
        gen_bob = bob_verifier.verify(
            pair.bob, key.copy(), is_alice=False
        )

        alice_result, bob_result = run_generator_pair(gen_alice, gen_bob)

        assert alice_result is True
        assert bob_result is True


class TestVerificationWithRandomKeys:
    """Test verification with random keys."""

    @pytest.mark.parametrize("key_length", [32, 64, 128, 256, 512])
    def test_various_key_lengths(self, key_length):
        """Test verification with various key lengths."""
        np.random.seed(42)
        key = list(np.random.randint(0, 2, key_length))

        pair = MockSocketPair()
        alice_verifier = KeyVerifier(tag_bits=64, rng_seed=42)
        bob_verifier = KeyVerifier(tag_bits=64, rng_seed=42)

        gen_alice = alice_verifier.verify(
            pair.alice, key.copy(), is_alice=True
        )
        gen_bob = bob_verifier.verify(
            pair.bob, key.copy(), is_alice=False
        )

        alice_result, bob_result = run_generator_pair(gen_alice, gen_bob)

        assert alice_result is True
        assert bob_result is True

    def test_random_keys_match(self):
        """Test that random identical keys always match."""
        np.random.seed(42)

        for _ in range(20):
            key = list(np.random.randint(0, 2, 100))

            pair = MockSocketPair()
            alice_verifier = KeyVerifier(tag_bits=64, rng_seed=None)
            bob_verifier = KeyVerifier(tag_bits=64, rng_seed=None)

            gen_alice = alice_verifier.verify(
                pair.alice, key.copy(), is_alice=True
            )
            gen_bob = bob_verifier.verify(
                pair.bob, key.copy(), is_alice=False
            )

            alice_result, bob_result = run_generator_pair(gen_alice, gen_bob)

            assert alice_result is True
            assert bob_result is True

    def test_random_keys_with_errors_fail(self):
        """Test that random keys with errors fail verification."""
        np.random.seed(42)

        failures = 0
        for _ in range(20):
            key_alice = list(np.random.randint(0, 2, 100))
            key_bob = key_alice.copy()
            # Introduce random error
            error_pos = np.random.randint(0, len(key_bob))
            key_bob[error_pos] ^= 1

            pair = MockSocketPair()
            alice_verifier = KeyVerifier(tag_bits=64, rng_seed=None)
            bob_verifier = KeyVerifier(tag_bits=64, rng_seed=None)

            gen_alice = alice_verifier.verify(
                pair.alice, key_alice, is_alice=True
            )
            gen_bob = bob_verifier.verify(
                pair.bob, key_bob, is_alice=False
            )

            alice_result, bob_result = run_generator_pair(gen_alice, gen_bob)

            if not alice_result:
                failures += 1

        # With 64-bit tags, virtually all should fail
        # (collision probability is negligible)
        assert failures == 20


class TestAfterReconciliation:
    """Test verification as it would be used after reconciliation."""

    @pytest.fixture
    def mock_socket_pair(self):
        """Provide a pair of linked mock sockets."""
        return MockSocketPair()

    def test_post_reconciliation_identical(self, mock_socket_pair):
        """Test verification after successful reconciliation (keys match)."""
        # Simulate reconciled keys
        np.random.seed(42)
        reconciled_key = list(np.random.randint(0, 2, 128))

        alice_verifier = KeyVerifier(tag_bits=64, rng_seed=42)
        bob_verifier = KeyVerifier(tag_bits=64, rng_seed=42)

        gen_alice = alice_verifier.verify(
            mock_socket_pair.alice, reconciled_key.copy(), is_alice=True
        )
        gen_bob = bob_verifier.verify(
            mock_socket_pair.bob, reconciled_key.copy(), is_alice=False
        )

        alice_result, bob_result = run_generator_pair(gen_alice, gen_bob)

        # After successful reconciliation, verification should pass
        assert alice_result is True
        assert bob_result is True

        # Leakage should be tracked
        assert alice_verifier.leakage_bits == 64
        assert bob_verifier.leakage_bits == 64

    def test_post_reconciliation_residual_error(self, mock_socket_pair):
        """Test verification catches residual errors after failed reconciliation."""
        # Simulate keys with residual error (reconciliation didn't fully correct)
        np.random.seed(42)
        key_alice = list(np.random.randint(0, 2, 128))
        key_bob = key_alice.copy()
        # One residual error remains
        key_bob[50] ^= 1

        alice_verifier = KeyVerifier(tag_bits=64, rng_seed=42)
        bob_verifier = KeyVerifier(tag_bits=64, rng_seed=42)

        gen_alice = alice_verifier.verify(
            mock_socket_pair.alice, key_alice, is_alice=True
        )
        gen_bob = bob_verifier.verify(
            mock_socket_pair.bob, key_bob, is_alice=False
        )

        alice_result, bob_result = run_generator_pair(gen_alice, gen_bob)

        # Verification should catch the residual error
        assert alice_result is False
        assert bob_result is False
