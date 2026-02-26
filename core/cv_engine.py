"""
cv_engine.py — Webcam analysis engine.
Detects skin pallor and ambient lighting changes using OpenCV + MediaPipe.

Compatible with mediapipe 0.10+ (new Tasks API, no mp.solutions).
Also falls back gracefully to whole-frame colour if face detection fails.

Dependencies:
    pip install opencv-python mediapipe numpy
"""

import cv2
import numpy as np
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Tuple


# ── Landmark indices for cheek / forehead skin ─────────────────────────────────
_SKIN_LANDMARKS = [
    10, 338, 297, 332, 284,   # forehead
    93, 132, 58,  172, 136,   # left cheek
    323, 361, 288, 397, 365,  # right cheek
]


# ── Data Classes ───────────────────────────────────────────────────────────────

@dataclass
class Baseline:
    mean_rgb:     np.ndarray
    brightness:   float
    warmth_ratio: float
    captured_at:  float = field(default_factory=time.time)


@dataclass
class CVReading:
    pallor_score:    float
    lighting_score:  float
    blue_cast_score: float
    overall_score:   float
    face_detected:   bool
    frame:           Optional[np.ndarray] = None


# ── Face detector factory ──────────────────────────────────────────────────────

def _make_detector() -> Tuple[str, object]:
    """
    Returns (detector_type, detector_object).
    detector_type is one of: "tasks", "legacy", "none"

    Tries in order:
      1. mediapipe Tasks API (0.10+)  — needs a .task model file
      2. mp.solutions legacy API      — works on older installs
      3. None                         — whole-frame fallback, no face tracking
    """
    import mediapipe as mp

    # ── 1. Try Tasks API ──────────────────────────────────────────────────────
    try:
        from mediapipe.tasks.python import vision as mp_vision
        from mediapipe.tasks.python import BaseOptions

        import os, urllib.request, tempfile
        model_path = os.path.join(tempfile.gettempdir(), "face_landmarker_v2.task")

        if not os.path.exists(model_path):
            url = (
                "https://storage.googleapis.com/mediapipe-models/"
                "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
            )
            urllib.request.urlretrieve(url, model_path)

        options = mp_vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=mp_vision.RunningMode.IMAGE,
            num_faces=1,
        )
        detector = mp_vision.FaceLandmarker.create_from_options(options)
        return ("tasks", detector)
    except Exception:
        pass

    # ── 2. Try legacy mp.solutions ────────────────────────────────────────────
    try:
        face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        return ("legacy", face_mesh)
    except Exception:
        pass

    # ── 3. No face detection available ────────────────────────────────────────
    return ("none", None)


# ── CV Engine ──────────────────────────────────────────────────────────────────

