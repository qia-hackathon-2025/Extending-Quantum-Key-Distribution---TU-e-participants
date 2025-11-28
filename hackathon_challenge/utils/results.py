"""Result handling utilities for QKD simulations.

Provides functions for saving, loading, and analyzing simulation results
in JSON and CSV formats, with basic plotting capabilities.

Reference:
- implementation_plan.md (result handling)

Notes
-----
Results are stored with timestamps and scenario metadata for traceability.
Plotting requires matplotlib (optional dependency).
"""

import csv
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np

from hackathon_challenge.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RunResult:
    """Result from a single QKD protocol run.
    
    Attributes
    ----------
    run_id : int
        Index of this run within the scenario.
    success : bool
        Whether the protocol completed successfully.
    qber : Optional[float]
        Measured QBER (if available).
    raw_key_length : int
        Length of raw key before processing.
    final_key_length : int
        Length of final secret key (0 if failed).
    leakage_ec : float
        Bits leaked during error correction.
    leakage_ver : float
        Bits leaked during verification.
    error_message : Optional[str]
        Error message if protocol failed.
    duration_ms : float
        Execution time in milliseconds.
    keys_match : Optional[bool]
        Whether Alice and Bob keys match (if both available).
    """
    
    run_id: int
    success: bool
    qber: Optional[float] = None
    raw_key_length: int = 0
    final_key_length: int = 0
    leakage_ec: float = 0.0
    leakage_ver: float = 0.0
    error_message: Optional[str] = None
    duration_ms: float = 0.0
    keys_match: Optional[bool] = None


@dataclass
class ScenarioResult:
    """Aggregated results from a scenario execution.
    
    Attributes
    ----------
    scenario_name : str
        Name of the scenario.
    timestamp : str
        ISO timestamp when the scenario was executed.
    config : Dict[str, Any]
        Configuration used for the scenario.
    runs : List[RunResult]
        Results from individual runs.
    summary : Dict[str, Any]
        Computed summary statistics.
    """
    
    scenario_name: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    config: Dict[str, Any] = field(default_factory=dict)
    runs: List[RunResult] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    
    def compute_summary(self) -> Dict[str, Any]:
        """Compute summary statistics from runs.
        
        Returns
        -------
        Dict[str, Any]
            Summary statistics including success rate, average key length, etc.
        """
        if not self.runs:
            return {}
        
        successful_runs = [r for r in self.runs if r.success]
        failed_runs = [r for r in self.runs if not r.success]
        
        summary = {
            "total_runs": len(self.runs),
            "successful_runs": len(successful_runs),
            "failed_runs": len(failed_runs),
            "success_rate": len(successful_runs) / len(self.runs) if self.runs else 0,
        }
        
        if successful_runs:
            qbers = [r.qber for r in successful_runs if r.qber is not None]
            key_lengths = [r.final_key_length for r in successful_runs]
            
            summary.update({
                "avg_qber": np.mean(qbers) if qbers else None,
                "std_qber": np.std(qbers) if qbers else None,
                "min_qber": np.min(qbers) if qbers else None,
                "max_qber": np.max(qbers) if qbers else None,
                "avg_key_length": np.mean(key_lengths),
                "std_key_length": np.std(key_lengths),
                "min_key_length": np.min(key_lengths),
                "max_key_length": np.max(key_lengths),
                "keys_match_rate": sum(1 for r in successful_runs if r.keys_match) / len(successful_runs),
            })
        
        if failed_runs:
            error_counts: Dict[str, int] = {}
            for r in failed_runs:
                err = r.error_message or "Unknown"
                error_counts[err] = error_counts.get(err, 0) + 1
            summary["error_distribution"] = error_counts
        
        self.summary = summary
        return summary


def save_results_json(
    results: Union[ScenarioResult, List[ScenarioResult]],
    output_path: Union[str, Path],
) -> Path:
    """Save results to JSON file.
    
    Parameters
    ----------
    results : Union[ScenarioResult, List[ScenarioResult]]
        Results to save.
    output_path : Union[str, Path]
        Output file path (will add .json extension if missing).
    
    Returns
    -------
    Path
        Path to the saved file.
    """
    output_path = Path(output_path)
    if output_path.suffix != ".json":
        output_path = output_path.with_suffix(".json")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if isinstance(results, ScenarioResult):
        results = [results]
    
    # Convert to serializable format
    data = []
    for result in results:
        result_dict = {
            "scenario_name": result.scenario_name,
            "timestamp": result.timestamp,
            "config": result.config,
            "runs": [asdict(run) for run in result.runs],
            "summary": result.summary,
        }
        data.append(result_dict)
    
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    
    logger.info(f"Saved results to {output_path}")
    return output_path


