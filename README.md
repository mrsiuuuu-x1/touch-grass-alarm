# Touch Grass Alarm 🌱

> Aggressively wholesome. This app bullies you into self-care.

---

## Folder Structure

```
touch_grass/
│
├── main.py                  ← Entry point — run this
│
├── core/                    ← Pure logic, no UI code
│   ├── __init__.py
│   ├── config.py            ← Constants: thresholds, colours, health facts
│   └── session.py           ← Timer, alert level tracking, break stats
│
├── ui/                      ← All visual components
│   ├── __init__.py
│   ├── dashboard.py         ← Main app window
│   ├── overlay.py           ← Critical-level warning popup
│   ├── lockout.py           ← Lockout screen (cannot be closed without code)
│   └── widgets.py           ← Reusable buttons, stat cards, dividers
│
└── assets/                  ← Icons, sounds (empty for now)
```

---

## Setup

```bash
pip install customtkinter opencv-python mediapipe numpy pillow
python main.py
```

---

## Adjusting Thresholds

Open `core/config.py` and change the `THRESHOLDS` dict:

```python
# Demo values (seconds)
THRESHOLDS = {
    AlertLevel.WARNING:  30,
    AlertLevel.CRITICAL: 60,
    AlertLevel.LOCKOUT:  90,
}

# Production values (seconds = hours × 3600)
THRESHOLDS = {
    AlertLevel.WARNING:  7200,   # 2 hours
    AlertLevel.CRITICAL: 10800,  # 3 hours
    AlertLevel.LOCKOUT:  14400,  # 4 hours
}
```

---

## Roadmap

| Phase | Feature                        | Status      |
|-------|--------------------------------|-------------|
| 1     | UI — Dashboard + warning screens | ✅ Done    |
| 2     | CV / webcam pallor detection    | ✅ Done    |
| 3     | Real Windows lockout mechanism  | ⬜ Next    |
| 4     | Mobile verification app         | ⬜ Planned |
| 5     | Stats persistence & streaks     | ⬜ Planned |
