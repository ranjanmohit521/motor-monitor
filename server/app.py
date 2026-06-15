"""
============================================================
Industrial Motor Monitoring System -- Flask Server
============================================================
Serves:
  - REST API  for ESP32 simulator data ingestion
  - HTML dashboard at http://localhost:5000
  - CSV storage + automation logic
============================================================
"""

import csv
import json
import os
import random
import threading
import time
from datetime import datetime

from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ── Configuration ─────────────────────────────────────────────
DATA_DIR          = os.path.join(os.path.dirname(__file__), "..", "data")
CSV_PATH          = os.path.join(DATA_DIR, "motor_data.csv")
TEMP_THRESHOLD    = 50.0
CURRENT_THRESHOLD = 5.0
MAX_ROWS_RETURN   = 200

CSV_HEADERS = ["timestamp", "temperature", "current",
               "vibration", "motor_status", "alert"]

state_lock   = threading.Lock()
system_state = {
    "motor_status":   "ON",
    "motor_override": None,
    "active_alerts":  [],
    "last_reading":   {},
}

# In-memory data store (cloud-friendly, no filesystem needed)
data_history = []

# ── HTML Dashboard (inline) ────────────────────────────────────
DASHBOARD_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Motor Monitor — IoT Dashboard</title>
<meta name="description" content="Real-time industrial motor monitoring dashboard with temperature, current, and vibration tracking."/>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet"/>
<style>
:root{
  --bg:       #080c18;
  --bg2:      #0d1428;
  --card:     rgba(255,255,255,0.04);
  --border:   rgba(255,255,255,0.08);
  --text:     #e2e8f0;
  --muted:    #64748b;
  --accent:   #6366f1;
  --green:    #34d399;
  --red:      #f87171;
  --orange:   #fb923c;
  --yellow:   #fbbf24;
  --purple:   #a78bfa;
}
*{box-sizing:border-box;margin:0;padding:0;}
body{
  font-family:'Inter',sans-serif;
  background:linear-gradient(135deg,var(--bg) 0%,var(--bg2) 100%);
  color:var(--text);min-height:100vh;
}
/* ── Header ── */
.header{
  background:rgba(255,255,255,0.02);
  border-bottom:1px solid var(--border);
  padding:18px 32px;
  display:flex;align-items:center;justify-content:space-between;
  backdrop-filter:blur(10px);
  position:sticky;top:0;z-index:100;
}
.header h1{font-size:20px;font-weight:800;letter-spacing:-0.02em;
  background:linear-gradient(90deg,#818cf8,#34d399);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.header-right{text-align:right;}
.header-right .label{font-size:11px;color:var(--muted);font-family:'JetBrains Mono';}
.header-right .time{font-size:13px;font-weight:600;color:#94a3b8;font-family:'JetBrains Mono';}
.conn-dot{display:inline-block;width:8px;height:8px;border-radius:50%;
  background:var(--green);box-shadow:0 0 8px var(--green);margin-right:6px;
  animation:blink 1.5s infinite;}
@keyframes blink{0%,100%{opacity:1;}50%{opacity:0.3;}}

/* ── Layout ── */
.container{max-width:1400px;margin:0 auto;padding:28px 32px;}
.section-label{font-size:11px;font-weight:600;text-transform:uppercase;
  letter-spacing:0.12em;color:var(--muted);margin-bottom:16px;
  padding-bottom:8px;border-bottom:1px solid var(--border);}

/* ── Status Cards Row ── */
.cards-row{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:28px;}
.card{
  background:var(--card);border:1px solid var(--border);border-radius:16px;
  padding:24px 20px;text-align:center;
  transition:transform .2s,box-shadow .2s;cursor:default;
  position:relative;overflow:hidden;
}
.card::before{
  content:'';position:absolute;inset:0;border-radius:16px;
  background:linear-gradient(135deg,rgba(255,255,255,0.03),transparent);
  pointer-events:none;
}
.card:hover{transform:translateY(-3px);box-shadow:0 12px 40px rgba(0,0,0,0.4);}
.card-icon{font-size:32px;margin-bottom:12px;}
.card-value{font-size:36px;font-weight:800;letter-spacing:-0.03em;line-height:1;}
.card-unit{font-size:16px;font-weight:400;color:var(--muted);}
.card-label{font-size:11px;font-weight:600;text-transform:uppercase;
  letter-spacing:0.1em;color:var(--muted);margin-top:8px;}
.card.motor-on {border-color:rgba(52,211,153,0.4);box-shadow:0 0 32px rgba(52,211,153,0.1);}
.card.motor-off{border-color:rgba(248,113,113,0.4);box-shadow:0 0 32px rgba(248,113,113,0.1);}
.card.warn     {border-color:rgba(251,191,36,0.4); box-shadow:0 0 20px rgba(251,191,36,0.1);}
.card.danger   {border-color:rgba(248,113,113,0.4);box-shadow:0 0 20px rgba(248,113,113,0.1);}

/* ── Middle Row ── */
.mid-row{display:grid;grid-template-columns:1fr 280px;gap:16px;margin-bottom:28px;}

/* ── Alert Panel ── */
.alert-panel{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:20px;}
.alerts-list{max-height:220px;overflow-y:auto;display:flex;flex-direction:column;gap:8px;margin-top:12px;}
.alert-item{padding:10px 14px;border-radius:10px;font-family:'JetBrains Mono';font-size:12px;line-height:1.5;}
.alert-critical{background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.35);color:#fca5a5;}
.alert-warning {background:rgba(251,191,36,0.12);border:1px solid rgba(251,191,36,0.35);color:#fde68a;}
.alert-normal  {background:rgba(52,211,153,0.1); border:1px solid rgba(52,211,153,0.3); color:#6ee7b7;}
.alert-time{font-size:10px;color:var(--muted);display:block;margin-bottom:2px;}

/* ── Controls ── */
.controls{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:20px;display:flex;flex-direction:column;gap:10px;}
.ctrl-label{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.1em;color:var(--muted);margin-bottom:4px;}
.btn{width:100%;padding:11px 16px;border-radius:10px;border:none;cursor:pointer;
  font-weight:600;font-size:13px;letter-spacing:0.05em;
  transition:transform .15s,box-shadow .15s;font-family:'Inter',sans-serif;}
.btn:hover{transform:translateY(-1px);box-shadow:0 6px 20px rgba(0,0,0,0.3);}
.btn:active{transform:translateY(0);}
.btn-on {background:linear-gradient(135deg,#059669,#34d399);color:#fff;}
.btn-off{background:linear-gradient(135deg,#b91c1c,#f87171);color:#fff;}
.btn-auto{background:linear-gradient(135deg,#3730a3,#818cf8);color:#fff;}
.override-mode{font-size:11px;color:var(--muted);font-family:'JetBrains Mono';text-align:center;padding:6px;
  background:rgba(255,255,255,0.03);border-radius:8px;border:1px solid var(--border);}

/* ── Charts ── */
.charts-row{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:28px;}
.chart-card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:20px;}
.chart-title{font-size:13px;font-weight:600;color:var(--text);margin-bottom:16px;}
.chart-wrap{position:relative;height:200px;}
.chart-full{background:var(--card);border:1px solid var(--border);border-radius:16px;
  padding:20px;margin-bottom:28px;}
.chart-full .chart-wrap{height:140px;}

/* ── Stats Row ── */
.stats-row{display:grid;grid-template-columns:repeat(5,1fr);gap:16px;margin-bottom:28px;}
.stat{background:var(--card);border:1px solid var(--border);border-radius:12px;
  padding:16px;text-align:center;}
.stat-value{font-size:24px;font-weight:700;color:var(--text);}
.stat-label{font-size:11px;color:var(--muted);margin-top:4px;text-transform:uppercase;letter-spacing:0.08em;}

/* ── Table ── */
.table-card{background:var(--card);border:1px solid var(--border);border-radius:16px;
  padding:20px;margin-bottom:28px;overflow-x:auto;}
table{width:100%;border-collapse:collapse;font-size:13px;}
th{text-align:left;padding:10px 14px;font-size:11px;font-weight:600;
  text-transform:uppercase;letter-spacing:0.08em;color:var(--muted);
  border-bottom:1px solid var(--border);}
td{padding:10px 14px;border-bottom:1px solid rgba(255,255,255,0.04);
  font-family:'JetBrains Mono';font-size:12px;color:#cbd5e1;}
tr:last-child td{border-bottom:none;}
tr:hover td{background:rgba(255,255,255,0.02);}
.badge{display:inline-block;padding:2px 8px;border-radius:20px;font-size:11px;font-weight:600;}
.badge-on {background:rgba(52,211,153,0.15);color:var(--green);border:1px solid rgba(52,211,153,0.3);}
.badge-off{background:rgba(248,113,113,0.15);color:var(--red);border:1px solid rgba(248,113,113,0.3);}
.badge-warn{background:rgba(251,191,36,0.15);color:var(--yellow);border:1px solid rgba(251,191,36,0.3);}

/* ── Footer ── */
.footer{text-align:center;padding:20px;border-top:1px solid var(--border);
  font-size:12px;color:var(--muted);font-family:'JetBrains Mono';}
.divider{border:none;border-top:1px solid var(--border);margin:0 0 24px;}

/* ── Pulse animation for alerts ── */
@keyframes pulse-border{0%,100%{border-color:rgba(239,68,68,0.4);}50%{border-color:rgba(239,68,68,0.8);}}
.has-critical{animation:pulse-border 1.5s infinite;}
</style>
</head>
<body>

<!-- HEADER -->
<div class="header">
  <div>
    <h1>&#x1F3ED; Industrial Motor Monitoring System</h1>
    <div style="font-size:12px;color:var(--muted);margin-top:4px;font-family:'JetBrains Mono'">
      ESP32 + Flask IoT Dashboard &nbsp;&bull;&nbsp; Auto-refresh: 5s
    </div>
  </div>
  <div class="header-right">
    <div class="label"><span class="conn-dot"></span>LIVE</div>
    <div class="time" id="clock">--:--:--</div>
  </div>
</div>

<div class="container">

  <!-- STATUS CARDS -->
  <div class="section-label" style="margin-top:4px;">&#x1F4CA; Live Sensor Readings</div>
  <div class="cards-row">
    <div class="card" id="card-motor">
      <div class="card-icon" id="motor-icon">&#x26AA;</div>
      <div class="card-value" id="motor-val">--</div>
      <div class="card-label">Motor Status</div>
    </div>
    <div class="card" id="card-temp">
      <div class="card-icon">&#x1F321;</div>
      <div class="card-value" id="temp-val">--<span class="card-unit"> &deg;C</span></div>
      <div class="card-label">Temperature</div>
    </div>
    <div class="card" id="card-curr">
      <div class="card-icon">&#x26A1;</div>
      <div class="card-value" id="curr-val">--<span class="card-unit"> A</span></div>
      <div class="card-label">Current Draw</div>
    </div>
    <div class="card" id="card-vib">
      <div class="card-icon">&#x1F4F3;</div>
      <div class="card-value" id="vib-val">--</div>
      <div class="card-label">Vibration</div>
    </div>
  </div>

  <!-- ALERT + CONTROLS -->
  <div class="mid-row">
    <div class="alert-panel" id="alert-panel">
      <div class="section-label" style="margin-bottom:0">&#x1F6A8; Alert Panel</div>
      <div class="alerts-list" id="alerts-list">
        <div class="alert-item alert-normal">Waiting for data...</div>
      </div>
    </div>
    <div class="controls">
      <div class="ctrl-label">&#x1F39B; Motor Control</div>
      <div class="override-mode" id="override-mode">Mode: AUTO</div>
      <button class="btn btn-on"   id="btn-on"   onclick="sendControl('ON')">&#x1F7E2; Force Motor ON</button>
      <button class="btn btn-off"  id="btn-off"  onclick="sendControl('OFF')">&#x1F534; Force Motor OFF</button>
      <button class="btn btn-auto" id="btn-auto" onclick="sendControl('AUTO')">&#x1F504; Set to AUTO</button>
      <div id="ctrl-feedback" style="font-size:11px;color:var(--green);font-family:'JetBrains Mono';
           text-align:center;min-height:16px;margin-top:4px;"></div>
    </div>
  </div>

  <hr class="divider"/>

  <!-- CHARTS -->
  <div class="section-label">&#x1F4C8; Historical Trends</div>
  <div class="charts-row">
    <div class="chart-card">
      <div class="chart-title">Temperature (&deg;C) &mdash; threshold 50&deg;C</div>
      <div class="chart-wrap"><canvas id="chartTemp"></canvas></div>
    </div>
    <div class="chart-card">
      <div class="chart-title">Current (A) &mdash; threshold 5A</div>
      <div class="chart-wrap"><canvas id="chartCurr"></canvas></div>
    </div>
  </div>
  <div class="chart-full">
    <div class="chart-title">Vibration / Fault History &nbsp;(1 = FAULT, 0 = OK)</div>
    <div class="chart-wrap"><canvas id="chartVib"></canvas></div>
  </div>

  <hr class="divider"/>

  <!-- STATS -->
  <div class="section-label">&#x1F4CB; Session Statistics</div>
  <div class="stats-row">
    <div class="stat"><div class="stat-value" id="stat-total">--</div><div class="stat-label">Total Readings</div></div>
    <div class="stat"><div class="stat-value" id="stat-avg-t">--</div><div class="stat-label">Avg Temp (&deg;C)</div></div>
    <div class="stat"><div class="stat-value" id="stat-max-t">--</div><div class="stat-label">Max Temp (&deg;C)</div></div>
    <div class="stat"><div class="stat-value" id="stat-avg-c">--</div><div class="stat-label">Avg Current (A)</div></div>
    <div class="stat"><div class="stat-value" id="stat-faults">--</div><div class="stat-label">Vib Faults</div></div>
  </div>

  <!-- TABLE -->
  <div class="section-label">&#x1F4C4; Recent Data Log</div>
  <div class="table-card">
    <table id="data-table">
      <thead>
        <tr>
          <th>Timestamp</th><th>Temp (&deg;C)</th><th>Current (A)</th>
          <th>Vibration</th><th>Motor</th><th>Alert</th>
        </tr>
      </thead>
      <tbody id="table-body">
        <tr><td colspan="6" style="text-align:center;color:var(--muted);">Loading...</td></tr>
      </tbody>
    </table>
  </div>

</div><!-- /container -->

<div class="footer">
  Industrial Motor Monitoring System &nbsp;&bull;&nbsp; ESP32 + Flask &nbsp;&bull;&nbsp; Simulation Project
</div>

<script>
// ── Clock ──────────────────────────────────────────────────────
function updateClock(){
  document.getElementById('clock').textContent =
    new Date().toLocaleTimeString('en-GB');
}
setInterval(updateClock,1000); updateClock();

// ── Chart setup ───────────────────────────────────────────────
const chartDefaults = {
  responsive:true, maintainAspectRatio:false,
  animation:{duration:400},
  plugins:{legend:{display:false}},
  scales:{
    x:{ticks:{color:'#64748b',maxTicksLimit:8,maxRotation:0,font:{size:10}},
       grid:{color:'rgba(255,255,255,0.04)'}},
    y:{ticks:{color:'#64748b',font:{size:10}},
       grid:{color:'rgba(255,255,255,0.06)'}}
  }
};

function makeChart(id, color, fill=true){
  const ctx = document.getElementById(id).getContext('2d');
  return new Chart(ctx,{
    type:'line',
    data:{labels:[],datasets:[{data:[],borderColor:color,borderWidth:2.5,
      pointRadius:3,pointBackgroundColor:color,
      backgroundColor: fill ? color.replace(')',',0.08)').replace('rgb','rgba') : 'transparent',
      fill:fill, tension:0.3}]},
    options:{...chartDefaults}
  });
}

function makeBarChart(id){
  const ctx = document.getElementById(id).getContext('2d');
  return new Chart(ctx,{
    type:'bar',
    data:{labels:[],datasets:[{data:[],backgroundColor:[],borderRadius:4}]},
    options:{...chartDefaults,
      scales:{...chartDefaults.scales,
        y:{...chartDefaults.scales.y, min:0, max:1.2,
           ticks:{callback:v=>v===0?'OK':v===1?'FAULT':'',color:'#64748b',font:{size:10}}}}}
  });
}

const chartTemp = makeChart('chartTemp','rgb(251,146,60)');
const chartCurr = makeChart('chartCurr','rgb(129,140,248)');
const chartVib  = makeBarChart('chartVib');

// Threshold lines as annotations (drawn manually via plugin-free approach)
function addThresholdLine(chart, value, color){
  const original = chart.options.plugins.annotation;
  // Use afterDraw instead
  chart.config.options.plugins.afterDraw = chart.config.options.plugins.afterDraw || {};
  const origAfterDraw = Chart.registry.plugins.get('annotation');
  // Simple approach: overlay via CSS or just note in label — skip annotation plugin,
  // draw a horizontal dashed reference inside datasets
  chart.data.datasets.push({
    data: [], type:'line',
    borderColor:color, borderWidth:1.5,
    borderDash:[6,4], pointRadius:0, fill:false,
    label:'threshold', order:0
  });
}

function setThresholdData(chart, value, count){
  if(chart.data.datasets.length > 1){
    chart.data.datasets[1].data = Array(count).fill(value);
    chart.data.datasets[1].label = 'Threshold '+value;
  }
}

// Add threshold datasets
chartTemp.data.datasets.push({
  data:[],type:'line',borderColor:'rgba(239,68,68,0.6)',borderWidth:1.5,
  borderDash:[6,4],pointRadius:0,fill:false,label:'50°C limit',order:0
});
chartCurr.data.datasets.push({
  data:[],type:'line',borderColor:'rgba(239,68,68,0.6)',borderWidth:1.5,
  borderDash:[6,4],pointRadius:0,fill:false,label:'5A limit',order:0
});

// ── Alert log (client-side history) ───────────────────────────
const alertHistory = [];
function pushAlert(alerts, timestamp){
  alerts.forEach(a=>{
    alertHistory.unshift({text:a, time:timestamp});
    if(alertHistory.length>50) alertHistory.pop();
  });
}

function renderAlerts(activeAlerts){
  const list = document.getElementById('alerts-list');
  if(alertHistory.length===0 && activeAlerts.length===0){
    list.innerHTML='<div class="alert-item alert-normal">&#x2705; No alerts &mdash; System operating normally</div>';
    return;
  }
  const items = alertHistory.slice(0,10).map(a=>{
    const cls = a.text.includes('CRITICAL') ? 'alert-critical'
              : a.text.includes('WARNING')  ? 'alert-warning'
              : 'alert-normal';
    const icon = a.text.includes('CRITICAL') ? '&#x1F534;'
               : a.text.includes('WARNING')  ? '&#x1F7E1;' : '&#x1F535;';
    return `<div class="alert-item ${cls}"><span class="alert-time">${a.time}</span>${icon} ${a.text}</div>`;
  }).join('');
  list.innerHTML = items || '<div class="alert-item alert-normal">&#x2705; No alerts &mdash; System operating normally</div>';
}

// ── Fetch & Update ─────────────────────────────────────────────
let firstLoad = true;

async function fetchAndUpdate(){
  try{
    const [statusRes, histRes] = await Promise.all([
      fetch('/api/status'),
      fetch('/api/data?limit=60')
    ]);
    const status = await statusRes.json();
    const hist   = await histRes.json();

    updateStatusCards(status);
    updateCharts(hist);
    updateStats(hist);
    updateTable(hist);
    pushAlert(status.active_alerts || [], new Date().toLocaleTimeString('en-GB'));
    renderAlerts(status.active_alerts || []);
    updateOverrideLabel(status.motor_override);

  }catch(e){
    console.warn('Fetch error:',e);
  }
  setTimeout(fetchAndUpdate, 5000);
}

function updateStatusCards(status){
  const motor = status.motor_status || 'OFF';
  const lr    = status.last_reading || {};
  const temp  = parseFloat(lr.temperature||0);
  const curr  = parseFloat(lr.current||0);
  const vib   = parseInt(lr.vibration||0);

  // Motor card
  const mc = document.getElementById('card-motor');
  mc.className = 'card ' + (motor==='ON' ? 'motor-on' : 'motor-off');
  document.getElementById('motor-icon').innerHTML = motor==='ON' ? '&#x1F7E2;' : '&#x1F534;';
  document.getElementById('motor-val').innerHTML =
    `<span style="color:${motor==='ON'?'#34d399':'#f87171'}">${motor}</span>`;

  // Temp card
  const tc = document.getElementById('card-temp');
  tc.className = 'card' + (temp>50?' danger':'');
  document.getElementById('temp-val').innerHTML =
    `<span style="color:${temp>50?'#f87171':'#fb923c'}">${temp.toFixed(1)}</span><span class="card-unit"> &deg;C</span>`;

  // Current card
  const cc = document.getElementById('card-curr');
  cc.className = 'card' + (curr>5?' danger':'');
  document.getElementById('curr-val').innerHTML =
    `<span style="color:${curr>5?'#f87171':'#a78bfa'}">${curr.toFixed(2)}</span><span class="card-unit"> A</span>`;

  // Vibration card
  const vc = document.getElementById('card-vib');
  vc.className = 'card' + (vib===1?' warn':'');
  document.getElementById('vib-val').innerHTML =
    vib===1
      ? '<span style="color:#fbbf24">FAULT</span>'
      : '<span style="color:#34d399">NORMAL</span>';
}

function updateCharts(hist){
  if(!hist||hist.length===0) return;
  const labels = hist.map(r=>r.timestamp ? r.timestamp.slice(11,19) : '');
  const temps  = hist.map(r=>parseFloat(r.temperature)||0);
  const currs  = hist.map(r=>parseFloat(r.current)||0);
  const vibs   = hist.map(r=>parseInt(r.vibration)||0);
  const vibColors = vibs.map(v=>v===1?'rgba(248,113,113,0.8)':'rgba(52,211,153,0.7)');

  chartTemp.data.labels = labels;
  chartTemp.data.datasets[0].data = temps;
  chartTemp.data.datasets[1].data = Array(labels.length).fill(50);
  chartTemp.update('none');

  chartCurr.data.labels = labels;
  chartCurr.data.datasets[0].data = currs;
  chartCurr.data.datasets[1].data = Array(labels.length).fill(5);
  chartCurr.update('none');

  chartVib.data.labels = labels;
  chartVib.data.datasets[0].data = vibs;
  chartVib.data.datasets[0].backgroundColor = vibColors;
  chartVib.update('none');
}

function updateStats(hist){
  if(!hist||hist.length===0) return;
  const temps  = hist.map(r=>parseFloat(r.temperature)||0);
  const currs  = hist.map(r=>parseFloat(r.current)||0);
  const faults = hist.filter(r=>parseInt(r.vibration)===1).length;
  const avg = arr => arr.reduce((a,b)=>a+b,0)/arr.length;

  document.getElementById('stat-total').textContent  = hist.length;
  document.getElementById('stat-avg-t').textContent  = avg(temps).toFixed(1);
  document.getElementById('stat-max-t').textContent  = Math.max(...temps).toFixed(1);
  document.getElementById('stat-avg-c').textContent  = avg(currs).toFixed(2);
  document.getElementById('stat-faults').textContent = faults;
}

function updateTable(hist){
  if(!hist||hist.length===0) return;
  const rows = hist.slice(-15).reverse().map(r=>{
    const motor = r.motor_status||'?';
    const badge = motor==='ON'
      ? '<span class="badge badge-on">ON</span>'
      : '<span class="badge badge-off">OFF</span>';
    const alert = (r.alert||'Normal').includes('WARNING')
      ? `<span class="badge badge-warn">${r.alert}</span>`
      : r.alert||'Normal';
    return `<tr>
      <td>${r.timestamp||''}</td>
      <td>${parseFloat(r.temperature||0).toFixed(1)}</td>
      <td>${parseFloat(r.current||0).toFixed(3)}</td>
      <td>${parseInt(r.vibration||0)===1?'<span style="color:#fbbf24">FAULT</span>':'OK'}</td>
      <td>${badge}</td>
      <td style="font-size:11px;max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${alert}</td>
    </tr>`;
  }).join('');
  document.getElementById('table-body').innerHTML = rows ||
    '<tr><td colspan="6" style="text-align:center;color:var(--muted)">No data yet</td></tr>';
}

function updateOverrideLabel(override){
  document.getElementById('override-mode').textContent =
    'Mode: ' + (override ? override+' (manual)' : 'AUTO');
}

// ── Motor Controls ─────────────────────────────────────────────
async function sendControl(cmd){
  try{
    const r = await fetch('/api/control',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({command:cmd})
    });
    const data = await r.json();
    const fb = document.getElementById('ctrl-feedback');
    fb.textContent = data.message || 'Done';
    setTimeout(()=>fb.textContent='',3000);
  }catch(e){
    document.getElementById('ctrl-feedback').textContent='Error: '+e.message;
  }
}

// ── Start ──────────────────────────────────────────────────────
fetchAndUpdate();
</script>
</body>
</html>
"""

# ── Helpers ───────────────────────────────────────────────────
def ensure_csv():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, "w", newline="") as f:
            csv.writer(f).writerow(CSV_HEADERS)


def append_to_csv(row: dict):
    with open(CSV_PATH, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=CSV_HEADERS).writerow(row)


def evaluate_automation(temp, current, vibration):
    with state_lock:
        override = system_state["motor_override"]

    alerts, motor_off = [], False

    if temp > TEMP_THRESHOLD:
        alerts.append(
            f"[CRITICAL] Overheating! Temperature {temp:.1f}C exceeds {TEMP_THRESHOLD}C - Motor SHUTDOWN"
        )
        motor_off = True

    if current > CURRENT_THRESHOLD:
        alerts.append(
            f"[CRITICAL] Overload! Current {current:.2f}A exceeds {CURRENT_THRESHOLD}A - Motor SHUTDOWN"
        )
        motor_off = True

    if vibration == 1:
        alerts.append("[WARNING]  Vibration fault detected - check motor bearings")

    if override == "OFF":
        return "OFF", alerts
    if override == "ON" and not motor_off:
        return "ON", alerts
    if override == "ON" and motor_off:
        alerts.append("[INFO] Manual ON ignored - safety threshold breached")

    return "OFF" if motor_off else "ON", alerts


# ── Routes ────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/data", methods=["POST"])
def receive_data():
    payload = request.get_json(force=True)
    if not payload:
        return jsonify({"error": "No JSON payload"}), 400
    try:
        temperature = float(payload["temperature"])
        current     = float(payload["current"])
        vibration   = int(payload.get("vibration", 0))
    except (KeyError, ValueError) as e:
        return jsonify({"error": f"Invalid payload: {e}"}), 400

    motor_status, alerts = evaluate_automation(temperature, current, vibration)
    timestamp  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    alert_str  = "; ".join(alerts) if alerts else "Normal"

    row = {
        "timestamp":    timestamp,
        "temperature":  round(temperature, 2),
        "current":      round(current, 3),
        "vibration":    vibration,
        "motor_status": motor_status,
        "alert":        alert_str,
    }
    append_to_csv(row)

    with state_lock:
        system_state["motor_status"]  = motor_status
        system_state["active_alerts"] = alerts
        system_state["last_reading"]  = row
        data_history.append(row)
        # Keep only last 500 rows in memory
        if len(data_history) > 500:
            del data_history[:len(data_history) - 500]

    print(f"  [{timestamp}] T={temperature:.1f}C  I={current:.2f}A  "
          f"V={vibration}  Motor={motor_status}  Alerts={len(alerts)}")

    return jsonify({
        "status":       "ok",
        "motor_status": motor_status,
        "alerts":       alerts,
        "timestamp":    timestamp,
    }), 200


@app.route("/api/data", methods=["GET"])
def get_data():
    limit = request.args.get("limit", MAX_ROWS_RETURN, type=int)
    with state_lock:
        return jsonify(data_history[-limit:])


@app.route("/api/status", methods=["GET"])
def get_status():
    with state_lock:
        return jsonify({
            "motor_status":   system_state["motor_status"],
            "active_alerts":  system_state["active_alerts"],
            "last_reading":   system_state["last_reading"],
            "motor_override": system_state["motor_override"],
        })


@app.route("/api/control", methods=["POST"])
def control_motor():
    payload = request.get_json(force=True)
    command = payload.get("command", "").upper()
    if command not in ("ON", "OFF", "AUTO"):
        return jsonify({"error": "Use ON, OFF, or AUTO"}), 400
    with state_lock:
        if command == "AUTO":
            system_state["motor_override"] = None
            msg = "Motor control set to AUTO"
        else:
            system_state["motor_override"] = command
            msg = f"Motor manually set to {command}"
    print(f"  [CONTROL] {msg}")
    return jsonify({"status": "ok", "message": msg})


# ── Built-in Simulator (background thread) ────────────────────
SCENARIOS = [
    {"name": "Normal",     "temp": (25.0, 45.0), "curr": (1.0, 4.5), "vib": 0},
    {"name": "Overheat",   "temp": (51.0, 80.0), "curr": (2.0, 4.0), "vib": 0},
    {"name": "Overload",   "temp": (30.0, 45.0), "curr": (5.1, 8.0), "vib": 0},
    {"name": "Vibration",  "temp": (30.0, 45.0), "curr": (2.0, 4.0), "vib": 1},
]
SCENARIO_DURATION = 10  # sends per scenario
SIMULATOR_INTERVAL = 5  # seconds between sends


def run_simulator():
    """Background thread that simulates ESP32 sensor data."""
    send_count = 0
    while True:
        try:
            idx = (send_count // SCENARIO_DURATION) % len(SCENARIOS)
            sc  = SCENARIOS[idx]

            temp = round(random.uniform(*sc["temp"]) + random.gauss(0, 0.3), 2)
            curr = round(random.uniform(*sc["curr"]) + random.gauss(0, 0.05), 3)
            temp = max(20.0, min(100.0, temp))
            curr = max(0.0, min(15.0, curr))
            vib  = sc["vib"]

            motor_status, alerts = evaluate_automation(temp, curr, vib)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            alert_str = "; ".join(alerts) if alerts else "Normal"

            row = {
                "timestamp":    timestamp,
                "temperature":  round(temp, 2),
                "current":      round(curr, 3),
                "vibration":    vib,
                "motor_status": motor_status,
                "alert":        alert_str,
            }

            try:
                append_to_csv(row)
            except Exception:
                pass  # CSV may not be writable on cloud

            with state_lock:
                system_state["motor_status"]  = motor_status
                system_state["active_alerts"] = alerts
                system_state["last_reading"]  = row
                data_history.append(row)
                if len(data_history) > 500:
                    del data_history[:len(data_history) - 500]

            print(f"  [SIM][{timestamp}] {sc['name']:10s} T={temp:.1f}C  "
                  f"I={curr:.2f}A  V={vib}  Motor={motor_status}")
        except Exception as e:
            print(f"  [SIMULATOR ERROR] {e}")

        send_count += 1
        time.sleep(SIMULATOR_INTERVAL)


# ── Startup & Debug ───────────────────────────────────────────
simulator_started = False
thread_lock = threading.Lock()

@app.before_request
def start_simulator_on_first_request():
    global simulator_started
    if not simulator_started:
        with thread_lock:
            if not simulator_started:
                try:
                    ensure_csv()
                except Exception as e:
                    print(f"  [CSV WARNING] Could not verify CSV setup: {e}")
                sim_thread = threading.Thread(
                    target=run_simulator, daemon=True, name="SimulatorThread"
                )
                sim_thread.start()
                simulator_started = True
                print("  [OK] Simulator thread started inside worker process")


@app.route("/api/debug", methods=["GET"])
def get_debug_info():
    import threading
    threads = [t.name for t in threading.enumerate()]
    return jsonify({
        "threads": threads,
        "history_len": len(data_history),
        "system_state": system_state,
        "csv_path_exists": os.path.exists(CSV_PATH),
        "simulator_started_flag": simulator_started,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 60)
    print("  Industrial Motor Monitoring -- Flask Server")
    print(f"  Dashboard : http://localhost:{port}")
    print(f"  API       : http://localhost:{port}/api/")
    print("=" * 60)
    app.run(host="0.0.0.0", port=port, debug=False)