def save_results_csv(
    results: Union[ScenarioResult, List[ScenarioResult]],
    output_path: Union[str, Path],
) -> Path:
    """Save results to CSV file (flattened format).
    
    Parameters
    ----------
    results : Union[ScenarioResult, List[ScenarioResult]]
        Results to save.
    output_path : Union[str, Path]
        Output file path (will add .csv extension if missing).
    
    Returns
    -------
    Path
        Path to the saved file.
    """
    output_path = Path(output_path)
    if output_path.suffix != ".csv":
        output_path = output_path.with_suffix(".csv")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if isinstance(results, ScenarioResult):
        results = [results]
    
    # Flatten results for CSV
    rows = []
    for scenario in results:
        for run in scenario.runs:
            row = {
                "scenario": scenario.scenario_name,
                "timestamp": scenario.timestamp,
                "run_id": run.run_id,
                "success": run.success,
                "qber": run.qber,
                "raw_key_length": run.raw_key_length,
                "final_key_length": run.final_key_length,
                "leakage_ec": run.leakage_ec,
                "leakage_ver": run.leakage_ver,
                "error_message": run.error_message,
                "duration_ms": run.duration_ms,
                "keys_match": run.keys_match,
            }
            # Add selected config values
            if scenario.config:
                row["config_noise"] = scenario.config.get("network", {}).get("link_noise")
                row["config_num_pairs"] = scenario.config.get("epr", {}).get("num_pairs")
            rows.append(row)
    
    if not rows:
        logger.warning("No results to save")
        return output_path
    
    fieldnames = list(rows[0].keys())
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    logger.info(f"Saved results to {output_path}")
    return output_path


def load_results_json(input_path: Union[str, Path]) -> List[ScenarioResult]:
    """Load results from JSON file.
    
    Parameters
    ----------
    input_path : Union[str, Path]
        Path to JSON file.
    
    Returns
    -------
    List[ScenarioResult]
        Loaded results.
    """
    input_path = Path(input_path)
    
    with open(input_path, "r") as f:
        data = json.load(f)
    
    results = []
    for item in data:
        runs = [RunResult(**run) for run in item.get("runs", [])]
        result = ScenarioResult(
            scenario_name=item["scenario_name"],
            timestamp=item.get("timestamp", ""),
            config=item.get("config", {}),
            runs=runs,
            summary=item.get("summary", {}),
        )
        results.append(result)
    
    return results


