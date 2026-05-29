# AI PR Review 助手

一款基于 AI 的 GitHub Pull Request 代码评审工具，帮助开发者提升 Review 效率与质量。

## 功能

- **PR 变更总结** — 自动概括 PR 的改动范围和核心逻辑
- **风险代码识别** — 按严重程度（严重/中等/轻微）标记潜在问题，含位置、影响分析和修复建议
- **Review 建议** — 按优先级排列的改进建议，覆盖代码质量/性能/安全/可维护性/测试
- **总体评价** — 一键判断是否建议合并，指出最需关注的风险点

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Streamlit |
| AI 引擎 | DeepSeek Chat API (OpenAI SDK 兼容模式) |
| 数据源 | GitHub REST API |
| 环境管理 | python-dotenv |

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/Yosemite3-gus/qiniu-intern.git
cd qiniu-intern

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY（必填）和 GITHUB_TOKEN（选填）

# 4. 启动
python -m streamlit run app.py
```

访问 http://localhost:8501，输入 GitHub PR 地址即可开始分析。

## 配置说明

| 环境变量 | 必填 | 说明 |
|----------|------|------|
| `DEEPSEEK_API_KEY` | 是 | DeepSeek API 密钥 |
| `DEEPSEEK_BASE_URL` | 否 | API 端点，默认 `https://api.deepseek.com/v1` |
| `GITHUB_TOKEN` | 否 | GitHub Token，提升 API 限流（60→5000次/小时） |

GitHub Token 获取：https://github.com/settings/tokens → Fine-grained token → Public Repositories (read-only)

## 项目结构

```
qiniu-intern/
├── app.py                      # Streamlit 主界面
├── services/
│   ├── github_service.py       # GitHub REST API 封装
│   ├── analyzer.py             # AI 分析引擎（DeepSeek）
│   └── prompts.py              # Prompt 模板设计
├── requirements.txt
├── .env.example
└── .gitignore
```

## 设计思路

### 模型选择

选用 **DeepSeek Chat**，原因：
- 128K 上下文窗口，可容纳大型 PR 的 diff 内容
- OpenAI SDK 兼容，接入成本低
- 代码理解能力强，尤其擅长中文技术文档输出
- 性价比高，适合个人开发者

### 上下文获取

通过 GitHub REST API 获取三种信息维度：
1. **PR 元数据** — 标题、描述、作者、分支关系
2. **文件清单** — 变更文件列表及统计（+/- 行数）
3. **Unified Diff** — 标准 git diff 格式，LLM 可直接理解

对超大 diff（>50000 字符）采用截断策略，优先保留文件头部内容，并在结果中标注"基于截断内容"。

### 未来扩展方向

- **增量分析** — 对 commit-by-commit 逐个分析，减少单次上下文压力
- **项目规范感知** — 读取仓库的 CONTRIBUTING.md / .eslintrc 等，给出符合项目风格的 Review
- **多模型对比** — 同时调用 DeepSeek / Qwen / GPT 进行交叉验证，降低单一模型误判
- **历史学习** — 记录 Reviewer 对 AI 建议的采纳/拒绝，逐步优化 prompt
- **CI 集成** — 提供 GitHub App 形态，PR 创建时自动触发分析并评论

## Demo 视频

> 待录制，上传后将链接更新至此。

## 许可证

MIT
