"""Simplified Cascade error reconciliation protocol.

This is a more robust implementation that uses explicit synchronization
to avoid message ordering issues with the original Cascade implementation.

Reference:
- implementation_plan.md §Phase 2
- extending_qkd_theorethical_aspects.md §2.4

The key difference from the complex Cascade:
- No backtracking (simplifies synchronization)  
- All passes complete before moving on
- Explicit block ordering agreement
"""

from typing import TYPE_CHECKING, Generator, List, Optional, Protocol, Union

import numpy as np
from netqasm.sdk.classical_communication.message import StructuredMessage
from pydynaa import EventExpression

from hackathon_challenge.core.constants import DEFAULT_NUM_PASSES
from hackathon_challenge.reconciliation.utils import (
    compute_optimal_block_size,
    compute_parity,
    permute_indices,
    split_into_blocks,
)

if TYPE_CHECKING:
    from hackathon_challenge.auth.socket import AuthenticatedSocket


class SocketProtocol(Protocol):
    """Protocol for socket-like objects supporting structured messages."""

    def send_structured(self, msg: StructuredMessage) -> None:
        ...

    def recv_structured(
        self, **kwargs
    ) -> Generator[EventExpression, None, StructuredMessage]:
        ...


# Message types for simplified cascade
MSG_PARITIES = "CASCADE_PARITIES"
MSG_SEARCH_REQUEST = "CASCADE_SEARCH"
MSG_SEARCH_RESPONSE = "CASCADE_RESP" 
MSG_SEARCH_COMPLETE = "CASCADE_DONE"
MSG_PASS_SYNC = "CASCADE_SYNC"


