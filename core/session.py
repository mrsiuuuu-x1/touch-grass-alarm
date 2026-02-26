"""
session.py — Tracks indoor time, alert level, and break stats.
Pure logic — no UI code lives here.
"""

import time
import threading
from datetime import datetime
from core.config import AlertLevel, THRESHOLDS


class Session:
    def __init__(self, on_tick=None, on_level_change=None):
        """
        on_tick(elapsed_seconds)         — called every second
        on_level_change(new_level)       — called when alert level changes
        """
        self.elapsed_seconds  = 0
        self.alert_level      = AlertLevel.HEALTHY
        self.breaks_taken     = 0
        self.sessions_today   = 1
        self.streak_days      = 0
        self.session_start    = datetime.now()

        self._on_tick         = on_tick
        self._on_level_change = on_level_change
        self._running         = False
        self._thread          = None

    # ── Timer control ──────────────────────────────────────────────────────────
    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._tick_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _tick_loop(self):
        while self._running:
            time.sleep(1)
            self.elapsed_seconds += 1
            new_level = self._compute_level()

            if new_level != self.alert_level:
                self.alert_level = new_level
                if self._on_level_change:
                    self._on_level_change(new_level)

            if self._on_tick:
                self._on_tick(self.elapsed_seconds)

    # ── Level logic ────────────────────────────────────────────────────────────
    def _compute_level(self) -> AlertLevel:
        for level in [AlertLevel.LOCKOUT, AlertLevel.CRITICAL, AlertLevel.WARNING]:
            if self.elapsed_seconds >= THRESHOLDS[level]:
                return level
        return AlertLevel.HEALTHY

    # ── Actions ────────────────────────────────────────────────────────────────
    def snooze(self):
        """Push elapsed time back just below the warning threshold."""
        self.elapsed_seconds = max(0, THRESHOLDS[AlertLevel.WARNING] - 5)
        self.alert_level = AlertLevel.HEALTHY

    def log_outdoor_break(self):
        """Call this when the user successfully goes outside."""
        self.breaks_taken  += 1
        self.elapsed_seconds = 0
        self.alert_level     = AlertLevel.HEALTHY

    # ── Helpers ────────────────────────────────────────────────────────────────
    def time_until_next_warning(self) -> int:
        """Returns seconds until the next threshold, or 0 if past lockout."""
        for level in [AlertLevel.WARNING, AlertLevel.CRITICAL, AlertLevel.LOCKOUT]:
            if self.elapsed_seconds < THRESHOLDS[level]:
                return THRESHOLDS[level] - self.elapsed_seconds
        return 0

    def lockout_progress(self) -> float:
        """Returns 0.0–1.0 progress toward the lockout threshold."""
        return min(self.elapsed_seconds / THRESHOLDS[AlertLevel.LOCKOUT], 1.0)

    def formatted_elapsed(self) -> str:
        h, rem = divmod(self.elapsed_seconds, 3600)
        m, s   = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    # ── Demo / testing ─────────────────────────────────────────────────────────
    def jump_to_level(self, level: AlertLevel):
        """Instantly set elapsed time to a given level (for demo buttons)."""
        if level == AlertLevel.HEALTHY:
            self.elapsed_seconds = 0
        else:
            self.elapsed_seconds = THRESHOLDS[level]
        self.alert_level = level
