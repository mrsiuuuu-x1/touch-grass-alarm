from enum import Enum


# Alert Levels
class AlertLevel(Enum):
    HEALTHY  = 0
    WARNING  = 1
    CRITICAL = 2
    LOCKOUT  = 3


# Time Thresholds
# Set to small values for easy testing.
THRESHOLDS = {
    AlertLevel.WARNING:  30,
    AlertLevel.CRITICAL: 60,
    AlertLevel.LOCKOUT:  90,
}

LEVEL_COLORS = {
    AlertLevel.HEALTHY:  {"bg": "#1a2e1a", "accent": "#4CAF50", "text": "#81C784", "label": "Healthy 🌿"},
    AlertLevel.WARNING:  {"bg": "#2e2a1a", "accent": "#FFC107", "text": "#FFD54F", "label": "Warning ⚠️"},
    AlertLevel.CRITICAL: {"bg": "#2e1a1a", "accent": "#FF5722", "text": "#FF8A65", "label": "Critical 🔴"},
    AlertLevel.LOCKOUT:  {"bg": "#1a0000", "accent": "#D32F2F", "text": "#EF9A9A", "label": "LOCKOUT 🔒"},
}


# Health Facts (rotated every 15 s)
HEALTH_FACTS = [
    "Sunlight boosts serotonin — your brain's natural mood stabiliser.",
    "15 minutes outside can reduce cortisol levels by up to 21%.",
    "Natural light resets your circadian rhythm for better sleep.",
    "Walking outside improves creativity by up to 81% (Stanford study).",
    "Vitamin D from sunlight supports immune function and bone health.",
    "Green spaces reduce mental fatigue and restore focus.",
    "Fresh air has 10× lower CO₂ than most indoor spaces.",
]


# App Meta
APP_TITLE   = "Touch Grass Alarm 🌱"
APP_VERSION = "0.1"
WINDOW_SIZE = "520x740"