"""Typed parameters that configure a node without adding code.

A component declares the parameters it accepts as ``ParamSpec`` values. A node in an
agent definition supplies plain JSON values for them; they are checked against the
specs, never evaluated, so parameters remain data and not a way to run arbitrary code.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

ParamKind = Literal["string", "text", "integer", "number", "boolean", "enum"]
PARAM_KINDS: tuple[str, ...] = (
    "string",
    "text",
    "integer",
    "number",
    "boolean",
    "enum",
)

# Hard ceilings, so a stored definition cannot carry an unbounded blob.
MAX_STRING_LENGTH = 200
MAX_TEXT_LENGTH = 4000

UNKNOWN_PARAM = "UNKNOWN_PARAM"
INVALID_PARAM_VALUE = "INVALID_PARAM_VALUE"
MISSING_PARAM = "MISSING_PARAM"


class ParamError(ValueError):
    """A parameter value that a spec refuses; ``code`` matches the diagnostic."""

    def __init__(self, code: str, param: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.param = param


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


@dataclass(frozen=True)
class ParamSpec:
    """The declaration of one parameter: its type, limits and default."""

    name: str
    kind: ParamKind
    default: Any = None
    required: bool = False
    minimum: float | None = None
    maximum: float | None = None
    max_length: int | None = None
    choices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Parameter name cannot be empty")
        if self.kind not in PARAM_KINDS:
            raise ValueError(f"Parameter '{self.name}' has unknown kind '{self.kind}'")
        object.__setattr__(self, "choices", tuple(self.choices))
        if self.kind == "enum" and not self.choices:
            raise ValueError(f"Enum parameter '{self.name}' needs choices")
        if self.kind != "enum" and self.choices:
            raise ValueError(f"Parameter '{self.name}' is not an enum")
        if self.kind in {"string", "text"}:
            ceiling = MAX_STRING_LENGTH if self.kind == "string" else MAX_TEXT_LENGTH
            limit = ceiling if self.max_length is None else self.max_length
            if not 0 < limit <= ceiling:
                raise ValueError(f"Parameter '{self.name}' max_length is out of range")
            object.__setattr__(self, "max_length", limit)
        elif self.max_length is not None:
            raise ValueError(f"Parameter '{self.name}' takes no max_length")
        if self.kind not in {"integer", "number"} and (
            self.minimum is not None or self.maximum is not None
        ):
            raise ValueError(f"Parameter '{self.name}' takes no numeric range")
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum > self.maximum
        ):
            raise ValueError(f"Parameter '{self.name}' has an empty range")
        if self.default is None:
            if not self.required:
                raise ValueError(
                    f"Parameter '{self.name}' needs a default or required=True"
                )
            return
        try:
            object.__setattr__(self, "default", self.validate(self.default))
        except ParamError as error:
            raise ValueError(f"Default of '{self.name}' is invalid: {error}") from error

    def validate(self, value: Any) -> Any:
        """Return the value if it fits the spec, otherwise raise ``ParamError``."""

        def refuse(reason: str) -> ParamError:
            return ParamError(INVALID_PARAM_VALUE, self.name, f"{self.name}: {reason}")

        if self.kind == "boolean":
            if not isinstance(value, bool):
                raise refuse("must be true or false")
            return value
        if self.kind == "enum":
            if value not in self.choices:
                raise refuse(f"must be one of {list(self.choices)}")
            return value
        if self.kind in {"string", "text"}:
            if not isinstance(value, str):
                raise refuse("must be text")
            if len(value) > (self.max_length or 0):
                raise refuse(f"is longer than {self.max_length} characters")
            return value
        if self.kind == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                raise refuse("must be a whole number")
        elif not _is_number(value) or (
            isinstance(value, float) and not math.isfinite(value)
        ):
            raise refuse("must be a finite number")
        if self.minimum is not None and value < self.minimum:
            raise refuse(f"must be at least {self.minimum}")
        if self.maximum is not None and value > self.maximum:
            raise refuse(f"must be at most {self.maximum}")
        return value

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON, leaving out the limits that do not apply."""
        data: dict[str, Any] = {
            "name": self.name,
            "kind": self.kind,
            "default": self.default,
            "required": self.required,
        }
        if self.minimum is not None:
            data["minimum"] = self.minimum
        if self.maximum is not None:
            data["maximum"] = self.maximum
        if self.kind in {"string", "text"}:
            data["max_length"] = self.max_length
        if self.choices:
            data["choices"] = list(self.choices)
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ParamSpec":
        return cls(
            name=data["name"],
            kind=data["kind"],
            default=data.get("default"),
            required=bool(data.get("required", False)),
            minimum=data.get("minimum"),
            maximum=data.get("maximum"),
            max_length=data.get("max_length"),
            choices=tuple(data.get("choices", ())),
        )


def check_params(
    specs: Sequence[ParamSpec], params: Mapping[str, Any]
) -> list[ParamError]:
    """Every problem with ``params`` against ``specs``, in a stable order."""
    by_name = {spec.name: spec for spec in specs}
    problems: list[ParamError] = []
    for name in sorted(params):
        spec = by_name.get(name)
        if spec is None:
            problems.append(
                ParamError(
                    UNKNOWN_PARAM, name, f"{name}: this component has no such parameter"
                )
            )
            continue
        try:
            spec.validate(params[name])
        except ParamError as error:
            problems.append(error)
    for spec in specs:
        if spec.required and spec.name not in params:
            problems.append(
                ParamError(
                    MISSING_PARAM, spec.name, f"{spec.name}: a value is required"
                )
            )
    return problems


def resolve_params(
    specs: Sequence[ParamSpec], params: Mapping[str, Any]
) -> dict[str, Any]:
    """The given values with the defaults filled in, or the first problem raised."""
    problems = check_params(specs, params)
    if problems:
        raise problems[0]
    resolved = {spec.name: spec.default for spec in specs}
    resolved.update(params)
    return resolved
