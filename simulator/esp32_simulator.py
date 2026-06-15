"""
============================================================
Industrial Motor Monitoring System -- ESP32 Simulator
============================================================
Simulates an ESP32 microcontroller collecting sensor data
and transmitting it to the Flask server every 5 seconds.

Cycles through four scenarios from PRD Section 11:
  1. Normal Operation   (Temp 25-45 C, Current 1-4.5A, Vib 0)
  2. Overheating        (Temp 51-80 C, Current 2-4A,   Vib 0)
  3. Overload           (Temp 30-45 C, Current 5.1-8A, Vib 0)
  4. Vibration Fault    (Temp 30-45 C, Current 2-4A,   Vib 1)
============================================================
"""

import io
import random
import sys
import time
from datetime import datetime

import requests

# Force UTF-8 output on Windows to avoid charmap errors
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Configuration ────────────────────────────────────────────
SERVER_URL        = "http://localhost:5000/api/data"
SEND_INTERVAL     = 5   # seconds between transmissions
SCENARIO_DURATION = 10  # how many sends before cycling to next scenario

# ANSI colour codes
RED     = "\033[91m"
YELLOW  = "\033[93m"
GREEN   = "\033[92m"
CYAN    = "\033[96m"
BLUE    = "\033[94m"
MAGENTA = "\033[95m"
RESET   = "\033[0m"
BOLD    = "\033[1m"


# ── Scenario Definitions (ASCII icons only) ──────────────────
SCENARIOS = [
    {
        "name":        "Normal Operation",
        "color":       GREEN,
        "icon":        "[OK]",
        "temp_range":  (25.0, 45.0),
        "curr_range":  (1.0, 4.5),
        "vibration":   0,
        "description": "Motor running within safe parameters",
    },
    {
        "name":        "Overheating",
        "color":       RED,
        "icon":        "[HOT]",
        "temp_range":  (51.0, 80.0),
        "curr_range":  (2.0, 4.0),
        "vibration":   0,
        "description": "Temperature > 50 C threshold -> Motor SHUTDOWN",
    },
    {
        "name":        "Overload",
        "color":       YELLOW,
        "icon":        "[OVL]",
        "temp_range":  (30.0, 45.0),
        "curr_range":  (5.1, 8.0),
        "vibration":   0,
        "description": "Current > 5A threshold -> Motor SHUTDOWN",
    },
    {
        "name":        "Vibration Fault",
        "color":       MAGENTA,
        "icon":        "[VIB]",
        "temp_range":  (30.0, 45.0),
        "curr_range":  (2.0, 4.0),
        "vibration":   1,
        "description": "Vibration fault detected -> Warning generated",
    },
]


def generate_sensor_reading(scenario: dict) -> dict:
    """
    Generate a realistic sensor reading for the given scenario.
    Adds small random noise to simulate real sensor behavior.
    """
    temp      = round(random.uniform(*scenario["temp_range"]) + random.gauss(0, 0.3), 2)
    current   = round(random.uniform(*scenario["curr_range"]) + random.gauss(0, 0.05), 3)
    vibration = scenario["vibration"]

    # Keep values physically plausible
    temp    = max(20.0, min(100.0, temp))
    current = max(0.0,  min(15.0,  current))

    return {"temperature": temp, "current": current, "vibration": vibration}


def print_banner():
    print(f"\n{BOLD}{CYAN}{'='*62}{RESET}")
    print(f"{BOLD}{CYAN}  ESP32 Industrial Motor Simulator{RESET}")
    print(f"{BOLD}{CYAN}  Target : {SERVER_URL}{RESET}")
    print(f"{BOLD}{CYAN}  Interval: {SEND_INTERVAL}s  |  Scenario duration: {SCENARIO_DURATION} sends each{RESET}")
    print(f"{BOLD}{CYAN}{'='*62}{RESET}")
    print(f"\n  Scenarios cycling:")
    for i, s in enumerate(SCENARIOS, 1):
        print(f"  {s['color']}{s['icon']} {i}. {s['name']}{RESET}  --  {s['description']}")
    print(f"\n  Press Ctrl+C to stop.\n")
    sys.stdout.flush()


