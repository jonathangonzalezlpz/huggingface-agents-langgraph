"""Question batteries that run in the background on the server."""

from huggingface_agents_langgraph.api.http import (
    JsonResponse,
    Request,
    Response,
    failure,
    ok,
)
from huggingface_agents_langgraph.api.router import Router
from huggingface_agents_langgraph.application.batteries import (
    MAX_QUESTIONS,
    BatteryBusyError,
    BatteryManager,
    BatteryUnavailableError,
)

BATTERIES = BatteryManager()


def current(request: Request) -> Response:
    return ok(BATTERIES.status())


def stop(request: Request) -> Response:
    return ok(BATTERIES.stop())


def start(request: Request) -> Response:
    """Start a battery, or resume an unfinished experiment."""
    try:
        payload = request.json_object()
        limit = payload.get("limit", MAX_QUESTIONS)
        if type(limit) is not int:
            raise ValueError("limit must be an integer")
        resume_id = payload.get("resume_id")
        if resume_id is not None and not isinstance(resume_id, str):
            raise ValueError("resume_id must be an experiment id")
        status = BATTERIES.start(
            payload.get("experiment"), limit=limit, resume_id=resume_id
        )
    except BatteryBusyError as error:
        return failure(409, str(error))
    except BatteryUnavailableError as error:
        return failure(503, str(error))
    except FileNotFoundError:
        return failure(404, "Experiment not found")
    except (ValueError, TypeError, KeyError) as error:
        return failure(400, str(error))
    return JsonResponse(202, status)


def register(router: Router) -> None:
    router.add("GET", "/api/batteries/current")(current)
    router.add("POST", "/api/batteries")(start)
    router.add("POST", "/api/batteries/stop")(stop)
