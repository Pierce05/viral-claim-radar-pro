"""Premium cyber-intelligence dashboard UI for Viral Claim Radar PRO++."""

from __future__ import annotations

import html
import os
import sys
from typing import Any

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import plotly.graph_objects as go

    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False

from main import run_fact_check, run_live_updates
from modules.claim_extractor import extract_claims
from modules.dataset_loader import get_dataset_stats, load_claims_dataset
from modules.insight_engine import generate_insights
from modules.update_fetcher import get_available_regions
from modules.utils import confidence_to_label

BG = "#060912"
BG2 = "#0B1220"
PRIMARY = "#38BDF8"
DANGER = "#F43F5E"
WARNING = "#F59E0B"
SUCCESS = "#22C55E"
TEXT = "#E2E8F0"
MUTED = "#94A3B8"
LINE = "rgba(56,189,248,0.18)"

SAMPLE_CLAIMS = (
    "Vaccines cause autism.\n"
    "Climate change is primarily caused by human activities.\n"
    "The Great Wall of China is visible from space with the naked eye."
)
SAMPLE_SINGLE = "Vaccines cause autism."


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def pct(value: Any) -> float:
    try:
        return max(0.0, min(100.0, float(value)))
    except Exception:
        return 0.0


def plotly_available() -> bool:
    if not HAS_PLOTLY:
        return False
    try:
        import pandas as pd  # type: ignore

        return all(hasattr(pd, attr) for attr in ["DataFrame", "Series", "Index"])
    except Exception:
        return False


@st.cache_resource
def cached_dataset() -> list[dict]:
    return load_claims_dataset()


def boot_state() -> None:
    st.session_state.setdefault("fact_results", None)
    st.session_state.setdefault("live_results", None)
    st.session_state.setdefault("fact_history", [])
    st.session_state.setdefault("live_history", [])
    st.session_state.setdefault("fact_input", SAMPLE_SINGLE)
    st.session_state.setdefault("region", "Global")


def verdict_meta(label: str) -> tuple[str, str, str]:
    meta = {
        "Supported": ("SUPPORTED", SUCCESS, "rgba(34,197,94,0.18)"),
        "Refuted": ("REFUTED", DANGER, "rgba(244,63,94,0.18)"),
        "Uncertain": ("UNCERTAIN", WARNING, "rgba(245,158,11,0.18)"),
    }
    return meta.get(label, meta["Uncertain"])


