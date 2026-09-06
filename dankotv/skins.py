"""12 skins dark + fuentes del sistema para Danko TV."""
from PyQt6.QtGui import QFont, QFontDatabase

SKINS = {
    "Naranja Oscuro": {"accent": "#FF6A00", "accent2": "#FF8C32", "bg": "#121212", "panel": "#1E1E1E", "sel": "#2A1A0A", "text": "#EAEAEA", "sub": "#B0A090"},
    "Naranja Neón": {"accent": "#FF7A00", "accent2": "#FFB347", "bg": "#0F0F0F", "panel": "#1A1A1A", "sel": "#331A00", "text": "#FFF0E0", "sub": "#CCAA80"},
    "Ámbar Dorado": {"accent": "#FFAB00", "accent2": "#FFD740", "bg": "#1A160F", "panel": "#24200F", "sel": "#332A0A", "text": "#FFF8E0", "sub": "#C9B080"},
    "Atardecer": {"accent": "#FF5722", "accent2": "#FF9800", "bg": "#160F0D", "panel": "#241815", "sel": "#33150A", "text": "#FFEDE3", "sub": "#C09A80"},
    "Océano": {"accent": "#00A8FF", "accent2": "#4DB8FF", "bg": "#0F1419", "panel": "#1A2430", "sel": "#0A1E33", "text": "#E0F0FF", "sub": "#80A0B8"},
    "Azul Nocturno": {"accent": "#3D5AFE", "accent2": "#8C9EFF", "bg": "#0D1021", "panel": "#161A35", "sel": "#101640", "text": "#E3E6FF", "sub": "#8A90B8"},
    "Bosque": {"accent": "#00C853", "accent2": "#69F0AE", "bg": "#0F1A14", "panel": "#1A2E22", "sel": "#0A3320", "text": "#E0FFE8", "sub": "#80B898"},
    "Violeta Neón": {"accent": "#7C4DFF", "accent2": "#B388FF", "bg": "#14101E", "panel": "#1E1A2E", "sel": "#1A0A33", "text": "#F0E6FF", "sub": "#A080C0"},
    "Rosa Neón": {"accent": "#FF2E93", "accent2": "#FF7EBC", "bg": "#1A0F16", "panel": "#2A1622", "sel": "#330A20", "text": "#FFE3F1", "sub": "#C080A8"},
    "Rojo Carmesí": {"accent": "#FF1744", "accent2": "#FF616F", "bg": "#1A1014", "panel": "#2E1A1E", "sel": "#330A14", "text": "#FFE0E6", "sub": "#C08090"},
    "Grafito": {"accent": "#B0BEC5", "accent2": "#ECEFF1", "bg": "#101010", "panel": "#1B1B1B", "sel": "#262626", "text": "#F0F0F0", "sub": "#909090"},
    "Cian Eléctrico": {"accent": "#00E5FF", "accent2": "#84FFFF", "bg": "#0C1416", "panel": "#142226", "sel": "#0A2A33", "text": "#DFFAFF", "sub": "#7FA8B0"},
}

SKIN_NAMES = list(SKINS.keys())
DEFAULT_SKIN = "Naranja Oscuro"

FONT_CANDIDATES = ["Ubuntu", "Noto Sans", "Inter", "Cantarell", "DejaVu Sans", "Liberation Sans"]
DEFAULT_FONT = "Ubuntu"


def available_fonts():
    try:
        fams = set(QFontDatabase.families())
    except Exception:
        return list(FONT_CANDIDATES)
    return [f for f in FONT_CANDIDATES if f in fams] or ["Sans Serif"]


def resolve_font(preferred):
    fams = available_fonts()
    if preferred in fams:
        return preferred
    for fb in [DEFAULT_FONT, "Noto Sans", "Inter", "DejaVu Sans"]:
        if fb in fams:
            return fb
    return fams[0]


def app_font(family=None, size=10, medium=True):
    fam = resolve_font(family or DEFAULT_FONT)
    f = QFont(fam, size)
    if medium:
        try:
            f.setWeight(QFont.Weight.Medium)
        except Exception:
            f.setBold(True)
    return f


def stylesheet(skin_name, font_family=None):
    c = SKINS.get(skin_name, SKINS[DEFAULT_SKIN])
    fam = resolve_font(font_family or DEFAULT_FONT)
    return f"""
    QWidget {{ background-color: {c['bg']}; color: {c['text']}; font-family: '{fam}'; }}
    QMainWindow {{ background-color: {c['bg']}; }}
    QMenuBar {{ background-color: {c['panel']}; border-bottom: 1px solid {c['accent']}; }}
    QMenuBar::item:selected {{ background-color: {c['sel']}; color: {c['accent2']}; }}
    QMenu {{ background-color: {c['panel']}; border: 1px solid {c['accent']}; }}
    QMenu::item:selected {{ background-color: {c['sel']}; color: {c['accent2']}; }}
    QListWidget {{ background-color: {c['panel']}; border: 1px solid {c['accent']}; border-radius: 10px; padding: 6px; }}
    QListWidget::item {{ border-radius: 6px; padding: 4px; }}
    QListWidget::item:selected {{ background-color: {c['sel']}; color: {c['accent2']}; border-left: 3px solid {c['accent']}; }}
    QLineEdit, QComboBox, QSpinBox {{ background-color: {c['panel']}; border: 1px solid {c['accent']}; border-radius: 8px; padding: 7px; color: {c['text']}; }}
    QPushButton {{ background-color: {c['accent']}; color: #0A0A0A; border: none; border-radius: 8px; padding: 8px 14px; font-weight: 600; }}
    QPushButton:hover {{ background-color: {c['accent2']}; }}
    QPushButton:pressed {{ background-color: {c['accent']}; }}
    QPushButton:disabled {{ background-color: {c['panel']}; color: {c['sub']}; }}
    QStatusBar {{ background-color: {c['panel']}; border-top: 1px solid {c['accent']}; }}
    QTabWidget::pane {{ border: 1px solid {c['accent']}; }}
    QTabBar::tab {{ background-color: {c['panel']}; padding: 7px 14px; border-top-left-radius: 8px; border-top-right-radius: 8px; }}
    QTabBar::tab:selected {{ background-color: {c['sel']}; color: {c['accent2']}; }}
    QFrame#videoFrame {{ border: 2px solid {c['accent']}; border-radius: 12px; }}
    QFrame#card {{ background-color: {c['panel']}; border: 1px solid {c['accent']}; border-radius: 12px; }}
    QLabel#title {{ color: {c['accent']}; }}
    QLabel#muted {{ color: {c['sub']}; }}
    """


def apply_look(app, skin_name, font_family):
    skin = skin_name if skin_name in SKINS else DEFAULT_SKIN
    fam = resolve_font(font_family)
    try:
        app.setFont(app_font(fam))
    except Exception:
        pass
    try:
        app.setStyleSheet(stylesheet(skin, fam))
    except Exception:
        pass
    return skin, fam
