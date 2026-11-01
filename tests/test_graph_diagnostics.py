"""Tests for structured validation diagnostics."""

import pytest

from huggingface_agents_langgraph.graph_definition.diagnostics import (
    Diagnostic,
    ValidationReport,
)


def _diagnostic(severity="error", code="X", **kwargs):
    return Diagnostic(code=code, severity=severity, message="msg", **kwargs)


class TestDiagnostic:
    def test_rejects_unknown_severity(self):
        with pytest.raises(ValueError, match="severity"):
            _diagnostic(severity="fatal")

    def test_rejects_empty_code(self):
        with pytest.raises(ValueError, match="code"):
            _diagnostic(code=" ")

    def test_details_are_immutable_and_copied(self):
        source = {"paths": ["a", "b"]}
        diagnostic = _diagnostic(details=source)
        source["paths"].append("c")
        assert list(diagnostic.details["paths"]) == ["a", "b"]
        with pytest.raises(TypeError):
            diagnostic.details["x"] = 1  # type: ignore

    def test_to_dict_is_json_friendly_and_omits_unset_locations(self):
        diagnostic = _diagnostic(node_id="n1", details={"fields": ["f"]})
        assert diagnostic.to_dict() == {
            "code": "X",
            "severity": "error",
            "message": "msg",
            "node_id": "n1",
            "details": {"fields": ["f"]},
        }

    def test_to_dict_includes_edge_location(self):
        data = _diagnostic(edge_source="a", branch="act").to_dict()
        assert data["edge_source"] == "a"
        assert data["branch"] == "act"


class TestValidationReport:
    def test_valid_without_errors(self):
        report = ValidationReport(
            diagnostics=(_diagnostic("warning"), _diagnostic("info"))
        )
        assert report.is_valid
        assert len(report.warnings) == 1
        assert report.errors == ()

    def test_invalid_with_errors(self):
        report = ValidationReport(diagnostics=(_diagnostic("error"),))
        assert not report.is_valid
        assert len(report.errors) == 1

    def test_empty_report_is_valid(self):
        assert ValidationReport(diagnostics=()).is_valid

    def test_to_dict_summarizes_counts(self):
        report = ValidationReport(
            diagnostics=(_diagnostic("error"), _diagnostic("warning"))
        )
        data = report.to_dict()
        assert data["is_valid"] is False
        assert data["counts"] == {"error": 1, "warning": 1, "info": 0}
        assert len(data["diagnostics"]) == 2
