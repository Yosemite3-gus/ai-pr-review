"""GitHub 服务层 — 获取 PR 信息、变更文件、diff 内容"""
import re
import os
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

from services.utils import retry_on_network_error

load_dotenv(override=True)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
BASE_URL = "https://api.github.com"

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"


@retry_on_network_error(max_retries=3)
def _api(path: str) -> dict | list | str | None:
    """调用 GitHub REST API，自动处理分页和错误"""
    url = f"{BASE_URL}{path}" if path.startswith("/") else path
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    # 如果是 diff 类型（text/plain），直接返回文本
    if "text/plain" in resp.headers.get("Content-Type", ""):
        return resp.text
    return resp.json()


def parse_pr_url(url: str) -> dict:
    """解析 GitHub PR URL，返回 {owner, repo, number}

    支持格式:
    - https://github.com/owner/repo/pull/123
    - https://github.com/owner/repo/pull/123/files
    - github.com/owner/repo/pull/123
    """
    # 去掉协议前缀统一处理
    clean = re.sub(r"^https?://", "", url.strip())
    pattern = r"github\.com/([^/]+)/([^/]+)/pull/(\d+)"
    match = re.search(pattern, clean)
    if not match:
        raise ValueError(f"无法解析 PR URL: {url}")
    return {
        "owner": match.group(1),
        "repo": match.group(2),
        "number": int(match.group(3)),
    }


def fetch_pr(owner: str, repo: str, number: int) -> dict:
    """获取 PR 基本信息：标题、描述、作者、状态、分支、统计"""
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
        "commits": data["commits"],
        "changed_files": data["changed_files"],
        "additions": data["additions"],
        "deletions": data["deletions"],
        "url": data["html_url"],
        "created_at": data["created_at"],
    }


def fetch_pr_files(owner: str, repo: str, number: int) -> list[dict]:
    """获取 PR 变更的文件列表，每个文件含 filename, status, additions, deletions, patch"""
    data = _api(f"/repos/{owner}/{repo}/pulls/{number}/files")
    if data is None:
        return []
    return [
        {
            "filename": f["filename"],
            "status": f["status"],
            "additions": f["additions"],
            "deletions": f["deletions"],
            "changes": f["changes"],
            "patch": f.get("patch", ""),
        }
        for f in data
    ]


@retry_on_network_error(max_retries=3)
def fetch_diff(owner: str, repo: str, number: int) -> str:
    """获取 PR 的 unified diff 原始文本"""
    headers = dict(HEADERS)
    headers["Accept"] = "application/vnd.github.v3.diff"
    url = f"{BASE_URL}/repos/{owner}/{repo}/pulls/{number}"
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code == 404:
        raise ValueError(f"PR 不存在: {owner}/{repo}#{number}")
    resp.raise_for_status()
    return resp.text


def fetch_pr_full(pr_url: str) -> dict:
    """一站式接口：输入 PR URL，返回 PR 信息 + 文件列表 + diff"""
    info = parse_pr_url(pr_url)
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
    }
