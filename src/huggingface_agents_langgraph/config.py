"""Runtime configuration for the application."""

import os

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://127.0.0.1:8080/v1")
LLM_TIMEOUT_SECONDS = 60
CODE_EXECUTION_TIMEOUT_SECONDS = 60
