from flask import Flask, render_template, jsonify, request
import threading, time, random, uuid, json
from datetime import datetime
from collections import defaultdict
from qr_gen import generate_qr_b64

app = Flask(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# FIXED DATA — lives in memory, works on any server (no file writes needed)
# ─────────────────────────────────────────────────────────────────────────────
LOCALITIES = ["Godowlia", "Lanka", "Assi Ghat", "Sigra", "Bhelupur"]

CITIZENS = [
    ("Ramesh Kumar",     "9876501001"), ("Priya Sharma",      "9876501002"),
    ("Anil Gupta",       "9876501003"), ("Sunita Devi",       "9876501004"),
    ("Vikram Singh",     "9876501005"), ("Meena Pandey",      "9876501006"),
    ("Rajesh Yadav",     "9876501007"), ("Kavita Mishra",     "9876501008"),
    ("Suresh Tiwari",    "9876501009"), ("Anjali Verma",      "9876501010"),
    ("Mohan Lal",        "9876501011"), ("Rekha Srivastava",  "9876501012"),
    ("Deepak Chaurasia", "9876501013"), ("Pooja Jaiswal",     "9876501014"),
    ("Santosh Bind",     "9876501015"), ("Geeta Maurya",      "9876501016"),
    ("Ashok Patel",      "9876501017"), ("Nirmala Singh",     "9876501018"),
    ("Dinesh Tripathi",  "9876501019"), ("Usha Dubey",        "9876501020"),
    ("Ravi Shankar",     "9876501021"), ("Lalita Keshari",    "9876501022"),
    ("Harish Pathak",    "9876501023"), ("Savita Chauhan",    "9876501024"),
    ("Manoj Kumar",      "9876501025"),
]

WASTE_ITEMS = {
    "wet":       ["kitchen scraps", "vegetable peels", "food leftovers", "fruit waste",
                  "cooked rice", "dal remains", "garden clippings", "banana peels"],
    "dry":       ["plastic bottles", "cardboard boxes", "newspapers", "glass jars",
                  "aluminium cans", "polythene bags", "paper waste", "tetra packs"],
    "hazardous": ["old batteries", "expired medicines", "paint cans", "chemical bottles",
                  "fluorescent bulbs", "motor oil containers", "pesticide cans", "e-waste"],
}
CONFIDENCE = ["98.2%", "96.7%", "99.1%", "94.5%", "97.8%", "95.3%", "99.4%", "93.8%"]

# ── In-memory store ───────────────────────────────────────────────────────────
_lock         = threading.Lock()
_users        = {}   # uid -> {name, phone}
_bins         = {loc: {"wet": 0.0, "dry": 0.0, "hazardous": 0.0} for loc in LOCALITIES}
_contributions = []  # [{user_id, locality, waste_type, kg, timestamp, item, confidence}]
_camera_feed  = []   # latest 60 events for live display

# Build users dict at startup
for name, phone in CITIZENS:
    uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, phone)).replace("-","")[:8].upper()
    _users[uid] = {"name": name, "phone": phone}

# ── Helpers ───────────────────────────────────────────────────────────────────
def make_qr(uid, name):
    return generate_qr_b64(
        json.dumps({"user_id": uid, "name": name}), size=200)

def calc_incentives(total_kg):
    inc = []
    if total_kg >= 5:
        d = min(int(total_kg / 5) * 2, 20)
        inc.append({"icon": "⚡", "title": f"{d}% Electric Bill Discount",
                    "desc": "Applied on next UPPCL electricity bill cycle", "color": "#f59e0b"})
    if total_kg >= 10:
        inc.append({"icon": "🏛️", "title": "Property Tax Rebate ₹500",
                    "desc": "Varanasi Nagar Nigam property tax reduction", "color": "#3b82f6"})
    if total_kg >= 20:
        inc.append({"icon": "💧", "title": "Water Bill Subsidy 10%",
                    "desc": "Jal Nigam water bill monthly discount", "color": "#06b6d4"})
    if total_kg >= 30:
        inc.append({"icon": "☀️", "title": "PM Surya Ghar Yojana Priority",
                    "desc": "Fast-track rooftop solar subsidy approval", "color": "#f97316"})
    if total_kg >= 50:
        inc.append({"icon": "🌿", "title": "Varanasi Green Citizen Card",
                    "desc": "Free bus pass + municipal facility priority", "color": "#10b981"})
    if total_kg >= 100:
        inc.append({"icon": "🏆", "title": "Swachh Bharat Champion Certificate",
                    "desc": "Official Govt of UP recognition certificate", "color": "#8b5cf6"})
    return inc

