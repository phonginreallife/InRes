"""
Config Package - Configuration Management.

- settings: Application settings and environment variables
- loader: YAML config loading from shared config file

Usage:
    from config import config
    
    db_url = config.database_url
    api_key = config.anthropic_api_key
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from .loader import load_config
from .settings import config  # Export the singleton

__all__ = [
    "load_config",
    "config",
]
