"""AI PR Review 助手 — Streamlit 主界面"""
import streamlit as st

from services.router import fetch_pr_full
from services.analyzer import analyze_pr, analyze_pr_compare
from services.utils import generate_report, generate_compare_report
from services.history import save_analysis, load_history, delete_analysis

# ── 组合 Hero：粒子球 + 文字层叠（移植自模板 hero-section.tsx + animated-sphere.tsx）──
COMBINED_HERO_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body {
    width: 100%; height: 100%;
    background: #fafafa;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    overflow: hidden;
  }
  body {
    background-image:
      linear-gradient(rgba(0,0,0,0.035) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0,0,0,0.035) 1px, transparent 1px);
    background-size: 40px 40px;
    background-position: center center;
  }
  /* 网格线 (来自模板 hero) */
  .grid-overlay { position: absolute; inset: 0; overflow: hidden; pointer-events: none; opacity: 0.3; z-index: 0; }
  .grid-overlay .h-line { position: absolute; left: 0; right: 0; height: 1px; background: rgba(0,0,0,0.08); }
  .grid-overlay .v-line  { position: absolute; top: 0; bottom: 0; width: 1px; background: rgba(0,0,0,0.08); }
  /* 粒子球容器 — 贴近右侧，向下延伸覆盖输入区 */
  #sphere-wrap {
    position: absolute;
    right: -40px;
    top: 52%;
    transform: translateY(-50%);
    width: min(900px, 58vw);
    height: min(900px, 58vw);
    z-index: 1;
    opacity: 0.5;
    pointer-events: none;
  }
  #sphere-wrap canvas { width: 100%; height: 100%; display: block; }
  /* 文字层 */
  .hero-content {
    position: relative; z-index: 10;
    max-width: 1400px; margin: 0 auto;
    padding: clamp(3rem, 8vh, 6rem) 2.5rem 2rem;
    height: 100%;
    display: flex; flex-direction: column; justify-content: center;
  }
  .hero-eyebrow {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    color: #999;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 1rem;
  }
  .hero-eyebrow .line {
    display: inline-block; width: 32px; height: 1px;
    background: #ccc; margin-right: 12px; vertical-align: middle;
  }
  .hero-heading {
    font-family: 'Instrument Serif', Georgia, 'Times New Roman', serif;
    font-size: clamp(3.5rem, 13vw, 10rem);
    font-weight: 400;
    color: #1a1a1a;
    letter-spacing: -0.02em;
    line-height: 0.88;
    margin-bottom: 1.5rem;
  }
  .hero-heading .muted { color: #999; }
  .hero-desc {
    color: #666;
    font-size: clamp(0.95rem, 1.4vw, 1.2rem);
    line-height: 1.6;
    max-width: 460px;
  }
  /* 轮播词 */
  .rotating-wrap {
    position: relative;
    display: inline-block;
  }
  .rotating-underline {
    position: absolute;
    bottom: -2px;
    left: 0;
    right: 0;
    height: 6px;
    background: rgba(0,0,0,0.08);
    border-radius: 3px;
    transition: width 0.4s cubic-bezier(0.22, 1, 0.36, 1);
  }
  .char-in {
    display: inline-block;
    animation: char-in 0.5s cubic-bezier(0.22, 1, 0.36, 1) forwards;
    opacity: 0;
    filter: blur(40px);
    transform: translateY(100%);
  }
  @keyframes char-in {
    0% {
      opacity: 0;
      filter: blur(40px);
      transform: translateY(100%);
    }
    100% {
      opacity: 1;
      filter: blur(0);
      transform: translateY(0);
    }
  }
  @media (max-width: 768px) {
    #sphere-wrap { right: -120px; width: 380px; height: 380px; opacity: 0.22; }
    .hero-heading { font-size: 3rem; }
    .hero-content { padding: 2rem 1.5rem 1.5rem; }
  }
</style>
</head>
<body>
  <div class="grid-overlay" id="grid-overlay"></div>
  <div id="sphere-wrap"><canvas id="sphere"></canvas></div>
  <div class="hero-content">
    <div class="hero-eyebrow"><span class="line"></span>The platform for code review</div>
    <h1 class="hero-heading">AI-Powered<br>Code <span class="muted"><span class="rotating-wrap" id="rotating-wrap"><span id="rotating-word"></span><span class="rotating-underline"></span></span></span></h1>
    <p class="hero-desc">输入 GitHub / Gitee PR 链接，AI 自动分析代码变更 — 总结 · 风险识别 · Review 建议</p>
  </div>
<script>
(function() {
  /* ── 网格线 ── */
  var grid = document.getElementById('grid-overlay');
  for (var i = 1; i <= 8; i++) {
    var h = document.createElement('div');
    h.className = 'h-line';
    h.style.top = (12.5 * i) + '%';
    grid.appendChild(h);
  }
  for (var j = 1; j <= 12; j++) {
    var v = document.createElement('div');
    v.className = 'v-line';
    v.style.left = (8.33 * j) + '%';
    grid.appendChild(v);
  }

  /* ── 粒子球 ── */
  var canvas = document.getElementById('sphere');
  var ctx = canvas.getContext('2d');
  var chars = '░▒▓█▀▄▌▐│─┤├┴┬╭╮╰╯';
  var time = 0, frameId;

  function resize() {
    var dpr = window.devicePixelRatio || 1;
    var rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpr, dpr);
  }

  function render() {
    var rect = canvas.getBoundingClientRect();
    ctx.clearRect(0, 0, rect.width, rect.height);

    var cx = rect.width / 2, cy = rect.height / 2;
    var radius = Math.min(rect.width, rect.height) * 0.45;
    ctx.font = '14px monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    var points = [];
    var step = 0.18;
    for (var phi = 0; phi < Math.PI * 2; phi += step) {
      for (var theta = step; theta < Math.PI - step; theta += step) {
        var sx = Math.sin(theta) * Math.cos(phi + time * 0.5);
        var sy = Math.sin(theta) * Math.sin(phi + time * 0.5);
        var sz = Math.cos(theta);

        var ry = time * 0.3;
        var nx = sx * Math.cos(ry) - sz * Math.sin(ry);
        var nz = sx * Math.sin(ry) + sz * Math.cos(ry);

        var rx = time * 0.2;
        var ny = sy * Math.cos(rx) - nz * Math.sin(rx);
        var fz = sy * Math.sin(rx) + nz * Math.cos(rx);

        var d = (fz + 1) / 2;
        points.push({
          x: cx + nx * radius,
          y: cy + ny * radius,
          z: fz,
          c: chars[Math.floor(d * (chars.length - 1))]
        });
      }
    }
    points.sort(function(a,b) { return a.z - b.z; });
    for (var i = 0; i < points.length; i++) {
      var p = points[i];
      var alpha = 0.1 + (p.z + 1) * 0.3;
      ctx.fillStyle = 'rgba(0,0,0,' + alpha + ')';
      ctx.fillText(p.c, p.x, p.y);
    }
    time += 0.02;
    frameId = requestAnimationFrame(render);
  }

  resize();
  window.addEventListener('resize', resize);
  render();

  /* ── 轮播词 ── */
  var words = ['review', 'refactor', 'refine', 'resolve'];
  var wordIdx = 0;
  var rotatingEl = document.getElementById('rotating-word');
  var rotatingWrap = document.getElementById('rotating-wrap');

  function setWord(word) {
    rotatingEl.innerHTML = '';
    word.split('').forEach(function(ch, i) {
      var span = document.createElement('span');
      span.textContent = ch;
      span.className = 'char-in';
      span.style.animationDelay = (i * 50) + 'ms';
      rotatingEl.appendChild(span);
    });
  }

  setWord(words[0]);

  setInterval(function() {
    wordIdx = (wordIdx + 1) % words.length;
    setWord(words[wordIdx]);
  }, 2500);

  /* ── 父页面滚动 → 导航栏收缩 ── */
  (function initNavScroll() {
    try {
      var parentDoc = window.parent.document;
      var parentWin = window.parent;
      var navbar = parentDoc.querySelector('.navbar');
      if (!navbar) { setTimeout(initNavScroll, 200); return; }
      var getScrollY = function() {
        // 尝试多个可能的滚动容器
        var main = parentDoc.querySelector('.stMain');
        if (main && main.scrollTop > 0) return main.scrollTop;
        return parentWin.scrollY || parentDoc.documentElement.scrollTop || 0;
      };
      var onScroll = function() {
        navbar.classList.toggle('navbar-scrolled', getScrollY() > 20);
      };
      // 监听 stMain + window + document
      var main = parentDoc.querySelector('.stMain');
      if (main) main.addEventListener('scroll', onScroll, {passive: true});
      parentWin.addEventListener('scroll', onScroll, {passive: true});
      parentDoc.addEventListener('scroll', onScroll, {passive: true});
      onScroll();
    } catch(e) {}
  })();
})();
</script>
</body>
</html>
"""

# ── 交互式 How It Works（步骤切换 + 代码动画）──────────
HOW_IT_WORKS_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body {
    width: 100%; height: 100%;
    background: #1a1a1a;
    color: #fafafa;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    overflow: hidden;
  }
  body {
    background-image: repeating-linear-gradient(
      -45deg,
      transparent,
      transparent 40px,
      rgba(255,255,255,0.03) 40px,
      rgba(255,255,255,0.03) 41px
    );
  }

  .container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 3.5rem 2rem 2.5rem;
    height: 100%;
  }

  /* ── Label ── */
  .label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    color: rgba(255,255,255,0.4);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 1rem;
    display: flex; align-items: center; gap: 0.75rem;
  }
  .label .line {
    display: inline-block;
    width: 32px; height: 1px;
    background: rgba(255,255,255,0.3);
  }
  .heading {
    font-family: 'Instrument Serif', Georgia, serif;
    font-size: clamp(2.5rem, 5vw, 3.8rem);
    font-weight: 400;
    letter-spacing: -0.02em;
    line-height: 1.08;
    margin-bottom: 2rem;
  }
  .heading .muted { color: rgba(255,255,255,0.3); }

  /* ── Grid ── */
  .grid {
    flex: 1;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 3rem;
    align-items: start;
    min-height: 0;
  }

  /* ── Steps ── */
  .steps { display: flex; flex-direction: column; }
  .step {
    background: none; border: none;
    text-align: left; cursor: pointer;
    padding: 1.25rem 0;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    transition: opacity 0.5s ease;
    color: #fafafa;
    width: 100%;
    font-family: inherit;
  }
  .step:first-child { border-top: 1px solid rgba(255,255,255,0.08); }
  .step.inactive { opacity: 0.35; }
  .step.inactive:hover { opacity: 0.6; }
  .step-row {
    display: flex; align-items: flex-start; gap: 1.5rem;
  }
  .roman {
    font-family: 'Instrument Serif', Georgia, serif;
    font-size: 2rem; font-weight: 400;
    color: rgba(255,255,255,0.2);
    line-height: 1; min-width: 2.2rem;
    transition: color 0.5s ease;
  }
  .step.active .roman { color: rgba(255,255,255,0.5); }
  .step-info { flex: 1; }
  .step-title {
    font-size: 1.4rem; font-weight: 700;
    margin-bottom: 0.25rem;
    transition: transform 0.3s ease;
  }
  .step:hover .step-title { transform: translateX(4px); }
  .step-desc {
    font-size: 0.85rem; color: rgba(255,255,255,0.5);
    line-height: 1.6;
  }
  /* ── Code Window ── */
  .code-window {
    border: 1px solid rgba(255,255,255,0.1);
    background: rgba(255,255,255,0.02);
    align-self: start;
  }
  .code-header {
    padding: 0.7rem 1.25rem;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    display: flex; align-items: center; justify-content: space-between;
  }
  .code-dots { display: flex; gap: 6px; }
  .code-dots span {
    width: 10px; height: 10px; border-radius: 50%;
    background: rgba(255,255,255,0.15);
  }
  .code-filename {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem; color: rgba(255,255,255,0.3);
  }
  .code-body {
    padding: 1.5rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    line-height: 1.9;
    min-height: 260px;
  }
  .code-body .ln {
    color: rgba(255,255,255,0.1);
    display: inline-block; width: 1.5rem; text-align: right;
    margin-right: 0.8rem; user-select: none;
  }
  .code-body .kw { color: rgba(255,255,255,0.7); }
  .code-body .str { color: rgba(255,255,255,0.45); }
  .code-body .cm { color: rgba(255,255,255,0.18); }
  .code-body .fn { color: rgba(255,255,255,0.6); }
  .code-status {
    padding: 0.7rem 1.25rem;
    border-top: 1px solid rgba(255,255,255,0.08);
    display: flex; align-items: center; gap: 0.5rem;
  }
  .code-status .dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: #4ade80;
    animation: pulse-dot 2s infinite;
  }
  @keyframes pulse-dot {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }
  .code-status .stxt {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem; color: rgba(255,255,255,0.3);
  }

  /* ── Code reveal animation ── */
  .code-line {
    opacity: 0;
    transform: translateX(-8px);
    animation: line-in 0.4s cubic-bezier(0.22, 1, 0.36, 1) forwards;
  }
  @keyframes line-in {
    to { opacity: 1; transform: translateX(0); }
  }
  .code-char {
    opacity: 0;
    filter: blur(8px);
    animation: char-in 0.3s cubic-bezier(0.22, 1, 0.36, 1) forwards;
  }
  @keyframes char-in {
    to { opacity: 1; filter: blur(0); }
  }

  @media (max-width: 768px) {
    .grid { grid-template-columns: 1fr; gap: 2rem; }
    .code-body { min-height: 200px; }
    .container { padding: 3rem 1.5rem 2rem; }
  }
</style>
</head>
<body>
<div class="container">
  <div class="grid">
    <!-- Left column: label + heading + steps -->
    <div>
      <div class="label"><span class="line"></span>Process</div>
      <div class="heading">Three steps.<br><span class="muted">Infinite possibilities.</span></div>
      <div class="steps" id="steps"></div>
    </div>

    <!-- Right column: code window (aligned to top) -->
    <div class="code-window">
      <div class="code-header">
        <div class="code-dots"><span></span><span></span><span></span></div>
        <div class="code-filename" id="code-filename">fetch_pr.py</div>
      </div>
      <div class="code-body" id="code-body"></div>
      <div class="code-status">
        <div class="dot"></div>
        <div class="stxt" id="code-status-text">Ready</div>
      </div>
    </div>
  </div>
</div>

<script>
(function() {
  var stepsData = [
    {
      number: "I",
      title: "粘贴 PR 链接",
      desc: "支持 GitHub 和 Gitee 仓库，自动获取 PR 详情、commit 历史和完整代码变更 diff。",
      filename: "fetch_pr.py",
      status: "Fetched 15 files, +342 / -128 lines",
      code: [
        { text: "from pr_review import ReviewClient", cls: "" },
        { text: "", cls: "" },
        { text: "client = ReviewClient(", cls: "" },
        { text: "    platform=\"github\",", cls: "str" },
        { text: "    repo=\"owner/repo\",", cls: "str" },
        { text: "    pr_number=123", cls: "" },
        { text: ")", cls: "" },
        { text: "", cls: "" },
        { text: "# Fetch PR details…", cls: "cm" },
        { text: "pr = client.fetch()", cls: "fn" },
        { text: "", cls: "" },
        { text: "# → PR #123: Refactor auth", cls: "cm" },
        { text: "# → Files changed: 15", cls: "cm" },
        { text: "# → +342 additions / -128 deletions", cls: "cm" },
        { text: "# → Base: main ← Head: feat/auth", cls: "cm" }
      ]
    },
    {
      number: "II",
      title: "AI 自动分析",
      desc: "DeepSeek + Qwen 双模型并行审查，逐文件分析变更，智能汇总 PR 变更总结和风险点。",
      filename: "analyzer.py",
      status: "Analyzing 15 files with dual models…",
      code: [
        { text: "from pr_review import AIAnalyzer", cls: "" },
        { text: "", cls: "" },
        { text: "analyzer = AIAnalyzer(", cls: "" },
        { text: "    models=[\"deepseek\", \"qwen\"],", cls: "str" },
        { text: "    mode=\"compare\",", cls: "str" },
        { text: "    max_tokens=4096", cls: "" },
        { text: ")", cls: "" },
        { text: "", cls: "" },
        { text: "# Analyzing file by file…", cls: "cm" },
        { text: "report = analyzer.review(pr)", cls: "fn" },
        { text: "", cls: "" },
        { text: "#  ✓ src/auth/login.py", cls: "cm" },
        { text: "#  ✓ src/api/middleware.py", cls: "cm" },
        { text: "#  ✓ src/utils/helpers.py", cls: "cm" },
        { text: "#  ⠙ 12 more files…", cls: "cm" }
      ]
    },
    {
      number: "III",
      title: "获取 Review 报告",
      desc: "一键下载完整 Markdown 报告，包含变更总结、风险代码识别、Review 建议和总体评价。",
      filename: "report.md",
      status: "Report saved — 4 findings, 2 risks",
      code: [
        { text: "# Analysis complete in 12.4s", cls: "cm" },
        { text: "", cls: "" },
        { text: "print(report.summary)", cls: "fn" },
        { text: "# → PR #123: Refactor auth middleware", cls: "cm" },
        { text: "# → Risk level: Low (2 minor)", cls: "cm" },
        { text: "# → Overall: ✓ Recommended", cls: "cm" },
        { text: "", cls: "" },
        { text: "report.export(", cls: "fn" },
        { text: "    format=\"markdown\",", cls: "str" },
        { text: "    output=\"PR-Review-123.md\"", cls: "str" },
        { text: ")", cls: "" },
        { text: "", cls: "" },
        { text: "# → DeepSeek: 3 suggestions", cls: "cm" },
        { text: "# → Qwen:     2 suggestions", cls: "cm" },
        { text: "# → Consensus: 4 unique findings", cls: "cm" }
      ]
    }
  ];

  var activeIdx = 0;
  var isTransitioning = false;

  var stepsEl = document.getElementById('steps');
  var codeBody = document.getElementById('code-body');
  var codeFilename = document.getElementById('code-filename');
  var codeStatusText = document.getElementById('code-status-text');

  /* ── Render steps ── */
  function renderSteps() {
    stepsEl.innerHTML = '';
    stepsData.forEach(function(step, i) {
      var btn = document.createElement('button');
      btn.className = 'step' + (i === activeIdx ? ' active' : ' inactive');
      btn.innerHTML =
        '<div class="step-row">' +
          '<div class="roman">' + step.number + '</div>' +
          '<div class="step-info">' +
            '<div class="step-title">' + step.title + '</div>' +
            '<div class="step-desc">' + step.desc + '</div>' +
          '</div>' +
        '</div>';
      btn.addEventListener('click', (function(idx) {
        return function() { switchTo(idx); };
      })(i));
      stepsEl.appendChild(btn);
    });
  }

  /* ── Render code with reveal animation ── */
  function renderCode(step) {
    codeFilename.textContent = step.filename;
    codeStatusText.textContent = step.status;
    codeBody.innerHTML = '';

    step.code.forEach(function(line, li) {
      var lineDiv = document.createElement('div');
      lineDiv.className = 'code-line';
      lineDiv.style.animationDelay = (li * 60) + 'ms';

      var lnSpan = document.createElement('span');
      lnSpan.className = 'ln';
      lnSpan.textContent = line.text ? (li + 1) : '';
      lineDiv.appendChild(lnSpan);

      var contentSpan = document.createElement('span');
      contentSpan.className = 'code-content';

      var chars = line.text.split('');
      chars.forEach(function(ch, ci) {
        var charSpan = document.createElement('span');
        charSpan.className = 'code-char' + (line.cls ? ' ' + line.cls : '');
        charSpan.style.animationDelay = (li * 60 + ci * 12) + 'ms';
        charSpan.textContent = ch === ' ' ? ' ' : ch;
        contentSpan.appendChild(charSpan);
      });

      lineDiv.appendChild(contentSpan);
      codeBody.appendChild(lineDiv);
    });
  }

  /* ── Switch step ── */
  function switchTo(idx) {
    if (isTransitioning || idx === activeIdx) return;
    isTransitioning = true;
    activeIdx = idx;
    renderSteps();
    renderCode(stepsData[idx]);
    setTimeout(function() { isTransitioning = false; }, 300);
  }

  /* ── Init ── */
  renderSteps();
  renderCode(stepsData[0]);
})();
</script>
</body>
</html>
"""

