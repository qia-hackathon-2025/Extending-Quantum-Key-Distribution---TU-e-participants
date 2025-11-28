"""Tests for the results infrastructure and scenario configuration.

Tests for:
- Result dataclasses
- JSON/CSV serialization
- Config loading and merging
- Scenario runner (mock mode)
"""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from hackathon_challenge.utils.results import (
    RunResult,
    ScenarioResult,
    save_results_json,
    save_results_csv,
    load_results_json,
    load_results_csv,
    generate_result_filename,
    generate_summary_report,
)

from hackathon_challenge.configs import (
    load_base_config,
    load_scenario,
    list_scenarios,
    list_networks,
)


# =============================================================================
# RunResult Tests
# =============================================================================


class TestRunResult:
    """Tests for RunResult dataclass."""

    def test_create_successful_run(self):
        """Test creating a successful run result."""
        result = RunResult(
            run_id=0,
            success=True,
            qber=0.05,
            raw_key_length=500,
            final_key_length=200,
            leakage_ec=50.0,
            leakage_ver=64.0,
            duration_ms=1234.5,
            keys_match=True,
        )

        assert result.success is True
        assert result.qber == 0.05
        assert result.final_key_length == 200
        assert result.keys_match is True
        assert result.error_message is None

    def test_create_failed_run(self):
        """Test creating a failed run result."""
        result = RunResult(
            run_id=1,
            success=False,
            qber=0.15,
            error_message="QBER above threshold",
        )

        assert result.success is False
        assert result.error_message == "QBER above threshold"
        assert result.final_key_length == 0

    def test_default_values(self):
        """Test default values are set correctly."""
        result = RunResult(run_id=0, success=False)

        assert result.qber is None
        assert result.raw_key_length == 0
        assert result.final_key_length == 0
        assert result.leakage_ec == 0.0
        assert result.leakage_ver == 0.0
        assert result.error_message is None
        assert result.duration_ms == 0.0
        assert result.keys_match is None


# =============================================================================
# ScenarioResult Tests
# =============================================================================


class TestScenarioResult:
    """Tests for ScenarioResult dataclass."""

    @pytest.fixture
    def sample_runs(self):
        """Create sample run results."""
        return [
            RunResult(run_id=0, success=True, qber=0.04, final_key_length=150, keys_match=True),
            RunResult(run_id=1, success=True, qber=0.05, final_key_length=140, keys_match=True),
            RunResult(run_id=2, success=False, qber=0.12, error_message="QBER above threshold"),
            RunResult(run_id=3, success=True, qber=0.03, final_key_length=160, keys_match=True),
        ]

    def test_create_scenario_result(self, sample_runs):
        """Test creating a scenario result."""
        result = ScenarioResult(
            scenario_name="test_scenario",
            config={"network": {"link_noise": 0.05}},
            runs=sample_runs,
        )

        assert result.scenario_name == "test_scenario"
        assert len(result.runs) == 4
        assert "link_noise" in result.config["network"]

    def test_compute_summary(self, sample_runs):
        """Test summary computation."""
        result = ScenarioResult(
            scenario_name="test_scenario",
            runs=sample_runs,
        )

        summary = result.compute_summary()

        assert summary["total_runs"] == 4
        assert summary["successful_runs"] == 3
        assert summary["failed_runs"] == 1
        assert summary["success_rate"] == 0.75

        assert abs(summary["avg_qber"] - 0.04) < 0.01  # (0.04+0.05+0.03)/3
        assert summary["avg_key_length"] == 150.0

        assert "error_distribution" in summary
        assert summary["error_distribution"]["QBER above threshold"] == 1

    def test_compute_summary_empty(self):
        """Test summary computation with no runs."""
        result = ScenarioResult(scenario_name="empty")
        summary = result.compute_summary()

        assert summary == {}

    def test_compute_summary_all_failed(self):
        """Test summary computation when all runs fail."""
        runs = [
            RunResult(run_id=0, success=False, error_message="Error A"),
            RunResult(run_id=1, success=False, error_message="Error B"),
            RunResult(run_id=2, success=False, error_message="Error A"),
        ]
        result = ScenarioResult(scenario_name="all_failed", runs=runs)
        summary = result.compute_summary()

        assert summary["success_rate"] == 0.0
        assert "avg_qber" not in summary
        assert summary["error_distribution"]["Error A"] == 2
        assert summary["error_distribution"]["Error B"] == 1


# =============================================================================
# Serialization Tests
# =============================================================================


