"""
lockout.py — The lockout screen shown when the user has been indoors too long.
Cannot be closed without a valid unlock code.
Phase 3 will replace the placeholder code check with real verification.
"""

import customtkinter as ctk


class LockoutScreen(ctk.CTkToplevel):
    def __init__(self, parent, on_unlock):
        super().__init__(parent)

        self.title("🔒 Computer Locked")
        self.geometry("600x460")
        self.resizable(False, False)
        self.configure(fg_color="#0a0000")
        self.grab_set()

        # Prevent closing with the X button
        self.protocol("WM_DELETE_WINDOW", lambda: None)

        self._on_unlock   = on_unlock
        self._error_label = None

        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="🔒", font=ctk.CTkFont(size=64)).pack(pady=(32, 0))

        ctk.CTkLabel(
            self, text="TIME TO TOUCH GRASS",
            font=ctk.CTkFont(size=28, weight="bold"), text_color="#D32F2F",
        ).pack(pady=(4, 0))

        ctk.CTkLabel(
            self,
            text="You've been indoors too long.\nThis computer is locked until you go outside.",
            font=ctk.CTkFont(size=14), text_color="#EF9A9A",
            wraplength=480, justify="center",
        ).pack(pady=12)

        ctk.CTkLabel(
            self, text="To unlock:",
            font=ctk.CTkFont(size=13, weight="bold"), text_color="#EF9A9A",
        ).pack()

        ctk.CTkLabel(
            self,
            text=(
                "1. Go outside for at least 15 minutes\n"
                "2. Take a photo with sky/sunlight visible\n"
                "3. Submit it via the mobile app to receive your unlock code"
            ),
            font=ctk.CTkFont(size=13), text_color="#FFCDD2",
            justify="left",
        ).pack(pady=8)

        # ── Unlock code entry ──────────────────────────────────────────────────
        code_frame = ctk.CTkFrame(self, fg_color="#1a0000", corner_radius=10)
        code_frame.pack(pady=12, padx=40, fill="x")

        ctk.CTkLabel(
            code_frame, text="Enter 6-digit unlock code:",
            font=ctk.CTkFont(size=12), text_color="#EF9A9A",
        ).pack(pady=(12, 4))

        self._code_entry = ctk.CTkEntry(
            code_frame, width=200, height=38,
            font=ctk.CTkFont(family="Consolas", size=20),
            justify="center",
        )
        self._code_entry.pack(pady=(0, 6))
        self._code_entry.bind("<Return>", lambda _: self._try_unlock())

        self._error_label = ctk.CTkLabel(
            code_frame, text="",
            font=ctk.CTkFont(size=11), text_color="#D32F2F",
        )
        self._error_label.pack(pady=(0, 4))

        ctk.CTkButton(
            self, text="🔓  Submit Code",
            height=42, width=200,
            fg_color="#b71c1c", hover_color="#c62828",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._try_unlock,
        ).pack(pady=8)

    def _try_unlock(self):
        code = self._code_entry.get().strip()

        # ── Placeholder validation ─────────────────────────────────────────────
        # Phase 3: replace this with a real code check against the backend.
        if len(code) == 6:
            self.grab_release()
            self.destroy()
            self._on_unlock()
        else:
            self._error_label.configure(text="Invalid code — go touch some grass! 🌱")
