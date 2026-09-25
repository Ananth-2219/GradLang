"""Public semantic pass, sharing ordered symbol and shape inference."""

from .symbol_table import SemanticError, Symbol, build_symbol_table


def analyze(function, parameter_types=None):
    """Return the checked symbol table; raise SemanticError on the first fault.

    Checking and symbol construction share one ordered walk. Checking against a
    completed table alone would incorrectly accept uses before assignments.
    """
    return build_symbol_table(function, parameter_types)
