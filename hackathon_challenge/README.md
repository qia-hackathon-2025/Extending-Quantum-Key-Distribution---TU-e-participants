# QKD Extension: Cascade Reconciliation & Toeplitz Privacy Amplification

This package implements an extended Quantum Key Distribution (QKD) protocol based on the BB84 protocol with:
- **Cascade error reconciliation** (interactive parity-based correction)
- **Polynomial hash verification** (universal hashing over GF(2^n))
- **Toeplitz privacy amplification** (2-universal hashing)
- **Wegman-Carter authentication** (information-theoretic security)

## Project Structure

```
hackathon_challenge/
├── core/              # Main protocol components
├── auth/              # Authentication layer
├── reconciliation/    # Error correction (Cascade)
├── verification/      # Key verification (Polynomial hashing)
├── privacy/           # Privacy amplification (Toeplitz)
├── utils/             # Shared utilities
├── scripts/           # Execution scripts
└── tests/             # Unit and integration tests
```

## Installation

```bash
# From qia-hackathon-2025 root directory
cd qia-hackathon-2025
pip install -e .
pip install -e ".[dev]"  # For development tools
```

## Usage

Run a simulation:

```bash
cd hackathon_challenge
python scripts/run_simulation.py
```

Run tests:

```bash
# From qia-hackathon-2025 root
pytest hackathon_challenge/tests/ -v
pytest --cov=hackathon_challenge --cov-report=html
```

## Configuration

Edit `config.yaml` to adjust:
- Number of EPR pairs
- QBER threshold
- Cascade parameters
- Security parameters

## References

- **Implementation Plan**: `../challenges/qkd/implementation_plan.md`
- **Theoretical Framework**: `../docs/challenges/qkd/extending_qkd_theorethical_aspects.md`
- **Technical Guide**: `../docs/challenges/qkd/extending_qkd_technical_aspects.md`
- **Baseline Code**: `../../squidasm/examples/applications/qkd/example_qkd.py`

## License

See project root LICENSE file.
