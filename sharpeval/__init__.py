"""Local, descriptive comparisons of versioned trading-agent returns."""

__version__ = "0.3.0"

from .api import analyze, validate
from .validation import InputError, load_input

__all__ = ["analyze", "InputError", "load_input", "validate", "__version__"]
