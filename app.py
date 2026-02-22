"""
app.py — Streamlit dashboard for the Mobile OS Memory Management System.

Launch with:
    streamlit run app.py

The dashboard auto-detects whether a real Android device is attached via ADB.
If not, it seamlessly switches to demo mode with realistic simulated data.
"""

import sys
import os

# ── Ensure project root is on sys.path so `config` / `modules` resolve ──
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import threading
import time
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

from config import REFRESH_INTERVAL_MS, KILL_BLOCKLIST, CACHE_TTL_SECONDS, ADB_TIMEOUT_SECONDS
from modules.adb_utils import is_device_connected, get_device_info, force_stop_app, force_stop_batch
from modules.memory_reader import MemoryInfo, get_system_memory
from modules.process_reader import ProcessInfo, get_running_processes
from modules.smart_manager import (
    calculate_usage_percent,
    get_system_recommendation,
    get_kill_candidates,
    estimate_freed_mb,
    android_vs_model_comparison,
)
from modules.demo_data import get_fake_memory, get_fake_processes, get_fake_device_info


# ═══════════════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Mobile OS Memory Manager",
    page_icon="📱",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════════════════
#  SESSION STATE INIT
# ═══════════════════════════════════════════════════════════════════════

if "memory_history" not in st.session_state:
    st.session_state.memory_history = []
if "last_killed" not in st.session_state:
    st.session_state.last_killed = None
if "kill_log" not in st.session_state:
    st.session_state.kill_log = []          # list of {time, package, pss_mb, status}
if "auto_refresh_on" not in st.session_state:
    st.session_state.auto_refresh_on = False
if "app_mode" not in st.session_state:
    st.session_state.app_mode = None        # None = not chosen, "demo", "live"
if "device_connected" not in st.session_state:
    st.session_state.device_connected = False

# Only auto-refresh when user explicitly enables it
if st.session_state.auto_refresh_on:
    st_autorefresh(interval=REFRESH_INTERVAL_MS, key="auto_refresh")


# ═══════════════════════════════════════════════════════════════════════
#  GLASSMORPHISM THEME — Custom CSS injection
# ═══════════════════════════════════════════════════════════════════════

