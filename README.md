# 🏭 Industrial Motor Monitoring & Data Acquisition System

> **Simulation of an Industrial Motor Monitoring System using ESP32 and IoT Dashboard**
>
> Built with: Python · Flask · Streamlit · Plotly · CSV Storage

---

## 📐 System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    SIMULATION SYSTEM                    │
│                                                         │
│  ┌──────────────────────┐                               │
│  │   ESP32 Simulator    │  ← esp32_simulator.py         │
│  │  (Python Script)     │    Cycles 4 test scenarios    │
│  │                      │    POST /api/data every 5s    │
│  └────────┬─────────────┘                               │
│           │ HTTP POST (JSON)                            │
│           ▼                                             │
│  ┌──────────────────────┐                               │
│  │   Flask Server       │  ← server/app.py              │
│  │   localhost:5000     │    Automation logic           │
│  │                      │    CSV storage                │
│  └────────┬─────────────┘    REST API                  │
│           │ HTTP GET                                    │
│           ▼                                             │
│  ┌──────────────────────┐                               │
│  │  Streamlit Dashboard │  ← dashboard/dashboard.py     │
│  │  localhost:8501      │    Real-time charts           │
│  │                      │    Alert panel                │
│  └──────────────────────┘    Motor controls             │
└─────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
motor_monitor/
├── server/
│   ├── app.py              # Flask server — ingestion, API, automation
│   └── requirements.txt
├── simulator/
│   ├── esp32_simulator.py  # ESP32 simulation — 4 test scenarios
│   └── requirements.txt
├── dashboard/
│   ├── dashboard.py        # Streamlit IoT dashboard
│   └── requirements.txt
├── data/
│   └── motor_data.csv      # Auto-generated: historical readings
├── start_all.bat           # ⚡ One-click launcher (Windows)
└── README.md
```

---

## 🚀 Quick Start (Windows)

### Option A — One Click
1. Double-click **`start_all.bat`**
2. The dashboard opens automatically at **http://localhost:8501**

### Option B — Manual (3 separate terminals)

**Terminal 1 — Flask Server:**
```bash
cd motor_monitor
pip install -r server/requirements.txt
python server/app.py
```

**Terminal 2 — ESP32 Simulator:**
```bash
cd motor_monitor
pip install -r simulator/requirements.txt
python simulator/esp32_simulator.py
```

**Terminal 3 — Streamlit Dashboard:**
```bash
cd motor_monitor
pip install -r dashboard/requirements.txt
streamlit run dashboard/dashboard.py
```

---

## 🧪 Test Scenarios (PRD Section 11)

The ESP32 simulator automatically cycles through all 4 PRD test cases:

| # | Scenario | Temp | Current | Vibration | Expected Result |
|---|----------|------|---------|-----------|-----------------|
| 1 | **Normal Operation** | 25–45°C | 1–4.5A | 0 | Motor ON, No alerts |
| 2 | **Overheating** | 51–80°C | 2–4A | 0 | ⚠️ CRITICAL alert, Motor OFF |
| 3 | **Overload** | 30–45°C | 5.1–8A | 0 | ⚡ CRITICAL alert, Motor OFF |
| 4 | **Vibration Fault** | 30–45°C | 2–4A | 1 | 📳 WARNING, Motor stays ON |

Each scenario runs for **10 transmissions × 5 seconds = 50 seconds**, then cycles to next.

---

## ⚙️ Automation Logic (PRD FR-7)

| Condition | Action |
|-----------|--------|
| Temperature > **50°C** | Motor → **OFF** + CRITICAL alert |
| Current > **5A** | Motor → **OFF** + CRITICAL alert |
| Vibration = **1** | WARNING alert (motor unaffected unless other rule fires) |
| Dashboard: Force ON | Manual override (blocked if safety threshold breached) |
| Dashboard: Force OFF | Motor → OFF regardless |
| Dashboard: AUTO | Return to automated threshold-based control |

---

## 🔌 REST API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/data` | Receive sensor data from ESP32 |
| `GET` | `/api/data?limit=N` | Fetch last N readings |
| `GET` | `/api/status` | Current motor status + active alerts |
| `POST` | `/api/control` | Motor control: `{"command": "ON/OFF/AUTO"}` |

---

## 📊 Dashboard Features

- 🟢🔴 **Motor Status** — live ON/OFF with color-coded indicator
- 🌡 **Temperature Gauge** — live reading with threshold warning
- ⚡ **Current Gauge** — live reading with overload warning
- 📳 **Vibration Status** — OK / FAULT indicator
- 🚨 **Alert Panel** — live alerts with severity colors (CRITICAL / WARNING)
- 📈 **Temperature Trend Chart** — line chart with 50°C shutdown threshold line
- 📈 **Current Trend Chart** — line chart with 5A shutdown threshold line
- 📊 **Vibration History** — bar chart (green = OK, red = FAULT)
- 📋 **Session Statistics** — avg/max temp, avg current, fault count
- 🎛 **Motor Controls** — Force ON / Force OFF / AUTO buttons
- 📄 **Raw Data Log** — expandable table of last 20 readings

---

## 📦 Dependencies

| Package | Version | Use |
|---------|---------|-----|
| flask | ≥3.0 | REST API server |
| flask-cors | ≥4.0 | Cross-origin requests |
| requests | ≥2.31 | HTTP client (simulator) |
| streamlit | ≥1.35 | Dashboard UI |
| plotly | ≥5.22 | Interactive charts |
| pandas | ≥2.2 | Data manipulation |

---

## 📝 Data Format (CSV)

`data/motor_data.csv` columns:

| Column | Type | Description |
|--------|------|-------------|
| `timestamp` | string | `YYYY-MM-DD HH:MM:SS` |
| `temperature` | float | °C |
| `current` | float | Amperes |
| `vibration` | int | 0=OK, 1=FAULT |
| `motor_status` | string | `ON` or `OFF` |
| `alert` | string | Alert message or `Normal` |

---

## 🛠 Requirements

- Python 3.10+
- Windows (for `start_all.bat`; manual startup works on any OS)
- Internet connection for Google Fonts (dashboard styling)

---

*This project is a simulation demonstrating Industrial Automation and Data Acquisition principles.*
*All sensor data is virtually generated — no real hardware required.*
