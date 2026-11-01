"""Tool registry and the components built on it (no network, no models)."""

import json

import pytest

from huggingface_agents_langgraph import tool_components, tool_library
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

TASK = {"task_id": "t", "question": "Who wrote Hamlet?", "file_name": ""}


def evidence(content, source="https://example.org", kind="web", links=None):
    item = {"content": content, "source": source, "source_type": kind}
    if links is not None:
        item["links"] = links
    return item


@pytest.fixture(autouse=True)
def passthrough_selection(monkeypatch):
    """Keep every item: relevance ranking is tested elsewhere."""
    monkeypatch.setattr(
        tool_components, "select_relevant_evidence", lambda question, items: items
    )


class TestToolLibrary:
    def test_the_registry_lists_the_vetted_tools_with_their_flags(self):
        tools = tool_library.TOOLS
        assert set(tools) == {"web_search", "wikipedia", "fetch_url", "calculate"}
        assert tools["web_search"].network is True
        assert tools["fetch_url"].network is True
        assert tools["calculate"].network is False
        assert all(spec.description for spec in tools.values())

    def test_each_tool_is_a_langchain_structured_tool(self):
        from langchain_core.tools import BaseTool

        for spec in tool_library.TOOLS.values():
            tool = tool_library.as_langchain_tool(spec)
            assert isinstance(tool, BaseTool)
            assert tool.name == spec.id
            assert tool.description == spec.description

    def test_running_a_tool_returns_evidence(self, monkeypatch):
        monkeypatch.setattr(
            tool_library, "_search_web", lambda text: [evidence(f"hit for {text}")]
        )
        result = tool_library.run_tool("web_search", "hamlet")
        assert result == [evidence("hit for hamlet")]

    def test_the_calculator_wraps_its_result_as_evidence(self, monkeypatch):
        monkeypatch.setattr(tool_library, "calculate", lambda expression: "391")
        result = tool_library.run_tool("calculate", "17*23")
        assert result == [
            {"content": "391", "source": "17*23", "source_type": "calculation"}
        ]

    def test_an_unknown_tool_is_refused(self):
        with pytest.raises(KeyError):
            tool_library.run_tool("rm_rf", "x")


class TestToolNode:
    PARAMS = {"tool": "web_search", "input_from": "question", "text": ""}

    def _run(self, params, state, monkeypatch, result=None):
        calls = []

        def fake(tool, text):
            calls.append((tool, text))
            return result if result is not None else [evidence("found")]

        monkeypatch.setattr(tool_components, "run_tool", fake)
        update = tool_components.build_tool_node(params)(state)
        return update, calls

    def test_it_feeds_the_question_by_default(self, monkeypatch):
        update, calls = self._run(self.PARAMS, dict(TASK), monkeypatch)
        assert calls == [("web_search", "Who wrote Hamlet?")]
        assert update["evidence"] == [evidence("found")]

    def test_it_can_feed_the_draft_answer_or_a_fixed_text(self, monkeypatch):
        _, calls = self._run(
            self.PARAMS | {"input_from": "draft_answer"},
            TASK | {"draft_answer": "Shakespeare"},
            monkeypatch,
        )
        assert calls == [("web_search", "Shakespeare")]
        _, calls = self._run(
            self.PARAMS | {"input_from": "text", "text": "hamlet author"},
            dict(TASK),
            monkeypatch,
        )
        assert calls == [("web_search", "hamlet author")]

    def test_a_missing_input_is_an_error_not_a_silent_empty_call(self, monkeypatch):
        with pytest.raises(ValueError, match="draft_answer"):
            self._run(
                self.PARAMS | {"input_from": "draft_answer"}, dict(TASK), monkeypatch
            )
        with pytest.raises(ValueError, match="text"):
            self._run(self.PARAMS | {"input_from": "text"}, dict(TASK), monkeypatch)

    def test_new_evidence_is_added_to_what_was_gathered(self, monkeypatch):
        state = TASK | {"evidence": [evidence("earlier")]}
        update, _ = self._run(self.PARAMS, state, monkeypatch)
        assert [item["content"] for item in update["evidence"]] == ["earlier", "found"]

    def test_links_move_to_the_source_links_without_duplicates(self, monkeypatch):
        state = TASK | {"source_links": ["https://a"]}
        result = [evidence("page", links=["https://a", "https://b"])]
        update, _ = self._run(self.PARAMS, state, monkeypatch, result)
        assert update["source_links"] == ["https://a", "https://b"]
        assert "links" not in update["evidence"][0]

    def test_no_results_leave_a_note(self, monkeypatch):
        update, _ = self._run(self.PARAMS, dict(TASK), monkeypatch, result=[])
        assert any("web_search" in note for note in update["research_notes"])
        assert "evidence" not in update or update["evidence"] == []

    def test_an_unknown_tool_is_refused_at_build_time(self):
        with pytest.raises(ValueError):
            tool_components.build_tool_node(self.PARAMS | {"tool": "nope"})


