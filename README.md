# Pan-European Quantum Internet Hackathon 2025 - QKD Extension

This repository contains the implementation of an extended Quantum Key Distribution (QKD) protocol for the QIA Hackathon 2025 challenge. The project extends the baseline BB84 implementation in SquidASM with production-grade post-processing components.

## Repository Structure

```
qia-hackathon-2025/
├── hackathon_challenge/   # Main implementation (see below)
├── docs/                  # Documentation
│   ├── challenges/qkd/    # Challenge specifications
│   ├── tutorials/         # SquidASM usage guides
│   ├── api/               # API reference
│   └── Advanced/          # Advanced topics
├── templates/             # Starter templates for 2/3-node networks
└── challenges/            # Original challenge PDFs
```

### hackathon_challenge/

The core implementation directory:

| Directory | Purpose |
|:----------|:--------|
| `core/` | Protocol orchestration (`AliceProgram`, `BobProgram`) |
| `auth/` | Wegman-Carter authentication over classical channels |
| `reconciliation/` | Cascade error correction with backtracking |
| `verification/` | Polynomial hash-based key verification |
| `privacy/` | Toeplitz matrix privacy amplification |
| `configs/` | YAML configuration files for scenarios |
| `scripts/` | Simulation execution and analysis tools |
| `tests/` | Unit and integration tests |
| `results/` | Simulation output (JSON, CSV, reports) |

See [hackathon_challenge/README.md](hackathon_challenge/README.md) for detailed component documentation.

### docs/

| Directory | Content |
|:----------|:--------|
| `challenges/qkd/` | Theoretical and technical specifications for the QKD extension challenge |
| `tutorials/` | Step-by-step SquidASM guides (basics, NetQASM, simulation control) |
| `api/` | Reference documentation for SquidASM classes and functions |
| `Advanced/` | Custom protocols, noise models, debugging |

## Installation

### Prerequisites

- Python 3.10 or higher
- NetSquid account (register at [forum.netsquid.org](https://forum.netsquid.org))
- Linux or macOS (Windows users require WSL)

### Setup

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Set NetSquid credentials:

```bash
export NETSQUIDPYPI_USER=your_username
export NETSQUIDPYPI_PWD=your_password
```

3. Install SquidASM (from a separate directory):

```bash
git clone https://github.com/QuTech-Delft/squidasm.git
cd squidasm
make install
make verify
cd ..
```

4. Install this package:

```bash
cd qia-hackathon-2025
pip install -e .
pip install -e ".[dev]"  # For development tools (pytest, mypy, black)
```

## Running Simulations

### Single Simulation

Execute a single QKD session with default or custom parameters:

```bash
cd hackathon_challenge
python scripts/run_simulation.py                     # Default parameters
python scripts/run_simulation.py --num-pairs 500     # Custom EPR pairs
python scripts/run_simulation.py --noise 0.05        # Set channel noise
python scripts/run_simulation.py --log-level DEBUG   # Verbose output
```

### Scenario Execution

Run predefined scenarios from configuration files:

```bash
python scripts/run_scenarios.py                      # Run all scenarios
python scripts/run_scenarios.py --scenario low_noise # Specific scenario
python scripts/run_scenarios.py --list               # List available scenarios
python scripts/run_scenarios.py --mock               # Mock mode (no SquidASM)
```

Available scenarios in `configs/scenarios/`:
- `quick_test.yaml` - Fast validation run
- `low_noise.yaml` - QBER approximately 2%
- `medium_noise.yaml` - QBER approximately 5%
- `high_noise.yaml` - QBER approximately 10%
- `threshold_test.yaml` - Near abort threshold (11%)

### Result Analysis

Analyze completed simulation results:

```bash
python scripts/analyze_results.py results/*.json    # Analyze specific files
python scripts/analyze_results.py --all             # Analyze all results
python scripts/analyze_results.py --all --plot      # Generate visualizations
```

## Output Structure

Simulation results are saved to `hackathon_challenge/results/` with timestamped filenames:

```
results/
├── results_2025-11-28T13-36-30-428019.json    # Structured result data
├── results_2025-11-28T13-36-30-428019.csv     # Tabular format
├── results_2025-11-28T13-36-30-428019_report.txt  # Human-readable summary
└── plots/                                      # Generated visualizations
```

### JSON Output Format

```json
{
  "scenario": "quick_test",
  "timestamp": "2025-11-28T13:36:30.428019",
  "runs": [
    {
      "success": true,
      "qber": 0.0156,
      "key_length": 42,
      "leakage": 128,
      "secret_key": "..."
    }
  ],
  "statistics": {
    "success_rate": 1.0,
    "avg_qber": 0.0156,
    "avg_key_length": 42
  }
}
```

### Report Format

```
======================================================================
QKD SIMULATION RESULTS SUMMARY
======================================================================
Scenario: quick_test
Total runs:      5
Successful:      5
Success rate:    100.0%
QBER (avg):      0.0156 +/- 0.002
Key length (avg): 42
======================================================================
```

## Testing

Run the test suite:

```bash
pytest hackathon_challenge/tests/ -v
pytest --cov=hackathon_challenge --cov-report=html
```

## Documentation

- [Theoretical Aspects](docs/challenges/qkd/extending_qkd_theorethical_aspects.md) - Mathematical framework for Cascade and privacy amplification
- [SquidASM Tutorial](https://squidasm.readthedocs.io/en/latest/) - Official SquidASM documentation

## License

See LICENSE file in project root.
