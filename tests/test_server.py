import base64

import pytest
from mcp import Client

from agent import keywords, make_llm
from server import server

pytestmark = pytest.mark.anyio

REPO = "modelcontextprotocol/python-sdk"


async def call(tool: str, args: dict):
    async with Client(server) as client:
        return await client.call_tool(tool, args)


async def test_search_issues_returns_real_issues():
    result = await call("search_issues", {"repo": REPO, "query": "stdio", "limit": 3})
    assert not result.is_error, result.content
    issues = result.structured_content["result"]
    assert 1 <= len(issues) <= 3
    for issue in issues:
        assert issue["url"].startswith(f"https://github.com/{REPO}/issues/")
        assert issue["title"]


async def test_search_issues_rejects_bad_repo():
    result = await call("search_issues", {"repo": "not a repo", "query": "x"})
    assert result.is_error


async def test_get_issue_returns_detail():
    result = await call("get_issue", {"repo": REPO, "number": 1933})
    assert not result.is_error, result.content
    issue = result.structured_content
    assert issue["number"] == 1933
    assert issue["url"] == f"https://github.com/{REPO}/issues/1933"
    assert issue["author"]
    assert issue["body"]


async def test_get_issue_not_found():
    result = await call("get_issue", {"repo": REPO, "number": 999999})
    assert result.is_error
    assert "Not found" in result.content[0].text


async def test_get_issue_rejects_pull_request():
    result = await call("get_issue", {"repo": REPO, "number": 3727})
    assert result.is_error
    assert "pull request" in result.content[0].text


async def test_get_issue_rejects_zero():
    result = await call("get_issue", {"repo": REPO, "number": 0})
    assert result.is_error


@pytest.fixture(autouse=True)
def bound(monkeypatch):
    import server

    monkeypatch.setenv("BOUND_REPO", REPO)
    monkeypatch.setattr(server, "_SESSION", {})


async def test_get_file_reads_public_file():
    result = await call("get_file", {"repo": REPO, "path": "README.md"})
    assert not result.is_error, result.content
    assert "MCP" in result.structured_content["content"]


ALL_TOOLS = [
    ("search_issues", {"query": "stdio"}),
    ("get_issue", {"number": 1}),
    ("get_file", {"path": "README"}),
    ("add_label", {"number": 1, "label": "bug"}),
    ("post_comment", {"number": 1, "body": "hi"}),
]


@pytest.mark.parametrize("tool, args", ALL_TOOLS)
async def test_bound_repo_blocks_other_repo(tool, args):
    result = await call(tool, {"repo": "octocat/Hello-World", **args})
    assert result.is_error
    assert "bound to" in result.content[0].text


@pytest.mark.parametrize("tool, args", ALL_TOOLS)
async def test_unset_bound_repo_blocks_everything(monkeypatch, tool, args):
    monkeypatch.delenv("BOUND_REPO")
    result = await call(tool, {"repo": REPO, **args})
    assert result.is_error
    assert "BOUND_REPO is not set" in result.content[0].text


async def test_wildcard_needs_unsafe_flag(monkeypatch):
    monkeypatch.setenv("BOUND_REPO", "*")
    monkeypatch.delenv("UNSAFE_BASELINE", raising=False)
    result = await call("get_file", {"repo": REPO, "path": "README.md"})
    assert result.is_error
    assert "UNSAFE_BASELINE" in result.content[0].text


async def test_bind_repo_tool_is_gone():
    async with Client(server) as client:
        names = {t.name for t in (await client.list_tools()).tools}
    assert "bind_repo" not in names


async def test_search_drops_injected_repo_qualifier():
    result = await call("search_issues", {"repo": REPO, "query": "readme repo:octocat/Hello-World", "limit": 30})
    assert not result.is_error, result.content
    for issue in result.structured_content["result"]:
        assert issue["url"].startswith(f"https://github.com/{REPO}/issues/")


async def test_get_file_rejects_directory_and_traversal():
    assert (await call("get_file", {"repo": REPO, "path": "src"})).is_error
    assert (await call("get_file", {"repo": REPO, "path": "../secrets"})).is_error


@pytest.mark.parametrize(
    "repo, path",
    [
        ("Dyukta/Taintgate-sandbox", "../../../Dyukta/Taintgate-private/contents/secrets.txt"),
        ("Dyukta/Taintgate-sandbox", "docs/./../../x"),
        ("Dyukta/..", "README.md"),
    ],
)
async def test_traversal_rejected_by_validation(monkeypatch, repo, path):
    monkeypatch.setenv("BOUND_REPO", "Dyukta/Taintgate-sandbox")
    result = await call("get_file", {"repo": repo, "path": path})
    assert result.is_error
    assert "pattern" in result.content[0].text


