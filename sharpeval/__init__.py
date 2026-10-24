"""Local conditional cohort rankings and versioned trading-agent comparisons."""

__version__ = "0.4.0"

from .api import analyze, validate
from .validation import InputError, load_input
from .cohort import rank_cohort

__all__ = ["analyze", "rank_cohort", "InputError", "load_input", "validate", "__version__"]
