"""Authentication package for QKD classical channel security.

This package provides information-theoretic and computational authentication
mechanisms for securing the classical channel in QKD protocols.

Modules
-------
exceptions
    Custom exceptions for authentication failures.
socket
    AuthenticatedSocket wrapper for ClassicalSocket.
wegman_carter
    Wegman-Carter authentication primitives using Toeplitz hashing.

Classes
-------
AuthenticatedSocket
    HMAC-authenticated wrapper for SquidASM ClassicalSocket.
SecurityError
    Base exception for authentication/security failures.
IntegrityError
    Exception raised when message integrity check fails.
ToeplitzAuthenticator
    Stateful Wegman-Carter authenticator.

Functions
---------
generate_auth_tag
    Generate Wegman-Carter authentication tag.
verify_auth_tag
    Verify Wegman-Carter authentication tag.

References
----------
- implementation_plan.md §Phase 1
- extending_qkd_theorethical_aspects.md Step 3
- extending_qkd_technical_aspects.md §3.1
"""

from hackathon_challenge.auth.exceptions import IntegrityError, SecurityError
from hackathon_challenge.auth.socket import AuthenticatedSocket
from hackathon_challenge.auth.wegman_carter import (
    DEFAULT_TAG_BITS,
    ToeplitzAuthenticator,
    generate_auth_tag,
    generate_toeplitz_seed_bits,
    verify_auth_tag,
)

__all__ = [
    # Exceptions
    "SecurityError",
    "IntegrityError",
    # Socket wrapper
    "AuthenticatedSocket",
    # Wegman-Carter primitives
    "generate_auth_tag",
    "verify_auth_tag",
    "generate_toeplitz_seed_bits",
    "ToeplitzAuthenticator",
    "DEFAULT_TAG_BITS",
]
