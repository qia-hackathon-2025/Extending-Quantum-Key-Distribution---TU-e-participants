"""Unit tests for authentication layer.

Tests cover:
1. Wegman-Carter authentication primitives (Toeplitz hashing)
2. AuthenticatedSocket wrapper functionality
3. Message integrity and tampering detection
4. Deterministic serialization

Reference: implementation_plan.md §Phase 1 (Unit Tests)
"""

from collections import OrderedDict
from typing import Any, Generator, List
from unittest.mock import MagicMock, patch

import pytest

from hackathon_challenge.auth.exceptions import IntegrityError, SecurityError
from hackathon_challenge.auth.socket import (
    AuthenticatedSocket,
    _compute_hmac,
    _serialize_payload,
)
from hackathon_challenge.auth.wegman_carter import (
    DEFAULT_TAG_BITS,
    ToeplitzAuthenticator,
    _bits_to_bytes,
    _bytes_to_bits,
    _construct_toeplitz_matrix,
    generate_auth_tag,
    generate_toeplitz_seed_bits,
    verify_auth_tag,
)


# =============================================================================
# Wegman-Carter Primitive Tests
# =============================================================================


class TestBitConversion:
    """Tests for bit/byte conversion utilities."""

    def test_bytes_to_bits_single_byte(self):
        """Test conversion of single byte to bits."""
        result = _bytes_to_bits(b"\x00")
        assert result == [0, 0, 0, 0, 0, 0, 0, 0]

        result = _bytes_to_bits(b"\xff")
        assert result == [1, 1, 1, 1, 1, 1, 1, 1]

        result = _bytes_to_bits(b"\xaa")  # 10101010
        assert result == [1, 0, 1, 0, 1, 0, 1, 0]

    def test_bytes_to_bits_multiple_bytes(self):
        """Test conversion of multiple bytes to bits."""
        result = _bytes_to_bits(b"\x00\xff")
        assert result == [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1]

    def test_bits_to_bytes_single_byte(self):
        """Test conversion of 8 bits to single byte."""
        result = _bits_to_bytes([0, 0, 0, 0, 0, 0, 0, 0])
        assert result == b"\x00"

        result = _bits_to_bytes([1, 1, 1, 1, 1, 1, 1, 1])
        assert result == b"\xff"

        result = _bits_to_bytes([1, 0, 1, 0, 1, 0, 1, 0])
        assert result == b"\xaa"

    def test_roundtrip_conversion(self):
        """Test that bytes -> bits -> bytes preserves data."""
        original = b"Hello, World!"
        bits = _bytes_to_bits(original)
        recovered = _bits_to_bytes(bits)
        assert recovered == original


class TestToeplitzMatrix:
    """Tests for Toeplitz matrix construction."""

    def test_toeplitz_matrix_dimensions(self):
        """Test that Toeplitz matrix has correct dimensions."""
        seed = [0, 1, 0, 1, 1, 0, 1]  # Length = rows + cols - 1 = 3 + 5 - 1 = 7
        matrix = _construct_toeplitz_matrix(seed, rows=3, cols=5)
        assert matrix.shape == (3, 5)

    def test_toeplitz_matrix_structure(self):
        """Test that Toeplitz matrix has constant diagonals."""
        seed = [0, 1, 0, 1, 1, 0, 1, 0, 1]
        matrix = _construct_toeplitz_matrix(seed, rows=4, cols=6)
        
        # Check that descending diagonals are constant
        for i in range(3):
            for j in range(5):
                if i + 1 < 4 and j + 1 < 6:
                    assert matrix[i, j] == matrix[i + 1, j + 1], \
                        f"Diagonal not constant at ({i},{j}) vs ({i+1},{j+1})"

    def test_toeplitz_matrix_seed_too_short_raises(self):
        """Test that insufficient seed length raises ValueError."""
        seed = [0, 1, 0]  # Too short for 3x5 matrix (needs 7)
        with pytest.raises(ValueError, match="Seed length"):
            _construct_toeplitz_matrix(seed, rows=3, cols=5)


