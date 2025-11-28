"""QBER estimation functions.

This module provides functions for estimating the Quantum Bit Error Rate
(QBER) from various sources including sampling and error correction data.

Reference:
- implementation_plan.md §Phase 4
- extending_qkd_technical_aspects.md §2.1
- extending_qkd_theorethical_aspects.md §2.1

Notes
-----
QBER estimation is critical for:
1. Deciding whether to abort (QBER > 11%)
2. Computing optimal error correction parameters
3. Determining final key length via Devetak-Winter formula

The estimation must be accurate yet efficient, balancing:
- Statistical confidence (larger samples = better estimates)
- Key length (fewer sampled bits = longer final key)
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

# QBER security threshold (Shor-Preskill bound)
QBER_THRESHOLD = 0.11

# Default confidence level for intervals
DEFAULT_CONFIDENCE = 0.95


@dataclass
class QBEREstimate:
    """Result of QBER estimation.

    Attributes
    ----------
    qber : float
        Point estimate of QBER.
    confidence_interval : Tuple[float, float]
        Lower and upper bounds of confidence interval.
    confidence_level : float
        Confidence level (e.g., 0.95 for 95%).
    sample_size : int
        Number of bits used for estimation.
    error_count : int
        Number of errors observed.
    is_secure : bool
        True if upper bound of confidence interval is below threshold.
    source : str
        Description of estimation source (e.g., "sampling", "cascade", "combined").
    """

    qber: float
    confidence_interval: Tuple[float, float]
    confidence_level: float
    sample_size: int
    error_count: int
    is_secure: bool
    source: str


def estimate_qber_from_sample(
    sample_bits_alice: List[int],
    sample_bits_bob: List[int],
) -> float:
    """Estimate QBER from comparing sample bits.

    Parameters
    ----------
    sample_bits_alice : List[int]
        Alice's sample bits.
    sample_bits_bob : List[int]
        Bob's sample bits.

    Returns
    -------
    float
        Estimated QBER (0 to 1).

    Raises
    ------
    ValueError
        If sample lists have different lengths or are empty.

    Notes
    -----
    This is the direct QBER estimation from sampled bits,
    performed before error correction.
    """
    if len(sample_bits_alice) != len(sample_bits_bob):
        raise ValueError(
            f"Sample lengths must match: {len(sample_bits_alice)} != {len(sample_bits_bob)}"
        )

    if len(sample_bits_alice) == 0:
        raise ValueError("Sample cannot be empty")

    errors = sum(a != b for a, b in zip(sample_bits_alice, sample_bits_bob))
    return errors / len(sample_bits_alice)


def count_sample_errors(
    sample_bits_alice: List[int],
    sample_bits_bob: List[int],
) -> int:
    """Count errors in sample bits.

    Parameters
    ----------
    sample_bits_alice : List[int]
        Alice's sample bits.
    sample_bits_bob : List[int]
        Bob's sample bits.

    Returns
    -------
    int
        Number of errors (differing bits).

    Raises
    ------
    ValueError
        If sample lists have different lengths.
    """
    if len(sample_bits_alice) != len(sample_bits_bob):
        raise ValueError(
            f"Sample lengths must match: {len(sample_bits_alice)} != {len(sample_bits_bob)}"
        )

    return sum(a != b for a, b in zip(sample_bits_alice, sample_bits_bob))


def estimate_qber_from_cascade(
    total_bits: int,
    sample_errors: int,
    cascade_errors: int,
) -> float:
    """Estimate QBER combining sample and Cascade errors.

    Parameters
    ----------
    total_bits : int
        Total number of sifted bits.
    sample_errors : int
        Errors found in sampling phase.
    cascade_errors : int
        Errors corrected during Cascade.

    Returns
    -------
    float
        Estimated QBER (0 to 1).

    Raises
    ------
    ValueError
        If total_bits is not positive or error counts are negative.

    Notes
    -----
    Implements integrated QBER estimation from theoretical doc §2.1.

    The total error count is the sum of:
    - Errors found during initial sampling
    - Errors corrected during Cascade reconciliation

    This provides a more accurate estimate than sampling alone.
    """
    if total_bits <= 0:
        raise ValueError(f"Total bits must be positive, got {total_bits}")
    if sample_errors < 0:
        raise ValueError(f"Sample errors must be non-negative, got {sample_errors}")
    if cascade_errors < 0:
        raise ValueError(f"Cascade errors must be non-negative, got {cascade_errors}")

    total_errors = sample_errors + cascade_errors
    return total_errors / total_bits


def compute_confidence_interval(
    error_count: int,
    sample_size: int,
    confidence_level: float = DEFAULT_CONFIDENCE,
) -> Tuple[float, float]:
    """Compute confidence interval for QBER estimate.

    Uses the Clopper-Pearson exact method for binomial proportions.

    Parameters
    ----------
    error_count : int
        Number of errors observed.
    sample_size : int
        Total number of bits sampled.
    confidence_level : float, optional
        Desired confidence level (default 0.95).

    Returns
    -------
    Tuple[float, float]
        Lower and upper bounds of confidence interval.

    Raises
    ------
    ValueError
        If parameters are invalid.

    Notes
    -----
    The Clopper-Pearson interval is exact and conservative,
    meaning the actual coverage is at least the nominal level.

    Uses the relationship between binomial and beta distributions
    for efficient computation.
    """
    if sample_size <= 0:
        raise ValueError(f"Sample size must be positive, got {sample_size}")
    if error_count < 0 or error_count > sample_size:
        raise ValueError(
            f"Error count must be in [0, {sample_size}], got {error_count}"
        )
    if confidence_level <= 0 or confidence_level >= 1:
        raise ValueError(
            f"Confidence level must be in (0, 1), got {confidence_level}"
        )

    alpha = 1 - confidence_level

    # Use scipy for beta distribution quantiles
    try:
        from scipy import stats

        # Lower bound using beta distribution
        if error_count == 0:
            lower = 0.0
        else:
            lower = stats.beta.ppf(alpha / 2, error_count, sample_size - error_count + 1)

        # Upper bound using beta distribution
        if error_count == sample_size:
            upper = 1.0
        else:
            upper = stats.beta.ppf(
                1 - alpha / 2, error_count + 1, sample_size - error_count
            )

        return (float(lower), float(upper))

    except ImportError:
        # Fallback to normal approximation if scipy not available
        p_hat = error_count / sample_size
        z = 1.96 if confidence_level == 0.95 else 2.576  # 95% or 99%
        margin = z * np.sqrt(p_hat * (1 - p_hat) / sample_size)
        return (max(0.0, p_hat - margin), min(1.0, p_hat + margin))


def estimate_qber_detailed(
    total_bits: int,
    sample_errors: int,
    cascade_errors: int,
    sample_size: Optional[int] = None,
    confidence_level: float = DEFAULT_CONFIDENCE,
) -> QBEREstimate:
    """Estimate QBER with detailed statistics.

    Parameters
    ----------
    total_bits : int
        Total number of sifted bits.
    sample_errors : int
        Errors found in sampling phase.
    cascade_errors : int
        Errors corrected during Cascade.
    sample_size : int, optional
        Number of bits used for estimation. If None, uses total_bits.
    confidence_level : float, optional
        Confidence level for interval (default 0.95).

    Returns
    -------
    QBEREstimate
        Detailed estimation result.
    """
    qber = estimate_qber_from_cascade(total_bits, sample_errors, cascade_errors)

    effective_sample = sample_size if sample_size is not None else total_bits
    total_errors = sample_errors + cascade_errors

    ci = compute_confidence_interval(
        min(total_errors, effective_sample),  # Cap at sample size
        effective_sample,
        confidence_level,
    )

    return QBEREstimate(
        qber=qber,
        confidence_interval=ci,
        confidence_level=confidence_level,
        sample_size=effective_sample,
        error_count=total_errors,
        is_secure=ci[1] < QBER_THRESHOLD,  # Upper bound below threshold
        source="combined" if cascade_errors > 0 else "sampling",
    )


def is_qber_acceptable(
    qber: float,
    threshold: float = QBER_THRESHOLD,
) -> bool:
    """Check if QBER is below the security threshold.

    Parameters
    ----------
    qber : float
        Estimated QBER.
    threshold : float, optional
        Maximum acceptable QBER (default 0.11).

    Returns
    -------
    bool
        True if qber < threshold.
    """
    return qber < threshold


def estimate_qber_with_correction(
    observed_qber: float,
    sample_fraction: float,
) -> float:
    """Apply finite-sample correction to QBER estimate.

    Parameters
    ----------
    observed_qber : float
        Observed QBER from sampling.
    sample_fraction : float
        Fraction of total bits used for sampling (0 < f < 1).

    Returns
    -------
    float
        Corrected QBER estimate.

    Notes
    -----
    When only a fraction of bits are sampled, the observed QBER
    may slightly underestimate or overestimate the true QBER.
    This function applies a conservative correction.

    For large samples (f > 0.1), the correction is minimal.
    """
    if sample_fraction <= 0 or sample_fraction >= 1:
        raise ValueError(
            f"Sample fraction must be in (0, 1), got {sample_fraction}"
        )

    # Conservative correction factor
    # Increases estimate slightly for very small samples
    correction = 1.0 + 0.01 * (1.0 - sample_fraction) / sample_fraction

    return min(0.5, observed_qber * correction)


def compute_optimal_sample_size(
    total_bits: int,
    target_precision: float = 0.01,
    confidence_level: float = DEFAULT_CONFIDENCE,
    expected_qber: float = 0.05,
) -> int:
    """Compute optimal sample size for QBER estimation.

    Balances precision requirements against key length reduction.

    Parameters
    ----------
    total_bits : int
        Total number of sifted bits available.
    target_precision : float, optional
        Desired half-width of confidence interval (default 0.01).
    confidence_level : float, optional
        Confidence level (default 0.95).
    expected_qber : float, optional
        Expected QBER for variance calculation (default 0.05).

    Returns
    -------
    int
        Recommended sample size.

    Notes
    -----
    Uses the normal approximation for binomial proportions to
    estimate required sample size. The actual sample size is
    capped at total_bits.
    """
    if total_bits <= 0:
        raise ValueError(f"Total bits must be positive, got {total_bits}")
    if target_precision <= 0:
        raise ValueError(f"Target precision must be positive, got {target_precision}")

    # Z-score for confidence level
    from scipy import stats

    z = stats.norm.ppf(1 - (1 - confidence_level) / 2)

    # Sample size formula: n = (z^2 * p * (1-p)) / precision^2
    variance = expected_qber * (1 - expected_qber)
    n_required = int(np.ceil((z ** 2 * variance) / (target_precision ** 2)))

    # Cap at total available bits, but use at least 100
    return max(100, min(n_required, total_bits))
