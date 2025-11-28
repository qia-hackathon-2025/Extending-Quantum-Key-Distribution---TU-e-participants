"""Privacy amplification using Toeplitz hashing.

This module implements privacy amplification, the final step in QKD that
converts a partially secret key into a shorter but fully secret key.

Reference:
- implementation_plan.md §Phase 4
- extending_qkd_technical_aspects.md §2.2
- extending_qkd_theorethical_aspects.md §4.2

Notes
-----
Privacy amplification uses the Leftover Hash Lemma to extract nearly
uniform randomness from a weakly random source. The protocol:

1. Estimate information leakage (EC + verification + security margin)
2. Compute final key length using Devetak-Winter formula
3. Generate shared random Toeplitz matrix
4. Apply matrix multiplication: K_sec = T × K_ver mod 2

The security guarantee is:
- Trace distance from uniform ≤ ε_sec
- Requires sacrificing 2*log₂(1/ε_sec) bits for security margin

Typical security parameter: ε_sec = 10^-12
"""

from dataclasses import dataclass
from typing import Generator, List, Optional, Tuple, Union

import numpy as np
from netqasm.sdk.classical_communication.message import StructuredMessage
from pydynaa import EventExpression
from scipy.linalg import toeplitz

from hackathon_challenge.privacy.entropy import (
    QBER_THRESHOLD,
    compute_final_key_length,
    is_qber_secure,
)
from hackathon_challenge.privacy.utils import (
    construct_toeplitz_matrix,
    generate_toeplitz_seed,
    validate_toeplitz_seed,
)


# Message headers for privacy amplification protocol
MSG_PA_SEED = "PA_SEED"
MSG_PA_COMPLETE = "PA_COMPLETE"


@dataclass
class AmplificationResult:
    """Result of privacy amplification.

    Attributes
    ----------
    secret_key : List[int]
        Final secret key bits.
    input_length : int
        Length of input (reconciled) key.
    output_length : int
        Length of output (secret) key.
    compression_ratio : float
        Ratio of output to input length.
    toeplitz_seed : Optional[List[int]]
        Seed used for Toeplitz matrix (stored for verification).
    success : bool
        True if amplification succeeded.
    error_message : Optional[str]
        Error message if amplification failed.
    leakage_ec : int
        Information leakage from error correction.
    leakage_ver : int
        Information leakage from verification.
    qber : float
        QBER used in calculation.
    security_parameter : float
        Epsilon security parameter.
    """

    secret_key: List[int]
    input_length: int
    output_length: int
    compression_ratio: float
    toeplitz_seed: Optional[List[int]] = None
    success: bool = True
    error_message: Optional[str] = None
    leakage_ec: int = 0
    leakage_ver: int = 0
    qber: float = 0.0
    security_parameter: float = 1e-12


