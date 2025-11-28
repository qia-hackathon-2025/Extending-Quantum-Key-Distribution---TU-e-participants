"""Key verification using universal hashing.

This module implements the KeyVerifier class for verifying that Alice
and Bob share identical keys after reconciliation.

Reference:
- implementation_plan.md §Phase 3
- extending_qkd_technical_aspects.md §1.4
- extending_qkd_theorethical_aspects.md §3 (Polynomial Hashing)

Notes
-----
Key verification is essential because reconciliation protocols like Cascade
are probabilistic and may leave residual errors (e.g., even number of errors
in all checked blocks). Universal hashing provides a high-confidence check
that keys are identical.

The protocol:
1. Alice generates a random salt r
2. Alice computes H_r(K_A) and sends (r, H_r(K_A)) to Bob
3. Bob computes H_r(K_B) and compares with Alice's tag
4. Bob sends the comparison result to Alice
5. Both return True if tags match, False otherwise

Collision probability is bounded by L/2^n where L is the number of
field elements and n is the field size in bits.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Generator, List, Optional, Union

import numpy as np
from netqasm.sdk.classical_communication.message import StructuredMessage
from pydynaa import EventExpression

from hackathon_challenge.core.constants import DEFAULT_TAG_BITS, MSG_VERIFY_HASH
from hackathon_challenge.verification.polynomial_hash import (
    collision_probability,
    compute_polynomial_hash,
    generate_hash_salt,
)

if TYPE_CHECKING:
    from hackathon_challenge.auth.socket import AuthenticatedSocket


# Message headers for verification protocol
MSG_VERIFY_RESULT = "VERIFY_RESULT"


@dataclass
class VerificationResult:
    """Result of key verification.

    Attributes
    ----------
    success : bool
        True if keys match, False otherwise.
    salt : int
        Salt used for hashing.
    local_tag : int
        Hash tag computed locally.
    remote_tag : Optional[int]
        Hash tag received from peer (only set for Bob).
    collision_prob : float
        Theoretical collision probability.
    """

    success: bool
    salt: int
    local_tag: int
    remote_tag: Optional[int] = None
    collision_prob: float = 0.0


class KeyVerifier:
    """Implements polynomial hashing over GF(2^n) for key equality check.

    This class provides a universal hash-based verification protocol
    to ensure Alice and Bob have identical keys after reconciliation.

    Parameters
    ----------
    tag_bits : int, optional
        Hash tag size in bits (default 64 for GF(2^64)).
        Larger values provide stronger security guarantees.
    element_bits : int, optional
        Bits per field element (defaults to tag_bits).
    rng_seed : Optional[int], optional
        Seed for random number generation. None for random seed.

    Notes
    -----
    Security analysis:
    - Collision probability ≤ L / 2^tag_bits
    - For 64-bit tags and L=1000 bits: prob ≈ 5.4 × 10^-17
    - For 64-bit tags and L=10000 bits: prob ≈ 8.5 × 10^-16

    The verification leaks tag_bits of information about the key,
    which must be accounted for in privacy amplification.

    Reference: extending_qkd_theorethical_aspects.md §3.3
    """

    def __init__(
        self,
        tag_bits: int = 64,
        element_bits: Optional[int] = None,
        rng_seed: Optional[int] = None,
    ) -> None:
        """Initialize key verifier.

        Parameters
        ----------
        tag_bits : int, optional
            Hash tag size in bits (default 64).
        element_bits : int, optional
            Bits per field element.
        rng_seed : Optional[int], optional
            Random seed for deterministic testing.
        """
        if tag_bits not in (64, 128):
            raise ValueError(f"tag_bits must be 64 or 128, got {tag_bits}")

        self._tag_bits = tag_bits
        self._element_bits = element_bits if element_bits else tag_bits
        self._rng = np.random.default_rng(rng_seed)

        # Leakage tracking
        self._leakage_bits = 0

    @property
    def tag_bits(self) -> int:
        """Return the tag size in bits."""
        return self._tag_bits

    @property
    def leakage_bits(self) -> int:
        """Return total bits leaked during verification."""
        return self._leakage_bits

    def get_collision_probability(self, key_length: int) -> float:
        """Calculate collision probability for a given key length.

        Parameters
        ----------
        key_length : int
            Length of key in bits.

        Returns
        -------
        float
            Upper bound on collision probability.
        """
        return collision_probability(key_length, self._element_bits)

    def compute_hash(self, key: List[int], salt: int) -> int:
        """Compute the polynomial hash of a key.

        Parameters
        ----------
        key : List[int]
            Key bits to hash.
        salt : int
            Random evaluation point.

        Returns
        -------
        int
            Hash tag.
        """
        return compute_polynomial_hash(
            key, salt, self._tag_bits, self._element_bits
        )

    def verify(
        self,
        socket: "AuthenticatedSocket",
        key: List[int],
        is_alice: bool,
    ) -> Generator[EventExpression, None, bool]:
        """Verify key equality using polynomial hashing.

        This is a generator that performs the verification protocol
        over an authenticated classical channel.

        Parameters
        ----------
        socket : AuthenticatedSocket
            Authenticated classical channel for communication.
        key : List[int]
            Local reconciled key bits.
        is_alice : bool
            True if this is Alice (initiator who generates salt).

        Yields
        ------
        EventExpression
            Network operation events.

        Returns
        -------
        bool
            True if keys match, False otherwise.

        Notes
        -----
        Protocol flow:
        1. Alice generates random salt r ∈ GF(2^n)
        2. Alice computes tag_A = H_r(K_A)
        3. Alice sends (salt, tag_A) to Bob
        4. Bob receives (salt, tag_A)
        5. Bob computes tag_B = H_r(K_B)
        6. Bob compares tag_A == tag_B
        7. Bob sends result to Alice
        8. Both return the result

        The protocol leaks tag_bits + 1 bits of information.
        """
        if is_alice:
            return (yield from self._verify_alice(socket, key))
        else:
            return (yield from self._verify_bob(socket, key))

    def _verify_alice(
        self,
        socket: "AuthenticatedSocket",
        key: List[int],
    ) -> Generator[EventExpression, None, bool]:
        """Alice's verification protocol.

        Parameters
        ----------
        socket : AuthenticatedSocket
            Communication channel.
        key : List[int]
            Alice's key.

        Yields
        ------
        EventExpression
            Network events.

        Returns
        -------
        bool
            Verification result.
        """
        # Generate random salt
        salt = generate_hash_salt(self._tag_bits, self._rng)

        # Compute local hash
        local_tag = self.compute_hash(key, salt)

        # Send salt and tag to Bob
        payload = {"salt": salt, "tag": local_tag}
        socket.send_structured(StructuredMessage(MSG_VERIFY_HASH, payload))

        # Track leakage (salt + tag bits)
        self._leakage_bits += self._tag_bits  # Tag reveals information

        # Wait for result from Bob
        response: StructuredMessage = yield from socket.recv_structured()

        if response.header != MSG_VERIFY_RESULT:
            raise ValueError(
                f"Expected {MSG_VERIFY_RESULT}, got {response.header}"
            )

        result = response.payload.get("match", False)
        return result

    def _verify_bob(
        self,
        socket: "AuthenticatedSocket",
        key: List[int],
    ) -> Generator[EventExpression, None, bool]:
        """Bob's verification protocol.

        Parameters
        ----------
        socket : AuthenticatedSocket
            Communication channel.
        key : List[int]
            Bob's key.

        Yields
        ------
        EventExpression
            Network events.

        Returns
        -------
        bool
            Verification result.
        """
        # Receive salt and tag from Alice
        msg: StructuredMessage = yield from socket.recv_structured()

        if msg.header != MSG_VERIFY_HASH:
            raise ValueError(f"Expected {MSG_VERIFY_HASH}, got {msg.header}")

        salt = msg.payload.get("salt")
        remote_tag = msg.payload.get("tag")

        if salt is None or remote_tag is None:
            raise ValueError("Invalid verification message: missing salt or tag")

        # Compute local hash with same salt
        local_tag = self.compute_hash(key, salt)

        # Compare tags
        match = local_tag == remote_tag

        # Track leakage
        self._leakage_bits += self._tag_bits

        # Send result to Alice
        socket.send_structured(
            StructuredMessage(MSG_VERIFY_RESULT, {"match": match})
        )

        return match

    def verify_local(
        self, key_a: List[int], key_b: List[int], salt: Optional[int] = None
    ) -> VerificationResult:
        """Verify two keys locally (for testing).

        Parameters
        ----------
        key_a : List[int]
            First key (Alice's key).
        key_b : List[int]
            Second key (Bob's key).
        salt : Optional[int], optional
            Salt to use. Generates random if None.

        Returns
        -------
        VerificationResult
            Detailed verification result.
        """
        if salt is None:
            salt = generate_hash_salt(self._tag_bits, self._rng)

        tag_a = self.compute_hash(key_a, salt)
        tag_b = self.compute_hash(key_b, salt)

        return VerificationResult(
            success=(tag_a == tag_b),
            salt=salt,
            local_tag=tag_a,
            remote_tag=tag_b,
            collision_prob=self.get_collision_probability(len(key_a)),
        )


def verify_keys_match(
    key_a: List[int],
    key_b: List[int],
    tag_bits: int = 64,
    salt: Optional[int] = None,
) -> bool:
    """Convenience function to verify two keys match locally.

    Parameters
    ----------
    key_a : List[int]
        First key.
    key_b : List[int]
        Second key.
    tag_bits : int, optional
        Tag size in bits (default 64).
    salt : Optional[int], optional
        Salt to use.

    Returns
    -------
    bool
        True if keys match according to hash.
    """
    verifier = KeyVerifier(tag_bits=tag_bits)
    result = verifier.verify_local(key_a, key_b, salt)
    return result.success
