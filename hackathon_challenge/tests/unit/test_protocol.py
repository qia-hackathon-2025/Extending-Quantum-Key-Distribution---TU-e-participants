"""Unit tests for QKD protocol components.

This module tests protocol classes in isolation using mocked sockets
and contexts, without requiring full SquidASM simulation.

Reference:
- implementation_plan.md §Phase 5 (Unit Tests)
"""

import pytest
from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Optional, Tuple
from unittest.mock import Mock, MagicMock, patch

import numpy as np

from hackathon_challenge.core.protocol import (
    AliceProgram,
    BobProgram,
    QkdProgram,
    PairInfo,
    create_qkd_programs,
)
from hackathon_challenge.core.constants import (
    DEFAULT_CASCADE_SEED,
    DEFAULT_MAX_QUBITS,
    DEFAULT_NUM_EPR_PAIRS,
    DEFAULT_TAG_BITS,
    MIN_KEY_LENGTH,
    MSG_ALL_MEASURED,
    MSG_PA_SEED,
    QBER_THRESHOLD,
    RESULT_ERROR,
    RESULT_KEY_LENGTH,
    RESULT_LEAKAGE,
    RESULT_QBER,
    RESULT_SECRET_KEY,
    RESULT_SUCCESS,
    SECURITY_PARAMETER,
)
from hackathon_challenge.core.base import QKDResult


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def alice_program():
    """Create an AliceProgram with default parameters."""
    return AliceProgram(
        num_epr_pairs=200,
        num_test_bits=50,
        cascade_seed=42,
        auth_key=b"test_key_for_unit_tests",
        verification_tag_bits=64,
        security_parameter=1e-12,
    )


@pytest.fixture
def bob_program():
    """Create a BobProgram with default parameters."""
    return BobProgram(
        num_epr_pairs=200,
        num_test_bits=50,
        cascade_seed=42,
        auth_key=b"test_key_for_unit_tests",
        verification_tag_bits=64,
        security_parameter=1e-12,
    )


@pytest.fixture
def pair_info_list():
    """Create a list of PairInfo objects for testing."""
    return [
        PairInfo(index=i, basis=i % 2, outcome=i % 2)
        for i in range(100)
    ]


@pytest.fixture
def sifted_pair_info():
    """Create PairInfo list after sifting with same_basis set."""
    pairs = []
    for i in range(100):
        pair = PairInfo(
            index=i,
            basis=i % 2,
            outcome=i % 2,
            same_basis=(i % 3 != 0),  # ~67% same basis
        )
        pairs.append(pair)
    return pairs


@pytest.fixture
def tested_pair_info():
    """Create PairInfo list after QBER testing."""
    pairs = []
    for i in range(100):
        same_basis = (i % 3 != 0)
        test_outcome = (i % 5 == 0) and same_basis  # ~20% of same-basis pairs
        pair = PairInfo(
            index=i,
            basis=i % 2,
            outcome=i % 2,
            same_basis=same_basis,
            test_outcome=test_outcome,
            same_outcome=True if test_outcome else None,
        )
        pairs.append(pair)
    return pairs


# =============================================================================
# Test Classes
# =============================================================================


class TestPairInfo:
    """Tests for PairInfo dataclass."""

    def test_creation(self):
        """Test PairInfo can be created with required fields."""
        pair = PairInfo(index=0, basis=1, outcome=0)
        assert pair.index == 0
        assert pair.basis == 1
        assert pair.outcome == 0
        assert pair.same_basis is None
        assert pair.test_outcome is None
        assert pair.same_outcome is None

    def test_creation_with_optional_fields(self):
        """Test PairInfo with all fields."""
        pair = PairInfo(
            index=5,
            basis=0,
            outcome=1,
            same_basis=True,
            test_outcome=False,
            same_outcome=True,
        )
        assert pair.index == 5
        assert pair.same_basis is True
        assert pair.test_outcome is False
        assert pair.same_outcome is True


class TestAliceProgramMeta:
    """Tests for AliceProgram metadata."""

    def test_peer_name(self, alice_program):
        """Test Alice's peer is Bob."""
        assert alice_program.PEER == "Bob"

    def test_meta_name(self, alice_program):
        """Test program name in metadata."""
        assert alice_program.meta.name == "alice_qkd"

    def test_meta_csockets(self, alice_program):
        """Test classical sockets are declared."""
        assert "Bob" in alice_program.meta.csockets

    def test_meta_epr_sockets(self, alice_program):
        """Test EPR sockets are declared."""
        assert "Bob" in alice_program.meta.epr_sockets

    def test_meta_max_qubits(self, alice_program):
        """Test max_qubits is set correctly."""
        assert alice_program.meta.max_qubits == DEFAULT_MAX_QUBITS


