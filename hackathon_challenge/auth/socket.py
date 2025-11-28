"""AuthenticatedSocket wrapper for classical communication.

This module implements HMAC-based authentication on top of ClassicalSocket.
It provides a secure wrapper that ensures message integrity and authenticity
for all classical communication in the QKD protocol.

The authentication uses HMAC-SHA256, which provides computational security.
For full information-theoretic security (as required by QKD), the underlying
Wegman-Carter primitives in wegman_carter.py can be used instead.

Reference:
- implementation_plan.md §Phase 1
- extending_qkd_technical_aspects.md §Step 3.1
"""

import hashlib
import hmac
import json
from collections import OrderedDict
from typing import Any, Generator, Optional, Union

from netqasm.sdk.classical_communication.message import StructuredMessage
from pydynaa import EventExpression

from hackathon_challenge.auth.exceptions import IntegrityError, SecurityError


def _serialize_payload(payload: Any) -> bytes:
    """Serialize payload deterministically for HMAC computation.

    Uses JSON serialization with sorted keys to ensure deterministic
    byte representation regardless of dict ordering.

    Parameters
    ----------
    payload : Any
        Payload to serialize. Must be JSON-serializable.

    Returns
    -------
    bytes
        Deterministic byte representation.

    Raises
    ------
    TypeError
        If payload cannot be serialized.

    Notes
    -----
    Uses OrderedDict and sorted keys to ensure deterministic serialization
    across Python versions and avoid HMAC verification failures.
    """
    try:
        # Convert to JSON with sorted keys for determinism
        serialized = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return serialized.encode("utf-8")
    except (TypeError, ValueError) as e:
        # Fallback to repr for non-JSON-serializable objects
        return repr(payload).encode("utf-8")


def _compute_hmac(key: bytes, data: bytes) -> bytes:
    """Compute HMAC-SHA256 tag for data.

    Parameters
    ----------
    key : bytes
        Secret authentication key.
    data : bytes
        Data to authenticate.

    Returns
    -------
    bytes
        HMAC-SHA256 tag (32 bytes).
    """
    return hmac.new(key, data, hashlib.sha256).digest()


