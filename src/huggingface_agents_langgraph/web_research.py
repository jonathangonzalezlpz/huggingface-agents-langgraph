"""Web and Wikipedia research node for tasks without attachments."""

import json
import re
import xml.etree.ElementTree as ElementTree
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from typing import TypedDict
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ddgs import DDGS
from ddgs.exceptions import DDGSException

from huggingface_agents_langgraph.config import (
    WEB_PAGE_LIMIT,
    WEB_SEARCH_RESULT_LIMIT,
    WEB_SEARCH_TIMEOUT_SECONDS,
)
from huggingface_agents_langgraph.evidence_selection import select_relevant_evidence
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
        source_evidence = _search_web(state["question"])
    else:
        raise ValueError(f"web_research does not support route: {route!r}")

    if not source_evidence:
        raise RuntimeError("No usable source pages were found for this question")
    evidence = select_relevant_evidence(state["question"], source_evidence)
    if not evidence:
        raise RuntimeError("No relevant evidence was extracted from the source pages")
    return {"evidence": evidence}


def _search_web(question: str) -> list[Evidence]:
    """Search for pages and extract their readable text."""
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

    for search_query in search_queries:
        evidence = _get_wikipedia_page(search_query)
        if evidence:
            return evidence
        evidence = _search_wikipedia_subject(search_query)
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


def _get_wikipedia_page(title: str) -> list[Evidence]:
    """Fetch a rendered article, including tables, for an exact page title."""
    parameters = {
        "action": "parse",
        "page": title,
        "prop": "text",
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
            "source": f"https://en.wikipedia.org/?curid={page_id}",
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
