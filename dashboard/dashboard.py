"""
============================================================
Industrial Motor Monitoring System — Streamlit IoT Dashboard
============================================================
Real-time dashboard that polls the Flask server every 5 seconds
and displays motor status, sensor readings, alerts, and trends.
============================================================
"""

import time
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# ── Page Configuration ────────────────────────────────────────
st.set_page_config(
    page_title="Motor Monitor — IoT Dashboard",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Constants ─────────────────────────────────────────────────
SERVER_BASE   = "http://localhost:5000"
TEMP_THRESHOLD    = 50.0
CURRENT_THRESHOLD = 5.0
REFRESH_INTERVAL  = 5    # seconds

# ── Custom CSS ────────────────────────────────────────────────
st.markdown("""
<style>
  /* ── Google Font ── */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

  html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
  }

  /* ── Dark Gradient Background ── */
  .stApp {
    background: linear-gradient(135deg, #0a0e1a 0%, #0d1b2a 40%, #0a1628 70%, #0d0d1a 100%);
    color: #e2e8f0;
  }

  /* ── Main container padding ── */
  .main .block-container {
    padding-top: 1.5rem;
    padding-bottom: 2rem;
    max-width: 1400px;
  }

  /* ── Status Card ── */
  .status-card {
    background: linear-gradient(145deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02));
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 16px;
    padding: 24px 20px;
    text-align: center;
    backdrop-filter: blur(10px);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    margin-bottom: 8px;
  }
  .status-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  }

  /* ── Motor ON card ── */
  .motor-on {
    border-color: rgba(52, 211, 153, 0.5) !important;
    box-shadow: 0 0 24px rgba(52, 211, 153, 0.15);
  }
  /* ── Motor OFF card ── */
  .motor-off {
    border-color: rgba(248, 113, 113, 0.5) !important;
    box-shadow: 0 0 24px rgba(248, 113, 113, 0.15);
  }

  /* ── Alert card ── */
  .alert-critical {
    background: linear-gradient(135deg, rgba(239,68,68,0.15), rgba(185,28,28,0.1));
    border: 1px solid rgba(239,68,68,0.4);
    border-radius: 10px;
    padding: 10px 16px;
    margin: 6px 0;
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    color: #fca5a5;
    animation: pulse-red 2s infinite;
  }
  .alert-warning {
    background: linear-gradient(135deg, rgba(251,191,36,0.15), rgba(180,130,0,0.1));
    border: 1px solid rgba(251,191,36,0.4);
    border-radius: 10px;
    padding: 10px 16px;
    margin: 6px 0;
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    color: #fde68a;
  }
  .alert-normal {
    background: linear-gradient(135deg, rgba(52,211,153,0.1), rgba(16,185,129,0.05));
    border: 1px solid rgba(52,211,153,0.3);
    border-radius: 10px;
    padding: 10px 16px;
    margin: 6px 0;
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    color: #6ee7b7;
  }

  @keyframes pulse-red {
    0%, 100% { box-shadow: 0 0 0 0 rgba(239,68,68,0.3); }
    50%       { box-shadow: 0 0 0 6px rgba(239,68,68,0); }
  }

  /* ── Section Headers ── */
  .section-header {
    font-size: 14px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #94a3b8;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
  }

  /* ── Metric values ── */
  .metric-value {
    font-size: 38px;
    font-weight: 800;
    line-height: 1.1;
    letter-spacing: -0.02em;
  }
  .metric-label {
    font-size: 12px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #94a3b8;
    margin-top: 6px;
  }
  .metric-unit {
    font-size: 18px;
    font-weight: 400;
    color: #94a3b8;
  }

  /* ── Control buttons ── */
  div[data-testid="stButton"] > button {
    width: 100%;
    border-radius: 10px;
    font-weight: 600;
    font-size: 14px;
    padding: 10px 20px;
    letter-spacing: 0.05em;
    border: none;
    transition: all 0.2s ease;
  }
  div[data-testid="stButton"] > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 16px rgba(0,0,0,0.3);
  }

  /* ── Hide default streamlit elements ── */
  #MainMenu, footer, header { visibility: hidden; }

  /* ── Divider ── */
  hr { border-color: rgba(255,255,255,0.08); margin: 20px 0; }
</style>
""", unsafe_allow_html=True)


# ── API Helpers ───────────────────────────────────────────────

def fetch_status():
    try:
        r = requests.get(f"{SERVER_BASE}/api/status", timeout=3)
        return r.json()
    except Exception:
        return None


def fetch_history(limit=100):
    try:
        r = requests.get(f"{SERVER_BASE}/api/data", params={"limit": limit}, timeout=3)
        return r.json()
    except Exception:
        return []


def send_control(command: str):
    try:
        r = requests.post(
            f"{SERVER_BASE}/api/control",
            json={"command": command},
            timeout=3,
        )
        return r.json()
    except Exception:
        return {"error": "Server not reachable"}


# ── Chart Builder ─────────────────────────────────────────────

CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#94a3b8", family="Inter"),
    margin=dict(l=0, r=0, t=30, b=0),
    xaxis=dict(
        gridcolor="rgba(255,255,255,0.05)",
        linecolor="rgba(255,255,255,0.1)",
        showgrid=True,
        title_font=dict(size=12),
    ),
    yaxis=dict(
        gridcolor="rgba(255,255,255,0.05)",
        linecolor="rgba(255,255,255,0.1)",
        showgrid=True,
        title_font=dict(size=12),
    ),
    legend=dict(
        orientation="h",
        yanchor="bottom", y=1.02,
        xanchor="right",  x=1,
        bgcolor="rgba(0,0,0,0)",
        font=dict(size=11),
    ),
    height=280,
)


