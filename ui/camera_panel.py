"""
camera_panel.py — Toggleable webcam preview panel embedded in the dashboard.
Shows a live feed with CV score overlays.
Can be minimised to a slim status bar or expanded to show the full preview.
"""

import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageTk
import cv2
import numpy as np
import threading
from typing import Optional, Callable
from core.cv_engine import CVEngine, CVReading


class CameraPanel(ctk.CTkFrame):
    """
    Drop-in panel for the dashboard.
    Embeds a live camera feed with annotated CV scores.

    States:
        expanded  — shows live preview (320×240) + scores
        minimised — shows a single-line status bar with latest scores
    """

    PREVIEW_W = 320
    PREVIEW_H = 240

    def __init__(
        self,
        parent,
        on_reading: Optional[Callable[[CVReading], None]] = None,
        **kwargs,
    ):
        super().__init__(parent, corner_radius=12, fg_color="#0a140a", **kwargs)

        self._on_reading_cb  = on_reading
        self._engine: Optional[CVEngine] = None
        self._expanded       = True
        self._latest_reading: Optional[CVReading] = None
        self._running        = False
        self._photo          = None   # keep reference to avoid GC

        self._build()

    # ── Build UI ───────────────────────────────────────────────────────────────

    def _build(self):
        # ── Header row (always visible) ───────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 0))

        ctk.CTkLabel(
            header, text="📷  WEBCAM MONITOR",
            font=ctk.CTkFont(size=11, weight="bold"), text_color="#4a6a4a",
        ).pack(side="left")

        self._toggle_btn = ctk.CTkButton(
            header, text="▲ Minimise", width=90, height=24,
            corner_radius=6, font=ctk.CTkFont(size=11),
            fg_color="#1a2e1a", hover_color="#243e24", text_color="#81C784",
            command=self._toggle,
        )
        self._toggle_btn.pack(side="right")

        self._status_dot = ctk.CTkLabel(
            header, text="● Off", font=ctk.CTkFont(size=11), text_color="#555",
        )
        self._status_dot.pack(side="right", padx=(0, 8))

        # ── Collapsible body ──────────────────────────────────────────────────
        self._body = ctk.CTkFrame(self, fg_color="transparent")
        self._body.pack(fill="x", padx=12, pady=(6, 0))

        # Camera canvas
        self._canvas = tk.Canvas(
            self._body,
            width=self.PREVIEW_W, height=self.PREVIEW_H,
            bg="#050f05", highlightthickness=0,
        )
        self._canvas.pack()

        # Draw placeholder
        self._canvas.create_text(
            self.PREVIEW_W // 2, self.PREVIEW_H // 2,
            text="Camera not started",
            fill="#2a4a2a", font=("Consolas", 12),
        )

        # Score bars row
        scores_frame = ctk.CTkFrame(self._body, fg_color="#0f1a0f", corner_radius=8)
        scores_frame.pack(fill="x", pady=(6, 0))
        scores_frame.columnconfigure((0, 1, 2, 3), weight=1)

        self._score_labels = {}
        for col, (key, label) in enumerate([
            ("pallor",    "Pallor"),
            ("lighting",  "Lighting"),
            ("blue_cast", "Blue Cast"),
            ("overall",   "Overall"),
        ]):
            cell = ctk.CTkFrame(scores_frame, fg_color="transparent")
            cell.grid(row=0, column=col, padx=4, pady=6, sticky="ew")
            ctk.CTkLabel(cell, text=label, font=ctk.CTkFont(size=9), text_color="#3a5a3a").pack()
            lbl = ctk.CTkLabel(cell, text="--", font=ctk.CTkFont(size=14, weight="bold"), text_color="#4CAF50")
            lbl.pack()
            self._score_labels[key] = lbl

        # Calibrate button
        self._calibrate_btn = ctk.CTkButton(
            self._body, text="🎯  Calibrate Baseline Now",
            height=32, corner_radius=8,
            fg_color="#1a2e1a", hover_color="#243e24", text_color="#81C784",
            font=ctk.CTkFont(size=12),
            command=self._calibrate,
        )
        self._calibrate_btn.pack(fill="x", pady=(8, 10))

        # Minimised status bar (hidden by default)
        self._mini_bar = ctk.CTkLabel(
            self, text="Overall: -- | No baseline",
            font=ctk.CTkFont(size=11), text_color="#4a6a4a",
        )

    # ── Toggle expanded/minimised ──────────────────────────────────────────────

    def _toggle(self):
        self._expanded = not self._expanded
        if self._expanded:
            self._mini_bar.pack_forget()
            self._body.pack(fill="x", padx=12, pady=(6, 0))
            self._toggle_btn.configure(text="▲ Minimise")
        else:
            self._body.pack_forget()
            self._mini_bar.pack(padx=12, pady=(2, 10))
            self._toggle_btn.configure(text="▼ Expand")

    # ── Engine control ─────────────────────────────────────────────────────────

    def start_camera(self, camera_index: int = 0) -> bool:
        """Start the CV engine and begin updating the preview."""
        self._engine = CVEngine(
            camera_index=camera_index,
            on_reading=self._on_reading,
            on_error=self._on_error,
            sample_interval=2.0,
        )
        ok = self._engine.start()
        if ok:
            self._running = True
            self._status_dot.configure(text="● Live", text_color="#4CAF50")
            # Auto-calibrate after 4 seconds
            threading.Timer(4.0, self._calibrate).start()
            # Start preview update loop
            self._update_preview()
        else:
            self._status_dot.configure(text="● Error", text_color="#D32F2F")
        return ok

    def stop_camera(self):
        self._running = False
        if self._engine:
            self._engine.stop()
        self._status_dot.configure(text="● Off", text_color="#555")

    def _calibrate(self):
        if self._engine:
            self._engine.calibrate()
            self._calibrate_btn.configure(
                text="✅  Baseline captured",
                fg_color="#1a3a1a", text_color="#81C784",
            )

    # ── Preview loop ───────────────────────────────────────────────────────────

    def _update_preview(self):
        """Pull the latest frame from the engine and draw it on the canvas."""
        if not self._running:
            return

        reading = self._latest_reading
        if reading is not None and reading.frame is not None and self._expanded:
            frame = reading.frame
            if self._engine:
                frame = self._engine.get_annotated_frame(frame, reading)

            # Resize to preview dimensions
            frame = cv2.resize(frame, (self.PREVIEW_W, self.PREVIEW_H))
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            self._photo = ImageTk.PhotoImage(image=img)
            self._canvas.delete("all")
            self._canvas.create_image(0, 0, anchor="nw", image=self._photo)

        # Schedule next update (~15 fps)
        self.after(66, self._update_preview)

    # ── Reading callback ───────────────────────────────────────────────────────

    def _on_reading(self, reading: CVReading):
        """Called from the CV engine thread — schedule UI update on main thread."""
        self._latest_reading = reading
        self.after(0, lambda: self._update_scores(reading))
        if self._on_reading_cb:
            self._on_reading_cb(reading)

    def _update_scores(self, reading: CVReading):
        def score_color(s):
            if s < 0.35:  return "#4CAF50"   # green — fine
            if s < 0.65:  return "#FFC107"   # amber — warning
            return "#F44336"                  # red — bad

        self._score_labels["pallor"].configure(
            text=f"{reading.pallor_score:.0%}",
            text_color=score_color(reading.pallor_score),
        )
        self._score_labels["lighting"].configure(
            text=f"{reading.lighting_score:.0%}",
            text_color=score_color(reading.lighting_score),
        )
        self._score_labels["blue_cast"].configure(
            text=f"{reading.blue_cast_score:.0%}",
            text_color=score_color(reading.blue_cast_score),
        )
        self._score_labels["overall"].configure(
            text=f"{reading.overall_score:.0%}",
            text_color=score_color(reading.overall_score),
        )

        # Update minimised bar too
        status = "🟢 OK" if reading.overall_score < 0.4 else ("🟡 Warning" if reading.overall_score < 0.7 else "🔴 Go outside!")
        self._mini_bar.configure(
            text=f"Overall: {reading.overall_score:.0%}  |  {status}",
            text_color=score_color(reading.overall_score),
        )

    def _on_error(self, msg: str):
        self.after(0, lambda: self._status_dot.configure(text=f"● {msg[:30]}", text_color="#D32F2F"))
