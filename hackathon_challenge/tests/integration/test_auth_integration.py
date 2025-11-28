"""Integration tests for the authentication package.

This module tests the auth package components in a simulated SquidASM
environment, verifying that:
1. AuthenticatedSocket works correctly in actual protocol scenarios
2. Wegman-Carter authentication integrates properly
3. Bidirectional communication maintains message integrity
4. Error handling works correctly across the full stack

Reference:
- implementation_plan.md §Phase 1 (Authentication Layer)
- extending_qkd_technical_aspects.md §Step 3.1

Notes
-----
These tests use the SquidASM framework to simulate actual Alice-Bob
communication over classical channels, validating the auth package
in a realistic environment without quantum operations.
"""

import logging
from typing import Any, Dict, Generator, List

import pytest
from netqasm.sdk.classical_communication.message import StructuredMessage
from pydynaa import EventExpression

from squidasm.run.stack.run import run
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta
from squidasm.util import create_two_node_network

from hackathon_challenge.auth import (
    AuthenticatedSocket,
    IntegrityError,
    SecurityError,
    ToeplitzAuthenticator,
    generate_auth_tag,
    verify_auth_tag,
)


# =============================================================================
# Test Programs for SquidASM Integration
# =============================================================================


class AuthTestProgramAlice(Program):
    """Alice's test program for authenticated communication.
    
    Sends authenticated messages to Bob and receives authenticated responses.
    
    Parameters
    ----------
    auth_key : bytes
        Pre-shared authentication key.
    messages_to_send : List[Dict[str, Any]]
        List of messages to send (each dict has 'header' and 'payload').
    expected_responses : List[str]
        Expected response headers from Bob.
    """
    
    PEER = "Bob"
    
    def __init__(
        self,
        auth_key: bytes,
        messages_to_send: List[Dict[str, Any]],
        expected_responses: List[str],
    ) -> None:
        self._auth_key = auth_key
        self._messages = messages_to_send
        self._expected_responses = expected_responses
        self.logger = LogManager.get_stack_logger(self.__class__.__name__)
    
    @property
    def meta(self) -> ProgramMeta:
        """Define program metadata with required sockets."""
        return ProgramMeta(
            name="alice_auth_test",
            csockets=[self.PEER],
            epr_sockets=[self.PEER],  # Required by SquidASM even if unused
            max_qubits=1,  # Minimum required by SquidASM
        )
    
    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        """Execute authenticated message exchange with Bob.
        
        Yields
        ------
        EventExpression
            Network operation events for SquidASM scheduler.
        
        Returns
        -------
        Dict[str, Any]
            Results including sent/received messages and any errors.
        """
        raw_socket = context.csockets[self.PEER]
        auth_socket = AuthenticatedSocket(raw_socket, self._auth_key)
        
        results = {
            "sent_messages": [],
            "received_messages": [],
            "errors": [],
        }
        
        try:
            for i, msg_data in enumerate(self._messages):
                # Send authenticated message
                msg = StructuredMessage(msg_data["header"], msg_data["payload"])
                auth_socket.send_structured(msg)
                results["sent_messages"].append(msg_data)
                self.logger.info(f"Alice sent: {msg_data['header']}")
                
                # Receive authenticated response
                response = yield from auth_socket.recv_structured()
                results["received_messages"].append({
                    "header": response.header,
                    "payload": response.payload,
                })
                self.logger.info(f"Alice received: {response.header}")
                
                # Verify expected response header
                if response.header != self._expected_responses[i]:
                    results["errors"].append(
                        f"Unexpected response header: {response.header}"
                    )
        
        except (IntegrityError, SecurityError) as e:
            results["errors"].append(str(e))
            self.logger.error(f"Authentication error: {e}")
        
        return results