_GLASSMORPHISM_CSS = """
<style>
/* ── Import modern font ─────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── Root variables ─────────────────────────────────────────────── */
:root {
    --glass-bg: rgba(255, 255, 255, 0.035);
    --glass-border: rgba(255, 255, 255, 0.07);
    --glass-blur: 24px;
    --glass-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    --accent-blue: #00d4ff;
    --accent-cyan: #00f0ff;
    --accent-purple: #a855f7;
    --accent-pink: #ec4899;
    --accent-green: #10b981;
    --accent-red: #ef4444;
    --text-primary: #eef1f5;
    --text-secondary: rgba(255, 255, 255, 0.50);
    --radius: 14px;
}

/* ── Kill ALL top padding / margins from Streamlit chrome ───────── */
.stApp > header { display: none !important; }
header[data-testid="stHeader"] { display: none !important; }
#MainMenu, footer, [data-testid="stDecoration"] { display: none !important; }

[data-testid="stAppViewBlockContainer"],
[data-testid="stMainBlockContainer"],
.block-container {
    padding-top: 1rem !important;
    max-width: 100% !important;
}

[data-testid="stSidebar"] > div:first-child {
    padding-top: 1.2rem !important;
}

/* ── Global background ──────────────────────────────────────────── */
.stApp, [data-testid="stAppViewContainer"] {
    background: linear-gradient(160deg, #060714 0%, #0b1120 30%, #140e2e 55%, #0b1120 80%, #060714 100%) !important;
    background-attachment: fixed !important;
    font-family: 'Inter', sans-serif !important;
    color: var(--text-primary) !important;
}

/* Subtle ambient glow */
.stApp::before {
    content: '';
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background:
        radial-gradient(ellipse 50% 40% at 15% 15%, rgba(0,212,255,0.045) 0%, transparent 100%),
        radial-gradient(ellipse 50% 40% at 85% 75%, rgba(168,85,247,0.04) 0%, transparent 100%);
    pointer-events: none;
    z-index: 0;
}

[data-testid="stMainBlockContainer"] {
    background: transparent !important;
}

/* ── Sidebar ────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(8,15,28,0.97) 0%, rgba(6,7,20,0.99) 100%) !important;
    border-right: 1px solid rgba(255,255,255,0.05) !important;
    backdrop-filter: blur(30px) !important;
    -webkit-backdrop-filter: blur(30px) !important;
}

[data-testid="stSidebar"] [data-testid="stMarkdown"] {
    color: var(--text-primary) !important;
}

[data-testid="stSidebar"] .stTitle, [data-testid="stSidebar"] h1 {
    background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple)) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    background-clip: text !important;
    font-weight: 700 !important;
    font-size: 1.3rem !important;
}

/* ── Main title ─────────────────────────────────────────────────── */
[data-testid="stMainBlockContainer"] h1 {
    background: linear-gradient(135deg, var(--accent-cyan) 0%, var(--accent-blue) 40%, var(--accent-purple) 100%) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    background-clip: text !important;
    font-weight: 800 !important;
    font-size: 1.75rem !important;
    letter-spacing: -0.6px !important;
    padding-bottom: 0 !important;
    margin-bottom: 0 !important;
    line-height: 1.25 !important;
}

/* Sub-headers */
h2, h3, [data-testid="stSubheader"] {
    color: rgba(255, 255, 255, 0.88) !important;
    font-weight: 600 !important;
    letter-spacing: -0.3px !important;
    font-size: 1.1rem !important;
    margin-top: 0.6rem !important;
}

/* Captions — tighter */
[data-testid="stCaptionContainer"], .stCaption {
    color: var(--text-secondary) !important;
    margin-top: -2px !important;
    margin-bottom: 4px !important;
}

/* ── Glass card for metric containers ───────────────────────────── */
[data-testid="stMetric"] {
    background: var(--glass-bg) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: var(--radius) !important;
    padding: 16px 20px !important;
    backdrop-filter: blur(var(--glass-blur)) !important;
    -webkit-backdrop-filter: blur(var(--glass-blur)) !important;
    box-shadow: var(--glass-shadow), inset 0 1px 0 rgba(255,255,255,0.04) !important;
    transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease !important;
}

[data-testid="stMetric"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 12px 40px rgba(0,212,255,0.12), inset 0 1px 0 rgba(255,255,255,0.06) !important;
    border-color: rgba(0,212,255,0.18) !important;
}

[data-testid="stMetric"] label {
    color: var(--text-secondary) !important;
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 1px !important;
}

[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: var(--accent-cyan) !important;
    font-weight: 700 !important;
    font-size: 1.55rem !important;
}

[data-testid="stMetric"] [data-testid="stMetricDelta"] {
    color: var(--accent-green) !important;
}

/* ── Tabs ───────────────────────────────────────────────────────── */
[data-testid="stTabs"] {
    background: transparent !important;
    margin-top: 0.25rem !important;
}

/* Equal-width tabs */
[data-testid="stTabs"] [role="tablist"] {
    display: flex !important;
    width: 100% !important;
}

[data-testid="stTabs"] [role="tablist"] > * {
    flex: 1 1 0 !important;
    min-width: 0 !important;
}

button[data-baseweb="tab"] {
    background: transparent !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
    color: var(--text-secondary) !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.84rem !important;
    padding: 10px 8px !important;
    transition: all 0.2s ease !important;
    width: 100% !important;
    text-align: center !important;
    justify-content: center !important;
}

button[data-baseweb="tab"]:hover {
    background: rgba(0,212,255,0.04) !important;
    color: var(--accent-cyan) !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    background: transparent !important;
    color: var(--accent-cyan) !important;
    border-bottom: none !important;
    font-weight: 600 !important;
}

[data-baseweb="tab-highlight"] {
    background-color: var(--accent-cyan) !important;
}

[data-baseweb="tab-border"] {
    background-color: rgba(255,255,255,0.05) !important;
}

/* ── Buttons ────────────────────────────────────────────────────── */
.stButton > button {
    background: rgba(0,212,255,0.08) !important;
    border: 1px solid rgba(0,212,255,0.18) !important;
    border-radius: 10px !important;
    color: var(--accent-cyan) !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
    padding: 8px 20px !important;
    transition: all 0.2s ease !important;
    box-shadow: none !important;
}

.stButton > button:hover {
    background: rgba(0,212,255,0.15) !important;
    border-color: rgba(0,212,255,0.35) !important;
    box-shadow: 0 4px 20px rgba(0,212,255,0.12) !important;
    transform: translateY(-1px) !important;
    color: #ffffff !important;
}

.stButton > button:active {
    transform: translateY(0px) !important;
}

/* Primary buttons */
.stButton > button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"] {
    background: linear-gradient(135deg, var(--accent-blue) 0%, var(--accent-purple) 100%) !important;
    color: #ffffff !important;
    border: none !important;
    box-shadow: 0 4px 20px rgba(0,212,255,0.25) !important;
}

.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="stBaseButton-primary"]:hover {
    box-shadow: 0 6px 30px rgba(0,212,255,0.4) !important;
}

/* ── Progress bar ───────────────────────────────────────────────── */
[data-testid="stProgress"] > div > div {
    background: rgba(255,255,255,0.05) !important;
    border-radius: 8px !important;
    overflow: hidden !important;
}

[data-testid="stProgress"] [role="progressbar"] {
    background: linear-gradient(90deg, var(--accent-blue), var(--accent-cyan), var(--accent-purple)) !important;
    border-radius: 8px !important;
    box-shadow: 0 0 12px rgba(0,212,255,0.3) !important;
}

/* ── DataFrames / Tables ────────────────────────────────────────── */
[data-testid="stDataFrame"], [data-testid="stTable"] {
    background: var(--glass-bg) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: var(--radius) !important;
    backdrop-filter: blur(var(--glass-blur)) !important;
    -webkit-backdrop-filter: blur(var(--glass-blur)) !important;
    box-shadow: var(--glass-shadow) !important;
    overflow: hidden !important;
}

/* ── Alerts ─────────────────────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: 10px !important;
    backdrop-filter: blur(10px) !important;
    -webkit-backdrop-filter: blur(10px) !important;
    border: 1px solid var(--glass-border) !important;
    font-size: 0.88rem !important;
}

div[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) {
    background: rgba(16,185,129,0.08) !important;
    border-color: rgba(16,185,129,0.2) !important;
}

div[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) {
    background: rgba(245,158,11,0.08) !important;
    border-color: rgba(245,158,11,0.2) !important;
}

div[data-testid="stAlert"]:has([data-testid="stAlertContentError"]) {
    background: rgba(239,68,68,0.08) !important;
    border-color: rgba(239,68,68,0.2) !important;
}

div[data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]) {
    background: rgba(0,212,255,0.06) !important;
    border-color: rgba(0,212,255,0.15) !important;
}

/* ── Dividers ───────────────────────────────────────────────────── */
[data-testid="stDivider"], hr {
    border-color: rgba(255,255,255,0.05) !important;
    opacity: 0.6 !important;
    margin-top: 0.5rem !important;
    margin-bottom: 0.5rem !important;
}

/* ── Toggle / Switch ────────────────────────────────────────────── */
[data-testid="stToggle"] label span {
    color: var(--text-secondary) !important;
    font-size: 0.85rem !important;
}

/* ── Expanders ──────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: var(--glass-bg) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: var(--radius) !important;
    backdrop-filter: blur(var(--glass-blur)) !important;
    -webkit-backdrop-filter: blur(var(--glass-blur)) !important;
}

/* ── Plotly chart containers ────────────────────────────────────── */
[data-testid="stPlotlyChart"] {
    background: var(--glass-bg) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: var(--radius) !important;
    backdrop-filter: blur(var(--glass-blur)) !important;
    -webkit-backdrop-filter: blur(var(--glass-blur)) !important;
    box-shadow: var(--glass-shadow) !important;
    padding: 6px !important;
}

/* ── Columns gap ────────────────────────────────────────────────── */
[data-testid="stHorizontalBlock"] {
    gap: 0.5rem !important;
}

/* ── Scrollbar ──────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(0,212,255,0.15); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(0,212,255,0.3); }

::selection { background: rgba(0,212,255,0.25); color: #fff; }

/* ── Links ──────────────────────────────────────────────────────── */
a { color: var(--accent-cyan) !important; }

/* ── Toast ──────────────────────────────────────────────────────── */
[data-testid="stToast"] {
    background: rgba(8,15,28,0.92) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: 10px !important;
    backdrop-filter: blur(20px) !important;
    color: var(--text-primary) !important;
}

/* ── Multiselect/select ─────────────────────────────────────────── */
[data-baseweb="select"], [data-baseweb="input"] {
    border-radius: 10px !important;
}

[data-baseweb="popover"] {
    border-radius: 10px !important;
    border: 1px solid var(--glass-border) !important;
    background: rgba(8,15,28,0.95) !important;
    backdrop-filter: blur(20px) !important;
}
</style>
"""

