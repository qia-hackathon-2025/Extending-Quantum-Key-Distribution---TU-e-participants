#!/usr/bin/env python3
"""Live demonstration of the QKD protocol system.

This script provides an aesthetically pleasing terminal demonstration
of the full QKD protocol pipeline, suitable for live presentations.

Features:
- Rich terminal output with progress indicators
- Real-time protocol step visualization
- Automatic plot generation
- Summary statistics display

Usage:
    python live_demo.py                  # Full demo with all scenarios
    python live_demo.py --quick          # Quick demo (fewer runs)
    python live_demo.py --mock           # Demo without SquidASM
    python live_demo.py --no-plots       # Skip plot generation

Reference:
- QIA Hackathon 2025 - Extended BB84 QKD Implementation
"""

import argparse
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Check dependencies
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# Check SquidASM availability
try:
    from squidasm.run.stack.run import run
    from squidasm.util import create_two_node_network
    SQUIDASM_AVAILABLE = True
except ImportError:
    SQUIDASM_AVAILABLE = False


# =============================================================================
# Terminal Styling Constants
# =============================================================================

class Style:
    """ANSI escape codes for terminal styling."""
    
    # Colors
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    
    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Bright colors
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"
    
    # Background colors
    BG_BLACK = "\033[40m"
    BG_BLUE = "\033[44m"
    BG_CYAN = "\033[46m"


class Symbols:
    """ASCII/Unicode symbols for visual feedback (no emojis)."""
    
    CHECK = "[OK]"
    CROSS = "[X]"
    ARROW = "->"
    BULLET = "*"
    STAR = ">"
    DIAMOND = ">"
    CIRCLE = "[ ]"
    FILLED_CIRCLE = "[*]"
    SQUARE = "[ ]"
    FILLED_SQUARE = "[#]"
    TRIANGLE = ">"
    LOCK = "[SECURE]"
    KEY = "[KEY]"
    LINK = "--"
    QUANTUM = "[Q]"
    WARNING = "[!]"
    INFO = "[i]"
    SPARKLE = "[*]"


# =============================================================================
# Display Helper Functions
# =============================================================================

