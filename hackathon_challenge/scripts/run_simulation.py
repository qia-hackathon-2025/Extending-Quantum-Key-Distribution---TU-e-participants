#!/usr/bin/env python3
"""Run QKD protocol simulation.

This script provides a command-line interface for executing the full
QKD protocol with configurable parameters.

Reference:
- implementation_plan.md §3.3
- squidasm/examples/applications/qkd/example_qkd.py

Usage:
    python run_simulation.py                    # Default parameters
    python run_simulation.py --num-pairs 500   # Custom EPR pairs
    python run_simulation.py --noise 0.05      # Set channel noise

Examples:
    # Low noise simulation
    python run_simulation.py --noise 0.02 --num-runs 5

    # High noise (should abort)
    python run_simulation.py --noise 0.15

    # Debug mode
    python run_simulation.py --log-level DEBUG --num-pairs 100
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List, Any

import yaml

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from squidasm.run.stack.run import run
    from squidasm.util import create_two_node_network
    from squidasm.sim.stack.common import LogManager
    SQUIDASM_AVAILABLE = True
except ImportError:
    SQUIDASM_AVAILABLE = False
    print("Warning: SquidASM not available. Running in mock mode.")

from hackathon_challenge.core.protocol import (
    AliceProgram,
    BobProgram,
    create_qkd_programs,
)
from hackathon_challenge.core.constants import (
    DEFAULT_CASCADE_SEED,
    DEFAULT_NUM_EPR_PAIRS,
    DEFAULT_NUM_TEST_BITS,
    RESULT_SECRET_KEY,
    RESULT_QBER,
    RESULT_KEY_LENGTH,
    RESULT_SUCCESS,
    RESULT_ERROR,
)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns
    -------
    argparse.Namespace
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Run QKD protocol simulation with SquidASM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Simulation parameters
    parser.add_argument(
        "--num-runs",
        type=int,
        default=1,
        help="Number of independent QKD sessions (default: 1)",
    )
    parser.add_argument(
        "--num-pairs",
        type=int,
        default=DEFAULT_NUM_EPR_PAIRS,
        help=f"Number of EPR pairs to generate (default: {DEFAULT_NUM_EPR_PAIRS})",
    )
    parser.add_argument(
        "--num-test-bits",
        type=int,
        default=None,
        help="Bits for QBER estimation (default: num_pairs // 4)",
    )

    # Noise parameters
    parser.add_argument(
        "--noise",
        type=float,
        default=0.05,
        help="Link noise level (0-1, controls QBER) (default: 0.05)",
    )
    parser.add_argument(
        "--qdevice-noise",
        type=float,
        default=0.0,
        help="Quantum device noise level (default: 0.0)",
    )

    # Protocol parameters
    parser.add_argument(
        "--cascade-seed",
        type=int,
        default=DEFAULT_CASCADE_SEED,
        help=f"Shared RNG seed for Cascade (default: {DEFAULT_CASCADE_SEED})",
    )
    parser.add_argument(
        "--auth-key",
        type=str,
        default="shared_secret_key",
        help="Pre-shared authentication key (default: shared_secret_key)",
    )
    parser.add_argument(
        "--tag-bits",
        type=int,
        choices=[64, 128],
        default=64,
        help="Verification hash tag bits (default: 64)",
    )

    # Configuration file
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to YAML config file (overrides other arguments)",
    )

    # Logging
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    # Output
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress detailed output",
    )

    return parser.parse_args()


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML file.

    Parameters
    ----------
    config_path : str
        Path to YAML config file.

    Returns
    -------
    Dict[str, Any]
        Configuration dictionary.
    """
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def print_results(
    results: List[List[Dict[str, Any]]],
    args: argparse.Namespace,
) -> None:
    """Print simulation results in a readable format.

    Parameters
    ----------
    results : List[List[Dict[str, Any]]]
        Results from squidasm run() function.
    args : argparse.Namespace
        Command line arguments.
    """
    alice_results = results[0]  # First stack is Alice
    bob_results = results[1]    # Second stack is Bob

    print("\n" + "=" * 60)
    print("QKD SIMULATION RESULTS")
    print("=" * 60)

    success_count = 0
    total_key_length = 0

    for i, (alice_result, bob_result) in enumerate(zip(alice_results, bob_results)):
        print(f"\n--- Run {i + 1} ---")

        # Check success
        alice_success = alice_result.get(RESULT_SUCCESS, False)
        bob_success = bob_result.get(RESULT_SUCCESS, False)

        if alice_success and bob_success:
            success_count += 1
            alice_key = alice_result.get(RESULT_SECRET_KEY, [])
            bob_key = bob_result.get(RESULT_SECRET_KEY, [])

            # Verify keys match
            keys_match = alice_key == bob_key

            print(f"  Status: SUCCESS {'✓' if keys_match else '✗ (KEYS MISMATCH!)'}")
            print(f"  QBER: {alice_result.get(RESULT_QBER, 0):.4f}")
            print(f"  Key Length: {len(alice_key)} bits")
            total_key_length += len(alice_key)

            if not args.quiet:
                key_preview = "".join(str(b) for b in alice_key[:32])
                if len(alice_key) > 32:
                    key_preview += "..."
                print(f"  Key Preview: {key_preview}")

            if not keys_match:
                print("  ERROR: Alice and Bob keys do not match!")
                # Find first difference
                for j, (a, b) in enumerate(zip(alice_key, bob_key)):
                    if a != b:
                        print(f"    First difference at bit {j}: Alice={a}, Bob={b}")
                        break
        else:
            alice_error = alice_result.get(RESULT_ERROR, "unknown")
            bob_error = bob_result.get(RESULT_ERROR, "unknown")
            print(f"  Status: FAILED")
            print(f"  Alice Error: {alice_error}")
            print(f"  Bob Error: {bob_error}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Total Runs: {len(alice_results)}")
    print(f"  Successful: {success_count}")
    print(f"  Failed: {len(alice_results) - success_count}")
    if success_count > 0:
        avg_key_length = total_key_length / success_count
        print(f"  Average Key Length: {avg_key_length:.1f} bits")
    print(f"  Link Noise: {args.noise}")
    print("=" * 60)