def inject_styles() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;700&family=Syne:wght@600;700;800&display=swap');
        .stApp {{
            background:
                radial-gradient(circle at 18% 10%, rgba(56,189,248,0.12), transparent 22%),
                radial-gradient(circle at 82% 14%, rgba(244,63,94,0.08), transparent 20%),
                linear-gradient(180deg, {BG} 0%, {BG2} 100%);
            color:{TEXT};
        }}
        .stApp::before {{
            content:"";
            position:fixed;
            inset:0;
            pointer-events:none;
            opacity:.06;
            background:repeating-linear-gradient(180deg, rgba(255,255,255,.7) 0, rgba(255,255,255,.7) 1px, transparent 2px, transparent 6px);
        }}
        .block-container {{ max-width:1480px; padding-top:1.1rem; padding-bottom:3rem; }}
        [data-testid="stSidebar"] {{ background:linear-gradient(180deg, rgba(11,18,32,.98), rgba(6,9,18,.98)); border-right:1px solid {LINE}; }}
        [data-testid="stSidebar"] .block-container {{ padding-top:1rem; }}
        div[data-baseweb="textarea"] textarea, .stSelectbox div[data-baseweb="select"] > div {{
            background:rgba(8,15,26,.98) !important;
            color:{TEXT} !important;
            border:1px solid {LINE} !important;
            border-radius:16px !important;
            font-family:'IBM Plex Mono', monospace !important;
        }}
        .stButton button {{
            border-radius:14px !important;
            border:1px solid rgba(56,189,248,.34) !important;
            background:linear-gradient(180deg, rgba(11,18,32,.98), rgba(14,24,40,.98)) !important;
            color:white !important;
            font-weight:700 !important;
            box-shadow:0 0 0 1px rgba(56,189,248,.05), 0 14px 28px rgba(2,8,23,.34) !important;
            transition:all .18s ease !important;
            min-height:2.8rem !important;
        }}
        .stButton button:hover {{
            transform:translateY(-1px) scale(1.01);
            box-shadow:0 0 20px rgba(56,189,248,.15), 0 18px 30px rgba(2,8,23,.4) !important;
        }}
        .stTabs [data-baseweb="tab-list"] {{ gap:1.4rem; border-bottom:1px solid rgba(148,163,184,.18); }}
        .stTabs [data-baseweb="tab"] {{ color:rgba(226,232,240,.62); font-weight:700; padding:0 0 .85rem 0; }}
        .stTabs [aria-selected="true"] {{ color:{TEXT} !important; position:relative; }}
        .stTabs [aria-selected="true"]::after {{
            content:"";
            position:absolute; left:0; right:0; bottom:0; height:3px; border-radius:999px;
            background:linear-gradient(90deg, {PRIMARY}, {SUCCESS});
            box-shadow:0 0 18px rgba(56,189,248,.42);
        }}
        .hero, .panel, .metric, .sidebar-panel {{
            background:linear-gradient(180deg, rgba(11,18,32,.98), rgba(15,23,36,.98));
            border:1px solid {LINE};
            box-shadow:0 20px 46px rgba(2,8,23,.42);
        }}
        .hero {{ border-radius:22px; padding:1.55rem 1.8rem; position:relative; overflow:hidden; }}
        .hero::before {{
            content:"";
            position:absolute; inset:-40% -10% auto auto; width:340px; height:340px;
            background:radial-gradient(circle, rgba(56,189,248,.16), transparent 65%);
            animation:floatGlow 6s ease-in-out infinite;
        }}
        @keyframes floatGlow {{ 0%,100%{{transform:translateY(0)}} 50%{{transform:translateY(14px)}} }}
        @keyframes pulseLine {{ 0%,100%{{opacity:.55}} 50%{{opacity:1}} }}
        .eyebrow {{ color:{PRIMARY}; font:700 .78rem 'IBM Plex Mono', monospace; letter-spacing:.28em; text-transform:uppercase; }}
        .hero-title {{ margin:.45rem 0 .5rem 0; font:800 2.7rem 'Syne', sans-serif; line-height:1.04; letter-spacing:-.03em; }}
        .hero-sub {{ color:{MUTED}; line-height:1.8; max-width:860px; }}
        .status-chip {{
            display:inline-flex; align-items:center; gap:.45rem; padding:.42rem .82rem; margin:.22rem .35rem .1rem 0;
            border-radius:999px; border:1px solid rgba(56,189,248,.18); background:rgba(56,189,248,.08);
            font:700 .76rem 'IBM Plex Mono', monospace;
        }}
        .metric {{ border-radius:16px; padding:1rem 1.05rem; min-height:122px; transition:all .18s ease; }}
        .metric:hover {{ transform:translateY(-2px) scale(1.01); box-shadow:0 0 20px rgba(56,189,248,.12), 0 20px 42px rgba(2,8,23,.46); }}
        .metric-label {{ color:{MUTED}; font:700 .76rem 'IBM Plex Mono', monospace; letter-spacing:.14em; text-transform:uppercase; }}
        .metric-value {{ margin-top:.78rem; font:800 2rem 'Syne', sans-serif; animation:countIn .6s ease; }}
        .metric-line {{ width:44px; height:4px; border-radius:999px; margin-top:.82rem; animation:pulseLine 2.2s infinite; }}
        @keyframes countIn {{ from{{opacity:0; transform:translateY(8px)}} to{{opacity:1; transform:translateY(0)}} }}
        .section-title {{ font:800 1.6rem 'Syne', sans-serif; margin:0; }}
        .muted {{ color:{MUTED}; line-height:1.75; }}
        .divider {{ height:1px; margin:1rem 0; background:linear-gradient(90deg, transparent, rgba(56,189,248,.28), transparent); }}
        .claim-chip {{
            display:inline-flex; align-items:center; padding:.42rem .76rem; margin:.2rem .34rem .12rem 0;
            border-radius:999px; border:1px solid rgba(56,189,248,.16); background:rgba(56,189,248,.08);
            font:700 .74rem 'IBM Plex Mono', monospace;
        }}
        .result-card, .feed-card, .signal-card {{
            border-radius:18px; padding:1.05rem 1.15rem; margin-bottom:1rem; transition:all .18s ease;
        }}
        .result-card:hover, .feed-card:hover, .signal-card:hover {{ transform:translateY(-2px) scale(1.005); }}
        .result-card {{ background:linear-gradient(180deg, rgba(11,18,32,.98), rgba(13,22,35,.98)); border:1px solid {LINE}; }}
        .feed-card {{ background:linear-gradient(180deg, rgba(11,18,32,.98), rgba(14,22,34,.98)); border:1px solid {LINE}; animation:slideIn .35s ease; }}
        .signal-card {{ background:linear-gradient(180deg, rgba(42,10,18,.94), rgba(24,10,14,.96)); border:1px solid rgba(244,63,94,.22); border-left:4px solid {DANGER}; box-shadow:0 0 18px rgba(244,63,94,.12); }}
        @keyframes slideIn {{ from{{opacity:0; transform:translateY(10px)}} to{{opacity:1; transform:translateY(0)}} }}
        .kicker {{ color:{MUTED}; font:700 .74rem 'IBM Plex Mono', monospace; letter-spacing:.12em; text-transform:uppercase; }}
        .claim-text {{ margin:.45rem 0 .75rem 0; font:700 1.06rem 'Syne', sans-serif; line-height:1.55; }}
        .verdict-pill {{
            display:inline-flex; padding:.36rem .76rem; border-radius:999px; border:1px solid rgba(255,255,255,.08);
            font:800 .74rem 'IBM Plex Mono', monospace; letter-spacing:.06em; text-transform:uppercase;
        }}
        .confidence-meta {{ display:flex; justify-content:space-between; margin:.65rem 0 .34rem 0; color:{MUTED}; font:500 .78rem 'IBM Plex Mono', monospace; }}
        .confidence-track {{ height:10px; border-radius:999px; overflow:hidden; background:rgba(255,255,255,.05); }}
        .confidence-fill {{ height:10px; border-radius:999px; animation:growBar .7s ease; }}
        @keyframes growBar {{ from{{width:0 !important}} to{{}} }}
        .hint-box {{
            border:1px dashed rgba(56,189,248,.28); border-radius:18px; padding:1.08rem 1.18rem;
            background:rgba(9,16,26,.82); color:{MUTED};
        }}
        .summary-card {{ padding:.85rem .95rem; border-radius:14px; background:rgba(16,25,42,.72); border:1px solid rgba(140,163,184,.12); margin-bottom:.55rem; line-height:1.65; }}
        .chart-box {{ background:rgba(16,25,42,.76); border:1px solid rgba(140,163,184,.12); border-radius:16px; padding:1rem; min-height:250px; }}
        .bar-row {{ margin-bottom:.78rem; }}
        .bar-meta {{ display:flex; justify-content:space-between; color:{MUTED}; font:500 .82rem 'IBM Plex Mono', monospace; margin-bottom:.35rem; }}
        .bar-track {{ height:9px; border-radius:999px; overflow:hidden; background:rgba(255,255,255,.05); }}
        .bar-fill {{ height:9px; border-radius:999px; }}
        details {{ background:rgba(16,25,42,.6); border:1px solid rgba(140,163,184,.12); border-radius:14px; padding:.8rem .95rem; }}
        details summary {{ cursor:pointer; color:{PRIMARY}; font-weight:700; }}
        .status-dot {{ width:9px; height:9px; border-radius:999px; background:{SUCCESS}; display:inline-block; box-shadow:0 0 14px {SUCCESS}; }}
        .signal-label {{
            display:inline-flex; align-items:center; gap:.35rem; margin-right:.35rem; padding:.3rem .68rem;
            border-radius:999px; background:rgba(244,63,94,.12); color:#FFC1CC; border:1px solid rgba(244,63,94,.2);
            font:800 .72rem 'IBM Plex Mono', monospace; text-transform:uppercase;
        }}
        .signal-strength {{ display:flex; gap:4px; margin-top:.7rem; }}
        .signal-strength span {{ width:14px; height:6px; border-radius:999px; background:rgba(56,189,248,.16); }}
        .signal-strength span.on {{ background:{PRIMARY}; box-shadow:0 0 10px rgba(56,189,248,.34); }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: Any, color: str) -> None:
    st.markdown(
        f'<div class="metric"><div class="metric-label">{esc(label)}</div><div class="metric-value" style="color:{color};">{esc(value)}</div><div class="metric-line" style="background:{color}; box-shadow:0 0 16px {color}66;"></div></div>',
        unsafe_allow_html=True,
    )


