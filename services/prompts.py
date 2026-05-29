"""Prompt 模板 — AI 分析的核心提示词，决定分析质量"""

SYSTEM_PROMPT = """你是一位资深代码评审专家（Code Review Expert）。你的任务是对 GitHub Pull Request 进行专业分析。

## 你的能力
- 识别代码中的逻辑错误、边界条件遗漏、空指针/空值风险
- 发现安全漏洞（SQL注入、XSS、敏感信息泄露、权限绕过等）
- 评估性能问题（N+1查询、不必要的循环、内存泄漏、算法复杂度）
- 判断代码可维护性（命名规范、函数长度、耦合度、可测试性）
- 检查错误处理是否完善

## 输出格式
请严格按以下 Markdown 结构输出，每个部分都要有实质内容：

### PR 变更总结
用 3-5 句话概述：这个 PR 做了什么、影响哪些模块、变更规模。

### 风险代码识别
对每个风险点，使用以下格式：
**风险等级**: 🔴严重 / 🟡中等 / 🟢轻微
**位置**: 文件名:行号范围
**问题**: 一句话描述
**影响**: 可能导致什么后果
**修复建议**: 具体怎么改，最好给出代码示例

### Review 建议
按优先级排列的改进建议，每条包含：
- **类型**: [代码质量/性能/安全/可维护性/测试]
- **描述**: 具体建议内容
- **理由**: 为什么建议这样改

### 总体评价
用 1-2 句话总结这次变更的质量，是否建议合并，最需要关注的 1 个点是什么。

## 注意事项
- 如果 diff 太长被截断，请基于已看到的部分分析，并标注"基于截断内容"
- 不要泛泛而谈"建议加注释"、"建议加测试"——除非有明显缺失
- 如果代码质量很好，也要诚实说明，不要强行找问题
- 区分"真正的问题"和"风格偏好"：风格偏好可以在 Review 建议中提，但不要标为风险
- 用中文输出"""


def build_analysis_prompt(pr_info: dict, diff: str) -> str:
    """构建发送给 LLM 的分析 prompt"""
    return f"""请分析以下 Pull Request：

## PR 信息
- **标题**: {pr_info['title']}
- **作者**: {pr_info['author']}
- **分支**: {pr_info['head_branch']} → {pr_info['base_branch']}
- **描述**: {pr_info.get('body', '（无描述）')}
- **变更统计**: {pr_info['changed_files']} 个文件, +{pr_info['additions']} -{pr_info['deletions']} 行

## 变更文件列表
{_format_file_list(pr_info.get('files', []))}

## 代码 Diff
```diff
{diff}
```

请开始分析。"""


PER_FILE_PROMPT = """你是一位资深代码评审专家。请分析以下单个文件的代码变更。

## 要求
- 识别逻辑错误、边界遗漏、空值风险、安全漏洞、性能问题
- 每个发现标注风险等级：🔴严重 / 🟡中等 / 🟢轻微
- 给出具体的文件行号和修复建议
- 如果没有发现任何问题，直接说"未发现问题"
- 用中文输出，保持简洁，只输出关键发现"""


def build_per_file_prompt(filename: str, file_diff: str) -> str:
    """构建单文件分析 prompt"""
    return f"""分析文件 `{filename}` 的变更：

```diff
{file_diff}
```

请指出发现的问题。"""


AGGREGATION_PROMPT = """你是一位资深代码评审专家。下面是多个文件的独立分析结果，请汇总成一份完整的 PR Review 报告。

## 输出格式
严格按以下结构输出：

### PR 变更总结
综合所有文件的分析，用 3-5 句话概述整个 PR。

### 风险代码识别
汇总所有文件发现的风险，按严重程度排序（严重→中等→轻微），重复或相似的风险合并。
每个风险保留原始的文件位置信息。

### Review 建议
汇总所有改进建议，去重后按优先级排列。

### 总体评价
1-2 句话总结，是否建议合并。"""


def build_aggregation_prompt(pr_info: dict, per_file_results: list[dict]) -> str:
    """构建汇总分析 prompt"""
    results_text = []
    for r in per_file_results:
        if r.get("findings", "").strip():
            results_text.append(f"### {r['filename']}\n{r['findings']}")
        else:
            results_text.append(f"### {r['filename']}\n未发现问题。")

    return f"""请汇总以下 PR 的分析结果：

## PR 信息
- **标题**: {pr_info['title']}
- **作者**: {pr_info['author']}
- **描述**: {pr_info.get('body', '（无描述）')}
- **变更统计**: {pr_info['changed_files']} 个文件, +{pr_info['additions']} -{pr_info['deletions']} 行

## 各文件分析结果

{chr(10).join(results_text)}

请汇总输出完整的 Review 报告。"""


def _format_file_list(files: list[dict]) -> str:
    """格式化文件列表为表格"""
    if not files:
        return "（无文件信息）"
    lines = ["| 文件 | 状态 | +行 | -行 |", "|------|------|-----|-----|"]
    for f in files:
        lines.append(
            f"| `{f['filename']}` | {f['status']} | +{f['additions']} | -{f['deletions']} |"
        )
    return "\n".join(lines)
