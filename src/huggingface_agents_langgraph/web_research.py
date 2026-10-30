"""Web and Wikipedia research node for tasks without attachments."""

import json
import re
import xml.etree.ElementTree as ElementTree
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from io import BytesIO
from typing import TypedDict
from urllib.error import URLError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

from ddgs import DDGS
from ddgs.exceptions import DDGSException

from huggingface_agents_langgraph.config import (
    WEB_PAGE_LIMIT,
    WEB_SEARCH_RESULT_LIMIT,
    WEB_SEARCH_TIMEOUT_SECONDS,
)
from huggingface_agents_langgraph.evidence_selection import select_relevant_evidence
from huggingface_agents_langgraph.llm import chat_completion
from huggingface_agents_langgraph.state import AgentState, Evidence

WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
EUROPE_PMC_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
EUROPE_PMC_FULL_TEXT_URL = (
    "https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
)
SCHOLARLY_TERMS = re.compile(
    r"\b(papers?|articles?|studies|publications?|journals?|research|published|"
    r"artículos?|articulos?|estudios|publicaciones?|revistas?)\b",
    re.IGNORECASE,
)
WIKIPEDIA_SOURCE_INSTRUCTION = re.compile(
    r"\b(?:you can use|use)\s+(?:the\s+)?(?:latest\s+)?(?:\d{4}\s+)?"
    r"version of (?:the )?(?:english|en)\s+wikipedia\b.*$",
    re.IGNORECASE,
)
WIKIPEDIA_SUBJECT_PATTERN = re.compile(
    r"\b(?:by|about|regarding|concerning|written by|performed by|"
    r"directed by|created by|of)\s+([A-Z][\w’'.-]*(?:\s+[A-Z][\w’'.-]*){0,4})"
)
WIKIPEDIA_TITLE_PATTERN = re.compile(r"\b[A-Z][\w’'.-]*(?:\s+[A-Z][\w’'.-]*)+\b")
WIKIPEDIA_GENERIC_TITLES = {
    "english wikipedia",
    "wikipedia",
}
WIKIPEDIA_IGNORED_CLASSES = {
    "catlinks",
    "mw-editsection",
    "mw-jump-link",
    "mw-references-wrap",
    "navbox",
    "references",
    "toc",
}