def render_sidebar(stats: dict, records: list[dict]) -> None:
    with st.sidebar:
        st.markdown(
            f'<div class="sidebar-panel"><div class="kicker">System Status</div><div style="margin-top:.55rem;font:800 1.32rem Syne, sans-serif;">ACTIVE</div><div class="muted" style="margin-top:.35rem;"><span class="status-dot"></span> Local-first fallback mode online.</div><div class="signal-strength"><span class="on"></span><span class="on"></span><span class="on"></span><span></span><span></span></div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="sidebar-panel"><div class="kicker">Session</div><div style="margin-top:.7rem;display:grid;gap:.45rem;"><div><strong>Total claims analyzed:</strong> {len(st.session_state.get("fact_history", []))}</div><div><strong>Live updates scored:</strong> {len(st.session_state.get("live_history", []))}</div><div><strong>Knowledge base size:</strong> {stats["total"]}</div></div></div>',
            unsafe_allow_html=True,
        )
        if st.button("Run Demo Flow", use_container_width=True):
            with st.spinner("Running guided demo flow..."):
                st.session_state["fact_input"] = SAMPLE_CLAIMS
                fact = run_fact_check(SAMPLE_CLAIMS, dataset=records, use_llm=False, top_k=3)
                live = run_live_updates(region="Global", dataset=records, max_items=6)
                st.session_state["fact_results"] = fact
                st.session_state["live_results"] = live
                st.session_state["fact_history"] = fact.get("results", [])
                st.session_state["live_history"] = live.get("assessments", [])
                st.session_state["region"] = "Global"
        st.markdown('<div class="sidebar-panel"><div class="kicker">Demo Instructions</div><div class="muted" style="margin-top:.7rem;">1. Load sample claims.<br>2. Analyze verdict cards.<br>3. Open Live Radar.<br>4. Finish in Insights.</div></div>', unsafe_allow_html=True)