def print_reading(scenario, reading, response_data, send_count, cycle):
    ts     = datetime.now().strftime("%H:%M:%S")
    motor  = response_data.get("motor_status", "?")
    alerts = response_data.get("alerts", [])

    motor_color = GREEN if motor == "ON" else RED
    motor_tag   = "[ON] " if motor == "ON" else "[OFF]"

    print(f"\n  {BLUE}[{ts}]{RESET}  Cycle {cycle}  |  "
          f"Send #{send_count % SCENARIO_DURATION + 1}/{SCENARIO_DURATION}")
    print(f"  {scenario['color']}{scenario['icon']} Scenario: {BOLD}{scenario['name']}{RESET}")
    print(f"  {'-'*52}")
    print(f"  Temp        : {BOLD}{reading['temperature']:.2f} C{RESET}")
    print(f"  Current     : {BOLD}{reading['current']:.3f} A{RESET}")
    print(f"  Vibration   : {BOLD}{'FAULT' if reading['vibration'] else 'OK'}{RESET}")
    print(f"  Motor Status: {motor_color}{BOLD}{motor_tag} {motor}{RESET}")

    for alert in alerts:
        if "CRITICAL" in alert:
            print(f"  {RED}!! {alert}{RESET}")
        elif "WARNING" in alert:
            print(f"  {YELLOW}>> {alert}{RESET}")
        else:
            print(f"  {CYAN}-- {alert}{RESET}")

    sys.stdout.flush()


def wait_for_server(max_retries=10):
    """Wait until the Flask server is reachable."""
    print(f"  {CYAN}Connecting to server at {SERVER_URL} ...{RESET}")
    sys.stdout.flush()
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.post(
                SERVER_URL,
                json={"temperature": 25.0, "current": 1.0, "vibration": 0},
                timeout=3,
            )
            if r.status_code == 200:
                print(f"  {GREEN}[CONNECTED] Server ready!{RESET}\n")
                sys.stdout.flush()
                return True
        except requests.exceptions.ConnectionError:
            print(f"  {YELLOW}  Attempt {attempt}/{max_retries} -- server not ready yet ...{RESET}")
            sys.stdout.flush()
            time.sleep(2)
    print(f"  {RED}[ERROR] Could not connect. Is Flask running on port 5000?{RESET}")
    sys.stdout.flush()
    return False


def main():
    print_banner()

    if not wait_for_server():
        sys.exit(1)

    send_count = 0
    cycle      = 1

    while True:
        scenario_index = (send_count // SCENARIO_DURATION) % len(SCENARIOS)
        scenario       = SCENARIOS[scenario_index]
        reading        = generate_sensor_reading(scenario)

        try:
            response      = requests.post(SERVER_URL, json=reading, timeout=5)
            response_data = response.json()
            print_reading(scenario, reading, response_data, send_count, cycle)
        except requests.exceptions.ConnectionError:
            print(f"  {RED}[ERROR] Connection lost! Retrying ...{RESET}")
            sys.stdout.flush()
        except Exception as e:
            print(f"  {RED}[ERROR] {e}{RESET}")
            sys.stdout.flush()

        send_count += 1

        if send_count % (SCENARIO_DURATION * len(SCENARIOS)) == 0:
            cycle += 1
            print(f"\n  {CYAN}{'='*52}")
            print(f"  >> Starting Cycle {cycle} -- all 4 scenarios repeat")
            print(f"  {'='*52}{RESET}")
            sys.stdout.flush()

        time.sleep(SEND_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n  {YELLOW}ESP32 Simulator stopped.{RESET}\n")
        sys.stdout.flush()