class CVEngine:
    """
    Reads webcam frames on a background thread and emits CVReading objects.

    All face detection happens lazily — if mediapipe is unavailable or the
    model download fails, the engine falls back to whole-frame colour analysis.
    """

    def __init__(
        self,
        camera_index:    int   = 0,
        on_reading:      Optional[Callable[[CVReading], None]] = None,
        on_error:        Optional[Callable[[str], None]]       = None,
        sample_interval: float = 2.0,
    ):
        self.camera_index    = camera_index
        self.on_reading      = on_reading
        self.on_error        = on_error
        self.sample_interval = sample_interval

        self._cap             = None
        self._running         = False
        self._thread          = None
        self._baseline        = None
        self._lock            = threading.Lock()
        self._detector_type   = "none"
        self._detector        = None
        self._detector_ready  = False

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self) -> bool:
        self._cap = cv2.VideoCapture(self.camera_index)
        if not self._cap.isOpened():
            if self.on_error:
                self.on_error("Could not open webcam. Check camera permissions.")
            return False

        self._running = True
        # Initialise detector on its own thread so UI doesn't freeze
        threading.Thread(target=self._init_detector, daemon=True).start()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._running = False
        if self._cap:
            self._cap.release()

    def calibrate(self):
        frame = self._grab_frame()
        if frame is None:
            return
        skin_rgb     = self._sample_skin(frame) or self._frame_mean_rgb(frame)
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

    # ── Detector init (background) ─────────────────────────────────────────────

    def _init_detector(self):
        try:
            dtype, det = _make_detector()
            self._detector_type  = dtype
            self._detector       = det
            self._detector_ready = True
        except Exception as e:
            self._detector_type  = "none"
            self._detector_ready = True  # ready, just no face tracking

    # ── Main capture loop ──────────────────────────────────────────────────────

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

            time.sleep(0.05)

    def _grab_frame(self) -> Optional[np.ndarray]:
        if not self._cap or not self._cap.isOpened():
            return None
        ret, frame = self._cap.read()
        return frame if ret else None

    # ── Analysis ───────────────────────────────────────────────────────────────

    def _analyse(self, frame: np.ndarray) -> Optional[CVReading]:
        with self._lock:
            baseline = self._baseline

        skin_rgb      = self._sample_skin(frame)
        face_detected = skin_rgb is not None
        if skin_rgb is None:
            skin_rgb = self._frame_mean_rgb(frame)

        cur_brightness = self._brightness(frame)
        cur_warmth     = self._warmth_ratio(skin_rgb)

        if baseline is None:
            pallor_score = blue_cast_score = 0.0
            lighting_score = 0.5
        else:
            pallor_score    = self._compute_pallor(skin_rgb, baseline.mean_rgb)
            lighting_score  = self._compute_lighting_stasis(cur_brightness, baseline.brightness)
            blue_cast_score = self._compute_blue_cast(cur_warmth, baseline.warmth_ratio)

        overall = pallor_score * 0.40 + lighting_score * 0.40 + blue_cast_score * 0.20

        return CVReading(
            pallor_score=round(pallor_score, 3),
            lighting_score=round(lighting_score, 3),
            blue_cast_score=round(blue_cast_score, 3),
            overall_score=round(overall, 3),
            face_detected=face_detected,
            frame=frame.copy(),
        )

    # ── Skin sampling ──────────────────────────────────────────────────────────

    def _sample_skin(self, frame: np.ndarray) -> Optional[np.ndarray]:
        if not self._detector_ready or self._detector is None:
            return None
        try:
            if self._detector_type == "tasks":
                return self._sample_tasks(frame)
            elif self._detector_type == "legacy":
                return self._sample_legacy(frame)
        except Exception:
            pass
        return None

    def _sample_tasks(self, frame: np.ndarray) -> Optional[np.ndarray]:
        import mediapipe as mp
        h, w  = frame.shape[:2]
        rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._detector.detect(image)
        if not result.face_landmarks:
            return None
        return self._landmarks_to_rgb(result.face_landmarks[0], frame, h, w, use_xy=True)

    def _sample_legacy(self, frame: np.ndarray) -> Optional[np.ndarray]:
        h, w  = frame.shape[:2]
        rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self._detector.process(rgb)
        if not result.multi_face_landmarks:
            return None
        return self._landmarks_to_rgb(result.multi_face_landmarks[0].landmark, frame, h, w, use_xy=True)

    def _landmarks_to_rgb(self, landmarks, frame, h, w, use_xy=True) -> Optional[np.ndarray]:
        pixels = []
        for idx in _SKIN_LANDMARKS:
            try:
                lm = landmarks[idx]
                x  = min(int(lm.x * w), w - 1)
                y  = min(int(lm.y * h), h - 1)
                patch = frame[max(0, y-1):y+2, max(0, x-1):x+2]
                if patch.size > 0:
                    pixels.append(patch.reshape(-1, 3))
            except (IndexError, AttributeError):
                continue
        if not pixels:
            return None
        bgr = np.vstack(pixels).astype(np.float32).mean(axis=0)
        return np.array([bgr[2], bgr[1], bgr[0]])  # BGR → RGB

    # ── Frame helpers ──────────────────────────────────────────────────────────

    def _frame_mean_rgb(self, frame: np.ndarray) -> np.ndarray:
        m = frame.mean(axis=(0, 1))
        return np.array([m[2], m[1], m[0]])

    def _brightness(self, frame: np.ndarray) -> float:
        return float(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean())

    def _warmth_ratio(self, rgb: np.ndarray) -> float:
        r, _, b = rgb
        return float(r / (b + 1e-6))

    # ── Metric computations ────────────────────────────────────────────────────

    def _compute_pallor(self, cur_rgb: np.ndarray, base_rgb: np.ndarray) -> float:
        def to_sv(rgb):
            bgr = np.uint8([[[int(rgb[2]), int(rgb[1]), int(rgb[0])]]])
            hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[0][0]
            return hsv[1] / 255.0, hsv[2] / 255.0

        base_sat, base_val = to_sv(base_rgb)
        cur_sat,  cur_val  = to_sv(cur_rgb)
        sat_drop = max(0.0, base_sat - cur_sat)
        val_rise = max(0.0, cur_val  - base_val)
        return min((sat_drop * 0.6 + val_rise * 0.4) * 2.0, 1.0)

    def _compute_lighting_stasis(self, cur: float, base: float) -> float:
        return max(0.0, 1.0 - abs(cur - base) / 30.0)

    def _compute_blue_cast(self, cur_warmth: float, base_warmth: float) -> float:
        return min(max(0.0, base_warmth - cur_warmth) / 0.3, 1.0)

    # ── Annotated preview ──────────────────────────────────────────────────────

    def get_annotated_frame(self, frame: np.ndarray, reading: CVReading) -> np.ndarray:
        out = frame.copy()
        h, w = out.shape[:2]

        overlay = out.copy()
        cv2.rectangle(overlay, (0, 0), (w, 88), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.55, out, 0.45, 0, out)

        def sc(s):
            if s < 0.4: return (80, 200, 80)
            if s < 0.7: return (60, 180, 220)
            return (60, 60, 220)

        lines = [
            (f"Pallor:   {reading.pallor_score:.2f}",   sc(reading.pallor_score)),
            (f"Lighting: {reading.lighting_score:.2f}",  sc(reading.lighting_score)),
            (f"BlueCast: {reading.blue_cast_score:.2f}", sc(reading.blue_cast_score)),
            (f"Overall:  {reading.overall_score:.2f}",   sc(reading.overall_score)),
        ]
        for i, (text, color) in enumerate(lines):
            cv2.putText(out, text, (8, 18 + i * 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, color, 1, cv2.LINE_AA)

        mode  = f"Mode: {self._detector_type}"
        face  = "Face: YES" if reading.face_detected else "Face: NO"
        color = (80, 200, 80) if reading.face_detected else (60, 180, 220)
        cv2.putText(out, f"{face}  |  {mode}", (8, 84),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, color, 1, cv2.LINE_AA)

        return out