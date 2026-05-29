"""AI 分析引擎 — 调用 DeepSeek 进行 PR 代码评审"""
import os
import re

from openai import OpenAI
from dotenv import load_dotenv

from services.prompts import (
    SYSTEM_PROMPT,
    build_analysis_prompt,
    PER_FILE_PROMPT,
    build_per_file_prompt,
    AGGREGATION_PROMPT,
    build_aggregation_prompt,
)

load_dotenv(override=True)

API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

if not API_KEY:
    raise RuntimeError("DEEPSEEK_API_KEY 未设置，请在 .env 中配置")

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
MODEL = "deepseek-chat"

# diff 大小阈值：超过此值启用按文件分段分析
MAX_DIFF_CHARS = 50000
# 单文件 diff 也设上限，防止单个超大文件撑爆上下文
MAX_PER_FILE_CHARS = 30000


def _call_llm(system: str, user: str, max_tokens: int = 4096) -> str:
    """统一 LLM 调用"""
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content


def _truncate_diff(diff: str, max_chars: int = MAX_DIFF_CHARS) -> tuple[str, bool]:
    """截断过长的 diff，保留前面的内容"""
    if len(diff) <= max_chars:
        return diff, False
    truncated = diff[:max_chars]
    last_newline = truncated.rfind("\n")
    if last_newline > 0:
        truncated = truncated[:last_newline]
    truncated += (
        f"\n\n... (diff 内容已截断，原始大小 {len(diff)} 字符)"
    )
    return truncated, True


def _split_diff_by_file(diff: str) -> list[tuple[str, str]]:
    """将 unified diff 按文件拆分，返回 [(filename, file_diff), ...]

    diff 格式: diff --git a/path b/path
    """
    # 按 "diff --git " 分割，第一个是空（在第一个 diff --git 之前）
    parts = re.split(r"\n(?=diff --git )", diff)
    result = []
    for part in parts:
        if not part.strip():
            continue
        # 提取文件名：diff --git a/path/to/file b/path/to/file
        m = re.match(r"diff --git a/(.+) b/(.+)", part)
        if m:
            filename = m.group(1)
        else:
            filename = "unknown"
        result.append((filename, part.strip()))
    return result


def _analyze_single_file(filename: str, file_diff: str) -> dict:
    """分析单个文件的 diff"""
    diff, _ = _truncate_diff(file_diff, MAX_PER_FILE_CHARS)
    prompt = build_per_file_prompt(filename, diff)
    findings = _call_llm(PER_FILE_PROMPT, prompt, max_tokens=1024)
    return {"filename": filename, "findings": findings.strip()}


def analyze_pr(pr_data: dict) -> dict:
    """对 PR 进行 AI 分析，自动选择单次分析或分段分析

    Returns:
        {
            "summary": str, "risks": str, "suggestions": str, "overall": str,
            "raw": str, "truncated": bool, "model": str, "chunked": bool,
            "files_analyzed": int,
        }
    """
    diff = pr_data.get("diff", "")

    # 小 PR：单次分析
    if len(diff) <= MAX_DIFF_CHARS:
        return _analyze_single_pass(pr_data, diff)

    # 大 PR：按文件分段分析
    return _analyze_chunked(pr_data, diff)


def _analyze_single_pass(pr_data: dict, diff: str) -> dict:
    """单次分析（diff 在阈值内）"""
    diff, was_truncated = _truncate_diff(diff)
    prompt = build_analysis_prompt(pr_data, diff)
    raw = _call_llm(SYSTEM_PROMPT, prompt)
    sections = _parse_sections(raw)

    return {
        **sections,
        "raw": raw,
        "truncated": was_truncated,
        "model": MODEL,
        "chunked": False,
        "files_analyzed": pr_data.get("changed_files", 0),
    }


def _analyze_chunked(pr_data: dict, diff: str) -> dict:
    """分段分析：按文件拆分，逐文件分析，最后汇总"""
    file_chunks = _split_diff_by_file(diff)
    total_files = len(file_chunks)

    # 第一步：逐个文件分析
    per_file_results = []
    for filename, file_diff in file_chunks:
        result = _analyze_single_file(filename, file_diff)
        per_file_results.append(result)

    # 第二步：汇总所有文件的分析结果
    agg_prompt = build_aggregation_prompt(pr_data, per_file_results)
    raw = _call_llm(AGGREGATION_PROMPT, agg_prompt, max_tokens=4096)
    sections = _parse_sections(raw)

    return {
        **sections,
        "raw": raw,
        "truncated": False,  # 分段分析不截断
        "model": MODEL,
        "chunked": True,
        "files_analyzed": total_files,
    }


def _parse_sections(text: str) -> dict:
    """将 AI 输出的 Markdown 解析为四个部分"""
    result = {
        "summary": "",
        "risks": "",
        "suggestions": "",
        "overall": "",
    }

    current_section = None
    current_content: list[str] = []

    for line in text.split("\n"):
        if line.startswith("###") or line.startswith("##"):
            if current_section and current_content:
                result[current_section] = "\n".join(current_content).strip()
                current_content = []

            if "总结" in line:
                current_section = "summary"
            elif "风险" in line:
                current_section = "risks"
            elif "建议" in line:
                current_section = "suggestions"
            elif "总体评价" in line:
                current_section = "overall"
            else:
                current_section = None
        elif current_section:
            current_content.append(line)

    if current_section and current_content:
        result[current_section] = "\n".join(current_content).strip()

    return result