def run_mock_simulation(args: argparse.Namespace) -> None:
    """Run a mock simulation when SquidASM is not available.

    Parameters
    ----------
    args : argparse.Namespace
        Command line arguments.
    """
    print("\n[MOCK MODE] Running without SquidASM simulation")
    print("=" * 60)

    # Create programs to verify they can be instantiated
    alice, bob = create_qkd_programs(
        num_epr_pairs=args.num_pairs,
        num_test_bits=args.num_test_bits,
        cascade_seed=args.cascade_seed,
        auth_key=args.auth_key.encode(),
        verification_tag_bits=args.tag_bits,
    )

    print(f"Created AliceProgram: {alice.meta.name}")
    print(f"  - CSockets: {alice.meta.csockets}")
    print(f"  - EPR Sockets: {alice.meta.epr_sockets}")
    print(f"  - Max Qubits: {alice.meta.max_qubits}")

    print(f"\nCreated BobProgram: {bob.meta.name}")
    print(f"  - CSockets: {bob.meta.csockets}")
    print(f"  - EPR Sockets: {bob.meta.epr_sockets}")
    print(f"  - Max Qubits: {bob.meta.max_qubits}")

    print("\n[MOCK MODE] To run full simulation, install SquidASM:")
    print("  pip install squidasm")


def main() -> int:
    """Main entry point.

    Returns
    -------
    int
        Exit code (0 for success, 1 for failure).
    """
    args = parse_args()

    # Load config file if specified
    if args.config:
        config = load_config(args.config)
        # Override args with config values
        if "simulation" in config:
            args.num_runs = config["simulation"].get("num_times", args.num_runs)
            args.log_level = config["simulation"].get("log_level", args.log_level)
        if "programs" in config:
            alice_cfg = config["programs"].get("alice", {})
            args.num_pairs = alice_cfg.get("num_epr_pairs", args.num_pairs)
            args.num_test_bits = alice_cfg.get("num_test_bits", args.num_test_bits)
            args.cascade_seed = alice_cfg.get("cascade_seed", args.cascade_seed)
            args.auth_key = alice_cfg.get("auth_key", args.auth_key)
        if "network_params" in config:
            args.noise = config["network_params"].get("noise_level", args.noise)

    if not SQUIDASM_AVAILABLE:
        run_mock_simulation(args)
        return 0

    # Setup logging
    LogManager.get_stack_logger().setLevel(getattr(logging, args.log_level))

    logger = LogManager.get_stack_logger(__name__)
    logger.info(f"Starting QKD simulation with {args.num_pairs} EPR pairs")

    # Create network configuration
    # Reference: squidasm/squidasm/util/util.py create_two_node_network
    network_config = create_two_node_network(
        node_names=["Alice", "Bob"],
        link_noise=args.noise,
        qdevice_noise=args.qdevice_noise,
    )

    # Create program instances
    alice, bob = create_qkd_programs(
        num_epr_pairs=args.num_pairs,
        num_test_bits=args.num_test_bits,
        cascade_seed=args.cascade_seed,
        auth_key=args.auth_key.encode(),
        verification_tag_bits=args.tag_bits,
    )

    # Set logging level on programs
    alice._logger.setLevel(getattr(logging, args.log_level))
    bob._logger.setLevel(getattr(logging, args.log_level))

    logger.info(f"Running {args.num_runs} simulation(s)...")

    try:
        # Run simulation
        # Reference: squidasm/squidasm/run/stack/run.py
        results = run(
            config=network_config,
            programs={"Alice": alice, "Bob": bob},
            num_times=args.num_runs,
        )

        # Print results
        print_results(results, args)

        # Return success if all runs succeeded
        alice_results = results[0]
        bob_results = results[1]
        all_success = all(
            a.get(RESULT_SUCCESS, False) and b.get(RESULT_SUCCESS, False)
            for a, b in zip(alice_results, bob_results)
        )
        return 0 if all_success else 1

    except Exception as e:
        logger.error(f"Simulation failed: {e}")
        if args.log_level == "DEBUG":
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
