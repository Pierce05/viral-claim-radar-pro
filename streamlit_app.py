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
from modules.update_fetcher import get_available_regions, get_available_topics
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
    st.session_state.setdefault("topic", "All")
    st.session_state.setdefault("live_filter_signature", ("Global", "All"))


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
        html, body, [class*="css"] {{
            font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
        }}
        body, .stApp {{
            background-color: {BG2};
            color: {TEXT};
            font-family: system-ui, -apple-system, sans-serif;
        }}
        .block-container {{
            padding-top: 2rem;
            padding-bottom: 2rem;
            max-width: 1100px;
        }}
        h1, h2, h3 {{
            font-family: system-ui, -apple-system, sans-serif;
            font-weight: 600;
            letter-spacing: 0.1px;
        }}
        code, pre, textarea, .kicker, .metric-label, .status-chip, .claim-chip, .verdict-pill, .confidence-meta {{
            font-family: 'IBM Plex Mono', monospace !important;
        }}
        [data-testid="stSidebar"] {{
            background: #0f1522;
            border-right: 1px solid #1f2937;
        }}
        div[data-baseweb="textarea"] textarea, .stSelectbox div[data-baseweb="select"] > div {{
            background: #0f172a !important;
            color: #e5e7eb !important;
            border: 1px solid #243244 !important;
            border-radius: 10px !important;
            padding: 12px !important;
            font-size: 15px !important;
        }}
        .stButton button {{
            border-radius: 10px !important;
            border: 1px solid #334155 !important;
            background: #111827 !important;
            color: #e6edf3 !important;
            box-shadow: none !important;
        }}
        .stTabs [data-baseweb="tab-list"] {{
            gap: 1rem;
            border-bottom: 1px solid #1f2937;
        }}
        .stTabs [data-baseweb="tab"] {{
            color: #94a3b8;
            font-weight: 500;
            padding: 0 0 0.8rem 0;
        }}
        .stTabs [aria-selected="true"] {{
            color: #e6edf3 !important;
            border-bottom: 2px solid {PRIMARY};
        }}
        .hero, .panel, .metric, .sidebar-panel, .result-card, .feed-card, .signal-card, .chart-box, .summary-card, .hint-box {{
            background: #111827;
            border: 1px solid #1f2937;
            box-shadow: none;
            border-radius: 12px;
        }}
        .hero {{
            padding: 1.5rem 1.7rem;
        }}
        .hero::before {{
            display: none;
        }}
        .eyebrow {{
            color: {PRIMARY};
            font: 700 .76rem 'IBM Plex Mono', monospace;
            letter-spacing: .18em;
            text-transform: uppercase;
        }}
        .hero-title {{
            margin: .4rem 0 .55rem 0;
            font-size: 2.35rem;
            line-height: 1.08;
            font-weight: 700;
        }}
        .hero-sub, .muted {{
            color: {MUTED};
            line-height: 1.7;
        }}
        .status-chip, .claim-chip {{
            display: inline-flex;
            align-items: center;
            padding: .42rem .75rem;
            margin: .2rem .32rem .12rem 0;
            border-radius: 999px;
            border: 1px solid #243244;
            background: #0f172a;
            font-size: .74rem;
            font-weight: 600;
        }}
        .metric {{
            padding: 1rem;
            min-height: 112px;
        }}
        .metric-label {{
            color: {MUTED};
            font-size: .74rem;
            letter-spacing: .12em;
            text-transform: uppercase;
            font-weight: 700;
        }}
        .metric-value {{
            margin-top: .8rem;
            font-size: 2rem;
            font-weight: 700;
        }}
        .metric-line {{
            width: 40px;
            height: 4px;
            border-radius: 999px;
            margin-top: .85rem;
        }}
        .section-title {{
            font-size: 1.55rem;
            font-weight: 600;
            margin: 0;
        }}
        .divider {{
            height: 1px;
            margin: 1rem 0;
            background: #1f2937;
        }}
        .result-card, .feed-card, .signal-card {{
            padding: 1rem 1.1rem;
            margin-bottom: 1rem;
        }}
        .briefing-card {{
            background: #111827;
            border: 1px solid #223047;
            border-radius: 14px;
            padding: 1rem 1.1rem;
            margin-bottom: .9rem;
        }}
        .briefing-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: .75rem;
            margin: .8rem 0 1rem 0;
        }}
        .briefing-metric {{
            background: #0f172a;
            border: 1px solid #223047;
            border-radius: 12px;
            padding: .85rem .95rem;
        }}
        .briefing-label {{
            color: #9fb0c7;
            font-size: .78rem;
            font-weight: 600;
            margin-bottom: .3rem;
        }}
        .briefing-value {{
            color: #e8eef7;
            font-size: 1rem;
            line-height: 1.5;
        }}
        .briefing-note {{
            color: #9fb0c7;
            line-height: 1.7;
            margin-top: .7rem;
        }}
        .source-item {{
            background: #0f172a;
            border: 1px solid #223047;
            border-radius: 12px;
            padding: .85rem .95rem;
            margin-bottom: .7rem;
        }}
        .source-title {{
            color: #f8fafc;
            font-weight: 700;
            line-height: 1.5;
            margin-bottom: .3rem;
        }}
        .source-meta {{
            color: #9fb0c7;
            font-size: .85rem;
            line-height: 1.6;
        }}
        .reading-card {{
            background: #0f172a;
            border: 1px solid #223047;
            border-radius: 12px;
            padding: .95rem 1rem;
            margin: .75rem 0;
        }}
        .reading-title {{
            color: #e8eef7;
            font-size: .95rem;
            font-weight: 700;
            margin-bottom: .35rem;
        }}
        .reading-body {{
            color: #c2d0e1;
            line-height: 1.75;
            font-size: .98rem;
        }}
        .kicker {{
            color: {MUTED};
            font-size: .73rem;
            letter-spacing: .11em;
            text-transform: uppercase;
            font-weight: 700;
        }}
        .soft-kicker {{
            color: #9fb0c7;
            font-size: .82rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: .08em;
        }}
        .claim-text {{
            margin: .45rem 0 .75rem 0;
            font-size: 1.08rem;
            font-weight: 600;
            line-height: 1.55;
        }}
        .verdict-pill {{
            display: inline-flex;
            padding: .35rem .74rem;
            border-radius: 999px;
            border: 1px solid #334155;
            font-size: .74rem;
            font-weight: 700;
            letter-spacing: .04em;
            text-transform: uppercase;
        }}
        .confidence-meta {{
            display: flex;
            justify-content: space-between;
            margin: .65rem 0 .34rem 0;
            color: {MUTED};
            font-size: .78rem;
        }}
        .confidence-track {{
            height: 10px;
            border-radius: 999px;
            overflow: hidden;
            background: #1f2937;
        }}
        .confidence-fill {{
            height: 10px;
            border-radius: 999px;
        }}
        .summary-card {{
            padding: .85rem .95rem;
            margin-bottom: .55rem;
            line-height: 1.65;
        }}
        .chart-box {{
            padding: 1rem;
            min-height: 250px;
        }}
        .bar-row {{
            margin-bottom: .78rem;
        }}
        .bar-meta {{
            display: flex;
            justify-content: space-between;
            color: {MUTED};
            font-size: .82rem;
            margin-bottom: .35rem;
        }}
        .bar-track {{
            height: 9px;
            border-radius: 999px;
            overflow: hidden;
            background: #1f2937;
        }}
        .bar-fill {{
            height: 9px;
            border-radius: 999px;
        }}
        details {{
            background: #0f172a;
            border: 1px solid #243244;
            border-radius: 12px;
            padding: .8rem .95rem;
        }}
        details summary {{
            cursor: pointer;
            color: {PRIMARY};
            font-weight: 600;
        }}
        .status-dot {{
            width: 9px;
            height: 9px;
            border-radius: 999px;
            background: {SUCCESS};
            display: inline-block;
        }}
        .signal-label {{
            display: inline-flex;
            align-items: center;
            gap: .35rem;
            margin-right: .35rem;
            padding: .3rem .68rem;
            border-radius: 999px;
            background: #1f1720;
            color: #fecdd3;
            border: 1px solid #3f1d2b;
            font-size: .72rem;
            font-weight: 700;
            text-transform: uppercase;
        }}
        .signal-strength {{
            display: flex;
            gap: 4px;
            margin-top: .7rem;
        }}
        .signal-strength span {{
            width: 14px;
            height: 6px;
            border-radius: 999px;
            background: #243244;
        }}
        .signal-strength span.on {{
            background: {PRIMARY};
        }}
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
                live = run_live_updates(region="Global", topic="All", dataset=records, max_items=6)
                st.session_state["fact_results"] = fact
                st.session_state["live_results"] = live
                st.session_state["fact_history"] = fact.get("results", [])
                st.session_state["live_history"] = live.get("assessments", [])
                st.session_state["region"] = "Global"
                st.session_state["topic"] = "All"
                st.session_state["live_filter_signature"] = ("Global", "All")
        st.markdown('<div class="sidebar-panel"><div class="kicker">Demo Instructions</div><div class="muted" style="margin-top:.7rem;">1. Load sample claims.<br>2. Analyze verdict cards.<br>3. Open Live Radar.<br>4. Finish in Insights.</div></div>', unsafe_allow_html=True)


