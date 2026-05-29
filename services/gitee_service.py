"""Gitee 服务层 — 获取 Gitee PR 信息、变更文件、diff 内容（与 GitHub 服务层接口一致）"""
import re
import os

import requests
from dotenv import load_dotenv

from services.utils import retry_on_network_error

load_dotenv(override=True)

GITEE_TOKEN = os.getenv("GITEE_TOKEN", "")
BASE_URL = "https://gitee.com/api/v5"

HEADERS = {"Accept": "application/json"}
if GITEE_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITEE_TOKEN}"


@retry_on_network_error(max_retries=3)
def _api(path: str) -> dict | list | None:
    url = f"{BASE_URL}{path}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def parse_gitee_url(url: str) -> dict:
    """解析 Gitee PR URL"""
    clean = re.sub(r"^https?://", "", url.strip())
    pattern = r"gitee\.com/([^/]+)/([^/]+)/pulls?/(\d+)"
    match = re.search(pattern, clean)
    if not match:
        raise ValueError(f"无法解析 Gitee PR URL: {url}")
    return {
        "owner": match.group(1),
        "repo": match.group(2),
        "number": int(match.group(3)),
        "platform": "gitee",
    }


def fetch_pr(owner: str, repo: str, number: int) -> dict:
    data = _api(f"/repos/{owner}/{repo}/pulls/{number}")
    if data is None:
        raise ValueError(f"PR 不存在: {owner}/{repo}#{number}")
    return {
        "title": data["title"],
        "body": data.get("body") or "",
        "author": data["user"]["login"],
        "state": data["state"],
        "base_branch": data["base"]["ref"],
        "head_branch": data["head"]["ref"],
        "commits": data.get("commits", 0),
        "changed_files": data.get("changed_files", 0),
        "additions": data.get("additions", 0),
        "deletions": data.get("deletions", 0),
        "url": data["html_url"],
        "created_at": data.get("created_at", ""),
    }


def fetch_pr_files(owner: str, repo: str, number: int) -> list[dict]:
    data = _api(f"/repos/{owner}/{repo}/pulls/{number}/files")
    if data is None:
        return []
    return [
        {
            "filename": f.get("filename", f.get("path", "")),
            "status": f.get("status", "modified"),
            "additions": f.get("additions", 0),
            "deletions": f.get("deletions", 0),
            "changes": f.get("additions", 0) + f.get("deletions", 0),
            "patch": f.get("patch", ""),
        }
        for f in data
    ]


def fetch_diff(owner: str, repo: str, number: int) -> str:
    """Gitee 不提供统一 diff 端点，从文件 patches 拼接"""
    files = fetch_pr_files(owner, repo, number)
    parts = []
    for f in files:
        if f["patch"]:
            parts.append(f"diff --git a/{f['filename']} b/{f['filename']}")
            parts.append(f"--- a/{f['filename']}")
            parts.append(f"+++ b/{f['filename']}")
            parts.append(f["patch"])
    return "\n".join(parts)


def fetch_pr_full(pr_url: str) -> dict:
    """一站式接口：输入 Gitee PR URL，返回完整数据"""
    info = parse_gitee_url(pr_url)
    owner, repo, num = info["owner"], info["repo"], info["number"]

    pr = fetch_pr(owner, repo, num)
    files = fetch_pr_files(owner, repo, num)
    diff = fetch_diff(owner, repo, num)

    return {
        **pr,
        "files": files,
        "diff": diff,
        "owner": owner,
        "repo": repo,
        "pr_number": num,
        "platform": "gitee",
    }