def confidence_bar(label: str, confidence: Any) -> None:
    _, color, _ = verdict_meta(label)
    value = pct(confidence)
    st.markdown(
        f'<div class="confidence-meta"><span>Confidence Signal</span><span>{value:.0f}% · {esc(confidence_to_label(value))}</span></div><div class="confidence-track"><div class="confidence-fill" style="width:{value}%; background:linear-gradient(90deg, {color}, rgba(255,255,255,.18));"></div></div>',
        unsafe_allow_html=True,
    )


def render_matches(matches: list[dict]) -> None:
    if not matches:
        return
    with st.expander("Evidence Matches"):
        for idx, match in enumerate(matches, start=1):
            label = match.get("label", "Uncertain")
            _, color, _ = verdict_meta(label)
            st.markdown(
                f'<div class="panel" style="margin-bottom:.7rem;"><div class="kicker" style="color:{color};">MATCH {idx} · {esc(label)} · {pct(match.get("similarity_score",0)):.0f}% similarity</div><div class="muted" style="margin-top:.45rem;color:{TEXT};font-weight:700;">{esc(match.get("claim",""))}</div><div class="muted" style="margin-top:.35rem;">{esc(match.get("explanation",""))}</div><div class="muted" style="margin-top:.35rem;font-family:IBM Plex Mono, monospace;">Source: {esc(match.get("source","Local knowledge base"))}</div></div>',
                unsafe_allow_html=True,
            )


