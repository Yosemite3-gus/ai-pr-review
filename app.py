"""AI PR Review 助手 — Streamlit 主界面"""
import streamlit as st

from services.router import fetch_pr_full
from services.analyzer import analyze_pr, analyze_pr_compare
from services.utils import generate_report, generate_compare_report
from services.history import save_analysis, load_history, delete_analysis

THREEJS_HTML = r"""
<!DOCTYPE html>
<html>
<head>
<style>
    body { margin: 0; overflow: hidden; background: #fafafa; }
    canvas { display: block; }
</style>
</head>
<body>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js">
</script>
<script>
(function() {
    var PARTICLE_COUNT = 800;
    var RADIUS = 2.2;

    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(60, 1, 0.1, 100);
    camera.position.z = 5;

    var renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setClearColor(0xfafafa, 1);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    // Soft dot texture
    var texCanvas = document.createElement('canvas');
    texCanvas.width = 32; texCanvas.height = 32;
    var ctx = texCanvas.getContext('2d');
    var gradient = ctx.createRadialGradient(16, 16, 0, 16, 16, 16);
    gradient.addColorStop(0, 'rgba(0,0,0,1)');
    gradient.addColorStop(0.25, 'rgba(0,0,0,0.9)');
    gradient.addColorStop(0.6, 'rgba(0,0,0,0.4)');
    gradient.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, 32, 32);
    var dotTexture = new THREE.CanvasTexture(texCanvas);

    var geometry = new THREE.BufferGeometry();
    var positions = new Float32Array(PARTICLE_COUNT * 3);
    var colors = new Float32Array(PARTICLE_COUNT * 3);

    for (var i = 0; i < PARTICLE_COUNT; i++) {
        var theta = Math.random() * Math.PI * 2;
        var phi = Math.acos(2 * Math.random() - 1);
        var x = RADIUS * Math.sin(phi) * Math.cos(theta);
        var y = RADIUS * Math.sin(phi) * Math.sin(theta);
        var z = RADIUS * Math.cos(phi);

        positions[i * 3] = x;
        positions[i * 3 + 1] = y;
        positions[i * 3 + 2] = z;

        // Left bright, right dark gradient
        var t = (x + RADIUS) / (2 * RADIUS);
        var shade = 0.85 - t * 0.73;
        colors[i * 3] = shade;
        colors[i * 3 + 1] = shade;
        colors[i * 3 + 2] = shade;
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    var material = new THREE.PointsMaterial({
        size: 0.06,
        map: dotTexture,
        vertexColors: true,
        blending: THREE.NormalBlending,
        depthWrite: false,
        transparent: true,
        opacity: 0.7,
    });

    var sphere = new THREE.Points(geometry, material);
    scene.add(sphere);

    function animate() {
        requestAnimationFrame(animate);
        sphere.rotation.y += 0.002;
        sphere.rotation.x += 0.0005;
        renderer.render(scene, camera);
    }

    function resize() {
        var container = document.body;
        var w = container.clientWidth;
        var h = container.clientHeight;
        var size = Math.min(w, h);
        renderer.setSize(size, size);
    }
    window.addEventListener('resize', resize);
    resize();
    animate();
})();
</script>
</body>
</html>
"""

st.set_page_config(
    page_title="AI PR Review",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 样式 ──────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* 全局 */
html, body, .stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background-color: #fafafa;
}
.stApp {
    background-image:
        linear-gradient(rgba(0, 0, 0, 0.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0, 0, 0, 0.04) 1px, transparent 1px);
    background-size: 40px 40px;
    background-position: center center;
}
.stApp > header { background: transparent !important; }

