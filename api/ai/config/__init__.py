"""
Config Package - Configuration Management.

- settings: Application settings and environment variables
- loader: YAML config loading from shared config file
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from .loader import load_config
from .settings import get_config

__all__ = [
    "load_config",
    "get_config",
]
