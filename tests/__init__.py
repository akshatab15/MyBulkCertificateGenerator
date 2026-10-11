"""Test package marker."""

from pathlib import Path
import sys

# Ensure the project root is importable when pytest is invoked from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
