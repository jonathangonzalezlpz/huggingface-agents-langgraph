"""Agent architectures: the catalog, stored versions, validation and layouts."""

from urllib.parse import unquote

from huggingface_agents_langgraph.api.http import Request, Response, failure, ok
from huggingface_agents_langgraph.api.router import Router
from huggingface_agents_langgraph.architecture_layouts import get_layout, save_layout
from huggingface_agents_langgraph.architecture_service import (
    architecture_detail,
    get_catalog,
    validate_definition,
)
from huggingface_agents_langgraph.architecture_store import (
    ArchitectureNotFoundError,
    list_architectures,
    save_architecture,
)
from huggingface_agents_langgraph.graph_definition import AgentDefinition

NOT_FOUND = "Architecture not found"


def list_all(request: Request) -> Response:
    return ok({"architectures": list_architectures()})


def catalog(request: Request) -> Response:
    return ok(get_catalog())


def detail(request: Request) -> Response:
    try:
        return ok(architecture_detail(unquote(request.params["id"])))
    except ArchitectureNotFoundError:
        return failure(404, NOT_FOUND)


def read_layout(request: Request) -> Response:
    try:
        return ok(get_layout(unquote(request.params["id"])))
    except ArchitectureNotFoundError:
        return failure(404, NOT_FOUND)


def write_layout(request: Request) -> Response:
    """Store the node layout of an architecture version."""
    try:
        return ok(save_layout(unquote(request.params["id"]), request.json_object()))
    except ArchitectureNotFoundError:
        return failure(404, NOT_FOUND)
    except (ValueError, TypeError) as error:
        return failure(400, str(error))


def validate(request: Request) -> Response:
    try:
        return ok(validate_definition(request.json_object()))
    except (ValueError, TypeError) as error:
        return failure(400, str(error))


def save(request: Request) -> Response:
    try:
        definition = AgentDefinition.from_dict(request.json_object())
        return ok(save_architecture(definition))
    except (KeyError, ValueError, TypeError, AttributeError) as error:
        message = (
            f"Missing field {error}" if isinstance(error, KeyError) else str(error)
        )
        return failure(400, message)


def register(router: Router) -> None:
    router.add("GET", "/api/architectures")(list_all)
    router.add("GET", "/api/catalog")(catalog)
    router.add("GET", "/api/architectures/{id}/layout")(read_layout)
    router.add("GET", "/api/architectures/{id}")(detail)
    router.add("PUT", "/api/architectures/{id}/layout")(write_layout)
    router.add("POST", "/api/architectures/validate")(validate)
    router.add("POST", "/api/architectures")(save)