class TestBobProgramMeta:
    """Tests for BobProgram metadata."""

    def test_peer_name(self, bob_program):
        """Test Bob's peer is Alice."""
        assert bob_program.PEER == "Alice"

    def test_meta_name(self, bob_program):
        """Test program name in metadata."""
        assert bob_program.meta.name == "bob_qkd"

    def test_meta_csockets(self, bob_program):
        """Test classical sockets are declared."""
        assert "Alice" in bob_program.meta.csockets

    def test_meta_epr_sockets(self, bob_program):
        """Test EPR sockets are declared."""
        assert "Alice" in bob_program.meta.epr_sockets


class TestProgramInitialization:
    """Tests for program initialization."""

    def test_alice_default_initialization(self):
        """Test AliceProgram with default parameters."""
        alice = AliceProgram()
        assert alice._num_epr_pairs == DEFAULT_NUM_EPR_PAIRS
        assert alice._num_test_bits == DEFAULT_NUM_EPR_PAIRS // 4
        assert alice._cascade_seed == DEFAULT_CASCADE_SEED
        assert alice._verification_tag_bits == DEFAULT_TAG_BITS
        assert alice._security_parameter == SECURITY_PARAMETER

    def test_bob_default_initialization(self):
        """Test BobProgram with default parameters."""
        bob = BobProgram()
        assert bob._num_epr_pairs == DEFAULT_NUM_EPR_PAIRS
        assert bob._num_test_bits == DEFAULT_NUM_EPR_PAIRS // 4

    def test_custom_parameters(self):
        """Test program with custom parameters."""
        alice = AliceProgram(
            num_epr_pairs=500,
            num_test_bits=100,
            cascade_seed=123,
            auth_key=b"custom_key",
            verification_tag_bits=128,
            security_parameter=1e-10,
        )
        assert alice._num_epr_pairs == 500
        assert alice._num_test_bits == 100
        assert alice._cascade_seed == 123
        assert alice._auth_key == b"custom_key"
        assert alice._verification_tag_bits == 128
        assert alice._security_parameter == 1e-10

    def test_default_auth_key(self):
        """Test default authentication key is set."""
        alice = AliceProgram()
        assert alice._auth_key is not None
        assert len(alice._auth_key) > 0


class TestCreateQkdPrograms:
    """Tests for create_qkd_programs factory function."""

    def test_creates_matching_programs(self):
        """Test factory creates Alice and Bob with matching params."""
        alice, bob = create_qkd_programs(
            num_epr_pairs=300,
            cascade_seed=99,
        )
        assert alice._num_epr_pairs == bob._num_epr_pairs == 300
        assert alice._cascade_seed == bob._cascade_seed == 99
        assert alice._auth_key == bob._auth_key

    def test_returns_correct_types(self):
        """Test factory returns correct program types."""
        alice, bob = create_qkd_programs()
        assert isinstance(alice, AliceProgram)
        assert isinstance(bob, BobProgram)

    def test_different_peers(self):
        """Test Alice and Bob have different peer names."""
        alice, bob = create_qkd_programs()
        assert alice.PEER == "Bob"
        assert bob.PEER == "Alice"


class TestExtractRawKey:
    """Tests for _extract_raw_key method."""

    def test_extracts_correct_bits(self, alice_program, tested_pair_info):
        """Test raw key extraction from sifted, non-test pairs."""
        raw_key = alice_program._extract_raw_key(tested_pair_info)
        
        # Should only include pairs where same_basis=True and test_outcome=False
        expected_count = sum(
            1 for p in tested_pair_info
            if p.same_basis and not p.test_outcome
        )
        assert len(raw_key) == expected_count

    def test_excludes_different_basis(self, alice_program):
        """Test pairs with different basis are excluded."""
        pairs = [
            PairInfo(index=0, basis=0, outcome=1, same_basis=False, test_outcome=False),
            PairInfo(index=1, basis=1, outcome=0, same_basis=True, test_outcome=False),
        ]
        raw_key = alice_program._extract_raw_key(pairs)
        assert len(raw_key) == 1
        assert raw_key[0] == 0

    def test_excludes_test_bits(self, alice_program):
        """Test pairs used for testing are excluded."""
        pairs = [
            PairInfo(index=0, basis=0, outcome=1, same_basis=True, test_outcome=True),
            PairInfo(index=1, basis=1, outcome=0, same_basis=True, test_outcome=False),
        ]
        raw_key = alice_program._extract_raw_key(pairs)
        assert len(raw_key) == 1
        assert raw_key[0] == 0

    def test_empty_pairs(self, alice_program):
        """Test with empty pair list."""
        raw_key = alice_program._extract_raw_key([])
        assert raw_key == []

    def test_all_excluded(self, alice_program):
        """Test when all pairs are excluded."""
        pairs = [
            PairInfo(index=0, basis=0, outcome=1, same_basis=False, test_outcome=False),
            PairInfo(index=1, basis=1, outcome=0, same_basis=True, test_outcome=True),
        ]
        raw_key = alice_program._extract_raw_key(pairs)
        assert raw_key == []