def render_fact_results(results: dict | None) -> None:
    if not results:
        st.markdown('<div class="hint-box">Try a sample claim to populate the verdict stream and evidence panels.</div>', unsafe_allow_html=True)
        return
    if results.get("error"):
        st.error(results["error"])
        return
    for item in results.get("results", []):
        label = item.get("label", "Uncertain")
        badge, color, glow = verdict_meta(label)
        consensus = item.get("consensus", {}) or {}
        trust_score = float(item.get("trust_score", 0.5) or 0.5)
        adjusted_verdict = item.get("adjusted_verdict", badge)
        sources = item.get("sources", []) or []
        st.markdown(
            f'<div class="result-card" style="border-left:3px solid {color}; box-shadow:0 0 0 1px {glow}, 0 18px 40px rgba(2,8,23,.44);"><div class="kicker">Live Verdict</div><div class="claim-text">{esc(item.get("claim",""))}</div><div class="verdict-pill" style="color:{color}; background:{glow};">{badge}</div><div class="muted" style="margin-top:.75rem;font-family:IBM Plex Mono, monospace;">Adjusted verdict: {esc(adjusted_verdict)}</div><div class="muted" style="margin-top:.75rem;">{esc(item.get("explanation",""))}</div></div>',
            unsafe_allow_html=True,
        )
        confidence_bar(label, item.get("confidence", 0))
        st.markdown(
            f'<div class="panel" style="margin:.8rem 0 1rem 0;"><div class="kicker">Consensus</div><div class="muted" style="margin-top:.55rem;font-family:IBM Plex Mono, monospace;">{consensus.get("refute", 0)} refute • {consensus.get("support", 0)} support</div><div class="muted" style="margin-top:.45rem;font-family:IBM Plex Mono, monospace;">Credibility Score: {int(trust_score * 100)}/100</div><div class="muted" style="margin-top:.45rem;font-family:IBM Plex Mono, monospace;">Enhanced Confidence: {int(float(item.get("enhanced_confidence", 0.5) or 0.5) * 100)}/100</div></div>',
            unsafe_allow_html=True,
        )
        if sources:
            with st.expander("Sources"):
                st.markdown("### 🔎 Sources")
                for source in sources:
                    title = source.get("title") or "Untitled source"
                    url = source.get("url") or ""
                    name = source.get("source") or "Unknown source"
                    if url:
                        st.markdown(f"- [{title}]({url}) ({name})")
                    else:
                        st.markdown(f"- {title} ({name})")
        elif item.get("wiki"):
            with st.expander("Wikipedia Fallback"):
                st.markdown(item.get("wiki", ""))
        render_matches(item.get("top_matches", []))


def render_live_feed(results: dict | None) -> None:
    if not results:
        st.markdown('<div class="hint-box">Refresh the local feed to populate Live Radar.</div>', unsafe_allow_html=True)
        return
    for item in results.get("assessments", []):
        label = item.get("label", "Uncertain")
        badge, color, glow = verdict_meta(label)
        st.markdown(
            f'<div class="feed-card" style="border-color:{glow}; box-shadow:0 0 0 1px {glow}, 0 18px 40px rgba(2,8,23,.44);"><div class="kicker">{esc(item.get("category","General"))} · {esc(item.get("region","Global"))}</div><div class="claim-text">{esc(item.get("headline",""))}</div><div class="verdict-pill" style="color:{color}; background:{glow};">{badge}</div><div class="muted" style="margin-top:.85rem;">{esc(item.get("reasoning",""))}</div></div>',
            unsafe_allow_html=True,
        )
        confidence_bar(label, item.get("confidence", 0))