class TestWegmanCarterAuth:
    """Tests for Wegman-Carter authentication functions."""

    def test_generate_auth_tag_returns_bytes(self, auth_key):
        """Test that generate_auth_tag returns bytes."""
        message = b"Test message"
        tag = generate_auth_tag(message, auth_key)
        assert isinstance(tag, bytes)
        assert len(tag) > 0

    def test_generate_auth_tag_deterministic(self, auth_key):
        """Test that same message/key produces same tag."""
        message = b"Deterministic test"
        tag1 = generate_auth_tag(message, auth_key)
        tag2 = generate_auth_tag(message, auth_key)
        assert tag1 == tag2

    def test_generate_auth_tag_different_messages(self, auth_key):
        """Test that different messages produce different tags."""
        message1 = b"Message one"
        message2 = b"Message two"
        tag1 = generate_auth_tag(message1, auth_key)
        tag2 = generate_auth_tag(message2, auth_key)
        assert tag1 != tag2

    def test_generate_auth_tag_different_keys(self):
        """Test that different keys produce different tags."""
        message = b"Same message"
        key1 = b"key_one_secret"
        key2 = b"key_two_secret"
        tag1 = generate_auth_tag(message, key1)
        tag2 = generate_auth_tag(message, key2)
        assert tag1 != tag2

    def test_verify_auth_tag_valid(self, auth_key):
        """Test that valid tags pass verification."""
        message = b"Valid message"
        tag = generate_auth_tag(message, auth_key)
        assert verify_auth_tag(message, tag, auth_key) is True

    def test_verify_auth_tag_invalid_message(self, auth_key):
        """Test that modified message fails verification."""
        message = b"Original message"
        tag = generate_auth_tag(message, auth_key)
        modified_message = b"Modified message"
        assert verify_auth_tag(modified_message, tag, auth_key) is False

    def test_verify_auth_tag_invalid_tag(self, auth_key):
        """Test that modified tag fails verification."""
        message = b"Test message"
        tag = generate_auth_tag(message, auth_key)
        # Flip a bit in the tag
        modified_tag = bytes([tag[0] ^ 0x01]) + tag[1:]
        assert verify_auth_tag(message, modified_tag, auth_key) is False

    def test_verify_auth_tag_wrong_key(self, auth_key):
        """Test that wrong key fails verification."""
        message = b"Test message"
        tag = generate_auth_tag(message, auth_key)
        wrong_key = b"wrong_key_secret"
        assert verify_auth_tag(message, tag, wrong_key) is False

    def test_empty_message_handling(self, auth_key):
        """Test authentication of empty message."""
        message = b""
        tag = generate_auth_tag(message, auth_key)
        assert verify_auth_tag(message, tag, auth_key) is True

    def test_custom_tag_bits(self, auth_key):
        """Test with custom tag bit length."""
        message = b"Test message"
        tag_32 = generate_auth_tag(message, auth_key, tag_bits=32)
        tag_64 = generate_auth_tag(message, auth_key, tag_bits=64)
        tag_128 = generate_auth_tag(message, auth_key, tag_bits=128)
        
        assert len(tag_32) == 4   # 32 bits = 4 bytes
        assert len(tag_64) == 8   # 64 bits = 8 bytes
        assert len(tag_128) == 16  # 128 bits = 16 bytes


class TestToeplitzAuthenticator:
    """Tests for the stateful ToeplitzAuthenticator class."""

    def test_authenticator_initialization(self, auth_key):
        """Test authenticator initialization."""
        authenticator = ToeplitzAuthenticator(auth_key)
        assert authenticator.tag_bits == DEFAULT_TAG_BITS
        assert authenticator._message_counter == 0

    def test_authenticator_custom_tag_bits(self, auth_key):
        """Test authenticator with custom tag bits."""
        authenticator = ToeplitzAuthenticator(auth_key, tag_bits=128)
        assert authenticator.tag_bits == 128

    def test_authenticate_returns_tuple(self, auth_key):
        """Test that authenticate returns (message, tag) tuple."""
        authenticator = ToeplitzAuthenticator(auth_key)
        message = b"Test"
        result = authenticator.authenticate(message)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result[0] == message
        assert isinstance(result[1], bytes)

    def test_verify_valid_tag(self, auth_key):
        """Test verification of valid tag."""
        authenticator = ToeplitzAuthenticator(auth_key)
        message = b"Test message"
        _, tag = authenticator.authenticate(message)
        
        # Reset counter for verification
        authenticator.reset_counter()
        assert authenticator.verify(message, tag) is True

    def test_message_counter_increments(self, auth_key):
        """Test that message counter increments."""
        authenticator = ToeplitzAuthenticator(auth_key)
        assert authenticator._message_counter == 0
        authenticator.authenticate(b"Message 1")
        assert authenticator._message_counter == 1
        authenticator.authenticate(b"Message 2")
        assert authenticator._message_counter == 2


