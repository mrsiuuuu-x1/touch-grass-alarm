"""
verification_server.py — Local HTTP server for mobile unlock verification.

Flow:
  1. Server starts on a random port (default 8080)
  2. Lockout screen shows a QR code + URL
  3. Phone visits http://<pc-ip>:<port>
  4. User submits a photo (any photo in relaxed mode)
  5. Server validates and returns a one-time unlock code
  6. User types code into lockout screen → unlocked

Fallback (no WiFi): a backup code is generated at the same time and
can be copied to clipboard or displayed.
"""

import http.server
import threading
import socket
import secrets
import hashlib
import json
import base64
import time
import os
from typing import Optional, Callable
from urllib.parse import urlparse, parse_qs


# ── Code manager ──────────────────────────────────────────────────────────────

class VerificationCodes:
    """Generates and validates challenge/unlock code pairs."""

    def __init__(self):
        self._challenge:      str  = ""
        self._unlock_code:    str  = ""
        self._backup_code:    str  = ""
        self._used:           bool = False
        self._generated_at:   float = 0
        self.EXPIRY_SECONDS   = 3600  # 1 hour

    def generate(self) -> dict:
        """Generate fresh codes. Returns a dict with all codes."""
        self._challenge   = secrets.token_hex(8).upper()
        self._unlock_code = secrets.token_hex(3).upper()  # 6-char hex
        self._backup_code = str(secrets.randbelow(900000) + 100000)  # 6-digit number
        self._used        = False
        self._generated_at = time.time()
        return {
            "challenge":    self._challenge,
            "unlock_code":  self._unlock_code,
            "backup_code":  self._backup_code,
        }

    def validate(self, code: str) -> bool:
        """Returns True if the code matches and hasn't been used/expired."""
        if self._used:
            return False
        if time.time() - self._generated_at > self.EXPIRY_SECONDS:
            return False
        entered = code.strip().upper()
        if entered in (self._unlock_code.upper(), self._backup_code):
            self._used = True
            return True
        return False

    @property
    def unlock_code(self) -> str:
        return self._unlock_code

    @property
    def backup_code(self) -> str:
        return self._backup_code

    @property
    def challenge(self) -> str:
        return self._challenge


# ── Photo validator ────────────────────────────────────────────────────────────

class PhotoValidator:
    """
    Validates submitted photos.
    Currently in RELAXED mode: any submitted photo passes.
    To tighten later, implement _check_sky_colours().
    """

    MODE = "relaxed"  # Change to "strict" to enable colour analysis

    def validate(self, image_b64: str) -> tuple[bool, str]:
        """
        Returns (passed: bool, reason: str).
        image_b64 is a base64-encoded image (stripped of data URI prefix).
        """
        if not image_b64:
            return False, "No image received."

        if self.MODE == "relaxed":
            return True, "Photo received — enjoy your break! 🌿"

        # ── Strict mode (future) ───────────────────────────────────────────────
        try:
            return self._check_sky_colours(image_b64)
        except Exception as e:
            return False, f"Could not analyse photo: {e}"

    def _check_sky_colours(self, image_b64: str) -> tuple[bool, str]:
        """
        Analyse image for outdoor indicators:
        - High blue channel in upper portion (sky)
        - High overall brightness (sunlight)
        - Low blue-cast ratio (not a monitor)
        Requires: pip install opencv-python numpy
        """
        import cv2
        import numpy as np

        data    = base64.b64decode(image_b64)
        arr     = np.frombuffer(data, dtype=np.uint8)
        img     = cv2.imdecode(arr, cv2.IMREAD_COLOR)

        if img is None:
            return False, "Could not decode image."

        h, w    = img.shape[:2]
        top     = img[:h//3, :, :]          # top third — likely sky
        mean_b  = float(top[:,:,0].mean())  # blue channel (BGR)
        mean_g  = float(top[:,:,1].mean())
        mean_r  = float(top[:,:,2].mean())
        brightness = float(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).mean())

        sky_score = (mean_b - mean_r) / (mean_r + 1)  # blue dominance

        if brightness < 60:
            return False, "Photo looks too dark — go outside in the light! ☀️"
        if sky_score < 0.05:
            return False, "No sky detected — make sure to take the photo outside! 🌤️"

        return True, "Outdoor photo verified! 🌿"


