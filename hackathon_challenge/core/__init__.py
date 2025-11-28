"""Core package initialization."""

from hackathon_challenge.core.constants import (
    QBER_THRESHOLD,
    MIN_KEY_LENGTH,
    SECURITY_PARAMETER,
    DEFAULT_CASCADE_SEED,
    DEFAULT_MAX_QUBITS,
    DEFAULT_NUM_EPR_PAIRS,
    DEFAULT_NUM_TEST_BITS,
    DEFAULT_TAG_BITS,
    MSG_ALL_MEASURED,
    MSG_PA_SEED,
    RESULT_ERROR,
    RESULT_KEY_LENGTH,
    RESULT_LEAKAGE,
    RESULT_QBER,
    RESULT_SECRET_KEY,
    RESULT_SUCCESS,
)
from hackathon_challenge.core.base import (
    CascadeConfig,
    PrivacyConfig,
    QKDResult,
)
from hackathon_challenge.core.protocol import (
    AliceProgram,
    BobProgram,
    QkdProgram,
    PairInfo,
    create_qkd_programs,
)

__all__ = [
    # Constants
    "QBER_THRESHOLD",
    "MIN_KEY_LENGTH",
    "SECURITY_PARAMETER",
    "DEFAULT_CASCADE_SEED",
    "DEFAULT_MAX_QUBITS",
    "DEFAULT_NUM_EPR_PAIRS",
    "DEFAULT_NUM_TEST_BITS",
    "DEFAULT_TAG_BITS",
    "MSG_ALL_MEASURED",
    "MSG_PA_SEED",
    "RESULT_ERROR",
    "RESULT_KEY_LENGTH",
    "RESULT_LEAKAGE",
    "RESULT_QBER",
    "RESULT_SECRET_KEY",
    "RESULT_SUCCESS",
    # Config dataclasses
    "CascadeConfig",
    "PrivacyConfig",
    "QKDResult",
    # Protocol classes
    "AliceProgram",
    "BobProgram",
    "QkdProgram",
    "PairInfo",
    "create_qkd_programs",
]