class TestGenerateToeplitzSeedBits:
    """Tests for random seed generation."""

    def test_seed_length(self):
        """Test that generated seed has correct length."""
        seed = generate_toeplitz_seed_bits(100)
        assert len(seed) == 100

    def test_seed_values_binary(self):
        """Test that seed contains only 0 and 1."""
        seed = generate_toeplitz_seed_bits(1000)
        assert all(bit in (0, 1) for bit in seed)

    def test_seed_randomness(self):
        """Test that different calls produce different seeds."""
        seed1 = generate_toeplitz_seed_bits(100)
        seed2 = generate_toeplitz_seed_bits(100)
        # Probability of identical seeds is 2^-100, effectively zero
        assert seed1 != seed2


# =============================================================================
# Serialization Tests
# =============================================================================


class TestSerialization:
    """Tests for deterministic serialization."""

    def test_serialize_dict_deterministic(self):
        """Test that dict serialization is deterministic (sorted keys)."""
        payload1 = {"b": 1, "a": 2, "c": 3}
        payload2 = {"a": 2, "c": 3, "b": 1}
        
        serialized1 = _serialize_payload(payload1)
        serialized2 = _serialize_payload(payload2)
        
        assert serialized1 == serialized2

    def test_serialize_nested_dict(self):
        """Test serialization of nested dicts."""
        payload = {"outer": {"inner_b": 1, "inner_a": 2}}
        serialized = _serialize_payload(payload)
        assert b"inner_a" in serialized
        assert b"inner_b" in serialized

    def test_serialize_list(self):
        """Test serialization of lists."""
        payload = [1, 2, 3, "four", 5.0]
        serialized = _serialize_payload(payload)
        assert isinstance(serialized, bytes)

    def test_serialize_primitives(self):
        """Test serialization of primitive types."""
        assert _serialize_payload(42) == b"42"
        assert _serialize_payload("hello") == b'"hello"'
        assert _serialize_payload(3.14) == b"3.14"
        assert _serialize_payload(True) == b"true"
        assert _serialize_payload(None) == b"null"


class TestComputeHMAC:
    """Tests for HMAC computation."""

    def test_hmac_returns_32_bytes(self):
        """Test that HMAC-SHA256 returns 32 bytes."""
        key = b"secret"
        data = b"test data"
        result = _compute_hmac(key, data)
        assert len(result) == 32

    def test_hmac_deterministic(self):
        """Test that same inputs produce same HMAC."""
        key = b"secret"
        data = b"test data"
        hmac1 = _compute_hmac(key, data)
        hmac2 = _compute_hmac(key, data)
        assert hmac1 == hmac2

    def test_hmac_different_data(self):
        """Test that different data produces different HMAC."""
        key = b"secret"
        hmac1 = _compute_hmac(key, b"data1")
        hmac2 = _compute_hmac(key, b"data2")
        assert hmac1 != hmac2

    def test_hmac_different_keys(self):
        """Test that different keys produce different HMAC."""
        data = b"test data"
        hmac1 = _compute_hmac(b"key1", data)
        hmac2 = _compute_hmac(b"key2", data)
        assert hmac1 != hmac2


# =============================================================================
# AuthenticatedSocket Tests
# =============================================================================


class MockStructuredMessage:
    """Mock StructuredMessage for testing."""

    def __init__(self, header: str, payload: Any):
        self.header = header
        self.payload = payload


class MockClassicalSocket:
    """Mock ClassicalSocket for testing without SquidASM."""

    def __init__(self):
        self._sent_messages: List[Any] = []
        self._receive_queue: List[Any] = []
        self.peer_name = "MockPeer"

    def send_structured(self, msg: Any) -> None:
        """Store sent message."""
        self._sent_messages.append(msg)

    def recv_structured(self, **kwargs) -> Generator[Any, None, Any]:
        """Return next message from queue."""
        if self._receive_queue:
            msg = self._receive_queue.pop(0)
            yield None  # Simulate EventExpression
            return msg
        raise RuntimeError("No messages in receive queue")

    def queue_message(self, msg: Any) -> None:
        """Add message to receive queue for testing."""
        self._receive_queue.append(msg)