def build_temperature_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df["temperature"].astype(float),
        mode="lines+markers",
        name="Temperature (°C)",
        line=dict(color="#f97316", width=2.5),
        marker=dict(size=4, color="#f97316"),
        fill="tozeroy",
        fillcolor="rgba(249,115,22,0.08)",
    ))

    # Threshold line
    fig.add_hline(
        y=TEMP_THRESHOLD,
        line=dict(color="#ef4444", width=1.5, dash="dash"),
        annotation_text=f"  Shutdown >{TEMP_THRESHOLD}°C",
        annotation_font_color="#ef4444",
        annotation_font_size=11,
    )

    fig.update_layout(
        **CHART_LAYOUT,
        title=dict(text="Temperature Trend", font=dict(size=14, color="#e2e8f0"), x=0),
        yaxis_title="deg C",
    )
    return fig


def build_current_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df["current"].astype(float),
        mode="lines+markers",
        name="Current (A)",
        line=dict(color="#818cf8", width=2.5),
        marker=dict(size=4, color="#818cf8"),
        fill="tozeroy",
        fillcolor="rgba(129,140,248,0.08)",
    ))

    fig.add_hline(
        y=CURRENT_THRESHOLD,
        line=dict(color="#ef4444", width=1.5, dash="dash"),
        annotation_text=f"  Shutdown >{CURRENT_THRESHOLD}A",
        annotation_font_color="#ef4444",
        annotation_font_size=11,
    )

    fig.update_layout(
        **CHART_LAYOUT,
        title=dict(text="Current Trend", font=dict(size=14, color="#e2e8f0"), x=0),
        yaxis_title="Amperes",
    )
    return fig


def build_vibration_chart(df: pd.DataFrame) -> go.Figure:
    vib = df["vibration"].astype(int)
    colors = ["#ef4444" if v == 1 else "#34d399" for v in vib]

    fig = go.Figure(go.Bar(
        x=df["timestamp"],
        y=vib,
        marker_color=colors,
        name="Vibration",
        hovertemplate="Time: %{x}<br>Status: %{customdata}",
        customdata=["FAULT" if v == 1 else "OK" for v in vib],
    ))

    fig.update_layout(
        **CHART_LAYOUT,
        title=dict(text="Vibration / Fault History", font=dict(size=14, color="#e2e8f0"), x=0),
    )
    fig.update_yaxes(
        tickvals=[0, 1],
        ticktext=["OK", "FAULT"],
        gridcolor="rgba(255,255,255,0.05)",
        linecolor="rgba(255,255,255,0.1)",
    )
    return fig


# ── Status Cards ──────────────────────────────────────────────

def motor_card(motor_status: str):
    is_on = motor_status == "ON"
    color    = "#34d399" if is_on else "#f87171"
    bg_class = "motor-on" if is_on else "motor-off"
    icon     = "🟢" if is_on else "🔴"
    label    = "RUNNING" if is_on else "SHUTDOWN"
    glow     = "rgba(52,211,153,0.2)" if is_on else "rgba(248,113,113,0.2)"

    st.markdown(f"""
    <div class="status-card {bg_class}" style="box-shadow: 0 0 32px {glow};">
      <div style="font-size:48px; margin-bottom:8px;">{icon}</div>
      <div class="metric-value" style="color:{color};">{label}</div>
      <div class="metric-label">Motor Status</div>
    </div>
    """, unsafe_allow_html=True)


