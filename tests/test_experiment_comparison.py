"""Structured, noise-aware comparison of persisted experiments."""

import json
from copy import deepcopy

import pytest

from huggingface_agents_langgraph.experiment_comparison import compare_experiments

BASE_CONFIG = {
    "name": "run",
    "pipeline_version": "3.1",
    "model": None,
    "improvements": ["answer_contract"],
    "seed": 42,
}


def _answer(task_id, correct=True, seconds=10.0, route="web", error=None, text="x"):
    return {
        "task_id": task_id,
        "locally_correct": correct,
        "duration_seconds": seconds,
        "route": route,
        "error": error,
        "submitted_answer": text,
        "truncated_calls": 0,
    }


def _record(record_id, answers=None, config=None, source="code-a", **extra):
    answers = answers if answers is not None else [_answer("t1"), _answer("t2")]
    record = {
        "id": record_id,
        "created_at": "2026-11-01T00:00:00+00:00",
        "config": deepcopy(config or BASE_CONFIG),
        "answers": answers,
        "status": "completed",
        "total_questions": len(answers),
        "source_identity": {"git_revision": "r", "source_sha256": source},
    }
    record.update(extra)
    return record


def _by_id(comparison, record_id):
    return next(e for e in comparison["experiments"] if e["id"] == record_id)


class TestComparability:
    def test_identical_setups_are_comparable(self):
        result = compare_experiments([_record("a"), _record("b")])
        comparability = result["comparability"]
        assert comparability["same_task_set"] is True
        assert comparability["same_code"] is True
        assert comparability["config_differences"] == {}
        assert comparability["warnings"] == []

    def test_config_differences_exclude_the_name(self):
        other = deepcopy(BASE_CONFIG) | {"name": "other", "model": "m", "seed": 7}
        result = compare_experiments([_record("a"), _record("b", config=other)])
        differences = result["comparability"]["config_differences"]
        assert set(differences) == {"model", "seed"}
        assert differences["seed"] == {"a": 42, "b": 7}

    def test_architecture_differences_are_reported(self):
        other = BASE_CONFIG | {"architecture": "builtin:gaia_v31"}
        result = compare_experiments([_record("a"), _record("b", config=other)])
        assert result["comparability"]["same_architecture"] is False
        assert "architecture" in result["comparability"]["config_differences"]

    def test_task_order_does_not_matter(self):
        forward = [_answer("t1"), _answer("t2")]
        result = compare_experiments(
            [_record("a", forward), _record("b", list(reversed(forward)))]
        )
        assert result["comparability"]["same_task_set"] is True

    def test_different_task_sets_are_flagged(self):
        result = compare_experiments(
            [_record("a"), _record("b", [_answer("t1"), _answer("t3")])]
        )
        assert result["comparability"]["same_task_set"] is False
        assert any("task set" in w for w in result["comparability"]["warnings"])

    def test_recorded_task_set_hash_is_used_when_present(self):
        a = _record("a", task_set_sha256="h1")
        b = _record("b", task_set_sha256="h2")
        assert compare_experiments([a, b])["comparability"]["same_task_set"] is False

    def test_different_code_is_flagged(self):
        result = compare_experiments([_record("a"), _record("b", source="code-b")])
        assert result["comparability"]["same_code"] is False
        assert any("code" in w for w in result["comparability"]["warnings"])

    def test_unknown_code_identity_is_not_assumed_equal(self):
        legacy = _record("b")
        del legacy["source_identity"]
        result = compare_experiments([_record("a"), legacy])
        assert result["comparability"]["same_code"] is None
        assert any("unknown" in w for w in result["comparability"]["warnings"])

    def test_partial_runs_are_flagged(self):
        partial = _record("b", status="cancelled", total_questions=20)
        result = compare_experiments([_record("a"), partial])
        assert any("partial" in w for w in result["comparability"]["warnings"])


class TestMetrics:
    def test_accuracy_latency_and_errors(self):
        answers = [
            _answer("t1", True, 10),
            _answer("t2", False, 20, error="boom"),
            _answer("t3", True, 30),
            _answer("t4", False, 40),
        ]
        result = compare_experiments([_record("a", answers), _record("b", answers)])
        metrics = _by_id(result, "a")["metrics"]
        assert metrics["answered"] == 4
        assert metrics["correct"] == 2
        assert metrics["accuracy"] == 0.5
        assert metrics["mean_seconds"] == 25
        assert metrics["median_seconds"] == 25
        assert metrics["technical_errors"] == 1

    def test_accuracy_falls_back_to_the_stored_local_score(self):
        answers = [_answer("t1", None), _answer("t2", None)]
        record = _record(
            "a",
            answers,
            local_score={"correct_count": 1, "total_attempted": 2, "score": 50},
        )
        result = compare_experiments([record, _record("b")])
        assert _by_id(result, "a")["metrics"]["accuracy"] == 0.5

    def test_unscored_runs_have_no_accuracy(self):
        record = _record("a", [_answer("t1", None)])
        result = compare_experiments([record, _record("b")])
        assert _by_id(result, "a")["metrics"]["accuracy"] is None


