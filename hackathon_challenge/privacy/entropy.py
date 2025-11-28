"""Binary entropy and key length calculation.

This module provides functions for computing information-theoretic quantities
used in QKD privacy amplification, including binary entropy, secrecy capacity,
and final key length calculations based on the Devetak-Winter formula.

Reference:
- implementation_plan.md §Phase 4
- extending_qkd_theorethical_aspects.md Step 2 §3

Notes
-----
The binary entropy function h(p) quantifies uncertainty:
- h(0) = h(1) = 0 (no uncertainty)
- h(0.5) = 1 (maximum uncertainty for a binary variable)

The Shor-Preskill bound establishes that secure key distribution
is impossible when QBER > 11% (unconditional security).
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np

# Security thresholds
QBER_THRESHOLD = 0.11  # Shor-Preskill bound (11%)
DEFAULT_EPSILON_SEC = 1e-12  # Default security parameter
MIN_EFFICIENCY_FACTOR = 0.0
MAX_EFFICIENCY_FACTOR = 1.0


@dataclass
class KeyLengthEstimate:
    """Result of key length estimation.

    Attributes
    ----------
    final_length : int
        Final secret key length (bits).
    raw_length : float
        Unrounded key length before floor operation.
    secrecy_capacity : float
        Available secrecy capacity n(1 - h(QBER)).
    total_leakage : float
        Total information leakage (EC + verification + security margin).
    is_secure : bool
        True if QBER is below threshold and key length is positive.
    qber : float
        QBER used in calculation.
    security_parameter : float
        Epsilon security parameter used.
    """

    final_length: int
    raw_length: float
    secrecy_capacity: float
    total_leakage: float
    is_secure: bool
    qber: float
    security_parameter: float


def binary_entropy(p: float) -> float:
    """Compute binary entropy function h(p).

    Parameters
    ----------
    p : float
        Probability (0 ≤ p ≤ 1).

    Returns
    -------
    float
        Binary entropy h(p) = -p*log₂(p) - (1-p)*log₂(1-p).

    Raises
    ------
    ValueError
        If p is not in [0, 1].

    Notes
    -----
    Used to quantify information leakage from quantum channel.
    At boundaries: h(0) = h(1) = 0 by convention (limit approach).

    Reference: theoretical doc Step 2 §3.1

    Examples
    --------
    >>> binary_entropy(0.5)
    1.0
    >>> binary_entropy(0.0)
    0.0
    >>> abs(binary_entropy(0.1) - 0.469) < 0.001
    True
    """
    if p < 0 or p > 1:
        raise ValueError(f"Probability must be in [0, 1], got {p}")

    if p <= 0 or p >= 1:
        return 0.0

    return float(-p * np.log2(p) - (1 - p) * np.log2(1 - p))


def binary_entropy_derivative(p: float) -> float:
    """Compute derivative of binary entropy h'(p).

    Parameters
    ----------
    p : float
        Probability (0 < p < 1).

    Returns
    -------
    float
        Derivative h'(p) = log₂((1-p)/p).

    Raises
    ------
    ValueError
        If p is not in (0, 1).

    Notes
    -----
    The derivative is useful for optimization and sensitivity analysis.
    h'(p) = 0 at p = 0.5 (maximum entropy point).
    """
    if p <= 0 or p >= 1:
        raise ValueError(f"Probability must be in (0, 1) for derivative, got {p}")

    return float(np.log2((1 - p) / p))


def inverse_binary_entropy(h_val: float, branch: str = "lower") -> float:
    """Compute inverse of binary entropy function.

    Finds p such that h(p) = h_val using Newton-Raphson iteration.

    Parameters
    ----------
    h_val : float
        Entropy value (0 ≤ h_val ≤ 1).
    branch : str, optional
        Which branch to return: "lower" (p < 0.5) or "upper" (p > 0.5).
        Default is "lower".

    Returns
    -------
    float
        Probability p such that h(p) = h_val.

    Raises
    ------
    ValueError
        If h_val is not in [0, 1] or branch is invalid.

    Notes
    -----
    Binary entropy is symmetric around p=0.5, so there are two solutions
    for any h_val in (0, 1): p and 1-p.

    Uses Newton-Raphson iteration: p_{n+1} = p_n - (h(p_n) - h_val) / h'(p_n)
    """
    if h_val < 0 or h_val > 1:
        raise ValueError(f"Entropy value must be in [0, 1], got {h_val}")

    if branch not in ("lower", "upper"):
        raise ValueError(f"Branch must be 'lower' or 'upper', got {branch}")

    # Boundary cases
    if h_val <= 1e-15:
        return 0.0 if branch == "lower" else 1.0
    if abs(h_val - 1.0) < 1e-15:
        return 0.5

    # Initial guess
    p = 0.1 if branch == "lower" else 0.9

    # Newton-Raphson iteration
    max_iterations = 100
    tolerance = 1e-12

    for _ in range(max_iterations):
        h_p = binary_entropy(p)
        error = h_p - h_val

        if abs(error) < tolerance:
            break

        h_prime = binary_entropy_derivative(p)
        if abs(h_prime) < 1e-15:
            break

        p = p - error / h_prime
        # Keep in valid range
        p = max(1e-15, min(1 - 1e-15, p))

    return float(p)


def secrecy_capacity(qber: float) -> float:
    """Compute the secrecy capacity for given QBER.

    The secrecy capacity represents the maximum rate at which
    secret key bits can be extracted per sifted bit.

    Parameters
    ----------
    qber : float
        Quantum Bit Error Rate (0 ≤ qber ≤ 0.5).

    Returns
    -------
    float
        Secrecy capacity: 1 - h(qber).
        Returns 0 if qber ≥ 0.5.

    Notes
    -----
    For BB84 with one-way classical post-processing:
    - Secrecy capacity = 1 - h(QBER) bits per sifted qubit
    - Becomes zero when QBER ≥ 0.5 (no secret key possible)
    """
    if qber < 0:
        raise ValueError(f"QBER must be non-negative, got {qber}")

    if qber >= 0.5:
        return 0.0

    return 1.0 - binary_entropy(qber)


def is_qber_secure(qber: float, threshold: float = QBER_THRESHOLD) -> bool:
    """Check if QBER is below security threshold.

    Parameters
    ----------
    qber : float
        Quantum Bit Error Rate.
    threshold : float, optional
        Maximum acceptable QBER (default: 0.11, Shor-Preskill bound).

    Returns
    -------
    bool
        True if qber < threshold, False otherwise.

    Notes
    -----
    The Shor-Preskill bound of 11% is the fundamental limit for
    unconditionally secure BB84 key distribution.
    """
    return qber < threshold


def compute_security_margin(epsilon_sec: float) -> float:
    """Compute security margin for privacy amplification.

    Parameters
    ----------
    epsilon_sec : float
        Security parameter (probability of failure).

    Returns
    -------
    float
        Security margin: 2 * log₂(1/ε_sec) bits.

    Raises
    ------
    ValueError
        If epsilon_sec is not in (0, 1].
    """
    if epsilon_sec <= 0 or epsilon_sec > 1:
        raise ValueError(f"Security parameter must be in (0, 1], got {epsilon_sec}")

    return float(2 * np.log2(1 / epsilon_sec))


def compute_final_key_length(
    reconciled_length: int,
    qber: float,
    leakage_ec: int,
    leakage_ver: int,
    epsilon_sec: float = DEFAULT_EPSILON_SEC,
    efficiency_factor: float = 1.0,
) -> int:
    """Compute final secret key length using Devetak-Winter formula.

    Parameters
    ----------
    reconciled_length : int
        Length of reconciled key after error correction.
    qber : float
        Quantum Bit Error Rate.
    leakage_ec : int
        Information leakage from error correction (bits).
    leakage_ver : int
        Information leakage from verification (bits).
    epsilon_sec : float, optional
        Security parameter (default 1e-12).
    efficiency_factor : float, optional
        Protocol efficiency factor (0 < f ≤ 1). Default 1.0.
        Accounts for practical protocol inefficiencies.

    Returns
    -------
    int
        Final secret key length (non-negative).

    Raises
    ------
    ValueError
        If parameters are out of valid ranges.

    Notes
    -----
    Formula: ℓ_sec ≈ n[1 - h(QBER)] - leak_EC - leak_ver - 2*log₂(1/ε_sec)

    The function returns 0 if QBER exceeds the security threshold.

    Reference: theoretical doc Step 2 §3.3
    """
    # Validate inputs
    if reconciled_length < 0:
        raise ValueError(f"Reconciled length must be non-negative, got {reconciled_length}")
    if qber < 0 or qber > 0.5:
        raise ValueError(f"QBER must be in [0, 0.5], got {qber}")
    if leakage_ec < 0:
        raise ValueError(f"EC leakage must be non-negative, got {leakage_ec}")
    if leakage_ver < 0:
        raise ValueError(f"Verification leakage must be non-negative, got {leakage_ver}")
    if epsilon_sec <= 0 or epsilon_sec > 1:
        raise ValueError(f"Security parameter must be in (0, 1], got {epsilon_sec}")
    if efficiency_factor <= MIN_EFFICIENCY_FACTOR or efficiency_factor > MAX_EFFICIENCY_FACTOR:
        raise ValueError(
            f"Efficiency factor must be in ({MIN_EFFICIENCY_FACTOR}, {MAX_EFFICIENCY_FACTOR}], "
            f"got {efficiency_factor}"
        )

    # Check security threshold
    if not is_qber_secure(qber):
        return 0

    # Devetak-Winter formula
    security_margin = compute_security_margin(epsilon_sec)
    available = reconciled_length * secrecy_capacity(qber) * efficiency_factor
    final_length = available - leakage_ec - leakage_ver - security_margin

    return max(0, int(np.floor(final_length)))


def compute_final_key_length_detailed(
    reconciled_length: int,
    qber: float,
    leakage_ec: int,
    leakage_ver: int,
    epsilon_sec: float = DEFAULT_EPSILON_SEC,
    efficiency_factor: float = 1.0,
) -> KeyLengthEstimate:
    """Compute final key length with detailed breakdown.

    Parameters
    ----------
    reconciled_length : int
        Length of reconciled key after error correction.
    qber : float
        Quantum Bit Error Rate.
    leakage_ec : int
        Information leakage from error correction (bits).
    leakage_ver : int
        Information leakage from verification (bits).
    epsilon_sec : float, optional
        Security parameter (default 1e-12).
    efficiency_factor : float, optional
        Protocol efficiency factor (0 < f ≤ 1). Default 1.0.

    Returns
    -------
    KeyLengthEstimate
        Detailed result including breakdown of calculations.

    Notes
    -----
    Use this function when you need diagnostic information about
    the key length calculation for debugging or reporting.
    """
    # Validate inputs (reuse validation from simple function)
    if reconciled_length < 0:
        raise ValueError(f"Reconciled length must be non-negative, got {reconciled_length}")
    if qber < 0 or qber > 0.5:
        raise ValueError(f"QBER must be in [0, 0.5], got {qber}")
    if leakage_ec < 0:
        raise ValueError(f"EC leakage must be non-negative, got {leakage_ec}")
    if leakage_ver < 0:
        raise ValueError(f"Verification leakage must be non-negative, got {leakage_ver}")
    if epsilon_sec <= 0 or epsilon_sec > 1:
        raise ValueError(f"Security parameter must be in (0, 1], got {epsilon_sec}")

    is_secure = is_qber_secure(qber)

    if not is_secure:
        return KeyLengthEstimate(
            final_length=0,
            raw_length=0.0,
            secrecy_capacity=0.0,
            total_leakage=0.0,
            is_secure=False,
            qber=qber,
            security_parameter=epsilon_sec,
        )

    security_margin = compute_security_margin(epsilon_sec)
    capacity = secrecy_capacity(qber) * efficiency_factor
    available = reconciled_length * capacity
    total_leakage = leakage_ec + leakage_ver + security_margin
    raw_length = available - total_leakage
    final_length = max(0, int(np.floor(raw_length)))

    return KeyLengthEstimate(
        final_length=final_length,
        raw_length=raw_length,
        secrecy_capacity=available,
        total_leakage=total_leakage,
        is_secure=is_secure and final_length > 0,
        qber=qber,
        security_parameter=epsilon_sec,
    )
