"""The route table of the local server: every resource registers its own routes."""

from huggingface_agents_langgraph.api.handlers import (
    app_files,
    architectures,
    batteries,
    experiments,
    questions,
    runs,
    scoring,
    system,
    traces,
)
from huggingface_agents_langgraph.api.router import Router

RESOURCES = (
    app_files,
    questions,
    system,
    architectures,
    experiments,
    batteries,
    traces,
    runs,
    scoring,
)


def build_router() -> Router:
    router = Router()
    for resource in RESOURCES:
        resource.register(router)
    return router