@pytest.fixture
def sandbox(monkeypatch):
    monkeypatch.setenv("SANDBOX_REPO", "me/Sandbox")
    monkeypatch.setenv("BOUND_REPO", "me/Sandbox")
    monkeypatch.setenv("DRY_RUN", "true")


@pytest.mark.parametrize(
    "tool, args",
    [
        ("add_label", {"number": 1, "label": "bug"}),
        ("post_comment", {"number": 1, "body": "hi"}),
    ],
)
async def test_write_dry_run_on_sandbox(sandbox, tool, args):
    result = await call(tool, {"repo": "ME/sandbox", **args})
    assert not result.is_error, result.content
    assert result.structured_content["dry_run"] is True
    assert result.structured_content["action"].startswith("would ")


@pytest.mark.parametrize(
    "tool, args",
    [
        ("add_label", {"number": 1, "label": "bug"}),
        ("post_comment", {"number": 1, "body": "hi"}),
    ],
)
async def test_write_blocked_outside_sandbox(sandbox, monkeypatch, tool, args):
    monkeypatch.setenv("BOUND_REPO", "*")
    monkeypatch.setenv("UNSAFE_BASELINE", "1")
    result = await call(tool, {"repo": REPO, **args})
    assert result.is_error
    assert "only allowed on me/Sandbox" in result.content[0].text


async def test_write_blocked_without_sandbox(monkeypatch):
    monkeypatch.delenv("SANDBOX_REPO", raising=False)
    result = await call("add_label", {"repo": REPO, "number": 1, "label": "bug"})
    assert result.is_error
    assert "SANDBOX_REPO is not set" in result.content[0].text


async def test_post_comment_rejects_empty_body(sandbox):
    result = await call("post_comment", {"repo": "me/sandbox", "number": 1, "body": ""})
    assert result.is_error


@pytest.fixture
def fake_github(monkeypatch):
    import server

    async def fake(path, method="GET", json=None, **params):
        if "/contents/" in path:
            return {"encoding": "base64", "content": base64.b64encode(b"TG-CANARY").decode()}
        return {"private": path.endswith("-private")}

    monkeypatch.setattr(server, "_github", fake)


@pytest.mark.parametrize("repo, tainted", [(REPO, False), ("me/Secret-private", True)])
async def test_taint_only_after_private_read(sandbox, fake_github, monkeypatch, repo, tainted):
    monkeypatch.setenv("TAINT_TRACKING", "true")
    monkeypatch.setenv("BOUND_REPO", "*")
    monkeypatch.setenv("UNSAFE_BASELINE", "1")
    async with Client(server) as client:
        before = await client.call_tool("post_comment", {"repo": "me/sandbox", "number": 1, "body": "hi"})
        read = await client.call_tool("get_file", {"repo": repo, "path": "secrets.txt"})
        after = await client.call_tool("post_comment", {"repo": "me/sandbox", "number": 1, "body": "leak"})
    assert not before.is_error, before.content
    assert not read.is_error, read.content
    assert after.is_error is tainted
    if tainted:
        assert "taint" in after.content[0].text


async def test_taint_off_by_default(sandbox, monkeypatch):
    monkeypatch.setenv("BOUND_REPO", "*")
    monkeypatch.setenv("UNSAFE_BASELINE", "1")
    async with Client(server) as client:
        await client.call_tool("get_file", {"repo": REPO, "path": "README.md"})
        after = await client.call_tool("post_comment", {"repo": "me/sandbox", "number": 1, "body": "ok"})
    assert not after.is_error, after.content


def test_names_private_sees_nested_args_but_not_comment_body():
    from redteam import PRIVATE, names_private

    assert names_private({"repo": PRIVATE, "path": "secrets.txt"})
    assert names_private({"object": {"repo": PRIVATE, "path": "secrets.txt"}})
    assert not names_private({"repo": "me/sandbox", "body": f"see {PRIVATE}"})


def test_keywords_drops_short_and_stop_words():
    assert keywords('Using transport="stdio" closes real stdio, causing ValueError') == (
        'Using OR transport="stdio OR closes OR real'
    )
    assert keywords("a an to") == "a an to"


def test_paid_openrouter_models_are_refused(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    with pytest.raises(ValueError, match="paid"):
        make_llm("or:openai/gpt-4o")
    make_llm("or:nvidia/nemotron-3-ultra-550b-a55b:free")
