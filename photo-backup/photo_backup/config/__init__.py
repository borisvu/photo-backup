"""
Configuration management for photo backup system.

This package provides comprehensive configuration loading, validation,
and management with support for test mode using Minio instead of Wasabi.
"""

from .config import Config
from .defaults import DEFAULT_CONFIG, DEFAULT_CONFIG_DOCS, TEST_MODE_DEFAULTS
from .env_override import EnvOverride
from .loader import ConfigLoader
from .utils import ConfigUtils
from .validator import ConfigValidator

__all__ = [
    "DEFAULT_CONFIG",
    "DEFAULT_CONFIG_DOCS",
    "TEST_MODE_DEFAULTS",
    "Config",
    "ConfigLoader",
    "ConfigUtils",
    "ConfigValidator",
    "EnvOverride",
]