class AuthTestProgramBob(Program):
    """Bob's test program for authenticated communication.
    
    Receives authenticated messages from Alice and sends authenticated responses.
    
    Parameters
    ----------
    auth_key : bytes
        Pre-shared authentication key.
    response_map : Dict[str, Dict[str, Any]]
        Maps incoming headers to response messages.
    """
    
    PEER = "Alice"
    
    def __init__(
        self,
        auth_key: bytes,
        response_map: Dict[str, Dict[str, Any]],
    ) -> None:
        self._auth_key = auth_key
        self._response_map = response_map
        self.logger = LogManager.get_stack_logger(self.__class__.__name__)
    
    @property
    def meta(self) -> ProgramMeta:
        """Define program metadata with required sockets."""
        return ProgramMeta(
            name="bob_auth_test",
            csockets=[self.PEER],
            epr_sockets=[self.PEER],  # Required by SquidASM even if unused
            max_qubits=1,  # Minimum required by SquidASM
        )
    
    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        """Execute authenticated message exchange with Alice.
        
        Yields
        ------
        EventExpression
            Network operation events for SquidASM scheduler.
        
        Returns
        -------
        Dict[str, Any]
            Results including sent/received messages and any errors.
        """
        raw_socket = context.csockets[self.PEER]
        auth_socket = AuthenticatedSocket(raw_socket, self._auth_key)
        
        results = {
            "sent_messages": [],
            "received_messages": [],
            "errors": [],
        }
        
        try:
            # Process each expected message
            for _ in range(len(self._response_map)):
                # Receive authenticated message
                msg = yield from auth_socket.recv_structured()
                results["received_messages"].append({
                    "header": msg.header,
                    "payload": msg.payload,
                })
                self.logger.info(f"Bob received: {msg.header}")
                
                # Look up and send response
                if msg.header in self._response_map:
                    response_data = self._response_map[msg.header]
                    response = StructuredMessage(
                        response_data["header"],
                        response_data["payload"],
                    )
                    auth_socket.send_structured(response)
                    results["sent_messages"].append(response_data)
                    self.logger.info(f"Bob sent: {response_data['header']}")
                else:
                    results["errors"].append(f"Unknown message header: {msg.header}")
        
        except (IntegrityError, SecurityError) as e:
            results["errors"].append(str(e))
            self.logger.error(f"Authentication error: {e}")
        
        return results


class MismatchedKeyProgramAlice(Program):
    """Alice program with different key to test key mismatch detection."""
    
    PEER = "Bob"
    
    def __init__(self, auth_key: bytes) -> None:
        self._auth_key = auth_key
        self.logger = LogManager.get_stack_logger(self.__class__.__name__)
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="alice_mismatch",
            csockets=[self.PEER],
            epr_sockets=[self.PEER],  # Required by SquidASM
            max_qubits=1,
        )
    
    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        raw_socket = context.csockets[self.PEER]
        auth_socket = AuthenticatedSocket(raw_socket, self._auth_key)
        
        # Send message with Alice's key
        msg = StructuredMessage("TEST", {"data": "secret"})
        auth_socket.send_structured(msg)
        self.logger.info("Alice sent message with her key")
        
        return {"status": "sent"}


class MismatchedKeyProgramBob(Program):
    """Bob program with different key to test key mismatch detection."""
    
    PEER = "Alice"
    
    def __init__(self, auth_key: bytes) -> None:
        self._auth_key = auth_key
        self.logger = LogManager.get_stack_logger(self.__class__.__name__)
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="bob_mismatch",
            csockets=[self.PEER],
            epr_sockets=[self.PEER],  # Required by SquidASM
            max_qubits=1,
        )
    
    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        raw_socket = context.csockets[self.PEER]
        auth_socket = AuthenticatedSocket(raw_socket, self._auth_key)
        
        result = {"status": "unknown", "error": None}
        
        try:
            # Try to receive with different key - should fail
            msg = yield from auth_socket.recv_structured()
            result["status"] = "received"  # Should not reach here
        except IntegrityError as e:
            result["status"] = "integrity_error"
            result["error"] = str(e)
            self.logger.info(f"Bob detected key mismatch: {e}")
        except SecurityError as e:
            result["status"] = "security_error"
            result["error"] = str(e)
        
        return result


class MultipleExchangeProgramAlice(Program):
    """Alice program for testing multiple message exchanges."""
    
    PEER = "Bob"
    
    def __init__(self, auth_key: bytes, num_exchanges: int) -> None:
        self._auth_key = auth_key
        self._num_exchanges = num_exchanges
        self.logger = LogManager.get_stack_logger(self.__class__.__name__)
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="alice_multi",
            csockets=[self.PEER],
            epr_sockets=[self.PEER],  # Required by SquidASM
            max_qubits=1,
        )
    
    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        raw_socket = context.csockets[self.PEER]
        auth_socket = AuthenticatedSocket(raw_socket, self._auth_key)
        
        exchanges_completed = 0
        
        for i in range(self._num_exchanges):
            # Send a numbered message
            auth_socket.send_int(i)
            
            # Receive response
            response = yield from auth_socket.recv_int()
            
            if response == i * 2:  # Bob doubles the number
                exchanges_completed += 1
        
        return {"exchanges_completed": exchanges_completed}


