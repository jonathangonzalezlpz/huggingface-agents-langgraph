# AGENTS.md

## Project purpose

This repository contains my implementation of the Hugging Face Agents Course
Unit 4 final assignment using LangGraph.

The project is also intended to serve as a public portfolio/certification
repository, so code quality, reproducibility, and clarity are important.

Do not solve or implement parts of the assignment proactively.
Only work on the specific task explicitly requested by the user.

## Python and environment

- Use Python 3.12 unless the project explicitly requires another version.
- Use `uv` for Python version management, virtual environments, dependency
  management, and lockfiles.
- Keep dependencies declared in `pyproject.toml`.
- Commit `uv.lock` to ensure reproducible environments.
- Do not introduce pip requirements files unless explicitly required by an
  external platform such as Hugging Face Spaces.
- Prefer `uv run <command>` when executing project tools.

## Project structure

- Keep the code modular.
- Application/library code belongs under `src/`.
- Tests belong under `tests/`.
- Avoid large monolithic modules.
- Separate responsibilities such as graph definition, state, nodes, tools,
  configuration, API clients, and evaluation when the project grows enough
  to justify it.
- Do not create abstractions prematurely.
- Prefer simple solutions until additional complexity is actually needed.

## Python style

- Follow clean-code principles and idiomatic modern Python.
- Follow PEP 8.
- Use descriptive names.
- Prefer small, focused functions and classes.
- Use type hints for public functions, state structures, and relevant
  interfaces.
- Prefer explicit code over clever code.
- Avoid unnecessary duplication.
- Avoid mutable global state.
- Avoid magic values; use named constants or configuration when appropriate.
- Prefer pathlib over raw path strings for filesystem operations.
- Prefer dataclasses, TypedDict, or other typed structures when they make the
  domain clearer.
- Keep functions focused on one responsibility.

## Comments and documentation

- Code, identifiers, docstrings, and comments must be written in English.
- Add comments only when the intent cannot be made clear through good naming
  and code structure.
- Comments should explain non-obvious behavior or constraints, not restate
  the code.
- Do not add comments about:
  - AI assistance
  - why an AI made a decision
  - implementation history
  - problems encountered while developing
  - problems that were fixed
  - conversation context
- Do not leave temporary explanatory comments after a problem has been
  resolved.
- Public APIs and non-obvious components may use concise docstrings.

## LangGraph

- Use LangGraph explicitly for the final assignment.
- Keep graph state clearly typed.
- Keep nodes focused on a single responsibility.
- Keep routing logic explicit and testable.
- Prefer deterministic logic when an LLM is not necessary.
- Do not introduce additional agents, graph nodes, tools, memory systems, or
  abstractions unless they solve a demonstrated requirement.

## Dependencies

- Add dependencies only when they are actually required.
- Before introducing a new dependency, prefer the Python standard library if
  it provides a clear and maintainable solution.
- Do not replace existing libraries or architecture without explicit user
  approval.

## Quality checks

Use Ruff for linting and formatting.

Before considering a coding task complete, run the relevant checks:

    uv run ruff check .
    uv run ruff format --check .
    uv run pytest

Fix failures caused by the changes made.

Do not modify unrelated code just to make unrelated checks pass.

## Tests

- Add tests for non-trivial deterministic logic.
- Prefer small unit tests for nodes, routing, parsing, formatting, and utility
  functions.
- Do not write tests whose only purpose is to increase coverage.
- External LLM/API calls should not be required for normal unit tests when
  they can reasonably be mocked or isolated.

## Secrets and configuration

- Never commit API keys, tokens, credentials, or secrets.
- Read secrets from environment variables.
- Provide `.env.example` when environment variables need to be documented.
- Never commit `.env`.
- Do not print secrets in logs or tests.

## Git

- Never create a commit unless the user explicitly asks for one.
- Never include IA coauthor.
- Never push changes unless the user explicitly asks for it.
- Never create or switch branches unless explicitly requested.
- Never amend, squash, rebase, or rewrite history unless explicitly requested.
- Avoid excessive commits.
- Group related changes into coherent commits.
- Before committing:
  1. Show or inspect `git status`.
  2. Review the relevant diff.
  3. Run the relevant checks.
  4. Propose the commit message.
  5. Wait for explicit user approval.

Use Conventional Commits.

Allowed common prefixes include:

- `feat:`
- `fix:`
- `refactor:`
- `test:`
- `docs:`
- `chore:`
- `ci:`

Commit messages must:

- Be written in English.
- Be a single line.
- Have no body.
- Be concise and descriptive.

Example:

    feat: add initial LangGraph state

## Scope discipline

- Modify only files needed for the requested task.
- Do not refactor unrelated code.
- Do not implement future assignment requirements unless explicitly asked.
- If a design decision has meaningful alternatives, explain them to the user
  before making a large architectural choice.
- If requirements are ambiguous, ask before making consequential assumptions.

## Definition of done

A task is complete when:

- The requested behavior is implemented.
- The code follows the repository conventions.
- Relevant tests pass.
- Ruff checks pass.
- No secrets or temporary files were introduced.
- No unrelated changes were made.
- No commit was created unless explicitly requested.