def next_delay():
    """Realistic delay based on time of day (IST = UTC+5:30)."""
    # Convert server UTC time to IST
    utc_hour = datetime.utcnow().hour
    ist_hour  = (utc_hour + 5) % 24  # approximate IST

    if 7 <= ist_hour <= 10:    return random.uniform(120, 240)   # morning: 2-4 min
    elif 11 <= ist_hour <= 16: return random.uniform(300, 600)   # midday: 5-10 min
    elif 17 <= ist_hour <= 20: return random.uniform(120, 300)   # evening: 2-5 min
    elif 21 <= ist_hour <= 23: return random.uniform(600, 1200)  # late eve: 10-20 min
    else:                      return random.uniform(1800, 3600) # night: 30-60 min

# ── AI Camera Simulation Thread ───────────────────────────────────────────────
def camera_loop():
    time.sleep(5)
    print("[camera] AI simulation started")
    while True:
        try:
            with _lock:
                users = list(_users.items())

            uid, user  = random.choice(users)
            locality   = random.choice(LOCALITIES)
            wtype      = random.choices(["wet", "dry", "hazardous"], weights=[55, 35, 10])[0]
            kg         = round(random.uniform(0.3, 8.5), 1)
            item       = random.choice(WASTE_ITEMS[wtype])
            conf       = random.choice(CONFIDENCE)
            ts         = datetime.now()

            event = {
                "id":         str(uuid.uuid4())[:6],
                "timestamp":  ts.strftime("%H:%M:%S"),
                "date":       ts.strftime("%d %b"),
                "name":       user["name"],
                "user_id":    uid,
                "locality":   locality,
                "waste_type": wtype,
                "kg":         kg,
                "item":       item,
                "confidence": conf,
            }

            with _lock:
                _bins[locality][wtype] = round(_bins[locality][wtype] + kg, 2)
                _contributions.append(event)
                _camera_feed.insert(0, event)
                if len(_camera_feed) > 60:
                    _camera_feed.pop()

            print(f"[camera] {user['name']} → {locality} · {wtype} · {kg}kg")

        except Exception as e:
            print(f"[camera error] {e}")

        time.sleep(next_delay())

# ── API Routes ────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html", localities=LOCALITIES)

@app.route("/api/stats")
def api_stats():
    with _lock:
        total  = sum(v for b in _bins.values() for v in b.values())
        events = len(_contributions)
        users  = len(_users)
    return jsonify({"total_kg": round(total, 1), "total_users": users, "total_events": events})

@app.route("/api/bins")
def api_bins():
    with _lock:
        return jsonify({k: dict(v) for k, v in _bins.items()})

@app.route("/api/camera_feed")
def api_camera_feed():
    with _lock:
        return jsonify(list(_camera_feed[:50]))

@app.route("/api/leaderboard")
def api_leaderboard():
    with _lock:
        contribs = list(_contributions)
        users    = dict(_users)

    scores = defaultdict(lambda: {"wet": 0.0, "dry": 0.0, "hazardous": 0.0, "total": 0.0})
    for c in contribs:
        uid = c["user_id"]
        scores[uid][c["waste_type"]] += c["kg"]
        scores[uid]["total"]         += c["kg"]

    board = []
    for uid, s in scores.items():
        u = users.get(uid, {})
        board.append({
            "user_id":    uid,
            "name":       u.get("name", "Unknown"),
            "wet":        round(s["wet"],       2),
            "dry":        round(s["dry"],       2),
            "hazardous":  round(s["hazardous"], 2),
            "total":      round(s["total"],     2),
            "incentives": calc_incentives(s["total"]),
        })
    board.sort(key=lambda x: x["total"], reverse=True)
    for i, e in enumerate(board):
        e["rank"] = i + 1
    return jsonify(board)

@app.route("/api/user/<user_id>")
def api_user(user_id):
    uid = user_id.upper()
    with _lock:
        if uid not in _users:
            return jsonify({"error": "User not found"}), 404
        u        = _users[uid]
        contribs = [c for c in _contributions if c["user_id"] == uid]

    total = sum(c["kg"] for c in contribs)
    return jsonify({
        "user_id":       uid,
        "name":          u["name"],
        "total_kg":      round(total, 2),
        "contributions": contribs[-10:],  # last 10
        "incentives":    calc_incentives(total),
        "qr":            make_qr(uid, u["name"]),
    })

@app.route("/api/users")
def api_users():
    """Returns all registered citizens — used by profile search."""
    with _lock:
        return jsonify([
            {"user_id": uid, "name": u["name"]} for uid, u in _users.items()
        ])

# ── Start simulation thread ───────────────────────────────────────────────────
_sim_thread = threading.Thread(target=camera_loop, daemon=True)
_sim_thread.start()

if __name__ == "__main__":
    app.run(debug=True, port=5000, use_reloader=False)
