"""工具模块 — 网络容错、重试机制、报告生成"""
import time
import functools
from datetime import datetime, timezone, timedelta

import requests

# 北京时间
CST = timezone(timedelta(hours=8))


def retry_on_network_error(max_retries: int = 3, base_delay: float = 1.0):
    """装饰器：网络异常时自动重试，指数退避

    Args:
        max_retries: 最大重试次数（不含首次调用）
        base_delay: 基础等待秒数，每次重试翻倍（1s → 2s → 4s）
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except requests.ConnectionError as e:
                    last_error = e
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        time.sleep(delay)
                except requests.Timeout as e:
                    last_error = e
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        time.sleep(delay)
                except requests.HTTPError as e:
                    # 5xx 服务端错误才重试，4xx 客户端错误不重试
                    if e.response is not None and e.response.status_code >= 500:
                        last_error = e
                        if attempt < max_retries:
                            delay = base_delay * (2 ** attempt)
                            time.sleep(delay)
                    else:
                        raise
            raise last_error  # type: ignore
        return wrapper
    return decorator


def generate_report(pr_data: dict, result: dict) -> str:
    """生成 Markdown 格式的 Review 报告"""
    now = datetime.now(CST).strftime("%Y-%m-%d %H:%M")
    mode = "分段分析" if result.get("chunked") else "单次分析"

    lines = [
        f"# AI PR Review 报告",
        "",
        f"**PR**: [{pr_data['title']}]({pr_data['url']})",
        f"**作者**: {pr_data['author']}",
        f"**分支**: {pr_data['head_branch']} → {pr_data['base_branch']}",
        f"**分析时间**: {now} (北京时间)",
        f"**分析模型**: {result['model']}",
        f"**分析模式**: {mode}",
        f"**变更规模**: {pr_data['changed_files']} 个文件, +{pr_data['additions']} -{pr_data['deletions']} 行",
        "",
        "---",
        "",
    ]

    sections = [
        ("## PR 变更总结", result.get("summary", "")),
        ("## 风险代码识别", result.get("risks", "")),
        ("## Review 建议", result.get("suggestions", "")),
        ("## 总体评价", result.get("overall", "")),
    ]

    for heading, content in sections:
        lines.append(heading)
        lines.append("")
        if content.strip():
            lines.append(content)
        else:
            lines.append("（无内容）")
        lines.append("")

    lines.append("---")
    lines.append("*由 AI PR Review 助手生成*")

    return "\n".join(lines)
