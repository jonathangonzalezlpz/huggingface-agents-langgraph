import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "publish_space.py"


@pytest.fixture
def publisher():
    return runpy.run_path(str(SCRIPT))


@pytest.mark.parametrize(
    "name",
    [
        ".env",
        ".env.backup",
        ".runtime/runs/private.json",
        "../secret.py",
        "src/.env/private.py",
        "src/.aws/credentials.py",
        "Agents.md",
    ],
)
def test_publication_rejects_private_or_unrelated_paths(publisher, name):
    assert not publisher["is_publishable"](name)


@pytest.mark.parametrize(
    "content",
    [
        b"hf_" + b"x" * 30,
        b"-----BEGIN " + b"PRIVATE KEY-----",
        b"https://" + b"user:password" + b"@example.org",
        b"C:" + b"\\Users\\" + b"private-person\\file",
    ],
)
def test_privacy_audit_never_echoes_detected_content(publisher, content):
    with pytest.raises(ValueError) as captured:
        publisher["audit_content"]("example.py", content, [])
    assert content.decode() not in str(captured.value)
    assert "example.py" in str(captured.value)


def test_environment_example_must_have_empty_credentials(publisher):
    publisher["audit_content"](".env.example", b"HF_TOKEN=\n", [])
    with pytest.raises(ValueError, match="must be empty"):
        publisher["audit_content"](".env.example", b"HF_TOKEN=example\n", [])


def test_package_ignores_untracked_files_and_reads_explicit_assets(publisher, tmp_path):
    prepare = publisher["prepare_package"]
    prepare.__globals__["PUBLICATION_FILES"] = {"LICENSE", "space/index.html"}
    prepare.__globals__["git"] = lambda *_a: (
        b"README.md\0src/agent.py\0.env\0Agents.md\0"
    )
    for name in (
        "README.md",
        "src/agent.py",
        "LICENSE",
        "space/index.html",
        ".env",
        "Agents.md",
        "src/untracked.py",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("sample", encoding="utf-8")
    package = prepare(tmp_path, [])
    assert set(package) == {"README.md", "src/agent.py", "LICENSE", "space/index.html"}


def test_remote_audit_rejects_private_history_before_download(publisher):
    api = SimpleNamespace(
        space_info=lambda *_a, **_k: SimpleNamespace(private=False, sdk="static"),
        list_repo_commits=lambda *_a, **_k: [SimpleNamespace(commit_id="revision")],
        list_repo_tree=lambda *_a, **_k: [
            SimpleNamespace(
                path=".env",
                blob_id="hash",
                size=20,
            )
        ],
    )
    with pytest.raises(ValueError, match="Private filename"):
        publisher["audit_remote"](api, "owner/space", [])


def test_publication_records_uploaded_commit_before_verification_failure(
    publisher,
    monkeypatch,
    tmp_path,
):
    import json
    import sys

    main = publisher["main"]
    globals_ = main.__globals__
    globals_["PROJECT_ROOT"] = tmp_path
    globals_["prepare_package"] = lambda *_a: {"README.md": b"public source"}
    globals_["git"] = lambda *_a: b"pipeline-commit"
    globals_["audit_remote"] = lambda *_a: {"parent_commit": "initial"}
    api = SimpleNamespace(
        whoami=lambda: {"name": "jonyglez"},
        create_commit=lambda **_k: SimpleNamespace(oid="published"),
    )
    globals_["HfApi"] = lambda **_k: api

    def fail_verification(*_args):
        raise OSError("Read failed")

    globals_["read_public_file"] = fail_verification
    monkeypatch.setenv("HF_TOKEN", "test-credential")
    monkeypatch.setattr(sys, "argv", ["publish_space.py", "--publish"])
    with pytest.raises(OSError, match="Read failed"):
        main()
    report = json.loads(
        (tmp_path / ".runtime/space-publication/audit.json").read_text()
    )
    assert report["published_commit"] == "published"
    assert report["verification"] == "pending"
