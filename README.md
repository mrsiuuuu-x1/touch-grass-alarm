# Touch Grass Alarm 🌱

> Aggressively wholesome. This app bullies you into self-care.

---

## What It Does

Monitors how long you've been sitting at your computer and forces you to go outside. Uses your webcam to detect signs of indoor strain (skin pallor, unchanging lighting, blue monitor cast), escalates warnings over time, and eventually locks your screen until you submit photo proof from outside via your phone.

---

## Setup

```bash
pip install customtkinter opencv-python mediapipe numpy pillow qrcode[pil]
python main.py
```

> **Note:** On first webcam enable, mediapipe may download a small face landmark model (~5 MB) to your temp folder. This only happens once.

---

## Folder Structure

```
touch_grass/
│
├── main.py                        ← Entry point — run this
│
├── core/                          ← Pure logic, no UI code
│   ├── config.py                  ← Thresholds, colours, health facts
│   ├── session.py                 ← Timer, alert level, break tracking
│   ├── cv_engine.py               ← Webcam analysis (pallor, lighting, blue cast)
│   ├── stats_db.py                ← Persistent stats (streaks, breaks, sessions)
│   └── verification_server.py    ← Local HTTP server for mobile unlock flow
│
├── ui/                            ← All visual components
│   ├── dashboard.py               ← Main scrollable app window
│   ├── camera_panel.py            ← Live webcam preview (expand/minimise)
│   ├── overlay.py                 ← Critical-level warning popup
│   ├── lockout.py                 ← Lockout screen with QR + backup code
│   └── widgets.py                 ← Reusable buttons, stat cards, dividers
│
├── data/                          ← Auto-created at runtime, gitignored
│   └── stats.json                 ← Persistent stats (do not edit manually)
│
└── assets/                        ← Icons, sounds (empty — add yours here)
```

### Where to put new files

| File type | Folder |
|---|---|
| Logic, algorithms, APIs, data | `core/` |
| Windows, panels, screens, widgets | `ui/` |
| Icons, sounds, images | `assets/` |
| Entry point only | `main.py` (don't add logic here) |

---

## Alert Levels

| Level | Default threshold | What happens |
|---|---|---|
| Healthy 🌿 | < 2 hours | Green dashboard, passive monitoring |
| Warning ⚠️ | 2 hours | Dashboard turns amber |
| Critical 🔴 | 3 hours | Full-screen overlay popup every 15 min |
| Lockout 🔒 | 4 hours | Screen locks, phone verification required |

---

## Adjusting Thresholds

Open `core/config.py` and edit the `THRESHOLDS` dict:

```python
# Demo values — good for testing (seconds)
THRESHOLDS = {
    AlertLevel.WARNING:  30,
    AlertLevel.CRITICAL: 60,
    AlertLevel.LOCKOUT:  90,
}

# Production values (hours × 3600)
THRESHOLDS = {
    AlertLevel.WARNING:  7200,    # 2 hours
    AlertLevel.CRITICAL: 10800,   # 3 hours
    AlertLevel.LOCKOUT:  14400,   # 4 hours
}
```

---

## Stats & Streaks

Stats are saved automatically to `data/stats.json` and persist across sessions.

| Stat | Logic |
|---|---|
| Sessions Today | Increments on each app launch, resets to 1 at midnight |
| Breaks Taken | All-time total, never resets |
| 🔥 Streak | Days in a row with at least one outdoor break — resets if you miss a day |

The `data/` folder is gitignored — it lives only on your machine.

---

## Mobile Unlock Flow

When the lockout screen appears:

1. **WiFi mode** — scan the QR code on screen with your phone (must be on same network)
2. Go outside for 15 minutes 🌳
3. Submit a photo on the phone page
4. An unlock code appears on your phone — type it into the lockout screen
5. **No WiFi?** — use the 6-digit backup code shown on the lockout screen instead

The local server runs on port `8080` by default. If that port is busy, it picks the next available one automatically.

### Tightening photo verification

Currently in **relaxed mode** — any submitted photo unlocks. To enable outdoor colour analysis, open `core/verification_server.py` and change:

```python
MODE = "relaxed"   # ← change to "strict"
```

Strict mode checks for sky colours and sunlight brightness in the photo.

---

## Webcam Detection

The CV engine analyses three signals every 2 seconds:

| Signal | What it measures |
|---|---|
| Pallor score | Skin saturation vs. your healthy baseline |
| Lighting stasis | How unchanged your ambient brightness is |
| Blue cast | Monitor-glow coolness vs. natural warmth |

All processing is **100% local** — no images are stored or transmitted.

Click **Calibrate Baseline Now** in the camera panel after sitting down in good lighting for best results.

---

## Roadmap

| Feature | Status |
|---|---|
| Scrollable dashboard + alert states | ✅ Done |
| CV webcam detection | ✅ Done |
| Mobile verification (WiFi + backup code) | ✅ Done |
| Stats persistence & streaks across sessions | ✅ Done |
| Real Windows lockout (blocks keyboard/mouse) | ⬜ Planned |
| Settings screen (adjust thresholds in UI) | ⬜ Planned |
| Strict photo verification (sky/brightness check) | ⬜ Planned |