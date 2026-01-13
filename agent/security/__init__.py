"""
Security Package - Zero Trust and Authentication.

- verifier: Zero trust certificate verification
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from .verifier import get_verifier, init_verifier

__all__ = [
    "get_verifier",
    "init_verifier",
]
