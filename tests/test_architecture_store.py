"""Tests for immutable, versioned persistence of agent definitions."""

from dataclasses import replace
from uuid import UUID

import pytest

from huggingface_agents_langgraph import run_tracking
from huggingface_agents_langgraph.architecture_store import (
    BUILTIN_V31_ID,
    ArchitectureNotFoundError,
    content_sha256,
    get_architecture,
    get_layout,
    list_architectures,
    save_architecture,
    save_layout,
    validate_definition,
)
from huggingface_agents_langgraph.graph_definition import (
    AgentDefinition,
    EdgeDefinition,
    NodeDefinition,
)
from huggingface_agents_langgraph.graph_definition.definitions import (
    create_gaia_v31_definition,
)


@pytest.fixture(autouse=True)
def runtime_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(run_tracking, "RUNTIME_DIRECTORY", str(tmp_path))


def _definition(architecture_id="demo", targets=("a", "b")) -> AgentDefinition:
    nodes = tuple(
        NodeDefinition(id=name, implementation_id="preprocessing") for name in targets
    )
    edges = tuple(
        EdgeDefinition(source=src, target=dst)
        for src, dst in zip(targets, (*targets[1:], "__end__"), strict=True)
    )
    return AgentDefinition(
        schema_version="4.0",
        architecture_id=architecture_id,
        state_type="AgentState",
        initial_node=targets[0],
        nodes=nodes,
        edges=edges,
    )


class TestContentHash:
    def test_is_stable_for_equal_definitions(self):
        assert content_sha256(_definition()) == content_sha256(_definition())

    def test_changes_with_content(self):
        assert content_sha256(_definition()) != content_sha256(
            _definition(targets=("a", "b", "c"))
        )

    def test_survives_a_serialization_round_trip(self):
        definition = create_gaia_v31_definition()
        restored = AgentDefinition.from_dict(definition.to_dict())
        assert content_sha256(restored) == content_sha256(definition)


class TestSave:
    def test_first_save_creates_version_one_without_parent(self):
        record = save_architecture(_definition())
        assert record["version"] == 1
        assert record["parent_id"] is None
        assert record["architecture_id"] == "demo"
        assert record["content_sha256"] == content_sha256(_definition())
        assert UUID(record["id"])

    def test_saving_identical_content_is_idempotent(self):
        first = save_architecture(_definition())
        second = save_architecture(_definition())
        assert second == first
        assert len(list_architectures()) == 2  # saved version plus built-in

    def test_new_content_creates_the_next_version_with_a_parent(self):
        first = save_architecture(_definition())
        second = save_architecture(_definition(targets=("a", "b", "c")))
        assert second["version"] == 2
        assert second["parent_id"] == first["id"]

    def test_resaving_an_older_version_does_not_create_a_new_one(self):
        first = save_architecture(_definition())
        save_architecture(_definition(targets=("a", "b", "c")))
        assert save_architecture(_definition()) == first

    def test_versions_are_numbered_per_architecture(self):
        save_architecture(_definition("one"))
        other = save_architecture(_definition("two"))
        assert other["version"] == 1
        assert other["parent_id"] is None

    def test_invalid_drafts_are_stored(self):
        draft = replace(_definition(), edges=())
        assert save_architecture(draft)["version"] == 1

    def test_builtin_identifier_cannot_be_shadowed(self):
        with pytest.raises(ValueError, match="reserved"):
            save_architecture(replace(_definition(), architecture_id="gaia_v31"))


class TestRead:
    def test_get_returns_the_saved_record(self):
        saved = save_architecture(_definition())
        record = get_architecture(saved["id"])
        assert record["definition"] == _definition().to_dict()
        assert AgentDefinition.from_dict(record["definition"]) == _definition()

    def test_unknown_or_malformed_ids_raise_not_found(self):
        with pytest.raises(ArchitectureNotFoundError):
            get_architecture("00000000-0000-0000-0000-000000000000")
        with pytest.raises(ArchitectureNotFoundError):
            get_architecture("not-a-uuid")

    def test_listing_is_summarized_and_ordered_by_version(self):
        save_architecture(_definition())
        save_architecture(_definition(targets=("a", "b", "c")))
        saved = [s for s in list_architectures() if not s["read_only"]]
        assert [s["version"] for s in saved] == [1, 2]
        assert all("definition" not in s for s in saved)

    def test_builtin_v31_is_listed_and_readable_but_not_persisted(self, tmp_path):
        builtin = [s for s in list_architectures() if s["read_only"]]
        assert [s["id"] for s in builtin] == [BUILTIN_V31_ID]
        assert builtin[0]["content_sha256"] == content_sha256(
            create_gaia_v31_definition()
        )
        record = get_architecture(BUILTIN_V31_ID)
        assert record["read_only"] is True
        assert record["definition"] == create_gaia_v31_definition().to_dict()
        assert not (tmp_path / "architectures").exists()


