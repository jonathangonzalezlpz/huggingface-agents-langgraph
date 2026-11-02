"""LLM roles (planner, verifier, reflection, voting) and the verdict route."""

import json

import pytest

from huggingface_agents_langgraph import llm_roles
from huggingface_agents_langgraph.architecture_store import get_catalog
from huggingface_agents_langgraph.graph_definition import (
    AgentDefinition,
    EdgeDefinition,
    GraphCompiler,
    NodeDefinition,
)
from huggingface_agents_langgraph.graph_definition.registry import (
    create_studio_registry,
)
from huggingface_agents_langgraph.graph_definition.routing_registry import (
    create_studio_routing_registry,
)
from huggingface_agents_langgraph.graph_definition.validator import GraphValidator
from huggingface_agents_langgraph.state import AgentState

TASK = {"task_id": "t", "question": "What is 2+2?", "file_name": ""}


class FakeLLM:
    """Returns the queued replies in order and records every call."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        reply = self.replies.pop(0) if self.replies else self.replies_default
        return reply

    replies_default = "4"


@pytest.fixture
def fake(monkeypatch):
    def install(*replies):
        llm = FakeLLM(*replies)
        monkeypatch.setattr(llm_roles, "chat_completion", llm)
        return llm

    return install


def _user_text(call):
    return " ".join(m["content"] for m in call["messages"] if m["role"] == "user")


class TestState:
    def test_the_new_fields_are_optional_and_typed(self):
        annotations = AgentState.__annotations__
        for name in ("plan", "verdict", "candidates", "revision_count"):
            assert name in annotations
            assert name not in AgentState.__required_keys__


class TestPlanner:
    def test_it_asks_for_a_numbered_plan_and_stores_the_steps(self, fake):
        llm = fake("1. Add the numbers\n2. Check the sum\n- Report it")
        update = llm_roles.build_planner({"max_steps": 4, "max_tokens": 300})(TASK)
        assert update["plan"] == ["Add the numbers", "Check the sum", "Report it"]
        assert "Plan: Add the numbers" in update["research_notes"][-1]
        assert llm.calls[0]["max_tokens"] == 300
        assert "at most 4" in llm.calls[0]["messages"][0]["content"]

    def test_the_plan_is_cut_to_the_step_limit(self, fake):
        fake("\n".join(f"{n}. step {n}" for n in range(1, 9)))
        update = llm_roles.build_planner({"max_steps": 3, "max_tokens": 300})(TASK)
        assert update["plan"] == ["step 1", "step 2", "step 3"]

    def test_earlier_notes_are_kept(self, fake):
        fake("1. only step")
        state = TASK | {"research_notes": ["earlier"]}
        update = llm_roles.build_planner({"max_steps": 4, "max_tokens": 300})(state)
        assert update["research_notes"][0] == "earlier"

    def test_an_empty_reply_gives_an_empty_plan_not_an_error(self, fake):
        fake("   ")
        update = llm_roles.build_planner({"max_steps": 4, "max_tokens": 300})(TASK)
        assert update["plan"] == []


class TestVerifier:
    PARAMS = {"max_revisions": 1, "strictness": "strict", "max_tokens": 300}

    def _state(self, **extra):
        return TASK | {"draft_answer": "5"} | extra

    def test_it_accepts_when_the_model_says_so(self, fake):
        fake(json.dumps({"ok": True, "reason": "matches the evidence"}))
        update = llm_roles.build_verifier(self.PARAMS)(self._state())
        assert update["verdict"] == {
            "ok": True,
            "reason": "matches the evidence",
            "final": False,
        }

    def test_a_rejection_asks_for_a_revision_while_the_budget_lasts(self, fake):
        fake(json.dumps({"ok": False, "reason": "wrong sum"}))
        update = llm_roles.build_verifier(self.PARAMS)(self._state(revision_count=0))
        assert update["verdict"]["ok"] is False
        assert update["verdict"]["final"] is False

    def test_the_last_rejection_is_final_so_the_loop_ends(self, fake):
        fake(json.dumps({"ok": False, "reason": "still wrong"}))
        update = llm_roles.build_verifier(self.PARAMS)(self._state(revision_count=1))
        assert update["verdict"]["final"] is True

    def test_zero_revisions_means_a_single_check(self, fake):
        fake(json.dumps({"ok": False, "reason": "bad"}))
        params = self.PARAMS | {"max_revisions": 0}
        assert llm_roles.build_verifier(params)(self._state())["verdict"]["final"]

    def test_json_wrapped_in_prose_is_still_read(self, fake):
        fake('Sure! {"ok": false, "reason": "off by one"} Hope that helps.')
        update = llm_roles.build_verifier(self.PARAMS)(self._state())
        assert update["verdict"]["ok"] is False
        assert update["verdict"]["reason"] == "off by one"

    def test_an_unreadable_reply_accepts_instead_of_looping(self, fake):
        fake("I cannot decide.")
        update = llm_roles.build_verifier(self.PARAMS)(self._state())
        assert update["verdict"]["ok"] is True
        assert "unreadable" in update["verdict"]["reason"]

    def test_strictness_changes_the_instructions(self, fake):
        llm = fake('{"ok": true, "reason": ""}', '{"ok": true, "reason": ""}')
        llm_roles.build_verifier(self.PARAMS | {"strictness": "strict"})(self._state())
        llm_roles.build_verifier(self.PARAMS | {"strictness": "lenient"})(self._state())
        strict, lenient = (c["messages"][0]["content"] for c in llm.calls)
        assert strict != lenient

    def test_evidence_is_given_as_data(self, fake):
        llm = fake('{"ok": true, "reason": ""}')
        state = self._state(
            evidence=[{"content": "2+2=4", "source": "s", "source_type": "x"}]
        )
        llm_roles.build_verifier(self.PARAMS)(state)
        assert "2+2=4" in _user_text(llm.calls[0])
        assert "data" in llm.calls[0]["messages"][0]["content"].lower()


class TestReflection:
    PARAMS = {"max_tokens": 600, "thinking": False}

    def test_it_revises_the_draft_using_the_critique_and_counts_the_revision(
        self, fake
    ):
        llm = fake("The sum is 4.")
        state = TASK | {
            "draft_answer": "5",
            "verdict": {"ok": False, "reason": "wrong sum", "final": False},
            "revision_count": 1,
        }
        update = llm_roles.build_reflect(self.PARAMS)(state)
        assert update == {"draft_answer": "The sum is 4.", "revision_count": 2}
        text = _user_text(llm.calls[0])
        assert "wrong sum" in text and "5" in text

    def test_the_first_revision_starts_the_count_at_one(self, fake):
        fake("4")
        state = TASK | {"draft_answer": "5", "verdict": {"ok": False, "reason": "x"}}
        assert llm_roles.build_reflect(self.PARAMS)(state)["revision_count"] == 1


class TestSelfConsistency:
    PARAMS = {"n": 3, "temperature": 0.7, "max_tokens": 400}

    def test_the_majority_answer_wins(self, fake):
        llm = fake("Work.\nFINAL: 4", "Other.\nFINAL: five", "More.\nFINAL: 4")
        update = llm_roles.build_self_consistency(self.PARAMS)(TASK)
        assert update["draft_answer"].endswith("FINAL: 4")
        assert update["candidates"] == ["4", "five", "4"]
        assert len(llm.calls) == 3
        assert all(call["temperature"] == 0.7 for call in llm.calls)

    def test_votes_ignore_case_and_spacing(self, fake):
        fake("FINAL: Paris", "FINAL:  paris ", "FINAL: Lyon")
        update = llm_roles.build_self_consistency(self.PARAMS)(TASK)
        assert update["draft_answer"].lower().endswith("paris")

    def test_a_tie_keeps_the_first_answer(self, fake):
        fake("FINAL: a", "FINAL: b")
        update = llm_roles.build_self_consistency(self.PARAMS | {"n": 2})(TASK)
        assert update["draft_answer"].endswith("FINAL: a")

    def test_a_reply_without_a_final_line_counts_as_its_last_line(self, fake):
        fake("thinking\n42", "thinking\n42", "FINAL: 7")
        update = llm_roles.build_self_consistency(self.PARAMS)(TASK)
        assert update["candidates"][:2] == ["42", "42"]
        assert update["draft_answer"].endswith("42")

    def test_one_sample_is_just_one_call(self, fake):
        llm = fake("FINAL: 4")
        update = llm_roles.build_self_consistency(self.PARAMS | {"n": 1})(TASK)
        assert len(llm.calls) == 1
        assert update["candidates"] == ["4"]

    def test_it_stops_sampling_when_the_run_is_out_of_time(self, fake, monkeypatch):
        llm = fake("FINAL: 4", "FINAL: 4", "FINAL: 4")
        times = iter([100.0, 1.0])
        monkeypatch.setattr(llm_roles, "remaining_seconds", lambda: next(times))
        update = llm_roles.build_self_consistency(self.PARAMS)(TASK)
        assert len(llm.calls) == 2
        assert update["candidates"] == ["4", "4"]

    def test_failed_samples_are_skipped_if_one_succeeds(self, fake, monkeypatch):
        replies = iter([ValueError("boom"), "FINAL: 4", ValueError("boom")])

        def flaky(messages, **kwargs):
            reply = next(replies)
            if isinstance(reply, Exception):
                raise reply
            return reply

        monkeypatch.setattr(llm_roles, "chat_completion", flaky)
        update = llm_roles.build_self_consistency(self.PARAMS)(TASK)
        assert update["candidates"] == ["4"]

    def test_all_failing_raises_so_the_node_reports_it(self, monkeypatch):
        def broken(messages, **kwargs):
            raise ValueError("no model")

        monkeypatch.setattr(llm_roles, "chat_completion", broken)
        with pytest.raises(ValueError, match="no model"):
            llm_roles.build_self_consistency(self.PARAMS)(TASK)


class TestVerdictRoute:
    @pytest.mark.parametrize(
        ("verdict", "expected"),
        [
            (None, "accept"),
            ({"ok": True, "reason": "", "final": False}, "accept"),
            ({"ok": False, "reason": "x", "final": False}, "revise"),
            ({"ok": False, "reason": "x", "final": True}, "accept"),
        ],
    )
    def test_routes_by_verdict(self, verdict, expected):
        state = TASK | ({"verdict": verdict} if verdict is not None else {})
        assert llm_roles.route_on_verdict(state) == expected


def _loop_definition(max_revisions):
    """reasoning stub -> verifier -> (revise: reflect -> verifier | accept: end)."""
    return AgentDefinition(
        "4.0",
        "verify_loop",
        "AgentState",
        "draft",
        (
            NodeDefinition("draft", "reasoning"),
            NodeDefinition(
                "check",
                "llm_verifier",
                params={"max_revisions": max_revisions},
            ),
            NodeDefinition("fix", "llm_reflect"),
        ),
        (
            EdgeDefinition("draft", "check"),
            EdgeDefinition(
                "check",
                edge_type="conditional",
                routing_strategy="route_on_verdict",
                conditional_targets={"accept": "__end__", "revise": "fix"},
            ),
            EdgeDefinition("fix", "check"),
        ),
    )


class TestInAnArchitecture:
    def _compiler(self, monkeypatch):
        registry = create_studio_registry()
        monkeypatch.setattr(
            "huggingface_agents_langgraph.reasoning.chat_completion",
            lambda *a, **k: "5",
        )
        return GraphCompiler(registry, create_studio_routing_registry())

    def test_a_valid_loop_has_no_errors(self):
        report = GraphValidator(
            create_studio_registry(), create_studio_routing_registry()
        ).validate(_loop_definition(2))
        assert report.is_valid, [d.message for d in report.errors]

    def test_the_loop_corrects_a_wrong_draft_and_stops(self, fake, monkeypatch):
        compiler = self._compiler(monkeypatch)
        llm = fake(
            json.dumps({"ok": False, "reason": "wrong"}),
            "4",
            json.dumps({"ok": True, "reason": "right"}),
        )
        result = compiler.compile(_loop_definition(2)).invoke(dict(TASK))
        assert result["draft_answer"] == "4"
        assert result["revision_count"] == 1
        assert result["verdict"]["ok"] is True
        assert len(llm.calls) == 3

    def test_the_loop_ends_at_the_revision_budget_even_if_never_satisfied(
        self, fake, monkeypatch
    ):
        compiler = self._compiler(monkeypatch)
        bad = json.dumps({"ok": False, "reason": "no"})
        llm = fake(bad, "6", bad, "7", bad)
        result = compiler.compile(_loop_definition(2)).invoke(dict(TASK))
        assert result["revision_count"] == 2
        assert result["verdict"]["final"] is True
        assert len(llm.calls) == 5

    def test_the_catalog_lists_the_roles_with_their_parameters(self):
        catalog = get_catalog()
        nodes = {node["implementation_id"]: node for node in catalog["nodes"]}
        for name in ("llm_planner", "llm_verifier", "llm_reflect", "self_consistency"):
            assert name in nodes
            assert nodes[name]["params"], name
            assert nodes[name]["category"] in {"planning", "verification", "reasoning"}
        strategies = {s["identifier"]: s for s in catalog["routing_strategies"]}
        assert strategies["route_on_verdict"]["outputs"] == ["accept", "revise"]
        for field in ("plan", "verdict", "candidates", "revision_count"):
            assert field in catalog["state"]["fields"]

    def test_the_planner_feeds_the_next_node_through_the_notes(self, fake, monkeypatch):
        fake("1. Add\n2. Check")
        monkeypatch.setattr(
            "huggingface_agents_langgraph.reasoning.chat_completion",
            lambda *a, **k: "4",
        )
        definition = AgentDefinition(
            "4.0",
            "planned",
            "AgentState",
            "plan",
            (
                NodeDefinition("plan", "llm_planner"),
                NodeDefinition("solve", "reasoning"),
            ),
            (EdgeDefinition("plan", "solve"), EdgeDefinition("solve", "__end__")),
        )
        compiler = GraphCompiler(
            create_studio_registry(), create_studio_routing_registry()
        )
        result = compiler.compile(definition).invoke(dict(TASK))
        assert result["plan"] == ["Add", "Check"]
        assert result["draft_answer"] == "4"