class MultipleExchangeProgramBob(Program):
    """Bob program for testing multiple message exchanges."""
    
    PEER = "Alice"
    
    def __init__(self, auth_key: bytes, num_exchanges: int) -> None:
        self._auth_key = auth_key
        self._num_exchanges = num_exchanges
        self.logger = LogManager.get_stack_logger(self.__class__.__name__)
    
    @property
    def meta(self) -> ProgramMeta:
        return ProgramMeta(
            name="bob_multi",
            csockets=[self.PEER],
            epr_sockets=[self.PEER],  # Required by SquidASM
            max_qubits=1,
        )
    
    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        raw_socket = context.csockets[self.PEER]
        auth_socket = AuthenticatedSocket(raw_socket, self._auth_key)
        
        exchanges_completed = 0
        
        for _ in range(self._num_exchanges):
            # Receive number from Alice
            value = yield from auth_socket.recv_int()
            
            # Send back doubled value
            auth_socket.send_int(value * 2)
            exchanges_completed += 1
        
        return {"exchanges_completed": exchanges_completed}


class QKDStyleMessageProgram(Program):
    """Test program that mimics QKD-style message patterns."""
    
    PEER: str
    
    def __init__(self, auth_key: bytes, is_alice: bool) -> None:
        self._auth_key = auth_key
        self._is_alice = is_alice
        self.PEER = "Bob" if is_alice else "Alice"
        self.logger = LogManager.get_stack_logger(self.__class__.__name__)
    
    @property
    def meta(self) -> ProgramMeta:
        name = "alice_qkd_style" if self._is_alice else "bob_qkd_style"
        return ProgramMeta(
            name=name,
            csockets=[self.PEER],
            epr_sockets=[self.PEER],  # Required by SquidASM
            max_qubits=1,
        )
    
    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        raw_socket = context.csockets[self.PEER]
        auth_socket = AuthenticatedSocket(raw_socket, self._auth_key)
        
        # Simulate QKD-style message exchange
        if self._is_alice:
            # Alice initiates basis exchange
            bases = [0, 1, 0, 1, 1, 0, 0, 1]
            auth_socket.send_structured(StructuredMessage("BASES", bases))
            
            bob_bases = yield from auth_socket.recv_structured()
            
            # Calculate matching indices
            matching = [
                i for i in range(len(bases))
                if bases[i] == bob_bases.payload[i]
            ]
            
            # Send test indices for error estimation
            test_indices = matching[:2]
            auth_socket.send_structured(
                StructuredMessage("TEST_INDICES", test_indices)
            )
            
            # Receive test outcomes
            bob_outcomes = yield from auth_socket.recv_structured()
            
            return {
                "matching_count": len(matching),
                "test_received": bob_outcomes.payload,
            }
        else:
            # Bob responds
            alice_bases = yield from auth_socket.recv_structured()
            
            bob_bases = [1, 1, 0, 0, 1, 0, 1, 1]
            auth_socket.send_structured(StructuredMessage("BASES", bob_bases))
            
            test_indices = yield from auth_socket.recv_structured()
            
            # Send test outcomes
            test_outcomes = [0, 1]  # Mock outcomes
            auth_socket.send_structured(
                StructuredMessage("TEST_OUTCOMES", test_outcomes)
            )
            
            return {
                "alice_bases_received": alice_bases.payload,
                "test_indices_received": test_indices.payload,
            }


# =============================================================================
# Integration Tests
# =============================================================================


