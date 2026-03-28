import customtkinter as ctk


class OverlayWarning(ctk.CTkToplevel):
    def __init__(self, parent, elapsed_minutes: int, fact: str,
                 on_snooze, on_go_outside, on_close):
        super().__init__(parent)

        self.title("⚠️ Take a Break!")
        self.geometry("480x340")
        self.resizable(False, False)
        self.configure(fg_color="#1a0a00")
        self.grab_set()

        self._on_snooze      = on_snooze
        self._on_go_outside  = on_go_outside
        self._on_close_cb    = on_close

        self.protocol("WM_DELETE_WINDOW", self._handle_close)
        self._build(elapsed_minutes, fact)

    def _build(self, elapsed_minutes: int, fact: str):
        ctk.CTkLabel(self, text="⚠️", font=ctk.CTkFont(size=52)).pack(pady=(28, 0))

        ctk.CTkLabel(
            self, text="You've Been Indoors for a While",
            font=ctk.CTkFont(size=20, weight="bold"), text_color="#FF8A65",
        ).pack(pady=(4, 0))

        ctk.CTkLabel(
            self,
            text=f"You've been inside for over {elapsed_minutes} minutes.\nYour mind and body need a break!",
            font=ctk.CTkFont(size=13), text_color="#FFCCBC",
            wraplength=380, justify="center",
        ).pack(pady=10)

        ctk.CTkLabel(
            self, text=f"💡  {fact}",
            font=ctk.CTkFont(size=12, slant="italic"), text_color="#FF8A65",
            wraplength=400, justify="center",
        ).pack(pady=4)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=16)

        ctk.CTkButton(
            btn_frame, text="😴  Snooze 10 min",
            width=160, height=40,
            fg_color="#2a1500", hover_color="#3a2000", text_color="#FF8A65",
            command=self._snooze,
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            btn_frame, text="🌳  Going Outside Now!",
            width=180, height=40,
            fg_color="#e65100", hover_color="#bf360c", text_color="white",
            font=ctk.CTkFont(weight="bold"),
            command=self._go_outside,
        ).pack(side="left", padx=8)

    def _snooze(self):
        self._on_snooze()
        self._close()

    def _go_outside(self):
        self._on_go_outside()
        self._close()

    def _handle_close(self):
        self._snooze()

    def _close(self):
        self._on_close_cb()
        self.grab_release()
        self.destroy()
