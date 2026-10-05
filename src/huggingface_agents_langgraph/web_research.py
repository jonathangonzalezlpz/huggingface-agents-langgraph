"""Web and Wikipedia research node for tasks without attachments."""

import json
import re
import xml.etree.ElementTree as ElementTree
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

    evidence = (
        _search_scholarly_literature(question)
        if _is_scholarly_question(question)
        else []
    )
    extracted_pages = 0
    for result in search_results:
        if extracted_pages >= WEB_PAGE_LIMIT:
            break
        url = result.get("href", "")
        if not url.startswith(("http://", "https://")):
            continue
        title = result.get("title", "").strip()
        snippet = result.get("body", "").strip()
        content = snippet
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

        if content:
            evidence.append(
                {
                    "content": f"{title}\n\n{content}" if title else content,
                    "source": url,
                    "source_type": "web_page",
                }
            )
            extracted_pages += 1
    if not evidence and not search_results:
        raise RuntimeError("Web and scholarly searches failed")
    return evidence


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
    parameters = {
        "action": "query",
        "generator": "search",
        "gsrsearch": question,
        "gsrnamespace": "0",
        "gsrlimit": str(WEB_PAGE_LIMIT),
        "prop": "extracts",
        "explaintext": "1",
        "exsectionformat": "plain",
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
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError("Wikipedia search failed") from error

    pages = payload.get("query", {}).get("pages", {})
    evidence: list[Evidence] = []
    for page in pages.values():
        title = page.get("title", "")
        content = page.get("extract", "").strip()
        page_id = page.get("pageid")
        if content and title and page_id:
            evidence.append(
                {
                    "content": content,
                    "source": f"https://en.wikipedia.org/?curid={page_id}",
                    "source_type": "wikipedia",
                }
            )
    return evidence