# ── HTML template ──────────────────────────────────────────────────────────────

def _build_html(challenge: str, unlock_code: Optional[str] = None, message: Optional[str] = None) -> str:
    if unlock_code:
        body = f"""
        <div class="card success">
            <div class="icon">✅</div>
            <h2>Verified!</h2>
            <p>{message or "Photo accepted."}</p>
            <p class="label">Your unlock code:</p>
            <div class="code">{unlock_code}</div>
            <p class="hint">Type this code into the lockout screen on your computer.</p>
        </div>
        """
    elif message:
        body = f"""
        <div class="card error">
            <div class="icon">❌</div>
            <h2>Not Accepted</h2>
            <p>{message}</p>
            <a href="/" class="btn">Try Again</a>
        </div>
        """
    else:
        body = f"""
        <div class="card">
            <div class="icon">🌳</div>
            <h2>Touch Grass Verification</h2>
            <p>You need to go outside for at least <strong>15 minutes</strong>.</p>
            <p>Take a photo outside (sky, trees, or outdoors), then submit it below.</p>
            <p class="hint">Session: {challenge}</p>
            <form id="form">
                <div class="upload-area" id="uploadArea">
                    <input type="file" id="photo" accept="image/*" capture="environment" required>
                    <label for="photo">
                        <div class="upload-icon">📷</div>
                        <div>Tap to take photo or choose from gallery</div>
                    </label>
                    <div id="preview-wrap" style="display:none">
                        <img id="preview" src="" alt="preview">
                    </div>
                </div>
                <button type="submit" class="btn" id="submitBtn">Submit Photo</button>
            </form>
            <div id="status"></div>
        </div>
        <script>
            const photo = document.getElementById('photo');
            const preview = document.getElementById('preview');
            const previewWrap = document.getElementById('preview-wrap');
            const uploadArea = document.getElementById('uploadArea');
            const status = document.getElementById('status');
            const submitBtn = document.getElementById('submitBtn');

            photo.addEventListener('change', () => {{
                if (photo.files && photo.files[0]) {{
                    const reader = new FileReader();
                    reader.onload = e => {{
                        preview.src = e.target.result;
                        previewWrap.style.display = 'block';
                    }};
                    reader.readAsDataURL(photo.files[0]);
                }}
            }});

            document.getElementById('form').addEventListener('submit', async (e) => {{
                e.preventDefault();
                if (!photo.files || !photo.files[0]) {{
                    status.textContent = 'Please select a photo first.';
                    return;
                }}
                submitBtn.disabled = true;
                submitBtn.textContent = 'Verifying...';
                status.textContent = '';

                const reader = new FileReader();
                reader.onload = async (e) => {{
                    const b64 = e.target.result.split(',')[1];
                    const resp = await fetch('/verify', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{image: b64, challenge: '{challenge}'}})
                    }});
                    const html = await resp.text();
                    document.body.innerHTML = html;
                }};
                reader.readAsDataURL(photo.files[0]);
            }});
        </script>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Touch Grass Verification</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #0d1f0d;
    color: #c8e6c9;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }}
  .card {{
    background: #1a2e1a;
    border-radius: 20px;
    padding: 32px 24px;
    max-width: 400px;
    width: 100%;
    text-align: center;
    border: 1px solid #2a4a2a;
  }}
  .card.success {{ border-color: #4CAF50; }}
  .card.error   {{ border-color: #f44336; }}
  .icon  {{ font-size: 52px; margin-bottom: 12px; }}
  h2     {{ font-size: 22px; margin-bottom: 12px; color: #81C784; }}
  p      {{ color: #a5d6a7; margin-bottom: 10px; line-height: 1.5; }}
  .label {{ font-size: 12px; color: #4a7a4a; margin-top: 16px; }}
  .code  {{
    font-family: 'Courier New', monospace;
    font-size: 36px;
    font-weight: bold;
    color: #4CAF50;
    letter-spacing: 6px;
    background: #0f1f0f;
    border-radius: 10px;
    padding: 14px;
    margin: 10px 0 16px;
  }}
  .hint  {{ font-size: 12px; color: #4a7a4a; }}
  .upload-area {{
    border: 2px dashed #2a4a2a;
    border-radius: 12px;
    padding: 24px;
    margin: 16px 0;
    cursor: pointer;
    transition: border-color 0.2s;
  }}
  .upload-area:hover {{ border-color: #4CAF50; }}
  input[type=file] {{ display: none; }}
  .upload-icon {{ font-size: 32px; margin-bottom: 8px; }}
  label {{ cursor: pointer; color: #81C784; }}
  #preview {{ max-width: 100%; border-radius: 8px; margin-top: 10px; }}
  .btn {{
    display: inline-block;
    background: #2e7d32;
    color: white;
    border: none;
    border-radius: 10px;
    padding: 14px 32px;
    font-size: 16px;
    font-weight: bold;
    cursor: pointer;
    width: 100%;
    margin-top: 8px;
    text-decoration: none;
    transition: background 0.2s;
  }}
  .btn:hover   {{ background: #388e3c; }}
  .btn:disabled {{ background: #1a3a1a; color: #4a6a4a; cursor: not-allowed; }}
  #status {{ margin-top: 12px; color: #ef9a9a; font-size: 14px; }}
</style>
</head>
<body>{body}</body>
</html>"""