/* Hero */
.hero { padding: 1.5rem 0 1rem; }
.hero h1 {
    font-size: 2.8rem;
    font-weight: 800;
    color: #1a1a1a;
    letter-spacing: -0.02em;
    line-height: 1.1;
    margin-bottom: 0.3rem;
}
.hero p { color: #666666; font-size: 1rem; line-height: 1.5; }
.hero .label-tag {
    display: inline-block;
    font-family: 'SF Mono', 'Fira Code', 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    color: #888888;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.5rem;
}
.hero .label-tag::before {
    content: "—— ";
    color: #cccccc;
}

/* 输入区 */
.input-section {
    background: #ffffff;
    border: 1px solid #e5e5e5;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
}

/* 结果卡片 */
.section-card {
    background: #ffffff;
    border: 1px solid #e5e5e5;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1rem;
}
.section-card h3 { margin-top: 0; color: #1a1a1a; }

/* 风险标记 */
.risk-high { color: #dc2626; font-weight: 700; }
.risk-medium { color: #d97706; font-weight: 700; }
.risk-low { color: #16a34a; font-weight: 700; }

/* PR 信息条 */
.pr-meta {
    display: flex; gap: 0.75rem; flex-wrap: wrap;
    color: #666666; font-size: 0.85rem; margin: 0.75rem 0;
}
.pr-meta span {
    background: transparent;
    border: 1px solid #d4d4d4;
    padding: 0.2rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.78rem;
    color: #555555;
}

/* 统计信息条 */
.stats-bar {
    padding: 0.75rem 1rem;
    border-top: 1px solid #e5e5e5;
    display: flex; gap: 1rem; flex-wrap: wrap;
    font-size: 0.75rem;
    font-family: 'SF Mono', 'Fira Code', 'JetBrains Mono', monospace;
    color: #888888; margin-top: 1.5rem;
}
.stats-sep { color: #d4d4d4; }

/* 按钮 — 胶囊形 */
.stButton > button {
    border-radius: 9999px !important;
    font-family: 'Inter', sans-serif;
    font-weight: 600; font-size: 0.875rem;
    padding: 0.5rem 1.5rem;
    border: 1.5px solid #1a1a1a;
    background: #1a1a1a;
    color: #ffffff;
    transition: all 0.15s ease;
}
.stButton > button:hover {
    background: #333333;
    border-color: #333333;
}
.stButton > button[kind="secondary"] {
    background: transparent;
    color: #1a1a1a;
    border: 1.5px solid #d4d4d4;
}

/* 下载按钮 */
.stDownloadButton > button {
    border-radius: 9999px !important;
    border: 1.5px solid #d4d4d4;
    background: transparent;
    color: #1a1a1a;
    font-weight: 600;
    font-family: 'Inter', sans-serif;
}
.stDownloadButton > button:hover {
    border-color: #1a1a1a;
    color: #1a1a1a;
    background: #f5f5f5;
}

/* 输入框 */
.stTextInput > div > div > input {
    border-radius: 12px;
    border: 1.5px solid #e5e5e5;
    background: #ffffff;
    font-family: 'Inter', sans-serif;
    font-size: 0.9rem;
    padding: 0.75rem 1rem;
}
.stTextInput > div > div > input:focus {
    border-color: #1a1a1a;
    box-shadow: none;
}

/* Tabs — 下划线风格 */
.stTabs [data-baseweb="tab-list"] {
    gap: 2rem;
    border-bottom: 1px solid #e5e5e5;
}
.stTabs [data-baseweb="tab"] {
    font-family: 'Inter', sans-serif;
    font-weight: 500;
    font-size: 0.9rem;
    color: #999999;
    background: transparent;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    padding: 0.5rem 0;
}
.stTabs [aria-selected="true"] {
    color: #1a1a1a;
    border-bottom-color: #1a1a1a;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #ffffff;
    border-right: 1px solid #e5e5e5;
}

/* Checkbox */
.stCheckbox label {
    font-family: 'Inter', sans-serif;
    color: #1a1a1a;
}

/* Expander */
.stExpander {
    border: 1px solid #e5e5e5;
    border-radius: 12px;
}

/* Success/Warning/Info/Error 提示条 */
[data-testid="stNotification"] {
    border-radius: 12px;
}
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
hero_left, hero_right = st.columns([3, 2])
with hero_left:
    st.markdown("""
    <div class="hero">
        <div class="label-tag">AI Code Review Platform</div>
        <h1>AI PR Review</h1>
        <p>输入 GitHub / Gitee PR 链接，AI 自动分析代码变更 — 总结 · 风险识别 · Review 建议</p>
    </div>
    """, unsafe_allow_html=True)
with hero_right:
    st.components.v1.html(THREEJS_HTML, height=420)

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
        <span style="color:#16a34a">+{selected.get('additions', 0)}</span>
        <span style="color:#dc2626">-{selected.get('deletions', 0)}</span>
    </div>
    """, unsafe_allow_html=True)

    if r.get("compare_mode"):
        _render_compare_history(r)
    else:
        _render_single_history(r)

    st.caption(f"分析模型: {r.get('model', 'N/A')} | 分析时间: {selected['timestamp']}")
    st.stop()  # 不显示下方的输入区

# ── 输入区 ────────────────────────────────────────────
pr_url = st.text_input(
    "PR 地址",
    placeholder="https://github.com/owner/repo/pull/123",
    label_visibility="collapsed",
)
col1, col2, col3 = st.columns([1, 1, 3])
with col1:
    analyze_btn = st.button("Start Analysis", type="primary", use_container_width=True)
with col2:
    compare_mode = st.checkbox("Multi-model", help="DeepSeek + Qwen 交叉验证")

# ── 分析逻辑 ──────────────────────────────────────────
if analyze_btn and pr_url.strip():
    try:
        # Step 1: 获取 PR 数据
        with st.status("正在获取 PR 信息...", expanded=False) as status:
            pr_data = fetch_pr_full(pr_url.strip())
            status.update(label="PR 信息获取完成", state="complete", expanded=False)

        # Step 2: AI 分析
        if compare_mode:
            with st.status("正在用 DeepSeek + Qwen 双模型分析...", expanded=False) as status:
                result = analyze_pr_compare(pr_data)
                status.update(label="双模型分析完成", state="complete", expanded=False)
        else:
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
            <span style="color:#16a34a">+{pr_data['additions']}</span>
            <span style="color:#dc2626">-{pr_data['deletions']}</span>
            <span>状态: {pr_data['state']}</span>
        </div>
        """, unsafe_allow_html=True)

        if not compare_mode:
            if result.get("chunked"):
                st.success(f"已启用分段分析模式，逐文件分析了 {result['files_analyzed']} 个文件后汇总")
            elif result["truncated"]:
                st.warning("diff 内容过长已截断，分析基于部分变更。建议对大型 PR 拆分为多个小 PR。")

        st.divider()

        if compare_mode:
            # ── 对比模式：四个 tab，每个内部左右两栏 ──
            _render_compare_result(result)
        else:
            # ── 单模型模式：原有逻辑 ──
            _render_single_result(result)

        # 原始输出（折叠）
        with st.expander(" 查看 AI 原始输出"):
            if compare_mode:
                col_a, col_b = st.columns(2)
                with col_a:
                    st.caption(f"DeepSeek ({result['deepseek']['model']})")
                    st.code(result["deepseek"]["raw"], language="markdown")
                with col_b:
                    if result["qwen"]:
                        st.caption(f"Qwen ({result['qwen']['model']})")
                        st.code(result["qwen"]["raw"], language="markdown")
                    else:
                        st.warning("Qwen 未配置（缺少 BAILIAN_API_KEY）")
            else:
                st.code(result["raw"], language="markdown")

        # 下载报告
        if compare_mode:
            report_md = generate_compare_report(pr_data, result)
        else:
            report_md = generate_report(pr_data, result)
        st.download_button(
            label=" 下载 Markdown 报告",
            data=report_md,
            file_name=f"PR-Review-{pr_data['repo']}-#{pr_data['pr_number']}.md",
            mime="text/markdown",
            use_container_width=True,
        )

        # 统计信息条
        model_label = ""
        if compare_mode:
            model_label = f"DeepSeek + Qwen"
        else:
            model_label = result.get('model', 'N/A')
        st.markdown(f"""
        <div class="stats-bar">
            <span>PR #{pr_data['pr_number']}</span>
            <span class="stats-sep">|</span>
            <span>{pr_data['changed_files']} files</span>
            <span class="stats-sep">|</span>
            <span style="color:#16a34a">+{pr_data['additions']}</span>
            <span class="stats-sep">|</span>
            <span style="color:#dc2626">-{pr_data['deletions']}</span>
            <span class="stats-sep">|</span>
            <span>{pr_data['head_branch']} → {pr_data['base_branch']}</span>
            <span class="stats-sep">|</span>
            <span>Model: {model_label}</span>
        </div>
        """, unsafe_allow_html=True)

    except ValueError as e:
        st.error(f"输入错误: {e}")
    except Exception as e:
        st.error(f"分析失败: {e}")

elif analyze_btn and not pr_url.strip():
    st.warning("请输入 GitHub PR 地址")


# ── 渲染辅助函数 ────────────────────────────────────────

def _colorize_risks(text: str) -> str:
    """给风险等级文字加上颜色标记"""
    text = text.replace("严重", '<span class="risk-high">严重</span>')
    text = text.replace("中等", '<span class="risk-medium">中等</span>')
    text = text.replace("轻微", '<span class="risk-low">轻微</span>')
    return text


def _render_single_result(result: dict):
    """渲染单模型分析结果"""
    tab1, tab2, tab3, tab4 = st.tabs([
        " PR 变更总结", " 风险代码识别", " Review 建议", " 总体评价",
    ])

    with tab1:
        if result["summary"]:
            st.markdown(result["summary"])
        else:
            st.info("AI 未输出此部分")

    with tab2:
        if result["risks"]:
            st.markdown(_colorize_risks(result["risks"]), unsafe_allow_html=True)
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


def _render_compare_result(result: dict):
    """渲染多模型对比结果：四个 tab，每个内部左右两栏"""
    ds = result["deepseek"]
    qw = result.get("qwen")

    tab1, tab2, tab3, tab4 = st.tabs([
        " PR 变更总结", " 风险代码识别", " Review 建议", " 总体评价",
    ])

    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**DeepSeek**")
            st.markdown(ds.get("summary", "（未输出）"))
        with c2:
            st.markdown("**Qwen**")
            if qw:
                st.markdown(qw.get("summary", "（未输出）"))
            else:
                st.warning("Qwen 未配置")

    with tab2:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**DeepSeek**")
            if ds.get("risks"):
                st.markdown(_colorize_risks(ds["risks"]), unsafe_allow_html=True)
            else:
                st.success("未发现明显的风险代码")
        with c2:
            st.markdown("**Qwen**")
            if qw:
                if qw.get("risks"):
                    st.markdown(_colorize_risks(qw["risks"]), unsafe_allow_html=True)
                else:
                    st.success("未发现明显的风险代码")
            else:
                st.warning("Qwen 未配置")

    with tab3:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**DeepSeek**")
            st.markdown(ds.get("suggestions", "（未输出）"))
        with c2:
            st.markdown("**Qwen**")
            if qw:
                st.markdown(qw.get("suggestions", "（未输出）"))
            else:
                st.warning("Qwen 未配置")

    with tab4:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**DeepSeek**")
            st.markdown(ds.get("overall", "（未输出）"))
        with c2:
            st.markdown("**Qwen**")
            if qw:
                st.markdown(qw.get("overall", "（未输出）"))
            else:
                st.warning("Qwen 未配置")


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
            st.markdown(_colorize_risks(risks), unsafe_allow_html=True)
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
                st.markdown(_colorize_risks(risks), unsafe_allow_html=True)
            else:
                st.success("未发现")
        with c2:
            st.markdown("**Qwen**")
            if qw:
                risks = qw.get("risks", "")
                if risks:
                    st.markdown(_colorize_risks(risks), unsafe_allow_html=True)
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
