#!/usr/bin/env python3
"""Run QKD protocol scenarios from configuration files.

This script provides batch execution of QKD simulations with different
configurations, collecting and saving results for analysis.

Usage:
    python run_scenarios.py                        # Run all scenarios
    python run_scenarios.py --scenario low_noise   # Run specific scenario
    python run_scenarios.py --list                 # List available scenarios
    python run_scenarios.py --mock                 # Run in mock mode (no SquidASM)

Examples:
    # Run all scenarios with default settings
    python run_scenarios.py

    # Run specific scenario with verbose output
    python run_scenarios.py --scenario quick_test --log-level DEBUG

    # Run with custom output directory
    python run_scenarios.py --output-dir ./my_results

Reference:
- implementation_plan.md §3.3
- configs/scenarios/*.yaml
"""

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Check SquidASM availability
try:
    from squidasm.run.stack.run import run
    from squidasm.util import create_two_node_network
    from squidasm.sim.stack.common import LogManager
    SQUIDASM_AVAILABLE = True
except ImportError:
    SQUIDASM_AVAILABLE = False

from hackathon_challenge.core.protocol import create_qkd_programs
from hackathon_challenge.core.constants import (
    RESULT_ERROR,
    RESULT_KEY_LENGTH,
    RESULT_LEAKAGE,
    RESULT_QBER,
    RESULT_SECRET_KEY,
    RESULT_SUCCESS,
)
from hackathon_challenge.utils.results import (
    RunResult,
    ScenarioResult,
    save_results_csv,
    save_results_json,
    generate_result_filename,
    generate_summary_report,
)
from hackathon_challenge.utils.logging import get_logger

logger = get_logger(__name__)

# Default paths
CONFIGS_DIR = Path(__file__).parent.parent / "configs"
SCENARIOS_DIR = CONFIGS_DIR / "scenarios"
RESULTS_DIR = Path(__file__).parent.parent / "results"


def load_base_config() -> Dict[str, Any]:
    """Load base configuration.
    
    Returns
    -------
    Dict[str, Any]
        Base configuration dictionary.
    """
    base_path = CONFIGS_DIR / "base.yaml"
    if base_path.exists():
        with open(base_path, "r") as f:
            return yaml.safe_load(f)
    return {}


def load_scenario_config(scenario_name: str) -> Dict[str, Any]:
    """Load scenario configuration with base inheritance.
    
    Parameters
    ----------
    scenario_name : str
        Name of the scenario (without .yaml extension).
    
    Returns
    -------
    Dict[str, Any]
        Merged configuration dictionary.
    """
    scenario_path = SCENARIOS_DIR / f"{scenario_name}.yaml"
    if not scenario_path.exists():
        raise FileNotFoundError(f"Scenario not found: {scenario_path}")
    
    # Load base config
    config = load_base_config()
    
    # Load scenario config and merge
    with open(scenario_path, "r") as f:
        scenario_config = yaml.safe_load(f)
    
    # Deep merge scenario into base
    config = deep_merge(config, scenario_config)
    
    return config


def deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge two dictionaries.
    
    Parameters
    ----------
    base : Dict
        Base dictionary.
    override : Dict
        Override dictionary (takes precedence).
    
    Returns
    -------
    Dict
        Merged dictionary.
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def list_available_scenarios() -> List[str]:
    """List available scenario configurations.
    
    Returns
    -------
    List[str]
        List of scenario names.
    """
    scenarios = []
    if SCENARIOS_DIR.exists():
        for f in SCENARIOS_DIR.glob("*.yaml"):
            scenarios.append(f.stem)
    return sorted(scenarios)