st.set_page_config(
    page_title="AI PR Review",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── 全局样式 ──────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');

/* ── 基础 ── */
html, body, .stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background-color: #fafafa;
}
.stApp {
    background-color: #fafafa;
    background-image:
        linear-gradient(rgba(0, 0, 0, 0.035) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0, 0, 0, 0.035) 1px, transparent 1px);
    background-size: 40px 40px;
    background-position: center center;
}
[data-testid="stHeader"] { display: none !important; }

/* ── 主内容区贴顶 ── */
.stApp { padding-top: 0 !important; }
[data-testid="stAppViewContainer"] { padding-top: 0 !important; }
.block-container { padding: 0 !important; max-width: none !important; }

/* ── 首个 iframe（Hero）让鼠标事件穿透 ── */
[data-testid="stElementContainer"]:has(iframe) {
    margin-bottom: -160px !important;
}
[data-testid="stElementContainer"]:has(iframe) iframe {
    pointer-events: none !important;
}
/* 后续 iframe（How It Works 等）恢复点击 + 移除负边距 */
[data-testid="stElementContainer"]:has(iframe) ~ [data-testid="stElementContainer"]:has(iframe) {
    margin-bottom: 0 !important;
}
[data-testid="stElementContainer"]:has(iframe) ~ [data-testid="stElementContainer"]:has(iframe) iframe {
    pointer-events: auto !important;
}
/* 输入区上移后紧跟的 spacer 去掉默认间距 */
.input-section-spacer {
    margin-top: 0 !important;
}