class AuthenticatedSocket:
    """Wrapper that adds HMAC-SHA256 authentication to ClassicalSocket.

    All recv-methods that block on the network are generators and must be
    used with ``yield from`` by callers. This is critical for proper
    integration with SquidASM's event-driven architecture.

    The socket wraps messages in an envelope containing:
    - Original header
    - Tuple of (payload, hmac_tag)

    Parameters
    ----------
    socket : ClassicalSocket
        Underlying classical socket from SquidASM.
    key : bytes
        Pre-shared authentication key. Should be at least 32 bytes
        for adequate security.

    Attributes
    ----------
    _socket : ClassicalSocket
        The wrapped socket instance.
    _key : bytes
        Pre-shared authentication key.

    Notes
    -----
    - Uses deterministic serialization to ensure HMAC consistency.
    - All recv operations must use ``yield from`` pattern.
    - Raises IntegrityError on authentication failure.

    Examples
    --------
    In AliceProgram.run():

    >>> raw_socket = context.csockets["Bob"]
    >>> auth_socket = AuthenticatedSocket(raw_socket, b"shared_secret")
    >>> auth_socket.send_structured(StructuredMessage("HELLO", {"data": 42}))
    >>> msg = yield from auth_socket.recv_structured()

    References
    ----------
    - extending_qkd_technical_aspects.md §3.1 (AuthenticatedSocket design)
    """

    def __init__(self, socket: "ClassicalSocket", key: bytes) -> None:
        """Initialize authenticated socket.

        Parameters
        ----------
        socket : ClassicalSocket
            Underlying classical socket.
        key : bytes
            Pre-shared authentication key.

        Raises
        ------
        ValueError
            If key is empty.
        """
        if not key:
            raise ValueError("Authentication key cannot be empty")
        
        self._socket = socket
        self._key = key

    @property
    def peer_name(self) -> str:
        """Get the name of the peer for this socket.

        Returns
        -------
        str
            Peer node name.
        """
        return getattr(self._socket, "peer_name", "unknown")

    def send_structured(self, msg: StructuredMessage) -> None:
        """Send authenticated message.

        Computes HMAC-SHA256 over the header and serialized payload,
        then sends an envelope containing the original payload and tag.

        Parameters
        ----------
        msg : StructuredMessage
            Message to send with authentication.

        Notes
        -----
        The envelope format is:
        StructuredMessage(
            header=original_header,
            payload=(original_payload, hmac_tag)
        )
        """
        # Serialize header + payload for HMAC computation
        header_bytes = msg.header.encode("utf-8")
        payload_bytes = _serialize_payload(msg.payload)
        
        # Compute HMAC over header || payload
        data_to_sign = header_bytes + b"|" + payload_bytes
        tag = _compute_hmac(self._key, data_to_sign)
        
        # Create envelope with (payload, tag)
        envelope = StructuredMessage(msg.header, (msg.payload, tag))
        self._socket.send_structured(envelope)

    def recv_structured(
        self, **kwargs
    ) -> Generator[EventExpression, None, StructuredMessage]:
        """Receive and verify authenticated message.

        Receives an envelope, extracts the HMAC tag, recomputes the
        expected tag, and verifies authenticity using constant-time
        comparison.

        Parameters
        ----------
        **kwargs
            Additional arguments passed to underlying recv_structured.

        Yields
        ------
        EventExpression
            Network operation events (for SquidASM scheduler).

        Returns
        -------
        StructuredMessage
            Verified message with original header and payload.

        Raises
        ------
        IntegrityError
            If HMAC verification fails, indicating tampering or
            key mismatch.
        SecurityError
            If the envelope format is invalid.

        Notes
        -----
        CRITICAL: Must be called with ``yield from``:
        >>> msg = yield from auth_socket.recv_structured()
        """
        # Receive envelope from underlying socket
        envelope: StructuredMessage = yield from self._socket.recv_structured(**kwargs)
        
        # Validate envelope structure
        if not isinstance(envelope.payload, (tuple, list)) or len(envelope.payload) != 2:
            raise SecurityError(
                f"Invalid envelope format: expected (payload, tag) tuple, "
                f"got {type(envelope.payload)}"
            )
        
        payload, received_tag = envelope.payload
        
        # Validate tag type
        if not isinstance(received_tag, bytes):
            raise SecurityError(
                f"Invalid tag type: expected bytes, got {type(received_tag)}"
            )
        
        # Recompute expected HMAC
        header_bytes = envelope.header.encode("utf-8")
        payload_bytes = _serialize_payload(payload)
        data_to_verify = header_bytes + b"|" + payload_bytes
        expected_tag = _compute_hmac(self._key, data_to_verify)
        
        # Constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(received_tag, expected_tag):
            raise IntegrityError(
                f"HMAC verification failed for message with header '{envelope.header}'. "
                "Message may have been tampered with or keys do not match."
            )
        
        # Return original message (unwrapped)
        return StructuredMessage(envelope.header, payload)

    def send(self, msg: str) -> None:
        """Send authenticated raw string message.

        Wraps the string in a StructuredMessage for authentication.

        Parameters
        ----------
        msg : str
            String message to send.
        """
        structured_msg = StructuredMessage("RAW_STRING", msg)
        self.send_structured(structured_msg)

    def recv(self, **kwargs) -> Generator[EventExpression, None, str]:
        """Receive authenticated raw string message.

        Parameters
        ----------
        **kwargs
            Additional arguments passed to underlying recv.

        Yields
        ------
        EventExpression
            Network operation events.

        Returns
        -------
        str
            Verified string message.

        Raises
        ------
        IntegrityError
            If HMAC verification fails.
        SecurityError
            If the message format is unexpected.
        """
        msg: StructuredMessage = yield from self.recv_structured(**kwargs)
        
        if msg.header != "RAW_STRING":
            raise SecurityError(
                f"Expected RAW_STRING message, got '{msg.header}'"
            )
        
        return msg.payload

    def send_int(self, value: int) -> None:
        """Send authenticated integer.

        Parameters
        ----------
        value : int
            Integer to send.
        """
        self.send_structured(StructuredMessage("INT", value))

    def recv_int(self, **kwargs) -> Generator[EventExpression, None, int]:
        """Receive authenticated integer.

        Parameters
        ----------
        **kwargs
            Additional arguments for receive.

        Yields
        ------
        EventExpression
            Network operation events.

        Returns
        -------
        int
            Verified integer value.
        """
        msg: StructuredMessage = yield from self.recv_structured(**kwargs)
        
        if msg.header != "INT":
            raise SecurityError(f"Expected INT message, got '{msg.header}'")
        
        return int(msg.payload)

    def send_float(self, value: float) -> None:
        """Send authenticated float.

        Parameters
        ----------
        value : float
            Float to send.
        """
        self.send_structured(StructuredMessage("FLOAT", value))

    def recv_float(self, **kwargs) -> Generator[EventExpression, None, float]:
        """Receive authenticated float.

        Parameters
        ----------
        **kwargs
            Additional arguments for receive.

        Yields
        ------
        EventExpression
            Network operation events.

        Returns
        -------
        float
            Verified float value.
        """
        msg: StructuredMessage = yield from self.recv_structured(**kwargs)
        
        if msg.header != "FLOAT":
            raise SecurityError(f"Expected FLOAT message, got '{msg.header}'")
        
        return float(msg.payload)

    def send_list(self, values: list) -> None:
        """Send authenticated list.

        Parameters
        ----------
        values : list
            List to send.
        """
        self.send_structured(StructuredMessage("LIST", values))

    def recv_list(self, **kwargs) -> Generator[EventExpression, None, list]:
        """Receive authenticated list.

        Parameters
        ----------
        **kwargs
            Additional arguments for receive.

        Yields
        ------
        EventExpression
            Network operation events.

        Returns
        -------
        list
            Verified list.
        """
        msg: StructuredMessage = yield from self.recv_structured(**kwargs)
        
        if msg.header != "LIST":
            raise SecurityError(f"Expected LIST message, got '{msg.header}'")
        
        return list(msg.payload)
