from __future__ import annotations

import re
from typing import Any

import structlog

from mcp_server_toolkit.context import AppContext

logger = structlog.get_logger(__name__)

_GITHUB_SLUG = re.compile(r"^[A-Za-z0-9._-]+$")


def _validate_github_slug(value: str, label: str) -> str:
    cleaned = value.strip()
    if not cleaned or not _GITHUB_SLUG.fullmatch(cleaned):
        raise ValueError(f"Invalid GitHub {label}; must match [A-Za-z0-9._-]")
    return cleaned


async def _get_json(app: AppContext, path: str) -> Any:
    url = f"{app.settings.github_api_base.rstrip('/')}/{path.lstrip('/')}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "mcp-server-toolkit-demo",
    }
    if app.settings.github_token:
        headers["Authorization"] = f"Bearer {app.settings.github_token}"
    response = await app.http.get(url, headers=headers)
    if response.status_code == 404:
        raise ValueError(f"GitHub resource not found: {path}")
    response.raise_for_status()
    return response.json()


async def summarize_github_repository(owner: str, repo: str, *, app: AppContext) -> str:
    """Fetch repository metadata and a snapshot of open issues."""

    owner = _validate_github_slug(owner, "owner")
    repo = _validate_github_slug(repo, "repository name")

    meta = await _get_json(app, f"repos/{owner}/{repo}")
    issues_payload = await _get_json(app, f"repos/{owner}/{repo}/issues?state=open&per_page=5")
    issues = issues_payload if isinstance(issues_payload, list) else []

    lines = [
        f"# {meta.get('full_name', f'{owner}/{repo}')}",
        "",
        meta.get("description") or "_No description provided._",
        "",
        "## Stats",
        f"- Stars: {meta.get('stargazers_count', 0):,}",
        f"- Forks: {meta.get('forks_count', 0):,}",
        f"- Open issues: {meta.get('open_issues_count', 0):,}",
        f"- Default branch: `{meta.get('default_branch', 'unknown')}`",
        f"- Primary language: {meta.get('language') or 'unknown'}",
        f"- License: {(meta.get('license') or {}).get('spdx_id') or 'none'}",
        "",
        "## Recent open issues",
    ]

    if not issues:
        lines.append("_No open issues in the first page._")
    else:
        for issue in issues:
            if "pull_request" in issue:
                continue
            number = issue.get("number")
            title = issue.get("title", "")
            user = (issue.get("user") or {}).get("login", "unknown")
            lines.append(f"- #{number} **{title}** (by {user})")

    logger.info("github_repo_summarized", owner=owner, repo=repo)
    return "\n".join(lines)


async def summarize_github_issue(
    owner: str,
    repo: str,
    issue_number: int,
    *,
    app: AppContext,
) -> str:
    """Summarize a single GitHub issue including labels and comment count."""

    if issue_number < 1:
        raise ValueError("issue_number must be positive")

    owner = _validate_github_slug(owner, "owner")
    repo = _validate_github_slug(repo, "repository name")
    issue = await _get_json(app, f"repos/{owner}/{repo}/issues/{issue_number}")

    labels = ", ".join(label.get("name", "") for label in issue.get("labels", [])) or "none"
    body = (issue.get("body") or "").strip()
    if len(body) > 1200:
        body = body[:1200] + "\n\n… _(truncated)_"

    lines = [
        f"# Issue #{issue.get('number')}: {issue.get('title')}",
        "",
        f"- State: **{issue.get('state')}**",
        f"- Author: {(issue.get('user') or {}).get('login', 'unknown')}",
        f"- Labels: {labels}",
        f"- Comments: {issue.get('comments', 0)}",
        f"- URL: {issue.get('html_url')}",
        "",
        "## Body",
        body or "_Empty body._",
    ]
    logger.info("github_issue_summarized", owner=owner, repo=repo, issue=issue_number)
    return "\n".join(lines)
