#
# Copyright (c) 2026 Dankoiptv
#
# This file is part of Dankoiptv.
#
# Dankoiptv is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Dankoiptv skins: dark mode con acentos de color (naranja por defecto)
# + fuente preferida Ubuntu Medium con fallback Noto Sans.
#
from PyQt6 import QtGui, QtWidgets

SKINS = {
    "Naranja Oscuro": {
        "accent": "#FF6A00", "accent2": "#FF8C32",
        "bg": "#121212", "panel": "#1E1E1E", "sel": "#2A1A0A",
        "text": "#EAEAEA", "sub": "#B0A090",
    },
    "Naranja Neón": {
        "accent": "#FF7A00", "accent2": "#FFB347",
        "bg": "#0F0F0F", "panel": "#1A1A1A", "sel": "#331A00",
        "text": "#FFF0E0", "sub": "#CCAA80",
    },
    "Ámbar Dorado": {
        "accent": "#FFAB00", "accent2": "#FFD740",
        "bg": "#1A160F", "panel": "#24200F", "sel": "#332A0A",
        "text": "#FFF8E0", "sub": "#C9B080",
    },
    "Azul Nocturno": {
        "accent": "#00A8FF", "accent2": "#4DB8FF",
        "bg": "#0F1419", "panel": "#1A2430", "sel": "#0A1E33",
        "text": "#E0F0FF", "sub": "#80A0B8",
    },
    "Verde Esmeralda": {
        "accent": "#00C853", "accent2": "#69F0AE",
        "bg": "#0F1A14", "panel": "#1A2E22", "sel": "#0A3320",
        "text": "#E0FFE8", "sub": "#80B898",
    },
    "Violeta Neón": {
        "accent": "#7C4DFF", "accent2": "#B388FF",
        "bg": "#14101E", "panel": "#1E1A2E", "sel": "#1A0A33",
        "text": "#F0E6FF", "sub": "#A080C0",
    },
    "Rojo Carmesí": {
        "accent": "#FF1744", "accent2": "#FF616F",
        "bg": "#1A1014", "panel": "#2E1A1E", "sel": "#330A14",
        "text": "#FFE0E6", "sub": "#C08090",
    },
}

SKIN_NAMES = list(SKINS.keys())
DEFAULT_SKIN = "Naranja Oscuro"

APP_FONTS = ["Ubuntu", "Noto Sans"]
DEFAULT_FONT = "Ubuntu"


def resolve_font_family(preferred):
    """Devuelve la familia disponible: preferida si existe, si no fallback."""
    try:
        available = set(QtGui.QFontDatabase.families())
    except Exception:
        return preferred or DEFAULT_FONT
    for cand in [preferred, DEFAULT_FONT, "Noto Sans", "Sans Serif"]:
        if cand and cand in available:
            return cand
    return preferred or DEFAULT_FONT


def app_font(family=None, point_size=10):
    """Fuente de la app: Ubuntu Medium (casi bold) o fallback."""
    fam = resolve_font_family(family or DEFAULT_FONT)
    f = QtGui.QFont(fam, point_size)
    try:
        f.setWeight(QtGui.QFont.Weight.Medium)
    except Exception:
        pass
    return f


def skin_stylesheet(skin_name, font_family=None):
    c = SKINS.get(skin_name, SKINS[DEFAULT_SKIN])
    fam = resolve_font_family(font_family or DEFAULT_FONT)
    return f"""
    QWidget {{ background-color: {c['bg']}; color: {c['text']}; font-family: '{fam}'; }}
    QMainWindow {{ background-color: {c['bg']}; }}
    QMenuBar {{ background-color: {c['panel']}; color: {c['text']}; border-bottom: 1px solid {c['accent']}; }}
    QMenuBar::item:selected {{ background-color: {c['sel']}; color: {c['accent2']}; }}
    QMenu {{ background-color: {c['panel']}; color: {c['text']}; border: 1px solid {c['accent']}; }}
    QMenu::item:selected {{ background-color: {c['sel']}; color: {c['accent2']}; }}
    QDockWidget {{ background-color: {c['bg']}; color: {c['text']}; titlebar-close-icon: none; }}
    QDockWidget::title {{ background-color: {c['panel']}; color: {c['accent2']}; padding: 4px; }}
    QListWidget {{ background-color: {c['panel']}; border: 1px solid {c['accent']}; border-radius: 8px; padding: 4px; }}
    QListWidget::item:selected {{ background-color: {c['sel']}; color: {c['accent2']}; border-left: 3px solid {c['accent']}; }}
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ background-color: {c['panel']}; border: 1px solid {c['accent']}; border-radius: 6px; padding: 5px; color: {c['text']}; }}
    QLineEdit:focus, QComboBox:focus {{ border: 1px solid {c['accent2']}; }}
    QPushButton {{ background-color: {c['accent']}; color: #0A0A0A; border: none; border-radius: 7px; padding: 7px 12px; font-weight: 600; }}
    QPushButton:hover {{ background-color: {c['accent2']}; }}
    QPushButton:pressed {{ background-color: {c['accent']}; }}
    QPushButton:disabled {{ background-color: {c['panel']}; color: {c['sub']}; }}
    QCheckBox, QLabel {{ color: {c['text']}; }}
    QStatusBar {{ background-color: {c['panel']}; border-top: 1px solid {c['accent']}; }}
    QTabWidget::pane {{ border: 1px solid {c['accent']}; background-color: {c['bg']}; }}
    QTabBar::tab {{ background-color: {c['panel']}; color: {c['text']}; padding: 6px 12px; border-top-left-radius: 6px; border-top-right-radius: 6px; }}
    QTabBar::tab:selected {{ background-color: {c['sel']}; color: {c['accent2']}; }}
    QProgressBar {{ background-color: {c['panel']}; border: 1px solid {c['accent']}; border-radius: 4px; text-align: center; }}
    QProgressBar::chunk {{ background-color: {c['accent']}; }}
    QSlider::handle:horizontal {{ background-color: {c['accent']}; border-radius: 6px; width: 14px; }}
    QSlider::groove:horizontal {{ background-color: {c['panel']}; height: 6px; border-radius: 3px; }}
    QScrollBar:vertical {{ background-color: {c['bg']}; width: 12px; }}
    QScrollBar::handle:vertical {{ background-color: {c['accent']}; border-radius: 5px; min-height: 20px; }}
    QTableWidget {{ background-color: {c['panel']}; gridline-color: {c['sel']}; }}
    QHeaderView::section {{ background-color: {c['sel']}; color: {c['accent2']}; }}
    """


def apply_look(skin_name=None, font_family=None):
    """Aplica fuente + stylesheet a la QApplication activa. Retorna (skin, font)."""
    from dankoiptv_lib.misc import DankoData

    skin = skin_name or DankoData.settings.get("skin", DEFAULT_SKIN)
    if skin not in SKINS:
        skin = DEFAULT_SKIN
    font_fam = resolve_font_family(
        font_family or DankoData.settings.get("font_family", DEFAULT_FONT)
    )
    app = QtWidgets.QApplication.instance()
    if app is not None:
        try:
            app.setFont(app_font(font_fam))
        except Exception:
            pass
        try:
            app.setStyleSheet(skin_stylesheet(skin, font_fam))
        except Exception:
            pass
    return skin, font_fam
