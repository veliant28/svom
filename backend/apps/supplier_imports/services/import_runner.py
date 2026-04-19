"""Backward-compatible shim for the decomposed import runner package."""

from .import_runner import ImportExecutionResult, SupplierImportRunner

__all__ = [
    "ImportExecutionResult",
    "SupplierImportRunner",
]
