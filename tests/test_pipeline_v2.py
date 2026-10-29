import json
from io import BytesIO

import pytest

from huggingface_agents_langgraph import answer_production as formatting
from huggingface_agents_langgraph import graph as graph_module
from huggingface_agents_langgraph import llm, research, run_tracking
from huggingface_agents_langgraph.calculation import calculate, validate_expression
from huggingface_agents_langgraph.experiments import normalize_experiment


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os')",
        "(1).__class__",
        "open('secret')",
        "[x for x in range(4) if x.__class__]",
        "2 ** 100",
        "sum([1], start=3)",
    ],
)
def test_calculator_rejects_non_calculation_syntax(expression):
    with pytest.raises(ValueError):
        validate_expression(expression)


def test_calculator_handles_table_comparison_and_aggregation():
    assert calculate("sum([1.25, 2.75])") == "4.0"
    assert json.loads(
        calculate(
            "sorted({i for i in range(2) for j in range(2) "
            "if [[1,2],[3,4]][i][j] != [[1,2],[3,4]][j][i]})"
        )
    ) == [0, 1]


def test_formatter_repairs_invalid_output(monkeypatch):
    replies = iter(["zebra, apple", "apple, zebra"])
    monkeypatch.setattr(formatting, "chat_completion", lambda *_a, **_k: next(replies))
    result = formatting.answer_production(
        {
            "question": "Return a comma separated list alphabetically.",
            "draft_answer": "zebra and apple",
        }
    )
    assert result["submitted_answer"] == "apple, zebra"


def test_formatter_rejects_unrepaired_invalid_move(monkeypatch):
    monkeypatch.setattr(formatting, "chat_completion", lambda *_a, **_k: "He f.")
    with pytest.raises(ValueError, match="validation"):
        formatting.answer_production(
            {"question": "Give the move in algebraic notation."}
        )


def test_review_never_calls_tools_in_direct_experiment(monkeypatch):
    def unexpected(*_a, **_k):
        raise AssertionError("Direct mode must not plan tool calls")

    monkeypatch.setattr(research, "chat_completion", unexpected)
    result = research.review(
        {
            "question": "Compute 2+2.",
            "experiment": normalize_experiment({"force_direct": True}),
        }
    )
    assert result["research_action"]["action"] == "finish"


def test_review_stops_at_action_budget(monkeypatch):
    monkeypatch.setattr(research, "PIPELINE_MAX_ACTIONS", 1)
    result = research.review({"question": "Question", "research_steps": 1})
    assert result["research_action"]["action"] == "finish"


def test_review_rejects_disabled_tools_and_retries(monkeypatch):
    replies = iter(['{"action":"search","query":"something"}', '{"action":"finish"}'])
    monkeypatch.setattr(research, "chat_completion", lambda *_a, **_k: next(replies))
    state = {
        "question": "Question",
        "experiment": normalize_experiment({"enabled_capabilities": ["code"]}),
    }
    assert research.review(state)["research_action"] == {"action": "finish"}
    with pytest.raises(ValueError, match="disabled"):
        research.research_action(
            state | {"research_action": {"action": "search", "query": "x"}}
        )


def test_review_stops_repeated_action(monkeypatch):
    action = {"action": "calculate", "expression": "2+2"}
    monkeypatch.setattr(
        research, "chat_completion", lambda *_a, **_k: json.dumps(action)
    )
    state = {
        "question": "Question",
        "action_history": [json.dumps(action, sort_keys=True)],
    }
    result = research.review(state)
    assert result["research_action"]["action"] == "finish"
    assert result["research_notes"]


def test_tool_failure_preserves_evidence_and_consumes_budget():
    evidence = [
        {"content": "Prior fact", "source": "example", "source_type": "web_page"}
    ]
    result = research.research_action(
        {
            "question": "Question",
            "evidence": evidence,
            "research_action": {"action": "calculate", "expression": "open('secret')"},
        }
    )
    assert result["evidence"] == evidence
    assert result["research_steps"] == 1
    assert result["research_notes"]


def test_graph_chains_tools_and_accumulates_evidence(monkeypatch):
    monkeypatch.setattr(graph_module, "router", lambda _s: {"route": "direct"})
    monkeypatch.setattr(
        graph_module,
        "review",
        lambda s: {
            "research_action": {"action": "finish"}
            if s.get("research_steps", 0)
            else {"action": "calculate", "expression": "2+2"}
        },
    )
    monkeypatch.setattr(
        graph_module,
        "reasoning",
        lambda s: {"draft_answer": s["evidence"][0]["content"]},
    )
    monkeypatch.setattr(
        graph_module,
        "answer_production",
        lambda s: {"submitted_answer": s["draft_answer"]},
    )
    result = graph_module.build_state_graph().invoke(
        {"task_id": "test", "question": "Compute", "file_name": ""}
    )
    assert result["submitted_answer"] == "4"
    assert result["research_steps"] == 1


