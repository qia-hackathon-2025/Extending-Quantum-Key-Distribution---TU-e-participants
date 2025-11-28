"""Main QKD protocol implementation (Alice and Bob programs).

This module integrates all post-processing components into a complete
QKD protocol implementation for SquidASM:
- Authentication layer (HMAC-based)
- Cascade reconciliation (interactive error correction)
- Polynomial hash verification (key equality check)
- Privacy amplification (Toeplitz hashing)

Reference:
- implementation_plan.md §Phase 5
- extending_qkd_technical_aspects.md §Step 4
- squidasm/examples/applications/qkd/example_qkd.py (baseline)

Notes
-----
The protocol follows the standard BB84 post-processing pipeline:
1. EPR distribution and measurement (quantum phase)
2. Basis sifting (classical)
3. QBER estimation via sampling
4. Cascade reconciliation
5. Universal hash verification
6. Privacy amplification

Key SquidASM patterns:
- All network operations must use `yield from`
- recv methods are generators returning Generator[EventExpression, None, T]
- flush() must follow quantum operations
- ProgramMeta must declare all sockets used
"""

import abc
import random
from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Optional, Tuple, Union

from netqasm.sdk.classical_communication.message import StructuredMessage
from pydynaa import EventExpression
from squidasm.sim.stack.program import Program, ProgramContext, ProgramMeta

