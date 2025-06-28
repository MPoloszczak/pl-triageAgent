import logging
import os
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)
GITHUB_API = "https://api.github.com"


def _github_request(method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
    """Thin wrapper around the GitHub REST API with auth and error handling."""
    headers = kwargs.pop("headers", {})
    headers.setdefault("Authorization", f"token {os.getenv('GH_TOKEN')}")
    headers.setdefault("Accept", "application/vnd.github+json")
    url = f"{GITHUB_API}{endpoint}"
    resp = requests.request(method, url, headers=headers, timeout=30, **kwargs)

    if not resp.ok:
        logger.error("GitHub API error %s -> %s", resp.status_code, resp.text)
        resp.raise_for_status()
    if resp.text:
        return resp.json()
    return {}


def apply_label(number: int, label: str, owner: str, repo: str) -> None:
    """Apply a label to an issue or pull request."""
    endpoint = f"/repos/{owner}/{repo}/issues/{number}/labels"
    _github_request("POST", endpoint, json={"labels": [label]})


def comment_issue(number: int, body: str, owner: str, repo: str) -> None:
    """Post a comment to an issue or pull request."""
    endpoint = f"/repos/{owner}/{repo}/issues/{number}/comments"
    _github_request("POST", endpoint, json={"body": body})


def set_labels(number: int, labels: list[str], owner: str, repo: str) -> None:
    """Replace all labels on an issue or pull request with the provided list."""
    endpoint = f"/repos/{owner}/{repo}/issues/{number}/labels"
    _github_request("PUT", endpoint, json={"labels": labels}) 