"""AI 分析引擎 — 调用 DeepSeek 进行 PR 代码评审"""
import os

from openai import OpenAI
from dotenv import load_dotenv

from services.prompts import SYSTEM_PROMPT, build_analysis_prompt

load_dotenv(override=True)

API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

if not API_KEY:
    raise RuntimeError("DEEPSEEK_API_KEY 未设置，请在 .env 中配置")

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
MODEL = "deepseek-chat"

# diff 最大长度（字符），超出则截断，保留模型上下文空间给分析和输出
MAX_DIFF_CHARS = 50000


def _truncate_diff(diff: str, max_chars: int = MAX_DIFF_CHARS) -> tuple[str, bool]:
    """截断过长的 diff，保留前面的内容（文件头通常更重要）"""
    if len(diff) <= max_chars:
        return diff, False
    truncated = diff[:max_chars]
    # 尝试在最后一个完整的行处截断
    last_newline = truncated.rfind("\n")
    if last_newline > 0:
        truncated = truncated[:last_newline]
    truncated += (
        f"\n\n... (diff 内容已截断，原始大小 {len(diff)} 字符，"
        f"当前显示 {len(truncated)} 字符)"
    )
    return truncated, True


def analyze_pr(pr_data: dict) -> dict:
    """对 PR 进行 AI 分析，返回结构化结果

    Args:
        pr_data: fetch_pr_full() 返回的完整 PR 数据

    Returns:
        {
            "summary": str,        # PR 变更总结
            "risks": str,          # 风险代码识别
            "suggestions": str,    # Review 建议
            "overall": str,        # 总体评价
            "raw": str,            # 原始 AI 回复
            "truncated": bool,     # diff 是否被截断
            "model": str,          # 使用的模型
        }
    """
    diff, was_truncated = _truncate_diff(pr_data.get("diff", ""))
    prompt = build_analysis_prompt(pr_data, diff)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,  # 低温度，让输出更一致
        max_tokens=4096,
    )

    raw_output = response.choices[0].message.content

    # 解析 AI 回复中的四个部分
    sections = _parse_sections(raw_output)

    return {
        **sections,
        "raw": raw_output,
        "truncated": was_truncated,
        "model": MODEL,
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
        line_lower = line.strip().lower()
        if line.startswith("###") or line.startswith("##"):
            # 保存上一个 section
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

    # 保存最后一个 section
    if current_section and current_content:
        result[current_section] = "\n".join(current_content).strip()

    return result