st.markdown(_GLASSMORPHISM_CSS, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════
#  DATA COLLECTION — Non-blocking background fetcher
# ═══════════════════════════════════════════════════════════════════════

# Module-level thread-safe cache so ADB calls never block the UI render.
_bg_lock = threading.Lock()
_bg_live_data = None        # (memory, processes, device_info) or None
_bg_live_time: float = 0.0  # epoch when last fetch completed
_bg_thread = None            # reference to the running fetcher thread


def _bg_fetch_live():
    """Worker: fetch live data in background, store in module-level cache."""
    global _bg_live_data, _bg_live_time
    try:
        memory = get_system_memory()
        processes = get_running_processes()
        device_info = get_device_info()
        with _bg_lock:
            _bg_live_data = (memory, processes, device_info)
            _bg_live_time = time.time()
    except Exception:
        pass  # keep serving last-known-good data


def collect_live_data(force: bool = False):
    """Return live device data without blocking the UI.

    • If fresh cached data exists (< CACHE_TTL_SECONDS old), return it
      instantly and kick off a background refresh for next cycle.
    • If no data exists yet (first load), block briefly until the
      background thread delivers.
    • *force=True* resets the cache age so the next call triggers a fetch.
    """
    global _bg_thread

    with _bg_lock:
        data = _bg_live_data
        age = time.time() - _bg_live_time

    # Kick off a background fetch if data is stale or missing
    need_fetch = data is None or age > CACHE_TTL_SECONDS or force
    if need_fetch and (_bg_thread is None or not _bg_thread.is_alive()):
        _bg_thread = threading.Thread(target=_bg_fetch_live, daemon=True)
        _bg_thread.start()

    # First-ever load: we must wait for *some* data to arrive
    if data is None and _bg_thread is not None:
        _bg_thread.join(timeout=ADB_TIMEOUT_SECONDS + 5)
        with _bg_lock:
            data = _bg_live_data
        if data is None:
            raise RuntimeError("Unable to fetch data from device")

    return data


def clear_live_cache():
    """Invalidate the background cache so the next call triggers a fresh fetch."""
    global _bg_live_data, _bg_live_time
    with _bg_lock:
        _bg_live_time = 0.0  # mark as stale; keep old data for display


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def collect_demo_data():
    """Return realistic simulated data (cached to prevent flicker on rerun)."""
    return get_fake_memory(), get_fake_processes(), get_fake_device_info()


# ═══════════════════════════════════════════════════════════════════════
#  MODE SELECTION SCREEN
# ═══════════════════════════════════════════════════════════════════════

def _render_mode_selection():
    """Show the mode selection landing page."""
    st.markdown(
        '<div style="text-align:center;padding:40px 0 10px;">'
        '<span style="font-size:3.5rem;">📱</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<h1 style="text-align:center;background:linear-gradient(135deg,#00d4ff,#a855f7);'
        '-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
        'font-weight:700;margin-bottom:4px;">'
        'Mobile OS Memory Management System</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="text-align:center;color:rgba(255,255,255,0.55);font-size:1rem;margin-bottom:40px;">'
        'Real-time adaptive memory monitoring, analysis &amp; optimization</p>',
        unsafe_allow_html=True,
    )

    col_left, col_demo, col_gap, col_live, col_right = st.columns([1, 2, 0.5, 2, 1])

    with col_demo:
        st.markdown(
            '<div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);'
            'border-radius:16px;padding:30px 24px;text-align:center;'
            'backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);">'
            '<div style="font-size:2.5rem;margin-bottom:12px;">🖥️</div>'
            '<div style="font-size:1.15rem;font-weight:700;color:#f0f0f0;margin-bottom:8px;">Demo Mode</div>'
            '<div style="font-size:0.85rem;color:rgba(255,255,255,0.55);line-height:1.5;margin-bottom:20px;">'
            'Explore the dashboard with realistic simulated data.<br/>'
            'No Android device required.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        if st.button("🖥️  Start Demo Mode", key="btn_demo", use_container_width=True):
            st.session_state.app_mode = "demo"
            st.rerun()

    with col_live:
        st.markdown(
            '<div style="background:rgba(0,212,255,0.06);border:1px solid rgba(0,212,255,0.2);'
            'border-radius:16px;padding:30px 24px;text-align:center;'
            'backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);">'
            '<div style="font-size:2.5rem;margin-bottom:12px;">📲</div>'
            '<div style="font-size:1.15rem;font-weight:700;color:#00d4ff;margin-bottom:8px;">Live Mode</div>'
            '<div style="font-size:0.85rem;color:rgba(255,255,255,0.55);line-height:1.5;margin-bottom:20px;">'
            'Connect a real Android device via USB.<br/>'
            'Monitor &amp; manage memory in real-time.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        if st.button("📲  Start Live Mode", key="btn_live", use_container_width=True):
            st.session_state.app_mode = "live"
            st.session_state.device_connected = False
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════
#  LIVE MODE — CONNECTION WIZARD
# ═══════════════════════════════════════════════════════════════════════

def _render_connection_wizard():
    """Guide the user through connecting their Android device."""
    st.markdown(
        '<h1 style="text-align:center;background:linear-gradient(135deg,#00d4ff,#a855f7);'
        '-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
        'font-weight:700;">'
        '📲 Live Mode — Device Setup</h1>',
        unsafe_allow_html=True,
    )
    st.caption("Follow the steps below to connect your Android device")
    st.divider()

    # Check current device status
    try:
        connected = is_device_connected()
    except Exception:
        connected = False

    if connected:
        try:
            dev_info = get_device_info()
            model = dev_info.get("model", "Android Device")
            android_ver = dev_info.get("android_version", "")
        except Exception:
            model = "Android Device"
            android_ver = ""
        st.session_state.device_connected = True
    else:
        model = None
        android_ver = None

    # Step indicators
    def _wizard_step(number, title, description, status, result_text=""):
        """Render a connection wizard step. status: 'done' | 'active' | 'pending'"""
        if status == "done":
            icon = "✅"
            border_col = "rgba(16,185,129,0.5)"
            bg = "rgba(16,185,129,0.06)"
            label = "DONE"
            label_col = "#10b981"
        elif status == "active":
            icon = "🔵"
            border_col = "rgba(0,212,255,0.5)"
            bg = "rgba(0,212,255,0.06)"
            label = "IN PROGRESS"
            label_col = "#00d4ff"
        else:
            icon = "⏳"
            border_col = "rgba(255,255,255,0.1)"
            bg = "rgba(255,255,255,0.02)"
            label = "PENDING"
            label_col = "rgba(255,255,255,0.35)"

        result_html = ""
        if result_text:
            result_html = (
                f'<div style="margin-top:8px;padding:8px 12px;'
                f'background:rgba(16,185,129,0.10);border-radius:8px;'
                f'font-weight:600;font-size:0.9rem;color:#10b981;">'
                f'{result_text}</div>'
            )

        st.markdown(
            f'<div style="background:{bg};border:1px solid {border_col};'
            f'border-radius:14px;padding:18px 22px;margin-bottom:12px;'
            f'backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);'
            f'box-shadow:0 4px 20px rgba(0,0,0,0.25);">'
            f'<div style="display:flex;align-items:center;gap:12px;">'
            f'<span style="font-size:1.6rem;">{icon}</span>'
            f'<div style="flex:1;">'
            f'<span style="font-weight:700;font-size:1.05rem;color:#f0f0f0;">'
            f'Step {number}: {title}</span><br/>'
            f'<span style="font-size:0.85rem;color:rgba(255,255,255,0.55);">'
            f'{description}</span></div>'
            f'<span style="font-size:0.72rem;font-weight:600;padding:3px 10px;'
            f'border-radius:20px;border:1px solid {label_col};color:{label_col};">'
            f'{label}</span></div>'
            f'{result_html}</div>',
            unsafe_allow_html=True,
        )

    _, wizard_col, _ = st.columns([1, 3, 1])
    with wizard_col:
        if connected:
            # All steps done
            _wizard_step(1, "Connect Phone via USB",
                         "Plug your Android device into this computer using a USB cable.",
                         "done")
            _wizard_step(2, "Enable USB Debugging",
                         "Go to Settings → Developer Options → Enable USB Debugging. Tap \"Allow\" on the prompt.",
                         "done")
            _wizard_step(3, "Detecting Device…",
                         "Waiting for ADB to recognise the connected device.",
                         "done")

            ver_text = f" (Android {android_ver})" if android_ver else ""
            _wizard_step(4, "Device Detected",
                         "Your device has been successfully identified.",
                         "done",
                         f"✅ {model}{ver_text} detected")

            st.markdown("")
            if st.button("🚀  Continue to Dashboard", type="primary", use_container_width=True):
                st.rerun()
        else:
            # Steps 1 & 2 are instructions, step 3 is active (detecting)
            _wizard_step(1, "Connect Phone via USB",
                         "Plug your Android device into this computer using a USB cable.",
                         "active")
            _wizard_step(2, "Enable USB Debugging",
                         "Go to Settings → Developer Options → Enable USB Debugging. Tap \"Allow\" on the prompt.",
                         "pending")
            _wizard_step(3, "Detecting Device…",
                         "Waiting for ADB to recognise the connected device.",
                         "pending")
            _wizard_step(4, "Device Detected",
                         "Your device will appear here once connected.",
                         "pending")

            st.markdown("")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🔄  Retry Detection", use_container_width=True):
                    st.rerun()
            with c2:
                if st.button("← Back to Mode Selection", use_container_width=True):
                    st.session_state.app_mode = None
                    st.session_state.device_connected = False
                    st.rerun()

            st.markdown("")
            st.info("💡 **Tip:** Make sure ADB is installed and your phone shows a USB debugging authorisation dialog. Tap **Allow** on the phone, then click **Retry Detection**.")


# ═══════════════════════════════════════════════════════════════════════
#  MODE ROUTER — Decide what to show
# ═══════════════════════════════════════════════════════════════════════

# If no mode selected yet, show the selection screen and stop
if st.session_state.app_mode is None:
    _render_mode_selection()
    st.stop()

# Guard against invalid app_mode values
if st.session_state.app_mode not in ("demo", "live"):
    st.session_state.app_mode = None
    st.rerun()

# If live mode but device not yet connected, show the wizard and stop
if st.session_state.app_mode == "live" and not st.session_state.device_connected:
    _render_connection_wizard()
    st.stop()

# ── From here on, we're in an active dashboard session ───────────────

is_live = st.session_state.app_mode == "live"

if is_live:
    try:
        memory, processes, device_info = collect_live_data()
    except Exception:
        # Device was disconnected — bounce back to wizard
        st.session_state.device_connected = False
        st.warning("Device connection lost. Returning to setup…")
        time.sleep(1)
        st.rerun()
        st.stop()
    # Pre-trigger the *next* background fetch so it's ready before the
    # next auto-refresh fires — the UI will never wait.
    collect_live_data()
else:
    memory, processes, device_info = collect_demo_data()

# Record history
usage_pct = calculate_usage_percent(memory)
st.session_state.memory_history.append({
    "time": datetime.now().strftime("%H:%M:%S"),
    "used_mb": round(memory.used_kb / 1024, 1),
    "free_mb": round(memory.free_kb / 1024, 1),
    "usage_pct": round(usage_pct, 1),
})
# Keep last 120 data points (~10 min at 5 s interval)
st.session_state.memory_history = st.session_state.memory_history[-120:]


# ═══════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.title("📱 Device Info")

    if is_live:
        st.success("🟢  LIVE — Device Connected")
    else:
        st.info("🖥️  DEMO MODE")

    st.markdown(f"**Model:** {device_info.get('model', 'N/A')}")
    st.markdown(f"**Android:** {device_info.get('android_version', 'N/A')}")
    st.divider()

    if st.button("🔄 Refresh Now"):
        if is_live:
            clear_live_cache()
        else:
            collect_demo_data.clear()
        st.rerun()

    st.toggle(
        "Auto-Refresh (15s)",
        key="auto_refresh_on",
        help="Automatically refresh data every 15 seconds",
    )

    st.divider()

    if st.button("🔀 Switch Mode"):
        st.session_state.app_mode = None
        st.session_state.device_connected = False
        st.session_state.memory_history = []
        if is_live:
            clear_live_cache()
        st.rerun()

    st.divider()
    st.caption("Built for OS Course Project")
    st.caption("Real-time Android Memory Manager")

    if st.session_state.last_killed:
        st.divider()
        st.info(f"Last stopped: {st.session_state.last_killed}")


# ═══════════════════════════════════════════════════════════════════════
#  HEADER
# ═══════════════════════════════════════════════════════════════════════

st.title("🧠 Mobile OS Memory Management System")
_mode_label = "🟢 Live" if is_live else "🖥️ Demo"
st.caption(f"Real-time adaptive memory monitoring, analysis & optimization — {_mode_label}")

severity, rec_title, rec_detail = get_system_recommendation(usage_pct)


# ═══════════════════════════════════════════════════════════════════════
#  TABS
# ═══════════════════════════════════════════════════════════════════════

tab_overview, tab_processes, tab_history, tab_smart, tab_compare, tab_algo = st.tabs([
    "📊 Memory Overview",
    "📋 Running Processes",
    "📈 History",
    "🧠 Smart Recommendations",
    "⚔️ Android vs Our Model",
    "🔬 Algorithm Execution",
])

# ─── Tab 1: Memory Overview ──────────────────────────────────────────

with tab_overview:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total RAM", f"{memory.total_kb / 1024:.0f} MB")
    col2.metric("Used RAM",  f"{memory.used_kb / 1024:.0f} MB")
    col3.metric("Free RAM",  f"{memory.free_kb / 1024:.0f} MB")
    col4.metric("Usage",     f"{usage_pct:.1f} %")

    st.divider()

    g_col, p_col = st.columns([1, 1])

    with g_col:
        # Plotly gauge
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=round(usage_pct, 1),
            number={"suffix": " %", "font": {"size": 48, "color": "#00d4ff"}},
            title={"text": "RAM Usage", "font": {"size": 20, "color": "rgba(255,255,255,0.8)"}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1,
                         "tickcolor": "rgba(255,255,255,0.3)",
                         "tickfont": {"color": "rgba(255,255,255,0.6)"}},
                "bgcolor": "rgba(255,255,255,0.03)",
                "bar": {"color": "#00d4ff"},
                "steps": [
                    {"range": [0, 60],  "color": "rgba(16,185,129,0.15)"},
                    {"range": [60, 80], "color": "rgba(245,158,11,0.15)"},
                    {"range": [80, 100],"color": "rgba(239,68,68,0.15)"},
                ],
                "threshold": {
                    "line": {"color": "#ef4444", "width": 3},
                    "thickness": 0.8,
                    "value": 80,
                },
            },
        ))
        fig.update_layout(
            height=320, margin=dict(t=60, b=20, l=40, r=40),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="rgba(255,255,255,0.8)"),
        )
        st.plotly_chart(fig, use_container_width=True)

    with p_col:
        st.subheader("System Status")
        st.progress(min(int(usage_pct), 100), text=f"Memory: {usage_pct:.1f} %")

        if severity == "critical":
            st.error(f"🔴 {rec_title}")
        elif severity == "warning":
            st.warning(f"🟡 {rec_title}")
        else:
            st.success(f"🟢 {rec_title}")

        st.info(rec_detail)

        st.markdown("**Memory Breakdown**")
        breakdown = pd.DataFrame({
            "Category": ["Used", "Free", "Lost"],
            "MB": [
                round(memory.used_kb / 1024, 1),
                round(memory.free_kb / 1024, 1),
                round(memory.lost_kb / 1024, 1),
            ],
        })
        st.dataframe(breakdown, use_container_width=True, hide_index=True)


