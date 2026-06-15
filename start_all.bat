@echo off
title Industrial Motor Monitoring System — Launcher
color 0A

echo.
echo ============================================================
echo   Industrial Motor Monitoring System — Starting All Components
echo ============================================================
echo.

REM ── Navigate to the motor_monitor directory ──
cd /d "%~dp0"

REM ── Locate Python: prefer PATH python, fall back to known location ──
set PYTHON_EXE=python
python --version >nul 2>&1
if errorlevel 1 (
    set PYTHON_EXE=C:\Users\ranja\AppData\Local\Python\pythoncore-3.14-64\python.exe
    "%PYTHON_EXE%" --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python not found! Please install Python 3.x and add to PATH.
        pause
        exit /b 1
    )
)

REM ── Locate streamlit ──
set STREAMLIT_EXE=C:\Users\ranja\AppData\Local\Python\pythoncore-3.14-64\Scripts\streamlit.exe
if not exist "%STREAMLIT_EXE%" (
    set STREAMLIT_EXE=streamlit
)

echo Python  : %PYTHON_EXE%
echo Streamlit: %STREAMLIT_EXE%
echo.

echo [1/4] Dependencies should already be installed.
echo       If not, run:  pip install flask flask-cors streamlit plotly pandas requests
echo.

REM ── Start Flask Server ──
echo [2/4] Starting Flask Server on http://localhost:5000 ...
start "Flask Server — Motor Monitor" cmd /k "color 0B && echo ============================================ && echo   Flask Server  [http://localhost:5000] && echo ============================================ && "%PYTHON_EXE%" server\app.py"
timeout /t 3 /nobreak >nul

REM ── Start ESP32 Simulator (waits 3s for server to be ready) ──
echo [3/4] Starting ESP32 Simulator ...
start "ESP32 Simulator — Motor Monitor" cmd /k "color 0E && echo ============================================ && echo   ESP32 Simulator ^(sending data every 5s^) && echo ============================================ && timeout /t 3 /nobreak >nul && "%PYTHON_EXE%" simulator\esp32_simulator.py"

REM ── Start Streamlit Dashboard ──
echo [4/4] Starting Streamlit Dashboard on http://localhost:8501 ...
start "IoT Dashboard — Motor Monitor" cmd /k "color 0D && echo ============================================ && echo   IoT Dashboard  [http://localhost:8501] && echo ============================================ && "%STREAMLIT_EXE%" run dashboard\dashboard.py --server.port 8501"

echo.
echo ============================================================
echo   ALL COMPONENTS STARTED!
echo.
echo   Flask Server    ->  http://localhost:5000
echo   IoT Dashboard   ->  http://localhost:8501
echo.
echo   Order of startup:
echo     1. Flask Server  (starts immediately)
echo     2. ESP32 Simulator (starts after 3s delay)
echo     3. Streamlit Dashboard (opens in browser)
echo.
echo   Close the 3 terminal windows to stop all components.
echo ============================================================
echo.

REM ── Auto-open dashboard in browser after 6 seconds ──
timeout /t 6 /nobreak >nul
start "" "http://localhost:8501"

echo Dashboard opened in browser. This window can be closed.
pause
