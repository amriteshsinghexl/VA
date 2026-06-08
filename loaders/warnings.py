"""
ModelWarning — lightweight warning class used across all layers.

Usage:
    from io.warnings import ModelWarning, warn
    warn("RAND placeholder encountered — value not used", source="Product Features!CO5")
"""
from __future__ import annotations

import dataclasses
import warnings
from typing import ClassVar


@dataclasses.dataclass
class ModelWarning(UserWarning):
    """Issued for non-fatal model anomalies that should appear in the Warnings sheet."""

    message: str
    source: str = ""

    _registry: ClassVar[list["ModelWarning"]] = []

    def __str__(self) -> str:
        return f"{self.message}" + (f"  [source: {self.source}]" if self.source else "")


def warn(message: str, source: str = "") -> None:
    """Issue a ModelWarning and register it for output sheet collection."""
    w = ModelWarning(message=message, source=source)
    ModelWarning._registry.append(w)
    warnings.warn(w, stacklevel=2)


def get_warnings() -> list[ModelWarning]:
    return list(ModelWarning._registry)


def clear_warnings() -> None:
    ModelWarning._registry.clear()
