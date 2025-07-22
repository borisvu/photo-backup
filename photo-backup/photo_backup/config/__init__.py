"""
Configuration management for photo backup system.

This package provides comprehensive configuration loading, validation,
and management with support for test mode using Minio instead of Wasabi.
"""

from .defaults import DEFAULT_CONFIG, DEFAULT_CONFIG_DOCS, TEST_MODE_DEFAULTS
from .validator import ConfigValidator
from .loader import ConfigLoader
from .utils import ConfigUtils
from .env_override import EnvOverride
from .config import Config

__all__ = [
    'Config',
    'ConfigValidator', 
    'ConfigLoader',
    'ConfigUtils',
    'EnvOverride',
    'DEFAULT_CONFIG',
    'DEFAULT_CONFIG_DOCS',
    'TEST_MODE_DEFAULTS'
]