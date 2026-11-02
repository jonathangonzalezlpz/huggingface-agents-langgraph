"""The small vocabulary handlers use: a request in, a response out."""

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, BinaryIO

MAX_REQUEST_BYTES = 1_000_000


@dataclass
class Request:
    """What a handler may know about a request; the body is read only on demand."""

    method: str
    path: str
    params: Mapping[str, str]
    headers: Mapping[str, str]
    rfile: BinaryIO

    def json_value(self) -> Any:
        """The JSON body, whatever its shape. Raises ``ValueError`` if unusable."""
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= MAX_REQUEST_BYTES:
            raise ValueError("Request body is empty or too large")
        return json.loads(self.rfile.read(length))

    def json_object(self) -> dict:
        """The JSON body, which must be an object."""
        payload = self.json_value()
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object")
        return payload


@dataclass(frozen=True)
class JsonResponse:
    status: int
    payload: object


@dataclass(frozen=True)
class BytesResponse:
    status: int
    body: bytes
    content_type: str
    headers: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Redirect:
    location: str


Response = JsonResponse | BytesResponse | Redirect
Handler = Callable[[Request], Response]


def ok(payload: object) -> JsonResponse:
    return JsonResponse(200, payload)


def failure(status: int, message: str) -> JsonResponse:
    return JsonResponse(status, {"error": message})
