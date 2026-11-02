"""Contract declarations for workflow node inputs and outputs.

Allows static validation and introspection of data flow across nodes without
executing the underlying node implementations.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class NodeContract:
    """Explicit declaration of node state dependencies and outputs.

    Contracts distinguish between mandatory inputs, optional inputs, guaranteed
    outputs, and optional outputs.
    """

    required_inputs: frozenset[str] = field(default_factory=frozenset)
    optional_inputs: frozenset[str] = field(default_factory=frozenset)
    guaranteed_outputs: frozenset[str] = field(default_factory=frozenset)
    optional_outputs: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        object.__setattr__(self, "required_inputs", frozenset(self.required_inputs))
        object.__setattr__(self, "optional_inputs", frozenset(self.optional_inputs))
        object.__setattr__(
            self, "guaranteed_outputs", frozenset(self.guaranteed_outputs)
        )
        object.__setattr__(self, "optional_outputs", frozenset(self.optional_outputs))

        input_overlap = self.required_inputs & self.optional_inputs
        if input_overlap:
            overlap_str = sorted(input_overlap)
            raise ValueError(
                f"Fields cannot be both required and optional inputs: {overlap_str}"
            )

        output_overlap = self.guaranteed_outputs & self.optional_outputs
        if output_overlap:
            overlap_str = sorted(output_overlap)
            raise ValueError(
                f"Fields cannot be both guaranteed and optional outputs: {overlap_str}"
            )

    @property
    def all_inputs(self) -> frozenset[str]:
        """All valid input fields (required + optional)."""
        return self.required_inputs | self.optional_inputs

    @property
    def all_outputs(self) -> frozenset[str]:
        """All possible output fields (guaranteed + optional)."""
        return self.guaranteed_outputs | self.optional_outputs

    def validate_inputs(
        self, available_fields: set[str] | frozenset[str] | Mapping[str, Any]
    ) -> list[str]:
        """Return a sorted list of missing required input field names.

        SEMANTICS:
        Performs a key-presence check only. Verifies whether required field names
        exist in the provided set or Mapping keys.
        A field present with value `None` is considered PRESENT at this contract
        level; validating non-null values, types, and domain preconditions belongs
        to downstream execution or validation layers.
        """
        provided = (
            set(available_fields.keys())
            if isinstance(available_fields, Mapping)
            else set(available_fields)
        )
        missing = sorted(self.required_inputs - provided)
        return missing

    def to_dict(self) -> dict[str, list[str]]:
        """Serialize contract to a JSON-compatible dictionary."""
        return {
            "required_inputs": sorted(self.required_inputs),
            "optional_inputs": sorted(self.optional_inputs),
            "guaranteed_outputs": sorted(self.guaranteed_outputs),
            "optional_outputs": sorted(self.optional_outputs),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NodeContract":
        """Deserialize contract from a dictionary representation."""
        return cls(
            required_inputs=frozenset(data.get("required_inputs", [])),
            optional_inputs=frozenset(data.get("optional_inputs", [])),
            guaranteed_outputs=frozenset(data.get("guaranteed_outputs", [])),
            optional_outputs=frozenset(data.get("optional_outputs", [])),
        )