/* ── 导航栏（基础 = 页面顶部展开状态）── */
.navbar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 0.85rem 2rem;
    background: transparent;
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
    border-bottom: 1px solid transparent;
    position: fixed; top: 0; left: 0; right: 0; z-index: 100;
    width: 100%;
    transition: padding 0.4s cubic-bezier(0.22, 1, 0.36, 1),
                background 0.4s cubic-bezier(0.22, 1, 0.36, 1),
                border-radius 0.4s cubic-bezier(0.22, 1, 0.36, 1),
                box-shadow 0.4s cubic-bezier(0.22, 1, 0.36, 1),
                margin 0.4s cubic-bezier(0.22, 1, 0.36, 1),
                width 0.4s cubic-bezier(0.22, 1, 0.36, 1),
                top 0.4s cubic-bezier(0.22, 1, 0.36, 1),
                backdrop-filter 0.4s cubic-bezier(0.22, 1, 0.36, 1);
}
/* 滚动后收缩为浮窗 */
.navbar.navbar-scrolled {
    padding: 0.5rem 2rem;
    margin: 0.75rem auto;
    width: min(calc(100% - 2rem), 1200px);
    left: 0; right: 0;
    top: 0.75rem;
    background: rgba(250,250,250,0.8);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid rgba(0,0,0,0.06);
    border-radius: 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.navbar .logo {
    font-family: 'Inter', sans-serif;
    font-weight: 800;
    font-size: 1.2rem;
    color: #1a1a1a;
    letter-spacing: -0.02em;
}
.navbar .logo sup {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    font-weight: 400;
    color: #999;
    margin-left: 2px;
}
.navbar .nav-links { display: flex; align-items: center; gap: 1.5rem; }
.navbar .nav-link {
    font-family: 'Inter', sans-serif;
    font-size: 0.85rem;
    color: #666;
    text-decoration: none;
    transition: color 0.15s;
    cursor: pointer;
    scroll-behavior: smooth;
}
.navbar .nav-link:hover { color: #1a1a1a; }
.navbar .nav-btn {
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    font-size: 0.85rem;
    padding: 0.45rem 1.25rem;
    border-radius: 9999px;
    border: 1.5px solid #1a1a1a;
    background: #1a1a1a;
    color: #fff;
    cursor: pointer;
    transition: all 0.15s;
}
.navbar .nav-btn:hover { background: #333; }
.navbar .history-badge {
    display: inline-flex; align-items: center; justify-content: center;
    background: #1a1a1a; color: #fff;
    font-size: 0.65rem; font-weight: 700;
    min-width: 18px; height: 18px; border-radius: 50%;
    margin-left: 4px;
    padding: 0 4px;
}

/* ── 侧边栏 ── */
[data-testid="stSidebar"] {
    background-color: #ffffff;
    border-right: 1px solid #e5e5e5;
}
[data-testid="stSidebar"] h3 {
    font-family: 'Inter', sans-serif;
    font-weight: 700;
    font-size: 1rem;
    color: #1a1a1a;
}

/* ── 按钮 ── */
.stButton > button {
    border-radius: 9999px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.875rem !important;
    padding: 0.5rem 1.5rem !important;
    border: 1.5px solid #1a1a1a !important;
    background: #1a1a1a !important;
    color: #ffffff !important;
    transition: all 0.15s ease !important;
    box-shadow: none !important;
}
.stButton > button:hover {
    background: #333333 !important;
    border-color: #333333 !important;
}

/* ── 输入框 ── */
.stTextInput > div > div > input {
    border-radius: 12px !important;
    border: 1.5px solid #e5e5e5 !important;
    background: #ffffff !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.9rem !important;
    padding: 0.75rem 1rem !important;
    box-shadow: none !important;
}
.stTextInput > div > div > input:focus {
    border-color: #1a1a1a !important;
    box-shadow: none !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 2rem;
    border-bottom: 1px solid #e5e5e5;
}
.stTabs [data-baseweb="tab"] {
    font-family: 'Inter', sans-serif;
    font-weight: 500;
    font-size: 0.85rem;
    color: #999999;
    background: transparent;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    padding: 0.5rem 0;
}
.stTabs [aria-selected="true"] {
    color: #1a1a1a !important;
    border-bottom-color: #1a1a1a !important;
}

/* ── 复选框 ── */
.stCheckbox label {
    font-family: 'Inter', sans-serif;
    font-size: 0.85rem;
    color: #666666;
}

/* ── 下载按钮 ── */
.stDownloadButton > button {
    border-radius: 9999px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.875rem !important;
    border: 1.5px solid #d4d4d4 !important;
    background: transparent !important;
    color: #1a1a1a !important;
    box-shadow: none !important;
}
.stDownloadButton > button:hover {
    background: #f5f5f5 !important;
    border-color: #1a1a1a !important;
}

/* ── Expander ── */
.stExpander {
    border: 1px solid #e5e5e5 !important;
    border-radius: 12px !important;
    background: #ffffff !important;
}

/* ── 信息/警告/成功提示 ── */
[data-testid="stInfo"] {
    background: #f5f5f5 !important;
    border: 1px solid #e5e5e5 !important;
    border-radius: 12px !important;
    color: #1a1a1a !important;
}
[data-testid="stSuccess"] {
    background: #f0fdf4 !important;
    border: 1px solid #bbf7d0 !important;
    border-radius: 12px !important;
}
[data-testid="stWarning"] {
    background: #fffbeb !important;
    border: 1px solid #fde68a !important;
    border-radius: 12px !important;
}
[data-testid="stError"] {
    background: #fef2f2 !important;
    border: 1px solid #fecaca !important;
    border-radius: 12px !important;
}

/* ── status 进度框 ── */
[data-testid="stStatus"] {
    border-radius: 12px !important;
    border: 1px solid #e5e5e5 !important;
}

/* ── Hero ── */
/* hero 文字已移入 iframe，此 CSS 仅供输入区域使用 */

/* ── PR 信息条 ── */
.pr-meta {
    display: flex; gap: 0.75rem; flex-wrap: wrap;
    font-size: 0.8rem; color: #666666;
    margin: 0.75rem 0;
}
.pr-meta span {
    background: transparent;
    border: 1px solid #d4d4d4;
    padding: 0.2rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.78rem;
    color: #555555;
}

/* ── 统计信息条 ── */
.stats-bar {
    padding: 0.75rem 0;
    border-top: 1px solid #e5e5e5;
    display: flex; gap: 1rem; flex-wrap: wrap;
    font-size: 0.78rem;
    font-family: 'JetBrains Mono', monospace;
    color: #888888;
    margin-top: 1.5rem;
}
.stats-bar .stat-value { color: #1a1a1a; font-weight: 600; }
.stats-sep { color: #d4d4d4; }

/* ── 风险标记 ── */
.risk-high { color: #dc2626; font-weight: 700; }
.risk-medium { color: #d97706; font-weight: 700; }
.risk-low { color: #16a34a; font-weight: 700; }

/* ── Features Section ── */
.features-section {
    max-width: 1400px;
    margin: 0 auto;
    padding: 6rem 2rem 5rem;
}
.features-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    color: #999;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 1.5rem;
}
.features-label .line {
    display: inline-block;
    width: 32px;
    height: 1px;
    background: #ccc;
    margin-right: 12px;
    vertical-align: middle;
}
.features-heading {
    font-size: clamp(2rem, 4vw, 3.5rem);
    font-weight: 800;
    color: #1a1a1a;
    letter-spacing: -0.02em;
    line-height: 1.1;
    margin-bottom: 3rem;
}
.features-heading .muted { color: #999; }
.features-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1px;
    background: rgba(0,0,0,0.06);
    border: 1px solid rgba(0,0,0,0.06);
}
.feature-card {
    background: #fafafa;
    padding: 2.5rem 2rem;
}
.feature-card .num {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    color: #999;
    margin-bottom: 1rem;
}
.feature-card .title {
    font-size: 1.5rem;
    font-weight: 700;
    color: #1a1a1a;
    margin-bottom: 0.5rem;
}
.feature-card .desc {
    font-size: 0.9rem;
    color: #888;
    line-height: 1.6;
}
@media (max-width: 768px) {
    .features-grid { grid-template-columns: 1fr; }
}

/* ── How It Works Section ── */
.how-section {
    background: #1a1a1a;
    color: #fafafa;
    padding: 6rem 2rem 5rem;
    position: relative;
    overflow: hidden;
}
.how-section::before {
    content: '';
    position: absolute; inset: 0; pointer-events: none; opacity: 0.03;
    background-image: repeating-linear-gradient(
        -45deg,
        transparent,
        transparent 40px,
        currentColor 40px,
        currentColor 41px
    );
}
.how-inner {
    max-width: 1400px;
    margin: 0 auto;
    position: relative; z-index: 10;
}
.how-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: 4rem; align-items: start;
}
.how-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    color: rgba(255,255,255,0.4);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 1.5rem;
}
.how-label .line {
    display: inline-block;
    width: 32px;
    height: 1px;
    background: rgba(255,255,255,0.3);
    margin-right: 12px;
    vertical-align: middle;
}
.how-heading {
    font-size: clamp(2rem, 4vw, 3.5rem);
    font-weight: 800;
    letter-spacing: -0.02em;
    line-height: 1.1;
    margin-bottom: 3rem;
}
.how-heading .muted { color: rgba(255,255,255,0.35); }
.how-steps { display: flex; flex-direction: column; }
.how-step {
    border-bottom: 1px solid rgba(255,255,255,0.1);
    padding: 1.75rem 0;
}
.how-step:first-child { border-top: 1px solid rgba(255,255,255,0.1); }
.how-step .step-row { display: flex; align-items: flex-start; gap: 1.5rem; }
.how-step .roman {
    font-family: 'Inter', serif;
    font-size: 2rem; font-weight: 700;
    color: rgba(255,255,255,0.2);
    line-height: 1; min-width: 2.5rem;
}
.how-step .step-info { flex: 1; }
.how-step .step-title {
    font-size: 1.3rem; font-weight: 700; margin-bottom: 0.3rem;
}
.how-step .step-desc {
    font-size: 0.9rem; color: rgba(255,255,255,0.5); line-height: 1.6;
}

/* 代码终端窗口 */
.code-window {
    border: 1px solid rgba(255,255,255,0.1);
    overflow: hidden;
    background: rgba(255,255,255,0.02);
}
.code-header {
    padding: 0.75rem 1.25rem;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    display: flex; align-items: center; justify-content: space-between;
}
.code-dots { display: flex; gap: 6px; }
.code-dots span {
    width: 10px; height: 10px; border-radius: 50%;
    background: rgba(255,255,255,0.15);
}
.code-filename {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem; color: rgba(255,255,255,0.3);
}
.code-body {
    padding: 1.5rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem; color: rgba(255,255,255,0.55);
    line-height: 1.9;
    min-height: 320px;
}
.code-body .ln {
    color: rgba(255,255,255,0.12);
    display: inline-block; width: 1.5rem; text-align: right;
    margin-right: 1rem; user-select: none;
}
.code-body .kw { color: rgba(255,255,255,0.75); }
.code-body .str { color: rgba(255,255,255,0.4); }
.code-body .cm { color: rgba(255,255,255,0.2); }
.code-status {
    padding: 0.75rem 1.25rem;
    border-top: 1px solid rgba(255,255,255,0.08);
    display: flex; align-items: center; gap: 0.5rem;
}
.code-status .dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: #4ade80;
    animation: pulse-dot 2s infinite;
}
@keyframes pulse-dot {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
}
.code-status .stxt {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem; color: rgba(255,255,255,0.3);
}

@media (max-width: 768px) {
    .how-grid { grid-template-columns: 1fr; }
    .how-step .roman { font-size: 1.5rem; min-width: 2rem; }
}

</style>
""", unsafe_allow_html=True)

# ── 顶部导航栏 ──────────────────────────────────────
st.markdown("""
<div class="navbar">
    <div class="logo">AI PR Review<sup>TM</sup></div>
    <div class="nav-links">
        <a class="nav-link" href="#features">Features</a>
        <a class="nav-link" href="#how-it-works">How it works</a>
    </div>
</div>
""", unsafe_allow_html=True)

# ── 历史面板 ──────────────────────────────────────
history = load_history()
if st.session_state.get("show_history", False):
    st.markdown("""
    <div style="display:flex;align-items:center;justify-content:space-between;padding:1rem 1.5rem 0;">
        <div style="font-family:'Inter',sans-serif;font-size:0.8rem;font-weight:600;color:#1a1a1a;">
            分析历史
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_close, col_new = st.columns([5, 1])
    with col_close:
        if st.button("关闭历史", use_container_width=True, key="close_history"):
            st.session_state["show_history"] = False
            st.rerun()
    with col_new:
        if st.button("新建", use_container_width=True, type="primary", key="new_from_history"):
            st.session_state.pop("selected_history", None)
            st.session_state["show_history"] = False
            st.rerun()

    if not history:
        st.caption("暂无历史记录，完成一次分析后自动保存。")
    else:
        for i, entry in enumerate(history):
            c1, c2, c3 = st.columns([3, 1, 1])
            with c1:
                label = f"{entry['pr_title'][:40]}..."
                if st.button(label, key=f"hist_panel_{entry['id']}", use_container_width=True):
                    st.session_state["selected_history"] = entry
                    st.session_state["show_history"] = False
                    st.rerun()
            with c2:
                st.caption(f"{entry['timestamp']}")
            with c3:
                if st.button("", key=f"del_panel_{entry['id']}", help="删除"):
                    delete_analysis(entry["id"])
                    st.session_state.pop("selected_history", None)
                    st.rerun()
            st.caption(f"{entry.get('platform', 'github')} | {entry.get('model', 'N/A')}")
    st.divider()

# ── Hero（球 + 文字 层叠布局）─────────────────────────
st.components.v1.html(COMBINED_HERO_HTML, height=820)

# ── 输入区（负边距上移，叠加在球上方）───────────────
st.markdown('<div class="input-section-spacer"></div>', unsafe_allow_html=True)
_, input_wrap, _ = st.columns([1, 5, 1])
with input_wrap:
    pr_url = st.text_input(
        "GitHub / Gitee PR 地址",
        placeholder="https://github.com/owner/repo/pull/123",
        label_visibility="collapsed",
    )
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        analyze_btn = st.button("Start Analysis", type="primary", use_container_width=True)
    with c2:
        compare_mode = st.checkbox("Multi-model compare", help="DeepSeek + Qwen 交叉验证")
    with c3:
        if st.button("History", use_container_width=True, key="history_toggle_btn"):
            st.session_state["show_history"] = not st.session_state.get("show_history", False)
            st.rerun()

# ── Features Section ─────────────────────────────────
st.markdown("""
<div id="features" class="features-section">
    <div class="features-label"><span class="line"></span>Capabilities</div>
    <div class="features-heading">
        AI-powered PR Review.<br>
        <span class="muted">Zero hassle.</span>
    </div>
    <div class="features-grid">
        <div class="feature-card">
            <div class="num">01</div>
            <div class="title">AI 智能分析</div>
            <div class="desc">DeepSeek + Qwen 双模型交叉验证，多角度审视代码变更，确保分析结果全面可靠。</div>
        </div>
        <div class="feature-card">
            <div class="num">02</div>
            <div class="title">风险识别</div>
            <div class="desc">自动标注严重、中等、轻微三级风险代码，快速定位潜在问题，保护代码质量。</div>
        </div>
        <div class="feature-card">
            <div class="num">03</div>
            <div class="title">多平台支持</div>
            <div class="desc">支持 GitHub 和 Gitee 仓库 PR 分析，覆盖主流代码托管平台。</div>
        </div>
        <div class="feature-card">
            <div class="num">04</div>
            <div class="title">历史回顾</div>
            <div class="desc">分析结果自动保存，随时回看历史记录，支持一键导出 Markdown 报告。</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── How It Works Section ─────────────────────────────
st.markdown('<div id="how-it-works" style="position:absolute"></div>', unsafe_allow_html=True)
st.components.v1.html(HOW_IT_WORKS_HTML, height=680)

# ── 历史记录回看 ──────────────────────────────────────
selected = st.session_state.get("selected_history")
if selected:
    st.info(f"正在查看历史分析: **{selected['pr_title']}** ({selected['timestamp']})")

    r = selected["result"]

    st.markdown(f"""
    <div class="pr-meta">
        <span>{selected.get('pr_author', '')}</span>
        <span>{selected.get('head_branch', '')} &rarr; {selected.get('base_branch', '')}</span>
        <span>{selected.get('changed_files', 0)} files</span>
        <span style="color:#16a34a">+{selected.get('additions', 0)}</span>
        <span style="color:#dc2626">-{selected.get('deletions', 0)}</span>
    </div>
    """, unsafe_allow_html=True)

    if r.get("compare_mode"):
        _render_compare_history(r)
    else:
        _render_single_history(r)

    st.caption(f"分析模型: {r.get('model', 'N/A')} | 分析时间: {selected['timestamp']}")
    st.stop()

# ── 分析逻辑 ──────────────────────────────────────────
if analyze_btn and pr_url.strip():
    try:
        with st.status("正在获取 PR 信息...", expanded=False) as status:
            pr_data = fetch_pr_full(pr_url.strip())
            status.update(label="PR 信息获取完成", state="complete", expanded=False)

        if compare_mode:
            with st.status("正在用 DeepSeek + Qwen 双模型分析...", expanded=False) as status:
                result = analyze_pr_compare(pr_data)
                status.update(label="双模型分析完成", state="complete", expanded=False)
        else:
            with st.status(f"正在用 AI 分析 {pr_data['changed_files']} 个文件...", expanded=False) as status:
                result = analyze_pr(pr_data)
                status.update(label="AI 分析完成", state="complete", expanded=False)

        save_analysis(pr_data, result)

        # ── 结果展示 ──

        st.markdown(f"""
        <div class="pr-meta">
            <span>{pr_data['author']}</span>
            <span>{pr_data['head_branch']} &rarr; {pr_data['base_branch']}</span>
            <span>{pr_data['changed_files']} files</span>
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
            _render_compare_result(result)
        else:
            _render_single_result(result)

        # 原始输出
        with st.expander("查看 AI 原始输出"):
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

        # 统计信息条
        model_label = (
            f"DeepSeek ({result['deepseek']['model']}) + Qwen ({result.get('qwen', {}).get('model', 'N/A')})"
            if compare_mode
            else f"DeepSeek ({result['model']})"
        )
        st.markdown(f"""
        <div class="stats-bar">
            <span>PR <span class="stat-value">#{pr_data['pr_number']}</span></span>
            <span class="stats-sep">|</span>
            <span class="stat-value">{pr_data['changed_files']}</span> files changed
            <span class="stats-sep">|</span>
            <span style="color:#16a34a">+{pr_data['additions']}</span>
            <span class="stats-sep">|</span>
            <span style="color:#dc2626">-{pr_data['deletions']}</span>
            <span class="stats-sep">|</span>
            <span>{pr_data['head_branch']} &rarr; {pr_data['base_branch']}</span>
            <span class="stats-sep">|</span>
            <span>{model_label}</span>
        </div>
        """, unsafe_allow_html=True)

        # 下载报告
        if compare_mode:
            report_md = generate_compare_report(pr_data, result)
        else:
            report_md = generate_report(pr_data, result)
        st.download_button(
            label="下载 Markdown 报告",
            data=report_md,
            file_name=f"PR-Review-{pr_data['repo']}-#{pr_data['pr_number']}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    except ValueError as e:
        st.error(f"输入错误: {e}")
    except Exception as e:
        st.error(f"分析失败: {e}")

elif analyze_btn and not pr_url.strip():
    st.warning("请输入 GitHub / Gitee PR 地址")


# ── 渲染辅助函数 ────────────────────────────────────────

def _colorize_risks(text: str) -> str:
    text = text.replace("严重", '<span class="risk-high">严重</span>')
    text = text.replace("中等", '<span class="risk-medium">中等</span>')
    text = text.replace("轻微", '<span class="risk-low">轻微</span>')
    return text


def _render_single_result(result: dict):
    tab1, tab2, tab3, tab4 = st.tabs([
        "PR 变更总结", "风险代码识别", "Review 建议", "总体评价",
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
    ds = result["deepseek"]
    qw = result.get("qwen")

    tab1, tab2, tab3, tab4 = st.tabs([
        "PR 变更总结", "风险代码识别", "Review 建议", "总体评价",
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
    tab1, tab2, tab3, tab4 = st.tabs([
        "PR 变更总结", "风险代码识别", "Review 建议", "总体评价",
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

    with st.expander("查看 AI 原始输出"):
        st.code(r.get("raw", ""), language="markdown")


def _render_compare_history(r: dict):
    ds = r.get("deepseek", {})
    qw = r.get("qwen")

    tab1, tab2, tab3, tab4 = st.tabs([
        "PR 变更总结", "风险代码识别", "Review 建议", "总体评价",
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

    with st.expander("查看 AI 原始输出"):
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
