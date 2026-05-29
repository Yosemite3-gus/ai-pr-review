"""PR 服务路由 — 根据 URL 自动选择 GitHub 或 Gitee 后端"""

from services.github_service import fetch_pr_full as github_fetch
from services.gitee_service import fetch_pr_full as gitee_fetch


def detect_platform(url: str) -> str:
    """根据 URL 识别平台"""
    if "gitee.com" in url:
        return "gitee"
    return "github"


def fetch_pr_full(url: str) -> dict:
    """自动识别平台并获取 PR 数据，返回统一格式"""
    platform = detect_platform(url)
    if platform == "gitee":
        return gitee_fetch(url)
    return github_fetch(url)