class _WikipediaHTMLTextParser(HTMLParser):
    """Convert article HTML into text while preserving table rows and cells."""

    _BLOCK_TAGS = {"br", "div", "li", "p", "tr"}
    _HEADING_TAGS = {"h2": "==", "h3": "===", "h4": "===="}
    _CELL_TAGS = {"td", "th"}
    _IGNORED_TAGS = {"script", "style", "sup"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        from huggingface_agents_langgraph.experiments import improvement_enabled

        if (
            improvement_enabled(None, "web_sources")
            and self._ignored_depth
            and tag
            in {
                "area",
                "base",
                "br",
                "col",
                "embed",
                "hr",
                "img",
                "input",
                "link",
                "meta",
                "param",
                "source",
                "track",
                "wbr",
            }
        ):
            return
        if self._ignored_depth:
            self._ignored_depth += 1
            return
        classes = set((dict(attrs).get("class") or "").split())
        if tag in self._IGNORED_TAGS or classes & WIKIPEDIA_IGNORED_CLASSES:
            self._ignored_depth = 1
            return
        if tag in self._HEADING_TAGS:
            self._parts.append(f"\n{self._HEADING_TAGS[tag]} ")
        elif tag in self._BLOCK_TAGS:
            self._parts.append("\n")
        elif tag in self._CELL_TAGS:
            self._parts.append(" | ")

    def handle_endtag(self, tag: str) -> None:
        if self._ignored_depth:
            self._ignored_depth -= 1
            return
        if tag in self._HEADING_TAGS:
            self._parts.append(f" {self._HEADING_TAGS[tag]}\n")
        elif tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self._parts.append(data)

    def get_text(self) -> str:
        lines = [
            re.sub(r"\s+", " ", line).strip()
            for line in "".join(self._parts).splitlines()
        ]
        return "\n".join(line for line in lines if line)


class WebResearchUpdate(TypedDict):
    """State fields produced by the web research node."""

    evidence: list[Evidence]


def web_research(state: AgentState) -> WebResearchUpdate:
    """Search the web or Wikipedia, then select relevant source passages."""
    route = state.get("route")
    if route == "wikipedia":
        source_evidence = _search_wikipedia(state["question"])
    elif route == "web":
        query = chat_completion(
            [
                {
                    "role": "system",
                    "content": (
                        "Write one concise web search query for the task. "
                        "Retain names, dates and source constraints. "
                        "Return only the query. /no_think"
                    ),
                },
                {"role": "user", "content": state["question"]},
            ],
            max_tokens=160,
            model=state.get("experiment", {}).get("model"),
        )
        source_evidence = _search_web(query)
    else:
        raise ValueError(f"web_research does not support route: {route!r}")

    if not source_evidence:
        raise RuntimeError("No usable source pages were found for this question")
    evidence = select_relevant_evidence(state["question"], source_evidence)
    if not evidence:
        raise RuntimeError("No relevant evidence was extracted from the source pages")
    return {"evidence": evidence}


class _LinkedTextParser(_WikipediaHTMLTextParser):
    """Preserve navigation targets alongside readable HTML text."""

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        super().handle_starttag(tag, attrs)
        if tag == "a" and len(self.links) < 500:
            href = dict(attrs).get("href")
            target = urljoin(self.url, href or "")
            if (
                href
                and target.startswith(("https://", "http://"))
                and target not in self.links
            ):
                self.links.append(target)


def fetch_source(url: str) -> list[Evidence]:
    """Read an HTML page or PDF, retaining links and page provenance."""
    if urlsplit(url).scheme not in {"http", "https"}:
        raise ValueError("Source URL must use HTTP or HTTPS")
    request = Request(url, headers={"User-Agent": "GAIA-course-agent/0.2"})
    with urlopen(request, timeout=WEB_SEARCH_TIMEOUT_SECONDS) as response:
        data = response.read(10_000_001)
        final_url = response.geturl()
        encoding = response.headers.get_content_charset() or "utf-8"
    if len(data) > 10_000_000:
        raise ValueError("Source exceeds the 10 MB download limit")
    if data.startswith(b"%PDF"):
        from pypdf import PdfReader

        return [
            {
                "content": text,
                "source": f"{final_url}#page={index}",
                "source_type": "pdf_text",
            }
            for index, page in enumerate(PdfReader(BytesIO(data)).pages, 1)
            if (text := (page.extract_text() or "").strip())
        ]
    parser = _LinkedTextParser(final_url)
    parser.feed(data.decode(encoding, errors="replace"))
    text = parser.get_text()
    from huggingface_agents_langgraph.experiments import improvement_enabled

    if improvement_enabled(None, "web_sources"):
        from trafilatura import extract

        text = (
            extract(
                data.decode(encoding, errors="replace"),
                url=final_url,
                output_format="markdown",
                include_tables=True,
                include_links=True,
                include_comments=False,
            )
            or text
        )
    links = sorted(
        parser.links,
        key=lambda link: (
            not any(
                term in link.lower() for term in ("doi.org", "arxiv", ".pdf", "paper")
            )
        ),
    )[:80]
    return (
        [
            {
                "content": text,
                "source": final_url,
                "source_type": "web_page",
                "links": links,
            }
        ]
        if text
        else []
    )


def _search_web(question: str) -> list[Evidence]:
    """Search for pages and extract their readable text."""
    from huggingface_agents_langgraph.experiments import improvement_enabled

    if improvement_enabled(None, "web_sources"):
        return _search_readable_sources(question)
    try:
        search_results = DDGS(timeout=WEB_SEARCH_TIMEOUT_SECONDS).text(
            question,
            max_results=WEB_SEARCH_RESULT_LIMIT,
        )
    except DDGSException:
        search_results = []

    page_results = []
    for result in search_results:
        if len(page_results) >= WEB_PAGE_LIMIT:
            break
        url = result.get("href", "")
        if url.startswith(("http://", "https://")):
            page_results.append(result)

    needs_scholarly_search = _is_scholarly_question(question)
    worker_count = len(page_results) + int(needs_scholarly_search)
    with ThreadPoolExecutor(max_workers=max(1, worker_count)) as executor:
        literature_future = (
            executor.submit(_search_scholarly_literature, question)
            if needs_scholarly_search
            else None
        )
        page_evidence = [
            page
            for page in executor.map(_extract_web_result, page_results)
            if page is not None
        ]
        evidence = (
            literature_future.result() if literature_future is not None else []
        ) + page_evidence

    if not evidence and not search_results:
        raise RuntimeError("Web and scholarly searches failed")
    return evidence


def _search_readable_sources(query: str) -> list[Evidence]:
    """Read search hits as sources and mark snippets explicitly on fetch failures."""
    try:
        results = DDGS(timeout=WEB_SEARCH_TIMEOUT_SECONDS).text(
            query,
            max_results=WEB_SEARCH_RESULT_LIMIT,
        )
    except DDGSException as error:
        raise RuntimeError("Web search failed") from error
    evidence = []
    for result in results[:WEB_PAGE_LIMIT]:
        url = result.get("href", "")
        if not url.startswith(("https://", "http://")):
            continue
        try:
            evidence.extend(fetch_source(url))
        except (OSError, ValueError, RuntimeError) as error:
            snippet = result.get("body", "").strip()
            if snippet:
                evidence.append(
                    {
                        "content": "Search snippet; source page not read "
                        f"({type(error).__name__}).\n" + snippet,
                        "source": url,
                        "source_type": "search_snippet",
                    }
                )
    if not evidence:
        raise RuntimeError("No usable source pages or snippets were found")
    return evidence


def _extract_web_result(result: dict[str, str]) -> Evidence | None:
    """Extract one result page, falling back to its search snippet."""
    url = result["href"]
    title = result.get("title", "").strip()
    content = result.get("body", "").strip()
    try:
        extracted = DDGS(timeout=WEB_SEARCH_TIMEOUT_SECONDS).extract(
            url,
            fmt="text_markdown",
        )
        extracted_content = extracted.get("content", "")
        if isinstance(extracted_content, str) and extracted_content.strip():
            content = extracted_content.strip()
    except DDGSException:
        pass

    if not content:
        return None
    return {
        "content": f"{title}\n\n{content}" if title else content,
        "source": url,
        "source_type": "web_page",
    }


def _is_scholarly_question(question: str) -> bool:
    """Check whether the question explicitly concerns a research publication."""
    return SCHOLARLY_TERMS.search(question) is not None


def _search_scholarly_literature(question: str) -> list[Evidence]:
    """Search Europe PMC, including full text when an open-access article exists."""
    parameters = {
        "query": question,
        "format": "json",
        "resultType": "core",
        "pageSize": str(WEB_PAGE_LIMIT),
    }
    request = Request(
        f"{EUROPE_PMC_SEARCH_URL}?{urlencode(parameters)}",
        headers={
            "User-Agent": "huggingface-agents-langgraph/0.1 (GAIA course project)"
        },
    )
    try:
        with urlopen(request, timeout=WEB_SEARCH_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, json.JSONDecodeError):
        return []

    results = payload.get("resultList", {}).get("result", [])
    evidence: list[Evidence] = []
    for result in results[:WEB_PAGE_LIMIT]:
        title = result.get("title", "").strip()
        abstract = result.get("abstractText", "").strip()
        pmcid = result.get("pmcid", "")
        doi = result.get("doi", "")
        content = _format_publication_metadata(result, abstract)
        if pmcid and result.get("isOpenAccess") == "Y":
            full_text = _fetch_europe_pmc_full_text(pmcid)
            if full_text:
                content = _format_publication_metadata(result, full_text)

        if not title or not content:
            continue
        if pmcid:
            source = f"https://europepmc.org/article/PMC/{pmcid}"
        elif doi:
            source = f"https://doi.org/{doi}"
        else:
            source = "https://europepmc.org/"
        evidence.append(
            {
                "content": content,
                "source": source,
                "source_type": "research_paper",
            }
        )
    return evidence


def _format_publication_metadata(result: dict[str, str], body: str) -> str:
    """Keep article identifiers and citation details alongside its text."""
    details = [result.get("title", "").strip()]
    for field in ("authorString", "firstPublicationDate", "journalTitle", "doi"):
        value = result.get(field, "").strip()
        if value:
            details.append(f"{field}: {value}")
    if body:
        details.append(body)
    return "\n\n".join(details)


def _fetch_europe_pmc_full_text(pmcid: str) -> str:
    """Return open-access article text, or an empty string if unavailable."""
    request = Request(
        EUROPE_PMC_FULL_TEXT_URL.format(pmcid=pmcid),
        headers={
            "User-Agent": "huggingface-agents-langgraph/0.1 (GAIA course project)"
        },
    )
    try:
        with urlopen(request, timeout=WEB_SEARCH_TIMEOUT_SECONDS) as response:
            root = ElementTree.fromstring(response.read())
    except (URLError, TimeoutError, ElementTree.ParseError):
        return ""
    return " ".join(text.strip() for text in root.itertext() if text.strip())


def _search_wikipedia(question: str) -> list[Evidence]:
    """Search English Wikipedia and return plaintext article evidence."""
    search_text = WIKIPEDIA_SOURCE_INSTRUCTION.sub("", question).strip()
    subjects = [
        match.group(1).strip()
        for match in WIKIPEDIA_SUBJECT_PATTERN.finditer(search_text)
    ]
    subjects.extend(
        match.group(0).strip()
        for match in WIKIPEDIA_TITLE_PATTERN.finditer(search_text)
        if match.group(0).strip().lower() not in WIKIPEDIA_GENERIC_TITLES
    )
    search_queries = list(dict.fromkeys(subjects)) or [search_text]
    from huggingface_agents_langgraph.experiments import improvement_enabled

    version = re.search(r"\b(?:latest\s+)?(\d{4})\s+version\b", question, re.I)
    as_of = (
        f"{version[1]}-12-31T23:59:59Z"
        if (version and improvement_enabled(None, "web_sources"))
        else None
    )

    for search_query in search_queries:
        evidence = (
            _get_wikipedia_page(search_query, as_of=as_of)
            if as_of
            else _get_wikipedia_page(search_query)
        )
        if evidence:
            return evidence
        evidence = _search_wikipedia_subject(search_query)
        if as_of and evidence:
            evidence = [
                revision
                for item in evidence
                for revision in _get_wikipedia_page(
                    item["content"].split("\n", 1)[0],
                    as_of=as_of,
                )
            ]
        if evidence:
            if search_query in subjects:
                exact_title = [
                    item
                    for item in evidence
                    if item["content"].split("\n", 1)[0].casefold()
                    == search_query.casefold()
                ]
                if exact_title:
                    return exact_title[:1]
            return evidence
    return []


def _get_wikipedia_page(title: str, *, as_of: str | None = None) -> list[Evidence]:
    """Fetch a rendered article, including tables, for an exact page title."""
    parameters = {
        "action": "parse",
        "page": title,
        "prop": "text",
        "format": "json",
    }
    revision_id = None
    if as_of:
        query = {
            "action": "query",
            "titles": title,
            "prop": "revisions",
            "rvprop": "ids|timestamp",
            "rvstart": as_of,
            "rvlimit": "1",
            "rvdir": "older",
            "format": "json",
            "redirects": "1",
        }
        try:
            with urlopen(
                Request(
                    f"{WIKIPEDIA_API_URL}?{urlencode(query)}",
                    headers={"User-Agent": "GAIA-LangGraph/0.1 (course portfolio)"},
                ),
                timeout=WEB_SEARCH_TIMEOUT_SECONDS,
            ) as response:
                pages = json.loads(response.read()).get("query", {}).get("pages", {})
            revisions = [
                revision
                for page in pages.values()
                for revision in page.get("revisions", [])
            ]
            if not revisions:
                return []
            revision_id = revisions[0]["revid"]
            parameters.pop("page")
            parameters["oldid"] = str(revision_id)
        except (OSError, ValueError, KeyError):
            return []
    request = Request(
        f"{WIKIPEDIA_API_URL}?{urlencode(parameters)}",
        headers={
            "User-Agent": "huggingface-agents-langgraph/0.1 (GAIA course project)"
        },
    )
    try:
        with urlopen(request, timeout=WEB_SEARCH_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, json.JSONDecodeError):
        return []

    parsed = payload.get("parse", {})
    page_title = parsed.get("title", title)
    html_response = parsed.get("text", "")
    html = (
        html_response.get("*", "") if isinstance(html_response, dict) else html_response
    )
    if not page_title or not html:
        return []

    text_parser = _WikipediaHTMLTextParser()
    text_parser.feed(html)
    content = text_parser.get_text()
    page_id = parsed.get("pageid")
    if not content or not page_id:
        return []
    return [
        {
            "content": f"{page_title}\n{content}",
            "source": f"https://en.wikipedia.org/?oldid={revision_id}"
            if revision_id
            else f"https://en.wikipedia.org/?curid={page_id}",
            "source_type": "wikipedia",
        }
    ]


def _search_wikipedia_subject(search_query: str) -> list[Evidence]:
    """Search for a concise subject or title and return its article extracts."""
    parameters = {
        "action": "query",
        "generator": "search",
        "gsrsearch": search_query,
        "gsrnamespace": "0",
        "gsrlimit": str(WEB_PAGE_LIMIT),
        "prop": "info",
        "redirects": "1",
        "format": "json",
    }
    request = Request(
        f"{WIKIPEDIA_API_URL}?{urlencode(parameters)}",
        headers={
            "User-Agent": "huggingface-agents-langgraph/0.1 (GAIA course project)"
        },
    )
    try:
        with urlopen(request, timeout=WEB_SEARCH_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, json.JSONDecodeError):
        return []

    pages = payload.get("query", {}).get("pages", {})
    evidence = []
    for page in sorted(pages.values(), key=lambda item: item.get("index", 0)):
        title = page.get("title", "")
        if title:
            evidence.extend(_get_wikipedia_page(title))
    return evidence