def load_results_csv(input_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Load results from CSV file.
    
    Parameters
    ----------
    input_path : Union[str, Path]
        Path to CSV file.
    
    Returns
    -------
    List[Dict[str, Any]]
        List of row dictionaries.
    """
    input_path = Path(input_path)
    
    with open(input_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def generate_result_filename(scenario_name: str, extension: str = "json") -> str:
    """Generate a timestamped filename for results.
    
    Parameters
    ----------
    scenario_name : str
        Name of the scenario.
    extension : str
        File extension (without dot).
    
    Returns
    -------
    str
        Generated filename.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{scenario_name}_{timestamp}.{extension}"


# =============================================================================
# Plotting Functions (require matplotlib)
# =============================================================================


def plot_qber_distribution(
    results: List[ScenarioResult],
    output_path: Optional[Union[str, Path]] = None,
    show: bool = True,
) -> None:
    """Plot QBER distribution across scenarios.
    
    Parameters
    ----------
    results : List[ScenarioResult]
        Results to plot.
    output_path : Optional[Union[str, Path]]
        If provided, save plot to this path.
    show : bool
        Whether to display the plot.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not available, skipping plot")
        return
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    for scenario in results:
        qbers = [r.qber for r in scenario.runs if r.qber is not None and r.success]
        if qbers:
            ax.hist(qbers, bins=20, alpha=0.5, label=scenario.scenario_name)
    
    ax.axvline(x=0.11, color="red", linestyle="--", label="Shor-Preskill threshold")
    ax.set_xlabel("QBER")
    ax.set_ylabel("Count")
    ax.set_title("QBER Distribution by Scenario")
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        logger.info(f"Saved plot to {output_path}")
    
    if show:
        plt.show()
    
    plt.close()


def plot_key_length_vs_qber(
    results: List[ScenarioResult],
    output_path: Optional[Union[str, Path]] = None,
    show: bool = True,
) -> None:
    """Plot final key length vs QBER.
    
    Parameters
    ----------
    results : List[ScenarioResult]
        Results to plot.
    output_path : Optional[Union[str, Path]]
        If provided, save plot to this path.
    show : bool
        Whether to display the plot.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not available, skipping plot")
        return
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    colors = plt.cm.tab10.colors
    for i, scenario in enumerate(results):
        qbers = []
        key_lengths = []
        for r in scenario.runs:
            if r.qber is not None and r.success:
                qbers.append(r.qber)
                key_lengths.append(r.final_key_length)
        
        if qbers:
            ax.scatter(
                qbers, key_lengths,
                c=[colors[i % len(colors)]],
                label=scenario.scenario_name,
                alpha=0.7,
            )
    
    ax.axvline(x=0.11, color="red", linestyle="--", label="Security threshold")
    ax.set_xlabel("QBER")
    ax.set_ylabel("Final Key Length (bits)")
    ax.set_title("Key Length vs QBER")
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        logger.info(f"Saved plot to {output_path}")
    
    if show:
        plt.show()
    
    plt.close()


def plot_success_rate_comparison(
    results: List[ScenarioResult],
    output_path: Optional[Union[str, Path]] = None,
    show: bool = True,
) -> None:
    """Plot success rate comparison across scenarios.
    
    Parameters
    ----------
    results : List[ScenarioResult]
        Results to plot.
    output_path : Optional[Union[str, Path]]
        If provided, save plot to this path.
    show : bool
        Whether to display the plot.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not available, skipping plot")
        return
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    names = []
    rates = []
    for scenario in results:
        if scenario.summary:
            names.append(scenario.scenario_name)
            rates.append(scenario.summary.get("success_rate", 0) * 100)
    
    if not names:
        logger.warning("No summary data available for plotting")
        return
    
    bars = ax.bar(names, rates, color="steelblue", alpha=0.8)
    
    # Add value labels on bars
    for bar, rate in zip(bars, rates):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 1,
            f"{rate:.1f}%",
            ha="center",
            va="bottom",
            fontsize=10,
        )
    
    ax.set_ylabel("Success Rate (%)")
    ax.set_title("Protocol Success Rate by Scenario")
    ax.set_ylim(0, 110)
    ax.grid(True, alpha=0.3, axis="y")
    
    plt.xticks(rotation=45, ha="right")
    
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        logger.info(f"Saved plot to {output_path}")
    
    if show:
        plt.show()
    
    plt.close()


def generate_summary_report(
    results: List[ScenarioResult],
    output_path: Optional[Union[str, Path]] = None,
) -> str:
    """Generate a text summary report of results.
    
    Parameters
    ----------
    results : List[ScenarioResult]
        Results to summarize.
    output_path : Optional[Union[str, Path]]
        If provided, save report to this path.
    
    Returns
    -------
    str
        The generated report text.
    """
    lines = []
    lines.append("=" * 70)
    lines.append("QKD SIMULATION RESULTS SUMMARY")
    lines.append("=" * 70)
    lines.append(f"Generated: {datetime.now().isoformat()}")
    lines.append(f"Total scenarios: {len(results)}")
    lines.append("")
    
    for scenario in results:
        lines.append("-" * 70)
        lines.append(f"Scenario: {scenario.scenario_name}")
        lines.append(f"Timestamp: {scenario.timestamp}")
        lines.append("")
        
        if scenario.summary:
            s = scenario.summary
            lines.append(f"  Total runs:      {s.get('total_runs', 0)}")
            lines.append(f"  Successful:      {s.get('successful_runs', 0)}")
            lines.append(f"  Failed:          {s.get('failed_runs', 0)}")
            lines.append(f"  Success rate:    {s.get('success_rate', 0) * 100:.1f}%")
            lines.append("")
            
            if s.get("avg_qber") is not None:
                lines.append(f"  QBER (avg±std):  {s['avg_qber']:.4f} ± {s.get('std_qber', 0):.4f}")
                lines.append(f"  QBER (range):    [{s.get('min_qber', 0):.4f}, {s.get('max_qber', 0):.4f}]")
            
            if s.get("avg_key_length") is not None:
                lines.append(f"  Key length (avg): {s['avg_key_length']:.1f}")
                lines.append(f"  Key length (range): [{s.get('min_key_length', 0)}, {s.get('max_key_length', 0)}]")
            
            if s.get("error_distribution"):
                lines.append("  Errors:")
                for err, count in s["error_distribution"].items():
                    lines.append(f"    - {err}: {count}")
        else:
            lines.append("  No summary available")
        
        lines.append("")
    
    lines.append("=" * 70)
    
    report = "\n".join(lines)
    
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(report)
        logger.info(f"Saved report to {output_path}")
    
    return report