# ─── Tab 2: Running Processes ────────────────────────────────────────

with tab_processes:
    st.subheader("Running Processes")

    if processes:
        rows = []
        for p in processes:
            rows.append({
                "Package": p.package_name,
                "PSS (MB)": p.pss_mb,
                "Priority": p.oom_label,
                "Kill Score": p.kill_score,
                "PID": p.pid,
            })
        df = pd.DataFrame(rows)
        st.dataframe(
            df.style.background_gradient(subset=["PSS (MB)"], cmap="OrRd"),
            use_container_width=True,
            hide_index=True,
            height=420,
        )

        # Bar chart — top 10 by PSS
        st.subheader("Top 10 Memory Consumers")
        top10 = df.nlargest(10, "PSS (MB)")
        fig_bar = go.Figure(go.Bar(
            x=top10["PSS (MB)"],
            y=top10["Package"],
            orientation="h",
            marker=dict(
                color=top10["PSS (MB)"],
                colorscale=[[0, "#00d4ff"], [0.5, "#a855f7"], [1, "#ec4899"]],
                line=dict(width=0),
            ),
        ))
        fig_bar.update_layout(
            yaxis=dict(autorange="reversed", tickfont=dict(color="rgba(255,255,255,0.7)")),
            xaxis=dict(title="PSS (MB)", gridcolor="rgba(255,255,255,0.06)",
                       tickfont=dict(color="rgba(255,255,255,0.7)"),
                       title_font=dict(color="rgba(255,255,255,0.7)")),
            height=380,
            margin=dict(l=10, r=10, t=30, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="rgba(255,255,255,0.8)"),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        # Individual kill buttons
        st.subheader("Force Stop an App")
        if not is_live:
            st.info("Kill buttons are disabled in demo mode (no device connected).")
        else:
            killable = [p for p in processes
                        if p.kill_score >= 3
                        and p.package_name not in KILL_BLOCKLIST]
            if killable:
                for p in killable:
                    bcol1, bcol2, bcol3 = st.columns([3, 1, 1])
                    bcol1.write(f"**{p.package_name}** — {p.pss_mb} MB ({p.oom_label})")
                    if bcol3.button("🛑 Stop", key=f"kill_{p.package_name}"):
                        ok = force_stop_app(p.package_name)
                        if ok:
                            st.session_state.last_killed = p.package_name
                            st.toast(f"Stopped {p.package_name}")
                            clear_live_cache()
                            st.rerun()
                        else:
                            st.error(f"Failed to stop {p.package_name}")
            else:
                st.write("No killable background apps found.")
    else:
        st.write("No process data available.")


# ─── Tab 3: Memory History ───────────────────────────────────────────

with tab_history:
    history = st.session_state.memory_history
    if len(history) >= 2:
        df_hist = pd.DataFrame(history)
        _total_mb = round(memory.total_kb / 1024, 1)

        # 1 ─ RAM Usage — Absolute Scale (Total RAM ceiling, no fill)
        st.subheader("RAM Usage (MB) — Absolute Scale")
        fig_abs = go.Figure()
        fig_abs.add_trace(go.Scatter(
            x=df_hist["time"], y=df_hist["used_mb"],
            mode="lines+markers", name="Used RAM",
            line=dict(color="#ec4899", width=2),
            marker=dict(size=5, color="#ec4899"),
        ))
        fig_abs.add_trace(go.Scatter(
            x=df_hist["time"], y=df_hist["free_mb"],
            mode="lines+markers", name="Free RAM",
            line=dict(color="#10b981", width=2),
            marker=dict(size=5, color="#10b981"),
        ))
        fig_abs.add_hline(
            y=_total_mb,
            line_dash="dash", line_color="rgba(255,255,255,0.35)", line_width=1,
            annotation_text=f"Total RAM ({_total_mb:.0f} MB)",
            annotation_position="top left",
            annotation_font=dict(color="rgba(255,255,255,0.55)", size=11),
        )
        fig_abs.update_layout(
            xaxis=dict(title="Time", gridcolor="rgba(255,255,255,0.06)",
                       tickfont=dict(color="rgba(255,255,255,0.6)"),
                       title_font=dict(color="rgba(255,255,255,0.7)")),
            yaxis=dict(title="Memory (MB)", range=[0, _total_mb * 1.05],
                       gridcolor="rgba(255,255,255,0.06)",
                       tickfont=dict(color="rgba(255,255,255,0.6)"),
                       title_font=dict(color="rgba(255,255,255,0.7)")),
            height=380,
            legend=dict(orientation="h", yanchor="bottom", y=1.02,
                        font=dict(color="rgba(255,255,255,0.8)")),
            margin=dict(t=40, b=40),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="rgba(255,255,255,0.8)"),
        )
        st.plotly_chart(fig_abs, use_container_width=True)

        # 2 ─ Usage % Over Time
        st.subheader("Usage % Over Time")
        fig_pct = go.Figure(go.Scatter(
            x=df_hist["time"], y=df_hist["usage_pct"],
            mode="lines+markers", name="Usage %",
            fill="tozeroy",
            line=dict(color="#00d4ff", width=2),
            marker=dict(size=5, color="#00d4ff"),
            fillcolor="rgba(0,212,255,0.08)",
        ))
        fig_pct.update_layout(
            yaxis=dict(range=[0, 100], gridcolor="rgba(255,255,255,0.06)",
                       tickfont=dict(color="rgba(255,255,255,0.6)")),
            xaxis=dict(gridcolor="rgba(255,255,255,0.06)",
                       tickfont=dict(color="rgba(255,255,255,0.6)")),
            height=300,
            margin=dict(t=20, b=40),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="rgba(255,255,255,0.8)"),
        )
        st.plotly_chart(fig_pct, use_container_width=True)

    # ── Kill Log ──────────────────────────────────────────────────────
    st.divider()
    st.subheader("📋 Kill Log")

    kill_log = st.session_state.kill_log
    if kill_log:
        # Most recent kills first
        df_log = pd.DataFrame(reversed(kill_log))
        df_log = df_log.rename(columns={
            "time": "Time", "package": "Package",
            "pss_mb": "Memory Freed (MB)", "status": "Status",
        })

        # Summary metrics
        _log_killed = [e for e in kill_log if "✅" in e["status"]]
        _log_total_freed = round(sum(e["pss_mb"] for e in _log_killed), 1)
        lc1, lc2, lc3 = st.columns(3)
        lc1.metric("Total Kills", len(_log_killed))
        lc2.metric("Total Memory Freed", f"{_log_total_freed} MB")
        lc3.metric("Failed Kills", len(kill_log) - len(_log_killed))

        st.dataframe(df_log, width=900, height=min(400, 40 + 35 * len(df_log)))

        if st.button("🗑️ Clear Kill Log"):
            st.session_state.kill_log = []
            st.rerun()
    else:
        st.info("No kills recorded yet. Stop apps from the Smart Recommendations tab to see them here.")

    if len(history) < 2 and not kill_log:
        st.info("Collecting data… the chart will appear after a few refresh cycles.")


