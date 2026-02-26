"""
widgets.py — Small reusable UI components used across multiple screens.
"""

import customtkinter as ctk


def make_divider(parent, color="#1e2e1e"):
    """A thin horizontal separator line."""
    ctk.CTkFrame(parent, height=1, fg_color=color).pack(fill="x", padx=24, pady=10)


def make_stat_card(parent, title: str, value: str, col: int) -> ctk.CTkLabel:
    """
    A small stat tile with a title and a large value label.
    Returns the value CTkLabel so the caller can update it later.
    """
    card = ctk.CTkFrame(parent, corner_radius=10, fg_color="#0f1a0f")
    card.grid(row=0, column=col, padx=4, sticky="ew", ipady=8)

    ctk.CTkLabel(
        card, text=title,
        font=ctk.CTkFont(size=10), text_color="#4a6a4a"
    ).pack()

    value_label = ctk.CTkLabel(
        card, text=value,
        font=ctk.CTkFont(size=20, weight="bold"), text_color="#81C784"
    )
    value_label.pack()
    return value_label


def make_primary_button(parent, text: str, command, **kwargs) -> ctk.CTkButton:
    """Green primary action button."""
    return ctk.CTkButton(
        parent, text=text, height=44, corner_radius=10,
        fg_color="#2e7d32", hover_color="#388e3c",
        text_color="white", font=ctk.CTkFont(size=14, weight="bold"),
        command=command, **kwargs
    )


def make_secondary_button(parent, text: str, command, **kwargs) -> ctk.CTkButton:
    """Muted secondary action button."""
    return ctk.CTkButton(
        parent, text=text, height=44, corner_radius=10,
        fg_color="#1e3a1e", hover_color="#2a4a2a",
        text_color="#81C784", font=ctk.CTkFont(size=14),
        command=command, **kwargs
    )