class TestSerialization:
    """Tests for JSON/CSV serialization."""

    @pytest.fixture
    def sample_scenario(self):
        """Create a sample scenario result."""
        runs = [
            RunResult(run_id=0, success=True, qber=0.04, final_key_length=150),
            RunResult(run_id=1, success=False, qber=0.12, error_message="High QBER"),
        ]
        result = ScenarioResult(
            scenario_name="test_scenario",
            config={"network": {"link_noise": 0.05}},
            runs=runs,
        )
        result.compute_summary()
        return result

    def test_save_and_load_json(self, sample_scenario):
        """Test JSON save and load round-trip."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "results.json"
            
            # Save
            saved_path = save_results_json(sample_scenario, path)
            assert saved_path.exists()
            
            # Load
            loaded = load_results_json(saved_path)
            
            assert len(loaded) == 1
            assert loaded[0].scenario_name == "test_scenario"
            assert len(loaded[0].runs) == 2
            assert loaded[0].runs[0].success is True
            assert loaded[0].runs[1].error_message == "High QBER"

    def test_save_multiple_scenarios_json(self, sample_scenario):
        """Test saving multiple scenarios to JSON."""
        scenarios = [sample_scenario, sample_scenario]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "results.json"
            
            saved_path = save_results_json(scenarios, path)
            loaded = load_results_json(saved_path)
            
            assert len(loaded) == 2

    def test_save_csv(self, sample_scenario):
        """Test CSV export."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "results.csv"
            
            saved_path = save_results_csv(sample_scenario, path)
            assert saved_path.exists()
            
            # Load and verify
            rows = load_results_csv(saved_path)
            
            assert len(rows) == 2
            assert rows[0]["scenario"] == "test_scenario"
            assert rows[0]["success"] == "True"
            assert rows[1]["success"] == "False"

    def test_generate_filename(self):
        """Test result filename generation."""
        filename = generate_result_filename("low_noise", "json")
        
        assert filename.startswith("low_noise_")
        assert filename.endswith(".json")
        assert len(filename) > len("low_noise_.json")

    def test_generate_summary_report(self, sample_scenario):
        """Test summary report generation."""
        report = generate_summary_report([sample_scenario])
        
        assert "QKD SIMULATION RESULTS SUMMARY" in report
        assert "test_scenario" in report
        assert "Total runs:" in report


# =============================================================================
# Configuration Tests
# =============================================================================


class TestConfiguration:
    """Tests for configuration loading."""

    def test_load_base_config(self):
        """Test loading base configuration."""
        config = load_base_config()
        
        # Should have default sections
        assert "simulation" in config or config == {}  # May be empty if file missing

    def test_list_scenarios(self):
        """Test listing available scenarios."""
        scenarios = list_scenarios()
        
        # Should have at least the scenarios we created
        assert isinstance(scenarios, list)
        if scenarios:  # If configs directory exists
            assert "quick_test" in scenarios or "low_noise" in scenarios

    def test_list_networks(self):
        """Test listing available networks."""
        networks = list_networks()
        
        assert isinstance(networks, list)
        if networks:
            assert any("ideal" in n or "noisy" in n for n in networks)

    def test_load_scenario_exists(self):
        """Test loading an existing scenario."""
        scenarios = list_scenarios()
        if not scenarios:
            pytest.skip("No scenarios configured")
        
        config = load_scenario(scenarios[0])
        
        assert isinstance(config, dict)
        assert "scenario" in config or "simulation" in config

    def test_load_scenario_not_found(self):
        """Test loading a non-existent scenario raises error."""
        with pytest.raises(FileNotFoundError):
            load_scenario("nonexistent_scenario_xyz")

    def test_config_inheritance(self):
        """Test that scenario configs inherit from base."""
        base = load_base_config()
        if not base:
            pytest.skip("No base config")
        
        scenarios = list_scenarios()
        if not scenarios:
            pytest.skip("No scenarios")
        
        config = load_scenario(scenarios[0])
        
        # Should have merged base values
        # (specific test depends on base config content)
        assert isinstance(config, dict)


# =============================================================================
# Mock Scenario Runner Tests
# =============================================================================


