"""Logging utilities.

This module provides a unified logging interface that wraps SquidASM's
LogManager to provide simulation-time-aware logging throughout the
hackathon challenge code.

Reference:
- implementation_plan.md §Phase 0
- squidasm/squidasm/sim/stack/common.py (LogManager)
"""

import logging
from typing import Optional

try:
    from squidasm.sim.stack.common import LogManager
    _SQUIDASM_AVAILABLE = True
except ImportError:
    _SQUIDASM_AVAILABLE = False


# Fallback logger for when SquidASM is not available (e.g., unit tests)
_FALLBACK_LOGGERS: dict = {}


def _get_fallback_logger(name: str) -> logging.Logger:
    """Create a fallback logger when SquidASM is not available.

    Parameters
    ----------
    name : str
        Logger name.

    Returns
    -------
    logging.Logger
        Configured fallback logger.
    """
    if name not in _FALLBACK_LOGGERS:
        logger = logging.getLogger(f"hackathon.{name}")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(levelname)s:%(name)s:%(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.propagate = False
        _FALLBACK_LOGGERS[name] = logger
    return _FALLBACK_LOGGERS[name]


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger for the given module.

    When running within SquidASM simulation, uses LogManager.get_stack_logger
    which includes simulation time in log messages. Falls back to standard
    logging when SquidASM is not available (e.g., in unit tests).

    Parameters
    ----------
    name : str
        Module name (typically __name__).

    Returns
    -------
    logging.Logger
        Configured logger instance.

    Notes
    -----
    - In simulation: logs include simulation time (ns)
    - Outside simulation: logs use standard format
    - Always use this function instead of direct logging.getLogger()

    Examples
    --------
    >>> logger = get_logger(__name__)
    >>> logger.info("Starting reconciliation")
    INFO:1234.5 ns:reconciliation:Starting reconciliation
    """
    if _SQUIDASM_AVAILABLE:
        return LogManager.get_stack_logger(name)
    else:
        return _get_fallback_logger(name)


def set_log_level(level: str) -> None:
    """Set the logging level for all hackathon loggers.

    Parameters
    ----------
    level : str
        Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).

    Notes
    -----
    Affects both SquidASM stack logger and fallback loggers.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    if _SQUIDASM_AVAILABLE:
        LogManager.get_stack_logger().setLevel(numeric_level)
    
    for logger in _FALLBACK_LOGGERS.values():
        logger.setLevel(numeric_level)


def get_protocol_logger(protocol_name: str) -> logging.Logger:
    """Get a logger specifically for protocol components.

    Parameters
    ----------
    protocol_name : str
        Name of the protocol (e.g., "alice_qkd", "bob_qkd").

    Returns
    -------
    logging.Logger
        Logger configured for protocol-level messages.

    Examples
    --------
    >>> logger = get_protocol_logger("alice_qkd")
    >>> logger.info("EPR distribution complete")
    """
    return get_logger(f"protocol.{protocol_name}")