from hackathon_challenge.auth.socket import AuthenticatedSocket
from hackathon_challenge.core.base import QKDResult
from hackathon_challenge.core.constants import (
    DEFAULT_CASCADE_SEED,
    DEFAULT_MAX_QUBITS,
    DEFAULT_NUM_EPR_PAIRS,
    DEFAULT_NUM_TEST_BITS,
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
from hackathon_challenge.privacy.amplifier import PrivacyAmplifier
from hackathon_challenge.privacy.entropy import compute_final_key_length
from hackathon_challenge.privacy.estimation import estimate_qber_from_cascade
from hackathon_challenge.privacy.utils import generate_toeplitz_seed
from hackathon_challenge.reconciliation.simple_cascade import SimpleCascadeReconciliator
from hackathon_challenge.utils.logging import get_logger
from hackathon_challenge.verification.verifier import KeyVerifier


# Module logger
logger = get_logger(__name__)


@dataclass
class PairInfo:
    """Information about one generated EPR pair.

    Attributes are filled progressively during the protocol.
    Extends the baseline PairInfo from example_qkd.py.

    Attributes
    ----------
    index : int
        Index in list of all generated pairs.
    basis : int
        Basis this node measured in. 0 = Z, 1 = X.
    outcome : int
        Measurement outcome (0 or 1).
    same_basis : Optional[bool]
        Whether peer measured in same basis.
    test_outcome : Optional[bool]
        Whether this pair is used for error estimation.
    same_outcome : Optional[bool]
        Whether outcomes match (only for test pairs).
    """

    index: int
    basis: int
    outcome: int
    same_basis: Optional[bool] = None
    test_outcome: Optional[bool] = None
    same_outcome: Optional[bool] = None


class QkdProgram(Program, abc.ABC):
    """Base class for QKD protocol programs.

    Provides common functionality for EPR distribution, basis sifting,
    and error estimation. Subclassed by AliceProgram and BobProgram.

    Parameters
    ----------
    num_epr_pairs : int
        Number of EPR pairs to generate/receive.
    num_test_bits : int, optional
        Number of bits for QBER estimation.
    cascade_seed : int, optional
        Shared RNG seed for Cascade permutations.
    auth_key : bytes, optional
        Pre-shared authentication key.

    Attributes
    ----------
    PEER : str
        Name of peer node (must be defined by subclass).
    _logger : logging.Logger
        Protocol logger instance.

    Notes
    -----
    Follows SquidASM generator patterns for network operations.
    All methods that touch the network must use `yield from`.

    Reference: squidasm/examples/applications/qkd/example_qkd.py
    """

    PEER: str  # Must be defined by subclass

    def __init__(
        self,
        num_epr_pairs: int = DEFAULT_NUM_EPR_PAIRS,
        num_test_bits: Optional[int] = None,
        cascade_seed: int = DEFAULT_CASCADE_SEED,
        auth_key: Optional[bytes] = None,
        verification_tag_bits: int = DEFAULT_TAG_BITS,
        security_parameter: float = SECURITY_PARAMETER,
    ) -> None:
        """Initialize QKD program.

        Parameters
        ----------
        num_epr_pairs : int
            Number of EPR pairs to generate.
        num_test_bits : Optional[int]
            Bits for QBER estimation. Defaults to num_epr_pairs // 4.
        cascade_seed : int
            Shared RNG seed for Cascade.
        auth_key : Optional[bytes]
            Pre-shared authentication key.
        verification_tag_bits : int
            Hash tag bits for verification (64 or 128).
        security_parameter : float
            Security parameter for PA.
        """
        self._num_epr_pairs = num_epr_pairs
        self._num_test_bits = num_test_bits if num_test_bits else num_epr_pairs // 4
        self._cascade_seed = cascade_seed
        self._auth_key = auth_key or b"default_shared_key_for_testing"
        self._verification_tag_bits = verification_tag_bits
        self._security_parameter = security_parameter
        self._logger = get_logger(self.__class__.__name__)

    @property
    @abc.abstractmethod
    def meta(self) -> ProgramMeta:
        """Return program metadata."""
        raise NotImplementedError

    @abc.abstractmethod
    def run(self, context: ProgramContext) -> Generator[EventExpression, None, Dict[str, Any]]:
        """Execute the QKD protocol."""
        raise NotImplementedError

    def _distribute_states(
        self, context: ProgramContext, is_initiator: bool
    ) -> Generator[EventExpression, None, List[PairInfo]]:
        """Generate and measure EPR pairs in random bases.

        Parameters
        ----------
        context : ProgramContext
            SquidASM program context.
        is_initiator : bool
            True if this node initiates EPR generation.

        Yields
        ------
        EventExpression
            Network operation events.

        Returns
        -------
        List[PairInfo]
            Information about each measured pair.

        Notes
        -----
        CRITICAL: Must call `yield from conn.flush()` after quantum ops.
        Reference: technical doc pitfall #2
        """
        conn = context.connection
        epr_socket = context.epr_sockets[self.PEER]

        results = []

        for i in range(self._num_epr_pairs):
            # Random basis: 0 = Z, 1 = X
            basis = random.randint(0, 1)

            if is_initiator:
                q = epr_socket.create_keep(1)[0]
            else:
                q = epr_socket.recv_keep(1)[0]

            # Apply Hadamard for X basis
            if basis == 1:
                q.H()

            m = q.measure()
            yield from conn.flush()

            results.append(PairInfo(index=i, outcome=int(m), basis=basis))

        return results

    def _filter_bases(
        self,
        socket: Union[AuthenticatedSocket, "ClassicalSocket"],
        pairs_info: List[PairInfo],
        is_initiator: bool,
    ) -> Generator[EventExpression, None, List[PairInfo]]:
        """Exchange bases and filter to matching pairs.

        Parameters
        ----------
        socket : AuthenticatedSocket or ClassicalSocket
            Socket for classical communication.
        pairs_info : List[PairInfo]
            Pairs from distribution phase.
        is_initiator : bool
            True if this node sends first.

        Yields
        ------
        EventExpression
            Network operation events.

        Returns
        -------
        List[PairInfo]
            Pairs with same_basis field populated.

        Notes
        -----
        Reference: example_qkd.py _filter_bases
        """
        bases = [(pair.index, pair.basis) for pair in pairs_info]

        if is_initiator:
            socket.send_structured(StructuredMessage("Bases", bases))
            response = yield from socket.recv_structured()
            remote_bases = response.payload
        else:
            response = yield from socket.recv_structured()
            remote_bases = response.payload
            socket.send_structured(StructuredMessage("Bases", bases))

        # Match bases
        for (i, basis), (remote_i, remote_basis) in zip(bases, remote_bases):
            assert i == remote_i, f"Index mismatch: {i} != {remote_i}"
            pairs_info[i].same_basis = (basis == remote_basis)

        return pairs_info

    def _estimate_error_rate(
        self,
        socket: Union[AuthenticatedSocket, "ClassicalSocket"],
        pairs_info: List[PairInfo],
        num_test_bits: int,
        is_initiator: bool,
    ) -> Generator[EventExpression, None, Tuple[List[PairInfo], float]]:
        """Estimate QBER by comparing random sample of outcomes.

        Parameters
        ----------
        socket : AuthenticatedSocket or ClassicalSocket
            Socket for classical communication.
        pairs_info : List[PairInfo]
            Pairs after basis sifting.
        num_test_bits : int
            Number of bits to sample.
        is_initiator : bool
            True if this node selects test indices.

        Yields
        ------
        EventExpression
            Network operation events.

        Returns
        -------
        Tuple[List[PairInfo], float]
            Updated pairs and estimated error rate.

        Notes
        -----
        Test bits are marked and excluded from final key.
        Reference: example_qkd.py _estimate_error_rate
        """
        if is_initiator:
            # Select random subset of same-basis pairs for testing
            same_basis_indices = [pair.index for pair in pairs_info if pair.same_basis]
            test_indices = random.sample(
                same_basis_indices, min(num_test_bits, len(same_basis_indices))
            )

            # Mark test pairs
            for pair in pairs_info:
                pair.test_outcome = pair.index in test_indices

            test_outcomes = [(i, pairs_info[i].outcome) for i in test_indices]

            # Exchange test information
            socket.send_structured(StructuredMessage("Test indices", test_indices))
            response = yield from socket.recv_structured()
            target_test_outcomes = response.payload
            socket.send_structured(StructuredMessage("Test outcomes", test_outcomes))
        else:
            # Receive test indices
            response = yield from socket.recv_structured()
            test_indices = response.payload

            # Mark test pairs
            for pair in pairs_info:
                pair.test_outcome = pair.index in test_indices

            test_outcomes = [(i, pairs_info[i].outcome) for i in test_indices]

            # Exchange test outcomes
            socket.send_structured(StructuredMessage("Test outcomes", test_outcomes))
            response = yield from socket.recv_structured()
            target_test_outcomes = response.payload

        # Count errors - sort both by index for consistent comparison
        test_outcomes_sorted = sorted(test_outcomes, key=lambda x: x[0])
        target_outcomes_sorted = sorted(target_test_outcomes, key=lambda x: x[0])

        num_errors = 0
        for (i1, t1), (i2, t2) in zip(test_outcomes_sorted, target_outcomes_sorted):
            assert i1 == i2, f"Test index mismatch: {i1} != {i2}"
            if t1 != t2:
                num_errors += 1
                pairs_info[i1].same_outcome = False
            else:
                pairs_info[i1].same_outcome = True

        error_rate = num_errors / max(1, len(test_outcomes))
        return pairs_info, error_rate

    def _extract_raw_key(self, pairs_info: List[PairInfo]) -> List[int]:
        """Extract raw key from sifted, non-test pairs.

        Parameters
        ----------
        pairs_info : List[PairInfo]
            Pairs after sifting and error sampling.

        Returns
        -------
        List[int]
            Raw key bits.
        """
        return [
            pair.outcome
            for pair in pairs_info
            if pair.same_basis and not pair.test_outcome
        ]


class AliceProgram(QkdProgram):
    """Alice's QKD protocol program (initiator).

    Implements the full QKD pipeline:
    1. EPR distribution (initiator)
    2. Basis sifting (sends first)
    3. QBER estimation (selects test indices)
    4. Cascade reconciliation (initiator)
    5. Verification (generates salt)
    6. Privacy amplification (generates seed)

    Parameters
    ----------
    num_epr_pairs : int
        Number of EPR pairs to generate.
    num_test_bits : Optional[int]
        Bits for QBER estimation.
    cascade_seed : int
        Shared RNG seed for Cascade.
    auth_key : bytes
        Pre-shared authentication key.
    verification_tag_bits : int
        Hash tag bits (64 or 128).
    security_parameter : float
        Security parameter for PA.

    Yields
    ------
    EventExpression
        SquidASM event expressions.

    Returns
    -------
    Dict[str, Any]
        Protocol result with keys:
        - "secret_key": Final key bits
        - "qber": Estimated QBER
        - "key_length": Final key length
        - "leakage": Total leakage
        - "success": Whether protocol succeeded
        - "error": Error message (if failed)

    Reference: implementation_plan.md §Phase 5 (AliceProgram)
    """

    PEER = "Bob"

    @property
    def meta(self) -> ProgramMeta:
        """Program metadata declaring sockets and qubits.

        Returns
        -------
        ProgramMeta
            Metadata with csockets, epr_sockets, and max_qubits.

        Notes
        -----
        CRITICAL: Must declare all sockets used.
        Reference: technical doc §4.2, pitfall #8
        """
        return ProgramMeta(
            name="alice_qkd",
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=DEFAULT_MAX_QUBITS,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        """Execute Alice's QKD protocol.

        Parameters
        ----------
        context : ProgramContext
            SquidASM program context.

        Yields
        ------
        EventExpression
            Network operation events.

        Returns
        -------
        Dict[str, Any]
            Protocol result dictionary.

        Notes
        -----
        Reference: implementation_plan.md §Phase 5 (run() workflow)
        """
        # ========== 1. Setup Authentication ==========
        raw_socket = context.csockets[self.PEER]
        auth_socket = AuthenticatedSocket(raw_socket, self._auth_key)
        self._logger.info("Authentication socket initialized")

        # ========== 2. Quantum Phase: EPR Distribution ==========
        pairs_info = yield from self._distribute_states(context, is_initiator=True)
        self._logger.info(f"Distributed {len(pairs_info)} EPR pairs")

        # Wait for Bob's confirmation
        response = yield from auth_socket.recv_structured()
        if response.header != MSG_ALL_MEASURED:
            self._logger.error(f"Unexpected message: {response.header}")
            return self._error_result("protocol_error", "Unexpected sync message")

        # ========== 3. Sifting ==========
        pairs_info = yield from self._filter_bases(auth_socket, pairs_info, is_initiator=True)
        same_basis_count = sum(1 for p in pairs_info if p.same_basis)
        self._logger.info(f"Sifting complete: {same_basis_count} same-basis pairs")

        # ========== 4. QBER Estimation ==========
        pairs_info, sample_qber = yield from self._estimate_error_rate(
            auth_socket, pairs_info, self._num_test_bits, is_initiator=True
        )
        self._logger.info(f"Sample QBER: {sample_qber:.4f}")

        # Check QBER threshold
        if sample_qber > QBER_THRESHOLD:
            self._logger.error(f"QBER {sample_qber:.4f} exceeds threshold {QBER_THRESHOLD}")
            return self._error_result("qber_too_high", f"QBER {sample_qber:.4f} > {QBER_THRESHOLD}")

        # ========== 5. Extract Raw Key ==========
        raw_key = self._extract_raw_key(pairs_info)
        self._logger.info(f"Raw key length: {len(raw_key)}")

        if len(raw_key) < MIN_KEY_LENGTH:
            self._logger.error(f"Raw key too short: {len(raw_key)} < {MIN_KEY_LENGTH}")
            return self._error_result("key_too_short", f"Raw key length {len(raw_key)} insufficient")

        # ========== 6. Cascade Reconciliation ==========
        reconciler = SimpleCascadeReconciliator(
            socket=auth_socket,
            is_initiator=True,
            key=raw_key,
            rng_seed=self._cascade_seed,
            estimated_qber=sample_qber,
        )
        leakage_ec = yield from reconciler.reconcile()
        reconciled_key = reconciler.get_key()
        errors_corrected = reconciler.get_errors_corrected()
        self._logger.info(
            f"Reconciliation complete: {errors_corrected} errors corrected, "
            f"{leakage_ec} bits leaked"
        )

        # ========== 7. Verification ==========
        verifier = KeyVerifier(tag_bits=self._verification_tag_bits)
        is_verified = yield from verifier.verify(
            auth_socket, reconciled_key, is_alice=True
        )
        leakage_ver = verifier.leakage_bits

        if not is_verified:
            self._logger.error("Key verification failed")
            return self._error_result("verification_failed", "Keys do not match after reconciliation")

        self._logger.info("Key verification successful")

        # ========== 8. QBER + Final Key Length ==========
        # Combine sample QBER with Cascade correction data
        total_qber = estimate_qber_from_cascade(
            total_bits=len(raw_key),
            sample_errors=int(sample_qber * self._num_test_bits),
            cascade_errors=errors_corrected,
        )

        # Compute final key length using Devetak-Winter formula
        self._logger.debug(
            f"Key length calc inputs: reconciled={len(reconciled_key)}, "
            f"qber={total_qber:.4f}, leakage_ec={leakage_ec}, leakage_ver={leakage_ver}, "
            f"epsilon={self._security_parameter}"
        )
        final_length = compute_final_key_length(
            reconciled_length=len(reconciled_key),
            qber=total_qber,
            leakage_ec=leakage_ec,
            leakage_ver=leakage_ver,
            epsilon_sec=self._security_parameter,
        )

        if final_length <= 0:
            self._logger.error(
                f"Computed final key length is {final_length}. "
                f"Inputs: reconciled={len(reconciled_key)}, qber={total_qber:.4f}, "
                f"leak_ec={leakage_ec}, leak_ver={leakage_ver}, eps={self._security_parameter}"
            )
            return self._error_result(
                "insufficient_secrecy",
                f"Cannot extract secure key (computed length: {final_length})"
            )

        self._logger.info(f"Target final key length: {final_length}")

        # ========== 9. Privacy Amplification ==========
        # Generate and share Toeplitz seed
        toeplitz_seed = generate_toeplitz_seed(len(reconciled_key), final_length)
        auth_socket.send_structured(StructuredMessage(MSG_PA_SEED, toeplitz_seed))

        # Apply privacy amplification
        amplifier = PrivacyAmplifier(epsilon_sec=self._security_parameter)
        final_key = amplifier.amplify(reconciled_key, toeplitz_seed, final_length)

        total_leakage = leakage_ec + leakage_ver
        self._logger.info(
            f"Protocol complete: {len(final_key)}-bit key, "
            f"QBER={total_qber:.4f}, leakage={total_leakage}"
        )

        return {
            RESULT_SECRET_KEY: final_key,
            RESULT_QBER: total_qber,
            RESULT_KEY_LENGTH: len(final_key),
            RESULT_LEAKAGE: total_leakage,
            RESULT_SUCCESS: True,
        }

    def _error_result(self, error_code: str, message: str) -> Dict[str, Any]:
        """Create error result dictionary.

        Parameters
        ----------
        error_code : str
            Short error identifier.
        message : str
            Human-readable error message.

        Returns
        -------
        Dict[str, Any]
            Error result.
        """
        return {
            RESULT_ERROR: error_code,
            "message": message,
            RESULT_SECRET_KEY: [],
            RESULT_SUCCESS: False,
        }


class BobProgram(QkdProgram):
    """Bob's QKD protocol program (responder).

    Mirrors Alice's protocol but with responder role:
    - EPR distribution: receives instead of creates
    - Binary search: responds to queries
    - Verification: receives salt
    - Privacy amplification: receives seed

    Parameters
    ----------
    num_epr_pairs : int
        Number of EPR pairs to receive.
    num_test_bits : Optional[int]
        Bits for QBER estimation.
    cascade_seed : int
        Shared RNG seed for Cascade.
    auth_key : bytes
        Pre-shared authentication key.
    verification_tag_bits : int
        Hash tag bits (64 or 128).
    security_parameter : float
        Security parameter for PA.

    Yields
    ------
    EventExpression
        SquidASM event expressions.

    Returns
    -------
    Dict[str, Any]
        Protocol result (same format as AliceProgram).

    Reference: implementation_plan.md §Phase 5 (BobProgram)
    """

    PEER = "Alice"

    @property
    def meta(self) -> ProgramMeta:
        """Program metadata declaring sockets and qubits.

        Returns
        -------
        ProgramMeta
            Metadata with csockets, epr_sockets, and max_qubits.
        """
        return ProgramMeta(
            name="bob_qkd",
            csockets=[self.PEER],
            epr_sockets=[self.PEER],
            max_qubits=DEFAULT_MAX_QUBITS,
        )

    def run(
        self, context: ProgramContext
    ) -> Generator[EventExpression, None, Dict[str, Any]]:
        """Execute Bob's QKD protocol.

        Parameters
        ----------
        context : ProgramContext
            SquidASM program context.

        Yields
        ------
        EventExpression
            Network operation events.

        Returns
        -------
        Dict[str, Any]
            Protocol result dictionary.
        """
        # ========== 1. Setup Authentication ==========
        raw_socket = context.csockets[self.PEER]
        auth_socket = AuthenticatedSocket(raw_socket, self._auth_key)
        self._logger.info("Authentication socket initialized")

        # ========== 2. Quantum Phase: EPR Distribution ==========
        pairs_info = yield from self._distribute_states(context, is_initiator=False)
        self._logger.info(f"Received {len(pairs_info)} EPR pairs")

        # Signal to Alice that measurement is complete
        auth_socket.send_structured(StructuredMessage(MSG_ALL_MEASURED, None))

        # ========== 3. Sifting ==========
        pairs_info = yield from self._filter_bases(auth_socket, pairs_info, is_initiator=False)
        same_basis_count = sum(1 for p in pairs_info if p.same_basis)
        self._logger.info(f"Sifting complete: {same_basis_count} same-basis pairs")

        # ========== 4. QBER Estimation ==========
        pairs_info, sample_qber = yield from self._estimate_error_rate(
            auth_socket, pairs_info, self._num_test_bits, is_initiator=False
        )
        self._logger.info(f"Sample QBER: {sample_qber:.4f}")

        # Check QBER threshold
        if sample_qber > QBER_THRESHOLD:
            self._logger.error(f"QBER {sample_qber:.4f} exceeds threshold {QBER_THRESHOLD}")
            return self._error_result("qber_too_high", f"QBER {sample_qber:.4f} > {QBER_THRESHOLD}")

        # ========== 5. Extract Raw Key ==========
        raw_key = self._extract_raw_key(pairs_info)
        self._logger.info(f"Raw key length: {len(raw_key)}")

        if len(raw_key) < MIN_KEY_LENGTH:
            self._logger.error(f"Raw key too short: {len(raw_key)} < {MIN_KEY_LENGTH}")
            return self._error_result("key_too_short", f"Raw key length {len(raw_key)} insufficient")

        # ========== 6. Cascade Reconciliation ==========
        reconciler = SimpleCascadeReconciliator(
            socket=auth_socket,
            is_initiator=False,  # Bob is responder
            key=raw_key,
            rng_seed=self._cascade_seed,
            estimated_qber=sample_qber,
        )
        leakage_ec = yield from reconciler.reconcile()
        reconciled_key = reconciler.get_key()
        errors_corrected = reconciler.get_errors_corrected()
        self._logger.info(
            f"Reconciliation complete: {errors_corrected} errors corrected, "
            f"{leakage_ec} bits leaked"
        )

        # ========== 7. Verification ==========
        verifier = KeyVerifier(tag_bits=self._verification_tag_bits)
        is_verified = yield from verifier.verify(
            auth_socket, reconciled_key, is_alice=False  # Bob is responder
        )
        leakage_ver = verifier.leakage_bits

        if not is_verified:
            self._logger.error("Key verification failed")
            return self._error_result("verification_failed", "Keys do not match after reconciliation")

        self._logger.info("Key verification successful")

        # ========== 8. QBER + Final Key Length ==========
        total_qber = estimate_qber_from_cascade(
            total_bits=len(raw_key),
            sample_errors=int(sample_qber * self._num_test_bits),
            cascade_errors=errors_corrected,
        )

        # Compute final key length (same as Alice)
        self._logger.debug(
            f"Key length calc inputs: reconciled={len(reconciled_key)}, "
            f"qber={total_qber:.4f}, leakage_ec={leakage_ec}, leakage_ver={leakage_ver}, "
            f"epsilon={self._security_parameter}"
        )
        final_length = compute_final_key_length(
            reconciled_length=len(reconciled_key),
            qber=total_qber,
            leakage_ec=leakage_ec,
            leakage_ver=leakage_ver,
            epsilon_sec=self._security_parameter,
        )

        if final_length <= 0:
            self._logger.error(
                f"Computed final key length is {final_length}. "
                f"Inputs: reconciled={len(reconciled_key)}, qber={total_qber:.4f}, "
                f"leak_ec={leakage_ec}, leak_ver={leakage_ver}, eps={self._security_parameter}"
            )
            return self._error_result(
                "insufficient_secrecy",
                f"Cannot extract secure key (computed length: {final_length})"
            )

        self._logger.info(f"Target final key length: {final_length}")

        # ========== 9. Privacy Amplification ==========
        # Receive Toeplitz seed from Alice
        response = yield from auth_socket.recv_structured()
        if response.header != MSG_PA_SEED:
            self._logger.error(f"Expected PA_SEED, got {response.header}")
            return self._error_result("protocol_error", "Missing PA seed")

        toeplitz_seed = response.payload

        # Apply privacy amplification with same seed
        amplifier = PrivacyAmplifier(epsilon_sec=self._security_parameter)
        final_key = amplifier.amplify(reconciled_key, toeplitz_seed, final_length)

        total_leakage = leakage_ec + leakage_ver
        self._logger.info(
            f"Protocol complete: {len(final_key)}-bit key, "
            f"QBER={total_qber:.4f}, leakage={total_leakage}"
        )

        return {
            RESULT_SECRET_KEY: final_key,
            RESULT_QBER: total_qber,
            RESULT_KEY_LENGTH: len(final_key),
            RESULT_LEAKAGE: total_leakage,
            RESULT_SUCCESS: True,
        }

    def _error_result(self, error_code: str, message: str) -> Dict[str, Any]:
        """Create error result dictionary.

        Parameters
        ----------
        error_code : str
            Short error identifier.
        message : str
            Human-readable error message.

        Returns
        -------
        Dict[str, Any]
            Error result.
        """
        return {
            RESULT_ERROR: error_code,
            "message": message,
            RESULT_SECRET_KEY: [],
            RESULT_SUCCESS: False,
        }


# Convenience functions for protocol execution


def create_qkd_programs(
    num_epr_pairs: int = DEFAULT_NUM_EPR_PAIRS,
    num_test_bits: Optional[int] = None,
    cascade_seed: int = DEFAULT_CASCADE_SEED,
    auth_key: bytes = b"shared_secret_key",
    verification_tag_bits: int = 64,
    security_parameter: float = SECURITY_PARAMETER,
) -> Tuple[AliceProgram, BobProgram]:
    """Create matching Alice and Bob programs.

    Parameters
    ----------
    num_epr_pairs : int
        Number of EPR pairs to generate.
    num_test_bits : Optional[int]
        Bits for QBER estimation.
    cascade_seed : int
        Shared RNG seed for Cascade.
    auth_key : bytes
        Pre-shared authentication key.
    verification_tag_bits : int
        Hash tag bits for verification.
    security_parameter : float
        Security parameter for PA.

    Returns
    -------
    Tuple[AliceProgram, BobProgram]
        Configured program instances.

    Examples
    --------
    >>> alice, bob = create_qkd_programs(num_epr_pairs=500)
    >>> # Use with squidasm.run.stack.run.run()
    """
    alice = AliceProgram(
        num_epr_pairs=num_epr_pairs,
        num_test_bits=num_test_bits,
        cascade_seed=cascade_seed,
        auth_key=auth_key,
        verification_tag_bits=verification_tag_bits,
        security_parameter=security_parameter,
    )
    bob = BobProgram(
        num_epr_pairs=num_epr_pairs,
        num_test_bits=num_test_bits,
        cascade_seed=cascade_seed,
        auth_key=auth_key,
        verification_tag_bits=verification_tag_bits,
        security_parameter=security_parameter,
    )
    return alice, bob
