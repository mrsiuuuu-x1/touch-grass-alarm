"""
cv_engine.py — Webcam analysis engine.
Detects skin pallor and ambient lighting changes using OpenCV + MediaPipe.

Dependencies:
    pip install opencv-python mediapipe numpy
"""

import cv2
import numpy as np
import mediapipe as mp
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Callable


# ── Data Classes ───────────────────────────────────────────────────────────────

@dataclass
class Baseline:
    """Captured at session start when the user is assumed healthy."""
    mean_rgb:        np.ndarray   # Average skin colour (R, G, B)
    brightness:      float        # Average frame brightness (0–255)
    warmth_ratio:    float        # R/B ratio — higher = warmer/natural light
    captured_at:     float = field(default_factory=time.time)

    def is_ready(self) -> bool:
        return self.mean_rgb is not None


@dataclass
class CVReading:
    """A single analysis snapshot."""
    pallor_score:     float   # 0.0 (healthy) → 1.0 (very pale)
    lighting_score:   float   # 0.0 (changed) → 1.0 (unchanged / still indoors)
    blue_cast_score:  float   # 0.0 (warm/natural) → 1.0 (blue/monitor light)
    overall_score:    float   # Combined indoor confidence (0.0–1.0)
    face_detected:    bool
    frame:            Optional[np.ndarray] = None  # Current frame for preview


# ── CV Engine ──────────────────────────────────────────────────────────────────