def run_scenario_squidasm(config: Dict[str, Any]) -> ScenarioResult:
    """Run a scenario using SquidASM simulation.
    
    Parameters
    ----------
    config : Dict[str, Any]
        Scenario configuration.
    
    Returns
    -------
    ScenarioResult
        Results from the scenario.
    """
    scenario_name = config.get("scenario", {}).get("name", "unknown")
    logger.info(f"Running scenario: {scenario_name}")
    
    # Extract configuration
    epr_config = config.get("epr", {})
    network_config = config.get("network", {})
    cascade_config = config.get("cascade", {})
    verification_config = config.get("verification", {})
    privacy_config = config.get("privacy", {})
    simulation_config = config.get("simulation", {})
    auth_config = config.get("auth", {})
    
    # Create network
    network = create_two_node_network(
        node_names=["Alice", "Bob"],
        link_noise=network_config.get("link_noise", 0.05),
        qdevice_noise=network_config.get("qdevice_noise", 0.0),
        clink_delay=network_config.get("clink_delay", 0.0),
        link_delay=network_config.get("link_delay", 0.0),
    )
    
    # Create programs
    num_pairs = epr_config.get("num_pairs", 500)
    num_test_bits = epr_config.get("num_test_bits")
    
    alice, bob = create_qkd_programs(
        num_epr_pairs=num_pairs,
        num_test_bits=num_test_bits,
        cascade_seed=cascade_config.get("seed", 42),
        auth_key=auth_config.get("key", "shared_key").encode(),
        verification_tag_bits=verification_config.get("tag_bits", 64),
        security_parameter=privacy_config.get("security_parameter", 1e-12),
    )
    
    # Set logging
    log_level = getattr(logging, simulation_config.get("log_level", "WARNING"))
    alice._logger.setLevel(log_level)
    bob._logger.setLevel(log_level)
    
    # Run simulation
    num_runs = simulation_config.get("num_runs", 5)
    logger.info(f"Running {num_runs} simulation(s)...")
    
    start_time = time.time()
    results = run(
        config=network,
        programs={"Alice": alice, "Bob": bob},
        num_times=num_runs,
    )
    total_time = time.time() - start_time
    
    # Process results
    alice_results = results[0]
    bob_results = results[1]
    
    run_results = []
    for i, (alice_result, bob_result) in enumerate(zip(alice_results, bob_results)):
        alice_success = alice_result.get(RESULT_SUCCESS, False)
        bob_success = bob_result.get(RESULT_SUCCESS, False)
        
        # RESULT_LEAKAGE is total leakage (int), not a dict
        total_leakage = alice_result.get(RESULT_LEAKAGE, 0)
        if isinstance(total_leakage, dict):
            # Handle case where it's a dict (backward compat)
            leakage_ec = total_leakage.get("ec", 0)
            leakage_ver = total_leakage.get("ver", 0)
        else:
            # It's the total leakage as an int
            leakage_ec = total_leakage  # Approximation
            leakage_ver = 64 if alice_success else 0  # Default verification hash size
        
        run_result = RunResult(
            run_id=i,
            success=alice_success and bob_success,
            qber=alice_result.get(RESULT_QBER),
            raw_key_length=epr_config.get("num_pairs", 0) // 2,  # Approximate
            final_key_length=len(alice_result.get(RESULT_SECRET_KEY, [])),
            leakage_ec=leakage_ec,
            leakage_ver=leakage_ver,
            error_message=alice_result.get(RESULT_ERROR) if not alice_success else None,
            duration_ms=total_time * 1000 / num_runs,
            keys_match=None,
        )
        
        # Check if keys match (for successful runs)
        if alice_success and bob_success:
            alice_key = alice_result.get(RESULT_SECRET_KEY, [])
            bob_key = bob_result.get(RESULT_SECRET_KEY, [])
            run_result.keys_match = alice_key == bob_key
        
        run_results.append(run_result)
    
    scenario_result = ScenarioResult(
        scenario_name=scenario_name,
        config=config,
        runs=run_results,
    )
    scenario_result.compute_summary()
    
    return scenario_result


