"""
QuantifiedStrides API package.

Ensures the project root is on sys.path so that existing intelligence
modules (training_load, recovery, alerts, recommend, db) can be imported
from anywhere inside the api/ package tree.
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