def confidence_bar(label: str, confidence: Any) -> None:
    _, color, _ = verdict_meta(label)
    value = pct(confidence)
    st.markdown(
        f'<div class="confidence-meta"><span>Confidence Signal</span><span>{value:.0f}% · {esc(confidence_to_label(value))}</span></div><div class="confidence-track"><div class="confidence-fill" style="width:{value}%; background:linear-gradient(90deg, {color}, rgba(255,255,255,.18));"></div></div>',
        unsafe_allow_html=True,
    )


def format_live_timestamp(value: Any) -> str:
    raw = "" if value is None else str(value).strip()
    if not raw:
        return "Timestamp unavailable"
    try:
        normalized = raw.replace("Z", "+00:00")
        stamp = normalized if "T" in normalized else normalized.replace(" ", "T")
        from datetime import datetime

        return datetime.fromisoformat(stamp).strftime("%d %b %Y · %I:%M %p")
    except Exception:
        return raw


def render_matches(matches: list[dict]) -> None:
    visible_matches = [match for match in (matches or []) if float(match.get("similarity_score", 0) or 0) >= 20]
    if not visible_matches:
        return
    with st.expander("Evidence Matches"):
        for idx, match in enumerate(visible_matches, start=1):
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
        consensus_text = (
            "No strong consensus detected. Limited high-confidence sources."
            if not consensus.get("refute", 0) and not consensus.get("support", 0)
            else f"{consensus.get('refute', 0)} refute • {consensus.get('support', 0)} support"
        )
        st.markdown(
            f'<div class="result-card" style="border-left:3px solid {color}; box-shadow:0 0 0 1px {glow}, 0 18px 40px rgba(2,8,23,.44);"><div class="soft-kicker">Live Verdict</div><div class="claim-text">{esc(item.get("claim",""))}</div><div class="verdict-pill" style="color:{color}; background:{glow};">{badge}</div><div class="reading-card"><div class="reading-title">Assessment</div><div class="reading-body">{esc(item.get("explanation",""))}</div></div></div>',
            unsafe_allow_html=True,
        )
        fetch_status = "ACTIVE" if item.get("source_fetch_active") else "INACTIVE"
        fetch_detail = "Google News live retrieval is active." if item.get("source_fetch_active") else "Google News live retrieval is inactive. Add SERP_API_KEY for real-time sources."
        st.markdown(
            f'<div class="briefing-grid"><div class="briefing-metric"><div class="briefing-label">Verdict</div><div class="briefing-value">{esc(adjusted_verdict)}</div></div><div class="briefing-metric"><div class="briefing-label">Live Sources</div><div class="briefing-value">{fetch_status} · {esc(item.get("source_fetch_mode","news"))}</div></div><div class="briefing-metric"><div class="briefing-label">Consensus</div><div class="briefing-value">{esc(consensus_text)}</div></div><div class="briefing-metric"><div class="briefing-label">Credibility</div><div class="briefing-value">{int(trust_score * 100)}/100</div></div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="reading-card"><div class="reading-title">Search Query</div><div class="reading-body">{esc(item.get("search_query",""))}</div><div class="briefing-note">{esc(fetch_detail)}</div></div>',
            unsafe_allow_html=True,
        )
        if item.get("claim_type") == "current_event" and not item.get("source_fetch_active"):
            st.warning("Live Google News retrieval is OFF for this current-event claim. Add `SERP_API_KEY` locally or in deployment secrets to verify against real-time reporting.")
        confidence_bar(label, item.get("confidence", 0))
        st.markdown(
            f'<div class="reading-card"><div class="reading-title">Confidence</div><div class="reading-body">Enhanced confidence: {int(float(item.get("enhanced_confidence", 0.5) or 0.5) * 100)}/100</div></div>',
            unsafe_allow_html=True,
        )
        if sources:
            with st.expander("Sources"):
                st.markdown("### Verified Sources")
                refutes = sum(1 for source in sources if source.get("stance") == "REFUTES")
                supports = sum(1 for source in sources if source.get("stance") == "SUPPORTS")
                unclear = sum(1 for source in sources if source.get("stance") not in {"REFUTES", "SUPPORTS"})
                st.markdown(
                    f'<div class="reading-card"><div class="reading-title">Source Snapshot</div><div class="reading-body">{refutes} refuting sources, {supports} supporting sources, {unclear} neutral.</div></div>',
                    unsafe_allow_html=True,
                )
                for source in sources:
                    title = source.get("title") or "Untitled source"
                    url = source.get("url") or ""
                    name = source.get("source") or "Unknown source"
                    stance = source.get("stance") or "UNCLEAR"
                    why = source.get("why") or "Matches the verification search intent"
                    published = source.get("published_at") or ""
                    score = float(source.get("credibility", 0) or 0)
                    meta = f"Source: {name} | Credibility: {score:.2f} | Stance: {stance}"
                    if published:
                        meta += f" | Published: {published}"
                    title_line = f'<a href="{esc(url)}" target="_blank" style="color:#f8fafc;text-decoration:none;">{esc(title)}</a>' if url else esc(title)
                    st.markdown(
                        f'<div class="source-item"><div class="source-title">{title_line}</div><div class="source-meta">{esc(meta)}</div><div class="briefing-note">Why it was selected: {esc(why)}</div></div>',
                        unsafe_allow_html=True,
                    )
        elif item.get("wiki"):
            with st.expander("Wikipedia Fallback"):
                st.markdown(item.get("wiki", ""))
        render_matches(item.get("top_matches", []))