def run_scenario_mock(config: Dict[str, Any]) -> ScenarioResult:
    """Run a scenario in mock mode (no SquidASM).
    
    This simulates the protocol flow using mock components
    for testing when SquidASM is not available.
    
    Parameters
    ----------
    config : Dict[str, Any]
        Scenario configuration.
    
    Returns
    -------
    ScenarioResult
        Simulated results from the scenario.
    """
    import random
    import numpy as np
    
    scenario_name = config.get("scenario", {}).get("name", "unknown")
    logger.info(f"Running scenario in MOCK mode: {scenario_name}")
    
    # Extract configuration
    epr_config = config.get("epr", {})
    network_config = config.get("network", {})
    simulation_config = config.get("simulation", {})
    
    num_runs = simulation_config.get("num_runs", 5)
    num_pairs = epr_config.get("num_pairs", 500)
    link_noise = network_config.get("link_noise", 0.05)
    
    run_results = []
    for i in range(num_runs):
        # Simulate QBER based on link noise
        qber = np.random.normal(link_noise, link_noise * 0.2)
        qber = max(0, min(qber, 0.5))  # Clamp to [0, 0.5]
        
        # Determine success based on QBER threshold
        success = qber < 0.11
        
        if success:
            # Estimate key length based on formulas
            sifted_length = num_pairs // 2  # ~50% same basis
            test_bits = epr_config.get("num_test_bits") or num_pairs // 4
            raw_key_length = sifted_length - test_bits
            
            # Approximate final key length after PA
            # L_sec ≈ n * [1 - h(QBER) - leakage]
            h_qber = -qber * np.log2(qber + 1e-10) - (1 - qber) * np.log2(1 - qber + 1e-10)
            efficiency = max(0.1, 1 - 2 * h_qber)
            final_key_length = int(raw_key_length * efficiency)
            final_key_length = max(0, final_key_length)
        else:
            raw_key_length = 0
            final_key_length = 0
        
        run_result = RunResult(
            run_id=i,
            success=success,
            qber=qber,
            raw_key_length=raw_key_length,
            final_key_length=final_key_length,
            leakage_ec=raw_key_length * qber * 1.2 if success else 0,
            leakage_ver=64 if success else 0,
            error_message="QBER above threshold" if not success else None,
            duration_ms=100 * random.random(),  # Simulated time
            keys_match=True if success else None,
        )
        run_results.append(run_result)
    
    scenario_result = ScenarioResult(
        scenario_name=f"{scenario_name}_mock",
        config=config,
        runs=run_results,
    )
    scenario_result.compute_summary()
    
    return scenario_result


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.
    
    Returns
    -------
    argparse.Namespace
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Run QKD protocol scenarios",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    parser.add_argument(
        "--scenario", "-s",
        type=str,
        default=None,
        help="Run specific scenario (name without .yaml)",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available scenarios",
    )
    parser.add_argument(
        "--mock", "-m",
        action="store_true",
        help="Run in mock mode (no SquidASM required)",
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default=str(RESULTS_DIR),
        help=f"Output directory for results (default: {RESULTS_DIR})",
    )
    parser.add_argument(
        "--output-format",
        type=str,
        choices=["json", "csv", "both"],
        default="both",
        help="Output format (default: both)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save results to files",
    )
    
    return parser.parse_args()


def main() -> int:
    """Main entry point.
    
    Returns
    -------
    int
        Exit code (0 for success).
    """
    args = parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # List scenarios if requested
    if args.list:
        scenarios = list_available_scenarios()
        print("Available scenarios:")
        for s in scenarios:
            print(f"  - {s}")
        return 0
    
    # Determine which scenarios to run
    if args.scenario:
        scenarios = [args.scenario]
    else:
        scenarios = list_available_scenarios()
        # Filter out special configs
        scenarios = [s for s in scenarios if not s.startswith("_")]
    
    if not scenarios:
        print("No scenarios found!")
        return 1
    
    # Check SquidASM availability
    use_mock = args.mock or not SQUIDASM_AVAILABLE
    if use_mock and not args.mock:
        logger.warning("SquidASM not available, using mock mode")
    
    # Run scenarios
    all_results: List[ScenarioResult] = []
    
    for scenario_name in scenarios:
        try:
            config = load_scenario_config(scenario_name)
            
            if use_mock:
                result = run_scenario_mock(config)
            else:
                result = run_scenario_squidasm(config)
            
            all_results.append(result)
            
            # Print summary
            print(f"\n{scenario_name}:")
            print(f"  Success rate: {result.summary.get('success_rate', 0) * 100:.1f}%")
            if result.summary.get('avg_qber') is not None:
                print(f"  Avg QBER: {result.summary['avg_qber']:.4f}")
            if result.summary.get('avg_key_length') is not None:
                print(f"  Avg key length: {result.summary['avg_key_length']:.1f}")
            
        except Exception as e:
            logger.error(f"Failed to run scenario {scenario_name}: {e}")
            if args.log_level == "DEBUG":
                import traceback
                traceback.print_exc()
    
    # Save results
    if not args.no_save and all_results:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = all_results[0].timestamp.replace(":", "-").replace(".", "-")
        base_filename = f"results_{timestamp}"
        
        if args.output_format in ("json", "both"):
            save_results_json(all_results, output_dir / f"{base_filename}.json")
        
        if args.output_format in ("csv", "both"):
            save_results_csv(all_results, output_dir / f"{base_filename}.csv")
        
        # Generate summary report
        report_path = output_dir / f"{base_filename}_report.txt"
        report = generate_summary_report(all_results, report_path)
        print("\n" + report)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