class SimpleCascadeReconciliator:
    """Simplified Cascade implementation with explicit synchronization.

    This implementation avoids complex backtracking to ensure both parties
    stay synchronized during the protocol.

    Parameters
    ----------
    socket : AuthenticatedSocket
        Authenticated classical channel to the peer.
    is_initiator : bool
        True if this party initiates (Alice), False for responder (Bob).
    key : List[int]
        Local raw key bits (0/1).
    rng_seed : int
        Shared permutation seed.
    num_passes : int
        Number of Cascade passes.
    initial_block_size : Optional[int]
        Initial block size. If None, computed from QBER.
    estimated_qber : Optional[float]
        Estimated QBER for computing optimal block size.
    """

    def __init__(
        self,
        socket: Union["AuthenticatedSocket", SocketProtocol],
        is_initiator: bool,
        key: List[int],
        rng_seed: int,
        num_passes: int = DEFAULT_NUM_PASSES,
        initial_block_size: Optional[int] = None,
        estimated_qber: Optional[float] = None,
    ) -> None:
        self._socket = socket
        self._is_initiator = is_initiator
        self._key = np.array(key, dtype=np.uint8)
        self._rng_seed = rng_seed
        self._num_passes = num_passes
        self._leakage_bits: int = 0
        self._errors_corrected: int = 0

        # Compute initial block size
        if initial_block_size is not None:
            self._initial_block_size = max(4, initial_block_size)
        elif estimated_qber is not None and estimated_qber > 0:
            self._initial_block_size = compute_optimal_block_size(estimated_qber)
        else:
            # For QBER=0 or unknown, use larger blocks to minimize leakage
            # With no errors expected, large blocks are more efficient
            self._initial_block_size = max(4, len(self._key) // 4)

    def reconcile(self) -> Generator[EventExpression, None, int]:
        """Run all Cascade passes and return total parity leakage.

        Yields
        ------
        EventExpression
            Network operation events.

        Returns
        -------
        int
            Total information leakage in bits.
        """
        block_size = self._initial_block_size

        for pass_idx in range(self._num_passes):
            yield from self._run_pass(pass_idx, block_size)
            block_size *= 2

        return self._leakage_bits

    def get_key(self) -> List[int]:
        """Return the reconciled key."""
        return self._key.tolist()

    def get_key_array(self) -> np.ndarray:
        """Return the reconciled key as numpy array."""
        return self._key.copy()

    def get_leakage(self) -> int:
        """Return total information leakage in bits."""
        return self._leakage_bits

    def get_errors_corrected(self) -> int:
        """Return total number of errors corrected."""
        return self._errors_corrected

    def _run_pass(
        self, pass_index: int, block_size: int
    ) -> Generator[EventExpression, None, None]:
        """Execute a single Cascade pass.

        Parameters
        ----------
        pass_index : int
            Current pass index.
        block_size : int
            Block size for this pass.
        """
        # Get permutation for this pass
        permutation = permute_indices(len(self._key), self._rng_seed, pass_index)

        # Split into blocks (in permuted space)
        blocks = split_into_blocks(len(self._key), block_size)

        # Convert to original indices
        original_blocks: List[List[int]] = []
        for block in blocks:
            original_indices = [int(permutation[i]) for i in block]
            original_blocks.append(original_indices)

        # Compute local parities
        local_parities = [compute_parity(self._key, block) for block in original_blocks]

        # Exchange parities
        if self._is_initiator:
            # Alice sends first
            self._socket.send_structured(StructuredMessage(MSG_PARITIES, local_parities))
            response = yield from self._socket.recv_structured()
            remote_parities = response.payload
        else:
            # Bob receives first
            response = yield from self._socket.recv_structured()
            remote_parities = response.payload
            self._socket.send_structured(StructuredMessage(MSG_PARITIES, local_parities))

        self._leakage_bits += len(original_blocks)

        # Find mismatched blocks (both parties will find same blocks)
        mismatched_indices = []
        for i, (lp, rp) in enumerate(zip(local_parities, remote_parities)):
            if lp != rp:
                mismatched_indices.append(i)

        # Process each mismatched block with binary search
        for block_idx in mismatched_indices:
            block = original_blocks[block_idx]
            yield from self._binary_search(block)

        # Sync point to ensure both parties finished this pass
        if self._is_initiator:
            self._socket.send_structured(StructuredMessage(MSG_PASS_SYNC, pass_index))
            response = yield from self._socket.recv_structured()
        else:
            response = yield from self._socket.recv_structured()
            self._socket.send_structured(StructuredMessage(MSG_PASS_SYNC, pass_index))

    def _binary_search(
        self, block_indices: List[int]
    ) -> Generator[EventExpression, None, Optional[int]]:
        """Run binary search on a block to find and correct one error.

        Parameters
        ----------
        block_indices : List[int]
            Indices of the block with odd parity.

        Returns
        -------
        Optional[int]
            Index of the corrected error.
        """
        if len(block_indices) == 0:
            return None

        if len(block_indices) == 1:
            # Single bit - initiator flips
            if self._is_initiator:
                self._key[block_indices[0]] ^= 1
            # Both parties track the error
            self._errors_corrected += 1
            return block_indices[0]

        # Binary search
        left = 0
        right = len(block_indices)

        while right - left > 1:
            mid = (left + right) // 2
            left_half = block_indices[left:mid]

            # Exchange parities for left half
            local_parity = compute_parity(self._key, left_half)

            if self._is_initiator:
                self._socket.send_structured(
                    StructuredMessage(MSG_SEARCH_REQUEST, {"indices": left_half, "parity": local_parity})
                )
                response = yield from self._socket.recv_structured()
                remote_parity = response.payload["parity"]
            else:
                response = yield from self._socket.recv_structured()
                remote_parity = response.payload["parity"]
                self._socket.send_structured(
                    StructuredMessage(MSG_SEARCH_RESPONSE, {"indices": left_half, "parity": local_parity})
                )

            self._leakage_bits += 1

            if local_parity != remote_parity:
                right = mid
            else:
                left = mid

        # Found the error
        error_idx = block_indices[left]

        # Only initiator flips the bit to converge to same value
        if self._is_initiator:
            self._key[error_idx] ^= 1
        # Both parties track the error count
        self._errors_corrected += 1

        # Signal completion
        if self._is_initiator:
            self._socket.send_structured(StructuredMessage(MSG_SEARCH_COMPLETE, error_idx))
            yield from self._socket.recv_structured()
        else:
            yield from self._socket.recv_structured()
            self._socket.send_structured(StructuredMessage(MSG_SEARCH_COMPLETE, error_idx))

        return error_idx