class TestAuthenticatedSocket:
    """Test suite for AuthenticatedSocket."""

    def test_initialization(self, auth_key):
        """Test socket initialization."""
        mock_socket = MockClassicalSocket()
        auth_socket = AuthenticatedSocket(mock_socket, auth_key)
        assert auth_socket._key == auth_key
        assert auth_socket._socket is mock_socket

    def test_initialization_empty_key_raises(self):
        """Test that empty key raises ValueError."""
        mock_socket = MockClassicalSocket()
        with pytest.raises(ValueError, match="cannot be empty"):
            AuthenticatedSocket(mock_socket, b"")

    def test_peer_name_property(self, auth_key):
        """Test peer_name property."""
        mock_socket = MockClassicalSocket()
        auth_socket = AuthenticatedSocket(mock_socket, auth_key)
        assert auth_socket.peer_name == "MockPeer"

    def test_send_structured_creates_envelope(self, auth_key):
        """Test that send_structured creates proper envelope."""
        mock_socket = MockClassicalSocket()
        auth_socket = AuthenticatedSocket(mock_socket, auth_key)
        
        # Need to use the actual StructuredMessage class
        from netqasm.sdk.classical_communication.message import StructuredMessage
        
        msg = StructuredMessage("TEST_HEADER", {"key": "value"})
        auth_socket.send_structured(msg)
        
        assert len(mock_socket._sent_messages) == 1
        envelope = mock_socket._sent_messages[0]
        assert envelope.header == "TEST_HEADER"
        assert isinstance(envelope.payload, tuple)
        assert len(envelope.payload) == 2
        payload, tag = envelope.payload
        assert payload == {"key": "value"}
        assert isinstance(tag, bytes)
        assert len(tag) == 32  # HMAC-SHA256

    def test_message_integrity(self, auth_key):
        """Test that valid messages pass authentication."""
        from netqasm.sdk.classical_communication.message import StructuredMessage
        
        mock_socket = MockClassicalSocket()
        auth_socket = AuthenticatedSocket(mock_socket, auth_key)
        
        # Send a message (creates envelope with HMAC)
        original_msg = StructuredMessage("DATA", {"value": 42})
        auth_socket.send_structured(original_msg)
        
        # Get the envelope that was sent
        envelope = mock_socket._sent_messages[0]
        
        # Queue the same envelope for receiving (simulates network)
        mock_socket.queue_message(envelope)
        
        # Receive should verify successfully
        gen = auth_socket.recv_structured()
        try:
            next(gen)  # Consume EventExpression
        except StopIteration as e:
            received_msg = e.value
            assert received_msg.header == "DATA"
            assert received_msg.payload == {"value": 42}

    def test_tampering_detection(self, auth_key):
        """Test that tampered messages raise IntegrityError."""
        from netqasm.sdk.classical_communication.message import StructuredMessage
        
        mock_socket = MockClassicalSocket()
        auth_socket = AuthenticatedSocket(mock_socket, auth_key)
        
        # Create a valid envelope first
        original_msg = StructuredMessage("DATA", {"value": 42})
        auth_socket.send_structured(original_msg)
        envelope = mock_socket._sent_messages[0]
        
        # Tamper with the payload
        tampered_payload = {"value": 999}  # Changed value
        tampered_envelope = StructuredMessage(
            envelope.header,
            (tampered_payload, envelope.payload[1])  # Keep original tag
        )
        mock_socket.queue_message(tampered_envelope)
        
        # Receive should detect tampering
        gen = auth_socket.recv_structured()
        with pytest.raises(IntegrityError, match="HMAC verification failed"):
            # Exhaust the generator to trigger the exception
            while True:
                try:
                    next(gen)
                except StopIteration:
                    break

    def test_deterministic_serialization(self, auth_key):
        """Test that same message produces same HMAC (deterministic)."""
        from netqasm.sdk.classical_communication.message import StructuredMessage
        
        mock_socket1 = MockClassicalSocket()
        mock_socket2 = MockClassicalSocket()
        auth_socket1 = AuthenticatedSocket(mock_socket1, auth_key)
        auth_socket2 = AuthenticatedSocket(mock_socket2, auth_key)
        
        # Send same logical message from both sockets
        msg1 = StructuredMessage("TEST", {"b": 2, "a": 1})
        msg2 = StructuredMessage("TEST", {"a": 1, "b": 2})  # Different order
        
        auth_socket1.send_structured(msg1)
        auth_socket2.send_structured(msg2)
        
        # Tags should be identical due to deterministic serialization
        tag1 = mock_socket1._sent_messages[0].payload[1]
        tag2 = mock_socket2._sent_messages[0].payload[1]
        assert tag1 == tag2

    def test_invalid_envelope_format(self, auth_key):
        """Test that invalid envelope format raises SecurityError."""
        from netqasm.sdk.classical_communication.message import StructuredMessage
        
        mock_socket = MockClassicalSocket()
        auth_socket = AuthenticatedSocket(mock_socket, auth_key)
        
        # Queue malformed envelope (payload not a tuple)
        bad_envelope = StructuredMessage("BAD", "not_a_tuple")
        mock_socket.queue_message(bad_envelope)
        
        gen = auth_socket.recv_structured()
        with pytest.raises(SecurityError, match="Invalid envelope format"):
            # Exhaust the generator to trigger the exception
            while True:
                try:
                    next(gen)
                except StopIteration:
                    break

    def test_send_and_recv_int(self, auth_key):
        """Test send_int and recv_int."""
        from netqasm.sdk.classical_communication.message import StructuredMessage
        
        mock_socket = MockClassicalSocket()
        auth_socket = AuthenticatedSocket(mock_socket, auth_key)
        
        auth_socket.send_int(42)
        envelope = mock_socket._sent_messages[0]
        mock_socket.queue_message(envelope)
        
        gen = auth_socket.recv_int()
        try:
            next(gen)
        except StopIteration as e:
            assert e.value == 42

    def test_send_and_recv_list(self, auth_key):
        """Test send_list and recv_list."""
        from netqasm.sdk.classical_communication.message import StructuredMessage
        
        mock_socket = MockClassicalSocket()
        auth_socket = AuthenticatedSocket(mock_socket, auth_key)
        
        test_list = [1, 2, 3, "four"]
        auth_socket.send_list(test_list)
        envelope = mock_socket._sent_messages[0]
        mock_socket.queue_message(envelope)
        
        gen = auth_socket.recv_list()
        try:
            next(gen)
        except StopIteration as e:
            assert e.value == test_list

    def test_key_mismatch_detection(self):
        """Test that different keys fail verification."""
        from netqasm.sdk.classical_communication.message import StructuredMessage
        
        mock_socket = MockClassicalSocket()
        key_alice = b"alice_secret_key"
        key_bob = b"wrong_bob_key"
        
        # Alice sends with her key
        auth_socket_alice = AuthenticatedSocket(mock_socket, key_alice)
        msg = StructuredMessage("SECRET", {"data": "classified"})
        auth_socket_alice.send_structured(msg)
        envelope = mock_socket._sent_messages[0]
        
        # Bob receives with wrong key
        mock_socket2 = MockClassicalSocket()
        mock_socket2.queue_message(envelope)
        auth_socket_bob = AuthenticatedSocket(mock_socket2, key_bob)
        
        gen = auth_socket_bob.recv_structured()
        with pytest.raises(IntegrityError):
            # Exhaust the generator to trigger the exception
            while True:
                try:
                    next(gen)
                except StopIteration:
                    break


