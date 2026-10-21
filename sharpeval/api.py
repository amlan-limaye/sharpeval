"""Dispatch schema 1 to its unchanged compatibility engine; schema 2 is opt-in."""

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
    if isinstance(document, dict) and document.get("schema_version") == 2:
        return validate_experiment(document)
    return validate_v1(document)