# ─── Tab 4: Smart Recommendations ───────────────────────────────────

with tab_smart:
    st.subheader("🧠 Smart Memory Optimisation")

    candidates = get_kill_candidates(processes, memory)
    freed_est = estimate_freed_mb(candidates)

    mc1, mc2 = st.columns(2)
    mc1.metric("Kill Candidates", len(candidates))
    mc2.metric("Estimated Freeable", f"{freed_est} MB")

    if candidates:
        cand_rows = [{
            "Package": c.package_name,
            "PSS (MB)": c.pss_mb,
            "Priority": c.oom_label,
            "Kill Score": c.kill_score,
        } for c in candidates]
        st.dataframe(
            pd.DataFrame(cand_rows).style.background_gradient(
                subset=["PSS (MB)"], cmap="OrRd",
            ),
            use_container_width=True,
            hide_index=True,
        )

        # ── Select & Kill Section ────────────────────────────────────
        st.subheader("Select Processes to Kill")

        if not is_live:
            st.info("Kill controls are disabled in demo mode (no device connected).")
        else:
            # Build options list: "package — PSS MB (Priority)"
            _cand_options = [
                f"{c.package_name} — {c.pss_mb} MB ({c.oom_label})"
                for c in candidates
            ]

            selected = st.multiselect(
                "Choose processes to force-stop:",
                options=_cand_options,
                default=[],
                help="Select one or more apps, then click the Kill button below.",
            )

            # Map selection back to ProcessInfo objects
            _selected_packages = set()
            for s in selected:
                pkg = s.split(" — ")[0]
                _selected_packages.add(pkg)

            _sel_candidates = [c for c in candidates if c.package_name in _selected_packages]
            _sel_freed = round(sum(c.pss_kb for c in _sel_candidates) / 1024, 1)

            sel_col1, sel_col2 = st.columns(2)
            sel_col1.metric("Selected", f"{len(_sel_candidates)} app(s)")
            sel_col2.metric("Est. Freeable", f"{_sel_freed} MB")

            if _sel_candidates:
                if st.button("🛑 Kill Selected Processes", key="kill_selected"):
                    _pkgs = [c.package_name for c in _sel_candidates]
                    _pss_map = {c.package_name: c.pss_mb for c in _sel_candidates}
                    results = force_stop_batch(_pkgs)
                    killed = [p for p, ok in results.items() if ok]
                    failed = [p for p, ok in results.items() if not ok]

                    # Log each kill
                    _now = datetime.now().strftime("%H:%M:%S")
                    for p in killed:
                        st.session_state.kill_log.append({
                            "time": _now, "package": p,
                            "pss_mb": _pss_map.get(p, 0), "status": "✅ Killed",
                        })
                    for p in failed:
                        st.session_state.kill_log.append({
                            "time": _now, "package": p,
                            "pss_mb": _pss_map.get(p, 0), "status": "❌ Failed",
                        })

                    if killed:
                        st.toast(f"Stopped {len(killed)} app(s), ~{_sel_freed} MB freed")
                    if failed:
                        st.warning(f"Failed to stop: {', '.join(failed)}")

                    st.session_state.last_killed = f"{len(killed)} selected app(s)"
                    clear_live_cache()
                    st.rerun()

        st.divider()

        # ── Per-app quick-kill buttons ─────────────────────────────────
        st.subheader("Quick Kill Individual Apps")
        if not is_live:
            st.info("Kill buttons are disabled in demo mode.")
        else:
            for c in candidates:
                col_name, col_mem, col_pri, col_btn = st.columns([3, 1.2, 1.2, 1])
                col_name.write(f"**{c.package_name}**")
                col_mem.write(f"{c.pss_mb} MB")
                col_pri.write(f"{c.oom_label}")
                if col_btn.button("🛑 Stop", key=f"smart_kill_{c.package_name}"):
                    ok = force_stop_app(c.package_name)
                    _now = datetime.now().strftime("%H:%M:%S")
                    st.session_state.kill_log.append({
                        "time": _now, "package": c.package_name,
                        "pss_mb": c.pss_mb,
                        "status": "✅ Killed" if ok else "❌ Failed",
                    })
                    if ok:
                        st.session_state.last_killed = c.package_name
                        st.toast(f"Stopped {c.package_name} (~{c.pss_mb} MB freed)")
                        clear_live_cache()
                        st.rerun()
                    else:
                        st.error(f"Failed to stop {c.package_name}")

        st.divider()

        # ── Pie chart of candidates ────────────────────────────────────
        fig_pie = go.Figure(go.Pie(
            labels=[c.package_name for c in candidates],
            values=[c.pss_kb for c in candidates],
            hole=0.45,
            marker=dict(
                colors=["#00d4ff", "#a855f7", "#ec4899", "#10b981",
                        "#f59e0b", "#6366f1", "#14b8a6", "#f43f5e",
                        "#8b5cf6", "#06b6d4", "#d946ef", "#22d3ee"],
                line=dict(color="rgba(0,0,0,0.3)", width=1),
            ),
            textfont=dict(color="rgba(255,255,255,0.85)"),
        ))
        fig_pie.update_layout(
            height=350, margin=dict(t=20, b=20),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="rgba(255,255,255,0.8)"),
            legend=dict(font=dict(color="rgba(255,255,255,0.7)")),
        )
        st.plotly_chart(fig_pie, use_container_width=True)

        # ── Optimize All button (improved) ─────────────────────────────
        if is_live:
            st.divider()
            if st.button("⚡ Optimize Now — Kill All Candidates", type="primary"):
                _all_pkgs = [c.package_name for c in candidates]
                _pss_map = {c.package_name: c.pss_mb for c in candidates}
                with st.spinner(f"Batch-killing {len(_all_pkgs)} apps..."):
                    results = force_stop_batch(_all_pkgs)
                killed = [p for p, ok in results.items() if ok]
                failed = [p for p, ok in results.items() if not ok]

                # Log every kill
                _now = datetime.now().strftime("%H:%M:%S")
                for p in killed:
                    st.session_state.kill_log.append({
                        "time": _now, "package": p,
                        "pss_mb": _pss_map.get(p, 0), "status": "✅ Killed",
                    })
                for p in failed:
                    st.session_state.kill_log.append({
                        "time": _now, "package": p,
                        "pss_mb": _pss_map.get(p, 0), "status": "❌ Failed",
                    })

                st.toast(f"Stopped {len(killed)}/{len(candidates)} apps, ~{freed_est} MB freed")
                if failed:
                    st.warning(f"Could not stop: {', '.join(failed)}")
                st.session_state.last_killed = f"{len(killed)}/{len(candidates)} apps"
                clear_live_cache()
                st.rerun()
        else:
            st.info("Optimize button is disabled in demo mode.")
    else:
        st.success("No low-priority apps to kill — memory is well-managed! ✅")


