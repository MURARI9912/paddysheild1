"""
PaddyShield - Cloud App Server
Local:  python app.py        → http://localhost:5000
Cloud:  auto-started by gunicorn via Procfile
"""

from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
import json, os
from datetime import datetime
from paddyshield import fetch_weather, assess_risks, generate_advisory, ADVICE

load_dotenv()  # loads .env locally; Railway uses its own env vars

app = Flask(__name__)

# On cloud Railway gives ephemeral filesystem — use /tmp
# Locally save in project folder
IS_CLOUD   = os.environ.get("RAILWAY_ENVIRONMENT") is not None
DATA_FILE  = "/tmp/farmers.json"        if IS_CLOUD else "farmers.json"
LINKS_FILE = "/tmp/telegram_links.json" if IS_CLOUD else "telegram_links.json"

# Bot token from environment (never hardcoded on cloud)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# ── helpers ──────────────────────────────────────
def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_farmers():  return load_json(DATA_FILE, [])
def save_farmers(d): save_json(DATA_FILE, d)

VILLAGE_COORDS = {
    "quthbullapur": (17.55,  78.42),
    "medak":        (17.975, 78.263),
    "nalgonda":     (17.057, 79.267),
    "hyderabad":    (17.385, 78.486),
    "warangal":     (17.977, 79.598),
    "karimnagar":   (18.438, 79.128),
    "nizamabad":    (18.672, 78.094),
    "khammam":      (17.247, 80.150),
    "sangareddy":   (17.619, 78.085),
    "siddipet":     (18.102, 78.852),
    "suryapet":     (17.139, 79.623),
    "mahabubnagar": (16.738, 77.983),
    "adilabad":     (19.664, 78.532),
    "mancherial":   (18.869, 79.454),
    "jagtial":      (18.795, 78.914),
    "peddapalli":   (18.617, 79.383),
}

def get_coords(village):
    key = village.strip().lower()
    for k, v in VILLAGE_COORDS.items():
        if k in key or key in k:
            return v
    return (17.385, 78.486)

# ── routes ───────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/health")
def health():
    return jsonify({"status": "ok", "app": "PaddyShield", "cloud": IS_CLOUD})

@app.route("/api/farmers", methods=["GET"])
def get_farmers():
    return jsonify(load_farmers())

@app.route("/api/farmers", methods=["POST"])
def add_farmer():
    data    = request.json
    farmers = load_farmers()
    farmer  = {
        "id":         int(datetime.now().timestamp() * 1000),
        "name":       data["name"],
        "phone":      data["phone"],
        "village":    data["village"],
        "mandal":     data["mandal"],
        "stage":      data["stage"],
        "acres":      data["acres"],
        "registered": datetime.now().strftime("%d %b %Y"),
    }
    farmers.append(farmer)
    save_farmers(farmers)
    return jsonify({"ok": True, "farmer": farmer})

@app.route("/api/farmers/<int:fid>", methods=["DELETE"])
def delete_farmer(fid):
    farmers = [f for f in load_farmers() if f["id"] != fid]
    save_farmers(farmers)
    return jsonify({"ok": True})

@app.route("/api/risk/<int:fid>")
def get_risk(fid):
    farmers = load_farmers()
    farmer  = next((f for f in farmers if f["id"] == fid), None)
    if not farmer:
        return jsonify({"error": "not found"}), 404
    lat, lon = get_coords(farmer["village"])
    weather  = fetch_weather(lat, lon)
    risks    = assess_risks(weather)
    result   = {
        "farmer":    farmer,
        "weather":   weather,
        "risks":     [],
        "generated": datetime.now().strftime("%d %b %Y, %I:%M %p"),
    }
    for disease, (score, level) in risks.items():
        label = level.split()[-1]
        result["risks"].append({
            "disease": disease, "score": score, "level": label,
            "emoji":   "🔴" if label=="HIGH" else "🟡" if label=="MEDIUM" else "🟢",
            "advice":  ADVICE[disease][label],
        })
    lines = [
        "🌾 *PaddyShield Weekly Alert*",
        f"📍 Village: {farmer['village']}, {farmer['mandal']}",
        f"👤 Farmer: {farmer['name']}",
        f"🌱 Stage: {farmer['stage'].replace('_',' ').title()}",
        f"📅 {result['generated']}", "",
        "📊 *Weather (7-day)*",
        f"  Humidity: {weather['humidity']}%",
        f"  Rainfall: {weather['rainfall']} mm",
        f"  Temp: {weather['temp_min']}°C – {weather['temp_max']}°C", "",
        "⚠️ *Disease Risk*",
    ]
    for r in result["risks"]:
        lines.append(f"  {r['emoji']} {r['disease']}: *{r['level']}*")
    lines += ["", "✅ *Action*"]
    for r in result["risks"]:
        if r["level"] in ("HIGH","MEDIUM"):
            lines.append(f"  [{r['disease']}] {r['advice']}")
    lines += ["","📞 Follow govt pesticide dosage guidelines.",
              "🤝 PaddyShield — Protecting Farmers, Proactively."]
    result["whatsapp_text"] = "\n".join(lines)
    return jsonify(result)

@app.route("/api/risk/all")
def get_all_risks():
    farmers = load_farmers()
    results = []
    for farmer in farmers:
        lat, lon = get_coords(farmer["village"])
        weather  = fetch_weather(lat, lon)
        risks    = assess_risks(weather)
        summary  = {"farmer": farmer, "weather": weather, "risks": []}
        for disease, (score, level) in risks.items():
            label = level.split()[-1]
            summary["risks"].append({
                "disease": disease, "score": score, "level": label,
                "emoji": "🔴" if label=="HIGH" else "🟡" if label=="MEDIUM" else "🟢",
                "advice": ADVICE[disease][label],
            })
        results.append(summary)
    return jsonify(results)

@app.route("/api/send_alert/<int:fid>", methods=["POST"])
def send_telegram_alert(fid):
    farmers = load_farmers()
    farmer  = next((f for f in farmers if f["id"] == fid), None)
    if not farmer:
        return jsonify({"error": "farmer not found"}), 404
    try:
        from bot import send_message, build_alert
        phone   = farmer.get("phone","").replace("+91","").replace(" ","").strip()
        links   = load_json(LINKS_FILE, {})
        chat_id = links.get(phone)
        if not chat_id:
            return jsonify({"ok": False, "error": "Farmer has not linked Telegram yet"})
        lat, lon = get_coords(farmer["village"])
        weather  = fetch_weather(lat, lon)
        risks    = assess_risks(weather)
        msg      = build_alert(farmer, weather, risks)
        result   = send_message(chat_id, msg)
        return jsonify({"ok": result.get("ok", False)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/api/send_all", methods=["POST"])
def send_all_telegram():
    try:
        from bot import send_all_alerts
        send_all_alerts()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

if __name__ == "__main__":
    print("\n🌾 PaddyShield is starting...")
    print("👉 Open your browser at: http://localhost:5000\n")
    app.run(debug=True, port=5000)