def render_live_feed(results: dict | None) -> None:
    if not results:
        st.markdown('<div class="hint-box">Refresh the local feed to populate Live Radar.</div>', unsafe_allow_html=True)
        return
    st.markdown(
        f'<div class="panel" style="margin-bottom:1rem;"><div class="kicker">Active Feed</div><div class="muted" style="margin-top:.55rem;">Region: <strong style="color:{TEXT};">{esc(results.get("region","Global"))}</strong> · Topic: <strong style="color:{TEXT};">{esc(results.get("topic","All"))}</strong> · Source mode: <strong style="color:{TEXT};">{esc(results.get("source","cached"))}</strong></div></div>',
        unsafe_allow_html=True,
    )
    for item in results.get("assessments", []):
        label = item.get("label", "Uncertain")
        badge, color, glow = verdict_meta(label)
        st.markdown(
            f'<div class="feed-card" style="border-color:{glow}; box-shadow:0 0 0 1px {glow}, 0 18px 40px rgba(2,8,23,.44);"><div class="kicker">{esc(item.get("region","Global"))} · {esc(item.get("category","General"))}</div><div class="claim-text">{esc(item.get("headline",""))}</div><div class="verdict-pill" style="color:{color}; background:{glow};">{badge}</div><div class="muted" style="margin-top:.75rem;font-family:IBM Plex Mono, monospace;">Published: {esc(format_live_timestamp(item.get("published_at","")))} · Source: {esc(item.get("source","Unknown source"))}</div><div class="muted" style="margin-top:.35rem;font-family:IBM Plex Mono, monospace;">Signal type: {esc(item.get("count_label","No Clear Source"))} · Authority: {esc(item.get("authority_label","Moderate Authority"))}</div><div class="muted" style="margin-top:.85rem;">{esc(item.get("reasoning",""))}</div></div>',
            unsafe_allow_html=True,
        )
        confidence_bar(label, item.get("confidence", 0))
        if item.get("url"):
            st.markdown(f"[Open source article]({item.get('url')})")


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
            with st.form("claim_form"):
                user_input = st.text_area(
                    "Claim input",
                    placeholder="Paste or type claims here...",
                    height=150,
                    key="claim_input",
                )
                submitted = st.form_submit_button("Analyze Claim", use_container_width=True)
            st.session_state["fact_input"] = user_input
            st.caption("Tip: Paste multiple claims separated by periods for batch analysis")
            c1, c2 = st.columns([1, 1])
            with c1:
                sample = st.button("Load Sample", use_container_width=True)
            if sample:
                st.session_state["claim_input"] = SAMPLE_CLAIMS
                st.session_state["fact_input"] = SAMPLE_CLAIMS
                st.rerun()
            st.markdown('<div class="divider"></div><div class="kicker">Extracted Claims</div>', unsafe_allow_html=True)
            claims = extract_claims(st.session_state.get("claim_input", st.session_state.get("fact_input", "")), use_llm=False, api_key=None).get("claims", [])
            if claims:
                for claim in claims[:6]:
                    st.markdown(f'<span class="claim-chip">{esc(claim)}</span>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="hint-box" style="margin-top:.75rem;">Try a sample claim to generate extracted-claim chips.</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        if submitted:
            with st.spinner("Extracting claims, matching evidence, and generating verdicts..."):
                results = run_fact_check(user_input or SAMPLE_SINGLE, dataset=records, use_llm=False, top_k=3)
                st.session_state["fact_results"] = results
                st.session_state["fact_history"] = results.get("results", [])
        with right:
            render_fact_results(st.session_state.get("fact_results"))

    with live_tab:
        st.markdown('<h2 class="section-title">Live Radar</h2><div class="muted">A structured intelligence feed with region controls, verdict glow, and confidence signals.</div>', unsafe_allow_html=True)
        c1, c2, c3, _ = st.columns([1.15, 1.15, 1.05, 1.75])
        with c1:
            regions = get_available_regions()
            idx = regions.index(st.session_state.get("region", "Global")) if st.session_state.get("region", "Global") in regions else 0
            st.session_state["region"] = st.selectbox("Region", regions, index=idx)
        with c2:
            topics = get_available_topics()
            topic_idx = topics.index(st.session_state.get("topic", "All")) if st.session_state.get("topic", "All") in topics else 0
            st.session_state["topic"] = st.selectbox("Topic", topics, index=topic_idx)
        with c3:
            refresh = st.button("Refresh Radar", use_container_width=True)
        current_live_signature = (st.session_state.get("region", "Global"), st.session_state.get("topic", "All"))
        if refresh or st.session_state.get("live_results") is None or st.session_state.get("live_filter_signature") != current_live_signature:
            with st.spinner("Refreshing local radar feed..."):
                live = run_live_updates(
                    region=st.session_state.get("region", "Global"),
                    topic=st.session_state.get("topic", "All"),
                    dataset=records,
                    news_api_key=os.getenv("NEWS_API_KEY"),
                    max_items=6,
                )
                st.session_state["live_results"] = live
                st.session_state["live_history"] = live.get("assessments", [])
                st.session_state["live_filter_signature"] = current_live_signature
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