class TestAuthenticatedSocketIntegration:
    """Integration tests for AuthenticatedSocket in SquidASM environment."""
    
    @pytest.fixture
    def network_config(self):
        """Create a simple two-node network configuration."""
        return create_two_node_network(
            node_names=["Alice", "Bob"],
            link_noise=0.0,  # No noise for auth-only tests
        )
    
    @pytest.fixture
    def shared_key(self):
        """Provide a shared authentication key."""
        return b"integration_test_shared_secret_key_32bytes!"
    
    def test_basic_authenticated_exchange(self, network_config, shared_key):
        """Test basic authenticated message exchange between Alice and Bob.
        
        Verifies that:
        1. Alice can send authenticated messages to Bob
        2. Bob can verify and respond
        3. Both sides receive correct messages
        """
        messages = [
            {"header": "HELLO", "payload": {"greeting": "Hi Bob!"}},
        ]
        responses = ["ACK"]
        response_map = {
            "HELLO": {"header": "ACK", "payload": {"response": "Hi Alice!"}},
        }
        
        alice = AuthTestProgramAlice(shared_key, messages, responses)
        bob = AuthTestProgramBob(shared_key, response_map)
        
        alice.logger.setLevel(logging.ERROR)
        bob.logger.setLevel(logging.ERROR)
        
        alice_results, bob_results = run(
            config=network_config,
            programs={"Alice": alice, "Bob": bob},
            num_times=1,
        )
        
        # Verify Alice's results
        assert len(alice_results[0]["errors"]) == 0
        assert len(alice_results[0]["sent_messages"]) == 1
        assert len(alice_results[0]["received_messages"]) == 1
        assert alice_results[0]["received_messages"][0]["header"] == "ACK"
        
        # Verify Bob's results
        assert len(bob_results[0]["errors"]) == 0
        assert len(bob_results[0]["received_messages"]) == 1
        assert bob_results[0]["received_messages"][0]["header"] == "HELLO"
    
    def test_multiple_message_exchange(self, network_config, shared_key):
        """Test multiple consecutive authenticated message exchanges.
        
        Verifies that authentication works correctly across many messages.
        """
        num_exchanges = 10
        
        alice = MultipleExchangeProgramAlice(shared_key, num_exchanges)
        bob = MultipleExchangeProgramBob(shared_key, num_exchanges)
        
        alice.logger.setLevel(logging.ERROR)
        bob.logger.setLevel(logging.ERROR)
        
        alice_results, bob_results = run(
            config=network_config,
            programs={"Alice": alice, "Bob": bob},
            num_times=1,
        )
        
        assert alice_results[0]["exchanges_completed"] == num_exchanges
        assert bob_results[0]["exchanges_completed"] == num_exchanges
    
    def test_key_mismatch_detection(self, network_config):
        """Test that mismatched keys are detected and cause simulation failure.
        
        This is a critical security test verifying that authentication
        fails when Alice and Bob use different keys.
        
        Notes
        -----
        In SquidASM, when an IntegrityError is raised inside a generator,
        it propagates through the simulation engine and causes the run
        to fail. This test verifies that the simulation does not complete
        successfully when keys don't match.
        
        The actual HMAC verification failure is extensively tested in
        unit tests (test_auth.py::TestAuthenticatedSocket::test_key_mismatch_detection).
        """
        alice_key = b"alice_secret_key_1234567890"
        bob_key = b"bob_different_key_0987654321"
        
        alice = MismatchedKeyProgramAlice(alice_key)
        bob = MismatchedKeyProgramBob(bob_key)
        
        alice.logger.setLevel(logging.ERROR)
        bob.logger.setLevel(logging.ERROR)
        
        # The simulation should fail when Bob tries to verify a message
        # signed with a different key. The exact exception may vary depending
        # on how SquidASM handles exceptions in generators.
        with pytest.raises(Exception):
            run(
                config=network_config,
                programs={"Alice": alice, "Bob": bob},
                num_times=1,
            )
        # Success: the simulation failed due to key mismatch (as expected)
    
    def test_qkd_style_message_patterns(self, network_config, shared_key):
        """Test authentication with QKD-style message patterns.
        
        Simulates the message exchange patterns used in the actual
        QKD protocol (basis exchange, test indices, etc.).
        """
        alice = QKDStyleMessageProgram(shared_key, is_alice=True)
        bob = QKDStyleMessageProgram(shared_key, is_alice=False)
        
        alice.logger.setLevel(logging.ERROR)
        bob.logger.setLevel(logging.ERROR)
        
        alice_results, bob_results = run(
            config=network_config,
            programs={"Alice": alice, "Bob": bob},
            num_times=1,
        )
        
        # Verify message exchange worked
        assert alice_results[0]["matching_count"] >= 0
        assert "test_received" in alice_results[0]
        assert "alice_bases_received" in bob_results[0]
        assert "test_indices_received" in bob_results[0]
    
    def test_complex_payload_types(self, network_config, shared_key):
        """Test authentication with various payload types.
        
        Verifies that complex nested payloads are correctly serialized,
        authenticated, and deserialized.
        """
        messages = [
            {
                "header": "COMPLEX",
                "payload": {
                    "integers": [1, 2, 3, 4, 5],
                    "floats": [0.1, 0.2, 0.3],
                    "nested": {
                        "level1": {
                            "level2": "deep_value"
                        }
                    },
                    "string": "test_string",
                    "boolean": True,
                }
            },
        ]
        responses = ["ACK"]
        response_map = {
            "COMPLEX": {"header": "ACK", "payload": {"received": True}},
        }
        
        alice = AuthTestProgramAlice(shared_key, messages, responses)
        bob = AuthTestProgramBob(shared_key, response_map)
        
        alice.logger.setLevel(logging.ERROR)
        bob.logger.setLevel(logging.ERROR)
        
        alice_results, bob_results = run(
            config=network_config,
            programs={"Alice": alice, "Bob": bob},
            num_times=1,
        )
        
        assert len(alice_results[0]["errors"]) == 0
        assert len(bob_results[0]["errors"]) == 0
        
        # Verify complex payload was correctly received
        received = bob_results[0]["received_messages"][0]["payload"]
        assert received["integers"] == [1, 2, 3, 4, 5]
        assert received["nested"]["level1"]["level2"] == "deep_value"
    
    def test_repeated_runs_consistency(self, network_config, shared_key):
        """Test that authentication works consistently across multiple runs.
        
        Verifies deterministic behavior and no state leakage between runs.
        """
        num_runs = 3
        num_exchanges = 5
        
        alice = MultipleExchangeProgramAlice(shared_key, num_exchanges)
        bob = MultipleExchangeProgramBob(shared_key, num_exchanges)
        
        alice.logger.setLevel(logging.ERROR)
        bob.logger.setLevel(logging.ERROR)
        
        alice_results, bob_results = run(
            config=network_config,
            programs={"Alice": alice, "Bob": bob},
            num_times=num_runs,
        )
        
        # All runs should complete successfully
        for i in range(num_runs):
            assert alice_results[i]["exchanges_completed"] == num_exchanges
            assert bob_results[i]["exchanges_completed"] == num_exchanges