class TestNamedTools:
    def test_web_search_uses_the_question_or_its_own_query(self, monkeypatch):
        seen = []
        monkeypatch.setattr(
            tool_components,
            "run_tool",
            lambda tool, text: seen.append((tool, text)) or [evidence("x")],
        )
        tool_components.build_web_search({"query": ""})(dict(TASK))
        tool_components.build_web_search({"query": "shakespeare plays"})(dict(TASK))
        assert seen == [
            ("web_search", "Who wrote Hamlet?"),
            ("web_search", "shakespeare plays"),
        ]

    def test_wikipedia_search_uses_the_wikipedia_tool(self, monkeypatch):
        seen = []
        monkeypatch.setattr(
            tool_components,
            "run_tool",
            lambda tool, text: seen.append(tool) or [evidence("x")],
        )
        tool_components.build_wikipedia_search({"query": ""})(dict(TASK))
        assert seen == ["wikipedia"]

    def test_the_calculator_asks_the_model_for_one_expression_and_evaluates_it(
        self, monkeypatch
    ):
        asked = []
        monkeypatch.setattr(
            tool_components,
            "chat_completion",
            lambda messages, **kwargs: asked.append(messages) or "```\n17 * 23\n```",
        )
        seen = []
        monkeypatch.setattr(
            tool_components,
            "run_tool",
            lambda tool, text: (
                seen.append((tool, text))
                or [{"content": "391", "source": text, "source_type": "calculation"}]
            ),
        )
        update = tool_components.build_calculator({"max_tokens": 200})(
            TASK | {"question": "What is 17 times 23?"}
        )
        assert seen == [("calculate", "17 * 23")]
        assert update["evidence"][0]["content"] == "391"
        assert "What is 17 times 23?" in asked[0][-1]["content"]

    def test_the_calculator_refuses_an_empty_expression(self, monkeypatch):
        monkeypatch.setattr(tool_components, "chat_completion", lambda *a, **k: "  ")
        with pytest.raises(ValueError):
            tool_components.build_calculator({"max_tokens": 200})(dict(TASK))


class TestMediaComponents:
    def test_audio_transcription_needs_an_existing_file(self, tmp_path):
        with pytest.raises(ValueError):
            tool_components.transcribe_audio(dict(TASK))
        with pytest.raises(FileNotFoundError):
            tool_components.transcribe_audio(TASK | {"file_path": tmp_path / "x.mp3"})

    def test_audio_transcription_returns_the_transcript_as_evidence(
        self, tmp_path, monkeypatch
    ):
        audio = tmp_path / "talk.mp3"
        audio.write_bytes(b"x")
        monkeypatch.setattr(tool_components, "_transcribe", lambda path: "hello there")
        update = tool_components.transcribe_audio(TASK | {"file_path": audio})
        assert update["evidence"][0]["content"] == "Audio transcription:\nhello there"
        assert update["evidence"][0]["source_type"] == "audio_transcription"

    def test_an_empty_transcript_is_an_error(self, tmp_path, monkeypatch):
        audio = tmp_path / "talk.mp3"
        audio.write_bytes(b"x")
        monkeypatch.setattr(tool_components, "_transcribe", lambda path: "  ")
        with pytest.raises(ValueError):
            tool_components.transcribe_audio(TASK | {"file_path": audio})

    def test_image_description_asks_the_vision_model_about_the_question(
        self, tmp_path, monkeypatch
    ):
        image = tmp_path / "chart.png"
        image.write_bytes(b"x")
        monkeypatch.setattr(
            tool_components,
            "_inspect_image",
            lambda path, question, source: evidence(
                f"a chart ({question})", source, "image_vlm"
            ),
        )
        update = tool_components.describe_image(TASK | {"file_path": image})
        assert update["evidence"][0]["content"] == "a chart (Who wrote Hamlet?)"

    def test_media_components_keep_earlier_evidence(self, tmp_path, monkeypatch):
        audio = tmp_path / "talk.mp3"
        audio.write_bytes(b"x")
        monkeypatch.setattr(tool_components, "_transcribe", lambda path: "hi")
        state = TASK | {"file_path": audio, "evidence": [evidence("earlier")]}
        update = tool_components.transcribe_audio(state)
        assert [e["content"] for e in update["evidence"]][0] == "earlier"
        assert len(update["evidence"]) == 2


