"""
PaddyShield - Telegram Alert Bot
Run: python bot.py
Farmers message the bot to link their account, then receive weekly alerts.
"""

import json
import os
import time
import urllib.request
import urllib.parse
from datetime import datetime
from paddyshield import fetch_weather, assess_risks, ADVICE

# ── CONFIG ────────────────────────────────────────
BOT_TOKEN  = "8334015978:AAFIcIqQYtnnD7jVVhd4BRfZhfeI6J87BYo"
API_BASE   = f"https://api.telegram.org/bot{BOT_TOKEN}"
DATA_FILE  = "farmers.json"
LINKS_FILE = "telegram_links.json"  # phone → telegram_chat_id

VILLAGE_COORDS = {
    "quthbullapur": (17.55,  78.42),
    "medak":        (17.975, 78.263),
    "nalgonda":     (17.057, 79.267),
    "hyderabad":    (17.385, 78.486),
    "warangal":     (17.977, 79.598),
    "karimnagar":   (18.438, 79.128),
    "nizamabad":    (18.672, 78.094),
    "khammam":      (17.247, 80.150),
}

# ── HELPERS ───────────────────────────────────────
def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def tg_request(method, params=None):
    url = f"{API_BASE}/{method}"
    if params:
        data = json.dumps(params).encode()
        req  = urllib.request.Request(url, data=data,
               headers={"Content-Type": "application/json"})
    else:
        req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"  Telegram API error: {e}")
        return {}

def send_message(chat_id, text, parse_mode="Markdown"):
    return tg_request("sendMessage", {
        "chat_id":    chat_id,
        "text":       text,
        "parse_mode": parse_mode,
    })

def get_coords(village):
    key = village.strip().lower()
    for k, v in VILLAGE_COORDS.items():
        if k in key or key in k:
            return v
    return (17.385, 78.486)

# ── ALERT MESSAGE BUILDER ─────────────────────────
def build_alert(farmer, weather, risks):
    stage = farmer.get("stage","").replace("_"," ").title()
    lines = [
        "🌾 *PaddyShield Weekly Alert*",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"👤 Farmer  : *{farmer['name']}*",
        f"📍 Village : {farmer['village']}, {farmer['mandal']}",
        f"🌱 Stage   : {stage}",
        f"📐 Field   : {farmer['acres']} acres",
        f"📅 Date    : {datetime.now().strftime('%d %b %Y')}",
        "",
        "🌤 *Weather Forecast (7 days)*",
        f"  💧 Humidity  : {weather['humidity']}%",
        f"  🌧️ Rainfall  : {weather['rainfall']} mm",
        f"  🌡️ Temp      : {weather['temp_min']}°C – {weather['temp_max']}°C",
        f"  📡 Source    : {'Live Data' if weather['source']=='live' else 'Simulated'}",
        "",
        "⚠️ *Disease Risk Levels*",
    ]

    high_risks = []
    for disease, (score, level_str) in risks.items():
        level = level_str.split()[-1]
        emoji = "🔴" if level=="HIGH" else "🟡" if level=="MEDIUM" else "🟢"
        lines.append(f"  {emoji} *{disease}* : {level}")
        if level in ("HIGH","MEDIUM"):
            high_risks.append((disease, level))

    lines += ["", "✅ *Recommended Actions*"]
    if high_risks:
        for disease, level in high_risks:
            action = ADVICE[disease][level]
            lines.append(f"\n▪️ *{disease}*\n   → {action}")
    else:
        lines.append("  No urgent action needed. Keep monitoring your fields.")

    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "📞 Always follow govt pesticide dosage guidelines.",
        "🤝 _PaddyShield — Protecting Farmers, Proactively._",
    ]
    return "\n".join(lines)

# ── SEND ALERTS TO ALL LINKED FARMERS ─────────────
def send_all_alerts():
    farmers = load_json(DATA_FILE, [])
    links   = load_json(LINKS_FILE, {})

    if not farmers:
        print("  No farmers registered yet.")
        return

    print(f"\n📤 Sending alerts to {len(farmers)} farmers...\n")
    sent = skipped = 0

    for farmer in farmers:
        phone = farmer.get("phone","").replace("+91","").replace(" ","").strip()
        chat_id = links.get(phone)

        if not chat_id:
            print(f"  ⏭️  {farmer['name']} — not linked to Telegram yet")
            skipped += 1
            continue

        lat, lon = get_coords(farmer["village"])
        weather  = fetch_weather(lat, lon)
        risks    = assess_risks(weather)
        msg      = build_alert(farmer, weather, risks)

        result = send_message(chat_id, msg)
        if result.get("ok"):
            print(f"  ✅ Sent to {farmer['name']} ({farmer['village']})")
            sent += 1
        else:
            print(f"  ❌ Failed for {farmer['name']}: {result}")
        time.sleep(0.5)  # avoid rate limiting

    print(f"\n📊 Done! Sent: {sent} | Skipped (not linked): {skipped}")