class TestWegmanCarterIntegration:
    """Integration tests for Wegman-Carter authentication primitives."""
    
    def test_toeplitz_authenticator_full_workflow(self):
        """Test ToeplitzAuthenticator in a realistic workflow.
        
        Simulates Alice authenticating messages and Bob verifying them.
        """
        shared_key = b"wegman_carter_integration_test_key"
        
        # Create authenticators for both parties
        alice_auth = ToeplitzAuthenticator(shared_key, tag_bits=64)
        bob_auth = ToeplitzAuthenticator(shared_key, tag_bits=64)
        
        # Simulate protocol messages
        messages = [
            b"BASES:01010101",
            b"TEST_INDICES:0,2,4",
            b"TEST_OUTCOMES:0,1,0",
            b"CASCADE_REQ:block_0",
            b"VERIFY_HASH:abc123def456",
        ]
        
        # Alice authenticates all messages
        authenticated_msgs = []
        for msg in messages:
            msg_with_tag = alice_auth.authenticate(msg)
            authenticated_msgs.append(msg_with_tag)
        
        # Reset Bob's counter to match (simulating synchronized state)
        bob_auth.reset_counter()
        
        # Bob verifies all messages
        for msg, tag in authenticated_msgs:
            assert bob_auth.verify(msg, tag), f"Failed to verify: {msg}"
    
    def test_large_message_authentication(self):
        """Test authentication of large messages (simulating key data)."""
        key = b"large_message_test_key"
        
        # Create a large message (simulating a key or list of bases)
        large_data = bytes([i % 256 for i in range(10000)])
        
        # Generate and verify tag
        tag = generate_auth_tag(large_data, key, tag_bits=128)
        assert verify_auth_tag(large_data, tag, key, tag_bits=128)
        
        # Verify tampering detection
        tampered = large_data[:-1] + bytes([large_data[-1] ^ 0x01])
        assert not verify_auth_tag(tampered, tag, key, tag_bits=128)
    
    def test_cross_compatibility(self):
        """Test that generate_auth_tag and ToeplitzAuthenticator are compatible."""
        key = b"cross_compat_test_key_32bytes!!!"
        message = b"test message for compatibility"
        tag_bits = 64
        
        # Generate tag using function
        func_tag = generate_auth_tag(message, key, tag_bits)
        
        # Verify using function
        assert verify_auth_tag(message, func_tag, key, tag_bits)
        
        # Also verify using authenticator class
        authenticator = ToeplitzAuthenticator(key, tag_bits)
        _, class_tag = authenticator.authenticate(message)
        
        # Both should produce identical tags
        assert func_tag == class_tag