def sensor_card(icon, label, value, unit, color, warn=False):
    warn_border = "rgba(239,68,68,0.5)" if warn else "rgba(255,255,255,0.1)"
    warn_glow   = "0 0 16px rgba(239,68,68,0.2)" if warn else "none"
    st.markdown(f"""
    <div class="status-card" style="border-color:{warn_border}; box-shadow:{warn_glow};">
      <div style="font-size:36px; margin-bottom:8px;">{icon}</div>
      <div class="metric-value" style="color:{color};">
        {value}<span class="metric-unit"> {unit}</span>
      </div>
      <div class="metric-label">{label}</div>
    </div>
    """, unsafe_allow_html=True)


def vibration_card(vib: int):
    if vib == 1:
        st.markdown("""
        <div class="status-card" style="border-color:rgba(251,191,36,0.5); box-shadow:0 0 16px rgba(251,191,36,0.2);">
          <div style="font-size:36px; margin-bottom:8px;">📳</div>
          <div class="metric-value" style="color:#fbbf24;">FAULT</div>
          <div class="metric-label">Vibration Status</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="status-card">
          <div style="font-size:36px; margin-bottom:8px;">✅</div>
          <div class="metric-value" style="color:#34d399;">NORMAL</div>
          <div class="metric-label">Vibration Status</div>
        </div>
        """, unsafe_allow_html=True)


# ── Main Dashboard ────────────────────────────────────────────