class TestCatalogAndGraphs:
    NEW = {
        "tool_node",
        "web_search",
        "wikipedia_search",
        "calculator",
        "transcribe_audio",
        "describe_image",
    }

    def test_the_catalog_lists_the_new_components(self):
        nodes = {n["implementation_id"]: n for n in get_catalog()["nodes"]}
        assert self.NEW <= set(nodes)
        assert nodes["tool_node"]["category"] == "tools"
        assert nodes["web_search"]["category"] == "tools"
        tool_param = next(
            p for p in nodes["tool_node"]["params"] if p["name"] == "tool"
        )
        assert set(tool_param["choices"]) == {
            "web_search",
            "wikipedia",
            "fetch_url",
            "calculate",
        }
        assert "tools" in get_catalog()["categories"]

    def test_tool_components_recover_from_failures(self):
        nodes = {n["implementation_id"]: n for n in get_catalog()["nodes"]}
        for name in ("tool_node", "web_search", "wikipedia_search", "calculator"):
            assert nodes[name]["recover_errors"] is True, name

    def _definition(self, *nodes):
        edges = [
            EdgeDefinition(a.id, b.id) for a, b in zip(nodes, nodes[1:], strict=False)
        ]
        edges.append(EdgeDefinition(nodes[-1].id, "__end__"))
        return AgentDefinition(
            "4.0", "tooled", "AgentState", nodes[0].id, tuple(nodes), tuple(edges)
        )

    def test_a_search_then_reason_architecture_is_valid(self):
        definition = self._definition(
            NodeDefinition("find", "web_search"),
            NodeDefinition("solve", "reasoning"),
        )
        report = GraphValidator(
            create_studio_registry(), create_studio_routing_registry()
        ).validate(definition)
        assert report.is_valid, [d.message for d in report.errors]

    def test_the_architecture_runs_and_hands_evidence_to_reasoning(self, monkeypatch):
        monkeypatch.setattr(
            tool_components,
            "run_tool",
            lambda tool, text: [evidence("Shakespeare wrote Hamlet")],
        )
        seen = {}

        def fake_reasoning(messages, **kwargs):
            seen["prompt"] = json.dumps(messages)
            return "Shakespeare"

        monkeypatch.setattr(
            "huggingface_agents_langgraph.reasoning.chat_completion", fake_reasoning
        )
        definition = self._definition(
            NodeDefinition("find", "web_search"),
            NodeDefinition("solve", "reasoning"),
        )
        result = (
            GraphCompiler(create_studio_registry(), create_studio_routing_registry())
            .compile(definition)
            .invoke(dict(TASK))
        )
        assert result["draft_answer"] == "Shakespeare"
        assert "Shakespeare wrote Hamlet" in seen["prompt"]

    def test_a_failing_search_becomes_a_note_and_the_run_continues(self, monkeypatch):
        def broken(tool, text):
            raise RuntimeError("search unavailable")

        monkeypatch.setattr(tool_components, "run_tool", broken)
        monkeypatch.setattr(
            "huggingface_agents_langgraph.reasoning.chat_completion",
            lambda *a, **k: "unknown",
        )
        definition = self._definition(
            NodeDefinition("find", "web_search"),
            NodeDefinition("solve", "reasoning"),
        )
        result = (
            GraphCompiler(create_studio_registry(), create_studio_routing_registry())
            .compile(definition)
            .invoke(dict(TASK))
        )
        assert any("search unavailable" in n for n in result["research_notes"])
        assert result["draft_answer"] == "unknown"

    def test_the_v31_registry_is_untouched(self):
        from huggingface_agents_langgraph.graph_definition.registry import (
            create_gaia_v3_registry,
        )

        assert not self.NEW & set(create_gaia_v3_registry().list_implementations())
