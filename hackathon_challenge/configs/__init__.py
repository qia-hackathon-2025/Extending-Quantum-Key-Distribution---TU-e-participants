"""Configuration package for QKD hackathon challenge.

This package provides configuration management for QKD simulations.

Usage:
    from hackathon_challenge.configs import load_scenario, list_scenarios
    
    # List available scenarios
    scenarios = list_scenarios()
    
    # Load a specific scenario
    config = load_scenario("low_noise")
"""

import os
from pathlib import Path
from typing import Any, Dict, List

import yaml

CONFIGS_DIR = Path(__file__).parent
SCENARIOS_DIR = CONFIGS_DIR / "scenarios"
NETWORKS_DIR = CONFIGS_DIR / "networks"


def load_base_config() -> Dict[str, Any]:
    """Load the base configuration.
    
    Returns
    -------
    Dict[str, Any]
        Base configuration dictionary.
    """
    base_path = CONFIGS_DIR / "base.yaml"
    if not base_path.exists():
        return {}
    
    with open(base_path, "r") as f:
        return yaml.safe_load(f) or {}


def load_scenario(name: str) -> Dict[str, Any]:
    """Load a scenario configuration with base inheritance.
    
    Parameters
    ----------
    name : str
        Scenario name (without .yaml extension).
    
    Returns
    -------
    Dict[str, Any]
        Merged configuration dictionary.
    
    Raises
    ------
    FileNotFoundError
        If scenario file doesn't exist.
    """
    scenario_path = SCENARIOS_DIR / f"{name}.yaml"
    if not scenario_path.exists():
        raise FileNotFoundError(f"Scenario not found: {scenario_path}")
    
    # Start with base config
    config = load_base_config()
    
    # Load and merge scenario
    with open(scenario_path, "r") as f:
        scenario = yaml.safe_load(f) or {}
    
    return _deep_merge(config, scenario)


def load_network(name: str) -> Dict[str, Any]:
    """Load a network configuration.
    
    Parameters
    ----------
    name : str
        Network name (without .yaml extension).
    
    Returns
    -------
    Dict[str, Any]
        Network configuration dictionary.
    """
    network_path = NETWORKS_DIR / f"{name}.yaml"
    if not network_path.exists():
        raise FileNotFoundError(f"Network not found: {network_path}")
    
    with open(network_path, "r") as f:
        return yaml.safe_load(f) or {}


def list_scenarios() -> List[str]:
    """List available scenarios.
    
    Returns
    -------
    List[str]
        List of scenario names.
    """
    if not SCENARIOS_DIR.exists():
        return []
    return sorted(f.stem for f in SCENARIOS_DIR.glob("*.yaml"))


def list_networks() -> List[str]:
    """List available network configurations.
    
    Returns
    -------
    List[str]
        List of network names.
    """
    if not NETWORKS_DIR.exists():
        return []
    return sorted(f.stem for f in NETWORKS_DIR.glob("*.yaml"))


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge two dictionaries.
    
    Parameters
    ----------
    base : Dict
        Base dictionary.
    override : Dict
        Override dictionary (values take precedence).
    
    Returns
    -------
    Dict
        Merged dictionary.
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


__all__ = [
    "load_base_config",
    "load_scenario",
    "load_network",
    "list_scenarios",
    "list_networks",
    "CONFIGS_DIR",
    "SCENARIOS_DIR",
    "NETWORKS_DIR",
]