def fallback_bars(rows: list[dict], label_key: str, value_key: str, fill: str) -> None:
    st.markdown('<div class="chart-box">', unsafe_allow_html=True)
    if rows:
        max_value = max(pct(row.get(value_key, 0)) for row in rows) or 1
        for row in rows:
            width = pct(row.get(value_key, 0)) / max_value * 100
            st.markdown(
                f'<div class="bar-row"><div class="bar-meta"><span>{esc(row.get(label_key,"Unknown"))}</span><span>{pct(row.get(value_key,0)):.0f}</span></div><div class="bar-track"><div class="bar-fill" style="width:{width}%; background:{fill};"></div></div></div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown('<div class="muted">No chart data available yet.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def plot_or_fallback(kind: str, rows: list[dict], distribution: dict | None = None, label_key: str = "", value_key: str = "", color: str = PRIMARY, horizontal: bool = False) -> None:
    if plotly_available():
        if kind == "pie" and distribution is not None:
            fig = go.Figure(data=[go.Pie(labels=["Supported", "Refuted", "Uncertain"], values=[distribution.get("Supported", 0), distribution.get("Refuted", 0), distribution.get("Uncertain", 0)], hole=0.68, marker={"colors": [SUCCESS, DANGER, WARNING]}, textinfo="label+percent", sort=False)])
        elif horizontal:
            fig = go.Figure(go.Bar(y=[r.get(label_key) for r in rows], x=[r.get(value_key) for r in rows], orientation="h", marker=dict(color=color)))
        else:
            fig = go.Figure(go.Bar(x=[r.get(label_key) for r in rows], y=[r.get(value_key) for r in rows], marker=dict(color=color)))
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT), margin=dict(l=0, r=0, t=0, b=0), height=270, showlegend=False, xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="rgba(148,163,184,.12)"))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        if kind == "pie" and distribution is not None:
            rows = [{"label": "Supported", "value": distribution.get("Supported", 0)}, {"label": "Refuted", "value": distribution.get("Refuted", 0)}, {"label": "Uncertain", "value": distribution.get("Uncertain", 0)}]
            label_key, value_key, color = "label", "value", f"linear-gradient(90deg, {PRIMARY}, rgba(255,255,255,.14))"
        fallback_bars(rows, label_key, value_key, f"linear-gradient(90deg, {color}, rgba(255,255,255,.14))")


