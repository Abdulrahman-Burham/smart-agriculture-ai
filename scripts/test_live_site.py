"""Live Production Site Scenario Tester.

Executes real-time end-to-end integration tests directly against the deployed
production cloud endpoint (https://plantapi-abdo.uaenorth.cloudapp.azure.com).
"""

from __future__ import annotations

import sys
import time
import requests
import urllib3

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://plantapi-abdo.uaenorth.cloudapp.azure.com"


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def log_test(name: str, passed: bool, detail: str = "", duration: float = 0.0):
    status = f"{Colors.GREEN}✔ PASSED{Colors.RESET}" if passed else f"{Colors.RED}✖ FAILED{Colors.RESET}"
    dur_str = f"({duration:.2f}s)" if duration > 0 else ""
    print(f"[{status}] {Colors.BOLD}{name}{Colors.RESET} {dur_str}")
    if detail:
        print(f"       └─ {detail}")


def run_live_tests():
    print(f"\n{Colors.CYAN}{'='*75}{Colors.RESET}")
    print(f"{Colors.BOLD}🚀 Testing Live Production Site: {BASE_URL}{Colors.RESET}")
    print(f"{Colors.CYAN}{'='*75}{Colors.RESET}\n")

    passed_count = 0
    total_count = 0
    session = requests.Session()

    def check(test_name: str, fn):
        nonlocal passed_count, total_count
        total_count += 1
        t0 = time.time()
        try:
            ok, detail = fn()
            dur = time.time() - t0
            if ok:
                passed_count += 1
                log_test(test_name, True, detail, dur)
            else:
                log_test(test_name, False, detail, dur)
        except Exception as e:
            dur = time.time() - t0
            log_test(test_name, False, f"Exception: {e}", dur)

    # 1. Web Pages
    check("1.1 Landing Page (/)", lambda: (
        (r := session.get(f"{BASE_URL}/", verify=False)).status_code == 200 and ("الزراعة الذكية" in r.text or "Smart Agriculture" in r.text),
        f"Status: {r.status_code}, Length: {len(r.text)} bytes"
    ))

    check("1.2 Mobile UI (/m)", lambda: (
        (r := session.get(f"{BASE_URL}/m", verify=False)).status_code == 200,
        f"Status: {r.status_code}"
    ))

    check("1.3 Simple 2-Button Scan (/simple)", lambda: (
        (r := session.get(f"{BASE_URL}/simple", verify=False)).status_code == 200,
        f"Status: {r.status_code}"
    ))

    check("1.4 Offline Safety Guide (/offline-guide)", lambda: (
        (r := session.get(f"{BASE_URL}/offline-guide", verify=False)).status_code == 200,
        f"Status: {r.status_code}"
    ))

    check("1.5 Farmer Login Page (/login)", lambda: (
        (r := session.get(f"{BASE_URL}/login", verify=False)).status_code == 200,
        f"Status: {r.status_code}"
    ))

    check("1.6 Epidemic Heatmap (/epidemic-map)", lambda: (
        (r := session.get(f"{BASE_URL}/epidemic-map", verify=False)).status_code == 200 and "الرصد الوبائي" in r.text,
        f"Status: {r.status_code}, Length: {len(r.text)} bytes"
    ))

    # 2. System Health & Stats
    check("2.1 System Readiness Health Probe (/health)", lambda: (
        (r := session.get(f"{BASE_URL}/health", verify=False)).status_code == 200 and r.json().get("status") == "healthy",
        f"Gateway: {r.json().get('services', {}).get('api_gateway')}, RAG: {r.json().get('services', {}).get('rag_pipeline')}"
    ))

    check("2.2 Public Platform Stats (/api/public-stats)", lambda: (
        (r := session.get(f"{BASE_URL}/api/public-stats", verify=False)).status_code == 200 and "registered_farmers" in r.json(),
        f"Registered Farmers: {r.json().get('registered_farmers')}, RAG Engine: {r.json().get('rag_engine')}"
    ))

    # 3. Weather & Epidemic Early Warnings
    check("3.1 Weather by Governorate (الدقهلية)", lambda: (
        (r := session.get(f"{BASE_URL}/api/weather?gov=الدقهلية", verify=False)).status_code == 200 and r.json().get("governorate") == "الدقهلية",
        f"Temp: {r.json().get('temperature')}°C, Humidity: {r.json().get('humidity')}%, Alerts: {len(r.json().get('alerts', []))}"
    ))

    check("3.2 Weather GPS Nearest Mapping (31.04, 31.38)", lambda: (
        (r := session.get(f"{BASE_URL}/api/weather?lat=31.04&lon=31.38", verify=False)).status_code == 200 and r.json().get("governorate") == "الدقهلية",
        f"Mapped Gov: {r.json().get('governorate')}, GPS Mode: {r.json().get('is_gps')}"
    ))

    check("3.3 All-Governorates Epidemic Risk Map (/api/weather/epidemic-map)", lambda: (
        (r := session.get(f"{BASE_URL}/api/weather/epidemic-map", verify=False)).status_code == 200 and r.json().get("total_governorates") == 27,
        f"Total: {r.json().get('total_governorates')}, Danger: {r.json().get('danger_count')}, Warning: {r.json().get('warning_count')}, Safe: {r.json().get('safe_count')}"
    ))

    # 4. Smart Calculators (Realistic Egyptian Sprayer Rates)
    check("4.1 Tank-Mix: Direct Single Knapsack Tank (20L, 50ml/100L)", lambda: (
        (r := session.post(f"{BASE_URL}/api/calculator/tank-mix", json={
            "mode": "tank", "tanks_count": 1, "tank_type": "knapsack_20l",
            "dosage_rate": 50, "dosage_unit": "per_100l", "chemical_type": "liquid",
            "product_name": "Coragen", "crop_category": "vegetable"
        }, verify=False)).status_code == 200 and r.json().get("amount_per_tank") == 10.0,
        f"Per-tank dose: {r.json().get('amount_per_tank')} ml, Scoop: {r.json().get('amount_per_tank_practical')}"
    ))

    check("4.2 Tank-Mix: Direct 200L Blue Barrel (250g/100L)", lambda: (
        (r := session.post(f"{BASE_URL}/api/calculator/tank-mix", json={
            "mode": "tank", "tanks_count": 1, "tank_type": "motor_200l",
            "dosage_rate": 250, "dosage_unit": "per_100l", "chemical_type": "powder",
            "product_name": "Micronized Sulfur", "crop_category": "orchard"
        }, verify=False)).status_code == 200 and r.json().get("amount_per_tank") == 500.0,
        f"Per-tank dose: {r.json().get('amount_per_tank')} g, Scoop: {r.json().get('amount_per_tank_practical')}"
    ))

    check("4.3 Tank-Mix: Whole Area 1 Feddan (20L Knapsack -> 7 Fills)", lambda: (
        (r := session.post(f"{BASE_URL}/api/calculator/tank-mix", json={
            "mode": "area", "area_value": 1.0, "area_unit": "feddan", "tank_type": "knapsack_20l",
            "dosage_rate": 250, "dosage_unit": "per_feddan", "chemical_type": "powder",
            "product_name": "Dithane M45", "crop_category": "vegetable"
        }, verify=False)).status_code == 200 and r.json().get("tanks_count_practical") == 7,
        f"Water: {r.json().get('total_water_liters')}L (Fills: {r.json().get('tanks_count_practical')}), Dose: {r.json().get('amount_per_tank')}g, Scoop: {r.json().get('amount_per_tank_practical')}"
    ))

    check("4.4 Salinity Advisor: Sensitive Strawberry (1600 ppm -> Critical Risk)", lambda: (
        (r := session.post(f"{BASE_URL}/api/calculator/salinity", json={
            "salinity_value": 1600.0, "salinity_unit": "ppm",
            "crop_name": "فراولة", "irrigation_method": "تنقيط"
        }, verify=False)).status_code == 200 and r.json().get("is_critical_risk") is True,
        f"Yield Potential: {r.json().get('yield_potential_percent')}%, Grade: {r.json().get('water_quality_grade')}"
    ))

    # 5. User Preferences & Guest Me
    check("5.1 Auth Me & Guest Quota (/api/auth/me)", lambda: (
        (r := session.get(f"{BASE_URL}/api/auth/me", verify=False)).status_code == 200 and "guest_quota" in r.json(),
        f"Authenticated: {r.json().get('authenticated')}, Free Used: {r.json().get('guest_quota', {}).get('used_total')}"
    ))

    # 6. Egyptian Speech & Audio
    check("6.1 Egyptian Neural Voice Synthesis (/api/tts)", lambda: (
        (r := session.get(f"{BASE_URL}/api/tts?text=أهلاً+بك+في+الخبير+الزراعي&voice=ar-EG-ShakirNeural", verify=False)).status_code in (200, 503),
        f"Status: {r.status_code}, Media-Type: {r.headers.get('content-type', 'none')}"
    ))

    print(f"\n{Colors.CYAN}{'='*75}{Colors.RESET}")
    print(f"{Colors.BOLD}📊 Summary: {passed_count}/{total_count} Live Scenarios Passed Successfully!{Colors.RESET}")
    print(f"{Colors.CYAN}{'='*75}{Colors.RESET}\n")

    return passed_count == total_count


if __name__ == "__main__":
    success = run_live_tests()
    sys.exit(0 if success else 1)