class PrivacyAmplifier:
    """Toeplitz-matrix-based privacy amplification.

    Implements privacy amplification using 2-universal Toeplitz hashing
    with full support for parameter validation and leakage accounting.

    Parameters
    ----------
    epsilon_sec : float, optional
        Security parameter (default 1e-12).
        Determines the trace distance from uniform of the final key.
    rng_seed : Optional[int], optional
        Seed for deterministic Toeplitz matrix generation.
        Use for testing; leave None for cryptographic randomness.

    Attributes
    ----------
    epsilon_sec : float
        Security parameter.
    _rng_seed : Optional[int]
        Random seed for deterministic operation.

    Notes
    -----
    Implements the Leftover Hash Lemma using 2-universal Toeplitz matrices.
    Security guarantee: ||ρ_KE - ρ_U ⊗ ρ_E||_1 ≤ ε_sec

    Reference: theoretical doc §4.2
    """

    def __init__(
        self,
        epsilon_sec: float = 1e-12,
        rng_seed: Optional[int] = None,
    ) -> None:
        """Initialize privacy amplifier.

        Parameters
        ----------
        epsilon_sec : float
            Security parameter.
        rng_seed : Optional[int]
            Seed for deterministic operation.
        """
        if epsilon_sec <= 0 or epsilon_sec > 1:
            raise ValueError(
                f"Security parameter must be in (0, 1], got {epsilon_sec}"
            )

        self.epsilon_sec = epsilon_sec
        self._rng_seed = rng_seed

    def compute_output_length(
        self,
        input_length: int,
        qber: float,
        leakage_ec: int,
        leakage_ver: int,
    ) -> int:
        """Compute optimal output key length.

        Parameters
        ----------
        input_length : int
            Length of reconciled key.
        qber : float
            Quantum Bit Error Rate.
        leakage_ec : int
            Information leaked during error correction.
        leakage_ver : int
            Information leaked during verification.

        Returns
        -------
        int
            Optimal output key length.
        """
        return compute_final_key_length(
            reconciled_length=input_length,
            qber=qber,
            leakage_ec=leakage_ec,
            leakage_ver=leakage_ver,
            epsilon_sec=self.epsilon_sec,
        )

    def generate_seed(
        self,
        input_length: int,
        output_length: int,
    ) -> List[int]:
        """Generate Toeplitz seed for given dimensions.

        Parameters
        ----------
        input_length : int
            Number of columns (input key length).
        output_length : int
            Number of rows (output key length).

        Returns
        -------
        List[int]
            Random seed bits.
        """
        return generate_toeplitz_seed(
            key_length=input_length,
            final_length=output_length,
            rng_seed=self._rng_seed,
        )

    def amplify(
        self,
        key: List[int],
        toeplitz_seed: List[int],
        new_length: int,
    ) -> List[int]:
        """Apply Toeplitz hashing for privacy amplification.

        Parameters
        ----------
        key : List[int]
            Reconciled and verified key bits.
        toeplitz_seed : List[int]
            Random seed defining the Toeplitz matrix.
        new_length : int
            Desired output key length.

        Returns
        -------
        List[int]
            Final secret key bits.

        Raises
        ------
        ValueError
            If parameters are invalid.

        Notes
        -----
        Computes K_sec = T × K_ver where T is a Toeplitz matrix.
        Matrix multiplication is performed modulo 2.
        """
        # Validate inputs
        if not key:
            raise ValueError("Key cannot be empty")
        if new_length <= 0:
            raise ValueError(f"Output length must be positive, got {new_length}")
        if new_length > len(key):
            raise ValueError(
                f"Output length ({new_length}) cannot exceed input length ({len(key)})"
            )

        expected_seed_length = len(key) + new_length - 1
        if len(toeplitz_seed) != expected_seed_length:
            raise ValueError(
                f"Seed length must be {expected_seed_length}, got {len(toeplitz_seed)}"
            )

        key_arr = np.array(key, dtype=np.uint8)

        # Construct Toeplitz matrix from seed
        # scipy.linalg.toeplitz(c, r) creates a Toeplitz matrix where:
        # - c is the first column
        # - r is the first row (first element of r is ignored, using c[0] instead)
        col = toeplitz_seed[:new_length]
        row = toeplitz_seed[new_length - 1 : new_length - 1 + len(key)]
        T = toeplitz(col, row).astype(np.uint8)

        # Matrix multiplication mod 2
        result = (T @ key_arr) % 2
        return result.astype(int).tolist()

    def amplify_with_result(
        self,
        key: List[int],
        qber: float,
        leakage_ec: int,
        leakage_ver: int,
        toeplitz_seed: Optional[List[int]] = None,
    ) -> AmplificationResult:
        """Perform complete privacy amplification with validation.

        Parameters
        ----------
        key : List[int]
            Reconciled and verified key bits.
        qber : float
            Quantum Bit Error Rate.
        leakage_ec : int
            Information leaked during error correction.
        leakage_ver : int
            Information leaked during verification.
        toeplitz_seed : Optional[List[int]]
            Pre-shared Toeplitz seed. If None, generates new seed.

        Returns
        -------
        AmplificationResult
            Complete result with metadata.

        Notes
        -----
        This is the recommended high-level interface. It:
        1. Validates QBER is below threshold
        2. Computes optimal output length
        3. Generates/validates Toeplitz seed
        4. Applies privacy amplification
        5. Returns detailed result
        """
        input_length = len(key)

        # Check security threshold
        if not is_qber_secure(qber, QBER_THRESHOLD):
            return AmplificationResult(
                secret_key=[],
                input_length=input_length,
                output_length=0,
                compression_ratio=0.0,
                toeplitz_seed=None,
                success=False,
                error_message=f"QBER ({qber:.4f}) exceeds threshold ({QBER_THRESHOLD})",
                leakage_ec=leakage_ec,
                leakage_ver=leakage_ver,
                qber=qber,
                security_parameter=self.epsilon_sec,
            )

        # Compute output length
        output_length = self.compute_output_length(
            input_length=input_length,
            qber=qber,
            leakage_ec=leakage_ec,
            leakage_ver=leakage_ver,
        )

        if output_length <= 0:
            return AmplificationResult(
                secret_key=[],
                input_length=input_length,
                output_length=0,
                compression_ratio=0.0,
                toeplitz_seed=None,
                success=False,
                error_message="Computed output length is zero or negative",
                leakage_ec=leakage_ec,
                leakage_ver=leakage_ver,
                qber=qber,
                security_parameter=self.epsilon_sec,
            )

        # Generate or validate seed
        if toeplitz_seed is None:
            toeplitz_seed = self.generate_seed(input_length, output_length)
        else:
            if not validate_toeplitz_seed(toeplitz_seed, input_length, output_length):
                return AmplificationResult(
                    secret_key=[],
                    input_length=input_length,
                    output_length=output_length,
                    compression_ratio=0.0,
                    toeplitz_seed=toeplitz_seed,
                    success=False,
                    error_message="Invalid Toeplitz seed",
                    leakage_ec=leakage_ec,
                    leakage_ver=leakage_ver,
                    qber=qber,
                    security_parameter=self.epsilon_sec,
                )

        # Apply amplification
        try:
            secret_key = self.amplify(key, toeplitz_seed, output_length)
        except Exception as e:
            return AmplificationResult(
                secret_key=[],
                input_length=input_length,
                output_length=output_length,
                compression_ratio=0.0,
                toeplitz_seed=toeplitz_seed,
                success=False,
                error_message=f"Amplification failed: {str(e)}",
                leakage_ec=leakage_ec,
                leakage_ver=leakage_ver,
                qber=qber,
                security_parameter=self.epsilon_sec,
            )

        return AmplificationResult(
            secret_key=secret_key,
            input_length=input_length,
            output_length=output_length,
            compression_ratio=output_length / input_length,
            toeplitz_seed=toeplitz_seed,
            success=True,
            error_message=None,
            leakage_ec=leakage_ec,
            leakage_ver=leakage_ver,
            qber=qber,
            security_parameter=self.epsilon_sec,
        )

    def amplify_fixed_length(
        self,
        key: List[int],
        output_length: int,
        toeplitz_seed: Optional[List[int]] = None,
    ) -> Tuple[List[int], List[int]]:
        """Perform privacy amplification with fixed output length.

        Parameters
        ----------
        key : List[int]
            Input key bits.
        output_length : int
            Desired output length.
        toeplitz_seed : Optional[List[int]]
            Pre-shared seed. If None, generates new seed.

        Returns
        -------
        Tuple[List[int], List[int]]
            (secret_key, toeplitz_seed) tuple.

        Notes
        -----
        Use this method when you want direct control over output length
        without automatic computation from QBER and leakage.
        """
        if toeplitz_seed is None:
            toeplitz_seed = self.generate_seed(len(key), output_length)

        secret_key = self.amplify(key, toeplitz_seed, output_length)
        return secret_key, toeplitz_seed


def apply_privacy_amplification(
    key: List[int],
    qber: float,
    leakage_ec: int,
    leakage_ver: int,
    epsilon_sec: float = 1e-12,
    toeplitz_seed: Optional[List[int]] = None,
) -> AmplificationResult:
    """Convenience function for privacy amplification.

    Parameters
    ----------
    key : List[int]
        Reconciled and verified key bits.
    qber : float
        Quantum Bit Error Rate.
    leakage_ec : int
        Information leaked during error correction.
    leakage_ver : int
        Information leaked during verification.
    epsilon_sec : float, optional
        Security parameter (default 1e-12).
    toeplitz_seed : Optional[List[int]]
        Pre-shared Toeplitz seed. If None, generates new seed.

    Returns
    -------
    AmplificationResult
        Complete amplification result.

    Notes
    -----
    This is a convenience wrapper around PrivacyAmplifier.
    Use PrivacyAmplifier directly for more control.
    """
    amplifier = PrivacyAmplifier(epsilon_sec=epsilon_sec)
    return amplifier.amplify_with_result(
        key=key,
        qber=qber,
        leakage_ec=leakage_ec,
        leakage_ver=leakage_ver,
        toeplitz_seed=toeplitz_seed,
    )