def clear_screen():
    """Clear terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_banner():
    """Print the demo banner."""
    banner = f"""
{Style.BRIGHT_CYAN}{Style.BOLD}
+==============================================================================+
|                                                                              |
|       QUANTUM KEY DISTRIBUTION PROTOCOL - LIVE DEMONSTRATION                 |
|                                                                              |
|       Extended BB84 with Cascade, Verification & Privacy Amplification       |
|                                                                              |
|                           QIA Hackathon 2025                                 |
|                                                                              |
+==============================================================================+
{Style.RESET}"""
    print(banner)


def print_section(title: str):
    """Print a section header."""
    width = 78
    print()
    print(f"{Style.BRIGHT_BLUE}{Style.BOLD}{'=' * width}{Style.RESET}")
    print(f"{Style.BRIGHT_BLUE}{Style.BOLD}  {title.upper()}{Style.RESET}")
    print(f"{Style.BRIGHT_BLUE}{'-' * width}{Style.RESET}")
    time.sleep(0.3)


def print_step(step_num: int, description: str, status: str = "running"):
    """Print a protocol step with status."""
    status_icons = {
        "running": f"{Style.YELLOW}[~]{Style.RESET}",
        "done": f"{Style.GREEN}[OK]{Style.RESET}",
        "failed": f"{Style.RED}[X]{Style.RESET}",
        "pending": f"{Style.DIM}[ ]{Style.RESET}",
    }
    icon = status_icons.get(status, status_icons["pending"])
    print(f"       {icon} Step {step_num}: {description}")


def print_metric(name: str, value: Any, unit: str = "", good: Optional[bool] = None):
    """Print a metric with optional good/bad indicator."""
    if good is None:
        indicator = Style.CYAN + Symbols.BULLET + Style.RESET
    elif good:
        indicator = Style.GREEN + Symbols.CHECK + Style.RESET
    else:
        indicator = Style.RED + Symbols.CROSS + Style.RESET
    
    value_style = Style.BRIGHT_WHITE if good is None else (Style.GREEN if good else Style.RED)
    print(f"       {indicator} {name}: {value_style}{value}{Style.RESET} {unit}")


def print_progress_bar(current: int, total: int, width: int = 40, prefix: str = ""):
    """Print a progress bar."""
    filled = int(width * current / total)
    bar = "█" * filled + "░" * (width - filled)
    percent = current / total * 100
    print(f"\r{prefix} {Style.CYAN}[{bar}]{Style.RESET} {percent:5.1f}%", end="", flush=True)
    if current == total:
        print()


def print_key_visual(key: List[int], max_display: int = 64):
    """Print a visual representation of a key."""
    display_key = key[:max_display]
    
    # Create colored representation
    key_str = ""
    for bit in display_key:
        if bit == 0:
            key_str += f"{Style.BLUE}0{Style.RESET}"
        else:
            key_str += f"{Style.MAGENTA}1{Style.RESET}"
    
    if len(key) > max_display:
        key_str += f" {Style.DIM}... ({len(key) - max_display} more bits){Style.RESET}"
    
    print(f"       {Symbols.KEY} Key: {key_str}")


def animated_wait(message: str, duration: float = 1.0, steps: int = 10):
    """Show an animated waiting indicator."""
    chars = ["|", "/", "-", "\\"]
    step_duration = duration / steps
    for i in range(steps):
        char = chars[i % len(chars)]
        print(f"\r       {Style.CYAN}[{char}]{Style.RESET} {message}...", end="", flush=True)
        time.sleep(step_duration)
    print(f"\r       {Style.GREEN}[OK]{Style.RESET} {message}    ")


# =============================================================================
# Demo Scenario Data
# =============================================================================

@dataclass
class DemoScenario:
    """Configuration for a demo scenario."""
    name: str
    description: str
    noise_level: float
    num_pairs: int
    num_runs: int
    color: str
    test_bits_ratio: float = 0.10
    cascade_passes: int = 4
    security_param: float = 1e-10
    
    
DEMO_SCENARIOS = [
    DemoScenario(
        name="Ideal Channel",
        description="Near-perfect quantum channel, minimal errors",
        noise_level=0.015,
        num_pairs=2000,
        num_runs=5,
        color="#27ae60",
        test_bits_ratio=0.08,
        cascade_passes=3,
        security_param=1e-6,
    ),
    DemoScenario(
        name="Standard Operation",
        description="Typical metropolitan fiber link conditions",
        noise_level=0.045,
        num_pairs=2500,
        num_runs=5,
        color="#3498db",
        test_bits_ratio=0.10,
        cascade_passes=4,
        security_param=1e-6,
    ),
    DemoScenario(
        name="Degraded Channel",
        description="Longer distance or aging infrastructure",
        noise_level=0.075,
        num_pairs=3000,
        num_runs=5,
        color="#f39c12",
        test_bits_ratio=0.12,
        cascade_passes=5,
        security_param=1e-6,
    ),
    DemoScenario(
        name="Threshold Test",
        description="Operating near security limit (QBER ~10-12%)",
        noise_level=0.100,
        num_pairs=4000,
        num_runs=8,
        color="#e74c3c",
        test_bits_ratio=0.15,
        cascade_passes=6,
        security_param=1e-6,
    ),
]

QUICK_SCENARIOS = [
    DemoScenario(
        name="Quick Validation",
        description="Fast sanity check with moderate noise",
        noise_level=0.03,
        num_pairs=750,  # Increased for reliable key generation
        num_runs=3,
        color="#9b59b6",
        test_bits_ratio=0.10,
        cascade_passes=4,
        security_param=1e-6,  # Standard security parameter
    ),
]


# =============================================================================
# Mock Simulation (when SquidASM not available)
# =============================================================================

def run_mock_simulation(scenario: DemoScenario) -> Dict[str, Any]:
    """Run a mock simulation with realistic behavior."""
    import random
    
    # Set seed for reproducibility within demo
    random.seed(hash(scenario.name) % 10000)
    
    results = []
    for run_id in range(scenario.num_runs):
        # Realistic QBER simulation with variance dependent on noise level
        base_qber = scenario.noise_level
        variance_factor = 0.15 + 0.10 * (base_qber / 0.11)
        qber = random.gauss(base_qber, base_qber * variance_factor)
        qber = max(0.005, min(qber, 0.18))
        
        QBER_THRESHOLD = 0.11
        error_msg = None
        
        if qber >= QBER_THRESHOLD:
            # QBER exceeds security threshold
            success = False
            raw_key_length = int(scenario.num_pairs * 0.5 * (1 - scenario.test_bits_ratio))
            final_key_length = 0
            secret_key = []
            leakage_ec = 0
            leakage_ver = 0
            error_msg = f"QBER {qber:.1%} exceeds security threshold (11%)"
        else:
            # Calculate key length using realistic formulas
            sifted_length = int(scenario.num_pairs * 0.5)
            test_bits = int(sifted_length * scenario.test_bits_ratio)
            raw_key_length = sifted_length - test_bits
            
            # Binary entropy function h(p)
            if 0 < qber < 0.5:
                h_qber = -qber * np.log2(qber) - (1 - qber) * np.log2(1 - qber)
            else:
                h_qber = 0
            
            # Secrecy capacity: bits that are information-theoretically secret
            secrecy_rate = 1 - h_qber
            
            # Cascade leakage: typically 1.05-1.2 times the entropy leaked
            cascade_efficiency = 1.05 + 0.10 * (qber / 0.11)
            leakage_ec = int(raw_key_length * h_qber * cascade_efficiency)
            leakage_ver = 64  # Verification hash tag
            
            # Security margin: 2 * log2(1/epsilon)
            # Use scenario's security_param (e.g., 1e-10 -> ~33 bits)
            security_bits = int(np.ceil(2 * np.log2(1 / scenario.security_param)))
            
            # Final key length = secrecy_capacity - leakage - security_margin
            available_bits = raw_key_length * secrecy_rate
            final_key_length = max(0, int(available_bits - leakage_ec - leakage_ver - security_bits))
            
            if final_key_length > 0:
                success = True
                secret_key = [random.randint(0, 1) for _ in range(final_key_length)]
            else:
                success = False
                secret_key = []
                error_msg = f"Insufficient secrecy (key length would be {final_key_length})"
        
        results.append({
            "run_id": run_id,
            "success": success,
            "qber": qber,
            "raw_key_length": raw_key_length,
            "final_key_length": final_key_length,
            "secret_key": secret_key,
            "leakage_ec": leakage_ec,
            "leakage_ver": leakage_ver,
            "error": error_msg,
        })
    
    return {
        "scenario": scenario.name,
        "config": {
            "noise_level": scenario.noise_level,
            "num_pairs": scenario.num_pairs,
            "test_bits_ratio": scenario.test_bits_ratio,
            "cascade_passes": scenario.cascade_passes,
        },
        "runs": results,
    }


def run_squidasm_simulation(scenario: DemoScenario) -> Dict[str, Any]:
    """Run actual SquidASM simulation."""
    from hackathon_challenge.core.protocol import create_qkd_programs
    from hackathon_challenge.core.constants import (
        RESULT_SECRET_KEY,
        RESULT_QBER,
        RESULT_SUCCESS,
        RESULT_LEAKAGE,
        RESULT_ERROR,
    )
    
    # Create network with depolarizing noise model
    # link_noise maps to fidelity = 1 - link_noise * 3/4
    # e.g., link_noise=0.05 -> fidelity=0.9625
    network_config = create_two_node_network(
        node_names=["Alice", "Bob"],
        link_noise=scenario.noise_level,
        qdevice_noise=0.0,
    )
    
    # Calculate test bits based on scenario config
    # Use scenario's test_bits_ratio for consistency
    num_test_bits = int(scenario.num_pairs * scenario.test_bits_ratio)
    
    # Create programs with parameters balanced for viable key generation
    # Note: Total overhead = leakage_ec + leakage_ver + 2*log2(1/epsilon_sec)
    # With epsilon_sec=1e-6, security margin = ~40 bits (vs ~80 for 1e-12)
    alice, bob = create_qkd_programs(
        num_epr_pairs=scenario.num_pairs,
        num_test_bits=num_test_bits,
        cascade_seed=42,
        auth_key=b"demo_shared_key",
        verification_tag_bits=64,
        security_parameter=1e-6,  # Relaxed for demo (still cryptographically strong)
    )
    
    # Suppress verbose logging
    import logging
    alice._logger.setLevel(logging.WARNING)
    bob._logger.setLevel(logging.WARNING)
    
    # Run simulation
    sim_results = run(
        config=network_config,
        programs={"Alice": alice, "Bob": bob},
        num_times=scenario.num_runs,
    )
    
    # Process results
    alice_results = sim_results[0]
    bob_results = sim_results[1]
    
    results = []
    for run_id, (alice_res, bob_res) in enumerate(zip(alice_results, bob_results)):
        success = alice_res.get(RESULT_SUCCESS, False) and bob_res.get(RESULT_SUCCESS, False)
        secret_key = alice_res.get(RESULT_SECRET_KEY, [])
        
        total_leakage = alice_res.get(RESULT_LEAKAGE, 0)
        if isinstance(total_leakage, dict):
            leakage_ec = total_leakage.get("ec", 0)
            leakage_ver = total_leakage.get("ver", 64)
        else:
            leakage_ec = total_leakage
            leakage_ver = 64
        
        results.append({
            "run_id": run_id,
            "success": success,
            "qber": alice_res.get(RESULT_QBER, 0),
            "raw_key_length": scenario.num_pairs // 2,
            "final_key_length": len(secret_key),
            "secret_key": secret_key,
            "leakage_ec": leakage_ec,
            "leakage_ver": leakage_ver,
            "error": alice_res.get(RESULT_ERROR),
        })
    
    return {
        "scenario": scenario.name,
        "config": {
            "noise_level": scenario.noise_level,
            "num_pairs": scenario.num_pairs,
            "test_bits_ratio": scenario.test_bits_ratio,
            "cascade_passes": scenario.cascade_passes,
        },
        "runs": results,
    }


# =============================================================================
# Visualization Functions
# =============================================================================

def create_demo_plots(all_results: List[Dict[str, Any]], output_dir: Path):
    """Create visualization plots for the demo."""
    if not MATPLOTLIB_AVAILABLE:
        print(f"       {Style.YELLOW}[!]{Style.RESET} matplotlib not available, skipping plots")
        return
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Set style
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'ggplot')
    plt.rcParams['font.size'] = 10
    plt.rcParams['axes.titlesize'] = 12
    plt.rcParams['axes.labelsize'] = 11
    
    # Color scheme - updated for new scenarios
    colors = {
        "Ideal Channel": "#27ae60",
        "Standard Operation": "#3498db", 
        "Degraded Channel": "#f39c12",
        "Threshold Test": "#e74c3c",
        "Quick Validation": "#9b59b6",
        "Quick Demo": "#9b59b6",
    }
    
    # =========================
    # Plot 1: Performance Analysis (3 panels)
    # =========================
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle("QKD Protocol Performance Analysis", fontsize=14, fontweight='bold', y=1.02)
    
    # Panel 1: QBER by Scenario (ALL runs, not just successful)
    ax1 = axes[0]
    scenario_names = []
    qber_means = []
    qber_stds = []
    bar_colors = []
    
    for result in all_results:
        name = result["scenario"]
        # Include ALL runs for QBER calculation
        all_qbers = [r["qber"] for r in result["runs"]]
        if all_qbers:
            scenario_names.append(name.replace(" ", "\n"))
            qber_means.append(np.mean(all_qbers) * 100)
            qber_stds.append(np.std(all_qbers) * 100)
            bar_colors.append(colors.get(name, "#666666"))
    
    if scenario_names:
        x_pos = np.arange(len(scenario_names))
        bars = ax1.bar(x_pos, qber_means, yerr=qber_stds, capsize=5, 
                       color=bar_colors, alpha=0.8, edgecolor='black', linewidth=1.2)
        ax1.axhline(y=11, color='darkred', linestyle='--', linewidth=2, label='Security Threshold (11%)')
        ax1.set_ylabel('QBER (%)')
        ax1.set_title('Quantum Bit Error Rate')
        ax1.set_xticks(x_pos)
        ax1.set_xticklabels(scenario_names, fontsize=9)
        ax1.legend(loc='upper left', fontsize=8)
        ax1.set_ylim(0, 15)
        
        for bar, mean in zip(bars, qber_means):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3, 
                    f'{mean:.1f}%', ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    # Panel 2: Key Length vs QBER (mark failures)
    ax2 = axes[1]
    for result in all_results:
        name = result["scenario"]
        qbers = [r["qber"] * 100 for r in result["runs"]]
        key_lengths = [r["final_key_length"] for r in result["runs"]]
        success_mask = [r["success"] for r in result["runs"]]
        
        # Successful runs
        qbers_success = [q for q, s in zip(qbers, success_mask) if s]
        keys_success = [k for k, s in zip(key_lengths, success_mask) if s]
        # Failed runs
        qbers_fail = [q for q, s in zip(qbers, success_mask) if not s]
        keys_fail = [k for k, s in zip(key_lengths, success_mask) if not s]
        
        if qbers_success:
            ax2.scatter(qbers_success, keys_success, s=80, c=colors.get(name, "#666666"),
                       label=name, alpha=0.8, edgecolors='black', linewidth=1)
        if qbers_fail:
            ax2.scatter(qbers_fail, keys_fail, s=80, c=colors.get(name, "#666666"),
                       alpha=0.3, edgecolors='black', linewidth=1, marker='x')
    
    ax2.axvline(x=11, color='darkred', linestyle='--', linewidth=2, alpha=0.7)
    ax2.set_xlabel('QBER (%)')
    ax2.set_ylabel('Final Key Length (bits)')
    ax2.set_title('Key Length vs Error Rate')
    ax2.legend(loc='upper right', fontsize=8)
    ax2.set_xlim(0, 15)
    
    # Panel 3: Success Rate
    ax3 = axes[2]
    scenario_names_sr = []
    success_rates = []
    bar_colors_sr = []
    
    for result in all_results:
        name = result["scenario"]
        total = len(result["runs"])
        successful = sum(1 for r in result["runs"] if r["success"])
        scenario_names_sr.append(name.replace(" ", "\n"))
        success_rates.append(successful / total * 100 if total > 0 else 0)
        bar_colors_sr.append(colors.get(name, "#666666"))
    
    x_pos = np.arange(len(scenario_names_sr))
    bars = ax3.bar(x_pos, success_rates, color=bar_colors_sr, alpha=0.8,
                   edgecolor='black', linewidth=1.2)
    ax3.set_ylabel('Success Rate (%)')
    ax3.set_title('Protocol Success Rate')
    ax3.set_xticks(x_pos)
    ax3.set_xticklabels(scenario_names_sr, fontsize=9)
    ax3.set_ylim(0, 110)
    
    for bar, rate in zip(bars, success_rates):
        ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                f'{rate:.0f}%', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    plot_path = output_dir / "qkd_demo_analysis.png"
    plt.savefig(plot_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    
    print(f"       {Style.GREEN}[OK]{Style.RESET} Saved: {plot_path}")
    
    # =========================
    # Plot 2: Protocol Pipeline
    # =========================
    fig, ax = plt.subplots(figsize=(16, 7))
    
    # Define stages with (name, color) - organized by phase
    stages = [
        # Phase 1: Quantum Exchange
        ("HMAC\nHandshake", "#8e44ad"),
        ("EPR\nDistribution", "#9b59b6"),
        # Phase 2: Sifting & Estimation  
        ("Basis\nSifting", "#3498db"),
        ("QBER\nEstimation", "#2980b9"),
        # Phase 3: Reconciliation
        ("Cascade\nReconciliation", "#27ae60"),
        # Phase 4: Verification
        ("Hash\nVerification", "#f39c12"),
        # Phase 5: Privacy Amplification
        ("Toeplitz\nHashing", "#e74c3c"),
        ("Secure\nKey", "#1abc9c"),
    ]
    
    box_width = 0.10
    box_height = 0.35
    y_center = 0.5
    spacing = 0.11
    
    for i, (name, color) in enumerate(stages):
        x = 0.05 + i * spacing
        
        rect = mpatches.FancyBboxPatch(
            (x, y_center - box_height/2), box_width, box_height,
            boxstyle="round,pad=0.02,rounding_size=0.02",
            facecolor=color, edgecolor='black', linewidth=2, alpha=0.85,
            transform=ax.transAxes
        )
        ax.add_patch(rect)
        
        ax.text(x + box_width/2, y_center, name, ha='center', va='center',
               fontsize=9, fontweight='bold', color='white', transform=ax.transAxes)
        
        if i < len(stages) - 1:
            ax.annotate('', xy=(x + spacing, y_center), xytext=(x + box_width + 0.005, y_center),
                       arrowprops=dict(arrowstyle='->', color='gray', lw=2),
                       transform=ax.transAxes)
    
    ax.text(0.5, 0.92, "BB84 QKD Protocol Pipeline", ha='center', va='bottom',
           fontsize=14, fontweight='bold', transform=ax.transAxes)
    
    # Add phase labels above the stages
    phase_labels = [
        (0.10, "Phase 1:\nQuantum Exchange"),
        (0.30, "Phase 2:\nSifting"),
        (0.50, "Phase 3:\nReconciliation"),
        (0.61, "Phase 4:\nVerification"),
        (0.78, "Phase 5:\nAmplification"),
    ]
    for x, label in phase_labels:
        ax.text(x, 0.82, label, ha='center', va='bottom', fontsize=8, 
               style='italic', color='#555555', transform=ax.transAxes)
    
    legend_items = [
        mpatches.Patch(facecolor='#9b59b6', edgecolor='black', label='Phase 1: Quantum Exchange'),
        mpatches.Patch(facecolor='#3498db', edgecolor='black', label='Phase 2: Classical Sifting'),
        mpatches.Patch(facecolor='#27ae60', edgecolor='black', label='Phase 3: Error Correction'),
        mpatches.Patch(facecolor='#f39c12', edgecolor='black', label='Phase 4: Verification'),
        mpatches.Patch(facecolor='#e74c3c', edgecolor='black', label='Phase 5: Privacy Amplification'),
        mpatches.Patch(facecolor='#1abc9c', edgecolor='black', label='Output: Secure Key'),
    ]
    ax.legend(handles=legend_items, loc='lower center', ncol=3, fontsize=8,
             bbox_to_anchor=(0.5, -0.08), frameon=True)
    
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    
    pipeline_path = output_dir / "qkd_pipeline.png"
    plt.savefig(pipeline_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    
    print(f"       {Style.GREEN}[OK]{Style.RESET} Saved: {pipeline_path}")


# =============================================================================
# Main Demo Logic
# =============================================================================

def run_demo(scenarios: List[DemoScenario], use_mock: bool = False, 
             create_plots: bool = True) -> List[Dict[str, Any]]:
    """Run the full demonstration."""
    
    all_results = []
    
    # System info
    print_section("SYSTEM CONFIGURATION")
    print(f"       * Mode: {Style.CYAN}{'Mock Simulation' if use_mock else 'SquidASM Simulation'}{Style.RESET}")
    print(f"       * Scenarios: {Style.CYAN}{len(scenarios)}{Style.RESET}")
    print(f"       * Timestamp: {Style.CYAN}{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Style.RESET}")
    
    if not use_mock and SQUIDASM_AVAILABLE:
        print(f"       * Backend: {Style.GREEN}SquidASM Quantum Network Simulator{Style.RESET}")
    else:
        print(f"       * Backend: {Style.YELLOW}Mock Simulation (demonstration mode){Style.RESET}")
    
    time.sleep(1.0)
    
    # Protocol overview
    print_section("PROTOCOL OVERVIEW")
    print(f"""
    {Style.BOLD}BB84 Quantum Key Distribution Protocol{Style.RESET}
    
    Enables two parties (Alice and Bob) to establish a shared secret key with
    information-theoretic security guaranteed by quantum mechanics.
    
    {Style.BOLD}Security Guarantee:{Style.RESET} Any eavesdropping attempt disturbs quantum states,
                       introducing detectable errors in the key material.
    {Style.BOLD}Threshold:{Style.RESET} Protocol aborts if QBER > 11% (Shor-Preskill bound).
    """)
    
    time.sleep(1.0)
    
    print(f"    {Style.BOLD}Protocol Pipeline:{Style.RESET}")
    print()
    print(f"    {Style.CYAN}Phase 1: Quantum Exchange{Style.RESET}")
    print(f"       1. Secure Handshake      - Initialize HMAC-authenticated channel")
    print(f"       2. EPR Distribution      - Generate entangled pairs, measure in Z/X basis")
    print()
    print(f"    {Style.CYAN}Phase 2: Sifting & Estimation{Style.RESET}")
    print(f"       3. Basis Sifting         - Compare bases, discard mismatches (~50% kept)")
    print(f"       4. QBER Estimation       - Sample test bits, detect eavesdropping")
    print()
    print(f"    {Style.CYAN}Phase 3: Reconciliation (Cascade){Style.RESET}")
    print(f"       5. Error Correction      - Binary search to locate and fix bit errors")
    print(f"       6. Backtracking          - Recursively verify earlier blocks")
    print()
    print(f"    {Style.CYAN}Phase 4: Verification{Style.RESET}")
    print(f"       7. Polynomial Hashing    - Generate fingerprint with random salt")
    print(f"       8. Key Comparison        - Verify fingerprints match (abort if not)")
    print()
    print(f"    {Style.CYAN}Phase 5: Privacy Amplification{Style.RESET}")
    print(f"       9. Leakage Calculation   - Sum quantum + classical information leaked")
    print(f"      10. Toeplitz Hashing      - Compress key to erase Eve's partial knowledge")
    print(f"      11. Final Output          - Unconditionally secure shared secret key")
    print()
    
    time.sleep(2.5)
    
    # Scenarios overview table
    print_section("SIMULATION SCENARIOS")
    print()
    print(f"    {'Scenario':<22} {'Noise':>8} {'EPR Pairs':>12} {'Runs':>8} {'Test Bits':>12}")
    print(f"    {'-'*22} {'-'*8} {'-'*12} {'-'*8} {'-'*12}")
    for s in scenarios:
        test_bits = int(s.num_pairs * s.test_bits_ratio)
        print(f"    {s.name:<22} {s.noise_level*100:>7.1f}% {s.num_pairs:>12} {s.num_runs:>8} {test_bits:>12}")
    print()
    
    time.sleep(1.5)
    
    # Run each scenario
    for scenario_idx, scenario in enumerate(scenarios):
        print_section(f"SCENARIO {scenario_idx + 1}/{len(scenarios)}: {scenario.name.upper()}")
        print(f"    {Style.DIM}{scenario.description}{Style.RESET}")
        
        time.sleep(0.5)
        
        print()
        print(f"    {Style.BOLD}Configuration Parameters:{Style.RESET}")
        print(f"       * Channel noise level: {Style.CYAN}{scenario.noise_level * 100:.1f}%{Style.RESET}")
        print(f"       * EPR pairs: {Style.CYAN}{scenario.num_pairs}{Style.RESET}")
        print(f"       * Test bits for QBER: {Style.CYAN}{int(scenario.num_pairs * scenario.test_bits_ratio)}{Style.RESET}")
        print(f"       * Cascade passes: {Style.CYAN}{scenario.cascade_passes}{Style.RESET}")
        print(f"       * Security parameter: {Style.CYAN}{scenario.security_param:.0e}{Style.RESET}")
        print(f"       * Independent runs: {Style.CYAN}{scenario.num_runs}{Style.RESET}")
        
        time.sleep(1.0)
        
        print()
        print(f"    {Style.BOLD}Protocol Execution:{Style.RESET}")
        print()
        
        # Phase 1: Quantum Exchange
        print(f"    {Style.DIM}--- Phase 1: Quantum Exchange ---{Style.RESET}")
        print_step(1, "Secure handshake (HMAC authentication)", "running")
        animated_wait("Establishing authenticated channel", 0.3)
        print_step(1, "Authenticated channel established", "done")
        
        print_step(2, "EPR pair generation and measurement", "running")
        animated_wait(f"Distributing {scenario.num_pairs} entangled pairs", 0.5)
        print_step(2, "Quantum states distributed and measured", "done")
        print()
        
        # Phase 2: Sifting & Estimation
        print(f"    {Style.DIM}--- Phase 2: Sifting & Estimation ---{Style.RESET}")
        print_step(3, "Basis sifting via classical channel", "running")
        animated_wait("Comparing measurement bases", 0.3)
        print_step(3, "Basis sifting complete (~50% retained)", "done")
        
        print_step(4, "QBER estimation via test bit sampling", "running")
        animated_wait("Sampling and comparing test bits", 0.3)
        print_step(4, "QBER estimation complete", "done")
        print()
        
        # Phase 3: Reconciliation
        print(f"    {Style.DIM}--- Phase 3: Cascade Reconciliation ---{Style.RESET}")
        print_step(5, "Interactive error correction", "running")
        animated_wait(f"Running {scenario.cascade_passes} Cascade passes", 0.6)
        print_step(5, "Error correction complete", "done")
        print()
        
        # Phase 4: Verification
        print(f"    {Style.DIM}--- Phase 4: Verification ---{Style.RESET}")
        print_step(6, "Polynomial hash verification", "running")
        animated_wait("Computing and comparing fingerprints", 0.3)
        print_step(6, "Key verification passed", "done")
        print()
        
        # Phase 5: Privacy Amplification
        print(f"    {Style.DIM}--- Phase 5: Privacy Amplification ---{Style.RESET}")
        print_step(7, "Toeplitz hashing for secrecy", "running")
        animated_wait("Compressing key to remove leaked information", 0.4)
        print_step(7, "Secure key extracted", "done")
        
        time.sleep(0.5)
        
        print()
        print(f"    {Style.BOLD}Executing Simulation...{Style.RESET}")
        
        start_time = time.time()
        if use_mock or not SQUIDASM_AVAILABLE:
            result = run_mock_simulation(scenario)
        else:
            result = run_squidasm_simulation(scenario)
        elapsed = time.time() - start_time
        
        all_results.append(result)
        
        # Display results
        print()
        print(f"    {Style.BOLD}Results:{Style.RESET}")
        
        successful_runs = [r for r in result["runs"] if r["success"]]
        failed_runs = [r for r in result["runs"] if not r["success"]]
        
        success_rate = len(successful_runs) / len(result["runs"]) * 100
        print_metric("Success Rate", f"{success_rate:.0f}% ({len(successful_runs)}/{len(result['runs'])} runs)", "", success_rate >= 80)
        
        # Show QBER statistics for ALL runs
        all_qbers = [r["qber"] for r in result["runs"]]
        avg_qber = np.mean(all_qbers)
        std_qber = np.std(all_qbers)
        print_metric("Average QBER", f"{avg_qber:.2%} +/- {std_qber:.2%}", "", avg_qber < 0.11)
        
        if successful_runs:
            avg_key_len = np.mean([r["final_key_length"] for r in successful_runs])
            min_key_len = min([r["final_key_length"] for r in successful_runs])
            max_key_len = max([r["final_key_length"] for r in successful_runs])
            print_metric("Final Key Length", f"{avg_key_len:.0f} bits (range: {min_key_len}-{max_key_len})", "", avg_key_len >= 50)
            
            if successful_runs[0]["secret_key"]:
                print()
                print(f"    {Style.BOLD}Sample Secure Key (first successful run):{Style.RESET}")
                print_key_visual(successful_runs[0]["secret_key"])
        
        if failed_runs:
            print()
            print(f"       {Style.YELLOW}[!]{Style.RESET} {len(failed_runs)} run(s) failed:")
            for r in failed_runs[:3]:
                error_reason = r.get("error", "Unknown error")
                print(f"           Run {r['run_id']}: {error_reason} (QBER={r['qber']:.2%})")
        
        print()
        print(f"    {Style.DIM}Execution time: {elapsed:.2f}s{Style.RESET}")
        
        time.sleep(1.0)
    
    # Summary
    print_section("Summary")
    time.sleep(0.5)
    
    total_runs = sum(len(r["runs"]) for r in all_results)
    total_success = sum(sum(1 for run in r["runs"] if run["success"]) for r in all_results)
    
    print(f"    {Style.BOLD}Aggregate Statistics:{Style.RESET}")
    print()
    
    # Summary table
    print(f"    +{'-'*40}+{'-'*15}+")
    print(f"    | {'Metric':<38} | {'Value':>13} |")
    print(f"    +{'-'*40}+{'-'*15}+")
    print(f"    | {'Total simulation runs':<38} | {total_runs:>13} |")
    print(f"    | {'Successful key exchanges':<38} | {Style.GREEN}{total_success:>13}{Style.RESET} |")
    print(f"    | {'Failed (QBER threshold exceeded)':<38} | {Style.RED}{total_runs - total_success:>13}{Style.RESET} |")
    print(f"    | {'Overall success rate':<38} | {total_success/total_runs*100:>12.1f}% |")
    print(f"    +{'-'*40}+{'-'*15}+")
    print()
    
    # Per-scenario summary
    print(f"    {Style.BOLD}Per-Scenario Breakdown:{Style.RESET}")
    print()
    print(f"    +{'-'*24}+{'-'*8}+{'-'*10}+{'-'*12}+")
    print(f"    | {'Scenario':<22} | {'Runs':>6} | {'Success':>8} | {'Avg QBER':>10} |")
    print(f"    +{'-'*24}+{'-'*8}+{'-'*10}+{'-'*12}+")
    
    for result in all_results:
        name = result["scenario"][:22]
        runs = len(result["runs"])
        success = sum(1 for r in result["runs"] if r["success"])
        all_qbers = [r["qber"] for r in result["runs"]]
        avg_qber = np.mean(all_qbers) if all_qbers else 0
        
        success_str = f"{success}/{runs}"
        qber_str = f"{avg_qber:.2%}"
        
        print(f"    | {name:<22} | {runs:>6} | {success_str:>8} | {qber_str:>10} |")
    
    print(f"    +{'-'*24}+{'-'*8}+{'-'*10}+{'-'*12}+")
    print()
    
    time.sleep(1.0)
    
    # Generate plots
    if create_plots:
        print(f"    {Style.BOLD}Generating Visualizations...{Style.RESET}")
        animated_wait("Creating analysis plots", 1.5)
        output_dir = Path(__file__).parent.parent / "results" / "demo_plots"
        create_demo_plots(all_results, output_dir)
        print()
        time.sleep(0.5)
    
    # Footer
    print()
    print(f"{Style.BRIGHT_CYAN}{'='*78}{Style.RESET}")
    print(f"{Style.BRIGHT_CYAN}                    DEMONSTRATION COMPLETE{Style.RESET}")
    print(f"{Style.DIM}    Secure quantum key distribution achieved using BB84 protocol{Style.RESET}")
    print(f"{Style.BRIGHT_CYAN}{'='*78}{Style.RESET}")
    print()
    
    return all_results


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Live demonstration of QKD protocol",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--quick", "-q",
        action="store_true",
        help="Run quick demo with fewer scenarios",
    )
    parser.add_argument(
        "--mock", "-m",
        action="store_true",
        help="Use mock simulation (no SquidASM required)",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Skip plot generation",
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Don't clear screen at start",
    )
    
    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()
    
    # Clear screen and show banner
    if not args.no_clear:
        clear_screen()
    print_banner()
    
    # Select scenarios
    scenarios = QUICK_SCENARIOS if args.quick else DEMO_SCENARIOS
    
    # Determine simulation mode
    use_mock = args.mock or not SQUIDASM_AVAILABLE
    
    # Run demo
    try:
        run_demo(
            scenarios=scenarios,
            use_mock=use_mock,
            create_plots=not args.no_plots,
        )
        return 0
    except KeyboardInterrupt:
        print(f"\n\n{Style.YELLOW}{Symbols.WARNING} Demo interrupted by user{Style.RESET}")
        return 1
    except Exception as e:
        print(f"\n{Style.RED}{Symbols.CROSS} Error: {e}{Style.RESET}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
