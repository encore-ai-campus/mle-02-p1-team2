"""Visual system for the industrial incident dashboard."""

from __future__ import annotations

from html import escape

import streamlit as st

INK = "#252A27"
MUTED = "#626D64"
GRAPH_DARK = "#505652"
GRAPH_MID = "#858C86"
GRAPH_LIGHT = "#BFC5BF"
GRID = "#ECEFEC"
SEVERITY_COLORS = (GRAPH_DARK, GRAPH_MID, GRAPH_LIGHT)


def apply_styles() -> None:
    st.markdown(
        """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css');
:root { color-scheme:light; --font-ui:'Pretendard Variable','Pretendard','Noto Sans KR','Malgun Gothic',sans-serif; --font-mono:ui-monospace,'SFMono-Regular',Consolas,monospace; --ink:#252A27; --muted:#626D64; --line:#E5E8E4; --canvas:#F8F9F7; --sage:#54785B; }
html,body,#root,[data-testid="stScreencast"] { background:#D9DEDB !important; }
[data-testid="stApp"] { top:24px !important; right:auto !important; bottom:auto !important; left:50% !important; width:min(1360px,calc(100vw - 96px)) !important; height:calc(100vh - 48px) !important; transform:translateX(-50%); border:1px solid #E7EAE6; border-radius:12px; box-shadow:0 18px 55px rgba(44,55,47,.14),0 2px 8px rgba(44,55,47,.05); overflow:hidden; }
[data-testid="stAppDeployButton"],[data-testid="stMainMenuButton"] { display:none !important; }
html,body,[data-testid="stAppViewContainer"],[data-testid="stSidebar"],[data-testid="stMarkdownContainer"],[data-testid="stWidgetLabel"],button,input,textarea { font-family:var(--font-ui) !important; }
html,body,[data-testid="stAppViewContainer"] { color:var(--ink); font-size:15px; line-height:1.58; }
[data-testid="stAppViewContainer"],[data-testid="stHeader"] { background:var(--canvas); }
.block-container { max-width:1530px; padding:52px 30px 64px; }
@media(max-width:900px) {
  [data-testid="stApp"] { top:0 !important; left:0 !important; width:100vw !important; height:100dvh !important; transform:none; border:0; border-radius:0; box-shadow:none; }
  [data-testid="stSidebar"] { width:min(250px,78vw) !important; min-width:min(250px,78vw) !important; max-width:min(250px,78vw) !important; }
  .block-container { max-width:none; padding:42px 18px 58px; }
}
@media(max-width:560px) {
  .block-container { padding:66px 13px 52px; }
  .scroll-top-link { right:12px; bottom:12px; }
  .workspace-bar { align-items:flex-start; }
}
.scroll-top-link { position:fixed; right:28px; bottom:24px; z-index:999; display:flex; align-items:center; gap:7px; padding:9px 13px; border:1px solid #D6DFD6; border-radius:7px; background:#FFFFFFF2; box-shadow:0 5px 18px rgba(34,48,37,.12); color:#405A46 !important; font-size:11px; font-weight:560; text-decoration:none !important; backdrop-filter:blur(8px); transition:background .16s,border-color .16s,transform .16s; }
.scroll-top-link:hover { background:#F1F6F0; border-color:#B8CCBA; transform:translateY(-2px); }
.scroll-top-link:focus-visible { outline:2px solid #73947A; outline-offset:3px; }
@media(max-width:640px) { .scroll-top-link { right:13px; bottom:14px; width:44px; height:44px; padding:0; border-radius:50%; justify-content:center; gap:0; } .scroll-top-link span { display:none; } }
@media(prefers-reduced-motion:reduce) { html:focus-within { scroll-behavior:auto !important; } .scroll-top-link { transition:none !important; transform:none !important; } }
[data-testid="stMarkdownContainer"] p { line-height:1.58; }
[data-testid="stSidebar"] { background:#ECEFEB; border-right:1px solid #DDE2DC; width:clamp(172px,18.5vw,250px) !important; min-width:clamp(172px,18.5vw,250px) !important; max-width:clamp(172px,18.5vw,250px) !important; }
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { padding:22px 13px 25px; }
[data-testid="stSidebar"] hr { border-color:var(--line); margin:15px 0; }
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p { color:#67716A; font-size:12px; font-weight:500; }
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color:var(--muted); font-size:11px; }
.sidebar-brand { display:flex; align-items:center; gap:9px; padding:0 4px 19px; border-bottom:1px solid var(--line); }
.sidebar-brand-icon { display:grid; place-items:center; width:31px; height:31px; border-radius:6px; background:#202521; color:white; font:600 17px var(--font-mono); }
.sidebar-brand-name { color:var(--ink); font-size:12px; font-weight:650; letter-spacing:-.025em; line-height:1.1; white-space:nowrap; }
.sidebar-brand-sub { color:var(--muted); font:10px/1.2 var(--font-mono); margin-top:3px; }
.sidebar-section { color:var(--muted); font:10px/1.2 var(--font-mono); letter-spacing:.06em; text-transform:uppercase; margin:20px 8px 9px; }
.sidebar-help { color:var(--muted); font-size:11px; line-height:1.5; margin:5px 8px 0; }
.sidebar-live{box-sizing:border-box;width:100%;max-width:100%;min-width:0;margin:15px 0 4px;padding:13px 12px;border:1px solid #DDE4DC;border-radius:9px;background:linear-gradient(145deg,#FAFBF9,#F1F5F0);overflow:hidden}
.sidebar-live>*{box-sizing:border-box;max-width:100%;min-width:0}
.sidebar-live-head{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:6px;color:var(--muted);font:9px/1.4 var(--font-mono);letter-spacing:.04em}
.sidebar-live-state{padding:3px 6px;border:1px solid #E1E7E0;border-radius:99px;background:#fff;color:#69756B;letter-spacing:0}
.sidebar-live-site{min-width:0;margin-top:8px;color:#39463C;font-size:11px;font-weight:620;line-height:1.5;overflow-wrap:anywhere;word-break:keep-all}
.sidebar-live-empty-title{margin-top:13px;color:#35463A;font-size:13px;font-weight:620;line-height:1.45;word-break:keep-all}
.sidebar-live-note{margin:5px 0 0;color:#626D64;font-size:10px;line-height:1.65;overflow-wrap:anywhere;word-break:keep-all}
.sidebar-live-grid{display:grid;grid-template-columns:minmax(0,1fr);gap:5px;margin-top:11px}
.sidebar-live-metric{display:flex;align-items:center;justify-content:space-between;gap:8px;min-width:0;padding:7px 9px;border:1px solid #E5EAE4;border-radius:6px;background:#FFFFFFD9;text-align:left}
.sidebar-live-metric strong{flex:none;color:#36473A;font:620 14px/1.1 var(--font-ui);font-variant-numeric:tabular-nums}
.sidebar-live-metric span{min-width:0;color:#626D64;font-size:10px;line-height:1.35;word-break:keep-all}
.sidebar-live-qualifiers{display:grid;grid-template-columns:minmax(0,1fr);gap:6px;min-width:0;margin-top:10px;padding-top:9px;border-top:1px solid #E3E9E2;color:#5F6B61;font-size:10px;line-height:1.7;overflow-wrap:anywhere;word-break:normal}
.sidebar-live-qualifiers>span{display:block;box-sizing:border-box;min-width:0;width:100%;max-width:100%;white-space:normal;overflow-wrap:anywhere;word-break:normal}
[class*="st-key-nav_"] button { width:100%; min-height:40px; justify-content:flex-start; padding:7px 10px; border:1px solid transparent !important; border-radius:7px; background:transparent !important; color:var(--muted) !important; font-size:12px; font-weight:450; box-shadow:none !important; }
[class*="st-key-nav_"] button:hover { background:#E8EBE7 !important; color:var(--ink) !important; }
.sidebar-recent { display:flex; flex-direction:column; margin:1px 6px 0; }
.recent-row { display:flex; align-items:center; gap:8px; padding:7px 2px; border-bottom:1px solid #EAEBE9; min-width:0; }
.recent-dot { width:5px; height:5px; border-radius:50%; background:#9FB2A3; flex:none; }
.recent-title { font-size:11px; color:#676F69; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.recent-date { margin-left:auto; color:var(--muted); font:10px var(--font-mono); flex:none; }
.sidebar-foot { margin:25px 6px 0; padding-top:15px; border-top:1px solid var(--line); color:var(--muted); font:10px/1.6 var(--font-mono); }
[data-testid="stSidebar"] [data-testid="stExpander"] { border-color:var(--line); background:#F8F9F7; border-radius:8px; }
[data-testid="stSidebar"] [data-testid="stExpander"] summary { font-size:11px; color:#6A736C; }
[data-testid="stSidebar"] [data-testid="stFileUploader"] section { background:white; border:1px dashed #D5DAD4; border-radius:7px; }
[data-testid="stSidebar"] [data-testid="stFileUploader"] section * { font-size:11px; }
[data-testid="stSidebar"] [data-testid="stButton"] button,[data-testid="stSidebar"] [data-testid="stDownloadButton"] button { font-size:11px; }
.workspace-bar { display:flex; align-items:center; justify-content:space-between; min-height:29px; margin:0 0 16px; gap:14px; }
.crumbs { display:flex; align-items:center; gap:10px; color:var(--muted); font:11px var(--font-mono); }
.crumb-back { display:grid; place-items:center; width:25px; height:25px; border:1px solid var(--line); border-radius:6px; color:#7D867E; background:white; font:18px/1 var(--font-ui); }
.crumb-current { color:#4F5952; }
.workspace-right { display:flex; align-items:center; gap:8px; color:var(--muted); font:10px var(--font-mono); }
.toolbar-badge { padding:6px 9px; border:1px solid var(--line); border-radius:7px; background:white; white-space:nowrap; }
.toolbar-count { padding:6px 9px; border-radius:7px; background:#262C27; color:white; white-space:nowrap; }
.hero { position:relative; min-height:185px; overflow:hidden; border:1px solid var(--line); border-radius:12px; background:#F9FAF7 url('/app/static/hero-industrial.png') center right/cover no-repeat; }
.hero:before { content:''; position:absolute; inset:0; background:linear-gradient(90deg,rgba(255,255,255,.96) 0%,rgba(255,255,255,.90) 35%,rgba(255,255,255,.20) 62%,rgba(255,255,255,0) 85%); }
.hero-content { position:relative; z-index:1; padding:26px 30px 25px; max-width:650px; }
.hero-overline { color:var(--sage); font:600 10px/1.2 var(--font-mono); letter-spacing:.06em; }
.hero h1 { font-size:clamp(27px,2.5vw,38px); letter-spacing:-.045em; line-height:1.25; font-weight:650; color:#202622; margin:9px 0 5px; }
.hero p { color:#6F7970; font-size:13px; line-height:1.6; margin:0; }
.st-key-hero_ctas { position:relative; z-index:2; width:310px; margin:-50px 0 9px 30px; }
.st-key-hero_ctas [data-testid="stHorizontalBlock"] { gap:8px; }
.st-key-hero_ctas button { min-height:32px; padding:0 9px; font-size:11px; white-space:nowrap; }
.st-key-hero_primary button { background:#262C27 !important; border-color:#262C27 !important; color:white !important; box-shadow:0 3px 8px #252B2733; }
.st-key-hero_secondary button { background:#FFFFFFEE !important; border-color:#E6E9E4 !important; color:#465047 !important; }
.data-notice { margin:9px 0 0; color:var(--muted); font-size:11px; line-height:1.5; }
.filter-strip { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:9px 18px; margin:15px 0 8px; }
.filter-tabs { display:inline-flex; align-items:center; gap:3px; padding:3px; border:1px solid var(--line); border-radius:8px; background:#F0F2EF; }
.filter-tab { padding:6px 12px; color:var(--muted); font:10px var(--font-mono); white-space:nowrap; }
.filter-tab.active { background:white; color:#313A33; border-radius:6px; box-shadow:0 1px 2px #2B322C0E; }
.period-chip { padding:7px 10px; border:1px solid var(--line); border-radius:7px; color:#69736B; background:white; font:10px var(--font-mono); white-space:nowrap; }
.dashboard-row-label { display:flex; align-items:center; justify-content:space-between; margin:9px 0 8px; gap:10px; }
.dashboard-row-label h2 { font-size:13px !important; font-weight:600 !important; letter-spacing:-.02em; color:#343C35; margin:0 !important; line-height:1.4 !important; }
.dashboard-row-label h2:before { content:'◉'; color:#8F9D91; font-size:12px; margin-right:7px; }
.dashboard-row-label span { color:var(--muted); font:10px var(--font-mono); }
.feature-card { min-height:183px; padding:15px 15px 9px; border:1px solid var(--line); border-radius:10px; background:#F7F9F7; overflow:hidden; }
.feature-card,.distribution-card { transition:transform .2s ease,border-color .2s ease,box-shadow .2s ease; }
.feature-card:hover,.distribution-card:hover { transform:translateY(-2px); border-color:#CDD5CD; box-shadow:0 9px 18px #3641380B; }
.feature-card-top { display:flex; align-items:flex-start; justify-content:space-between; gap:8px; }
.feature-card-title { font:600 11px/1.2 var(--font-mono); color:#333C34; letter-spacing:-.02em; }
.feature-card-sub { font:9px/1.3 var(--font-mono); color:var(--muted); margin-top:3px; text-transform:uppercase; }
.card-icon { display:grid; place-items:center; width:22px; height:22px; border:1px solid #EAEEEA; border-radius:6px; color:var(--muted); font:12px var(--font-ui); }
.feature-value { color:#222A23; font:650 30px/1.15 var(--font-ui); letter-spacing:-.045em; margin:18px 0 0; }
.feature-unit { color:var(--muted); font:10px var(--font-mono); margin-top:2px; }
.sparkline { width:100%; height:48px; display:block; margin-top:6px; }
.spark-wrap { position:relative; width:100%; margin-top:6px; }
.spark-wrap .sparkline { margin-top:0; }
.spark-popover { position:absolute; z-index:2; bottom:43px; min-width:96px; padding:5px 7px; border:1px solid #4A534B; border-radius:5px; background:#303A32; box-shadow:0 4px 12px #28332A26; color:white; font:10px var(--font-mono); text-align:center; white-space:nowrap; pointer-events:none; visibility:hidden; opacity:0; transform:translateX(-50%); transition:opacity .16s ease; }
.sparkline polyline { transition:stroke-width .2s ease,stroke .2s ease; }
.feature-card:hover .sparkline polyline { stroke-width:2.5; stroke:#505A51; }
.spark-point,.spark-bar { cursor:crosshair; outline:none; }
.spark-guide { stroke:#AAB3AA; stroke-width:1; stroke-dasharray:2 3; opacity:0; transition:opacity .18s ease; }
.spark-point:hover .spark-guide,.spark-point:focus-visible .spark-guide { opacity:1; }
.spark-point:focus .spark-guide { opacity:1; }
.spark-bar { transition:opacity .18s ease,filter .18s ease; }
.spark-bar:hover,.spark-bar:focus-visible,.spark-bar:focus { filter:brightness(.78); }
.pillar-panel { border:1px solid var(--line); border-radius:10px; padding:8px 10px; background:white; }
.pillar-row { display:flex; align-items:center; gap:8px; padding:8px 2px; border-bottom:1px solid #EFF1EE; }
.pillar-row:last-child { border-bottom:0; }
.pillar-row>div { min-width:0; overflow-wrap:anywhere; word-break:keep-all; }
.pillar-icon { display:grid; place-items:center; flex:none; width:29px; height:29px; border:1px solid #E8ECE8; border-radius:6px; color:var(--muted); font-size:14px; }
.pillar-name { font:600 11px/1.3 var(--font-mono); color:#444D45; }
.pillar-sub { color:var(--muted); font:9px/1.3 var(--font-mono); margin-top:2px; }
.pillar-count { margin-left:auto; color:#67756B; background:#F4F6F3; padding:4px 6px; border-radius:4px; font:10px var(--font-mono); }
.quick-stat { min-height:70px; display:flex; align-items:center; gap:10px; padding:11px; border:1px solid var(--line); border-radius:8px; background:white; }
.quick-icon { color:var(--muted); font-size:16px; }
.quick-num { color:#39443B; font:600 16px/1.1 var(--font-mono); }
.quick-label { color:var(--muted); font:9px/1.3 var(--font-mono); margin-top:3px; }
.distribution-card { min-height:170px; border:1px solid var(--line); border-radius:9px; overflow:hidden; background:white; }
.distribution-visual { position:relative; height:83px; background:#F0F2EF; display:flex; align-items:end; gap:5px; padding:14px 17px 0; overflow:visible; }
.distribution-bar { flex:1; min-width:4px; max-width:33px; background:#919892; border-radius:2px 2px 0 0; opacity:.76; }
.distribution-bar { cursor:crosshair; outline:none; }
.distribution-bar::after { content:attr(data-label); position:absolute; z-index:2; top:7px; left:50%; padding:5px 7px; border:1px solid #4A534B; border-radius:5px; background:#303A32; box-shadow:0 4px 12px #28332A26; color:white; font:10px var(--font-ui); white-space:nowrap; pointer-events:none; visibility:hidden; opacity:0; transform:translateX(-50%); transition:opacity .16s ease; }
.distribution-bar:hover::after,.distribution-bar:focus-visible::after,.distribution-bar:focus::after { visibility:visible; opacity:1; }
.distribution-bar { transition:opacity .2s ease,transform .2s ease; }
.distribution-card:hover .distribution-bar { opacity:.92; }
.distribution-bar:hover { transform:translateY(-4px); opacity:1 !important; }
.distribution-bar:nth-child(even) { background:#C0C5C0; }
.distribution-content { padding:11px 12px 12px; }
.distribution-title { font:600 11px/1.3 var(--font-mono); color:#414A42; }
.distribution-description { color:var(--muted); font-size:10px; line-height:1.45; margin-top:4px; }
.distribution-meta { color:var(--muted); font:9px var(--font-mono); margin-top:11px; }
.section-heading { display:flex; align-items:baseline; justify-content:space-between; gap:14px; margin:30px 0 12px; }
.section-heading-left { display:flex; align-items:baseline; gap:8px; min-width:0; }
.section-index { color:var(--muted); font:10px var(--font-mono); }
.section-heading h2.section-title { color:#354037; font-size:16px !important; font-weight:600 !important; letter-spacing:-.02em; line-height:1.4 !important; margin:0 !important; }
.section-description { color:var(--muted); font-size:11px; }
.panel-heading { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; margin-bottom:8px; }
.panel-overline { color:var(--muted); font:9px var(--font-mono); letter-spacing:.04em; }
.panel-heading h3.panel-title { color:#3C463D; font-size:13px !important; font-weight:600 !important; line-height:1.4 !important; margin:3px 0 0 !important; }
.panel-subtitle { color:var(--muted); font-size:10px; line-height:1.5; margin-top:3px; }
.panel-chip { color:var(--muted); font:9px var(--font-mono); padding:4px 6px; border:1px solid var(--line); border-radius:5px; white-space:nowrap; }
[data-testid="stVerticalBlockBorderWrapper"] { background:white; border:1px solid var(--line); border-radius:10px; box-shadow:none; }
.infographic-panel { min-height:328px; padding:18px 19px; border:1px solid var(--line); border-radius:10px; background:white; overflow:hidden; }
.infographic-head { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; }
.infographic-kicker { color:var(--muted); font:10px/1.2 var(--font-mono); letter-spacing:.04em; }
.infographic-panel h3 { color:#303731; font-size:17px !important; font-weight:600 !important; line-height:1.35 !important; letter-spacing:-.025em; margin:7px 0 3px !important; }
.infographic-panel p { color:var(--muted); font-size:11px; margin:0; line-height:1.5; }
.infographic-highlight { display:flex; flex-direction:column; align-items:flex-end; white-space:nowrap; }
.infographic-highlight strong { color:#333A34; font:650 29px/1 var(--font-ui); letter-spacing:-.04em; }
.infographic-highlight span { color:var(--muted); font:9px/1.3 var(--font-mono); margin-top:5px; }
.infographic-chart { position:relative; margin-top:20px; }
.trend-svg { display:block; width:100%; height:210px; }
.chart-axis { fill:var(--muted); font:10px var(--font-mono); }
.timeline-period { cursor:crosshair; outline:none; }
.period-focus { opacity:0; pointer-events:none; transition:opacity .18s ease; }
.period-hit { pointer-events:all; }
.period-column { transition:filter .18s ease; }
.period-axis { transition:fill .18s ease; }
.timeline-period:hover .period-focus,.timeline-period:focus-visible .period-focus { opacity:1; }
.timeline-period:focus .period-focus { opacity:1; }
.timeline-period:hover .period-column,.timeline-period:focus-visible .period-column { filter:brightness(1.06) drop-shadow(0 2px 2px #38423A40); }
.timeline-period:focus .period-column { filter:brightness(1.06) drop-shadow(0 2px 2px #38423A40); }
.timeline-period:hover .period-axis,.timeline-period:focus-visible .period-axis { fill:#3B453C; }
.timeline-period:focus .period-axis { fill:#3B453C; }
.month-popover { position:absolute; z-index:3; top:3px; display:flex; flex-direction:column; gap:3px; min-width:166px; padding:9px 11px; border:1px solid #4B544C; border-radius:7px; background:#303A32; box-shadow:0 7px 18px #28332A30; color:#FFFFFF; pointer-events:none; visibility:hidden; opacity:0; transform:translateX(-50%); transition:opacity .16s ease; }
.month-popover span { color:#CFD9CF; font:10px var(--font-mono); }
.month-popover strong { color:white; font:600 15px/1.1 var(--font-ui); }
.month-popover small { color:#D5DDD5; font:9px var(--font-ui); white-space:nowrap; }
.infographic-footer { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:7px 12px; padding-top:11px; border-top:1px solid #F0F2EF; color:var(--muted); font-size:10px; }
.chart-legend { display:flex; align-items:center; flex-wrap:wrap; gap:12px; }
.chart-legend span { display:inline-flex; align-items:center; gap:5px; color:var(--muted); font-size:10px; }
.chart-legend i,.severity-legend-row i { display:inline-block; width:7px; height:7px; border-radius:2px; flex:none; }
.chart-footnote { color:var(--muted); font:10px var(--font-mono); }
.chart-footnote b { margin:0 5px; font-weight:400; color:#C3C8C3; }
.severity-visual { display:flex; align-items:center; justify-content:center; gap:12px; min-height:226px; }
.donut-svg { width:46%; max-width:180px; flex:none; }
.donut-segment { cursor:pointer; outline:none; transition:stroke-width .22s ease,opacity .22s ease,filter .22s ease; }
.severity-visual:has(.donut-segment:hover) .donut-segment:not(:hover),.severity-visual:has(.donut-segment:focus-visible) .donut-segment:not(:focus-visible) { opacity:.45; }
.donut-segment:hover,.donut-segment:focus-visible { stroke-width:27; filter:drop-shadow(0 2px 3px #39423A40); }
.donut-default,.donut-hover-value { pointer-events:none; transition:opacity .18s ease; }
.donut-hover-value { opacity:0; }
.severity-visual:has(.donut-segment:hover) .donut-default,.severity-visual:has(.donut-segment:focus-visible) .donut-default,.severity-visual:has(.severity-legend-row:hover) .donut-default,.severity-visual:has(.severity-legend-row:focus-visible) .donut-default { opacity:0; }
.severity-visual:has(.donut-segment:focus) .donut-default,.severity-visual:has(.severity-legend-row:focus) .donut-default { opacity:0; }
.severity-visual:has(.donut-segment.tone-0:focus) .donut-hover-value.tone-0,.severity-visual:has(.severity-legend-row.tone-0:focus) .donut-hover-value.tone-0,.severity-visual:has(.donut-segment.tone-1:focus) .donut-hover-value.tone-1,.severity-visual:has(.severity-legend-row.tone-1:focus) .donut-hover-value.tone-1,.severity-visual:has(.donut-segment.tone-2:focus) .donut-hover-value.tone-2,.severity-visual:has(.severity-legend-row.tone-2:focus) .donut-hover-value.tone-2 { opacity:1; }
.severity-visual:has(.severity-legend-row.tone-0:focus) .donut-segment.tone-0,.severity-visual:has(.severity-legend-row.tone-1:focus) .donut-segment.tone-1,.severity-visual:has(.severity-legend-row.tone-2:focus) .donut-segment.tone-2 { stroke-width:27; filter:drop-shadow(0 2px 3px #39423A40); }
.donut-segment:focus { stroke-width:27; filter:drop-shadow(0 2px 3px #39423A40); }
.severity-visual:has(.donut-segment.tone-0:hover) .donut-hover-value.tone-0,.severity-visual:has(.donut-segment.tone-0:focus-visible) .donut-hover-value.tone-0,.severity-visual:has(.severity-legend-row.tone-0:hover) .donut-hover-value.tone-0,.severity-visual:has(.severity-legend-row.tone-0:focus-visible) .donut-hover-value.tone-0,.severity-visual:has(.donut-segment.tone-1:hover) .donut-hover-value.tone-1,.severity-visual:has(.donut-segment.tone-1:focus-visible) .donut-hover-value.tone-1,.severity-visual:has(.severity-legend-row.tone-1:hover) .donut-hover-value.tone-1,.severity-visual:has(.severity-legend-row.tone-1:focus-visible) .donut-hover-value.tone-1,.severity-visual:has(.donut-segment.tone-2:hover) .donut-hover-value.tone-2,.severity-visual:has(.donut-segment.tone-2:focus-visible) .donut-hover-value.tone-2,.severity-visual:has(.severity-legend-row.tone-2:hover) .donut-hover-value.tone-2,.severity-visual:has(.severity-legend-row.tone-2:focus-visible) .donut-hover-value.tone-2 { opacity:1; }
.severity-visual:has(.severity-legend-row.tone-0:hover) .donut-segment.tone-0,.severity-visual:has(.severity-legend-row.tone-0:focus-visible) .donut-segment.tone-0,.severity-visual:has(.severity-legend-row.tone-1:hover) .donut-segment.tone-1,.severity-visual:has(.severity-legend-row.tone-1:focus-visible) .donut-segment.tone-1,.severity-visual:has(.severity-legend-row.tone-2:hover) .donut-segment.tone-2,.severity-visual:has(.severity-legend-row.tone-2:focus-visible) .donut-segment.tone-2 { stroke-width:27; filter:drop-shadow(0 2px 3px #39423A40); }
.donut-total { fill:#343B35; font:650 29px var(--font-ui); letter-spacing:-.04em; }
.donut-label { fill:var(--muted); font:9px var(--font-mono); letter-spacing:.07em; }
.severity-legend { flex:1; min-width:112px; }
.severity-legend-row { display:grid; grid-template-columns:8px 1fr auto; align-items:center; gap:5px; padding:8px 0; border-bottom:1px solid #F0F2EF; }
.severity-legend-row { border-radius:5px; cursor:pointer; outline:none; transition:background .18s ease,padding .18s ease; }
.severity-legend-row:hover,.severity-legend-row:focus-visible { background:#F4F6F3; padding-left:5px; padding-right:5px; }
.severity-legend-row:focus { background:#F4F6F3; padding-left:5px; padding-right:5px; }
.severity-visual:has(.donut-segment.tone-0:hover) .severity-legend-row.tone-0,.severity-visual:has(.donut-segment.tone-0:focus-visible) .severity-legend-row.tone-0,.severity-visual:has(.donut-segment.tone-1:hover) .severity-legend-row.tone-1,.severity-visual:has(.donut-segment.tone-1:focus-visible) .severity-legend-row.tone-1,.severity-visual:has(.donut-segment.tone-2:hover) .severity-legend-row.tone-2,.severity-visual:has(.donut-segment.tone-2:focus-visible) .severity-legend-row.tone-2 { background:#F4F6F3; padding-left:5px; padding-right:5px; }
.severity-legend-row:last-child { border:0; }
.severity-legend-row span { color:#626C63; font-size:11px; }
.severity-legend-row strong { color:#414A42; font:600 12px var(--font-mono); }
.severity-legend-row small { font:9px var(--font-mono); color:var(--muted); margin-left:2px; }
.severity-legend-row em { grid-column:2/4; color:var(--muted); font:9px var(--font-mono); font-style:normal; margin-top:-4px; }
.severity-share-track { grid-column:2/4; height:3px; margin-top:1px; border-radius:3px; overflow:hidden; background:#EDF0EC; }
.severity-share-track span { display:block; height:100%; border-radius:3px; }
.rank-panel { min-height:485px; }
.rank-description { margin-top:2px !important; }
.rank-leader { display:flex; align-items:flex-end; justify-content:space-between; gap:8px; margin-top:14px; padding:12px 13px; border:1px solid #E9ECE8; border-radius:8px; background:#F5F7F4; }
.rank-leader div { display:flex; flex-direction:column; gap:4px; min-width:0; }
.rank-leader span { color:var(--muted); font:9px/1.2 var(--font-mono); letter-spacing:.04em; }
.rank-leader strong { color:#414A42; font-size:15px; font-weight:600; line-height:1.45; white-space:normal; overflow-wrap:anywhere; word-break:keep-all; }
.rank-leader em { flex:none; color:#414942; font:600 17px/1.1 var(--font-mono); font-style:normal; white-space:nowrap; text-align:right; }
.rank-leader small { display:block; margin-top:4px; color:var(--muted); font:9px/1.2 var(--font-mono); }
.rank-list { margin-top:17px; }
.rank-row { margin-bottom:14px; }
.rank-row { border-radius:6px; outline:none; transition:transform .18s ease,background .18s ease; }
.rank-row:hover,.rank-row:focus-visible { transform:translateX(3px); background:#F7F9F6; }
.rank-row:focus { transform:translateX(3px); background:#F7F9F6; }
.rank-row:last-child { margin-bottom:0; }
.rank-line { display:flex; align-items:baseline; gap:7px; min-width:0; }
.rank-order { color:var(--muted); font:10px var(--font-mono); }
.rank-name { min-width:0; color:#535C54; font-size:11px; font-weight:550; line-height:1.5; white-space:normal; overflow-wrap:anywhere; word-break:keep-all; }
.rank-count { color:#414942; font:600 11px var(--font-mono); margin-left:auto; white-space:nowrap; }
.rank-count small { color:var(--muted); font:9px var(--font-mono); margin-left:2px; }
.rank-track { height:6px; margin:6px 0 2px 22px; border-radius:4px; background:#F0F2EF; overflow:hidden; }
.rank-track span { display:block; height:100%; background:linear-gradient(90deg,#5F6660,#9AA19B); border-radius:4px; }
.rank-track span { transform-origin:left center; transition:filter .18s ease,transform .18s ease; }
.rank-row:hover .rank-track span,.rank-row:focus-visible .rank-track span { filter:brightness(.83); transform:scaleY(1.2); }
.rank-row:focus .rank-track span { filter:brightness(.83); transform:scaleY(1.2); }
.rank-share { margin-left:22px; color:var(--muted); font:8px var(--font-mono); text-align:right; }
.interpret-note { margin:14px 0 0; color:var(--muted); font-size:11px; line-height:1.55; }
.hero h1,.simple-intro h1,.dashboard-row-label h2,.section-heading h2.section-title,.infographic-panel h3 { padding:0 !important; }
.simple-intro { position:relative; display:flex; flex-direction:column; justify-content:center; min-height:180px; padding:26px 29px; overflow:hidden; border:1px solid var(--line); border-radius:10px; background:white center right/cover no-repeat; }
.simple-intro.records { background-image:url('/app/static/hero-records.png'); }
.simple-intro.guide { background-image:url('/app/static/hero-guide.png'); }
.simple-intro.chat { background-image:url('/app/static/hero-guide.png'); }
.simple-intro::before { content:''; position:absolute; inset:0; background:linear-gradient(90deg,rgba(255,255,255,.97) 0%,rgba(255,255,255,.88) 42%,rgba(255,255,255,.08) 82%); }
.simple-intro > * { position:relative; z-index:1; max-width:62%; }
.simple-intro h1 { color:#29332B; font-size:29px !important; font-weight:650 !important; letter-spacing:-.04em; margin:8px 0 4px !important; }
.simple-intro p { color:var(--muted); font-size:12px; margin:0; }
.context-line { margin:12px 0 0; color:var(--muted); font:10px/1.6 var(--font-mono); }
.chat-page-heading { display:flex; align-items:end; justify-content:space-between; gap:16px; margin:23px 0 17px; }
.chat-page-heading span,.chat-options-kicker,.chat-conversation-head span { color:var(--muted); font:600 10px/1.3 var(--font-mono); letter-spacing:.07em; }
.chat-page-heading h2 { color:#202923; font-size:clamp(28px,3vw,34px) !important; font-weight:650 !important; letter-spacing:-.035em; line-height:1.3 !important; margin:0 0 10px !important; padding:0 !important; }
.chat-page-heading p { color:#46534A; font-size:16px; line-height:1.7; margin:0; }
.chat-source-mark { flex:none; padding:7px 10px; background:#EFF3EE; border:1px solid #E2E9E0; border-radius:6px; color:#536D58; font:10px var(--font-mono); }
.st-key-chat_options,.st-key-chat_reference { background:white; border-color:var(--line) !important; border-radius:10px !important; padding:17px !important; }
.st-key-chat_options h3,.st-key-chat_reference h3,.chat-conversation-head h3 { color:#2D352F; font-size:15px !important; font-weight:600 !important; letter-spacing:-.025em; margin:5px 0 10px !important; padding:0 !important; }
.st-key-chat_options [data-testid="stWidgetLabel"] p { color:#6B746D; font-size:11px; font-weight:500; }
.st-key-chat_options [data-testid="stCaptionContainer"],.st-key-chat_reference [data-testid="stCaptionContainer"] { color:var(--muted); font-size:11px; line-height:1.55; }
.chat-conversation-head { display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid var(--line); padding:4px 0 7px; margin:0 0 15px; }
.chat-conversation-head h3 { margin-bottom:0 !important; }
.chat-empty { display:flex; flex-direction:column; align-items:center; justify-content:center; min-height:220px; margin-bottom:15px; padding:25px; border:1px solid #E4EAE3; border-radius:10px; background:radial-gradient(circle at 50% 15%,#F0F5EF,white 64%); text-align:center; }
.chat-empty > span { display:grid; place-items:center; width:40px; height:40px; border:1px solid #D9E5D9; border-radius:11px; background:white; color:#64866A; font-size:19px; }
.chat-empty h3 { margin:15px 0 5px !important; color:#364139; font-size:17px !important; font-weight:600 !important; letter-spacing:-.025em; }
.chat-empty p { max-width:390px; margin:0; color:var(--muted); font-size:12px; line-height:1.65; }
.chat-source-item { margin:7px 0; padding:10px 12px; border:1px solid var(--line); border-radius:7px; background:#FAFBF9; }
.chat-source-item strong { display:block; color:#39463B; font-size:12px; font-weight:600; line-height:1.5; overflow-wrap:anywhere; word-break:break-word; }
.chat-source-item p { margin:3px 0 0 !important; color:var(--muted); font-size:11px; line-height:1.6; overflow-wrap:anywhere; word-break:break-word; }
.chat-source-item a { color:#5D7C62; font-size:11px; line-height:1.6; text-decoration:underline; text-underline-offset:2px; overflow-wrap:anywhere; word-break:break-word; }
[data-testid="stChatMessage"] { background:#F7F9F7; border:1px solid #E7ECE6; border-radius:9px; }
[data-testid="stChatMessage"] h3 { color:#354037; font-size:15px !important; font-weight:600 !important; line-height:1.45 !important; letter-spacing:-.025em; margin:10px 0 7px !important; }
[data-testid="stChatMessage"] li { color:#4E5A50; font-size:12px; line-height:1.7; margin:3px 0; }
[data-testid="stChatMessage"] .infographic-panel { margin-top:13px; min-height:0; padding:14px; }
[data-testid="stChatMessage"] .infographic-head { gap:8px; }
[data-testid="stChatMessage"] .infographic-panel h3 { margin:6px 0 3px !important; font-size:14px !important; }
[data-testid="stChatMessage"] .infographic-highlight strong { font-size:22px; }
[data-testid="stChatMessage"] .trend-svg { height:185px; }
[data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:8px; overflow:hidden; }
[data-testid="stButton"] button,[data-testid="stDownloadButton"] button,[data-testid="stFormSubmitButton"] button,[data-testid="stLinkButton"] button,[data-testid="stFileUploader"] button,[data-testid="stChatInput"] button,[class*="st-key-nav_"] button { height:auto !important; min-height:40px !important; border-radius:7px; font-weight:500; }
button:focus-visible,input:focus-visible,textarea:focus-visible,[role="combobox"]:focus-visible,a:focus-visible { outline:2px solid #638B73 !important; outline-offset:2px !important; }
hr { border-color:var(--line); }
@media (max-width:1100px) { [data-testid="stApp"] { width:calc(100vw - 80px) !important; top:24px !important; height:calc(100vh - 48px) !important; } .block-container { padding-left:18px; padding-right:18px; } .hero { min-height:209px; } .hero-content { padding:23px; } }
@media (max-width:780px) { .block-container { padding:66px 14px 45px; } .workspace-right { display:none; } .hero { min-height:190px; background-position:60% center; } .hero:before { background:linear-gradient(90deg,#FFFFFFF7 0%,#FFFFFFE8 52%,#FFFFFF55 100%); } .hero-content { padding:20px; } .hero h1 { font-size:27px; } .st-key-hero_ctas { width:100%; margin:8px 0 0; } .st-key-dashboard_main [data-testid="stHorizontalBlock"] { flex-wrap:wrap !important; } .st-key-dashboard_main [data-testid="stColumn"] { flex:1 1 100% !important; width:100% !important; } .section-description { display:none; } }
@media (max-width:780px) { [data-testid="stButton"] button,[data-testid="stDownloadButton"] button,[data-testid="stFormSubmitButton"] button,[data-testid="stLinkButton"] button,[data-testid="stFileUploader"] button,[data-testid="stChatInput"] button,[class*="st-key-nav_"] button { min-height:44px !important; } }
@media (max-width:780px) { html,body,#root,[data-testid="stScreencast"] { background:var(--canvas) !important; } [data-testid="stApp"] { top:0 !important; left:0 !important; width:100vw !important; height:100vh !important; transform:none; border:0; border-radius:0; box-shadow:none; } [data-testid="stSidebar"] { width:min(300px,80vw) !important; min-width:min(300px,80vw) !important; max-width:min(300px,80vw) !important; } }
@media (max-width:580px) { .severity-visual { justify-content:flex-start; } .donut-svg { width:43%; } .infographic-panel { padding:15px; } .infographic-highlight strong { font-size:24px; } .simple-intro { min-height:160px; padding:20px; background-position:62% center; } .simple-intro > * { max-width:76%; } .simple-intro::before { background:linear-gradient(90deg,#FFFFFFF8 0%,#FFFFFFE9 55%,#FFFFFF55 100%); } }
@media (max-width:580px) { .st-key-feature_grid [data-testid="stHorizontalBlock"],.st-key-distribution_grid [data-testid="stHorizontalBlock"],.st-key-quick_grid [data-testid="stHorizontalBlock"] { flex-wrap:wrap !important; } .st-key-feature_grid [data-testid="stColumn"],.st-key-distribution_grid [data-testid="stColumn"] { flex:1 1 100% !important; width:100% !important; } .st-key-quick_grid [data-testid="stColumn"] { flex:1 1 44% !important; width:44% !important; } .hero { background-position:68% center; } .hero p { max-width:215px; } .filter-strip { align-items:flex-start; } .filter-tabs { max-width:100%; overflow:auto; } }
@media (max-width:780px) { .chat-page-heading { align-items:flex-start; flex-direction:column; } .chat-source-mark { display:none; } }
@media (max-width:780px) { [data-testid="stHorizontalBlock"]:has(.st-key-chat_options) { flex-wrap:wrap !important; } [data-testid="stHorizontalBlock"]:has(.st-key-chat_options) > [data-testid="stColumn"] { flex:1 1 100% !important; width:100% !important; } }
@media (max-width:580px) { .st-key-chat_field_shortcuts [data-testid="stHorizontalBlock"] { flex-wrap:wrap !important; } .st-key-chat_field_shortcuts [data-testid="stColumn"] { flex:1 1 calc(50% - 5px) !important; width:calc(50% - 5px) !important; } }
.sidebar-brand-sub,.sidebar-section,.sidebar-help,.sidebar-foot,.recent-date,.sidebar-live-head,.sidebar-live-metric span,.sidebar-live-note,.crumbs,.workspace-right,.quick-icon,
.data-notice,.filter-tab:not(.active),.dashboard-row-label span,.feature-card-sub,.feature-unit,.pillar-sub,.quick-label,
.distribution-description,.distribution-meta,.section-index,.section-description,.panel-overline,.panel-subtitle,.panel-chip,
.infographic-kicker,.infographic-panel p,.infographic-highlight span,.infographic-footer,.chart-legend span,.chart-footnote,
.severity-legend-row small,.severity-legend-row em,.rank-leader span,.rank-leader small,.rank-order,.rank-count small,.rank-share,
.interpret-note,.simple-intro p,.context-line,.chat-page-heading p,.chat-source-mark,.chat-empty p,.chat-source-item p,
.chat-options-kicker,.chat-conversation-head span,[data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color:var(--muted) !important; }
.chart-axis { fill:var(--muted) !important; }
/* The chatbot uses a calm, Toss-inspired workspace instead of the dashboard's framed shell. */
body:has(.chat-landing) { background:#F5F7FB !important; }
body:has(.chat-landing) [data-testid="stApp"] { top:0 !important; right:0 !important; bottom:0 !important; left:0 !important; width:100vw !important; height:100vh !important; min-height:100vh !important; transform:none !important; border:0 !important; border-radius:0 !important; box-shadow:none !important; overflow:auto !important; background:radial-gradient(ellipse at 74% 10%,#EAF2FF 0,transparent 38%),#F5F7FB !important; }
body:has(.chat-landing) [data-testid="stAppViewContainer"],body:has(.chat-landing) [data-testid="stHeader"] { background:transparent !important; }
body:has(.chat-landing) .block-container { width:100% !important; max-width:1080px !important; margin:0 auto !important; padding:58px 36px 84px !important; }
body:has(.chat-landing) .workspace-bar { min-height:24px; margin-bottom:24px; }
body:has(.chat-landing) .crumb-back { border:0; background:transparent; color:#8B95A1; }
body:has(.chat-landing) .crumb-current { color:#4E5968; font-family:var(--font-ui); font-size:12px; font-weight:550; }
.chat-landing { display:grid; grid-template-columns:minmax(0,1fr) minmax(360px,1fr); align-items:center; gap:42px; min-height:410px; margin:0 0 4px; }
.chat-hero-copy { position:relative; z-index:1; }
.chat-kicker { display:flex; align-items:center; gap:8px; margin:0 0 16px; color:#4777B8; font-size:13px; font-weight:600; letter-spacing:-.015em; line-height:1.4; }
.chat-kicker::before { content:""; width:8px; height:8px; border-radius:50%; background:#4388F5; box-shadow:0 0 0 4px #E5EFFF; }
.chat-hero-copy h1 { margin:0 0 16px !important; color:#1D2939; font-size:clamp(38px,4.4vw,52px) !important; font-weight:680 !important; letter-spacing:-.065em !important; line-height:1.18 !important; }
.chat-hero-copy h1 em { color:#3478E5; font-style:normal; }
.chat-hero-copy p { max-width:400px; margin:0 !important; color:#68778A; font-size:15px; line-height:1.8; word-break:keep-all; }
.chat-site-chip { display:inline-flex; align-items:center; gap:9px; max-width:100%; margin-top:24px; padding:9px 12px; border:1px solid #E0E8F2; border-radius:999px; background:rgba(255,255,255,.76); color:#425267; font-size:12px; box-shadow:0 2px 8px rgba(35,58,90,.035); }
.chat-site-chip i { width:7px; height:7px; flex:none; border-radius:50%; background:#3886ED; box-shadow:0 0 0 3px #E7F1FF; }
.chat-site-chip span { max-width:275px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-weight:570; }
.chat-site-chip small { color:#8B97A7; font-size:10px; }
.chat-site-chip-empty i { background:#9AA8BA; box-shadow:0 0 0 3px #EFF2F6; }
.safety-motion-stage { position:relative; display:grid; place-items:center; min-height:350px; isolation:isolate; }
.motion-orbit { position:absolute; z-index:-1; border:1px solid rgba(100,145,203,.15); border-radius:50%; }
.motion-orbit-one { width:330px; height:330px; animation:orbit-breathe 7s ease-in-out infinite; }
.motion-orbit-two { width:258px; height:258px; border-style:dashed; border-color:rgba(100,145,203,.17); animation:orbit-turn 32s linear infinite; }
.motion-glow { position:absolute; z-index:-2; width:250px; height:220px; border-radius:50%; background:#DCEAFF; filter:blur(42px); opacity:.72; animation:glow-breathe 6s ease-in-out infinite; }
.safety-preview-card { position:relative; width:min(100%,336px); padding:21px 22px 17px; border:1px solid rgba(224,232,242,.95); border-radius:21px; background:rgba(255,255,255,.94); box-shadow:0 22px 58px rgba(44,71,111,.12),0 4px 12px rgba(44,71,111,.04); backdrop-filter:blur(12px); animation:card-hover 6.4s ease-in-out infinite; }
.safety-preview-head { display:flex; align-items:center; justify-content:space-between; color:#77869A; font:600 9px/1.4 var(--font-mono); letter-spacing:.11em; }
.safety-preview-head i { width:7px; height:7px; border-radius:50%; background:#43B88A; box-shadow:0 0 0 4px #E8F8F1; }
.safety-preview-meta { margin-top:12px; overflow:hidden; color:#8290A2; font-size:10px; text-overflow:ellipsis; white-space:nowrap; }
.safety-preview-count { display:flex; align-items:baseline; gap:9px; margin:2px 0 11px; }
.safety-preview-count strong { color:#1D2A3A; font-size:42px; font-weight:680; letter-spacing:-.06em; line-height:1.12; font-variant-numeric:tabular-nums; }
.safety-preview-count span { color:#536276; font-size:13px; font-weight:550; }
.safety-preview-list { display:flex; flex-direction:column; }
.motion-task-row { display:grid; grid-template-columns:48px minmax(0,1fr) auto; align-items:center; gap:8px; min-height:38px; border-top:1px solid #EEF1F5; }
.motion-task-row time { color:#758398; font:550 10px/1 var(--font-mono); font-variant-numeric:tabular-nums; }
.motion-task-row strong { min-width:0; overflow:hidden; color:#344256; font-size:11px; font-weight:570; text-overflow:ellipsis; white-space:nowrap; }
.motion-task-row small { color:#8D99A9; font-size:9px; }
.motion-empty-row { padding:12px 0; border-top:1px solid #EEF1F5; color:#7A8798; font-size:11px; }
.motion-step time { display:grid; place-items:center; width:23px; height:23px; border-radius:8px; background:#EEF4FD; color:#4B7EC0; font-size:9px; }
.safety-preview-foot { display:flex; align-items:center; gap:8px; margin-top:12px; padding:9px 10px; border-radius:10px; background:#F4F8FE; color:#56749D; font-size:10px; font-weight:550; }
.preview-check { display:grid; place-items:center; width:17px; height:17px; border-radius:50%; background:#E3F4EC; color:#29966A; font-size:10px; font-weight:700; }
.motion-float { position:absolute; display:flex; align-items:center; gap:8px; padding:10px 13px; border:1px solid rgba(226,234,244,.95); border-radius:12px; background:rgba(255,255,255,.91); box-shadow:0 10px 24px rgba(44,71,111,.08); color:#536276; font-size:10px; font-weight:570; backdrop-filter:blur(8px); }
.motion-float span { display:grid; place-items:center; width:20px; height:20px; border-radius:7px; background:#EDF4FF; color:#397DD9; font:600 9px/1 var(--font-mono); }
.motion-float-top { top:28px; right:0; animation:float-side 5.5s ease-in-out infinite; }
.motion-float-bottom { bottom:31px; left:-3px; animation:float-side 6.2s ease-in-out infinite reverse; }
.st-key-daily_briefing_upload { width:max-content; margin:8px 0 12px; padding:0 !important; border:0 !important; border-radius:999px !important; background:transparent !important; box-shadow:none !important; }
.st-key-daily_briefing_upload [data-testid="stPopoverButton"] { min-height:38px !important; border:1px solid #E0E7F0 !important; border-radius:999px !important; background:rgba(255,255,255,.72) !important; color:#50627A !important; font-size:12px !important; font-weight:560 !important; box-shadow:none !important; }
.st-key-daily_briefing_upload [data-testid="stPopoverButton"]:hover { border-color:#BFD2EB !important; background:#FFFFFF !important; color:#3478D3 !important; }
.chat-question-heading { display:none !important; }
.st-key-chat_question_suggestion_0,.st-key-chat_question_suggestion_1,.st-key-chat_question_suggestion_2 { display:none !important; }
.chat-input-hint { margin:8px 4px 0; color:#929EAE; font-size:11px; text-align:center; }
[data-testid="stChatInput"] { border:1px solid #DFE7F1 !important; border-radius:18px !important; background:rgba(255,255,255,.98) !important; box-shadow:0 10px 30px rgba(36,64,105,.08),0 2px 5px rgba(36,64,105,.03) !important; transition:border-color .2s ease,box-shadow .2s ease,transform .2s ease; }
[data-testid="stChatInput"]:focus-within { border-color:#A9C8F3 !important; box-shadow:0 12px 32px rgba(45,101,181,.13),0 0 0 4px rgba(67,136,245,.07) !important; transform:translateY(-1px); }
[data-testid="stChatInput"] textarea { min-height:56px !important; padding-top:16px !important; color:#253348 !important; font-size:15px !important; }
.st-key-daily_briefing_upload { display:flex !important; width:max-content !important; min-height:0 !important; margin:0 0 7px !important; padding:0 !important; border:0 !important; border-radius:999px !important; background:transparent !important; box-shadow:none !important; }
.st-key-daily_briefing_upload > div,
.st-key-daily_briefing_upload [data-testid="stVerticalBlockBorderWrapper"] { width:max-content !important; min-height:0 !important; margin:0 !important; padding:0 !important; border:0 !important; border-radius:0 !important; background:transparent !important; box-shadow:none !important; }
.st-key-daily_briefing_upload [data-testid="stPopoverButton"] { min-height:38px !important; padding:0 14px !important; border:1px solid #DEE7F1 !important; border-radius:999px !important; background:rgba(255,255,255,.78) !important; color:#53657D !important; font-size:12px !important; font-weight:560 !important; box-shadow:none !important; }
.st-key-daily_briefing_upload [data-testid="stPopoverButton"]:hover { border-color:#BFD3EE !important; background:#FFFFFF !important; color:#3478D3 !important; }
body:has(.chat-landing) [data-testid="stFileUploader"] button [data-testid="stMarkdownContainer"] p { visibility:hidden !important; font-size:0 !important; }
body:has(.chat-landing) [data-testid="stFileUploader"] button [data-testid="stMarkdownContainer"] p::after { content:"파일 선택"; visibility:visible; color:#246FDB; font-size:13px; line-height:1.4; }
.safety-preview-head i { background:#4388F5; box-shadow:0 0 0 4px #EAF2FF; }
.preview-check { width:7px; height:7px; border-radius:50%; background:#4388F5; box-shadow:0 0 0 3px #E3EEFC; }
.st-key-daily_briefing_upload [data-testid="stFileUploader"] section { border:1px dashed #CCD8E8 !important; border-radius:13px !important; background:#F7F9FC !important; }
.st-key-daily_briefing_upload [data-testid="stFileUploader"] section:hover { border-color:#8CB3E8 !important; background:#F2F7FF !important; }
.st-key-daily_briefing_upload [data-testid="stFileUploader"] button { border:0 !important; border-radius:9px !important; background:#EAF2FE !important; color:#246FDB !important; }
.st-key-daily_briefing_upload [data-testid="stFileUploader"] button [data-testid="stMarkdownContainer"] p { visibility:hidden; font-size:0 !important; }
.st-key-daily_briefing_upload [data-testid="stFileUploader"] button [data-testid="stMarkdownContainer"] p::after { content:"파일 선택"; visibility:visible; color:#246FDB; font-size:13px; }
.st-key-daily_briefing_upload [data-testid="stFileUploaderDropzoneInstructions"] span { color:transparent !important; font-size:0 !important; }
.st-key-daily_briefing_upload [data-testid="stFileUploaderDropzoneInstructions"] span::after { content:"최대 10MB · XLSX"; color:#6B7684; font-size:12px; }
@keyframes card-hover { 0%,100% { transform:translateY(0) rotate(-.4deg); } 50% { transform:translateY(-8px) rotate(.4deg); } }
@keyframes float-side { 0%,100% { transform:translate3d(0,0,0); } 50% { transform:translate3d(0,-7px,0); } }
@keyframes orbit-breathe { 0%,100% { transform:scale(.98); opacity:.72; } 50% { transform:scale(1.04); opacity:1; } }
@keyframes orbit-turn { to { transform:rotate(360deg); } }
@keyframes glow-breathe { 0%,100% { transform:scale(.96); opacity:.55; } 50% { transform:scale(1.08); opacity:.82; } }
.chat-home-heading { margin:0 0 24px; }
.chat-kicker { display:flex; align-items:center; gap:7px; margin:0 0 11px; color:#4777B8; font-size:12px; font-weight:600; letter-spacing:-.01em; line-height:1.4; }
.chat-kicker::before { content:""; width:7px; height:7px; border-radius:50%; background:#4388F5; box-shadow:0 0 0 4px #E5EFFF; }
.chat-home-heading h1 { margin:0 0 8px !important; color:#191F28; font-size:36px !important; font-weight:680 !important; letter-spacing:-.055em; line-height:1.22 !important; }
.chat-home-heading p { margin:0; color:#697586; font-size:15px; line-height:1.65; }
.chat-day-field-label { margin:0 0 5px; color:#8B95A1; font-size:11px; font-weight:550; }
.st-key-chat_current_top [data-baseweb="select"] > div { min-height:42px; border:1px solid #E5E8EB; border-radius:10px; background:#FFFFFF; }
.st-key-chat_current_actions [data-testid="stHorizontalBlock"] { align-items:center; }
.st-key-daily_briefing_upload,.st-key-chat_current_plan { margin:0 0 16px; padding:25px 26px !important; border:1px solid #E6EBF2 !important; border-radius:21px !important; background:rgba(255,255,255,.96) !important; box-shadow:0 12px 34px rgba(31,52,82,.045),0 2px 6px rgba(31,52,82,.025) !important; }
.st-key-daily_briefing_upload [data-testid="stHorizontalBlock"] { align-items:center; gap:14px; }
.chat-upload-title h3 { margin:0 0 5px !important; padding:0 !important; color:#191F28; font-size:19px !important; font-weight:630 !important; letter-spacing:-.04em; }
.chat-upload-title p { margin:0; color:#6B7684; font-size:12px; line-height:1.6; }
.st-key-chat_plan_sample_download button { min-height:40px !important; padding:0 13px !important; border:1px solid #E5E8EB !important; border-radius:10px !important; background:#FFFFFF !important; color:#465262 !important; font-size:12px !important; font-weight:570 !important; box-shadow:none !important; white-space:nowrap; }
.st-key-chat_plan_sample_download button:hover { border-color:#B9D0F2 !important; background:#F6F9FE !important; color:#246FDB !important; }
.st-key-daily_briefing_upload h3 { margin:0 0 17px !important; color:#191F28; font-size:18px !important; font-weight:620 !important; letter-spacing:-.035em; }
.st-key-daily_briefing_upload [data-testid="stWidgetLabel"] p { color:#4E5968; font-size:13px; font-weight:560; }
.st-key-daily_briefing_upload [data-testid="stFileUploader"] section { border:1px solid #E5E8EB; border-radius:14px; background:#F7F8FA; transition:border-color .16s ease,background .16s ease; }
.st-key-daily_briefing_upload [data-testid="stFileUploader"] section:hover { border-color:#A9C8F7; background:#F5F8FE; }
.st-key-daily_briefing_upload [data-testid="stFileUploader"] button { border:0 !important; border-radius:10px !important; background:#EAF2FE !important; color:#246FDB !important; font-weight:620 !important; }
.st-key-daily_briefing_upload [data-testid="stFileUploader"] button [data-testid="stMarkdownContainer"] p { visibility:hidden; font-size:0 !important; }
.st-key-daily_briefing_upload [data-testid="stFileUploader"] button [data-testid="stMarkdownContainer"] p::after { content:"파일 선택"; visibility:visible; color:#246FDB; font-size:13px; line-height:1.4; }
.st-key-daily_briefing_upload [data-testid="stFileUploaderDropzoneInstructions"] span { color:transparent !important; font-size:0 !important; }
.st-key-daily_briefing_upload [data-testid="stFileUploaderDropzoneInstructions"] span::after { content:"최대 10MB · XLSX"; color:#6B7684; font-size:12px; line-height:1.4; }
.st-key-daily_briefing_upload [data-testid="stCaptionContainer"] { color:#6B7684; font-size:12px; line-height:1.65; }
.chat-plan-location { display:flex; align-items:center; gap:8px; margin:4px 0 12px; color:#596575; font-size:12px; }
.chat-plan-location span { color:#8B95A1; }
.chat-plan-location strong { color:#465262; font-weight:570; }
.chat-plan-preview-head { display:flex; align-items:center; justify-content:space-between; gap:12px; margin:12px 0 6px; padding-top:13px; border-top:1px solid #EEF0F3; }
.chat-plan-preview-head strong { min-width:0; color:#303A49; font-size:13px; font-weight:600; overflow-wrap:anywhere; }
.chat-plan-preview-head span { flex:none; color:#6B7684; font-size:11px; }
.st-key-chat_current_plan { padding:19px 24px !important; }
.st-key-chat_current_plan [data-testid="stWidgetLabel"] p { color:#8B95A1; font-size:11px; font-weight:560; }

.chat-current-head { display:flex; align-items:center; justify-content:space-between; gap:14px; margin:1px 0 10px; }
.chat-current-head>div { display:flex; flex-direction:column; gap:4px; min-width:0; }
.chat-current-head>div span { color:#8B95A1; font-size:11px; }
.chat-current-head>div strong { color:#202A38; font-size:19px; font-weight:650; letter-spacing:-.035em; overflow-wrap:anywhere; }
.chat-plan-status { flex:none; padding:6px 10px; border:1px solid #E1ECFC; border-radius:99px; background:#F2F7FF; color:#3977CC; font-size:11px; font-weight:600; }
.chat-day-summary { display:flex; align-items:center; gap:7px; margin:17px 0 8px; padding-bottom:10px; border-bottom:1px solid #EDF0F4; color:#667386; font-size:13px; font-weight:550; }
.chat-day-summary strong { display:inline-grid; place-items:center; min-width:25px; height:25px; margin-left:2px; padding:0 6px; border-radius:8px; background:#EAF2FF; color:#3478D3; font-size:12px; font-weight:650; }
.chat-work-row { display:grid; grid-template-columns:112px minmax(0,1fr) auto; align-items:center; gap:13px; min-height:48px; padding:7px 2px; border-top:1px solid #F2F4F7; transition:background .16s ease; }
.chat-work-row:hover { background:#FAFBFD; }
.chat-work-row span { display:inline-flex; width:max-content; padding:5px 8px; border-radius:7px; background:#F2F5F9; color:#647184; font-size:11px; font-weight:550; font-variant-numeric:tabular-nums; }
.chat-work-row strong { min-width:0; color:#283445; font-size:14px; font-weight:570; overflow-wrap:anywhere; }
.chat-work-row small { padding:4px 8px; border-radius:7px; background:#F7F8FA; color:#788495; font-size:11px; }
.chat-plan-empty { display:flex; flex-direction:column; gap:4px; margin:12px 0; padding:14px 16px; border-radius:12px; background:#F7F8FA; }
.chat-plan-empty strong { color:#303A49; font-size:13px; font-weight:600; }
.chat-plan-empty span { color:#6B7684; font-size:12px; line-height:1.55; }
.st-key-chat_plan_replace_button button { min-height:40px !important; margin-top:8px; border:1px solid #E5E8EB !important; border-radius:10px !important; background:#FFFFFF !important; color:#4E5968 !important; font-size:13px !important; font-weight:550 !important; box-shadow:none !important; }
.st-key-chat_plan_replace_button button:hover { border-color:#B9D0F2 !important; background:#F6F9FE !important; color:#246FDB !important; }
.st-key-daily_briefing_apply button,.st-key-daily_briefing_repeat button { min-height:50px !important; border:0 !important; border-radius:13px !important; background:linear-gradient(100deg,#397FF0,#3475E8) !important; color:#FFFFFF !important; font-size:14px !important; font-weight:620 !important; box-shadow:0 5px 12px rgba(49,117,232,.18) !important; transition:background .16s ease,transform .16s ease; }
.st-key-daily_briefing_apply button:hover,.st-key-daily_briefing_repeat button:hover { background:#246FDB !important; transform:translateY(-1px); }
.st-key-chat_options,.st-key-chat_reference { border:0 !important; border-radius:16px !important; background:white !important; box-shadow:0 1px 2px rgba(15,23,42,.035) !important; }
.chat-question-heading { display:flex; flex-direction:column; gap:5px; margin:32px 0 13px; }
.chat-question-heading strong { color:#202A38; font-size:18px; font-weight:650; letter-spacing:-.035em; }
.chat-question-heading span { color:#778294; font-size:13px; }
.st-key-chat_question_suggestion_0 button,.st-key-chat_question_suggestion_1 button,.st-key-chat_question_suggestion_2 button { min-height:64px !important; padding:11px 14px !important; justify-content:flex-start; border:1px solid #E6EBF2 !important; border-radius:15px !important; background:#FFFFFF !important; color:#465262 !important; font-size:13px !important; font-weight:550 !important; line-height:1.5 !important; box-shadow:0 3px 10px rgba(31,52,82,.035) !important; text-align:left; box-shadow:none !important; white-space:normal !important; transition:border-color .16s ease,background .16s ease,color .16s ease; }
.st-key-chat_question_suggestion_0 button:hover,.st-key-chat_question_suggestion_1 button:hover,.st-key-chat_question_suggestion_2 button:hover { border-color:#C7D9F4 !important; background:#F7FAFF !important; color:#246FDB !important; transform:translateY(-1px); }
.st-key-chat_question_suggestion_0 button::before,.st-key-chat_question_suggestion_1 button::before,.st-key-chat_question_suggestion_2 button::before { content:""; display:block; flex:0 0 7px; width:7px; height:7px; margin:0 10px 0 2px; border-radius:50%; background:#4388F5; box-shadow:0 0 0 4px #EDF4FF; }
.chat-empty { border:0; border-radius:16px; background:#FFFFFF; box-shadow:0 1px 2px rgba(15,23,42,.04); }
.chat-empty>span { border-color:#DCE9FC; background:#F2F7FF; color:#3182F6; }
.chat-source-item { border-color:#E9EDF2; border-radius:12px; background:#F7F8FA; }
.chat-source-item a { color:#286FD2; }
[data-testid="stChatMessage"] { border:1px solid #E8EDF2; border-radius:16px; background:#FFFFFF; }
[data-testid="stChatInput"] { border:1px solid #E3E9F1 !important; border-radius:16px !important; background:#FFFFFF !important; box-shadow:0 5px 18px rgba(31,52,82,.04) !important; }
[data-testid="stChatInput"] textarea { font-size:15px !important; }
[data-testid="stChatInput"] textarea:focus { border-color:#79A9F7 !important; box-shadow:0 0 0 3px rgba(49,130,246,.12) !important; }
body:has(.chat-landing) [data-testid="stChatInput"] { border:1px solid rgba(255,255,255,.9) !important; border-radius:20px !important; background:rgba(255,255,255,.68) !important; box-shadow:0 12px 34px rgba(45,78,124,.08),inset 0 1px 0 rgba(255,255,255,.9) !important; backdrop-filter:blur(18px) saturate(1.18); transition:background .2s ease,border-color .2s ease,box-shadow .2s ease,transform .2s ease; }
body:has(.chat-landing) [data-testid="stChatInput"]:hover { border-color:rgba(126,168,224,.55) !important; background:rgba(255,255,255,.82) !important; box-shadow:0 16px 38px rgba(45,78,124,.12),inset 0 1px 0 #FFFFFF !important; transform:translateY(-2px); }
body:has(.chat-landing) [data-testid="stChatInput"]:focus-within { border-color:rgba(83,143,224,.72) !important; outline:2px solid rgba(83,143,224,.22) !important; outline-offset:3px; background:rgba(255,255,255,.92) !important; box-shadow:0 16px 38px rgba(45,98,168,.13),0 0 0 4px rgba(67,136,245,.08),inset 0 1px 0 #FFFFFF !important; transform:translateY(-2px); }
body:has(.chat-landing) [data-testid="stChatInput"] [data-baseweb="textarea"] { border:0 !important; outline:0 !important; background:transparent !important; box-shadow:none !important; }
body:has(.chat-landing) [data-testid="stChatInput"] textarea:focus { border:0 !important; outline:0 !important; box-shadow:none !important; }
body:has(.chat-landing) [data-testid="stChatInput"] textarea { height:56px !important; min-height:56px !important; max-height:56px !important; overflow-x:auto !important; overflow-y:hidden !important; resize:none !important; white-space:nowrap !important; padding-top:16px !important; }
body:has(.chat-landing) [data-testid="stChatMessage"]:has(.safety-report) { border-color:rgba(255,255,255,.92) !important; background:rgba(255,255,255,.72) !important; box-shadow:0 18px 48px rgba(43,72,116,.08),inset 0 1px 0 rgba(255,255,255,.9) !important; backdrop-filter:blur(16px) saturate(1.12); }
body:has(.chat-landing-welcome) { overflow:hidden !important; background:#F7FAFE !important; }
body:has(.chat-landing-welcome) [data-testid="stApp"] { top:0 !important; right:0 !important; bottom:0 !important; left:0 !important; width:100vw !important; height:100vh !important; min-height:100vh !important; transform:none !important; border:0 !important; border-radius:0 !important; box-shadow:none !important; overflow:hidden !important; background:radial-gradient(ellipse at 10% 4%,rgba(174,207,251,.28) 0,transparent 32%),radial-gradient(ellipse at 94% 92%,rgba(172,224,247,.24) 0,transparent 34%),#F7FAFE !important; }
body:has(.chat-landing-welcome) [data-testid="stAppViewContainer"],body:has(.chat-landing-welcome) [data-testid="stHeader"] { background:transparent !important; }
body:has(.chat-landing-welcome) .block-container { width:100% !important; max-width:none !important; min-height:100vh !important; padding:0 !important; }
body:has(.chat-landing-welcome) .workspace-bar,body:has(.chat-landing-welcome) [data-testid="stAlert"],body:has(.chat-landing-welcome) [data-testid="stExpander"] { display:none !important; }
body:has(.chat-conversation-active) { background:#F5F8FC !important; }
body:has(.chat-conversation-active) [data-testid="stApp"] { top:0 !important; right:0 !important; bottom:0 !important; left:0 !important; width:100vw !important; height:100vh !important; min-height:100vh !important; transform:none !important; border:0 !important; border-radius:0 !important; box-shadow:none !important; background:radial-gradient(ellipse at 86% 2%,rgba(208,228,255,.42) 0,transparent 34%),#F5F8FC !important; }
body:has(.chat-conversation-active) [data-testid="stAppViewContainer"],body:has(.chat-conversation-active) [data-testid="stHeader"] { background:transparent !important; }
body:has(.chat-conversation-active) .block-container { width:100% !important; max-width:1020px !important; margin:0 auto !important; padding:34px 28px 104px !important; }
body:has(.chat-conversation-active) [data-testid="stChatInput"] { width:min(880px,100%) !important; margin:14px auto !important; border-color:rgba(255,255,255,.92) !important; background:rgba(255,255,255,.76) !important; backdrop-filter:blur(16px) saturate(1.12); }
/* The entry scene stays deliberately quiet: edge light and one glass prompt, no central emblem. */
.chat-landing-welcome { position:fixed; inset:0; z-index:2; overflow:hidden; pointer-events:none; }
.welcome-blue-haze { position:absolute; top:37%; left:50%; width:min(1080px,120vw); height:420px; transform:translateX(-50%); border-radius:50%; background:radial-gradient(ellipse,rgba(184,215,255,.32) 0,rgba(211,231,255,.22) 40%,rgba(243,248,255,0) 74%); filter:blur(34px); animation:welcome-haze 8s ease-in-out infinite; }
.welcome-window-edges { position:absolute; inset:16px; border:1px solid transparent; border-radius:30px; opacity:.82; background:linear-gradient(135deg,rgba(255,255,255,.92),rgba(147,187,240,.18) 78%,transparent) top left/230px 1px no-repeat,linear-gradient(135deg,rgba(255,255,255,.84),rgba(147,187,240,.14) 78%,transparent) top left/1px 190px no-repeat,linear-gradient(225deg,rgba(255,255,255,.86),rgba(147,187,240,.16) 78%,transparent) top right/230px 1px no-repeat,linear-gradient(225deg,rgba(255,255,255,.8),rgba(147,187,240,.14) 78%,transparent) top right/1px 180px no-repeat,linear-gradient(315deg,rgba(117,165,229,.3),rgba(255,255,255,.5) 30%,transparent) bottom right/250px 1px no-repeat,linear-gradient(315deg,rgba(117,165,229,.24),rgba(255,255,255,.5) 30%,transparent) bottom right/1px 190px no-repeat,linear-gradient(45deg,rgba(117,165,229,.2),rgba(255,255,255,.45) 30%,transparent) bottom left/210px 1px no-repeat,linear-gradient(45deg,rgba(117,165,229,.16),rgba(255,255,255,.42) 30%,transparent) bottom left/1px 170px no-repeat; transition:opacity .45s ease,filter .45s ease; animation:welcome-edge-breathe 8s ease-in-out infinite; }
body:has(.chat-landing-welcome):has([data-testid="stChatInput"]:hover) .welcome-window-edges,body:has(.chat-landing-welcome):has([data-testid="stChatInput"]:focus-within) .welcome-window-edges { opacity:1; filter:drop-shadow(0 0 8px rgba(99,157,230,.28)); }
body:has(.chat-landing-welcome) [data-testid="stBottomBlockContainer"] { position:fixed !important; top:50% !important; bottom:auto !important; left:0 !important; z-index:25 !important; width:100% !important; padding:0 20px !important; transform:translateY(-50%) !important; background:transparent !important; }
body:has(.chat-landing-welcome) [data-testid="stBottomBlockContainer"] [data-testid="stChatInput"] { position:relative !important; top:auto !important; bottom:auto !important; width:min(760px,calc(100vw - 40px)) !important; margin:0 auto !important; transform:none !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"],body:has(.chat-landing-welcome) [data-testid="stChatInput"] > div,body:has(.chat-landing-welcome) [data-testid="stChatInput"] [data-baseweb="textarea"] { border-radius:999px !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"] { position:fixed !important; top:50% !important; left:50% !important; bottom:auto !important; z-index:30 !important; width:min(760px,calc(100vw - 40px)) !important; margin:0 !important; transform:translate(-50%,-50%) !important; border-radius:999px !important; border:1px solid rgba(255,255,255,.94) !important; background:linear-gradient(120deg,rgba(255,255,255,.82),rgba(244,249,255,.72) 48%,rgba(255,255,255,.84)) !important; box-shadow:0 22px 64px rgba(60,104,164,.12),0 5px 18px rgba(72,113,169,.06),inset 0 1px 0 rgba(255,255,255,.98),inset 0 -1px 0 rgba(123,169,224,.1) !important; backdrop-filter:blur(28px) saturate(1.28) !important; transition:transform .42s cubic-bezier(.18,.78,.2,1),background .35s ease,border-color .35s ease,box-shadow .35s ease,filter .35s ease !important; animation:prompt-arrive .9s cubic-bezier(.16,.82,.24,1) both; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"]::before { content:""; position:absolute; top:1px; left:8%; right:8%; height:1px; border-radius:999px; pointer-events:none; background:linear-gradient(90deg,transparent,rgba(255,255,255,.98) 28%,rgba(255,255,255,.98) 72%,transparent); opacity:.9; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"]:hover { transform:translate(-50%,-50%) scale(1.012) !important; border-color:rgba(154,193,244,.72) !important; background:linear-gradient(120deg,rgba(255,255,255,.93),rgba(238,247,255,.86) 48%,rgba(255,255,255,.94)) !important; box-shadow:0 28px 74px rgba(57,105,174,.18),0 0 0 7px rgba(255,255,255,.34),inset 0 1px 0 #FFFFFF,inset 0 -1px 0 rgba(84,146,222,.2) !important; filter:saturate(1.08); }
body:has(.chat-landing-welcome) [data-testid="stChatInput"]:focus-within { transform:translate(-50%,-50%) scale(1.012) !important; border-color:rgba(98,158,235,.78) !important; outline:0 !important; background:rgba(255,255,255,.95) !important; box-shadow:0 28px 74px rgba(57,105,174,.19),0 0 0 7px rgba(111,171,244,.1),inset 0 1px 0 #FFFFFF !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"] [data-baseweb="textarea"] { border:0 !important; outline:0 !important; background:transparent !important; box-shadow:none !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"] textarea { height:54px !important; min-height:54px !important; max-height:54px !important; overflow-x:auto !important; overflow-y:hidden !important; resize:none !important; white-space:nowrap !important; padding-top:18px !important; padding-left:164px !important; font-size:16px !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"] button { border-radius:50% !important; background:rgba(238,245,255,.72) !important; transition:transform .24s ease,background .24s ease,color .24s ease,box-shadow .24s ease !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"] button:hover { transform:scale(1.08) !important; background:#E6F0FF !important; box-shadow:0 4px 14px rgba(59,115,191,.14) !important; }
body:has(.chat-landing-welcome) .st-key-daily_briefing_upload { position:fixed !important; top:50% !important; left:max(20px,calc(50% - 366px)) !important; z-index:31 !important; margin:0 !important; transform:translateY(-50%) !important; }
body:has(.chat-landing-welcome) .st-key-daily_briefing_upload [data-testid="stPopoverButton"] { width:max-content !important; height:40px !important; min-height:40px !important; padding:0 12px !important; justify-content:center !important; white-space:nowrap !important; border-color:rgba(169,197,232,.42) !important; border-radius:999px !important; background:rgba(239,246,255,.78) !important; color:#5B7FAE !important; box-shadow:0 2px 8px rgba(76,112,162,.06) !important; backdrop-filter:blur(10px); font-size:12px !important; }
body:has(.chat-landing-welcome) .st-key-daily_briefing_upload [data-testid="stPopoverButton"] > div { flex-wrap:nowrap !important; white-space:nowrap !important; }
body:has(.chat-landing-welcome) .st-key-daily_briefing_upload [data-testid="stPopoverButton"] span { white-space:nowrap !important; }
body:has(.chat-landing-welcome) .st-key-daily_briefing_upload [data-testid="stPopoverButton"]:hover { transform:scale(1.06); border-color:rgba(88,150,227,.6) !important; background:rgba(255,255,255,.94) !important; color:#3478D3 !important; box-shadow:0 6px 18px rgba(47,107,255,.13) !important; }
@media(max-width:560px) {
  body:has(.chat-landing-welcome) [data-testid="stChatInput"] textarea { padding-left:142px !important; font-size:14px !important; }
  body:has(.chat-landing-welcome) .st-key-daily_briefing_upload { left:max(26px,calc(50% - 178px)) !important; }
  body:has(.chat-landing-welcome) .st-key-daily_briefing_upload [data-testid="stPopoverButton"] { padding:0 8px !important; font-size:11px !important; }
}
.chat-answer-enter { animation:briefing-arrive .78s cubic-bezier(.16,.82,.24,1) both; }
body:not(:has(.chat-landing-welcome)) [data-testid="stChatMessage"]:has(.safety-report) { animation:briefing-arrive .78s cubic-bezier(.16,.82,.24,1) .06s both; transform-origin:center top; }
@keyframes welcome-haze { 0%,100% { opacity:.66; transform:translateX(-50%) scale(.96); } 50% { opacity:1; transform:translateX(-50%) scale(1.04); } }
@keyframes welcome-edge-breathe { 0%,100% { opacity:.42; filter:blur(.2px); } 50% { opacity:.82; filter:blur(.7px); } }
@keyframes prompt-arrive { from { opacity:0; transform:translate(-50%,calc(-50% + 18px)) scale(.975); filter:blur(10px); } to { opacity:1; transform:translate(-50%,-50%) scale(1); filter:blur(0); } }
@keyframes briefing-arrive { from { opacity:0; transform:translateY(22px) scale(.985); filter:blur(12px); } to { opacity:1; transform:translateY(0) scale(1); filter:blur(0); } }
.safety-preview-card { border-color:rgba(255,255,255,.94); background:rgba(255,255,255,.76); box-shadow:0 24px 64px rgba(44,71,111,.13),0 4px 14px rgba(44,71,111,.045),inset 0 1px 0 rgba(255,255,255,.95); backdrop-filter:blur(22px) saturate(1.16); transition:background .2s ease,border-color .2s ease,box-shadow .2s ease,filter .2s ease; }
.safety-preview-card:hover { border-color:rgba(133,177,235,.72); background:rgba(255,255,255,.88); box-shadow:0 30px 72px rgba(44,79,133,.17),0 0 0 5px rgba(255,255,255,.28),inset 0 1px 0 #FFFFFF; filter:saturate(1.04); animation-play-state:paused; }
.motion-task-row { padding:0 7px; border-radius:8px; transition:background .16s ease,transform .16s ease,box-shadow .16s ease; }
.motion-task-row:hover { position:relative; z-index:1; transform:scale(1.018); background:rgba(238,246,255,.82); box-shadow:0 3px 10px rgba(48,93,151,.08); }
.motion-float { border-color:rgba(255,255,255,.82); background:rgba(255,255,255,.66); box-shadow:0 14px 32px rgba(44,71,111,.1),inset 0 1px 0 rgba(255,255,255,.85); backdrop-filter:blur(16px) saturate(1.12); transition:background .18s ease,border-color .18s ease,box-shadow .18s ease; }
.motion-float:hover { border-color:rgba(130,174,232,.7); background:rgba(255,255,255,.84); box-shadow:0 18px 36px rgba(44,71,111,.14),inset 0 1px 0 #FFFFFF; }
.st-key-daily_briefing_upload { display:flex !important; width:max-content !important; min-height:0 !important; margin:0 0 7px !important; padding:0 !important; border:0 !important; border-radius:999px !important; background:transparent !important; box-shadow:none !important; }
.st-key-daily_briefing_upload > div,
.st-key-daily_briefing_upload [data-testid="stVerticalBlockBorderWrapper"] { width:max-content !important; min-height:0 !important; margin:0 !important; padding:0 !important; border:0 !important; border-radius:0 !important; background:transparent !important; box-shadow:none !important; }
.st-key-daily_briefing_upload [data-testid="stPopoverButton"] { min-height:38px !important; padding:0 14px !important; border:1px solid #DEE7F1 !important; border-radius:999px !important; background:rgba(255,255,255,.78) !important; color:#53657D !important; font-size:12px !important; font-weight:560 !important; box-shadow:none !important; }
.st-key-daily_briefing_upload [data-testid="stPopoverButton"]:hover { border-color:#BFD3EE !important; background:#FFFFFF !important; color:#3478D3 !important; }
.safety-preview-head i { background:#4388F5; box-shadow:0 0 0 4px #EAF2FF; }
.preview-check { width:7px; height:7px; border-radius:50%; background:#4388F5; box-shadow:0 0 0 3px #E3EEFC; }
.st-key-chat_options,.st-key-chat_reference { border:1px solid #E6EBF2 !important; border-radius:13px !important; background:rgba(255,255,255,.75) !important; box-shadow:none !important; }
@media(max-width:560px) {
  body:has(.chat-landing) .block-container { max-width:none !important; padding:30px 18px 48px !important; }
  body:has(.chat-landing) .workspace-bar { margin-bottom:16px; }
  .chat-landing { grid-template-columns:minmax(0,1fr); gap:0; min-height:0; margin-bottom:18px; }
  .safety-motion-stage { grid-row:1; min-height:252px; margin:0 0 4px; }
  .chat-hero-copy { grid-row:2; }
  .chat-hero-copy h1 { max-width:360px; font-size:37px !important; }
  .chat-hero-copy p { max-width:360px; font-size:14px; }
  .chat-kicker { margin-bottom:12px; }
  .chat-site-chip { margin-top:16px; }
  .motion-orbit-one { width:238px; height:238px; }
  .motion-orbit-two { width:190px; height:190px; }
  .safety-preview-card { width:min(82%,320px); padding:17px 18px 14px; }
  .safety-preview-count strong { font-size:36px; }
  .motion-float-top { top:12px; right:0; }
  .motion-float-bottom { bottom:14px; left:0; }
  .st-key-daily_briefing_upload { margin:4px 0 12px; }
  .st-key-chat_current_plan { padding:20px 18px !important; border-radius:18px !important; }
  .chat-work-row { grid-template-columns:88px minmax(0,1fr) auto; gap:9px; }
  .chat-work-row strong { font-size:13px; }
  .st-key-chat_current_top [data-testid="stHorizontalBlock"] { flex-direction:column; gap:10px !important; }
  .st-key-chat_current_top [data-testid="column"] { width:100% !important; flex:1 1 100% !important; }
  .st-key-chat_current_actions [data-testid="stHorizontalBlock"] { flex-direction:column; gap:8px !important; }
  .st-key-chat_current_actions [data-testid="column"] { width:100% !important; flex:1 1 100% !important; }
}
@media (prefers-reduced-motion:reduce) { .safety-preview-card,.motion-float,.motion-orbit-one,.motion-orbit-two,.motion-glow { animation:none !important; transition:none !important; } }
@media (prefers-reduced-motion:reduce) { *,*::before,*::after { animation-duration:.01ms !important; animation-iteration-count:1 !important; scroll-behavior:auto !important; } .feature-card:hover,.distribution-card:hover,.distribution-bar:hover,.rank-row:hover,.rank-row:focus,.rank-row:focus-visible,.rank-row:hover .rank-track span,.rank-row:focus .rank-track span,.rank-row:focus-visible .rank-track span { transform:none !important; } .feature-card,.distribution-card,.distribution-bar,.distribution-bar::after,.sparkline polyline,.spark-guide,.spark-bar,.spark-popover,.period-focus,.period-column,.period-axis,.month-popover,.donut-segment,.donut-default,.donut-hover-value,.severity-legend-row,.rank-row,.rank-track span { transition:none !important; } }
/* Cinematic briefing stage: atmospheric green-blue light outside, compact glass UI inside. */
body:has(.chat-landing-welcome),body:has(.chat-conversation-active) { overflow:hidden !important; background:#020706 !important; }
body:has(.chat-landing-welcome) [data-testid="stApp"],body:has(.chat-conversation-active) [data-testid="stApp"] { position:fixed !important; inset:0 !important; width:100vw !important; height:100vh !important; min-height:100vh !important; overflow:hidden !important; background:radial-gradient(ellipse at 12% 8%,rgba(10,137,91,.72) 0,rgba(10,101,78,.34) 19%,transparent 46%),radial-gradient(ellipse at 91% 18%,rgba(34,103,155,.36) 0,transparent 36%),radial-gradient(ellipse at 50% 100%,#010303 0,rgba(2,13,11,.92) 42%,rgba(3,28,21,.76) 100%) !important; }
body:has(.chat-landing-welcome) [data-testid="stAppViewContainer"],body:has(.chat-conversation-active) [data-testid="stAppViewContainer"],body:has(.chat-landing-welcome) [data-testid="stHeader"],body:has(.chat-conversation-active) [data-testid="stHeader"] { background:transparent !important; }
body:has(.chat-landing-welcome) .block-container,body:has(.chat-conversation-active) .block-container { position:relative !important; display:block !important; box-sizing:border-box !important; width:min(80vw,1440px) !important; height:min(75vh,900px) !important; min-height:500px !important; max-height:calc(100vh - 64px) !important; margin:13vh auto 0 !important; padding:32px 42px 126px !important; overflow-x:hidden !important; overflow-y:auto !important; transform:none !important; border:1px solid rgba(197,222,247,.13) !important; border-radius:30px !important; background:radial-gradient(ellipse at 50% -8%,rgba(19,43,54,.48),transparent 42%),linear-gradient(155deg,#0C1114 0%,#080C0E 54%,#090F11 100%) !important; box-shadow:0 50px 140px rgba(0,0,0,.52),0 0 0 1px rgba(255,255,255,.025),inset 0 1px 0 rgba(255,255,255,.065),inset 0 -28px 90px rgba(17,82,66,.06) !important; scrollbar-width:thin; scrollbar-color:rgba(145,180,200,.22) transparent; }
body:has(.chat-landing-welcome) .block-container::-webkit-scrollbar,body:has(.chat-conversation-active) .block-container::-webkit-scrollbar { width:8px; }
body:has(.chat-landing-welcome) .block-container::-webkit-scrollbar-thumb,body:has(.chat-conversation-active) .block-container::-webkit-scrollbar-thumb { border:2px solid transparent; border-radius:9px; background:rgba(152,187,203,.22); background-clip:padding-box; }
.chat-landing-welcome { position:relative !important; inset:auto !important; display:flex !important; align-items:center !important; justify-content:center !important; width:100% !important; height:100% !important; min-height:360px !important; overflow:hidden !important; pointer-events:none !important; }
.welcome-blue-haze { top:37% !important; width:min(900px,90%) !important; height:380px !important; background:radial-gradient(ellipse,rgba(37,128,170,.16) 0,rgba(15,95,94,.09) 42%,transparent 73%) !important; filter:blur(36px) !important; }
.welcome-window-edges { inset:16px !important; border-radius:26px !important; opacity:.72 !important; background:linear-gradient(135deg,rgba(129,209,197,.42),rgba(66,133,160,.08) 72%,transparent) top left/240px 1px no-repeat,linear-gradient(135deg,rgba(129,209,197,.34),rgba(66,133,160,.05) 72%,transparent) top left/1px 190px no-repeat,linear-gradient(225deg,rgba(139,205,225,.3),rgba(66,133,160,.05) 72%,transparent) top right/210px 1px no-repeat,linear-gradient(225deg,rgba(139,205,225,.24),transparent 72%) top right/1px 176px no-repeat,linear-gradient(315deg,rgba(59,189,145,.22),rgba(66,133,160,.04) 72%,transparent) bottom right/230px 1px no-repeat,linear-gradient(315deg,rgba(59,189,145,.17),transparent 72%) bottom right/1px 170px no-repeat,linear-gradient(45deg,rgba(63,165,153,.2),rgba(66,133,160,.04) 72%,transparent) bottom left/210px 1px no-repeat,linear-gradient(45deg,rgba(63,165,153,.16),transparent 72%) bottom left/1px 160px no-repeat !important; }
.chat-stage-intro { position:relative !important; z-index:24 !important; top:auto !important; left:auto !important; display:block !important; visibility:visible !important; width:min(600px,calc(100% - 36px)); margin-top:-38px; transform:none; text-align:center; color:#F0F5F5 !important; animation:stage-copy-enter .95s cubic-bezier(.18,.78,.22,1) both; }
.chat-stage-kicker { display:inline-flex; align-items:center; gap:8px; color:#8FABA9; font:600 10px/1.5 var(--font-mono,monospace); letter-spacing:.17em; }
.chat-stage-kicker i { width:6px; height:6px; border-radius:50%; background:#54D6AA; box-shadow:0 0 12px rgba(84,214,170,.48); }
.chat-stage-intro h1 { margin:18px 0 10px !important; color:#F4F7F6 !important; font:500 clamp(27px,3.1vw,40px)/1.27 var(--font-ui,"Pretendard",sans-serif) !important; letter-spacing:-.055em !important; }
body:has(.chat-landing-welcome) .chat-stage-intro h1 { color:#F4F7F6 !important; }
.chat-stage-intro h1 em { color:#74D9BD; font-style:normal; font-weight:550; }
.chat-stage-intro p { margin:0 auto !important; max-width:450px; color:#81908F; font:400 13px/1.75 var(--font-ui,"Pretendard",sans-serif); letter-spacing:-.01em; }
body:has(.chat-landing-welcome) [data-testid="stBottomBlockContainer"],body:has(.chat-conversation-active) [data-testid="stBottomBlockContainer"] { position:fixed !important; top:calc(50% + min(37.5vh, 450px) - 47px) !important; bottom:auto !important; left:0 !important; z-index:40 !important; width:100% !important; padding:0 !important; transform:translateY(-50%) !important; background:transparent !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"],body:has(.chat-conversation-active) [data-testid="stChatInput"] { position:fixed !important; top:calc(13vh + min(75vh, 900px) - 47px) !important; left:50% !important; bottom:auto !important; width:min(70vw,1000px) !important; margin:0 !important; padding:0 12px !important; transform:translate(-50%,-50%) !important; border:1px solid rgba(195,222,235,.14) !important; border-radius:999px !important; background:linear-gradient(120deg,rgba(235,250,249,.085),rgba(226,242,255,.055) 48%,rgba(234,249,245,.085)) !important; box-shadow:0 18px 46px rgba(0,0,0,.24),inset 0 1px 0 rgba(255,255,255,.1),inset 0 -1px 0 rgba(83,178,153,.06) !important; backdrop-filter:blur(24px) saturate(1.2) !important; transition:border-color .32s ease,background .32s ease,box-shadow .32s ease,transform .32s cubic-bezier(.18,.78,.2,1) !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"],body:has(.chat-conversation-active) [data-testid="stChatInput"],body:has(.chat-landing-welcome) [data-testid="stChatInput"] > div,body:has(.chat-conversation-active) [data-testid="stChatInput"] > div,body:has(.chat-landing-welcome) [data-testid="stChatInput"] [data-baseweb="textarea"],body:has(.chat-conversation-active) [data-testid="stChatInput"] [data-baseweb="textarea"] { border-radius:999px !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"]:hover,body:has(.chat-conversation-active) [data-testid="stChatInput"]:hover,body:has(.chat-landing-welcome) [data-testid="stChatInput"]:focus-within,body:has(.chat-conversation-active) [data-testid="stChatInput"]:focus-within { transform:translate(-50%,calc(-50% - 2px)) !important; border-color:rgba(104,206,180,.52) !important; background:linear-gradient(120deg,rgba(225,250,245,.13),rgba(216,239,255,.09) 48%,rgba(225,250,245,.12)) !important; box-shadow:0 24px 58px rgba(0,0,0,.28),0 0 0 5px rgba(73,177,150,.055),inset 0 1px 0 rgba(255,255,255,.16),0 0 30px rgba(44,171,135,.08) !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"]::before,body:has(.chat-conversation-active) [data-testid="stChatInput"]::before { content:""; position:absolute; top:1px; left:7%; right:7%; height:1px; border-radius:999px; pointer-events:none; background:linear-gradient(90deg,transparent,rgba(206,243,236,.35) 25%,rgba(221,245,255,.48) 54%,rgba(206,243,236,.26) 76%,transparent); }
body:has(.chat-landing-welcome) [data-testid="stChatInput"] textarea,body:has(.chat-conversation-active) [data-testid="stChatInput"] textarea { height:54px !important; min-height:54px !important; max-height:54px !important; padding-top:18px !important; padding-left:164px !important; color:#E7F0EF !important; font-size:15px !important; line-height:1.3 !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"] textarea,body:has(.chat-conversation-active) [data-testid="stChatInput"] textarea,body:has(.chat-landing-welcome) [data-testid="stChatInput"] textarea:focus,body:has(.chat-conversation-active) [data-testid="stChatInput"] textarea:focus,body:has(.chat-landing-welcome) [data-testid="stChatInput"] [data-baseweb="textarea"],body:has(.chat-conversation-active) [data-testid="stChatInput"] [data-baseweb="textarea"] { border:0 !important; outline:0 !important; box-shadow:none !important; background:transparent !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"] textarea::placeholder,body:has(.chat-conversation-active) [data-testid="stChatInput"] textarea::placeholder { color:#718382 !important; opacity:1 !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"] *,body:has(.chat-conversation-active) [data-testid="stChatInput"] * { background-color:transparent !important; box-shadow:none !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"] [data-baseweb="textarea"],body:has(.chat-conversation-active) [data-testid="stChatInput"] [data-baseweb="textarea"],body:has(.chat-landing-welcome) [data-testid="stChatInput"] [data-baseweb="textarea"] > div,body:has(.chat-conversation-active) [data-testid="stChatInput"] [data-baseweb="textarea"] > div { border:0 !important; background:transparent !important; box-shadow:none !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"] button,body:has(.chat-conversation-active) [data-testid="stChatInput"] button { border-radius:50% !important; background:rgba(96,207,173,.12) !important; color:#87E2C2 !important; transition:transform .22s ease,background .22s ease,box-shadow .22s ease !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"] button:hover,body:has(.chat-conversation-active) [data-testid="stChatInput"] button:hover { transform:scale(1.08) !important; background:rgba(96,207,173,.24) !important; box-shadow:0 0 18px rgba(67,214,165,.16) !important; }
body:has(.chat-landing-welcome) .st-key-daily_briefing_upload,body:has(.chat-conversation-active) .st-key-daily_briefing_upload { position:fixed !important; top:calc(13vh + min(75vh, 900px) - 47px) !important; left:max(20px,calc(50% - min(35vw, 500px) + 14px)) !important; z-index:42 !important; margin:0 !important; transform:translateY(-50%) !important; }
body:has(.chat-landing-welcome) .st-key-daily_briefing_upload [data-testid="stPopoverButton"],body:has(.chat-conversation-active) .st-key-daily_briefing_upload [data-testid="stPopoverButton"] { height:38px !important; min-height:38px !important; padding:0 11px !important; border:1px solid rgba(199,225,229,.12) !important; border-radius:999px !important; background:rgba(229,244,246,.06) !important; color:#91A9A8 !important; font-size:11px !important; }
body:has(.chat-landing-welcome) .st-key-daily_briefing_upload [data-testid="stPopoverButton"]:hover,body:has(.chat-conversation-active) .st-key-daily_briefing_upload [data-testid="stPopoverButton"]:hover { border-color:rgba(99,207,176,.42) !important; background:rgba(90,191,165,.12) !important; color:#C4F1E2 !important; }
body:has(.chat-conversation-active) [data-testid="stChatMessage"] { color:#DEE8E7 !important; }
body:has(.chat-conversation-active) [data-testid="stChatMessage"]:has(.safety-report) { border:0 !important; background:transparent !important; box-shadow:none !important; backdrop-filter:none !important; animation:stage-answer-enter .76s cubic-bezier(.18,.78,.2,1) .06s both !important; }
body:has(.chat-conversation-active) [data-testid="stChatMessage"]:not(:has(.safety-report)) { width:fit-content !important; max-width:72% !important; margin:0 0 12px auto !important; padding:10px 15px !important; border:1px solid rgba(194,220,227,.1) !important; border-radius:17px 17px 5px 17px !important; background:rgba(226,242,242,.055) !important; box-shadow:inset 0 1px 0 rgba(255,255,255,.04) !important; color:#C6D2D0 !important; }
body:has(.chat-conversation-active) [data-testid="stChatMessage"]:not(:has(.safety-report)) > div:first-child { display:none !important; }
body:has(.chat-conversation-active) [data-testid="stChatMessage"]:not(:has(.safety-report)) * { color:#C6D2D0 !important; }
body:has(.chat-conversation-active) .st-key-chat_clear_messages [data-testid="stButton"] button { min-height:34px !important; padding:0 13px !important; border:1px solid rgba(194,220,227,.1) !important; border-radius:999px !important; background:rgba(226,242,242,.05) !important; color:#9FB3B1 !important; box-shadow:none !important; font-size:11px !important; }
body:has(.chat-conversation-active) .st-key-chat_clear_messages [data-testid="stButton"] button:hover { border-color:rgba(104,206,180,.32) !important; background:rgba(96,207,173,.08) !important; color:#D5E6E2 !important; }
body:has(.chat-conversation-active) .workspace-bar,body:has(.chat-conversation-active) [data-testid="stExpander"] { border-color:rgba(194,220,227,.1) !important; background:rgba(226,242,242,.035) !important; color:#9BB0AE !important; }
body:has(.chat-conversation-active) [data-testid="stExpander"],body:has(.chat-conversation-active) [data-testid="stExpander"] details { border:1px solid rgba(194,220,227,.09) !important; border-radius:12px !important; background:rgba(226,242,242,.035) !important; }
body:has(.chat-conversation-active) [data-testid="stExpander"] summary,body:has(.chat-conversation-active) [data-testid="stExpander"] button { border-radius:10px !important; background:transparent !important; color:#AFC0BE !important; }
body:has(.chat-conversation-active) [data-testid="stExpander"] summary:hover { background:rgba(226,242,242,.045) !important; color:#E3ECEA !important; }
body:has(.chat-landing-welcome) a[aria-label*="페이지 맨 위"],body:has(.chat-conversation-active) a[aria-label*="페이지 맨 위"] { position:fixed !important; top:calc(12.5vh + 16px) !important; right:max(10vw,calc((100vw - 1440px)/2 + 20px)) !important; bottom:auto !important; z-index:50 !important; border:1px solid rgba(194,220,227,.1) !important; border-radius:999px !important; background:rgba(225,242,242,.05) !important; color:#9EB5B2 !important; box-shadow:0 6px 22px rgba(0,0,0,.2),inset 0 1px 0 rgba(255,255,255,.05) !important; backdrop-filter:blur(14px); font-size:11px !important; }
@keyframes stage-copy-enter { from { opacity:0; transform:translateY(16px); filter:blur(8px); } to { opacity:1; transform:translateY(0); filter:blur(0); } }
@keyframes stage-answer-enter { from { opacity:0; transform:translateY(20px) scale(.985); } to { opacity:1; transform:translateY(0) scale(1); } }
@media(max-width:760px) {
  body:has(.chat-landing-welcome) .block-container,body:has(.chat-conversation-active) .block-container { width:94vw !important; height:84vh !important; min-height:500px !important; margin:8vh auto 0 !important; padding:24px 20px 116px !important; border-radius:24px !important; }
  body:has(.chat-landing-welcome) [data-testid="stBottomBlockContainer"],body:has(.chat-conversation-active) [data-testid="stBottomBlockContainer"] { top:calc(8vh + 84vh - 45px) !important; }
  body:has(.chat-landing-welcome) [data-testid="stChatInput"],body:has(.chat-conversation-active) [data-testid="stChatInput"] { top:calc(8vh + 84vh - 45px) !important; }
  body:has(.chat-landing-welcome) [data-testid="stChatInput"],body:has(.chat-conversation-active) [data-testid="stChatInput"] { width:88vw !important; }
  body:has(.chat-landing-welcome) [data-testid="stChatInput"] textarea,body:has(.chat-conversation-active) [data-testid="stChatInput"] textarea { padding-left:140px !important; font-size:13px !important; }
  body:has(.chat-landing-welcome) .st-key-daily_briefing_upload,body:has(.chat-conversation-active) .st-key-daily_briefing_upload { top:calc(8vh + 84vh - 45px) !important; left:calc(6vw + 12px) !important; }
  .chat-stage-intro { top:auto; width:calc(100% - 28px); }
  .chat-stage-intro h1 { font-size:29px !important; }
  .chat-stage-intro p { font-size:12px; }
}
/* Blue glass finish: pointer hover catches the stage rim and corner highlights. */
body:has(.chat-landing-welcome),body:has(.chat-conversation-active) { background:#020611 !important; }
body:has(.chat-landing-welcome) [data-testid="stApp"],body:has(.chat-conversation-active) [data-testid="stApp"] { background:radial-gradient(ellipse at 9% 8%,rgba(38,112,255,.58) 0,rgba(24,89,207,.27) 20%,transparent 48%),radial-gradient(ellipse at 92% 15%,rgba(47,177,255,.34) 0,transparent 37%),radial-gradient(ellipse at 50% 100%,#02040A 0,rgba(5,12,27,.96) 46%,rgba(8,27,59,.68) 100%) !important; }
body:has(.chat-landing-welcome) .block-container,body:has(.chat-conversation-active) .block-container { padding-bottom:176px !important; border-color:rgba(151,195,255,.16) !important; background:radial-gradient(ellipse at 50% -8%,rgba(30,68,125,.26),transparent 44%),linear-gradient(155deg,#0C111B 0%,#080C14 54%,#090E18 100%) !important; box-shadow:0 50px 140px rgba(0,0,0,.56),0 0 0 1px rgba(255,255,255,.025),inset 0 1px 0 rgba(225,240,255,.075),inset 0 -28px 90px rgba(38,104,209,.07) !important; scroll-padding-bottom:180px; }
body:has(.chat-landing-welcome) .block-container::before,body:has(.chat-conversation-active) .block-container::before { content:""; position:absolute; z-index:24; pointer-events:none; left:0; right:0; bottom:0; height:126px; border-radius:0 0 29px 29px; background:linear-gradient(180deg,transparent 0%,rgba(8,12,20,.56) 62%,#080C14 100%); }
body:has(.chat-landing-welcome) .block-container::after,body:has(.chat-conversation-active) .block-container::after { content:""; position:absolute; inset:0; z-index:8; pointer-events:none; border:1px solid transparent; border-radius:inherit; background:linear-gradient(135deg,rgba(197,226,255,.84),rgba(96,160,255,.13) 28%,transparent 49%,rgba(72,177,255,.16) 72%,rgba(172,213,255,.65)) border-box; background-size:220% 220%; -webkit-mask:linear-gradient(#fff 0 0) padding-box,linear-gradient(#fff 0 0); -webkit-mask-composite:xor; mask-composite:exclude; opacity:0; transition:opacity .42s ease,filter .42s ease; filter:drop-shadow(0 0 0 rgba(90,169,255,0)); }
body:has(.chat-landing-welcome) .block-container:hover::after,body:has(.chat-conversation-active) .block-container:hover::after { opacity:.9; filter:drop-shadow(0 0 11px rgba(83,158,255,.38)); animation:stage-rim-sheen 1.8s ease-in-out infinite alternate; }
body:has(.chat-landing-welcome) .block-container:hover,body:has(.chat-conversation-active) .block-container:hover { border-color:rgba(151,199,255,.4) !important; box-shadow:0 50px 140px rgba(0,0,0,.56),0 0 0 1px rgba(113,174,255,.14),0 0 30px rgba(65,139,255,.14),inset 0 1px 0 rgba(225,240,255,.11),inset 0 -28px 90px rgba(38,104,209,.1) !important; }
.welcome-blue-haze { background:radial-gradient(ellipse,rgba(54,139,255,.21) 0,rgba(20,93,187,.11) 43%,transparent 74%) !important; }
.welcome-window-edges { background:linear-gradient(135deg,rgba(151,203,255,.50),rgba(66,133,220,.08) 72%,transparent) top left/240px 1px no-repeat,linear-gradient(135deg,rgba(151,203,255,.36),rgba(66,133,220,.05) 72%,transparent) top left/1px 190px no-repeat,linear-gradient(225deg,rgba(139,205,255,.42),rgba(66,133,220,.05) 72%,transparent) top right/210px 1px no-repeat,linear-gradient(225deg,rgba(139,205,255,.30),transparent 72%) top right/1px 176px no-repeat,linear-gradient(315deg,rgba(91,161,255,.34),rgba(66,133,220,.04) 72%,transparent) bottom right/230px 1px no-repeat,linear-gradient(315deg,rgba(91,161,255,.23),transparent 72%) bottom right/1px 170px no-repeat,linear-gradient(45deg,rgba(63,139,255,.31),rgba(66,133,220,.04) 72%,transparent) bottom left/210px 1px no-repeat,linear-gradient(45deg,rgba(63,139,255,.22),transparent 72%) bottom left/1px 160px no-repeat !important; }
.chat-stage-kicker { color:#93A9CB !important; }
.chat-stage-kicker i { background:#77B7FF !important; box-shadow:0 0 13px rgba(102,174,255,.58) !important; }
.chat-stage-intro h1 em { color:#91C5FF !important; }
.chat-stage-intro p { color:#8A96AA !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"],body:has(.chat-conversation-active) [data-testid="stChatInput"] { border-color:rgba(158,195,244,.18) !important; background:linear-gradient(120deg,rgba(231,242,255,.09),rgba(205,224,255,.06) 48%,rgba(208,238,255,.09)) !important; box-shadow:0 18px 46px rgba(0,0,0,.28),inset 0 1px 0 rgba(230,241,255,.12),inset 0 -1px 0 rgba(83,145,218,.08) !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"]:hover,body:has(.chat-conversation-active) [data-testid="stChatInput"]:hover,body:has(.chat-landing-welcome) [data-testid="stChatInput"]:focus-within,body:has(.chat-conversation-active) [data-testid="stChatInput"]:focus-within { border-color:rgba(116,180,255,.6) !important; background:linear-gradient(120deg,rgba(224,239,255,.16),rgba(194,219,255,.10) 48%,rgba(205,237,255,.15)) !important; box-shadow:0 24px 58px rgba(0,0,0,.32),0 0 0 5px rgba(76,142,236,.08),inset 0 1px 0 rgba(255,255,255,.2),0 0 32px rgba(50,128,255,.13) !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"]::before,body:has(.chat-conversation-active) [data-testid="stChatInput"]::before { background:linear-gradient(90deg,transparent,rgba(206,229,255,.38) 25%,rgba(224,240,255,.58) 54%,rgba(206,229,255,.3) 76%,transparent) !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"] textarea,body:has(.chat-conversation-active) [data-testid="stChatInput"] textarea { color:#E8F1FF !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"] textarea::placeholder,body:has(.chat-conversation-active) [data-testid="stChatInput"] textarea::placeholder { color:#8291AA !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"] button,body:has(.chat-conversation-active) [data-testid="stChatInput"] button { background:rgba(99,165,255,.17) !important; color:#A9D0FF !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"] button:hover,body:has(.chat-conversation-active) [data-testid="stChatInput"] button:hover { background:rgba(99,165,255,.30) !important; box-shadow:0 0 18px rgba(67,139,255,.24) !important; }
body:has(.chat-landing-welcome) .st-key-daily_briefing_upload [data-testid="stPopoverButton"],body:has(.chat-conversation-active) .st-key-daily_briefing_upload [data-testid="stPopoverButton"] { border-color:rgba(158,195,244,.15) !important; background:rgba(213,230,255,.065) !important; color:#A0B5D4 !important; }
body:has(.chat-landing-welcome) .st-key-daily_briefing_upload [data-testid="stPopoverButton"]:hover,body:has(.chat-conversation-active) .st-key-daily_briefing_upload [data-testid="stPopoverButton"]:hover { border-color:rgba(116,180,255,.42) !important; background:rgba(90,150,235,.15) !important; color:#D2E5FF !important; }
body:has(.chat-conversation-active) [data-testid="stChatMessage"] { color:#DEE8F5 !important; }
body:has(.chat-conversation-active) [data-testid="stChatMessage"]:not(:has(.safety-report)) { border-color:rgba(175,204,244,.13) !important; background:rgba(221,234,255,.065) !important; color:#D0DDEE !important; }
body:has(.chat-conversation-active) [data-testid="stChatMessage"]:not(:has(.safety-report)) * { color:#D0DDEE !important; }
body:has(.chat-conversation-active) .st-key-chat_clear_messages [data-testid="stButton"] button:hover { border-color:rgba(116,180,255,.34) !important; background:rgba(96,148,220,.12) !important; color:#E0ECFC !important; }
body:has(.chat-conversation-active) .workspace-bar,body:has(.chat-conversation-active) [data-testid="stExpander"],body:has(.chat-conversation-active) [data-testid="stExpander"] details { border-color:rgba(175,204,244,.12) !important; background:rgba(221,234,255,.045) !important; color:#AFC0D5 !important; }
body:has(.chat-conversation-active) [data-testid="stExpander"] summary,body:has(.chat-conversation-active) [data-testid="stExpander"] button { color:#B9CBE3 !important; }
body:has(.chat-conversation-active) [data-testid="stExpander"] summary:hover { background:rgba(140,184,244,.07) !important; color:#E3EDFA !important; }
body:has(.chat-landing-welcome) a[aria-label*="페이지 맨 위"],body:has(.chat-conversation-active) a[aria-label*="페이지 맨 위"] { border-color:rgba(175,204,244,.13) !important; background:rgba(221,234,255,.06) !important; color:#A8C0E1 !important; }
@keyframes stage-rim-sheen { 0% { background-position:100% 0; } 100% { background-position:0 100%; } }
@media(prefers-reduced-motion:reduce) { body:has(.chat-landing-welcome) .block-container::after,body:has(.chat-conversation-active) .block-container::after { transition:none !important; animation:none !important; } }
/* Light blue glass stage with a cursor-reactive background. */
body:has(.chat-landing-welcome),body:has(.chat-conversation-active) { background:#EAF1F8 !important; }
body:has(.chat-landing-welcome) [data-testid="stApp"],body:has(.chat-conversation-active) [data-testid="stApp"] { background:radial-gradient(ellipse at 7% 8%,rgba(107,169,255,.48) 0,rgba(157,198,248,.25) 24%,transparent 53%),radial-gradient(ellipse at 94% 15%,rgba(136,211,255,.35) 0,transparent 38%),linear-gradient(180deg,#EFF5FC 0%,#E8EEF5 56%,#DEE6EF 100%) !important; }
body:has(.chat-landing-welcome) [data-testid="stAppViewContainer"],body:has(.chat-conversation-active) [data-testid="stAppViewContainer"],body:has(.chat-landing-welcome) [data-testid="stHeader"],body:has(.chat-conversation-active) [data-testid="stHeader"] { background:transparent !important; }
body:has(.chat-landing-welcome) .block-container,body:has(.chat-conversation-active) .block-container { border-color:rgba(255,255,255,.92) !important; background:radial-gradient(ellipse at 50% -8%,rgba(224,238,255,.78),transparent 44%),linear-gradient(155deg,#FFFFFF 0%,#FCFDFF 55%,#F7FAFE 100%) !important; box-shadow:0 35px 100px rgba(40,72,116,.15),0 2px 8px rgba(38,66,106,.055),inset 0 1px 0 #FFFFFF,inset 0 -24px 80px rgba(124,172,232,.045) !important; scrollbar-width:none !important; }
body:has(.chat-landing-welcome) .block-container::-webkit-scrollbar,body:has(.chat-conversation-active) .block-container::-webkit-scrollbar { display:none !important; width:0 !important; }
body:has(.chat-landing-welcome) .block-container::before,body:has(.chat-conversation-active) .block-container::before { background:linear-gradient(180deg,transparent 0%,rgba(250,252,255,.78) 62%,#F9FBFE 100%) !important; }
body:has(.chat-landing-welcome) .block-container::after,body:has(.chat-conversation-active) .block-container::after { opacity:0 !important; }
body:has(.chat-landing-welcome) .block-container:hover,body:has(.chat-conversation-active) .block-container:hover { border-color:rgba(255,255,255,.98) !important; box-shadow:0 35px 100px rgba(40,72,116,.15),0 2px 8px rgba(38,66,106,.055),inset 0 1px 0 #FFFFFF,inset 0 -24px 80px rgba(124,172,232,.045) !important; }
.welcome-blue-haze { background:radial-gradient(ellipse,rgba(119,177,255,.21) 0,rgba(159,205,255,.12) 43%,transparent 74%) !important; }
.welcome-window-edges { opacity:.35 !important; background:linear-gradient(135deg,rgba(111,169,245,.5),rgba(66,133,220,.04) 72%,transparent) top left/240px 1px no-repeat,linear-gradient(135deg,rgba(111,169,245,.36),rgba(66,133,220,.03) 72%,transparent) top left/1px 190px no-repeat,linear-gradient(225deg,rgba(139,194,255,.48),rgba(66,133,220,.04) 72%,transparent) top right/210px 1px no-repeat,linear-gradient(225deg,rgba(139,194,255,.32),transparent 72%) top right/1px 176px no-repeat,linear-gradient(315deg,rgba(91,151,235,.4),rgba(66,133,220,.03) 72%,transparent) bottom right/230px 1px no-repeat,linear-gradient(315deg,rgba(91,151,235,.28),transparent 72%) bottom right/1px 170px no-repeat,linear-gradient(45deg,rgba(63,139,255,.34),rgba(66,133,220,.03) 72%,transparent) bottom left/210px 1px no-repeat,linear-gradient(45deg,rgba(63,139,255,.23),transparent 72%) bottom left/1px 160px no-repeat !important; }
.chat-stage-intro h1,body:has(.chat-landing-welcome) .chat-stage-intro h1 { color:#172B49 !important; }
.chat-stage-intro h1 em { color:#397EE8 !important; }
.chat-stage-kicker { color:#6D83A2 !important; }
.chat-stage-kicker i { background:#5794F2 !important; box-shadow:0 0 11px rgba(77,139,239,.35) !important; }
.chat-stage-intro p { color:#6F7F96 !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"],body:has(.chat-conversation-active) [data-testid="stChatInput"] { border-color:rgba(183,202,229,.74) !important; background:linear-gradient(120deg,rgba(255,255,255,.88),rgba(247,250,255,.78) 48%,rgba(255,255,255,.88)) !important; box-shadow:0 17px 44px rgba(48,76,117,.13),inset 0 1px 0 #FFFFFF,inset 0 -1px 0 rgba(100,149,216,.08) !important; backdrop-filter:blur(28px) saturate(1.18) !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"]:hover,body:has(.chat-conversation-active) [data-testid="stChatInput"]:hover,body:has(.chat-landing-welcome) [data-testid="stChatInput"]:focus-within,body:has(.chat-conversation-active) [data-testid="stChatInput"]:focus-within { border-color:rgba(76,139,231,.56) !important; background:rgba(255,255,255,.96) !important; box-shadow:0 22px 54px rgba(50,93,159,.18),0 0 0 5px rgba(81,143,231,.07),inset 0 1px 0 #FFFFFF,0 0 26px rgba(95,157,247,.12) !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"]::before,body:has(.chat-conversation-active) [data-testid="stChatInput"]::before { background:linear-gradient(90deg,transparent,rgba(150,191,247,.32) 25%,rgba(255,255,255,.92) 54%,rgba(150,191,247,.26) 76%,transparent) !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"] textarea,body:has(.chat-conversation-active) [data-testid="stChatInput"] textarea { color:#243956 !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"] textarea::placeholder,body:has(.chat-conversation-active) [data-testid="stChatInput"] textarea::placeholder { color:#8797AE !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"] button,body:has(.chat-conversation-active) [data-testid="stChatInput"] button { background:rgba(77,140,235,.13) !important; color:#3978D1 !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"] button:hover,body:has(.chat-conversation-active) [data-testid="stChatInput"] button:hover { background:rgba(77,140,235,.22) !important; box-shadow:0 0 16px rgba(67,131,230,.16) !important; }
body:has(.chat-landing-welcome) .st-key-daily_briefing_upload [data-testid="stPopoverButton"],body:has(.chat-conversation-active) .st-key-daily_briefing_upload [data-testid="stPopoverButton"] { border-color:rgba(189,205,229,.68) !important; background:rgba(247,250,255,.88) !important; color:#536B8E !important; }
body:has(.chat-landing-welcome) .st-key-daily_briefing_upload [data-testid="stPopoverButton"]:hover,body:has(.chat-conversation-active) .st-key-daily_briefing_upload [data-testid="stPopoverButton"]:hover { border-color:rgba(103,156,235,.54) !important; background:#FFFFFF !important; color:#356FC1 !important; }
body:has(.chat-conversation-active) [data-testid="stChatMessage"] { color:#243752 !important; }
body:has(.chat-conversation-active) [data-testid="stChatMessage"]:not(:has(.safety-report)) { border-color:rgba(160,189,229,.48) !important; background:linear-gradient(135deg,rgba(238,246,255,.94),rgba(229,240,255,.87)) !important; color:#2C4568 !important; box-shadow:0 5px 18px rgba(53,92,145,.06) !important; }
body:has(.chat-conversation-active) [data-testid="stChatMessage"]:not(:has(.safety-report)) * { color:#2C4568 !important; }
body:has(.chat-conversation-active) .st-key-chat_clear_messages [data-testid="stButton"] button { border-color:rgba(177,195,221,.65) !important; background:rgba(255,255,255,.76) !important; color:#60748F !important; }
body:has(.chat-conversation-active) .st-key-chat_clear_messages [data-testid="stButton"] button:hover { border-color:rgba(105,157,231,.55) !important; background:#FFFFFF !important; color:#356FC1 !important; }
body:has(.chat-conversation-active) .workspace-bar,body:has(.chat-conversation-active) [data-testid="stExpander"],body:has(.chat-conversation-active) [data-testid="stExpander"] details { border-color:rgba(187,202,223,.68) !important; background:rgba(255,255,255,.76) !important; color:#536985 !important; }
body:has(.chat-conversation-active) [data-testid="stExpander"] summary,body:has(.chat-conversation-active) [data-testid="stExpander"] button { color:#526B8E !important; }
body:has(.chat-conversation-active) [data-testid="stExpander"] summary:hover { background:rgba(223,237,255,.62) !important; color:#274C7E !important; }
body:has(.chat-landing-welcome) a[aria-label*="페이지 맨 위"],body:has(.chat-conversation-active) a[aria-label*="페이지 맨 위"] { border-color:rgba(186,202,226,.74) !important; background:rgba(255,255,255,.78) !important; color:#60799C !important; box-shadow:0 5px 18px rgba(49,79,124,.09) !important; }
@media(max-width:760px) { body:has(.chat-landing-welcome) .block-container,body:has(.chat-conversation-active) .block-container { padding-bottom:156px !important; } }
@media(prefers-reduced-motion:reduce) { body:has(.chat-landing-welcome) .block-container::after,body:has(.chat-conversation-active) .block-container::after { transition:none !important; animation:none !important; } }
/* Pointer response lives in the stage paint layer, behind every UI element. */
@property --stage-drift-x { syntax:"<length>"; inherits:false; initial-value:0px; }
@property --stage-drift-y { syntax:"<length>"; inherits:false; initial-value:0px; }
body:has(.chat-landing-welcome) [data-testid="stApp"],body:has(.chat-conversation-active) [data-testid="stApp"] { background-image:radial-gradient(ellipse 54% 76% at calc(7% + var(--stage-drift-x,0px)) calc(8% + var(--stage-drift-y,0px)),rgba(107,169,255,.48) 0,rgba(157,198,248,.25) 24%,transparent 53%),radial-gradient(ellipse 48% 66% at calc(94% + var(--stage-drift-x,0px)) calc(15% + var(--stage-drift-y,0px)),rgba(136,211,255,.35) 0,transparent 38%),linear-gradient(180deg,#EFF5FC 0%,#E8EEF5 56%,#DEE6EF 100%) !important; transition:--stage-drift-x .58s cubic-bezier(.2,.8,.2,1),--stage-drift-y .58s cubic-bezier(.2,.8,.2,1) !important; }
body:has(.chat-landing-welcome) .block-container,body:has(.chat-conversation-active) .block-container { position:relative !important; isolation:isolate !important; background-image:linear-gradient(118deg,transparent 28%,rgba(124,174,244,.025) 42%,rgba(255,255,255,.12) 49.5%,rgba(127,179,245,.055) 56%,transparent 72%),radial-gradient(ellipse 82% 58% at calc(50% + var(--stage-drift-x,0px)) calc(-8% + var(--stage-drift-y,0px)),rgba(224,238,255,.74),transparent 44%),radial-gradient(ellipse 68% 52% at calc(89% + var(--stage-drift-x,0px)) calc(24% + var(--stage-drift-y,0px)),rgba(202,225,255,.17),transparent 69%),linear-gradient(155deg,#FFFFFF 0%,#FCFDFF 55%,#F7FAFE 100%) !important; background-size:180% 160%,100% 100%,100% 100%,100% 100% !important; background-position:calc(50% + var(--stage-drift-x,0px)) calc(50% + var(--stage-drift-y,0px)),center,center,center !important; transition:--stage-drift-x .52s cubic-bezier(.2,.8,.2,1),--stage-drift-y .52s cubic-bezier(.2,.8,.2,1),background-position .52s cubic-bezier(.2,.8,.2,1),box-shadow .35s ease !important; }
/* Disable legacy overlays: they washed out report text and sat above content. */
body:has(.chat-landing-welcome) .block-container::after,body:has(.chat-conversation-active) .block-container::after { content:none !important; display:none !important; }
body:has(.chat-landing-welcome) .block-container::before,body:has(.chat-conversation-active) .block-container::before { content:none !important; display:none !important; }
body:has(.chat-landing-welcome) .block-container,body:has(.chat-conversation-active) .block-container { scrollbar-width:none !important; }
body:has(.chat-landing-welcome) .block-container::-webkit-scrollbar,body:has(.chat-conversation-active) .block-container::-webkit-scrollbar { display:none !important; width:0 !important; }
body:has(.chat-landing-welcome) [data-testid="stBottomBlockContainer"] { top:calc(50% + min(37.5vh,450px) - 116px) !important; }
body:has(.chat-conversation-active) [data-testid="stBottomBlockContainer"] { top:calc(50% + min(37.5vh,450px) - 68px) !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"] { top:calc(13vh + min(75vh,900px) - 116px) !important; }
body:has(.chat-conversation-active) [data-testid="stChatInput"] { top:calc(13vh + min(75vh,900px) - 68px) !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"],body:has(.chat-conversation-active) [data-testid="stChatInput"] { box-sizing:border-box !important; height:64px !important; min-height:64px !important; padding:0 11px !important; border:1px solid rgba(183,202,229,.74) !important; outline:0 !important; background:rgba(255,255,255,.97) !important; box-shadow:0 12px 32px rgba(48,76,117,.12),inset 0 1px 0 #FFFFFF !important; backdrop-filter:blur(16px) saturate(1.1) !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"]:focus-within,body:has(.chat-conversation-active) [data-testid="stChatInput"]:focus-within { border-color:#A9C8F3 !important; outline:0 !important; box-shadow:0 12px 32px rgba(48,76,117,.13),0 0 0 3px rgba(83,143,224,.1),inset 0 1px 0 #FFFFFF !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"] textarea,body:has(.chat-conversation-active) [data-testid="stChatInput"] textarea { box-sizing:border-box !important; height:48px !important; min-height:48px !important; max-height:48px !important; padding-top:13px !important; padding-left:164px !important; color:#243956 !important; border:0 !important; outline:0 !important; box-shadow:none !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"] textarea:focus,body:has(.chat-conversation-active) [data-testid="stChatInput"] textarea:focus { border:0 !important; outline:0 !important; box-shadow:none !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"] button,body:has(.chat-conversation-active) [data-testid="stChatInput"] button { display:grid !important; place-items:center !important; box-sizing:border-box !important; width:38px !important; min-width:38px !important; max-width:38px !important; height:38px !important; min-height:38px !important; max-height:38px !important; padding:0 !important; flex:0 0 38px !important; border:0 !important; outline:0 !important; border-radius:50% !important; background:#EAF2FF !important; color:#3978D1 !important; }
body:has(.chat-conversation-active) .block-container { padding-bottom:190px !important; }
body:has(.chat-landing-welcome) .st-key-daily_briefing_upload { top:calc(13vh + min(75vh,900px) - 116px) !important; }
body:has(.chat-conversation-active) .st-key-daily_briefing_upload { top:calc(13vh + min(75vh,900px) - 68px) !important; }
body:has(.chat-landing-welcome) .st-key-daily_briefing_upload [data-testid="stPopoverButton"],body:has(.chat-conversation-active) .st-key-daily_briefing_upload [data-testid="stPopoverButton"] { box-sizing:border-box !important; height:40px !important; min-height:40px !important; padding:0 13px !important; border-color:#D9E4F2 !important; background:#F7FAFF !important; color:#506B91 !important; font-size:12px !important; }
body:has(.chat-landing-welcome) .st-key-daily_briefing_upload [data-testid="stPopoverButton"]:hover,body:has(.chat-conversation-active) .st-key-daily_briefing_upload [data-testid="stPopoverButton"]:hover { border-color:#A9C8F2 !important; background:#FFFFFF !important; color:#326DBD !important; }
body:has(.chat-landing-welcome) .scroll-top-link,body:has(.chat-conversation-active) .scroll-top-link { position:fixed !important; top:calc(13vh + 24px) !important; right:calc((100vw - min(80vw,1440px))/2 + 20px) !important; bottom:auto !important; display:grid !important; place-items:center !important; box-sizing:border-box !important; width:38px !important; height:38px !important; padding:0 !important; border:1px solid #DFE8F4 !important; border-radius:50% !important; background:rgba(255,255,255,.96) !important; color:#58799F !important; box-shadow:0 4px 16px rgba(54,87,133,.09) !important; }
body:has(.chat-conversation-active) .scroll-top-link { right:calc((100vw - min(94vw,1020px))/2 + 20px) !important; }
body:has(.chat-landing-welcome) .scroll-top-link span,body:has(.chat-conversation-active) .scroll-top-link span { display:none !important; }
body:has(.chat-landing-welcome) .scroll-top-link svg,body:has(.chat-conversation-active) .scroll-top-link svg { display:block; width:17px; height:17px; stroke:currentColor; stroke-width:1.7; stroke-linecap:round; stroke-linejoin:round; fill:none; }
body:has(.chat-landing-welcome) .scroll-top-link:hover,body:has(.chat-conversation-active) .scroll-top-link:hover { border-color:#B9D0F0 !important; background:#FFFFFF !important; color:#3978D1 !important; transform:translateY(-2px) !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"] [data-baseweb="textarea"],body:has(.chat-conversation-active) [data-testid="stChatInput"] [data-baseweb="textarea"],body:has(.chat-landing-welcome) [data-testid="stChatInput"] button,body:has(.chat-conversation-active) [data-testid="stChatInput"] button { outline:0 !important; box-shadow:none !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"]:focus-within [data-baseweb="textarea"],body:has(.chat-conversation-active) [data-testid="stChatInput"]:focus-within [data-baseweb="textarea"] { border:0 !important; outline:0 !important; box-shadow:none !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"] div:focus-within,body:has(.chat-conversation-active) [data-testid="stChatInput"] div:focus-within { border:0 !important; outline:0 !important; box-shadow:none !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"] button:focus-visible,body:has(.chat-conversation-active) [data-testid="stChatInput"] button:focus-visible { outline:2px solid #8BB7F1 !important; outline-offset:2px !important; }
@media(max-width:760px) {
  body:has(.chat-landing-welcome) [data-testid="stBottomBlockContainer"] { top:calc(8vh + 84vh - 116px) !important; }
  body:has(.chat-conversation-active) [data-testid="stBottomBlockContainer"] { top:calc(8vh + 84vh - 68px) !important; }
  body:has(.chat-landing-welcome) [data-testid="stChatInput"] { top:calc(8vh + 84vh - 116px) !important; }
  body:has(.chat-conversation-active) [data-testid="stChatInput"] { top:calc(8vh + 84vh - 68px) !important; }
  body:has(.chat-landing-welcome) [data-testid="stChatInput"],body:has(.chat-conversation-active) [data-testid="stChatInput"] { width:88vw !important; }
  body:has(.chat-landing-welcome) .st-key-daily_briefing_upload { top:calc(8vh + 84vh - 116px) !important; left:calc(6vw + 12px) !important; }
  body:has(.chat-conversation-active) .st-key-daily_briefing_upload { top:calc(8vh + 84vh - 68px) !important; left:calc(6vw + 12px) !important; }
  body:has(.chat-landing-welcome) .scroll-top-link,body:has(.chat-conversation-active) .scroll-top-link { top:calc(8vh + 13px) !important; right:calc(3vw + 15px) !important; }
  body:has(.chat-landing-welcome) [data-testid="stChatInput"] textarea,body:has(.chat-conversation-active) [data-testid="stChatInput"] textarea { padding-left:140px !important; font-size:13px !important; }
}

/* Opening motion: a site lead pushes the glass briefing pane aside, revealing the brand. */
.safety-intro-scene { position:absolute; z-index:30; inset:-32px; overflow:hidden; pointer-events:none; border-radius:30px; perspective:1100px; animation:safety-scene-clear 3.25s cubic-bezier(.72,0,.3,1) 1.48s both; }
.safety-intro-pane { position:absolute; z-index:1; top:13%; left:13%; width:61%; height:64%; box-sizing:border-box; display:flex; flex-direction:column; justify-content:center; gap:18px; padding:clamp(26px,5vw,76px); overflow:hidden; border:1px solid rgba(255,255,255,.86); border-radius:32px; background:linear-gradient(132deg,rgba(255,255,255,.93),rgba(242,248,255,.78) 46%,rgba(220,236,255,.69)); box-shadow:0 34px 100px rgba(46,91,153,.15),inset 0 1px 0 #fff,inset 0 -1px 0 rgba(95,145,209,.13); backdrop-filter:blur(25px) saturate(1.14); transform-origin:50% 50%; animation:safety-pane-push 1.55s cubic-bezier(.62,.02,.24,1) .12s both; }
.safety-intro-pane::before { content:""; position:absolute; inset:0; opacity:.42; background:linear-gradient(120deg,transparent 24%,rgba(255,255,255,.82) 48%,rgba(183,213,251,.16) 53%,transparent 69%); transform:translateX(-115%); animation:safety-pane-reflect 1.3s cubic-bezier(.2,.75,.2,1) .18s both; }
.safety-intro-overline { position:relative; z-index:1; color:#6884AA; font:600 11px/1.4 var(--font-mono,monospace); letter-spacing:.16em; }
.safety-intro-title { position:relative; z-index:1; color:#1C3558; font:600 clamp(23px,3.2vw,43px)/1.25 var(--font-ui,"Pretendard",sans-serif); letter-spacing:-.055em; }
.safety-intro-rule { position:relative; z-index:1; width:64px; height:2px; margin-top:4px; border-radius:3px; background:linear-gradient(90deg,#4E8DE7,rgba(78,141,231,0)); }
.safety-intro-worker { position:absolute; z-index:2; right:4%; bottom:-2%; width:min(40%,520px); height:96%; display:flex; align-items:flex-end; justify-content:center; filter:drop-shadow(0 24px 36px rgba(41,71,111,.2)); transform-origin:54% 78%; animation:safety-worker-drive 1.85s cubic-bezier(.19,.76,.21,1) .02s both; }
.safety-intro-worker img { display:block; width:100%; height:100%; object-fit:contain; object-position:center bottom; }
.safety-intro-sheen { position:absolute; z-index:3; inset:0; opacity:0; background:linear-gradient(108deg,transparent 34%,rgba(179,219,255,.05) 43%,rgba(255,255,255,.66) 49%,rgba(138,188,249,.22) 51%,transparent 61%); transform:translateX(-75%); animation:safety-screen-sweep .72s cubic-bezier(.2,.72,.25,1) .96s both; }
.safety-intro-brand { position:absolute; z-index:4; top:49%; left:50%; display:flex; align-items:center; gap:15px; color:#1D3454; opacity:0; transform:translate(-50%,-44%) scale(.88); animation:safety-brand-reveal 1.58s cubic-bezier(.16,.8,.2,1) 1.34s both; }
.safety-intro-mark { display:grid; place-items:center; width:58px; height:58px; border:1px solid rgba(115,156,212,.22); border-radius:19px; background:linear-gradient(145deg,#fff,#EDF4FF); box-shadow:0 12px 28px rgba(66,111,175,.15),inset 0 1px 0 #fff; }
.safety-intro-mark svg { width:31px; height:31px; fill:none; stroke:#4D83D2; stroke-width:2; stroke-linecap:round; stroke-linejoin:round; }
.safety-intro-brand strong,.safety-intro-brand small { display:block; white-space:nowrap; }
.safety-intro-brand strong { font:600 25px/1.2 var(--font-ui,"Pretendard",sans-serif); letter-spacing:-.04em; }
.safety-intro-brand small { margin-top:4px; color:#7B8DA8; font:500 9px/1.3 var(--font-ui,"Pretendard",sans-serif); letter-spacing:.15em; }
.chat-stage-intro { animation-delay:2.06s !important; }
body:has(.chat-landing-welcome) [data-testid="stChatInput"],body:has(.chat-landing-welcome) .st-key-daily_briefing_upload { animation:safety-controls-arrive .65s cubic-bezier(.18,.78,.22,1) 2.35s both; }
@keyframes safety-pane-push { 0% { opacity:0; transform:translate3d(0,16px,-100px) rotateY(-5deg) scale(.97); filter:blur(8px); } 18% { opacity:1; filter:blur(0); } 44% { transform:translate3d(0,0,0) rotateY(0) scale(1); } 100% { opacity:0; transform:translate3d(-115%,1%,80px) rotateY(16deg) scale(.91); filter:blur(9px); } }
@keyframes safety-worker-drive { 0% { opacity:0; transform:translate3d(46%,7%,0) scale(.83) rotate(3deg); filter:blur(8px) drop-shadow(0 24px 36px rgba(41,71,111,.2)); } 18% { opacity:1; filter:blur(0) drop-shadow(0 24px 36px rgba(41,71,111,.2)); } 48% { transform:translate3d(-6%,0,60px) scale(1.04) rotate(0); } 74% { opacity:1; transform:translate3d(-52%,-5%,170px) scale(1.13) rotate(-3deg); } 100% { opacity:0; transform:translate3d(-112%,-12%,260px) scale(1.2) rotate(-6deg); filter:blur(11px) drop-shadow(0 24px 36px rgba(41,71,111,.2)); } }
@keyframes safety-pane-reflect { 0% { transform:translateX(-115%); opacity:0; } 20% { opacity:.55; } 100% { transform:translateX(115%); opacity:0; } }
@keyframes safety-screen-sweep { 0% { opacity:0; transform:translateX(-75%); } 35% { opacity:.8; } 100% { opacity:0; transform:translateX(75%); } }
@keyframes safety-brand-reveal { 0% { opacity:0; transform:translate(-50%,-42%) scale(.82); filter:blur(7px); } 26% { opacity:1; filter:blur(0); } 66% { opacity:1; transform:translate(-50%,-50%) scale(1); } 100% { opacity:0; transform:translate(-50%,-54%) scale(1.015); filter:blur(2px); } }
@keyframes safety-scene-clear { 0%,74% { opacity:1; visibility:visible; } 100% { opacity:0; visibility:hidden; } }
@keyframes safety-controls-arrive { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:translateY(0); } }
@media(max-width:760px) { .safety-intro-scene { inset:-14px; } .safety-intro-pane { top:16%; left:6%; width:78%; height:54%; padding:24px; border-radius:24px; } .safety-intro-worker { right:-5%; bottom:0; width:57%; height:78%; } .safety-intro-title { font-size:clamp(20px,6vw,30px); } .safety-intro-brand { top:48%; gap:10px; } .safety-intro-mark { width:48px; height:48px; border-radius:16px; } .safety-intro-brand strong { font-size:21px; } }
@media(prefers-reduced-motion:reduce) { .safety-intro-scene,.safety-intro-pane,.safety-intro-pane::before,.safety-intro-worker,.safety-intro-sheen,.safety-intro-brand,body:has(.chat-landing-welcome) [data-testid="stChatInput"],body:has(.chat-landing-welcome) .st-key-daily_briefing_upload { animation:none !important; } .safety-intro-scene { display:none !important; } .chat-stage-intro { animation:none !important; } }
</style>
""",
        unsafe_allow_html=True,
    )