class CVEngine:
    """
    Continuously reads from the webcam and emits CVReading objects.

    Usage:
        engine = CVEngine(on_reading=my_callback)
        engine.start()
        engine.calibrate()   # call once ~5s after start
        engine.stop()
    """

    # MediaPipe face mesh landmark indices that cover cheek/forehead skin
    _SKIN_LANDMARKS = [
        10, 338, 297, 332, 284,   # forehead
        93, 132, 58, 172, 136,    # left cheek
        323, 361, 288, 397, 365,  # right cheek
    ]

    def __init__(
        self,
        camera_index: int = 0,
        on_reading: Optional[Callable[[CVReading], None]] = None,
        on_error:   Optional[Callable[[str], None]] = None,
        sample_interval: float = 2.0,   # seconds between analysis snapshots
    ):
        self.camera_index    = camera_index
        self.on_reading      = on_reading
        self.on_error        = on_error
        self.sample_interval = sample_interval

        self._cap            = None
        self._running        = False
        self._thread         = None
        self._baseline       = None
        self._lock           = threading.Lock()

        # MediaPipe face mesh
        self._mp_face = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self) -> bool:
        """Open camera and begin reading. Returns False if camera unavailable."""
        self._cap = cv2.VideoCapture(self.camera_index)
        if not self._cap.isOpened():
            if self.on_error:
                self.on_error("Could not open webcam. Check camera permissions.")
            return False

        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._running = False
        if self._cap:
            self._cap.release()

    def calibrate(self):
        """
        Capture a baseline snapshot right now.
        Call this ~3–5 seconds after start() so the camera has warmed up.
        """
        frame = self._grab_frame()
        if frame is None:
            return

        skin_rgb = self._sample_skin(frame)
        if skin_rgb is None:
            # No face found — fall back to whole-frame colour
            skin_rgb = self._frame_mean_rgb(frame)

        brightness   = self._brightness(frame)
        warmth_ratio = self._warmth_ratio(skin_rgb)

        with self._lock:
            self._baseline = Baseline(
                mean_rgb=skin_rgb,
                brightness=brightness,
                warmth_ratio=warmth_ratio,
            )

    def has_baseline(self) -> bool:
        with self._lock:
            return self._baseline is not None

    # ── Main loop ──────────────────────────────────────────────────────────────

    def _loop(self):
        last_sample = 0.0
        while self._running:
            frame = self._grab_frame()
            if frame is None:
                time.sleep(0.1)
                continue

            now = time.time()
            if now - last_sample >= self.sample_interval:
                last_sample = now
                reading = self._analyse(frame)
                if reading and self.on_reading:
                    self.on_reading(reading)

            time.sleep(0.05)  # ~20 fps grab rate

    def _grab_frame(self) -> Optional[np.ndarray]:
        if self._cap is None or not self._cap.isOpened():
            return None
        ret, frame = self._cap.read()
        return frame if ret else None

    # ── Analysis ───────────────────────────────────────────────────────────────

    def _analyse(self, frame: np.ndarray) -> Optional[CVReading]:
        with self._lock:
            baseline = self._baseline

        face_detected = False
        skin_rgb      = self._sample_skin(frame)

        if skin_rgb is not None:
            face_detected = True
        else:
            skin_rgb = self._frame_mean_rgb(frame)

        current_brightness   = self._brightness(frame)
        current_warmth       = self._warmth_ratio(skin_rgb)

        # ── Scores (all 0.0–1.0) ──────────────────────────────────────────────
        if baseline is None:
            # Not calibrated yet — neutral scores
            pallor_score    = 0.0
            lighting_score  = 0.5
            blue_cast_score = 0.0
        else:
            pallor_score    = self._compute_pallor(skin_rgb, baseline.mean_rgb)
            lighting_score  = self._compute_lighting_stasis(current_brightness, baseline.brightness)
            blue_cast_score = self._compute_blue_cast(current_warmth, baseline.warmth_ratio)

        overall = (
            pallor_score    * 0.40 +
            lighting_score  * 0.40 +
            blue_cast_score * 0.20
        )

        return CVReading(
            pallor_score=round(pallor_score, 3),
            lighting_score=round(lighting_score, 3),
            blue_cast_score=round(blue_cast_score, 3),
            overall_score=round(overall, 3),
            face_detected=face_detected,
            frame=frame.copy(),
        )

    # ── Feature extractors ─────────────────────────────────────────────────────

    def _sample_skin(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """Use MediaPipe face mesh to sample skin pixels from cheeks/forehead."""
        rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self._mp_face.process(rgb)

        if not result.multi_face_landmarks:
            return None

        h, w   = frame.shape[:2]
        lms    = result.multi_face_landmarks[0].landmark
        pixels = []

        for idx in self._SKIN_LANDMARKS:
            lm = lms[idx]
            x  = min(int(lm.x * w), w - 1)
            y  = min(int(lm.y * h), h - 1)
            # Sample a 3×3 patch around each landmark
            patch = frame[max(0,y-1):y+2, max(0,x-1):x+2]
            if patch.size > 0:
                pixels.append(patch.reshape(-1, 3))

        if not pixels:
            return None

        all_pixels = np.vstack(pixels).astype(np.float32)
        bgr_mean   = all_pixels.mean(axis=0)
        return np.array([bgr_mean[2], bgr_mean[1], bgr_mean[0]])  # → RGB

    def _frame_mean_rgb(self, frame: np.ndarray) -> np.ndarray:
        mean_bgr = frame.mean(axis=(0, 1))
        return np.array([mean_bgr[2], mean_bgr[1], mean_bgr[0]])

    def _brightness(self, frame: np.ndarray) -> float:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return float(gray.mean())

    def _warmth_ratio(self, rgb: np.ndarray) -> float:
        """R/B ratio. Higher = warmer (natural light). Lower = cooler (monitor)."""
        r, g, b = rgb
        return float(r / (b + 1e-6))

    # ── Metric computations ────────────────────────────────────────────────────

    def _compute_pallor(self, current_rgb: np.ndarray, baseline_rgb: np.ndarray) -> float:
        """
        How much paler is the skin now vs. baseline?
        Paleness = lower saturation + higher brightness in HSV.
        """
        def to_hsv_sat_val(rgb):
            bgr   = np.uint8([[[ int(rgb[2]), int(rgb[1]), int(rgb[0]) ]]])
            hsv   = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[0][0]
            return hsv[1] / 255.0, hsv[2] / 255.0  # saturation, value

        base_sat, base_val   = to_hsv_sat_val(baseline_rgb)
        cur_sat,  cur_val    = to_hsv_sat_val(current_rgb)

        # Pallor = saturation dropped AND brightness increased
        sat_drop  = max(0.0, base_sat - cur_sat)   # 0–1
        val_rise  = max(0.0, cur_val - base_val)   # 0–1

        score = (sat_drop * 0.6 + val_rise * 0.4)
        return min(score * 2.0, 1.0)  # scale up — small changes are meaningful

    def _compute_lighting_stasis(self, current_brightness: float, baseline_brightness: float) -> float:
        """
        How similar is the brightness now vs. baseline?
        If almost identical over a long period → likely still indoors, same lighting.
        Score of 1.0 = completely unchanged (strong indoor signal).
        """
        diff  = abs(current_brightness - baseline_brightness)
        # Normalise: diff of 30+ = clearly changed lighting (going outside)
        score = max(0.0, 1.0 - (diff / 30.0))
        return score

    def _compute_blue_cast(self, current_warmth: float, baseline_warmth: float) -> float:
        """
        Has the light become bluer (lower warmth ratio)?
        Monitor glow is cooler/bluer than natural light.
        Score of 1.0 = much bluer than baseline.
        """
        drop  = max(0.0, baseline_warmth - current_warmth)
        score = min(drop / 0.3, 1.0)  # 0.3 drop = full score
        return score

    # ── Preview frame helper ───────────────────────────────────────────────────

    def get_annotated_frame(self, frame: np.ndarray, reading: CVReading) -> np.ndarray:
        """
        Draw overlay info on a frame for the debug preview window.
        Returns a new annotated frame.
        """
        out = frame.copy()
        h, w = out.shape[:2]

        # Semi-transparent dark bar at top
        overlay = out.copy()
        cv2.rectangle(overlay, (0, 0), (w, 80), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.55, out, 0.45, 0, out)

        def score_color(score):
            # Green → Yellow → Red
            if score < 0.4:
                return (80, 200, 80)
            elif score < 0.7:
                return (60, 180, 220)
            else:
                return (60, 60, 220)

        lines = [
            (f"Pallor:   {reading.pallor_score:.2f}",   score_color(reading.pallor_score)),
            (f"Lighting: {reading.lighting_score:.2f}",  score_color(reading.lighting_score)),
            (f"BlueCast: {reading.blue_cast_score:.2f}", score_color(reading.blue_cast_score)),
            (f"Overall:  {reading.overall_score:.2f}",   score_color(reading.overall_score)),
        ]

        for i, (text, color) in enumerate(lines):
            cv2.putText(out, text, (8, 18 + i * 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, color, 1, cv2.LINE_AA)

        face_text  = "Face: YES" if reading.face_detected else "Face: NO"
        face_color = (80, 200, 80) if reading.face_detected else (60, 60, 220)
        cv2.putText(out, face_text, (w - 90, 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, face_color, 1, cv2.LINE_AA)

        return out