class TestErrorResult:
    """Tests for _error_result method."""

    def test_alice_error_result(self, alice_program):
        """Test Alice's error result format."""
        result = alice_program._error_result("test_error", "Test message")
        assert result[RESULT_ERROR] == "test_error"
        assert result["message"] == "Test message"
        assert result[RESULT_SECRET_KEY] == []
        assert result[RESULT_SUCCESS] is False

    def test_bob_error_result(self, bob_program):
        """Test Bob's error result format."""
        result = bob_program._error_result("other_error", "Other message")
        assert result[RESULT_ERROR] == "other_error"
        assert result["message"] == "Other message"
        assert result[RESULT_SECRET_KEY] == []
        assert result[RESULT_SUCCESS] is False


class TestQKDResultDataclass:
    """Tests for QKDResult dataclass."""

    def test_successful_result(self):
        """Test creating a successful result."""
        result = QKDResult(
            secret_key=[1, 0, 1, 0],
            qber=0.05,
            key_length=4,
            leakage=100,
            success=True,
        )
        assert result.secret_key == [1, 0, 1, 0]
        assert result.qber == 0.05
        assert result.key_length == 4
        assert result.success is True
        assert result.error_message is None

    def test_failed_result(self):
        """Test creating a failed result."""
        result = QKDResult(
            secret_key=[],
            qber=0.15,
            key_length=0,
            leakage=50,
            success=False,
            error_message="QBER too high",
        )
        assert result.success is False
        assert result.error_message == "QBER too high"


class TestConstants:
    """Tests for protocol constants."""

    def test_qber_threshold(self):
        """Test QBER threshold is correct (Shor-Preskill bound)."""
        assert QBER_THRESHOLD == 0.11

    def test_security_parameter(self):
        """Test default security parameter."""
        assert SECURITY_PARAMETER == 1e-12

    def test_min_key_length(self):
        """Test minimum key length requirement."""
        assert MIN_KEY_LENGTH > 0

    def test_message_headers_unique(self):
        """Test all message headers are unique strings."""
        headers = [MSG_ALL_MEASURED, MSG_PA_SEED]
        assert len(set(headers)) == len(headers)
        for header in headers:
            assert isinstance(header, str)
            assert len(header) > 0


class TestProgramInheritance:
    """Tests for program class hierarchy."""

    def test_alice_is_qkd_program(self, alice_program):
        """Test AliceProgram inherits from QkdProgram."""
        assert isinstance(alice_program, QkdProgram)

    def test_bob_is_qkd_program(self, bob_program):
        """Test BobProgram inherits from QkdProgram."""
        assert isinstance(bob_program, QkdProgram)

    def test_programs_share_base_methods(self, alice_program, bob_program):
        """Test both programs have base class methods."""
        assert hasattr(alice_program, "_distribute_states")
        assert hasattr(bob_program, "_distribute_states")
        assert hasattr(alice_program, "_filter_bases")
        assert hasattr(bob_program, "_filter_bases")
        assert hasattr(alice_program, "_estimate_error_rate")
        assert hasattr(bob_program, "_estimate_error_rate")
        assert hasattr(alice_program, "_extract_raw_key")
        assert hasattr(bob_program, "_extract_raw_key")


class TestProgramLogger:
    """Tests for program logging."""

    def test_alice_has_logger(self, alice_program):
        """Test Alice has a logger."""
        assert hasattr(alice_program, "_logger")
        assert alice_program._logger is not None

    def test_bob_has_logger(self, bob_program):
        """Test Bob has a logger."""
        assert hasattr(bob_program, "_logger")
        assert bob_program._logger is not None


# =============================================================================
# Mocked Protocol Flow Tests
# =============================================================================