class TestReplicateGroups:
    def _runs(self, prefix, corrects, config=None):
        return [
            _record(
                f"{prefix}{i}",
                [_answer("t1", c), _answer("t2", True)],
                config=config,
            )
            for i, c in enumerate(corrects)
        ]

    def test_same_setup_runs_form_one_group_with_a_range(self):
        runs = self._runs("a", [True, False, True])
        other = _record("b", config=BASE_CONFIG | {"seed": 1})
        result = compare_experiments([*runs, other])
        group = next(g for g in result["groups"] if len(g["experiment_ids"]) == 3)
        assert group["runs"] == 3
        assert group["accuracy"] == {
            "min": 0.5,
            "max": 1.0,
            "mean": pytest.approx(0.8333, abs=1e-3),
        }
        assert group["noise_estimate"] == "observed_range"

    def test_single_run_has_no_noise_estimate(self):
        result = compare_experiments([_record("a"), _record("b", source="code-b")])
        assert {g["noise_estimate"] for g in result["groups"]} == {"none"}

    def test_different_config_or_code_never_merge(self):
        other = BASE_CONFIG | {"seed": 1}
        result = compare_experiments(
            [_record("a"), _record("b", config=other), _record("c", source="z")]
        )
        assert len(result["groups"]) == 3

    def test_difference_is_assessable_only_with_repeated_runs_on_both_sides(self):
        base = self._runs("a", [True, True])
        other = self._runs("b", [False, False], config=BASE_CONFIG | {"seed": 1})
        result = compare_experiments([*base, *other])
        verdict = result["groups"][1]["versus_base"]["accuracy_difference"]
        assert verdict["assessment"] == "outside_observed_range"
        assert verdict["delta"] == pytest.approx(-0.5)

    def test_overlapping_ranges_are_within_noise(self):
        base = self._runs("a", [True, False])
        other = self._runs("b", [False, True], config=BASE_CONFIG | {"seed": 1})
        result = compare_experiments([*base, *other])
        verdict = result["groups"][1]["versus_base"]["accuracy_difference"]
        assert verdict["assessment"] == "within_observed_range"

    def test_single_runs_are_not_assessable(self):
        result = compare_experiments(
            [_record("a"), _record("b", config=BASE_CONFIG | {"seed": 1})]
        )
        verdict = result["groups"][1]["versus_base"]["accuracy_difference"]
        assert verdict["assessment"] == "not_assessable"


class TestTaskAlignment:
    def test_gained_and_lost_tasks_against_the_base(self):
        base = _record("a", [_answer("t1", True), _answer("t2", False), _answer("t3")])
        other = _record(
            "b",
            [_answer("t1", False), _answer("t2", True), _answer("t3")],
            config=BASE_CONFIG | {"seed": 1},
        )
        result = compare_experiments([base, other])
        tasks = {t["task_id"]: t for t in result["tasks"]}
        assert tasks["t1"]["outcomes"]["b"]["versus_base"] == "lost"
        assert tasks["t2"]["outcomes"]["b"]["versus_base"] == "gained"
        assert tasks["t3"]["outcomes"]["b"]["versus_base"] == "unchanged"
        summary = result["groups"][1]["versus_base"]
        assert (summary["gained"], summary["lost"], summary["unchanged"]) == (1, 1, 1)

    def test_only_common_tasks_are_aligned(self):
        result = compare_experiments(
            [_record("a"), _record("b", [_answer("t1"), _answer("t9")])]
        )
        assert [t["task_id"] for t in result["tasks"]] == ["t1"]

    def test_explicit_base_selects_the_reference_group(self):
        a = _record("a")
        b = _record("b", config=BASE_CONFIG | {"seed": 1})
        result = compare_experiments([a, b], base_id="b")
        assert result["base_group"] == next(
            g["key"] for g in result["groups"] if "b" in g["experiment_ids"]
        )

    def test_unknown_base_is_rejected(self):
        with pytest.raises(ValueError, match="base"):
            compare_experiments([_record("a"), _record("b")], base_id="zzz")

    def test_answers_matching_the_base_are_reported_without_exposing_text(self):
        a = _record("a", [_answer("t1", text="SECRET-ONE")])
        b = _record(
            "b", [_answer("t1", text="SECRET-TWO")], config=BASE_CONFIG | {"seed": 1}
        )
        result = compare_experiments([a, b])
        assert result["tasks"][0]["outcomes"]["b"]["same_answer_as_base"] is False
        assert "SECRET" not in json.dumps(result)


def test_at_least_two_experiments_are_required():
    with pytest.raises(ValueError, match="at least two"):
        compare_experiments([_record("a")])


def test_result_is_json_serializable():
    json.dumps(compare_experiments([_record("a"), _record("b")]))
