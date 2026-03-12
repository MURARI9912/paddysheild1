"""
PaddyShield - Proactive Paddy Disease Risk Alert System
Phase 1: Weather Fetching + Risk Logic
Founder: Murari - Village Tech Initiative
"""

import urllib.request
import json
from datetime import datetime

# ─────────────────────────────────────────────
# STEP 1: FETCH WEATHER DATA (Open-Meteo API)
# ─────────────────────────────────────────────
def fetch_weather(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&daily=precipitation_sum,relative_humidity_2m_max,temperature_2m_max,temperature_2m_min"
        f"&timezone=Asia%2FKolkata&forecast_days=7"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
        daily = data["daily"]
        avg_humidity   = sum(daily["relative_humidity_2m_max"]) / 7
        total_rainfall = sum(daily["precipitation_sum"])
        avg_temp_max   = sum(daily["temperature_2m_max"]) / 7
        avg_temp_min   = sum(daily["temperature_2m_min"]) / 7
        return {
            "humidity":  round(avg_humidity, 1),
            "rainfall":  round(total_rainfall, 1),
            "temp_max":  round(avg_temp_max, 1),
            "temp_min":  round(avg_temp_min, 1),
            "source":    "live"
        }
    except Exception:
        return {
            "humidity":  85.0,
            "rainfall":  42.0,
            "temp_max":  33.0,
            "temp_min":  24.0,
            "source":    "simulated"
        }

# ─────────────────────────────────────────────
# STEP 2: DISEASE RISK ENGINE
# ─────────────────────────────────────────────
def blast_risk(humidity, rainfall, temp_max, temp_min):
    score = 0
    if humidity >= 90:        score += 3
    elif humidity >= 80:      score += 2
    if 20 <= temp_min <= 28:  score += 2
    if 24 <= temp_max <= 30:  score += 1
    if 20 <= rainfall <= 80:  score += 2
    elif rainfall > 80:       score += 1
    return score

def brown_spot_risk(humidity, rainfall, temp_max):
    score = 0
    if humidity >= 85:        score += 3
    elif humidity >= 75:      score += 2
    if 28 <= temp_max <= 35:  score += 2
    elif 25 <= temp_max < 28: score += 1
    if rainfall > 50:         score += 2
    elif rainfall > 20:       score += 1
    return score

def sheath_blight_risk(humidity, rainfall, temp_max):
    score = 0
    if humidity >= 95:        score += 3
    elif humidity >= 85:      score += 2
    if temp_max >= 32:        score += 2
    elif temp_max >= 28:      score += 1
    if rainfall > 60:         score += 2
    elif rainfall > 30:       score += 1
    return score

def score_to_level(score):
    if score >= 6:   return "🔴 HIGH"
    elif score >= 3: return "🟡 MEDIUM"
    else:            return "🟢 LOW"

def assess_risks(weather):
    h  = weather["humidity"]
    r  = weather["rainfall"]
    tm = weather["temp_max"]
    tn = weather["temp_min"]
    blast  = blast_risk(h, r, tm, tn)
    brown  = brown_spot_risk(h, r, tm)
    sheath = sheath_blight_risk(h, r, tm)
    return {
        "Blast Disease": (blast,  score_to_level(blast)),
        "Brown Spot":    (brown,  score_to_level(brown)),
        "Sheath Blight": (sheath, score_to_level(sheath)),
    }

ADVICE = {
    "Blast Disease": {
        "HIGH":   "Spray recommended fungicide (Tricyclazole). Inspect leaves daily.",
        "MEDIUM": "Monitor fields closely. Avoid excess nitrogen fertiliser.",
        "LOW":    "No immediate action needed. Continue regular observation.",
    },
    "Brown Spot": {
        "HIGH":   "Apply Mancozeb or Propiconazole. Check soil nutrition levels.",
        "MEDIUM": "Ensure balanced fertilisation. Watch for brown oval spots on leaves.",
        "LOW":    "Conditions are safe. Maintain good crop spacing.",
    },
    "Sheath Blight": {
        "HIGH":   "Apply Hexaconazole or Validamycin. Drain excess water from fields.",
        "MEDIUM": "Reduce plant density if possible. Avoid over-irrigation.",
        "LOW":    "No action needed. Keep drainage channels clear.",
    },
}

def generate_advisory(village_name, weather, risks):
    week = datetime.now().strftime("%d %b %Y")
    lines = ["="*52, f"🌾 PaddyShield Weekly Alert — {week}",
             f"📍 Village: {village_name}", "-"*52]
    for disease, (score, level) in risks.items():
        label = level.split()[-1]
        lines.append(f"  {level}  {disease}: {ADVICE[disease][label]}")
    lines += ["-"*52, "🤝 PaddyShield — Protecting Farmers, Proactively.", "="*52]
    return "\n".join(lines)
