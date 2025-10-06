"""
Configuration Management Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Loads and validates configuration from YAML file.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class Config:
    """Configuration loader and accessor."""

    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize configuration from YAML file.

        Args:
            config_path: Path to configuration file

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._load_config()
        self._validate_config()

    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}\n"
                f"Please copy config.sample.yaml to config.yaml and customize it."
            )

        with open(self.config_path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f)

        if not self._config:
            raise ValueError("Configuration file is empty")

    def _validate_config(self) -> None:
        """Validate required configuration sections exist."""
        required_sections = ["scraping", "rate_limiting", "output", "logging", "data"]

        for section in required_sections:
            if section not in self._config:
                raise ValueError(f"Missing required configuration section: {section}")

        # Validate scraping config
        scraping = self._config["scraping"]
        if not scraping.get("target_roles"):
            raise ValueError("No target roles specified in configuration")
        if not scraping.get("location"):
            raise ValueError("No location specified in configuration")

        # Validate rate limiting
        rate_limiting = self._config["rate_limiting"]
        if rate_limiting.get("max_requests_per_hour", 0) <= 0:
            raise ValueError("max_requests_per_hour must be positive")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-notation key.

        Args:
            key: Configuration key (e.g., 'scraping.target_roles')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value

    @property
    def app(self) -> Dict[str, Any]:
        """Get app configuration."""
        return self._config.get("app", {})

    @property
    def scraping(self) -> Dict[str, Any]:
        """Get scraping configuration."""
        return self._config["scraping"]

    @property
    def rate_limiting(self) -> Dict[str, Any]:
        """Get rate limiting configuration."""
        return self._config["rate_limiting"]

    @property
    def filters(self) -> Dict[str, Any]:
        """Get filtering configuration."""
        return self._config.get("filters", {})

    @property
    def output(self) -> Dict[str, Any]:
        """Get output configuration."""
        return self._config["output"]

    @property
    def logging(self) -> Dict[str, Any]:
        """Get logging configuration."""
        return self._config["logging"]

    @property
    def data(self) -> Dict[str, Any]:
        """Get data storage configuration."""
        return self._config["data"]

    @property
    def processing(self) -> Dict[str, Any]:
        """Get data processing configuration."""
        return self._config.get("processing", {})

    @property
    def enrichment(self) -> Dict[str, Any]:
        """Get enrichment configuration."""
        return self._config.get("enrichment", {})

    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        directories = [
            self.data.get("raw_dir", "./data/raw"),
            self.data.get("processed_dir", "./data/processed"),
            self.data.get("output_dir", "./data/output"),
            self.logging.get("directory", "./logs"),
        ]

        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)

    def __repr__(self) -> str:
        """String representation of config."""
        return f"Config(config_path='{self.config_path}')"