def render_insights(insights: dict) -> None:
    label_dist = insights.get("label_distribution", {})
    topic_rows = [{"topic": k, "count": v.get("count", 0)} for k, v in list(insights.get("topic_distribution", {}).items())[:6]]
    bins = [{"bucket": f"{start}-{start+9}", "count": 0} for start in range(0, 100, 10)]
    for score in insights.get("confidence_trend", {}).get("scores", []):
        bins[min(int(float(score) // 10), 9)]["count"] += 1
    region_rows = [{"region": k, "refuted": v.get("refuted_pct", 0)} for k, v in list(insights.get("region_breakdown", {}).items())[:6]]

    st.markdown("### INTELLIGENCE SUMMARY")
    for bullet in insights.get("summary_bullets", []):
        st.markdown(f'<div class="summary-card">{esc(bullet)}</div>', unsafe_allow_html=True)

    r1c1, r1c2 = st.columns(2)
    r2c1, r2c2 = st.columns(2)
    with r1c1:
        st.markdown("### Verdict Distribution")
        plot_or_fallback("pie", [], distribution=label_dist)
    with r1c2:
        st.markdown("### Topic Activity")
        plot_or_fallback("bar", topic_rows, label_key="topic", value_key="count", color=PRIMARY, horizontal=True)
    with r2c1:
        st.markdown("### Confidence Histogram")
        plot_or_fallback("bar", bins, label_key="bucket", value_key="count", color=WARNING)
    with r2c2:
        st.markdown("### Region Breakdown")
        plot_or_fallback("bar", region_rows, label_key="region", value_key="refuted", color=DANGER)

    st.markdown("### Threat Signals")
    recurring = insights.get("recurring_disinfo", [])
    if recurring:
        for item in recurring:
            st.markdown(
                f'<div class="signal-card"><div><span class="signal-label">⚠ HIGH RISK</span><span class="signal-label">🔴 PATTERN DETECTED</span></div><div class="claim-text" style="font-size:1.02rem;">{esc(item.get("pattern",""))}</div><div class="muted" style="color:#F3B2BE;">{esc(item.get("description",""))}</div><div class="muted" style="margin-top:.55rem;font-family:IBM Plex Mono, monospace;color:#CDA7AF;">Example: {esc(item.get("example_claim",""))}</div></div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown('<div class="hint-box">No recurring misinformation signatures are active in the current session.</div>', unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(page_title="Viral Claim Radar PRO++", page_icon="🛰️", layout="wide")
    boot_state()
    inject_styles()

    records = cached_dataset()
    stats = get_dataset_stats(records)
    render_sidebar(stats, records)

    st.markdown(
        f'<div class="hero"><div class="eyebrow">CYBER INTELLIGENCE DASHBOARD</div><div class="hero-title">Viral Claim Radar PRO++</div><div class="hero-sub">Real-Time Claim Intelligence Platform for offline-safe demos, structured evidence review, and threat-signal analysis.</div><div style="margin-top:1rem;"><span class="status-chip">LOCAL-FIRST</span><span class="status-chip">OFFLINE SAFE</span><span class="status-chip">NO API REQUIRED</span><span class="status-chip">SYSTEM READY</span></div></div>',
        unsafe_allow_html=True,
    )

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        metric_card("Total Claims", stats["total"], PRIMARY)
    with k2:
        metric_card("Supported", stats["supported"], SUCCESS)
    with k3:
        metric_card("Refuted", stats["refuted"], DANGER)
    with k4:
        metric_card("Uncertain", stats["uncertain"], WARNING)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    fact_tab, live_tab, insights_tab = st.tabs(["Fact Check", "Live Radar", "Insights"])

    with fact_tab:
        st.markdown('<h2 class="section-title">Fact Check Mode</h2><div class="muted">Terminal-style input, extracted-claim chips, and live verdict cards with confidence and evidence.</div>', unsafe_allow_html=True)
        left, right = st.columns([1.05, 1.2])
        with left:
            st.markdown('<div class="panel">', unsafe_allow_html=True)
            claim_input = st.text_area("Claim input", value=st.session_state.get("fact_input", SAMPLE_SINGLE), height=220)
            st.session_state["fact_input"] = claim_input
            c1, c2 = st.columns(2)
            with c1:
                analyze = st.button("Analyze Claim", use_container_width=True)
            with c2:
                sample = st.button("Load Sample", use_container_width=True)
            if sample:
                st.session_state["fact_input"] = SAMPLE_CLAIMS
                st.rerun()
            st.markdown('<div class="divider"></div><div class="kicker">Extracted Claims</div>', unsafe_allow_html=True)
            claims = extract_claims(st.session_state.get("fact_input", ""), use_llm=False, api_key=None).get("claims", [])
            if claims:
                for claim in claims[:6]:
                    st.markdown(f'<span class="claim-chip">{esc(claim)}</span>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="hint-box" style="margin-top:.75rem;">Try a sample claim to generate extracted-claim chips.</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        if analyze:
            with st.spinner("Extracting claims, matching evidence, and generating verdicts..."):
                results = run_fact_check(st.session_state.get("fact_input", SAMPLE_SINGLE), dataset=records, use_llm=False, top_k=3)
                st.session_state["fact_results"] = results
                st.session_state["fact_history"] = results.get("results", [])
        with right:
            render_fact_results(st.session_state.get("fact_results"))

    with live_tab:
        st.markdown('<h2 class="section-title">Live Radar</h2><div class="muted">A structured intelligence feed with region controls, verdict glow, and confidence signals.</div>', unsafe_allow_html=True)
        c1, c2, _ = st.columns([1, 1, 2.4])
        with c1:
            regions = get_available_regions()
            idx = regions.index(st.session_state.get("region", "Global")) if st.session_state.get("region", "Global") in regions else 0
            st.session_state["region"] = st.selectbox("Region", regions, index=idx)
        with c2:
            refresh = st.button("Refresh Radar", use_container_width=True)
        if refresh or st.session_state.get("live_results") is None:
            with st.spinner("Refreshing local radar feed..."):
                live = run_live_updates(region=st.session_state.get("region", "Global"), dataset=records, max_items=6)
                st.session_state["live_results"] = live
                st.session_state["live_history"] = live.get("assessments", [])
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        render_live_feed(st.session_state.get("live_results"))

    with insights_tab:
        st.markdown('<h2 class="section-title">Insights</h2><div class="muted">Dark-themed intelligence summary with neon chart accents and dramatic threat-signal surfacing.</div>', unsafe_allow_html=True)
        with st.spinner("Generating intelligence summary..."):
            insights = generate_insights(
                fact_check_results=st.session_state.get("fact_history"),
                live_update_results=st.session_state.get("live_history"),
                dataset=records,
            )
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        render_insights(insights)


if __name__ == "__main__":
    main()
