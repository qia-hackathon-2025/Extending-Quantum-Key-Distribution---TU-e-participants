#!/usr/bin/env python3
"""Analyze QKD simulation results.

This script provides post-simulation analysis, statistics, and visualization
for QKD protocol results.

Usage:
    python analyze_results.py results/results_*.json
    python analyze_results.py --all                    # Analyze all results in results/
    python analyze_results.py --compare low_noise medium_noise
    python analyze_results.py results.json --plot      # Generate plots

Examples:
    # Analyze specific result file
    python analyze_results.py results/results_20240101_120000.json

    # Compare scenarios
    python analyze_results.py --all --compare

    # Generate plots only
    python analyze_results.py results/*.json --plot --no-report

Reference:
- utils/results.py (plotting functions)
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from hackathon_challenge.utils.results import (
    ScenarioResult,
    load_results_json,
    load_results_csv,
    generate_summary_report,
    plot_qber_distribution,
    plot_key_length_vs_qber,
    plot_success_rate_comparison,
)
from hackathon_challenge.utils.logging import get_logger

logger = get_logger(__name__)

RESULTS_DIR = Path(__file__).parent.parent / "results"


def find_result_files(pattern: str = "*.json") -> List[Path]:
    """Find result files in the results directory.
    
    Parameters
    ----------
    pattern : str
        Glob pattern for files.
    
    Returns
    -------
    List[Path]
        List of matching file paths.
    """
    if not RESULTS_DIR.exists():
        return []
    return sorted(RESULTS_DIR.glob(pattern))


def analyze_results(results: List[ScenarioResult]) -> Dict[str, Any]:
    """Perform statistical analysis on results.
    
    Parameters
    ----------
    results : List[ScenarioResult]
        Results to analyze.
    
    Returns
    -------
    Dict[str, Any]
        Analysis results.
    """
    import numpy as np
    
    analysis = {
        "total_scenarios": len(results),
        "total_runs": sum(len(r.runs) for r in results),
        "scenarios": {},
    }
    
    all_qbers = []
    all_key_lengths = []
    
    for scenario in results:
        scenario_name = scenario.scenario_name
        
        # Collect data
        qbers = [r.qber for r in scenario.runs if r.qber is not None]
        key_lengths = [r.final_key_length for r in scenario.runs if r.success]
        successful = [r for r in scenario.runs if r.success]
        failed = [r for r in scenario.runs if not r.success]
        
        all_qbers.extend(qbers)
        all_key_lengths.extend(key_lengths)
        
        scenario_analysis = {
            "num_runs": len(scenario.runs),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": len(successful) / len(scenario.runs) if scenario.runs else 0,
        }
        
        if qbers:
            scenario_analysis["qber"] = {
                "mean": float(np.mean(qbers)),
                "std": float(np.std(qbers)),
                "min": float(np.min(qbers)),
                "max": float(np.max(qbers)),
                "median": float(np.median(qbers)),
            }
        
        if key_lengths:
            scenario_analysis["key_length"] = {
                "mean": float(np.mean(key_lengths)),
                "std": float(np.std(key_lengths)),
                "min": int(np.min(key_lengths)),
                "max": int(np.max(key_lengths)),
                "median": float(np.median(key_lengths)),
            }
        
        # Categorize errors
        if failed:
            error_types: Dict[str, int] = {}
            for r in failed:
                err = r.error_message or "Unknown"
                error_types[err] = error_types.get(err, 0) + 1
            scenario_analysis["errors"] = error_types
        
        analysis["scenarios"][scenario_name] = scenario_analysis
    
    # Global statistics
    if all_qbers:
        analysis["global_qber"] = {
            "mean": float(np.mean(all_qbers)),
            "std": float(np.std(all_qbers)),
            "min": float(np.min(all_qbers)),
            "max": float(np.max(all_qbers)),
        }
    
    if all_key_lengths:
        analysis["global_key_length"] = {
            "mean": float(np.mean(all_key_lengths)),
            "std": float(np.std(all_key_lengths)),
            "min": int(np.min(all_key_lengths)),
            "max": int(np.max(all_key_lengths)),
        }
    
    return analysis


def compare_scenarios(
    results: List[ScenarioResult],
    metric: str = "success_rate",
) -> Dict[str, Any]:
    """Compare scenarios by a specific metric.
    
    Parameters
    ----------
    results : List[ScenarioResult]
        Results to compare.
    metric : str
        Metric to compare ("success_rate", "qber", "key_length").
    
    Returns
    -------
    Dict[str, Any]
        Comparison results.
    """
    import numpy as np
    
    comparison = {
        "metric": metric,
        "scenarios": {},
        "ranking": [],
    }
    
    values = []
    for scenario in results:
        name = scenario.scenario_name
        
        if metric == "success_rate":
            successful = sum(1 for r in scenario.runs if r.success)
            value = successful / len(scenario.runs) if scenario.runs else 0
        elif metric == "qber":
            qbers = [r.qber for r in scenario.runs if r.qber is not None and r.success]
            value = np.mean(qbers) if qbers else None
        elif metric == "key_length":
            lengths = [r.final_key_length for r in scenario.runs if r.success]
            value = np.mean(lengths) if lengths else 0
        else:
            value = None
        
        comparison["scenarios"][name] = value
        if value is not None:
            values.append((name, value))
    
    # Rank scenarios
    if metric == "qber":
        # Lower QBER is better
        values.sort(key=lambda x: x[1] if x[1] is not None else float("inf"))
    else:
        # Higher is better for success_rate and key_length
        values.sort(key=lambda x: x[1] if x[1] is not None else 0, reverse=True)
    
    comparison["ranking"] = [name for name, _ in values]
    
    return comparison


def print_analysis(analysis: Dict[str, Any]) -> None:
    """Print analysis results in a readable format.
    
    Parameters
    ----------
    analysis : Dict[str, Any]
        Analysis to print.
    """
    print("=" * 70)
    print("QKD SIMULATION ANALYSIS")
    print("=" * 70)
    print(f"Total scenarios: {analysis['total_scenarios']}")
    print(f"Total runs: {analysis['total_runs']}")
    print()
    
    for scenario_name, data in analysis.get("scenarios", {}).items():
        print("-" * 70)
        print(f"Scenario: {scenario_name}")
        print(f"  Runs: {data['num_runs']} (success: {data['successful']}, failed: {data['failed']})")
        print(f"  Success rate: {data['success_rate'] * 100:.1f}%")
        
        if "qber" in data:
            q = data["qber"]
            print(f"  QBER: {q['mean']:.4f} ± {q['std']:.4f} [{q['min']:.4f}, {q['max']:.4f}]")
        
        if "key_length" in data:
            k = data["key_length"]
            print(f"  Key length: {k['mean']:.1f} ± {k['std']:.1f} [{k['min']}, {k['max']}]")
        
        if "errors" in data:
            print("  Errors:")
            for err, count in data["errors"].items():
                print(f"    - {err}: {count}")
        print()
    
    if "global_qber" in analysis:
        q = analysis["global_qber"]
        print("-" * 70)
        print("Global Statistics:")
        print(f"  QBER: {q['mean']:.4f} ± {q['std']:.4f}")
    
    if "global_key_length" in analysis:
        k = analysis["global_key_length"]
        print(f"  Key length: {k['mean']:.1f} ± {k['std']:.1f}")
    
    print("=" * 70)


def print_comparison(comparison: Dict[str, Any]) -> None:
    """Print comparison results.
    
    Parameters
    ----------
    comparison : Dict[str, Any]
        Comparison to print.
    """
    print("=" * 70)
    print(f"SCENARIO COMPARISON: {comparison['metric']}")
    print("=" * 70)
    
    print("\nRanking:")
    for i, name in enumerate(comparison["ranking"], 1):
        value = comparison["scenarios"][name]
        if comparison["metric"] == "success_rate":
            value_str = f"{value * 100:.1f}%" if value is not None else "N/A"
        elif comparison["metric"] == "qber":
            value_str = f"{value:.4f}" if value is not None else "N/A"
        else:
            value_str = f"{value:.1f}" if value is not None else "N/A"
        print(f"  {i}. {name}: {value_str}")
    
    print("=" * 70)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.
    
    Returns
    -------
    argparse.Namespace
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Analyze QKD simulation results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    parser.add_argument(
        "files",
        nargs="*",
        help="Result files to analyze (JSON format)",
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Analyze all results in results directory",
    )
    parser.add_argument(
        "--compare", "-c",
        action="store_true",
        help="Compare scenarios",
    )
    parser.add_argument(
        "--metric",
        type=str,
        choices=["success_rate", "qber", "key_length"],
        default="success_rate",
        help="Metric for comparison (default: success_rate)",
    )
    parser.add_argument(
        "--plot", "-p",
        action="store_true",
        help="Generate plots",
    )
    parser.add_argument(
        "--plot-dir",
        type=str,
        default=None,
        help="Directory for plot output (default: results/plots/)",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Skip text report generation",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output file for analysis results (JSON)",
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
    
    # Find files to analyze
    if args.all:
        files = find_result_files("*.json")
    elif args.files:
        files = [Path(f) for f in args.files]
    else:
        # Show help if no files specified
        print("No result files specified. Use --all or provide file paths.")
        print("Use --help for usage information.")
        return 1
    
    if not files:
        print("No result files found!")
        return 1
    
    # Load results
    all_results: List[ScenarioResult] = []
    for file_path in files:
        try:
            results = load_results_json(file_path)
            all_results.extend(results)
            logger.info(f"Loaded {len(results)} scenario(s) from {file_path}")
        except Exception as e:
            logger.error(f"Failed to load {file_path}: {e}")
    
    if not all_results:
        print("No valid results loaded!")
        return 1
    
    # Perform analysis
    analysis = analyze_results(all_results)
    
    # Print report
    if not args.no_report:
        print_analysis(analysis)
    
    # Compare scenarios
    if args.compare:
        comparison = compare_scenarios(all_results, args.metric)
        print_comparison(comparison)
    
    # Generate plots
    if args.plot:
        plot_dir = Path(args.plot_dir) if args.plot_dir else RESULTS_DIR / "plots"
        plot_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            print("\nGenerating plots...")
            
            plot_qber_distribution(
                all_results,
                output_path=plot_dir / "qber_distribution.png",
                show=False,
            )
            print(f"  - Saved: {plot_dir / 'qber_distribution.png'}")
            
            plot_key_length_vs_qber(
                all_results,
                output_path=plot_dir / "key_length_vs_qber.png",
                show=False,
            )
            print(f"  - Saved: {plot_dir / 'key_length_vs_qber.png'}")
            
            plot_success_rate_comparison(
                all_results,
                output_path=plot_dir / "success_rate_comparison.png",
                show=False,
            )
            print(f"  - Saved: {plot_dir / 'success_rate_comparison.png'}")
            
        except ImportError:
            print("matplotlib not available, skipping plots")
        except Exception as e:
            logger.error(f"Failed to generate plots: {e}")
    
    # Save analysis results
    if args.output:
        import json
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(analysis, f, indent=2)
        print(f"\nSaved analysis to {output_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