# ── BOT LISTENER (links farmer phone → chat_id) ───
def listen_for_links():
    """
    Listens for incoming messages. When a farmer sends their
    phone number, it links their Telegram chat to their account.
    """
    print("\n👂 Bot is listening for farmer messages...")
    print("   Farmers should message the bot their phone number")
    print("   e.g.  9876543210")
    print("   Press Ctrl+C to stop.\n")

    offset = 0
    links  = load_json(LINKS_FILE, {})

    while True:
        try:
            result = tg_request("getUpdates", {"offset": offset, "timeout": 30})
            updates = result.get("result", [])

            for update in updates:
                offset = update["update_id"] + 1
                msg    = update.get("message", {})
                chat   = msg.get("chat", {})
                text   = msg.get("text", "").strip()
                chat_id = chat.get("id")
                first_name = chat.get("first_name", "Farmer")

                if not text or not chat_id:
                    continue

                if text == "/start":
                    send_message(chat_id,
                        f"🌾 *Welcome to PaddyShield, {first_name}!*\n\n"
                        "I send you weekly paddy disease risk alerts "
                        "based on your village weather.\n\n"
                        "To link your account, please send me your "
                        "*10-digit phone number* registered on PaddyShield.\n\n"
                        "_Example: 9876543210_"
                    )

                elif text.replace(" ","").isdigit() and len(text.replace(" ","")) == 10:
                    phone = text.replace(" ","").strip()
                    farmers = load_json(DATA_FILE, [])
                    match = next((f for f in farmers
                                  if f.get("phone","").replace("+91","").replace(" ","") == phone), None)
                    if match:
                        links[phone] = chat_id
                        save_json(LINKS_FILE, links)
                        send_message(chat_id,
                            f"✅ *Linked successfully!*\n\n"
                            f"👤 Name    : {match['name']}\n"
                            f"📍 Village : {match['village']}, {match['mandal']}\n"
                            f"🌱 Stage   : {match['stage'].replace('_',' ').title()}\n\n"
                            "You will now receive weekly disease risk alerts every Monday. 🌾"
                        )
                        print(f"  🔗 Linked: {match['name']} ({phone}) → chat {chat_id}")
                    else:
                        send_message(chat_id,
                            "❌ Phone number not found in PaddyShield.\n\n"
                            "Please ask your coordinator to register you first at the web app, "
                            "then try again."
                        )
                elif text == "/alert":
                    # farmer can request an alert on demand
                    phone_entry = next((p for p,c in links.items() if c==chat_id), None)
                    if phone_entry:
                        farmers = load_json(DATA_FILE, [])
                        farmer = next((f for f in farmers
                                       if f.get("phone","").replace("+91","").replace(" ","") == phone_entry), None)
                        if farmer:
                            send_message(chat_id, "⏳ Fetching your risk alert now...")
                            lat, lon = get_coords(farmer["village"])
                            weather  = fetch_weather(lat, lon)
                            risks    = assess_risks(weather)
                            msg      = build_alert(farmer, weather, risks)
                            send_message(chat_id, msg)
                    else:
                        send_message(chat_id, "Please link your account first by sending your phone number.")

                elif text == "/help":
                    send_message(chat_id,
                        "🌾 *PaddyShield Bot Commands*\n\n"
                        "/start — Welcome message\n"
                        "/alert — Get your risk alert right now\n"
                        "/help  — Show this help message\n\n"
                        "_Send your 10-digit phone number to link your account._"
                    )

        except KeyboardInterrupt:
            print("\n  Bot stopped.")
            break
        except Exception as e:
            print(f"  Error: {e}")
            time.sleep(5)

# ── MAIN ──────────────────────────────────────────
if __name__ == "__main__":
    import sys

    print("=" * 50)
    print("🌾  PaddyShield Telegram Bot")
    print("=" * 50)

    if len(sys.argv) > 1 and sys.argv[1] == "send":
        # python bot.py send  → send alerts to all linked farmers
        send_all_alerts()
    else:
        # python bot.py  → listen for farmer linking messages
        listen_for_links()
