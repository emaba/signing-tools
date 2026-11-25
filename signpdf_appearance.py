"""Compatibility import for source checkouts; installed commands use the package."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from signing_tools import signpdf_appearance as _implementation
sys.modules[__name__] = _implementation