class TestValidate:
    def test_valid_builtin_has_no_errors(self):
        report = validate_definition(create_gaia_v31_definition().to_dict())
        assert report["is_valid"] is True
        assert report["counts"]["error"] == 0

    def test_semantic_errors_are_reported(self):
        payload = replace(_definition(), edges=()).to_dict()
        report = validate_definition(payload)
        assert report["is_valid"] is False
        assert "NO_PATH_TO_END" in {d["code"] for d in report["diagnostics"]}

    def test_unconstructible_payload_reports_a_structural_error(self):
        report = validate_definition({"schema_version": "4.0"})
        assert report["is_valid"] is False
        assert report["diagnostics"][0]["code"] == "INVALID_DEFINITION"


class TestLayout:
    def _saved(self):
        return save_architecture(_definition())

    def test_defaults_to_an_empty_layout(self):
        layout = get_layout(self._saved()["id"])
        assert layout["layout"] == {"nodes": {}}
        assert layout["updated_at"] is None

    def test_round_trip_and_overwrite(self):
        version_id = self._saved()["id"]
        save_layout(version_id, {"nodes": {"a": {"x": 1.5, "y": -2}}})
        save_layout(
            version_id, {"nodes": {"a": {"x": 10, "y": 20}, "b": {"x": 0, "y": 0}}}
        )
        stored = get_layout(version_id)
        assert stored["layout"]["nodes"]["a"] == {"x": 10, "y": 20}
        assert set(stored["layout"]["nodes"]) == {"a", "b"}
        assert stored["updated_at"]

    def test_moving_nodes_never_changes_the_version(self):
        saved = self._saved()
        save_layout(saved["id"], {"nodes": {"a": {"x": 5, "y": 5}}})
        assert save_architecture(_definition()) == saved
        assert (
            get_architecture(saved["id"])["content_sha256"] == saved["content_sha256"]
        )

    def test_builtin_layout_can_be_stored_without_persisting_the_definition(
        self, tmp_path
    ):
        save_layout(BUILTIN_V31_ID, {"nodes": {"router": {"x": 3, "y": 4}}})
        assert get_layout(BUILTIN_V31_ID)["layout"]["nodes"]["router"] == {
            "x": 3,
            "y": 4,
        }
        assert not (tmp_path / "architectures").exists()

    def test_unknown_version_is_not_found(self):
        with pytest.raises(ArchitectureNotFoundError):
            get_layout("00000000-0000-0000-0000-000000000000")
        with pytest.raises(ArchitectureNotFoundError):
            save_layout("nope", {"nodes": {}})

    @pytest.mark.parametrize(
        "layout",
        [
            [],
            {},
            {"nodes": []},
            {"nodes": {"a": {"x": 1}}},
            {"nodes": {"a": {"x": 1, "y": 2, "z": 3}}},
            {"nodes": {"a": {"x": "1", "y": 2}}},
            {"nodes": {"a": {"x": True, "y": 2}}},
            {"nodes": {"a": {"x": float("nan"), "y": 2}}},
            {"nodes": {"a": {"x": float("inf"), "y": 2}}},
            {"nodes": {"a": {"x": 10**7, "y": 2}}},
            {"nodes": {"ghost": {"x": 1, "y": 2}}},
            {"nodes": {"a": {"x": 1, "y": 2}}, "extra": 1},
        ],
    )
    def test_invalid_layouts_are_rejected(self, layout):
        with pytest.raises(ValueError, match="layout"):
            save_layout(self._saved()["id"], layout)
