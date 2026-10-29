"""Audit and publish an explicit source package to the project's static Space."""

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen

from huggingface_hub import (
    CommitOperationAdd,
    HfApi,
    hf_hub_url,
)

REPOSITORY = "jonyglez/huggingface-agents-langgraph"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLICATION_FILES = {
    "LICENSE",
    "space/index.html",
    "scripts/publish_space.py",
    "docs/publicacion-space.md",
    "tests/test_space_publication.py",
}
ROOT_FILES = {
    "README.md",
    "LICENSE",
    "pyproject.toml",
    "uv.lock",
    ".env.example",
    ".gitignore",
    ".python-version",
}
SOURCE_DIRECTORIES = {"src", "tests", "scripts", "docs", "space"}
SOURCE_EXTENSIONS = {".py", ".ps1", ".md", ".html", ".css", ".js"}
PRIVATE_PARTS = {
    ".env",
    ".git",
    ".venv",
    ".runtime",
    ".uv-cache",
    ".aws",
    ".codex",
    ".agents",
    "__pycache__",
}
MAX_FILE_BYTES = 2_000_000
PATTERNS = {
    "access token": re.compile(rb"(?:hf_|sk-)[A-Za-z0-9_-]{20,}"),
    "private key": re.compile(rb"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"),
    "AWS access key": re.compile(rb"(?:AKIA|ASIA)[A-Z0-9]{16}"),
    "credential in URL": re.compile(rb"https?://[^\s/@]+:[^\s/@]+@"),
    "personal filesystem path": re.compile(
        rb"(?:[A-Za-z]:\\+Users\\+|/(?:Users|home)/)[A-Za-z0-9_.-]+"
    ),
}


def git(root: Path, *arguments: str) -> bytes:
    """Read repository metadata without changing refs, index, or working files."""
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={root.as_posix()}", *arguments],
        cwd=root,
    )


def is_publishable(name: str) -> bool:
    """Allow source files and project metadata, excluding private local state."""
    path = Path(name)
    if (
        path.is_absolute()
        or ".." in path.parts
        or any(part in PRIVATE_PARTS for part in path.parts)
    ):
        return False
    if path.name.startswith(".env") and name != ".env.example":
        return False
    return name in ROOT_FILES or (
        path.parts[0] in SOURCE_DIRECTORIES and path.suffix in SOURCE_EXTENSIONS
    )


def audit_content(name: str, content: bytes, secrets: list[bytes]) -> None:
    """Reject sensitive patterns without including their values in diagnostics."""
    if len(content) > MAX_FILE_BYTES:
        raise ValueError(f"Oversized publication file: {name}")
    for label, pattern in PATTERNS.items():
        if pattern.search(content):
            raise ValueError(f"Privacy audit: {label} detected in {name}")
    if any(secret and secret in content for secret in secrets):
        raise ValueError(f"Privacy audit: configured credential detected in {name}")
    if name == ".env.example":
        for line in content.decode("utf-8").splitlines():
            key, separator, value = line.partition("=")
            if (
                separator
                and key.endswith(("TOKEN", "PASSWORD", "SECRET", "API_KEY"))
                and value.strip()
            ):
                raise ValueError("Credential defaults must be empty in .env.example")


def prepare_package(root: Path, secrets: list[bytes]) -> dict[str, bytes]:
    """Read only tracked sources plus the explicitly listed publication assets."""
    tracked = git(root, "ls-files", "-z").decode().split("\0")
    names = sorted(
        {name for name in tracked if name and is_publishable(name)} | PUBLICATION_FILES
    )
    package = {}
    for name in names:
        path = root / name
        if not is_publishable(name) or path.is_symlink() or not path.is_file():
            raise ValueError(f"Invalid publication path: {name}")
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Publication path escapes the project: {name}")
        content = path.read_bytes()
        audit_content(name, content, secrets)
        package[name] = content
    return package