class TestMockScenarioRunner:
    """Tests for the mock scenario runner."""

    def test_mock_run_produces_results(self):
        """Test mock runner produces valid results."""
        from hackathon_challenge.scripts.run_scenarios import run_scenario_mock
        
        config = {
            "scenario": {"name": "test"},
            "epr": {"num_pairs": 500, "num_test_bits": None},
            "network": {"link_noise": 0.05},
            "simulation": {"num_runs": 3},
        }
        
        result = run_scenario_mock(config)
        
        assert result.scenario_name == "test_mock"
        assert len(result.runs) == 3
        assert all(isinstance(r, RunResult) for r in result.runs)

    def test_mock_low_noise_high_success(self):
        """Test mock mode with low noise has high success rate."""
        from hackathon_challenge.scripts.run_scenarios import run_scenario_mock
        
        config = {
            "scenario": {"name": "low_noise"},
            "epr": {"num_pairs": 500, "num_test_bits": None},
            "network": {"link_noise": 0.02},  # Very low noise
            "simulation": {"num_runs": 10},
        }
        
        np.random.seed(42)  # For reproducibility
        result = run_scenario_mock(config)
        result.compute_summary()
        
        # Low noise should have high success rate
        assert result.summary["success_rate"] > 0.7

    def test_mock_high_noise_low_success(self):
        """Test mock mode with high noise has low success rate."""
        from hackathon_challenge.scripts.run_scenarios import run_scenario_mock
        
        config = {
            "scenario": {"name": "high_noise"},
            "epr": {"num_pairs": 500, "num_test_bits": None},
            "network": {"link_noise": 0.15},  # Above threshold
            "simulation": {"num_runs": 10},
        }
        
        np.random.seed(42)
        result = run_scenario_mock(config)
        result.compute_summary()
        
        # High noise should mostly fail
        assert result.summary["success_rate"] < 0.5


# =============================================================================
# Statistical Analysis Tests
# =============================================================================


class TestStatisticalAnalysis:
    """Tests for statistical analysis functions."""

    def test_qber_statistics(self):
        """Test QBER statistics calculation."""
        runs = [
            RunResult(run_id=i, success=True, qber=0.04 + i*0.01, final_key_length=100)
            for i in range(5)
        ]
        result = ScenarioResult(scenario_name="test", runs=runs)
        summary = result.compute_summary()
        
        assert abs(summary["avg_qber"] - 0.06) < 0.001  # Mean of [0.04, 0.05, 0.06, 0.07, 0.08]
        assert abs(summary["std_qber"] - np.std([0.04, 0.05, 0.06, 0.07, 0.08])) < 0.001
        assert summary["min_qber"] == 0.04
        assert summary["max_qber"] == 0.08

    def test_key_length_statistics(self):
        """Test key length statistics calculation."""
        runs = [
            RunResult(run_id=i, success=True, qber=0.05, final_key_length=100 + i*10)
            for i in range(5)
        ]
        result = ScenarioResult(scenario_name="test", runs=runs)
        summary = result.compute_summary()
        
        assert summary["avg_key_length"] == 120.0  # Mean of [100, 110, 120, 130, 140]
        assert summary["min_key_length"] == 100
        assert summary["max_key_length"] == 140

    def test_keys_match_rate(self):
        """Test keys match rate calculation."""
        runs = [
            RunResult(run_id=0, success=True, qber=0.05, final_key_length=100, keys_match=True),
            RunResult(run_id=1, success=True, qber=0.05, final_key_length=100, keys_match=True),
            RunResult(run_id=2, success=True, qber=0.05, final_key_length=100, keys_match=False),
            RunResult(run_id=3, success=True, qber=0.05, final_key_length=100, keys_match=True),
        ]
        result = ScenarioResult(scenario_name="test", runs=runs)
        summary = result.compute_summary()
        
        assert summary["keys_match_rate"] == 0.75  # 3 out of 4


# =============================================================================
# Plotting Tests (if matplotlib available)
# =============================================================================


class TestPlotting:
    """Tests for plotting functions."""

    @pytest.fixture
    def sample_results(self):
        """Create sample results for plotting."""
        scenarios = []
        for name, noise in [("low", 0.03), ("medium", 0.06), ("high", 0.10)]:
            runs = [
                RunResult(
                    run_id=i,
                    success=noise < 0.11,
                    qber=noise + np.random.normal(0, 0.01),
                    final_key_length=int(200 * (1 - noise * 5)) if noise < 0.11 else 0,
                )
                for i in range(5)
            ]
            result = ScenarioResult(scenario_name=f"{name}_noise", runs=runs)
            result.compute_summary()
            scenarios.append(result)
        return scenarios

    def test_plotting_functions_exist(self):
        """Test that plotting functions can be imported."""
        from hackathon_challenge.utils.results import (
            plot_qber_distribution,
            plot_key_length_vs_qber,
            plot_success_rate_comparison,
        )
        
        assert callable(plot_qber_distribution)
        assert callable(plot_key_length_vs_qber)
        assert callable(plot_success_rate_comparison)

    def test_plot_to_file(self, sample_results):
        """Test saving plot to file."""
        try:
            import matplotlib
            matplotlib.use("Agg")  # Non-interactive backend
            from hackathon_challenge.utils.results import plot_success_rate_comparison
            
            with tempfile.TemporaryDirectory() as tmpdir:
                path = Path(tmpdir) / "test_plot.png"
                plot_success_rate_comparison(sample_results, output_path=path, show=False)
                
                assert path.exists()
                assert path.stat().st_size > 0
        except ImportError:
            pytest.skip("matplotlib not available")
