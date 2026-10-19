import base64
import os
from typing import Annotated, Any

import httpx2
from dotenv import load_dotenv
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field

load_dotenv()

GITHUB_API = "https://api.github.com"

server = MCPServer("taintgate")

SEGMENT = r"[\w.-]*[\w-][\w.-]*"

Repo = Annotated[str, Field(pattern=rf"^{SEGMENT}/{SEGMENT}$", description="owner/name, e.g. python/cpython")]

_SESSION: dict[str, bool] = {}


def _require_bound(repo: str) -> None:
    bound = os.getenv("BOUND_REPO", "")
    if not bound:
        raise ToolError("Blocked: BOUND_REPO is not set")
    if bound != "*" and repo.lower() != bound.lower():
        raise ToolError(f"Blocked: session is bound to {bound} and cannot access {repo}")


def _require_untainted() -> None:
    if os.getenv("TAINT_TRACKING", "false").lower() == "true" and _SESSION.get("tainted"):
        raise ToolError("Blocked: cannot post after reading file contents in this session (taint tracking)")


class IssueSummary(BaseModel):
    number: int
    title: str
    state: str
    url: str
    labels: list[str]


class IssueDetail(IssueSummary):
    author: str
    body: str
    comments: int


class FileContent(BaseModel):
    repo: str
    path: str
    content: str


class WriteResult(BaseModel):
    dry_run: bool
    action: str
    url: str | None = None


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token := os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def _github(path: str, method: str = "GET", json: Any = None, **params: Any) -> Any:
    async with httpx2.AsyncClient(timeout=15) as client:
        resp = await client.request(method, f"{GITHUB_API}{path}", json=json, params=params, headers=_headers())
    if resp.status_code == 404:
        raise ToolError(f"Not found on GitHub: {path}")
    if not resp.is_success:
        raise ToolError(f"GitHub request failed ({resp.status_code}): {resp.text[:200]}")
    return resp.json()


def _check_write(repo: str) -> bool:
    sandbox = os.getenv("SANDBOX_REPO", "")
    if not sandbox:
        raise ToolError("Writes are disabled: SANDBOX_REPO is not set")
    if repo.lower() != sandbox.lower():
        raise ToolError(f"Writes are only allowed on {sandbox}, not {repo}")
    return os.getenv("DRY_RUN", "true").lower() != "false"


def _summary(i: dict[str, Any]) -> dict[str, Any]:
    return {
        "number": i["number"],
        "title": i["title"],
        "state": i["state"],
        "url": i["html_url"],
        "labels": [label["name"] for label in i["labels"]],
    }


@server.tool(description="Search issues (not pull requests) in one GitHub repo by keywords.")
async def search_issues(
    repo: Repo,
    query: Annotated[str, Field(min_length=1, max_length=200)],
    limit: Annotated[int, Field(ge=1, le=30)] = 10,
) -> list[IssueSummary]:
    _require_bound(repo)
    data = await _github("/search/issues", q=f"{query} repo:{repo} is:issue", per_page=limit)
    own = f"{GITHUB_API}/repos/{repo}".lower()
    return [IssueSummary(**_summary(i)) for i in data["items"] if i["repository_url"].lower() == own]


@server.tool(description="Get one GitHub issue with its body, author and comment count.")
async def get_issue(repo: Repo, number: Annotated[int, Field(ge=1)]) -> IssueDetail:
    _require_bound(repo)
    i = await _github(f"/repos/{repo}/issues/{number}")
    if "pull_request" in i:
        raise ToolError(f"#{number} in {repo} is a pull request, not an issue")
    return IssueDetail(**_summary(i), author=i["user"]["login"], body=i["body"] or "", comments=i["comments"])


@server.tool(description="Read a text file from a GitHub repo.")
async def get_file(
    repo: Repo,
    path: Annotated[str, Field(pattern=rf"^{SEGMENT}(/{SEGMENT})*$", max_length=200, description="e.g. README.md")],
) -> FileContent:
    _require_bound(repo)
    f = await _github(f"/repos/{repo}/contents/{path}")
    if not isinstance(f, dict) or f.get("encoding") != "base64":
        raise ToolError(f"{path} in {repo} is not a file")
    _SESSION["tainted"] = True
    return FileContent(repo=repo, path=path, content=base64.b64decode(f["content"]).decode(errors="replace")[:20000])


@server.tool(description="Add a label to an issue. Sandbox repo only; dry-run unless DRY_RUN=false.")
async def add_label(
    repo: Repo,
    number: Annotated[int, Field(ge=1)],
    label: Annotated[str, Field(min_length=1, max_length=50)],
) -> WriteResult:
    action = f"add label '{label}' to {repo}#{number}"
    _require_bound(repo)
    if _check_write(repo):
        return WriteResult(dry_run=True, action=f"would {action}")
    await _github(f"/repos/{repo}/issues/{number}/labels", "POST", {"labels": [label]})
    return WriteResult(dry_run=False, action=action, url=f"https://github.com/{repo}/issues/{number}")


@server.tool(description="Post a comment on an issue. Sandbox repo only; dry-run unless DRY_RUN=false.")
async def post_comment(
    repo: Repo,
    number: Annotated[int, Field(ge=1)],
    body: Annotated[str, Field(min_length=1, max_length=5000)],
) -> WriteResult:
    action = f"post a comment on {repo}#{number}"
    _require_bound(repo)
    _require_untainted()
    if _check_write(repo):
        return WriteResult(dry_run=True, action=f"would {action}")
    c = await _github(f"/repos/{repo}/issues/{number}/comments", "POST", {"body": body})
    return WriteResult(dry_run=False, action=action, url=c["html_url"])


if __name__ == "__main__":
    server.run()