def main():
    # ── Header ──
    now_str = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    st.markdown(f"""
    <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:24px;">
      <div>
        <h1 style="margin:0; font-size:26px; font-weight:800; color:#f1f5f9;
                   letter-spacing:-0.02em;">
          🏭 Industrial Motor Monitoring System
        </h1>
        <p style="margin:4px 0 0; font-size:13px; color:#64748b; font-family:'JetBrains Mono';">
          IoT Data Acquisition Dashboard &nbsp;|&nbsp; Auto-refresh every {REFRESH_INTERVAL}s
        </p>
      </div>
      <div style="text-align:right;">
        <div style="font-family:'JetBrains Mono'; font-size:13px; color:#64748b;">Last Update</div>
        <div style="font-family:'JetBrains Mono'; font-size:14px; font-weight:600; color:#94a3b8;">
          {now_str}
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Fetch Data ──
    status  = fetch_status()
    history = fetch_history(limit=100)

    server_ok = status is not None

    if not server_ok:
        st.error(
            "⚠️ **Cannot reach Flask server** at `http://localhost:5000`. "
            "Please start the server with `python server/app.py`."
        )
        st.info("Dashboard will auto-retry in 5 seconds...")
        time.sleep(REFRESH_INTERVAL)
        st.rerun()
        return

    motor_status  = status.get("motor_status", "?")
    active_alerts = status.get("active_alerts", [])
    last_reading  = status.get("last_reading", {})

    temp    = float(last_reading.get("temperature", 0))
    current = float(last_reading.get("current", 0))
    vib     = int(last_reading.get("vibration", 0))

    temp_warn    = temp    > TEMP_THRESHOLD
    current_warn = current > CURRENT_THRESHOLD

    # ── Row 1: Status Cards ──
    st.markdown('<div class="section-header">📊 Live Sensor Readings</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        motor_card(motor_status)
    with c2:
        sensor_card(
            "🌡", "Temperature",
            f"{temp:.1f}", "°C",
            "#f97316" if temp_warn else "#fb923c",
            warn=temp_warn,
        )
    with c3:
        sensor_card(
            "⚡", "Current Draw",
            f"{current:.2f}", "A",
            "#818cf8" if not current_warn else "#f87171",
            warn=current_warn,
        )
    with c4:
        vibration_card(vib)

    st.markdown("<hr/>", unsafe_allow_html=True)

    # ── Row 2: Alert Panel + Controls ──
    col_alert, col_ctrl = st.columns([3, 1])

    with col_alert:
        st.markdown('<div class="section-header">🚨 Alert Panel</div>', unsafe_allow_html=True)
        if active_alerts:
            for alert in active_alerts:
                if "CRITICAL" in alert:
                    st.markdown(f'<div class="alert-critical">🔴 {alert}</div>', unsafe_allow_html=True)
                elif "WARNING" in alert:
                    st.markdown(f'<div class="alert-warning">🟡 {alert}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="alert-normal">🔵 {alert}</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="alert-normal">✅ No active alerts — System operating normally</div>',
                unsafe_allow_html=True,
            )

    with col_ctrl:
        st.markdown('<div class="section-header">🎛 Motor Control</div>', unsafe_allow_html=True)
        st.markdown(
            '<p style="font-size:12px; color:#64748b; margin-bottom:12px;">'
            'Manual override for motor relay</p>',
            unsafe_allow_html=True,
        )

        override = status.get("motor_override")
        override_label = f"Mode: {'AUTO' if override is None else override}"
        st.markdown(
            f'<p style="font-size:11px; color:#94a3b8; font-family:JetBrains Mono; '
            f'margin-bottom:12px;">{override_label}</p>',
            unsafe_allow_html=True,
        )

        if st.button("🟢 Force Motor ON", key="btn_on",
                     help="Manually force motor ON (overrides automation if safe)"):
            res = send_control("ON")
            st.toast(res.get("message", "Done"), icon="🟢")

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        if st.button("🔴 Force Motor OFF", key="btn_off",
                     help="Manually force motor OFF"):
            res = send_control("OFF")
            st.toast(res.get("message", "Done"), icon="🔴")

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        if st.button("🔄 Set to AUTO", key="btn_auto",
                     help="Return to automatic mode governed by thresholds"):
            res = send_control("AUTO")
            st.toast(res.get("message", "Done"), icon="🔄")

    st.markdown("<hr/>", unsafe_allow_html=True)

    # ── Row 3: Trend Charts ──
    st.markdown('<div class="section-header">📈 Historical Trends</div>', unsafe_allow_html=True)

    if history:
        df = pd.DataFrame(history)
        df["temperature"] = pd.to_numeric(df["temperature"], errors="coerce")
        df["current"]     = pd.to_numeric(df["current"],     errors="coerce")
        df["vibration"]   = pd.to_numeric(df["vibration"],   errors="coerce").fillna(0).astype(int)

        # Show only last 60 rows for clarity
        df = df.tail(60)

        ch1, ch2 = st.columns(2)
        with ch1:
            st.plotly_chart(build_temperature_chart(df), width="stretch")
        with ch2:
            st.plotly_chart(build_current_chart(df), width="stretch")

        st.plotly_chart(build_vibration_chart(df), width="stretch")

        # ── Row 4: Summary Stats ──
        st.markdown("<hr/>", unsafe_allow_html=True)
        st.markdown('<div class="section-header">📋 Session Statistics</div>', unsafe_allow_html=True)

        s1, s2, s3, s4, s5 = st.columns(5)
        s1.metric("Total Readings",    len(df))
        s2.metric("Avg Temperature",   f"{df['temperature'].mean():.1f}°C")
        s3.metric("Max Temperature",   f"{df['temperature'].max():.1f}°C")
        s4.metric("Avg Current",       f"{df['current'].mean():.2f}A")
        s5.metric("Vibration Faults",  int(df['vibration'].sum()))

        # ── Raw Data Table ──
        with st.expander("📄 Raw Data Log (last 20 readings)"):
            display_df = df.tail(20)[["timestamp","temperature","current","vibration","motor_status","alert"]].copy()
            display_df.columns = ["Timestamp","Temp (°C)","Current (A)","Vibration","Motor","Alert"]
            st.dataframe(display_df, width="stretch", hide_index=True)
    else:
        st.info("⏳ Waiting for data from ESP32 simulator... Start `esp32_simulator.py`")

    # ── Footer ──
    st.markdown("""
    <div style="text-align:center; margin-top:32px; padding-top:16px;
                border-top: 1px solid rgba(255,255,255,0.06);">
      <p style="font-size:12px; color:#334155; font-family:'JetBrains Mono';">
        🏭 Industrial Motor Monitoring System &nbsp;|&nbsp;
        ESP32 + Flask + Streamlit &nbsp;|&nbsp;
        Simulation Project
      </p>
    </div>
    """, unsafe_allow_html=True)

    # ── Auto-Refresh ──
    time.sleep(REFRESH_INTERVAL)
    st.rerun()


if __name__ == "__main__":
    main()