# ─── Tab 5: Android vs Our Model ────────────────────────────────────

with tab_compare:
    st.subheader("⚔️ Stock Android LMK  vs  Our Smart Model")
    st.caption("Innovation comparison for presentation / report")

    comparison = android_vs_model_comparison()
    st.dataframe(
        pd.DataFrame(comparison),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    st.markdown("""
### Key Innovations Claimed

1. **Real-time Mobile Memory Monitoring** — Live data from an actual Android device via ADB  
2. **Adaptive Allocation Model** — Threshold-aware recommendations (60 % / 80 %)  
3. **Priority-based Kill Engine** — Scores each process by OOM level & PSS; never kills critical system apps  
4. **Live Device Integration** — USB debugging → data extraction → dashboard in one pipeline  
5. **Predictive Optimisation** — Suggests and executes memory cleanup before the system degrades  
6. **Visual Analytics Dashboard** — Gauges, bar charts, history graphs, comparison tables  
""")


# ─── Tab 6: Smart Memory Management Algorithm Execution ─────────────

with tab_algo:

    # ── Section header ───────────────────────────────────────────────
    st.markdown(
        '<h2 style="text-align:center;background:linear-gradient(135deg,#00d4ff,#a855f7);'
        '-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
        'font-weight:700;letter-spacing:-0.5px;">'
        '⚙️&nbsp; Smart Memory Management — Algorithm Execution Engine</h2>',
        unsafe_allow_html=True,
    )
    st.caption("Live step-by-step execution of the adaptive memory management algorithm")
    st.divider()

    # ── Compute live algorithm values ────────────────────────────────
    _total_mb   = round(memory.total_kb / 1024, 1)
    _used_mb    = round(memory.used_kb / 1024, 1)
    _free_mb    = round(memory.free_kb / 1024, 1)
    _usage_pct  = round(usage_pct, 1)
    _n_procs    = len(processes)
    _candidates = get_kill_candidates(processes, memory)
    _freed      = estimate_freed_mb(_candidates)
    _sev, _title, _detail = get_system_recommendation(_usage_pct)

    # Determine which threshold band we fall into
    if _usage_pct >= 80:
        _band = "CRITICAL"
        _band_color = "#ef4444"
        _action = "Terminate low-priority apps immediately"
        _strategy = "Aggressive Reclamation"
    elif _usage_pct >= 60:
        _band = "WARNING"
        _band_color = "#f59e0b"
        _action = "Optimise background apps selectively"
        _strategy = "Selective Optimisation"
    else:
        _band = "HEALTHY"
        _band_color = "#10b981"
        _action = "No action required — memory is sufficient"
        _strategy = "Passive Monitoring"

    # ── Helper: render a single step card ────────────────────────────
    def _step_card(number: int, title: str, detail: str, status: str, result: str = ""):
        """Render one algorithm step as a glass card.
        status: 'done' | 'running' | 'pending'
        """
        if status == "done":
            icon = "✅"
            border_col = "rgba(16,185,129,0.5)"
            bg = "rgba(16,185,129,0.06)"
            label = "COMPLETED"
            label_col = "#10b981"
        elif status == "running":
            icon = "🔵"
            border_col = "rgba(0,212,255,0.5)"
            bg = "rgba(0,212,255,0.06)"
            label = "EXECUTING"
            label_col = "#00d4ff"
        else:
            icon = "⏳"
            border_col = "rgba(255,255,255,0.1)"
            bg = "rgba(255,255,255,0.02)"
            label = "PENDING"
            label_col = "rgba(255,255,255,0.35)"

        result_html = ""
        if result:
            result_html = (
                f'<div style="margin-top:6px;padding:6px 10px;'
                f'background:rgba(0,212,255,0.08);border-radius:8px;'
                f'font-family:monospace;font-size:0.82rem;color:#00f0ff;">'
                f'→ {result}</div>'
            )

        st.markdown(
            f'<div style="background:{bg};border:1px solid {border_col};'
            f'border-radius:14px;padding:16px 20px;margin-bottom:10px;'
            f'backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);'
            f'box-shadow:0 4px 20px rgba(0,0,0,0.25);">'
            f'<div style="display:flex;align-items:center;gap:10px;">'
            f'<span style="font-size:1.5rem;">{icon}</span>'
            f'<div style="flex:1;">'
            f'<span style="font-weight:700;font-size:1rem;color:#f0f0f0;">'
            f'Step {number}: {title}</span><br/>'
            f'<span style="font-size:0.85rem;color:rgba(255,255,255,0.55);">'
            f'{detail}</span></div>'
            f'<span style="font-size:0.72rem;font-weight:600;padding:3px 10px;'
            f'border-radius:20px;border:1px solid {label_col};color:{label_col};">'
            f'{label}</span></div>'
            f'{result_html}</div>',
            unsafe_allow_html=True,
        )

    # ── Algorithm Steps ──────────────────────────────────────────────
    st.subheader("1 · Algorithm Execution Flow")
    st.caption("Each step runs against live device data in real-time")

    _step_card(
        1, "Collect Memory Data",
        "Query the device via ADB — dumpsys meminfo & /proc/meminfo",
        "done",
        f"Total: {_total_mb} MB  |  Used: {_used_mb} MB  |  Free: {_free_mb} MB",
    )
    _step_card(
        2, "Calculate Memory Usage Percentage",
        "usage_pct = (used_kb / total_kb) × 100",
        "done",
        f"Usage = ({_used_mb} / {_total_mb}) × 100 = {_usage_pct} %",
    )
    _step_card(
        3, "Check Memory Thresholds",
        "Compare usage against CRITICAL (80%) and WARNING (60%) boundaries",
        "done",
        f"{_usage_pct}% falls in the {_band} zone ({_band_color})",
    )
    _step_card(
        4, "Analyse Running Processes",
        "Parse dumpsys activity processes for OOM codes and per-process PSS",
        "done",
        f"{_n_procs} processes detected across all priority levels",
    )
    _step_card(
        5, "Evaluate Process Priority & Kill Scores",
        "Map each OOM code → label + kill_score (0-5); filter by score ≥ 3 and blocklist",
        "done",
        f"{len(_candidates)} candidate(s) with kill_score ≥ 3 and not in blocklist",
    )
    _step_card(
        6, "Select Optimal Memory Allocation Strategy",
        "Choose action: Passive Monitoring / Selective Optimisation / Aggressive Reclamation",
        "done",
        f"Strategy: {_strategy} — {_action}",
    )
    _step_card(
        7, "Output Optimisation Decision",
        "Produce final recommendation and estimated recoverable memory",
        "done",
        f"{_title} → Est. freeable: {_freed} MB from {len(_candidates)} app(s)",
    )

    st.divider()

    # ── Live Execution Status ────────────────────────────────────────
    st.subheader("2 · Live Execution Status")

    status_cols = st.columns(7)
    _step_labels = [
        "Collect", "Calc %", "Threshold",
        "Processes", "Priority", "Strategy", "Output",
    ]
    for idx, (col, label) in enumerate(zip(status_cols, _step_labels), start=1):
        col.markdown(
            f'<div style="text-align:center;padding:10px 4px;'
            f'background:rgba(16,185,129,0.10);border:1px solid rgba(16,185,129,0.3);'
            f'border-radius:10px;">'
            f'<div style="font-size:1.3rem;">✅</div>'
            f'<div style="font-size:0.7rem;color:#10b981;font-weight:600;margin-top:2px;">'
            f'Step {idx}</div>'
            f'<div style="font-size:0.65rem;color:rgba(255,255,255,0.6);">{label}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.caption("All 7 steps completed successfully on this cycle.")
    st.divider()

    # ── Algorithm Logic Explanation ──────────────────────────────────
    st.subheader("3 · Algorithm Logic Explanation")

    _explanations = [
        ("Step 1 — Data Collection",
         "The system issues <code>adb shell dumpsys meminfo</code> to retrieve total, used, free, "
         "and lost RAM in kilobytes. If that command fails, it falls back to the lighter "
         "<code>/proc/meminfo</code> kernel interface."),
        ("Step 2 — Usage Calculation",
         "A simple ratio: <code>usage = used / total × 100</code>. This single percentage "
         "drives the entire decision tree that follows."),
        ("Step 3 — Threshold Evaluation",
         f"The percentage is tested against two configurable boundaries:<br/>"
         f"• <b>≥ 80 %</b> → Critical pressure (Red)<br/>"
         f"• <b>≥ 60 %</b> → Warning pressure (Yellow)<br/>"
         f"• <b>&lt; 60 %</b> → Healthy (Green)<br/>"
         f"Current result: <b>{_usage_pct}% → {_band}</b>"),
        ("Step 4 — Process Inventory",
         "Every running Android process is catalogued with its <b>PSS</b> "
         "(Proportional Set Size) — the most accurate per-app memory metric — "
         "and its <b>OOM adjustment code</b> (fore, vis, bak, cch …)."),
        ("Step 5 — Priority Scoring",
         "Each OOM code maps to a <b>kill_score</b> (0 = never kill, 5 = ideal target). "
         "Only processes with score ≥ 3 <i>and</i> not in the system blocklist become candidates."),
        ("Step 6 — Strategy Selection",
         f"Based on the threshold band, the engine selects a strategy:<br/>"
         f"• Healthy → <b>Passive Monitoring</b> (do nothing)<br/>"
         f"• Warning → <b>Selective Optimisation</b> (suggest cleanup)<br/>"
         f"• Critical → <b>Aggressive Reclamation</b> (recommend immediate kills)<br/>"
         f"Selected: <b>{_strategy}</b>"),
        ("Step 7 — Final Output",
         f"The engine outputs: severity=<b>{_sev}</b>, "
         f"candidates=<b>{len(_candidates)}</b>, "
         f"estimated freed=<b>{_freed} MB</b>. "
         "The dashboard renders this as actionable cards, charts, and kill buttons."),
    ]

    for title, html_body in _explanations:
        st.markdown(
            f'<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);'
            f'border-radius:12px;padding:14px 18px;margin-bottom:8px;'
            f'backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);">'
            f'<b style="color:#00d4ff;font-size:0.95rem;">{title}</b><br/>'
            f'<span style="font-size:0.88rem;color:rgba(255,255,255,0.72);line-height:1.5;">'
            f'{html_body}</span></div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Decision Path Visualization ──────────────────────────────────
    st.subheader("4 · Decision Path Visualization")
    st.caption("Condition-check tree executed by the algorithm this cycle")

    def _decision_node(condition: str, result: str, active: bool, indent: int = 0):
        """Render one if/else decision node."""
        if active:
            bg = "rgba(0,212,255,0.10)"
            border = "rgba(0,212,255,0.45)"
            icon = "▶"
            res_col = "#00f0ff"
        else:
            bg = "rgba(255,255,255,0.02)"
            border = "rgba(255,255,255,0.08)"
            icon = "○"
            res_col = "rgba(255,255,255,0.35)"

        left = 20 * indent
        st.markdown(
            f'<div style="margin-left:{left}px;background:{bg};'
            f'border:1px solid {border};border-radius:10px;'
            f'padding:10px 16px;margin-bottom:6px;display:flex;align-items:center;gap:10px;">'
            f'<span style="font-size:1.1rem;">{icon}</span>'
            f'<div style="flex:1;">'
            f'<span style="font-weight:600;color:#f0f0f0;font-size:0.9rem;">{condition}</span>'
            f'<br/><span style="font-size:0.82rem;color:{res_col};">{result}</span>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    _decision_node(
        f"IF memory_usage < 60%",
        "→ No action needed. Continue passive monitoring.",
        _usage_pct < 60, indent=0,
    )
    _decision_node(
        f"ELIF memory_usage 60–80%",
        "→ Selectively optimise background apps. Suggest cleanup.",
        60 <= _usage_pct < 80, indent=1,
    )
    _decision_node(
        f"ELIF memory_usage ≥ 80%",
        "→ Aggressive reclamation. Terminate low-priority apps immediately.",
        _usage_pct >= 80, indent=1,
    )

    st.markdown(
        f'<div style="margin-top:6px;margin-left:40px;padding:10px 16px;'
        f'background:rgba(168,85,247,0.08);border:1px solid rgba(168,85,247,0.3);'
        f'border-radius:10px;">'
        f'<span style="font-weight:700;color:#a855f7;font-size:0.9rem;">'
        f'Active Path ▸</span> '
        f'<span style="color:#f0f0f0;font-size:0.88rem;">'
        f'Usage = {_usage_pct}% → Band = {_band} → Strategy = {_strategy}</span></div>',
        unsafe_allow_html=True,
    )

    # Sub-decision: candidate filtering
    st.markdown("")
    _decision_node(
        "FOR each process: kill_score ≥ 3 ?",
        f"{len(_candidates)} process(es) passed the score threshold",
        len(_candidates) > 0, indent=0,
    )
    _decision_node(
        "AND package NOT IN system blocklist ?",
        f"{len(_candidates)} candidate(s) remain after blocklist filter",
        len(_candidates) > 0, indent=1,
    )
    _decision_node(
        "Sort candidates by PSS descending",
        f"Top candidate: {_candidates[0].package_name} ({_candidates[0].pss_mb} MB)"
        if _candidates else "No candidates to sort",
        len(_candidates) > 0, indent=2,
    )

    st.divider()

    # ── Final Output Result ──────────────────────────────────────────
    st.subheader("5 · Final Output Result")

    out1, out2, out3 = st.columns(3)
    out1.metric("Severity", _band)
    out2.metric("Strategy", _strategy)
    out3.metric("Freeable", f"{_freed} MB")

    # Detailed result card
    st.markdown(
        f'<div style="background:linear-gradient(135deg,rgba(0,212,255,0.06),rgba(168,85,247,0.06));'
        f'border:1px solid rgba(0,212,255,0.2);border-radius:16px;padding:22px 26px;margin-top:10px;'
        f'backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);'
        f'box-shadow:0 8px 32px rgba(0,0,0,0.3);">'
        f'<div style="font-size:1.1rem;font-weight:700;color:#00d4ff;margin-bottom:8px;">'
        f'🏁 Algorithm Decision Output</div>'
        f'<table style="width:100%;border-collapse:collapse;font-size:0.9rem;">'
        f'<tr><td style="padding:5px 0;color:rgba(255,255,255,0.55);width:160px;">Memory Usage</td>'
        f'<td style="color:#f0f0f0;font-weight:600;">{_usage_pct} %</td></tr>'
        f'<tr><td style="padding:5px 0;color:rgba(255,255,255,0.55);">Threshold Band</td>'
        f'<td><span style="color:{_band_color};font-weight:700;">{_band}</span></td></tr>'
        f'<tr><td style="padding:5px 0;color:rgba(255,255,255,0.55);">Selected Strategy</td>'
        f'<td style="color:#f0f0f0;font-weight:600;">{_strategy}</td></tr>'
        f'<tr><td style="padding:5px 0;color:rgba(255,255,255,0.55);">Action</td>'
        f'<td style="color:#f0f0f0;">{_action}</td></tr>'
        f'<tr><td style="padding:5px 0;color:rgba(255,255,255,0.55);">Kill Candidates</td>'
        f'<td style="color:#f0f0f0;font-weight:600;">{len(_candidates)} process(es)</td></tr>'
        f'<tr><td style="padding:5px 0;color:rgba(255,255,255,0.55);">Estimated Freeable</td>'
        f'<td style="color:#10b981;font-weight:700;">{_freed} MB</td></tr>'
        f'<tr><td style="padding:5px 0;color:rgba(255,255,255,0.55);">Recommendation</td>'
        f'<td style="color:rgba(255,255,255,0.8);">{_detail}</td></tr>'
        f'</table></div>',
        unsafe_allow_html=True,
    )

    # Reasoning explanation
    st.markdown("")
    if _band == "CRITICAL":
        _why = (
            f"Memory usage ({_usage_pct}%) has exceeded the critical threshold of 80%. "
            f"The algorithm identified {len(_candidates)} low-priority process(es) consuming "
            f"approximately {_freed} MB. Immediate termination is recommended to prevent "
            f"system slowdown and potential app crashes."
        )
    elif _band == "WARNING":
        _why = (
            f"Memory usage ({_usage_pct}%) is between 60% and 80%. The system is under "
            f"moderate pressure. {len(_candidates)} background/cached app(s) can be cleaned "
            f"to recover ~{_freed} MB and maintain responsiveness."
        )
    else:
        _why = (
            f"Memory usage ({_usage_pct}%) is below 60%. The device has adequate free RAM. "
            f"The algorithm recommends passive monitoring — no intervention is necessary."
        )

    st.markdown(
        f'<div style="background:rgba(168,85,247,0.06);border:1px solid rgba(168,85,247,0.2);'
        f'border-radius:12px;padding:14px 18px;margin-top:8px;">'
        f'<b style="color:#a855f7;">💡 Why this decision?</b><br/>'
        f'<span style="font-size:0.88rem;color:rgba(255,255,255,0.75);line-height:1.55;">'
        f'{_why}</span></div>',
        unsafe_allow_html=True,
    )