def read_public_file(repo_id: str, name: str, revision: str) -> bytes:
    """Read a size-limited public source file without credentials or a disk cache."""
    request = Request(
        hf_hub_url(repo_id, name, repo_type="space", revision=revision),
        headers={"User-Agent": "gaia-space-publication/1.0"},
    )
    with urlopen(request, timeout=30) as response:
        content = response.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise ValueError(f"Remote file exceeds publication limit: {name}")
    return content


def write_report(directory: Path, report: dict) -> None:
    """Retain publication status before and after post-upload verification."""
    (directory / "audit.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )


def audit_remote(api: HfApi, repo_id: str, secrets: list[bytes]) -> dict:
    """Scan every reachable Space revision before publishing source files."""
    info = api.space_info(repo_id, files_metadata=False)
    if info.private or info.sdk != "static":
        raise ValueError(
            "The publication target must be an existing public static Space"
        )
    commits = api.list_repo_commits(repo_id, repo_type="space")
    checked = set()
    for commit in commits:
        for entry in api.list_repo_tree(
            repo_id, repo_type="space", revision=commit.commit_id, recursive=True
        ):
            if not hasattr(entry, "blob_id"):
                continue
            if any(part in PRIVATE_PARTS for part in Path(entry.path).parts) or (
                Path(entry.path).name.startswith(".env")
                and entry.path != ".env.example"
            ):
                raise ValueError(
                    f"Private filename already present in Space history: {entry.path}"
                )
            if entry.size > MAX_FILE_BYTES:
                raise ValueError(
                    "Remote audit requires manual review of oversized file: "
                    f"{entry.path}"
                )
            identity = (entry.path, entry.blob_id)
            if identity in checked:
                continue
            content = read_public_file(repo_id, entry.path, commit.commit_id)
            audit_content(entry.path, content, secrets)
            checked.add(identity)
    return {
        "parent_commit": info.sha,
        "revisions_checked": len(commits),
        "file_versions_checked": len(checked),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--publish", action="store_true", help="Upload after local and remote audits"
    )
    parser.add_argument(
        "--audit-remote",
        action="store_true",
        help="Audit Space history without uploading",
    )
    args = parser.parse_args()
    token = os.environ.get("HF_TOKEN")
    secrets = [token.encode()] if token else []
    package = prepare_package(PROJECT_ROOT, secrets)
    directory = PROJECT_ROOT / ".runtime" / "space-publication"
    directory.mkdir(parents=True, exist_ok=True)
    report = {
        "repository": REPOSITORY,
        "pipeline_commit": git(PROJECT_ROOT, "rev-parse", "HEAD").decode().strip(),
        "files": {
            name: hashlib.sha256(content).hexdigest()
            for name, content in package.items()
        },
        "bytes": sum(map(len, package.values())),
        "privacy_audit": "passed",
    }
    if args.publish or args.audit_remote:
        if not token:
            raise ValueError("HF_TOKEN is required for the authenticated remote audit")
        api = HfApi(token=token)
        account = api.whoami().get("name")
        if account != REPOSITORY.split("/", 1)[0]:
            raise ValueError("Token account does not match the approved Space owner")
        report["remote_audit"] = audit_remote(api, REPOSITORY, secrets)
        if args.publish:
            commit = api.create_commit(
                repo_id=REPOSITORY,
                repo_type="space",
                operations=[
                    CommitOperationAdd(path_in_repo=name, path_or_fileobj=content)
                    for name, content in package.items()
                ],
                commit_message=(
                    "feat: publish audited GAIA agent portfolio with MIT license"
                ),
                parent_commit=report["remote_audit"]["parent_commit"],
            )
            report["published_commit"] = commit.oid
            report["verification"] = "pending"
            write_report(directory, report)
            for name, expected in report["files"].items():
                content = read_public_file(REPOSITORY, name, commit.oid)
                if hashlib.sha256(content).hexdigest() != expected:
                    raise ValueError(f"Published file hash mismatch: {name}")
            report["verification"] = "all published file hashes match"
    write_report(directory, report)
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "files"}
            | {"file_count": len(package)},
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
