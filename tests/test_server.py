import pytest
from mcp import Client

from agent import keywords
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
def unbound(monkeypatch):
    import server

    monkeypatch.setattr(server, "_BOUND", {})


async def test_get_file_reads_public_file():
    result = await call("get_file", {"repo": REPO, "path": "README.md"})
    assert not result.is_error, result.content
    assert "MCP" in result.structured_content["content"]


async def test_bound_repo_blocks_get_file_elsewhere():
    async with Client(server) as client:
        await client.call_tool("bind_repo", {"repo": REPO})
        same = await client.call_tool("get_file", {"repo": REPO, "path": "README.md"})
        other = await client.call_tool("get_file", {"repo": "octocat/Hello-World", "path": "README"})
    assert not same.is_error, same.content
    assert other.is_error
    assert "bound to" in other.content[0].text


async def test_bind_repo_cannot_rebind():
    async with Client(server) as client:
        await client.call_tool("bind_repo", {"repo": REPO})
        again = await client.call_tool("bind_repo", {"repo": "octocat/Hello-World"})
    assert again.is_error
    assert "already bound" in again.content[0].text


async def test_get_file_rejects_directory_and_traversal():
    assert (await call("get_file", {"repo": REPO, "path": "src"})).is_error
    assert (await call("get_file", {"repo": REPO, "path": "../secrets"})).is_error


@pytest.fixture
def sandbox(monkeypatch):
    monkeypatch.setenv("SANDBOX_REPO", "me/Sandbox")
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
async def test_write_blocked_outside_sandbox(sandbox, tool, args):
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


async def test_taint_blocks_post_after_get_file(sandbox, monkeypatch):
    monkeypatch.setenv("TAINT_TRACKING", "true")
    async with Client(server) as client:
        before = await client.call_tool("post_comment", {"repo": "me/sandbox", "number": 1, "body": "hi"})
        await client.call_tool("get_file", {"repo": REPO, "path": "README.md"})
        after = await client.call_tool("post_comment", {"repo": "me/sandbox", "number": 1, "body": "leak"})
    assert not before.is_error, before.content
    assert after.is_error
    assert "taint" in after.content[0].text


async def test_taint_off_by_default(sandbox):
    async with Client(server) as client:
        await client.call_tool("get_file", {"repo": REPO, "path": "README.md"})
        after = await client.call_tool("post_comment", {"repo": "me/sandbox", "number": 1, "body": "ok"})
    assert not after.is_error, after.content


def test_keywords_drops_short_and_stop_words():
    assert keywords('Using transport="stdio" closes real stdio, causing ValueError') == (
        'Using OR transport="stdio OR closes OR real'
    )
    assert keywords("a an to") == "a an to"