def test_run_persists_failure_and_restores_context(monkeypatch, tmp_path):
    monkeypatch.setattr(run_tracking, "RUNTIME_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(
        graph_module,
        "router",
        lambda _s: (_ for _ in ()).throw(ValueError("bad route")),
    )
    with pytest.raises(ValueError) as captured:
        run_tracking.run_pipeline(
            {"task_id": "test", "question": "Question", "file_name": ""}
        )
    record = run_tracking.read_record("runs", captured.value.run_id)
    assert record["error"] == "bad route"
    assert record["steps"][-1]["error"] == "bad route"
    assert run_tracking.current_trace.get() is None
    with pytest.raises(ValueError):
        run_tracking.read_record("runs", "../secret")


def test_llm_records_truncation_and_usage(monkeypatch):
    class Response(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    payload = {
        "model": "example",
        "usage": {"completion_tokens": 4},
        "choices": [{"finish_reason": "length", "message": {"content": "partial"}}],
    }
    monkeypatch.setattr(
        llm, "urlopen", lambda *_a, **_k: Response(json.dumps(payload).encode())
    )
    trace = run_tracking.RunTrace()
    token = run_tracking.current_trace.set(trace)
    try:
        with pytest.raises(ValueError, match="truncated"):
            llm.chat_completion([{"role": "user", "content": "Question"}], max_tokens=4)
        assert trace.calls[0]["response"]["usage"]["completion_tokens"] == 4
        assert trace.calls[0]["duration_seconds"] >= 0
    finally:
        run_tracking.current_trace.reset(token)


def test_call_budget_stops_before_model_request(monkeypatch):
    monkeypatch.setattr(run_tracking, "PIPELINE_MAX_LLM_CALLS", 1)
    trace = run_tracking.RunTrace(calls=[{"duration_seconds": 0.0}])
    token = run_tracking.current_trace.set(trace)
    try:
        with pytest.raises(RuntimeError, match="budget"):
            llm.chat_completion([{"role": "user", "content": "Question"}])
        assert len(trace.calls) == 1
    finally:
        run_tracking.current_trace.reset(token)


def test_local_history_api_preserves_and_deletes_selected_record(monkeypatch, tmp_path):
    from io import BytesIO
    from uuid import uuid4

    from huggingface_agents_langgraph.web_app import WebAppHandler

    monkeypatch.setattr(run_tracking, "RUNTIME_DIRECTORY", str(tmp_path))
    record = {"id": str(uuid4()), "created_at": "2026-10-29", "answers": []}
    body = json.dumps(record).encode()
    handler = WebAppHandler.__new__(WebAppHandler)
    responses = []
    handler._send_json = lambda status, payload: responses.append((status, payload))
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = BytesIO(body)
    handler.path = "/api/experiments"
    handler.do_POST()
    assert responses[-1][0] == 200
    handler.do_GET()
    assert responses[-1][1]["experiments"] == [record]
    handler.path = "/api/experiments/" + record["id"]
    handler.do_DELETE()
    assert responses[-1][1] == {"deleted": True}
    assert run_tracking.list_records("experiments") == []


def test_html_fetch_exposes_paper_links_without_losing_page_text(monkeypatch):
    from email.message import Message

    from huggingface_agents_langgraph import web_research

    class Response(BytesIO):
        headers = Message()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

        def geturl(self):
            return "https://example.org/article"

    html = b'<p>Observations.</p><a href="https://arxiv.org/pdf/1234">Paper</a>'
    monkeypatch.setattr(web_research, "urlopen", lambda *_a, **_k: Response(html))
    evidence = web_research.fetch_source("https://example.org/article")
    assert "Observations." in evidence[0]["content"]
    assert evidence[0]["links"] == ["https://arxiv.org/pdf/1234"]


def test_reasoning_recovers_once_from_exhausted_thinking_budget(monkeypatch):
    from huggingface_agents_langgraph import reasoning
    from huggingface_agents_langgraph.llm import CompletionTruncatedError

    calls = []

    def reply(messages, **kwargs):
        calls.append(list(messages))
        if len(calls) == 1:
            raise CompletionTruncatedError("truncated")
        return "Verified result: 25.0"

    monkeypatch.setattr(reasoning, "chat_completion", reply)
    result = reasoning.reasoning({"question": "Compute the total", "evidence": []})
    assert result["draft_answer"] == "Verified result: 25.0"
    assert result["reasoning_warnings"]
    assert "/no_think" not in calls[0][-1]["content"]
    assert calls[1][-1]["content"].endswith("/no_think")
    assert len(calls) == 2
