"""
dashboard.py — The main app window.
Displays the timer, progress bar, health facts, stats, and action buttons.
"""

import customtkinter as ctk
from core.config import AlertLevel, LEVEL_COLORS, HEALTH_FACTS, APP_TITLE, APP_VERSION
from core.session import Session
from ui.widgets import make_divider, make_stat_card, make_primary_button, make_secondary_button
from ui.overlay import OverlayWarning
from ui.lockout import LockoutScreen
from ui.camera_panel import CameraPanel


class Dashboard(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("520x900")   # taller to fit camera panel
        self.resizable(False, False)

        self._fact_index    = 0
        self._overlay_open  = False

        # Wire up session callbacks
        self.session = Session(
            on_tick=lambda s: self.after(0, self._on_tick),
            on_level_change=lambda l: self.after(0, lambda: self._on_level_change(l)),
        )

        self._build()
        self.session.start()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Build UI ───────────────────────────────────────────────────────────────
    def _build(self):
        self.configure(fg_color=LEVEL_COLORS[AlertLevel.HEALTHY]["bg"])

        # ── Header ─────────────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(28, 0))

        self._title_lbl = ctk.CTkLabel(
            header, text="🌱  Touch Grass Alarm",
            font=ctk.CTkFont(family="Segoe UI", size=26, weight="bold"),
            text_color="#81C784",
        )
        self._title_lbl.pack(side="left")

        self._status_badge = ctk.CTkLabel(
            header, text="● Healthy",
            font=ctk.CTkFont(size=13), text_color="#4CAF50",
        )
        self._status_badge.pack(side="right", pady=4)

        make_divider(self, color="#2a3a2a")

        # ── Timer card ─────────────────────────────────────────────────────────
        timer_card = ctk.CTkFrame(self, corner_radius=16, fg_color="#0f1f0f")
        timer_card.pack(fill="x", padx=24, pady=4)

        ctk.CTkLabel(
            timer_card, text="TIME INDOORS",
            font=ctk.CTkFont(size=11, weight="bold"), text_color="#4a6a4a",
        ).pack(pady=(16, 0))

        self._timer_lbl = ctk.CTkLabel(
            timer_card, text="00:00:00",
            font=ctk.CTkFont(family="Consolas", size=64, weight="bold"),
            text_color="#4CAF50",
        )
        self._timer_lbl.pack(pady=(0, 4))

        self._next_warning_lbl = ctk.CTkLabel(
            timer_card, text="Next warning in 00:30",
            font=ctk.CTkFont(size=12), text_color="#4a6a4a",
        )
        self._next_warning_lbl.pack(pady=(0, 16))

        # ── Progress bar ───────────────────────────────────────────────────────
        self._progress = ctk.CTkProgressBar(
            self, height=8, corner_radius=4,
            fg_color="#1e2e1e", progress_color="#4CAF50",
        )
        self._progress.pack(fill="x", padx=24, pady=(8, 2))
        self._progress.set(0)

        self._progress_lbl = ctk.CTkLabel(
            self, text="0% toward lockout threshold",
            font=ctk.CTkFont(size=11), text_color="#4a6a4a",
        )
        self._progress_lbl.pack(anchor="e", padx=28)

        make_divider(self)

        # ── Health fact card ───────────────────────────────────────────────────
        fact_card = ctk.CTkFrame(self, corner_radius=12, fg_color="#0f1a0f")
        fact_card.pack(fill="x", padx=24, pady=4)

        ctk.CTkLabel(
            fact_card, text="💡 DID YOU KNOW?",
            font=ctk.CTkFont(size=10, weight="bold"), text_color="#4a6a4a",
        ).pack(anchor="w", padx=16, pady=(12, 4))

        self._fact_lbl = ctk.CTkLabel(
            fact_card, text=HEALTH_FACTS[0],
            font=ctk.CTkFont(size=13), text_color="#81C784",
            wraplength=420, justify="left",
        )
        self._fact_lbl.pack(anchor="w", padx=16, pady=(0, 12))

        make_divider(self)

        # ── Camera panel ───────────────────────────────────────────────────────
        self._camera_panel = CameraPanel(self, on_reading=self._on_cv_reading)
        self._camera_panel.pack(fill="x", padx=24, pady=4)

        self._cam_start_btn = ctk.CTkButton(
            self, text="📷  Enable Webcam Monitoring",
            height=36, corner_radius=8,
            fg_color="#1a2e1a", hover_color="#243e24", text_color="#81C784",
            font=ctk.CTkFont(size=12),
            command=self._start_camera,
        )
        self._cam_start_btn.pack(fill="x", padx=24, pady=(0, 4))

        make_divider(self)

        # ── Stats row ──────────────────────────────────────────────────────────
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.pack(fill="x", padx=24, pady=4)
        stats_frame.columnconfigure((0, 1, 2), weight=1)

        self._stat_sessions = make_stat_card(stats_frame, "Sessions Today", "1", 0)
        self._stat_breaks   = make_stat_card(stats_frame, "Breaks Taken",   "0", 1)
        self._stat_streak   = make_stat_card(stats_frame, "🔥 Streak",      "0 days", 2)

        make_divider(self)

        # ── Action buttons ─────────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=24, pady=4)
        btn_frame.columnconfigure((0, 1), weight=1)

        make_secondary_button(btn_frame, "😴  Snooze 10 min", self._snooze).grid(
            row=0, column=0, padx=(0, 6), sticky="ew"
        )
        make_primary_button(btn_frame, "🌳  I'm Going Outside!", self._go_outside).grid(
            row=0, column=1, padx=(6, 0), sticky="ew"
        )

        # ── Demo controls ──────────────────────────────────────────────────────
        demo_frame = ctk.CTkFrame(self, fg_color="#0a0a0a", corner_radius=10)
        demo_frame.pack(fill="x", padx=24, pady=(14, 6))

        ctk.CTkLabel(
            demo_frame, text="🛠  DEMO CONTROLS",
            font=ctk.CTkFont(size=10), text_color="#333",
        ).pack(pady=(8, 2))

        demo_btn_row = ctk.CTkFrame(demo_frame, fg_color="transparent")
        demo_btn_row.pack(pady=(0, 8))

        for label, level in [
            ("Healthy",  AlertLevel.HEALTHY),
            ("Warning",  AlertLevel.WARNING),
            ("Critical", AlertLevel.CRITICAL),
            ("Lockout",  AlertLevel.LOCKOUT),
        ]:
            ctk.CTkButton(
                demo_btn_row, text=label, width=90, height=28,
                corner_radius=6, font=ctk.CTkFont(size=11),
                fg_color="#1a1a1a", hover_color="#2a2a2a",
                command=lambda l=level: self._demo_jump(l),
            ).pack(side="left", padx=4)

        # ── Footer ─────────────────────────────────────────────────────────────
        ctk.CTkLabel(
            self,
            text=f"All processing is local · No data stored · v{APP_VERSION}",
            font=ctk.CTkFont(size=10), text_color="#2a3a2a",
        ).pack(pady=(6, 12))

    # ── Callbacks from Session ─────────────────────────────────────────────────
    def _on_tick(self):
        s = self.session

        # Timer display
        self._timer_lbl.configure(text=s.formatted_elapsed())

        # Progress bar
        p = s.lockout_progress()
        self._progress.set(p)
        self._progress_lbl.configure(text=f"{int(p * 100)}% toward lockout threshold")

        # Next warning
        remaining = s.time_until_next_warning()
        if remaining:
            rm, rs = divmod(remaining, 60)
            self._next_warning_lbl.configure(text=f"Next warning in {rm:02d}:{rs:02d}")
        else:
            self._next_warning_lbl.configure(text="⚠️  Lockout threshold reached!")

        # Rotate facts every 15 s
        if s.elapsed_seconds % 15 == 0:
            self._fact_index = (self._fact_index + 1) % len(HEALTH_FACTS)
            self._fact_lbl.configure(text=HEALTH_FACTS[self._fact_index])

    def _on_level_change(self, level: AlertLevel):
        colors = LEVEL_COLORS[level]
        self.configure(fg_color=colors["bg"])
        self._timer_lbl.configure(text_color=colors["accent"])
        self._progress.configure(progress_color=colors["accent"])
        self._title_lbl.configure(text_color=colors["text"])
        self._status_badge.configure(text=f"● {colors['label']}", text_color=colors["accent"])
        self._fact_lbl.configure(text_color=colors["text"])

        if level == AlertLevel.CRITICAL and not self._overlay_open:
            self._open_overlay()
        elif level == AlertLevel.LOCKOUT:
            self._open_lockout()

    # ── Overlay & Lockout ──────────────────────────────────────────────────────
    def _open_overlay(self):
        self._overlay_open = True

        def on_close():
            self._overlay_open = False

        OverlayWarning(
            self,
            elapsed_minutes=self.session.elapsed_seconds // 60,
            fact=HEALTH_FACTS[self._fact_index],
            on_snooze=lambda: [self._snooze(), on_close()],
            on_go_outside=lambda: [self._go_outside(), on_close()],
            on_close=on_close,
        )

    def _open_lockout(self):
        LockoutScreen(self, on_unlock=self._reset_after_unlock)

    # ── Actions ────────────────────────────────────────────────────────────────
    def _snooze(self):
        self.session.snooze()
        self._on_level_change(AlertLevel.HEALTHY)

    def _go_outside(self):
        self.session.log_outdoor_break()
        self._stat_breaks.configure(text=str(self.session.breaks_taken))
        self._on_level_change(AlertLevel.HEALTHY)

    def _reset_after_unlock(self):
        self._go_outside()

    def _demo_jump(self, level: AlertLevel):
        self.session.jump_to_level(level)
        self._on_level_change(level)
        self._on_tick()

    def _start_camera(self):
        ok = self._camera_panel.start_camera()
        if ok:
            self._cam_start_btn.configure(
                text="📷  Webcam Monitoring Active",
                fg_color="#1a3a1a", state="disabled",
            )
        else:
            self._cam_start_btn.configure(
                text="❌  Camera unavailable — check permissions",
                fg_color="#3a1a1a", text_color="#EF9A9A",
            )

    def _on_cv_reading(self, reading):
        """
        Called every ~2 s with a fresh CVReading.
        If CV confidence is high, boost the session's elapsed time slightly
        to reflect detected indoor strain — even if the timer is short.
        (Optional: tie CV score directly to threshold acceleration.)
        """
        # For now: just log. Phase 3 will use this to adjust thresholds dynamically.
        pass

    def _on_close(self):
        self._camera_panel.stop_camera()
        self.session.stop()
        self.destroy()