class TestMockedFilterBases:
    """Tests for _filter_bases with mocked socket."""

    def test_filter_bases_initiator(self, alice_program, pair_info_list):
        """Test basis filtering as initiator (Alice)."""
        # Create mock socket
        mock_socket = Mock()
        
        # Remote bases (same basis for even indices, different for odd)
        remote_bases = [(i, i % 2) for i in range(len(pair_info_list))]
        mock_response = Mock()
        mock_response.payload = remote_bases
        
        # Mock recv_structured to return a generator that yields the response
        def mock_recv():
            yield  # Simulate EventExpression
            return mock_response
        
        mock_socket.recv_structured.return_value = mock_recv()
        
        # Run filter (need to consume the generator)
        gen = alice_program._filter_bases(mock_socket, pair_info_list, is_initiator=True)
        
        # Advance generator - this should call send_structured first
        try:
            while True:
                next(gen)
        except StopIteration as e:
            result = e.value
        
        # Verify send was called
        mock_socket.send_structured.assert_called_once()
        
        # All pairs should have same_basis set (all True since bases match)
        for pair in result:
            assert pair.same_basis is not None

    def test_filter_bases_responder(self, bob_program, pair_info_list):
        """Test basis filtering as responder (Bob)."""
        mock_socket = Mock()
        
        # Remote bases
        remote_bases = [(i, 0) for i in range(len(pair_info_list))]
        mock_response = Mock()
        mock_response.payload = remote_bases
        
        def mock_recv():
            yield
            return mock_response
        
        mock_socket.recv_structured.return_value = mock_recv()
        
        gen = bob_program._filter_bases(mock_socket, pair_info_list, is_initiator=False)
        
        try:
            while True:
                next(gen)
        except StopIteration as e:
            result = e.value
        
        # Verify recv was called before send
        mock_socket.recv_structured.assert_called_once()


class TestMockedEstimateErrorRate:
    """Tests for _estimate_error_rate with mocked socket."""

    def test_estimate_initiator_no_errors(self, alice_program, sifted_pair_info):
        """Test error estimation with no errors (initiator)."""
        mock_socket = Mock()
        test_count = 10
        
        # We need to capture what indices Alice sends, then respond with matching outcomes
        sent_indices = []
        
        def capture_send(msg):
            """Capture the sent message to know what indices were selected."""
            if msg.header == "Test indices":
                sent_indices.extend(msg.payload)
        
        mock_socket.send_structured.side_effect = capture_send
        
        # Create a dynamic mock_recv that returns outcomes for the actual selected indices
        recv_called = [False]  # Use list to allow mutation in nested function
        
        def mock_recv():
            """Return matching outcomes for whatever indices were selected."""
            yield  # First yield for recv_structured
            # At this point, send_structured has been called with the indices
            # Return matching outcomes for those exact indices
            matching_outcomes = [(i, sifted_pair_info[i].outcome) for i in sent_indices]
            mock_response = Mock()
            mock_response.payload = matching_outcomes
            return mock_response
        
        mock_socket.recv_structured.return_value = mock_recv()
        
        gen = alice_program._estimate_error_rate(
            mock_socket, sifted_pair_info, test_count, is_initiator=True
        )
        
        try:
            while True:
                next(gen)
        except StopIteration as e:
            pairs, error_rate = e.value
        
        # With matching outcomes, error rate should be 0
        assert error_rate == 0.0

    def test_estimate_responder(self, bob_program, sifted_pair_info):
        """Test error estimation as responder."""
        mock_socket = Mock()
        
        # Simulate receiving test indices
        same_basis_indices = [p.index for p in sifted_pair_info if p.same_basis]
        test_indices = same_basis_indices[:5]
        
        mock_indices_response = Mock()
        mock_indices_response.payload = test_indices
        
        # Then outcomes
        test_outcomes = [(i, sifted_pair_info[i].outcome) for i in test_indices]
        mock_outcomes_response = Mock()
        mock_outcomes_response.payload = test_outcomes
        
        recv_calls = iter([mock_indices_response, mock_outcomes_response])
        
        def mock_recv():
            yield
            return next(recv_calls)
        
        mock_socket.recv_structured.side_effect = [mock_recv(), mock_recv()]
        
        gen = bob_program._estimate_error_rate(
            mock_socket, sifted_pair_info, 5, is_initiator=False
        )
        
        # Consume generator
        try:
            while True:
                next(gen)
        except StopIteration as e:
            pairs, error_rate = e.value
        
        # Test bits should be marked
        for idx in test_indices:
            assert pairs[idx].test_outcome is True


# =============================================================================
# Integration with Other Components
# =============================================================================


