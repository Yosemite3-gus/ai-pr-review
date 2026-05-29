"""AI 分析引擎 — 调用 DeepSeek 进行 PR 代码评审"""
import os
import re
import time

from openai import OpenAI, APIError, APIConnectionError, APITimeoutError
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

deepseek_client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
DEEPSEEK_MODEL = "deepseek-chat"

# 百炼 Qwen 客户端（用于多模型对比）
BAILIAN_API_KEY = os.getenv("BAILIAN_API_KEY", "")
BAILIAN_BASE_URL = os.getenv("BAILIAN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
BAILIAN_MODEL = os.getenv("BAILIAN_MODEL", "qwen-plus")

bailian_client = None
if BAILIAN_API_KEY:
    bailian_client = OpenAI(api_key=BAILIAN_API_KEY, base_url=BAILIAN_BASE_URL)

# diff 大小阈值：超过此值启用按文件分段分析
MAX_DIFF_CHARS = 50000
# 单文件 diff 也设上限，防止单个超大文件撑爆上下文
MAX_PER_FILE_CHARS = 30000


def _call_llm_with_client(client: OpenAI, model: str, system: str, user: str,
                          max_tokens: int = 4096, max_retries: int = 3) -> str:
    """通用 LLM 调用，支持任意 OpenAI 兼容客户端"""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.3,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content
        except (APIConnectionError, APITimeoutError) as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(2 ** attempt)
        except APIError as e:
            if e.status_code is not None and e.status_code >= 500 and attempt < max_retries:
                last_error = e
                time.sleep(2 ** attempt)
            else:
                raise

    raise last_error  # type: ignore


def _call_llm(system: str, user: str, max_tokens: int = 4096, max_retries: int = 3) -> str:
    """DeepSeek LLM 调用（向后兼容）"""
    return _call_llm_with_client(deepseek_client, DEEPSEEK_MODEL, system, user, max_tokens, max_retries)


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


def _analyze_single_file(filename: str, file_diff: str, client: OpenAI, model: str) -> dict:
    """分析单个文件的 diff"""
    diff, _ = _truncate_diff(file_diff, MAX_PER_FILE_CHARS)
    prompt = build_per_file_prompt(filename, diff)
    findings = _call_llm_with_client(client, model, PER_FILE_PROMPT, prompt, max_tokens=1024)
    return {"filename": filename, "findings": findings.strip()}


def analyze_pr(pr_data: dict) -> dict:
    """对 PR 进行 AI 分析（DeepSeek），自动选择单次分析或分段分析

    Returns:
        {
            "summary": str, "risks": str, "suggestions": str, "overall": str,
            "raw": str, "truncated": bool, "model": str, "chunked": bool,
            "files_analyzed": int,
        }
    """
    return _analyze_pr_with_model(pr_data, deepseek_client, DEEPSEEK_MODEL)


def analyze_pr_compare(pr_data: dict) -> dict:
    """多模型对比分析：DeepSeek + Qwen 分别分析，返回对比结果

    Returns:
        {
            "deepseek": {...}, "qwen": {...} 或 None,
            "truncated": bool, "chunked": bool, "files_analyzed": int,
            "compare_mode": True,
        }
    """
    diff = pr_data.get("diff", "")
    is_chunked = len(diff) > MAX_DIFF_CHARS

    # DeepSeek 分析（始终可用）
    deepseek_result = _analyze_pr_with_model(pr_data, deepseek_client, DEEPSEEK_MODEL)

    # Qwen 分析（如果百炼未配置则跳过）
    qwen_result = None
    if bailian_client:
        qwen_result = _analyze_pr_with_model(pr_data, bailian_client, BAILIAN_MODEL)

    return {
        "deepseek": deepseek_result,
        "qwen": qwen_result,
        "truncated": deepseek_result.get("truncated", False),
        "chunked": is_chunked,
        "files_analyzed": deepseek_result.get("files_analyzed", 0),
        "compare_mode": True,
    }


def _analyze_pr_with_model(pr_data: dict, client: OpenAI, model: str) -> dict:
    """使用指定模型分析 PR"""
    diff = pr_data.get("diff", "")

    if len(diff) <= MAX_DIFF_CHARS:
        return _analyze_single_pass(pr_data, diff, client, model)

    return _analyze_chunked(pr_data, diff, client, model)


def _analyze_single_pass(pr_data: dict, diff: str, client: OpenAI, model: str) -> dict:
    """单次分析（diff 在阈值内）"""
    diff, was_truncated = _truncate_diff(diff)
    prompt = build_analysis_prompt(pr_data, diff)
    raw = _call_llm_with_client(client, model, SYSTEM_PROMPT, prompt)
    sections = _parse_sections(raw)

    return {
        **sections,
        "raw": raw,
        "truncated": was_truncated,
        "model": model,
        "chunked": False,
        "files_analyzed": pr_data.get("changed_files", 0),
    }


def _analyze_chunked(pr_data: dict, diff: str, client: OpenAI, model: str) -> dict:
    """分段分析：按文件拆分，逐文件分析，最后汇总"""
    file_chunks = _split_diff_by_file(diff)
    total_files = len(file_chunks)

    per_file_results = []
    for filename, file_diff in file_chunks:
        result = _analyze_single_file(filename, file_diff, client, model)
        per_file_results.append(result)

    agg_prompt = build_aggregation_prompt(pr_data, per_file_results)
    raw = _call_llm_with_client(client, model, AGGREGATION_PROMPT, agg_prompt, max_tokens=4096)
    sections = _parse_sections(raw)

    return {
        **sections,
        "raw": raw,
        "truncated": False,
        "model": model,
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