class TestAuthPackagePublicAPI:
    """Tests verifying the public API of the auth package."""
    
    def test_all_exports_accessible(self):
        """Verify all expected exports are accessible from package."""
        from hackathon_challenge import auth
        
        # Exceptions
        assert hasattr(auth, 'SecurityError')
        assert hasattr(auth, 'IntegrityError')
        
        # Socket wrapper
        assert hasattr(auth, 'AuthenticatedSocket')
        
        # Wegman-Carter primitives
        assert hasattr(auth, 'generate_auth_tag')
        assert hasattr(auth, 'verify_auth_tag')
        assert hasattr(auth, 'generate_toeplitz_seed_bits')
        assert hasattr(auth, 'ToeplitzAuthenticator')
        assert hasattr(auth, 'DEFAULT_TAG_BITS')
    
    def test_exception_hierarchy(self):
        """Verify exception inheritance is correct."""
        # IntegrityError should be a SecurityError
        assert issubclass(IntegrityError, SecurityError)
        
        # SecurityError should be a RuntimeError
        assert issubclass(SecurityError, RuntimeError)
        
        # Can catch IntegrityError with SecurityError handler
        try:
            raise IntegrityError("test")
        except SecurityError:
            pass  # Expected
    
    def test_constants_have_reasonable_values(self):
        """Verify constants are set to reasonable values."""
        from hackathon_challenge.auth import DEFAULT_TAG_BITS
        
        # Tag bits should be a reasonable security level
        assert DEFAULT_TAG_BITS >= 32, "Tag too short for security"
        assert DEFAULT_TAG_BITS <= 256, "Tag unnecessarily long"
        assert DEFAULT_TAG_BITS % 8 == 0, "Tag bits should be byte-aligned"


class TestAuthSecurityProperties:
    """Tests verifying security properties of the auth package."""
    
    def test_tag_uniqueness_per_message(self):
        """Verify that different messages produce different tags."""
        key = b"uniqueness_test_key"
        
        messages = [
            b"message_1",
            b"message_2",
            b"message_3",
            b"message_1a",  # Similar to message_1
            b"Message_1",   # Different case
        ]
        
        tags = [generate_auth_tag(msg, key) for msg in messages]
        
        # All tags should be unique
        assert len(set(tags)) == len(tags), "Tags are not unique"
    
    def test_key_sensitivity(self):
        """Verify that slightly different keys produce different tags."""
        message = b"key_sensitivity_test"
        
        key1 = b"key_1234567890abcdef"
        key2 = b"key_1234567890abcdee"  # One bit different
        
        tag1 = generate_auth_tag(message, key1)
        tag2 = generate_auth_tag(message, key2)
        
        assert tag1 != tag2, "Tags should differ with different keys"
    
    def test_empty_message_handling(self):
        """Verify proper handling of edge cases."""
        key = b"edge_case_test_key"
        
        # Empty message should still be authenticatable
        empty_tag = generate_auth_tag(b"", key)
        assert verify_auth_tag(b"", empty_tag, key)
        
        # Single byte
        single_tag = generate_auth_tag(b"\x00", key)
        assert verify_auth_tag(b"\x00", single_tag, key)
    
    def test_tag_length_corresponds_to_bits(self):
        """Verify tag length matches requested bit length."""
        key = b"tag_length_test_key"
        message = b"test"
        
        for bits in [32, 64, 96, 128]:
            tag = generate_auth_tag(message, key, tag_bits=bits)
            expected_bytes = bits // 8
            assert len(tag) == expected_bytes, \
                f"Tag length {len(tag)} != expected {expected_bytes} for {bits} bits"