# =============================================================================
# Integration Tests (without SquidASM)
# =============================================================================


class TestAuthenticationRoundtrip:
    """End-to-end tests for authentication roundtrip."""

    def test_full_message_roundtrip(self, auth_key):
        """Test complete send/receive cycle with verification."""
        from netqasm.sdk.classical_communication.message import StructuredMessage
        
        # Simulate Alice and Bob with shared key
        alice_socket_internal = MockClassicalSocket()
        bob_socket_internal = MockClassicalSocket()
        
        alice_auth = AuthenticatedSocket(alice_socket_internal, auth_key)
        bob_auth = AuthenticatedSocket(bob_socket_internal, auth_key)
        
        # Alice sends
        original = StructuredMessage("QKD_DATA", {
            "bases": [0, 1, 0, 1],
            "outcomes": [1, 0, 1, 0]
        })
        alice_auth.send_structured(original)
        
        # Transfer envelope to Bob's queue (simulates network)
        envelope = alice_socket_internal._sent_messages[0]
        bob_socket_internal.queue_message(envelope)
        
        # Bob receives and verifies
        gen = bob_auth.recv_structured()
        try:
            next(gen)
        except StopIteration as e:
            received = e.value
            assert received.header == original.header
            assert received.payload == original.payload

    def test_multiple_messages(self, auth_key):
        """Test multiple consecutive messages."""
        from netqasm.sdk.classical_communication.message import StructuredMessage
        
        mock_socket = MockClassicalSocket()
        auth_socket = AuthenticatedSocket(mock_socket, auth_key)
        
        messages = [
            StructuredMessage("MSG1", {"id": 1}),
            StructuredMessage("MSG2", {"id": 2}),
            StructuredMessage("MSG3", {"id": 3}),
        ]
        
        # Send all messages
        for msg in messages:
            auth_socket.send_structured(msg)
        
        # Verify all have different tags (due to different content)
        tags = [m.payload[1] for m in mock_socket._sent_messages]
        assert len(set(tags)) == len(tags)  # All unique
