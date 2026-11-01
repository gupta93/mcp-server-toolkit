from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from mcp_server_toolkit.config import Settings
from mcp_server_toolkit.context import AppContext
from mcp_server_toolkit.tools.github import summarize_github_issue, summarize_github_repository


@pytest.fixture
def app() -> AppContext:
    settings = Settings(github_token=None)
    client = httpx.AsyncClient()
    return AppContext(settings=settings, http=client, demo_db_path=Path("/tmp/unused.db"))


@respx.mock
@pytest.mark.asyncio
async def test_summarize_github_repository(app: AppContext) -> None:
    respx.get("https://api.github.com/repos/octocat/Hello-World").respond(
        200,
        json={
            "full_name": "octocat/Hello-World",
            "description": "My first repo",
            "stargazers_count": 100,
            "forks_count": 20,
            "open_issues_count": 3,
            "default_branch": "main",
            "language": "C",
            "license": {"spdx_id": "MIT"},
        },
    )
    respx.get(url__regex=r"https://api\.github\.com/repos/octocat/Hello-World/issues").respond(
        200,
        json=[
            {
                "number": 1,
                "title": "Bug",
                "user": {"login": "octocat"},
            }
        ],
    )

    text = await summarize_github_repository("octocat", "Hello-World", app=app)
    assert "octocat/Hello-World" in text
    assert "Stars: 100" in text
    assert "#1" in text


@respx.mock
@pytest.mark.asyncio
async def test_summarize_github_issue(app: AppContext) -> None:
    respx.get("https://api.github.com/repos/octocat/Hello-World/issues/42").respond(
        200,
        json={
            "number": 42,
            "title": "Important",
            "state": "open",
            "user": {"login": "octocat"},
            "labels": [{"name": "bug"}],
            "comments": 2,
            "html_url": "https://github.com/octocat/Hello-World/issues/42",
            "body": "Details here",
        },
    )

    text = await summarize_github_issue("octocat", "Hello-World", 42, app=app)
    assert "Issue #42" in text
    assert "Labels: bug" in text