def render_back_to_top() -> None:
    st.markdown('<a class="scroll-top-link" href="#page-top" aria-label="페이지 맨 위로 이동"><svg aria-hidden="true" viewBox="0 0 24 24"><path d="M12 19V5M6 11l6-6 6 6"/></svg><span>Back to top</span></a>', unsafe_allow_html=True)


def render_sidebar_brand() -> None:
    st.markdown(
        '<div class="sidebar-brand"><div class="sidebar-brand-icon">✳</div><div>'
        '<div class="sidebar-brand-name">Safety Atlas</div>'
        '<div class="sidebar-brand-sub">INCIDENT OS</div></div></div>',
        unsafe_allow_html=True,
    )


def _navigate(view: str) -> None:
    st.session_state["view"] = view
    st.query_params["page"] = view


def render_header(
    source: str, period: str, rows: int, latest_date: str, is_sample: bool, view: str
) -> None:
    source, period, latest_date = map(escape, (source, period, latest_date))
    page_label = {"overview": "현황 분석", "records": "사고 기록", "guide": "데이터 안내", "chat": "근거 챗봇"}[view]
    if view == "chat":
        st.markdown(
            '<div class="workspace-bar"><div class="crumbs"><span class="crumb-back">‹</span>'
            '<span>Safety Atlas</span><span>/</span><span class="crumb-current">근거 챗봇</span></div>'
            '<div class="workspace-right"><span class="toolbar-badge">SANUP-P RAG</span></div></div>',
            unsafe_allow_html=True,
        )
        return
    st.markdown(
        f'<div class="workspace-bar"><div class="crumbs"><span class="crumb-back">‹</span>'
        f'<span>Safety Atlas</span><span>/</span><span class="crumb-current">{page_label}</span></div>'
        f'<div class="workspace-right"><span class="toolbar-badge">{latest_date} 기준</span>'
        f'<span class="toolbar-count">{rows:,} RECORDS</span></div></div>',
        unsafe_allow_html=True,
    )
    if view == "overview":
        st.markdown(
            '<div class="hero"><div class="hero-content">'
            '<div class="hero-overline">SAFETY INTELLIGENCE / OVERVIEW</div>'
            '<h1>산업재해 현황</h1>'
            '<p>사고 기록에서 오늘의 위험 신호와 발생 패턴을 살펴보세요.</p>'
            '</div></div>',
            unsafe_allow_html=True,
        )
        with st.container(key="hero_ctas"):
            first, second = st.columns([1.3, 1], gap="small")
            with first:
                with st.container(key="hero_primary"):
                    st.button("＋ 사고 기록 보기", on_click=_navigate, args=("records",), width="stretch")
            with second:
                with st.container(key="hero_secondary"):
                    st.button("◉ 데이터 기준", on_click=_navigate, args=("guide",), width="stretch")
    else:
        overline = "INCIDENT RECORDS / EXPLORER" if view == "records" else "DATA SOURCE / METHODOLOGY"
        description = (
            "필터 결과에서 개별 사고를 찾고 필요한 기록을 내려받습니다."
            if view == "records" else "데이터 상태, 집계 기준, 해석 범위를 확인합니다."
        )
        st.markdown(
            f'<div class="simple-intro {view}"><div class="hero-overline">{overline}</div>'
            f'<h1>{page_label}</h1><p>{description}</p></div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        f'<div class="context-line">{source} · {period} · '
        f'{"시연용 가상 데이터" if is_sample else "업로드한 데이터"}</div>',
        unsafe_allow_html=True,
    )
    if is_sample:
        st.markdown(
            '<div class="data-notice">현재 수치는 시연용 가상 데이터이며 실제 산업재해 통계가 아닙니다.</div>',
            unsafe_allow_html=True,
        )


def section_heading(index: str, title: str, description: str = "") -> None:
    st.markdown(
        f'<div class="section-heading"><div class="section-heading-left">'
        f'<span class="section-index">{escape(index)}</span>'
        f'<h2 class="section-title">{escape(title)}</h2></div>'
        f'<span class="section-description">{escape(description)}</span></div>',
        unsafe_allow_html=True,
    )


def panel_heading(overline: str, title: str, subtitle: str, chip: str) -> None:
    st.markdown(
        f'<div class="panel-heading"><div><div class="panel-overline">{escape(overline)}</div>'
        f'<h3 class="panel-title">{escape(title)}</h3>'
        f'<div class="panel-subtitle">{escape(subtitle)}</div></div>'
        f'<span class="panel-chip">{escape(chip)}</span></div>',
        unsafe_allow_html=True,
    )
