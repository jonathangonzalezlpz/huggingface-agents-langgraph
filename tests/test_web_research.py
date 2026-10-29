import json
from io import BytesIO

from huggingface_agents_langgraph import web_research


class FakeDDGS:
    def __init__(self, timeout: int) -> None:
        assert timeout == web_research.WEB_SEARCH_TIMEOUT_SECONDS

    def text(self, _question: str, max_results: int) -> list[dict[str, str]]:
        assert max_results == web_research.WEB_SEARCH_RESULT_LIMIT
        return [
            {
                "title": "Relevant article",
                "href": "https://example.org/article",
                "body": "Search snippet",
            }
        ]

    def extract(self, _url: str, fmt: str) -> dict[str, str]:
        assert fmt == "text_markdown"
        return {"content": "The article says the answer is Paris."}


def test_web_research_searches_extracts_and_selects_page_text(
    monkeypatch,
) -> None:
    monkeypatch.setattr(web_research, "DDGS", FakeDDGS)
    state = {
        "task_id": "task-1",
        "question": "What city does this web page mention?",
        "file_name": "",
        "route": "web",
    }

    update = web_research.web_research(state)

    assert update["evidence"] == [
        {
            "content": "Relevant article\n\nThe article says the answer is Paris.",
            "source": "https://example.org/article",
            "source_type": "web_page",
        }
    ]


def test_web_research_queries_wikipedia_api_and_returns_article_source(
    monkeypatch,
) -> None:
    payload = {
        "parse": {
            "title": "Paris",
            "pageid": 123,
            "text": {"*": "<p>Paris is the capital and largest city of France.</p>"},
        }
    }

    class FakeResponse(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            self.close()

    def urlopen_mock(request, timeout: int):
        assert request.full_url.startswith(web_research.WIKIPEDIA_API_URL)
        assert "action=parse" in request.full_url
        assert "page=Paris" in request.full_url
        assert timeout == web_research.WEB_SEARCH_TIMEOUT_SECONDS
        return FakeResponse(json.dumps(payload).encode())

    monkeypatch.setattr(web_research, "urlopen", urlopen_mock)
    state = {
        "task_id": "task-1",
        "question": "What is the capital of Paris according to Wikipedia?",
        "file_name": "",
        "route": "wikipedia",
    }

    update = web_research.web_research(state)

    assert update["evidence"] == [
        {
            "content": "Paris\nParis is the capital and largest city of France.",
            "source": "https://en.wikipedia.org/?curid=123",
            "source_type": "wikipedia",
        }
    ]


def test_scholarly_search_fetches_open_access_full_text(monkeypatch) -> None:
    search_payload = {
        "resultList": {
            "result": [
                {
                    "title": "Specimens and their deposition",
                    "authorString": "A. Author",
                    "firstPublicationDate": "2010-01-01",
                    "journalTitle": "Journal of Example Studies",
                    "doi": "10.1000/example",
                    "pmcid": "PMC123456",
                    "isOpenAccess": "Y",
                    "abstractText": "Abstract text.",
                }
            ]
        }
    }

    class FakeResponse(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            self.close()

    requested_urls = []

    def urlopen_mock(request, timeout: int):
        requested_urls.append(request.full_url)
        assert timeout == web_research.WEB_SEARCH_TIMEOUT_SECONDS
        if request.full_url.startswith(web_research.EUROPE_PMC_SEARCH_URL):
            return FakeResponse(json.dumps(search_payload).encode())
        assert request.full_url == web_research.EUROPE_PMC_FULL_TEXT_URL.format(
            pmcid="PMC123456"
        )
        return FakeResponse(
            b"<article><body><p>Specimens were deposited in Paris.</p></body></article>"
        )

    monkeypatch.setattr(web_research, "urlopen", urlopen_mock)

    evidence = web_research._search_scholarly_literature(
        "Where were the specimens described in this paper deposited?"
    )

    assert len(requested_urls) == 2
    assert evidence == [
        {
            "content": (
                "Specimens and their deposition\n\n"
                "authorString: A. Author\n\n"
                "firstPublicationDate: 2010-01-01\n\n"
                "journalTitle: Journal of Example Studies\n\n"
                "doi: 10.1000/example\n\n"
                "Specimens were deposited in Paris."
            ),
            "source": "https://europepmc.org/article/PMC/PMC123456",
            "source_type": "research_paper",
        }
    ]


def test_scholarly_search_is_used_only_for_publication_questions() -> None:
    assert web_research._is_scholarly_question("Who wrote this research paper?")
    assert not web_research._is_scholarly_question("Where is Mercedes Sosa from?")


def test_general_web_research_adds_europe_pmc_for_paper_questions(
    monkeypatch,
) -> None:
    academic_evidence = {
        "content": "Research paper text.",
        "source": "https://europepmc.org/article/PMC/PMC123456",
        "source_type": "research_paper",
    }
    monkeypatch.setattr(web_research, "DDGS", FakeDDGS)
    monkeypatch.setattr(
        web_research,
        "_search_scholarly_literature",
        lambda _question: [academic_evidence],
    )

    evidence = web_research._search_web(
        "Where were the specimens described in this paper deposited?"
    )

    assert academic_evidence in evidence
