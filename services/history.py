"""分析历史记录 — 保存/加载/删除 past analyses"""
import json
import os
import uuid
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
HISTORY_FILE = "analysis_history.json"
MAX_ENTRIES = 50


def _load_all() -> list[dict]:
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def _save_all(entries: list[dict]):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def save_analysis(pr_data: dict, result: dict):
    """保存一次分析结果。不存储完整 diff，只存 PR 元信息 + 分析结果。"""
    entries = _load_all()

    entry = {
        "id": uuid.uuid4().hex[:12],
        "timestamp": datetime.now(CST).strftime("%Y-%m-%d %H:%M"),
        "pr_url": pr_data.get("url", ""),
        "pr_title": pr_data.get("title", ""),
        "pr_author": pr_data.get("author", ""),
        "repo": pr_data.get("repo", ""),
        "pr_number": pr_data.get("pr_number", 0),
        "platform": pr_data.get("platform", "github"),
        "head_branch": pr_data.get("head_branch", ""),
        "base_branch": pr_data.get("base_branch", ""),
        "changed_files": pr_data.get("changed_files", 0),
        "additions": pr_data.get("additions", 0),
        "deletions": pr_data.get("deletions", 0),
        "result": {
            "summary": result.get("summary", ""),
            "risks": result.get("risks", ""),
            "suggestions": result.get("suggestions", ""),
            "overall": result.get("overall", ""),
            "raw": result.get("raw", ""),
            "model": result.get("model", ""),
            "chunked": result.get("chunked", False),
            "files_analyzed": result.get("files_analyzed", 0),
        },
    }

    # 对比模式特殊处理
    if result.get("compare_mode"):
        entry["result"]["compare_mode"] = True
        ds = result.get("deepseek", {})
        qw = result.get("qwen") or {}
        entry["result"]["deepseek"] = {
            "summary": ds.get("summary", ""),
            "risks": ds.get("risks", ""),
            "suggestions": ds.get("suggestions", ""),
            "overall": ds.get("overall", ""),
            "raw": ds.get("raw", ""),
            "model": ds.get("model", ""),
        }
        if qw:
            entry["result"]["qwen"] = {
                "summary": qw.get("summary", ""),
                "risks": qw.get("risks", ""),
                "suggestions": qw.get("suggestions", ""),
                "overall": qw.get("overall", ""),
                "raw": qw.get("raw", ""),
                "model": qw.get("model", ""),
            }

    entries.insert(0, entry)

    # 超过上限时移除最旧的
    if len(entries) > MAX_ENTRIES:
        entries = entries[:MAX_ENTRIES]

    _save_all(entries)


def load_history() -> list[dict]:
    """返回所有历史记录，按时间倒序"""
    return _load_all()


def delete_analysis(entry_id: str):
    """删除指定条目"""
    entries = _load_all()
    entries = [e for e in entries if e["id"] != entry_id]
    _save_all(entries)
