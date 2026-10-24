"""Validate all input contracts; analyze preserves schema-1/2 comparisons.

Use the separate rank_cohort API for schema-3 evidence ranking.
"""

from .analysis import analyze as analyze_v1
from .experiments import analyze_experiment, validate_experiment
from .validation import InputError, validate as validate_v1


def analyze(document, **settings):
    if not isinstance(document, dict):
        raise InputError("input must be an object")
    if document.get("schema_version") == 2:
        return analyze_experiment(document, **settings)
    return analyze_v1(document, **settings)


def validate(document):
    if isinstance(document, dict) and document.get("schema_version") == 3:
        from .cohort import validate_cohort
        return validate_cohort(document)
    if isinstance(document, dict) and document.get("schema_version") == 2:
        return validate_experiment(document)
    return validate_v1(document)
