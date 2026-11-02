"""A route table: which handler answers which method and path."""

import re
from collections.abc import Callable
from dataclasses import dataclass

from huggingface_agents_langgraph.api.http import Handler

_PARAMETER = re.compile(r"\{(\w+)(\*?)\}")


@dataclass(frozen=True)
class Route:
    method: str
    pattern: re.Pattern[str]
    handler: Handler


def _compile(template: str) -> re.Pattern[str]:
    """``{name}`` matches one path segment, ``{name*}`` matches the rest of the path."""

    def replace(match: re.Match[str]) -> str:
        body = ".+" if match.group(2) else "[^/]+"
        return f"(?P<{match.group(1)}>{body})"

    return re.compile("^" + _PARAMETER.sub(replace, template) + "$")


class Router:
    """Routes are tried in the order they were added, so list specific ones first."""

    def __init__(self) -> None:
        self._routes: list[Route] = []

    def add(self, method: str, template: str) -> Callable[[Handler], Handler]:
        def register(handler: Handler) -> Handler:
            self._routes.append(Route(method, _compile(template), handler))
            return handler

        return register

    def match(self, method: str, path: str) -> tuple[Handler, dict[str, str]] | None:
        for route in self._routes:
            found = route.pattern.match(path)
            if route.method == method and found:
                return route.handler, found.groupdict()
        return None