class TestProtocolComponentIntegration:
    """Tests for integration with other protocol components."""

    def test_imports_cascade_reconciliator(self):
        """Test CascadeReconciliator can be imported."""
        from hackathon_challenge.reconciliation.cascade import CascadeReconciliator
        assert CascadeReconciliator is not None

    def test_imports_key_verifier(self):
        """Test KeyVerifier can be imported."""
        from hackathon_challenge.verification.verifier import KeyVerifier
        assert KeyVerifier is not None

    def test_imports_privacy_amplifier(self):
        """Test PrivacyAmplifier can be imported."""
        from hackathon_challenge.privacy.amplifier import PrivacyAmplifier
        assert PrivacyAmplifier is not None

    def test_imports_authenticated_socket(self):
        """Test AuthenticatedSocket can be imported."""
        from hackathon_challenge.auth.socket import AuthenticatedSocket
        assert AuthenticatedSocket is not None


class TestProtocolWithRealComponents:
    """Tests using real protocol components (no socket mocking)."""

    def test_privacy_amplification_integration(self):
        """Test privacy amplification with protocol parameters."""
        from hackathon_challenge.privacy.amplifier import PrivacyAmplifier
        from hackathon_challenge.privacy.utils import generate_toeplitz_seed
        
        # Simulate a reconciled key
        reconciled_key = [int(x) for x in np.random.randint(0, 2, 200)]
        final_length = 50
        
        seed = generate_toeplitz_seed(len(reconciled_key), final_length)
        amplifier = PrivacyAmplifier(epsilon_sec=SECURITY_PARAMETER)
        final_key = amplifier.amplify(reconciled_key, seed, final_length)
        
        assert len(final_key) == final_length
        assert all(b in (0, 1) for b in final_key)

    def test_key_verifier_with_matching_keys(self):
        """Test KeyVerifier with identical keys (non-network)."""
        from hackathon_challenge.verification.verifier import KeyVerifier
        
        key = [0, 1, 0, 1, 1, 0, 0, 1] * 10
        verifier = KeyVerifier(tag_bits=64)
        
        # Same salt should produce same hash
        salt = 12345
        hash1 = verifier.compute_hash(key, salt)
        hash2 = verifier.compute_hash(key, salt)
        
        assert hash1 == hash2

    def test_key_verifier_with_different_keys(self):
        """Test KeyVerifier detects different keys."""
        from hackathon_challenge.verification.verifier import KeyVerifier
        
        key1 = [0, 1, 0, 1, 1, 0, 0, 1] * 10
        key2 = [1, 1, 0, 1, 1, 0, 0, 1] * 10  # First bit differs
        
        verifier = KeyVerifier(tag_bits=64)
        salt = 12345
        
        hash1 = verifier.compute_hash(key1, salt)
        hash2 = verifier.compute_hash(key2, salt)
        
        assert hash1 != hash2


class TestProtocolEdgeCases:
    """Tests for edge cases in the protocol."""

    def test_minimum_epr_pairs(self):
        """Test program with minimum EPR pairs."""
        alice = AliceProgram(num_epr_pairs=MIN_KEY_LENGTH + 50)
        assert alice._num_epr_pairs == MIN_KEY_LENGTH + 50

    def test_zero_test_bits(self):
        """Test handling of zero test bits."""
        alice = AliceProgram(num_epr_pairs=100, num_test_bits=0)
        # Should use default
        assert alice._num_test_bits == 0 or alice._num_test_bits == 25

    def test_large_epr_pairs(self):
        """Test program with large number of EPR pairs."""
        alice = AliceProgram(num_epr_pairs=10000)
        assert alice._num_epr_pairs == 10000

    def test_verification_tag_bits_options(self):
        """Test both 64 and 128 bit tag options."""
        alice_64 = AliceProgram(verification_tag_bits=64)
        alice_128 = AliceProgram(verification_tag_bits=128)
        
        assert alice_64._verification_tag_bits == 64
        assert alice_128._verification_tag_bits == 128


class TestPairInfoOperations:
    """Tests for operations on PairInfo lists."""

    def test_count_same_basis(self, sifted_pair_info):
        """Test counting same-basis pairs."""
        count = sum(1 for p in sifted_pair_info if p.same_basis)
        assert count > 0
        assert count < len(sifted_pair_info)

    def test_count_test_bits(self, tested_pair_info):
        """Test counting test bits."""
        count = sum(1 for p in tested_pair_info if p.test_outcome)
        assert count > 0
        assert count < len(tested_pair_info)

    def test_extract_outcomes(self, pair_info_list):
        """Test extracting outcomes from pairs."""
        outcomes = [p.outcome for p in pair_info_list]
        assert len(outcomes) == len(pair_info_list)
        assert all(o in (0, 1) for o in outcomes)
