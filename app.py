"""AI PR Review 助手 — Streamlit 主界面"""
import streamlit as st

from services.router import fetch_pr_full
from services.analyzer import analyze_pr
from services.utils import generate_report
from services.history import save_analysis, load_history, delete_analysis

st.set_page_config(
    page_title="AI PR Review",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 样式 ──────────────────────────────────────────────
st.markdown("""
<style>
/* 全局暗色背景 */
.stApp {
    background: linear-gradient(135deg, #0a0e1a 0%, #0d1525 40%, #0f1629 100%);
}
.stApp > header { background: transparent !important; }

/* Hero */
.hero { text-align: center; padding: 2rem 0 1.5rem; }
.hero h1 {
    font-size: 2.6rem;
    font-weight: 800;
    background: linear-gradient(135deg, #60a5fa, #34d399);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.3rem;
}
.hero p { color: #94a3b8; font-size: 1.05rem; }

/* 输入区 */
.input-section {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
}
.input-section label { color: #cbd5e1 !important; font-weight: 600; }

/* 结果卡片 */
.section-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1rem;
}
.section-card h3 { margin-top: 0; color: #e2e8f0; }

/* 风险标记 */
.risk-high { color: #f87171; font-weight: 700; }
.risk-medium { color: #fbbf24; font-weight: 700; }
.risk-low { color: #4ade80; font-weight: 700; }

/* PR 信息条 */
.pr-meta {
    display: flex; gap: 1.5rem; flex-wrap: wrap;
    color: #94a3b8; font-size: 0.9rem;
}
.pr-meta span { background: rgba(255,255,255,0.05); padding: 0.25rem 0.75rem; border-radius: 20px; }
</style>
""", unsafe_allow_html=True)

# ── 侧边栏：分析历史 ────────────────────────────────
with st.sidebar:
    st.markdown("###  分析历史")

    # "新建分析"按钮 — 清空选中状态
    if st.button(" 新建分析", use_container_width=True, type="primary"):
        st.session_state.pop("selected_history", None)
        st.rerun()

    st.divider()

    history = load_history()
    if not history:
        st.caption("暂无历史记录，完成一次分析后自动保存。")
    else:
        for i, entry in enumerate(history):
            col1, col2 = st.columns([5, 1])
            with col1:
                label = f"{entry['pr_title'][:30]}..."
                if st.button(label, key=f"hist_{entry['id']}", use_container_width=True):
                    st.session_state["selected_history"] = entry
                    st.rerun()
            with col2:
                if st.button(" ", key=f"del_{entry['id']}", help="删除此记录"):
                    delete_analysis(entry["id"])
                    st.session_state.pop("selected_history", None)
                    st.rerun()
            st.caption(f"{entry['timestamp']} | {entry.get('platform', 'github')}")

# ── Hero ──────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <h1>AI PR Review 助手</h1>
    <p>输入 GitHub PR 链接，AI 自动分析代码变更 — 总结 · 风险识别 · Review 建议</p>
</div>
""", unsafe_allow_html=True)

# ── 历史记录回看 ──────────────────────────────────────
selected = st.session_state.get("selected_history")
if selected:
    st.info(f" 正在查看历史分析: **{selected['pr_title']}** ({selected['timestamp']})")

    r = selected["result"]
    pr_url_display = selected.get("pr_url", "")

    st.markdown(f"""
    <div class="pr-meta">
        <span>{selected.get('pr_author', '')}</span>
        <span>{selected.get('head_branch', '')} → {selected.get('base_branch', '')}</span>
        <span>{selected.get('changed_files', 0)} 文件</span>
        <span style="color:#4ade80">+{selected.get('additions', 0)}</span>
        <span style="color:#f87171">-{selected.get('deletions', 0)}</span>
    </div>
    """, unsafe_allow_html=True)

    if r.get("compare_mode"):
        _render_compare_history(r)
    else:
        _render_single_history(r)

    st.caption(f"分析模型: {r.get('model', 'N/A')} | 分析时间: {selected['timestamp']}")
    st.stop()  # 不显示下方的输入区

# ── 输入区 ────────────────────────────────────────────
st.markdown('<div class="input-section">', unsafe_allow_html=True)
pr_url = st.text_input(
    "GitHub PR 地址",
    placeholder="https://github.com/owner/repo/pull/123",
    label_visibility="collapsed",
)
col1, col2, col3 = st.columns([1, 1, 4])
with col1:
    analyze_btn = st.button("开始分析", type="primary", use_container_width=True)
with col2:
    # 清空按钮（实际上就是重新加载）
    pass
st.markdown('</div>', unsafe_allow_html=True)

# ── 分析逻辑 ──────────────────────────────────────────
if analyze_btn and pr_url.strip():
    try:
        # Step 1: 获取 PR 数据
        with st.status("正在获取 PR 信息...", expanded=False) as status:
            pr_data = fetch_pr_full(pr_url.strip())
            status.update(label="PR 信息获取完成", state="complete", expanded=False)

        # Step 2: AI 分析
        with st.status(f"正在用 AI 分析 {pr_data['changed_files']} 个文件...", expanded=False) as status:
            result = analyze_pr(pr_data)
            status.update(label="AI 分析完成", state="complete", expanded=False)

        # 自动保存到历史记录
        save_analysis(pr_data, result)

        # ── 结果展示 ──────────────────────────────

        # PR 基本信息条
        st.markdown(f"""
        <div class="pr-meta">
            <span>{pr_data['author']}</span>
            <span>{pr_data['head_branch']} → {pr_data['base_branch']}</span>
            <span>{pr_data['changed_files']} 文件</span>
            <span style="color:#4ade80">+{pr_data['additions']}</span>
            <span style="color:#f87171">-{pr_data['deletions']}</span>
            <span>状态: {pr_data['state']}</span>
        </div>
        """, unsafe_allow_html=True)

        if result.get("chunked"):
            st.success(f"已启用分段分析模式，逐文件分析了 {result['files_analyzed']} 个文件后汇总")
        elif result["truncated"]:
            st.warning("diff 内容过长已截断，分析基于部分变更。建议对大型 PR 拆分为多个小 PR。")

        st.divider()

        # 四个分析栏目
        tab1, tab2, tab3, tab4 = st.tabs([
            " PR 变更总结",
            " 风险代码识别",
            " Review 建议",
            " 总体评价",
        ])

        with tab1:
            if result["summary"]:
                st.markdown(result["summary"])
            else:
                st.info("AI 未输出此部分")

        with tab2:
            if result["risks"]:
                # 给风险内容加上颜色标记
                colored = result["risks"]
                colored = colored.replace("严重", '<span class="risk-high">严重</span>')
                colored = colored.replace("中等", '<span class="risk-medium">中等</span>')
                colored = colored.replace("轻微", '<span class="risk-low">轻微</span>')
                st.markdown(colored, unsafe_allow_html=True)
            else:
                st.success("未发现明显的风险代码")

        with tab3:
            if result["suggestions"]:
                st.markdown(result["suggestions"])
            else:
                st.info("AI 未输出此部分")

        with tab4:
            if result["overall"]:
                st.markdown(result["overall"])
            else:
                st.info("AI 未输出此部分")

        # 原始输出（折叠）
        with st.expander(" 查看 AI 原始输出"):
            st.code(result["raw"], language="markdown")

        # 下载报告
        report_md = generate_report(pr_data, result)
        st.download_button(
            label=" 下载 Markdown 报告",
            data=report_md,
            file_name=f"PR-Review-{pr_data['repo']}-#{pr_data['pr_number']}.md",
            mime="text/markdown",
            use_container_width=True,
        )

        st.caption(f"分析模型: {result['model']}")

    except ValueError as e:
        st.error(f"输入错误: {e}")
    except Exception as e:
        st.error(f"分析失败: {e}")

elif analyze_btn and not pr_url.strip():
    st.warning("请输入 GitHub PR 地址")


# ── 历史记录渲染 ──────────────────────────────────────

def _render_single_history(r: dict):
    """从历史记录渲染单模型结果"""
    tab1, tab2, tab3, tab4 = st.tabs([
        " PR 变更总结", " 风险代码识别", " Review 建议", " 总体评价",
    ])
    with tab1:
        st.markdown(r.get("summary", "（无内容）"))
    with tab2:
        risks = r.get("risks", "")
        if risks:
            risks = risks.replace("严重", '<span class="risk-high">严重</span>')
            risks = risks.replace("中等", '<span class="risk-medium">中等</span>')
            risks = risks.replace("轻微", '<span class="risk-low">轻微</span>')
            st.markdown(risks, unsafe_allow_html=True)
        else:
            st.success("未发现明显的风险代码")
    with tab3:
        st.markdown(r.get("suggestions", "（无内容）"))
    with tab4:
        st.markdown(r.get("overall", "（无内容）"))

    with st.expander(" 查看 AI 原始输出"):
        st.code(r.get("raw", ""), language="markdown")


def _render_compare_history(r: dict):
    """从历史记录渲染多模型对比结果"""
    ds = r.get("deepseek", {})
    qw = r.get("qwen")

    tab1, tab2, tab3, tab4 = st.tabs([
        " PR 变更总结", " 风险代码识别", " Review 建议", " 总体评价",
    ])

    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**DeepSeek**")
            st.markdown(ds.get("summary", "（无内容）"))
        with c2:
            st.markdown("**Qwen**")
            st.markdown(qw.get("summary", "（无内容）") if qw else "Qwen 未配置")

    with tab2:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**DeepSeek**")
            risks = ds.get("risks", "")
            if risks:
                risks = risks.replace("严重", '<span class="risk-high">严重</span>')
                risks = risks.replace("中等", '<span class="risk-medium">中等</span>')
                risks = risks.replace("轻微", '<span class="risk-low">轻微</span>')
                st.markdown(risks, unsafe_allow_html=True)
            else:
                st.success("未发现")
        with c2:
            st.markdown("**Qwen**")
            if qw:
                risks = qw.get("risks", "")
                if risks:
                    risks = risks.replace("严重", '<span class="risk-high">严重</span>')
                    risks = risks.replace("中等", '<span class="risk-medium">中等</span>')
                    risks = risks.replace("轻微", '<span class="risk-low">轻微</span>')
                    st.markdown(risks, unsafe_allow_html=True)
                else:
                    st.success("未发现")
            else:
                st.warning("Qwen 未配置")

    with tab3:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**DeepSeek**")
            st.markdown(ds.get("suggestions", "（无内容）"))
        with c2:
            st.markdown("**Qwen**")
            st.markdown(qw.get("suggestions", "（无内容）") if qw else "Qwen 未配置")

    with tab4:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**DeepSeek**")
            st.markdown(ds.get("overall", "（无内容）"))
        with c2:
            st.markdown("**Qwen**")
            st.markdown(qw.get("overall", "（无内容）") if qw else "Qwen 未配置")

    with st.expander(" 查看 AI 原始输出"):
        ca, cb = st.columns(2)
        with ca:
            st.caption(f"DeepSeek ({ds.get('model', '')})")
            st.code(ds.get("raw", ""), language="markdown")
        with cb:
            if qw:
                st.caption(f"Qwen ({qw.get('model', '')})")
                st.code(qw.get("raw", ""), language="markdown")
            else:
                st.warning("Qwen 未配置")