# ── HTTP handler ───────────────────────────────────────────────────────────────

class _Handler(http.server.BaseHTTPRequestHandler):
    codes:     VerificationCodes = None
    validator: PhotoValidator    = None
    on_unlock: Callable          = None

    def log_message(self, *args):
        pass  # suppress console spam

    def do_GET(self):
        html = _build_html(self.server.codes.challenge)
        self._send_html(html)

    def do_POST(self):
        if urlparse(self.path).path != "/verify":
            self._send_html("Not found", 404)
            return

        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)

        try:
            data  = json.loads(body)
            image = data.get("image", "")
        except Exception:
            self._send_html(_build_html(self.server.codes.challenge, message="Invalid request."))
            return

        passed, reason = self.server.validator.validate(image)

        if passed:
            codes = self.server.codes
            html  = _build_html(codes.challenge, unlock_code=codes.unlock_code, message=reason)
            self._send_html(html)
            if self.server.on_unlock:
                # Notify desktop on a separate thread so response sends first
                threading.Timer(0.5, self.server.on_unlock, args=[codes.unlock_code]).start()
        else:
            html = _build_html(self.server.codes.challenge, message=reason)
            self._send_html(html)

    def _send_html(self, html: str, code: int = 200):
        data = html.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


# ── Server ─────────────────────────────────────────────────────────────────────

class VerificationServer:
    """
    Manages the lifecycle of the local HTTP verification server.

    Usage:
        server = VerificationServer(on_photo_verified=my_callback)
        info   = server.start()   # returns {"url": ..., "backup_code": ..., "ip": ...}
        server.stop()
    """

    def __init__(
        self,
        port:               int      = 8080,
        on_photo_verified:  Callable = None,
    ):
        self.port              = port
        self.on_photo_verified = on_photo_verified
        self.codes             = VerificationCodes()
        self.validator         = PhotoValidator()
        self._httpd            = None
        self._thread           = None

    def start(self) -> dict:
        """Start the server. Returns connection info dict."""
        codes = self.codes.generate()
        ip    = self._local_ip()

        # Try requested port, fall back to OS-assigned if busy
        for attempt_port in [self.port, 0]:
            try:
                self._httpd = http.server.HTTPServer(("", attempt_port), _Handler)
                break
            except OSError:
                continue

        actual_port = self._httpd.server_address[1]
        url         = f"http://{ip}:{actual_port}"

        # Attach state to server instance
        self._httpd.codes     = self.codes
        self._httpd.validator = self.validator
        self._httpd.on_unlock = self.on_photo_verified

        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

        return {
            "url":         url,
            "ip":          ip,
            "port":        actual_port,
            "backup_code": codes["backup_code"],
            "challenge":   codes["challenge"],
        }

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()

    def validate_code(self, code: str) -> bool:
        """Validate a manually entered code (unlock or backup)."""
        return self.codes.validate(code)

    @staticmethod
    def _local_ip() -> str:
        """Best-effort local IP detection."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"