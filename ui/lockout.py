import customtkinter as ctk
import threading
import sys
from core.verification_server import VerificationServer

if sys.platform == "win32":
    from core.windows_lockout import WindowsLockout
else:
    WindowsLockout = None

class LockoutScreen(ctk.CTkToplevel):
    def __init__(self, parent, on_unlock):
        super().__init__(parent)

        self.title("🔒 Computer Locked")
        self.geometry("580x700")
        self.resizable(False, False)
        self.configure(fg_color="#0a0000")
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", lambda: None)

        self._on_unlock   = on_unlock
        self._server      = None
        self._server_info = None
        self._error_lbl   = None
        self._qr_label    = None
        self._win_lock    = WindowsLockout() if WindowsLockout else None

        self._build()
        self._start_server()

        self.after(200, self._engage_lockout)

    # Build UI

    def _build(self):
        ctk.CTkLabel(self, text="🔒", font=ctk.CTkFont(size=56)).pack(pady=(24, 0))

        ctk.CTkLabel(
            self, text="TIME TO TOUCH GRASS",
            font=ctk.CTkFont(size=26, weight="bold"), text_color="#D32F2F",
        ).pack(pady=(4, 0))

        ctk.CTkLabel(
            self,
            text="You've been indoors too long.\nGo outside for 15 minutes to unlock.",
            font=ctk.CTkFont(size=13), text_color="#EF9A9A",
            wraplength=480, justify="center",
        ).pack(pady=(8, 4))

        ctk.CTkFrame(self, height=1, fg_color="#3a0000").pack(fill="x", padx=24, pady=10)

        # Scrollable body
        scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color="#3a1a1a",
            scrollbar_button_hover_color="#5a2a2a",
        )
        scroll.pack(fill="both", expand=True)

        # QR / WiFi card
        conn_card = ctk.CTkFrame(scroll, fg_color="#1a0000", corner_radius=12)
        conn_card.pack(fill="x", padx=24, pady=(8, 4))

        ctk.CTkLabel(
            conn_card, text="📱  SCAN WITH YOUR PHONE",
            font=ctk.CTkFont(size=11, weight="bold"), text_color="#EF9A9A",
        ).pack(pady=(12, 4))

        self._qr_frame = ctk.CTkFrame(
            conn_card, fg_color="#0a0000", corner_radius=8, width=180, height=180,
        )
        self._qr_frame.pack(pady=4)
        self._qr_frame.pack_propagate(False)

        self._qr_placeholder = ctk.CTkLabel(
            self._qr_frame,
            text="Starting server…",
            font=ctk.CTkFont(size=11), text_color="#5a2a2a",
        )
        self._qr_placeholder.place(relx=0.5, rely=0.5, anchor="center")

        self._url_lbl = ctk.CTkLabel(
            conn_card, text="Detecting IP address…",
            font=ctk.CTkFont(family="Consolas", size=12), text_color="#EF9A9A",
        )
        self._url_lbl.pack(pady=(4, 2))

        ctk.CTkLabel(
            conn_card,
            text="Make sure your phone is on the same WiFi network",
            font=ctk.CTkFont(size=10, slant="italic"), text_color="#5a2a2a",
        ).pack(pady=(0, 12))

        # Backup code card
        backup_card = ctk.CTkFrame(scroll, fg_color="#1a0a00", corner_radius=12)
        backup_card.pack(fill="x", padx=24, pady=4)

        ctk.CTkLabel(
            backup_card, text="🔑  NO WIFI? USE BACKUP CODE",
            font=ctk.CTkFont(size=11, weight="bold"), text_color="#FF8A65",
        ).pack(pady=(12, 4))

        ctk.CTkLabel(
            backup_card,
            text="Note this code, go outside for 15 min, then enter it below:",
            font=ctk.CTkFont(size=11), text_color="#FFCCBC",
            wraplength=460, justify="center",
        ).pack(padx=16)

        self._backup_lbl = ctk.CTkLabel(
            backup_card, text="------",
            font=ctk.CTkFont(family="Consolas", size=40, weight="bold"),
            text_color="#FF5722",
        )
        self._backup_lbl.pack(pady=(4, 4))

        self._copy_btn = ctk.CTkButton(
            backup_card, text="📋  Copy to Clipboard",
            height=30, width=190, corner_radius=8,
            fg_color="#2a1000", hover_color="#3a1800", text_color="#FF8A65",
            font=ctk.CTkFont(size=11),
            command=self._copy_backup,
        )
        self._copy_btn.pack(pady=(0, 12))

        # Code entry card
        entry_card = ctk.CTkFrame(scroll, fg_color="#1a0000", corner_radius=12)
        entry_card.pack(fill="x", padx=24, pady=4)

        ctk.CTkLabel(
            entry_card, text="ENTER UNLOCK CODE",
            font=ctk.CTkFont(size=11, weight="bold"), text_color="#EF9A9A",
        ).pack(pady=(12, 4))

        ctk.CTkLabel(
            entry_card,
            text="Enter the code shown on your phone after submitting a photo,\nor the backup code above.",
            font=ctk.CTkFont(size=11), text_color="#FFCDD2",
            wraplength=460, justify="center",
        ).pack(padx=16)

        self._code_entry = ctk.CTkEntry(
            entry_card, width=200, height=42,
            font=ctk.CTkFont(family="Consolas", size=22),
            justify="center",
        )
        self._code_entry.pack(pady=(8, 4))
        self._code_entry.bind("<Return>", lambda _: self._try_unlock())

        self._error_lbl = ctk.CTkLabel(
            entry_card, text="",
            font=ctk.CTkFont(size=11), text_color="#D32F2F",
        )
        self._error_lbl.pack()

        ctk.CTkButton(
            entry_card, text="🔓  Unlock",
            height=42, width=200,
            fg_color="#b71c1c", hover_color="#c62828",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._try_unlock,
        ).pack(pady=(4, 14))

        # Steps reminder
        steps_card = ctk.CTkFrame(scroll, fg_color="#0f0000", corner_radius=10)
        steps_card.pack(fill="x", padx=24, pady=(4, 16))

        for step in [
            "1. Scan the QR code with your phone (or type the URL)",
            "2. Go outside for at least 15 minutes 🌳",
            "3. Take a photo and submit it on your phone",
            "4. Enter the code shown on your phone here",
        ]:
            ctk.CTkLabel(
                steps_card, text=step,
                font=ctk.CTkFont(size=11), text_color="#5a2a2a", anchor="w",
            ).pack(anchor="w", padx=16, pady=2)

        ctk.CTkLabel(steps_card, text="").pack(pady=4)

    # Server startup
    def _start_server(self):
        def _run():
            try:
                self._server = VerificationServer(
                    port=8080,
                    on_photo_verified=self._on_photo_verified,
                )
                info = self._server.start()
                self._server_info = info
                self.after(0, lambda: self._on_server_ready(info))
            except Exception as e:
                self.after(0, lambda: self._url_lbl.configure(
                    text=f"Server error: {e}", text_color="#D32F2F",
                ))

        threading.Thread(target=_run, daemon=True).start()

    def _on_server_ready(self, info: dict):
        self._url_lbl.configure(text=info["url"])
        self._backup_lbl.configure(text=info["backup_code"])
        self._show_qr(info["url"])

    def _show_qr(self, url: str):
        try:
            import qrcode
            from PIL import Image as PilImage

            qr = qrcode.QRCode(version=1, box_size=4, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="#EF9A9A", back_color="#0a0000")
            img = img.resize((170, 170), PilImage.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(170, 170))

            self._qr_placeholder.place_forget()
            lbl = ctk.CTkLabel(self._qr_frame, image=ctk_img, text="")
            lbl.place(relx=0.5, rely=0.5, anchor="center")

        except ImportError:
            self._qr_placeholder.configure(
                text=f"Open in phone browser:\n{url}",
                text_color="#EF9A9A",
                wraplength=160,
                justify="center",
            )

    # Unlock logic

    def _on_photo_verified(self, unlock_code: str):
        """Called by server thread when phone submits valid photo."""
        self.after(0, lambda: self._code_entry.delete(0, "end"))
        self.after(0, lambda: self._code_entry.insert(0, unlock_code))
        self.after(0, lambda: self._error_lbl.configure(
            text="✅  Photo verified! Click Unlock.", text_color="#4CAF50",
        ))

    def _engage_lockout(self):
        """Engage Windows-level input block after window is visible."""
        if self._win_lock:
            hwnd = self.winfo_id()
            self._win_lock.engage(hwnd)

    def _try_unlock(self):
        code = self._code_entry.get().strip()
        if not code:
            self._error_lbl.configure(text="Please enter a code.", text_color="#EF9A9A")
            return

        valid = self._server.validate_code(code) if self._server else False

        if valid:
            if self._win_lock:
                self._win_lock.release()
            if self._server:
                self._server.stop()
            self.grab_release()
            self.destroy()
            self._on_unlock()
        else:
            self._error_lbl.configure(
                text="Invalid code. Submit the photo on your phone first! 🌱",
                text_color="#D32F2F",
            )

    def _copy_backup(self):
        if self._server_info:
            self.clipboard_clear()
            self.clipboard_append(self._server_info["backup_code"])
            self._copy_btn.configure(text="✅  Copied!")
            self.after(2000, lambda: self._copy_btn.configure(text="📋  Copy to Clipboard"))