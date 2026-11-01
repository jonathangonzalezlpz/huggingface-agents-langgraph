"""Structured diagnostics produced by static graph validation.

Diagnostics carry a stable code and location so a UI can highlight the affected
node or edge without parsing messages.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from huggingface_agents_langgraph.graph_definition.schema import (
    _freeze_metadata,
    _unfreeze_metadata,
)

Severity = Literal["error", "warning", "info"]
SEVERITIES: tuple[Severity, ...] = ("error", "warning", "info")


@dataclass(frozen=True)
class Diagnostic:
    """A single finding about an agent definition."""

    code: str
    severity: Severity
    message: str
    node_id: str | None = None
    edge_source: str | None = None
    branch: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.code or not self.code.strip():
            raise ValueError("Diagnostic code cannot be empty")
        if self.severity not in SEVERITIES:
            raise ValueError(
                f"Invalid diagnostic severity '{self.severity}', "
                f"must be one of {list(SEVERITIES)}"
            )
        object.__setattr__(self, "details", _freeze_metadata(self.details))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary, omitting unset locations."""
        data: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
        }
        for key in ("node_id", "edge_source", "branch"):
            value = getattr(self, key)
            if value is not None:
                data[key] = value
        if self.details:
            data["details"] = _unfreeze_metadata(self.details)
        return data


@dataclass(frozen=True)
class ValidationReport:
    """Ordered collection of diagnostics for one agent definition."""

    diagnostics: tuple[Diagnostic, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))

    def _with_severity(self, severity: Severity) -> tuple[Diagnostic, ...]:
        return tuple(d for d in self.diagnostics if d.severity == severity)

    @property
    def errors(self) -> tuple[Diagnostic, ...]:
        return self._with_severity("error")

    @property
    def warnings(self) -> tuple[Diagnostic, ...]:
        return self._with_severity("warning")

    @property
    def infos(self) -> tuple[Diagnostic, ...]:
        return self._with_severity("info")

    @property
    def is_valid(self) -> bool:
        """True when there are no errors; warnings and infos do not invalidate."""
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "counts": {s: len(self._with_severity(s)) for s in SEVERITIES},
            "diagnostics": [d.to_dict() for d in self.diagnostics],
        }
