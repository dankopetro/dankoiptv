"""Layout declarativo Danko TV: botones/menús como datos editables.

Reordenar la UI = editar estas estructuras, no el código.
Cada item: {"id", "label", "icon"(emoji/texto), "slot"(método), "tip"}.
"""

TOOLBAR = [
    {"id": "play_pause", "label": "⏯", "slot": "toggle_play", "tip": "Play/Pausa (Espacio)"},
    {"id": "stop", "label": "⏹", "slot": "stop", "tip": "Detener (S)"},
    {"id": "prev", "label": "⏮", "slot": "prev_channel", "tip": "Canal anterior (B)"},
    {"id": "next", "label": "⏭", "slot": "next_channel", "tip": "Canal siguiente (N)"},
    {"id": "record", "label": "⏺", "slot": "toggle_record", "tip": "Grabar (R)"},
    {"id": "shot", "label": "📷", "slot": "screenshot", "tip": "Captura (H)"},
    {"id": "mute", "label": "🔇", "slot": "toggle_mute", "tip": "Silenciar (M)"},
    {"id": "fs", "label": "⛶", "slot": "toggle_fullscreen", "tip": "Pantalla completa (doble clic / F11 / Esc)"},
]

MENUS = {
    "Listas": [
        {"id": "home", "label": "Mis listas", "slot": "go_home"},
        {"id": "add_list", "label": "Nueva lista", "slot": "add_list"},
        {"id": "edit_list", "label": "Editar lista", "slot": "edit_list"},
        {"id": "reload", "label": "Recargar lista", "slot": "reload_list"},
        {"id": "quit", "label": "Salir", "slot": "quit_app", "tip": "Cerrar Danko TV (Ctrl+Q)"},
    ],
    "Ver": [
        {"id": "fs2", "label": "Pantalla completa", "slot": "toggle_fullscreen"},
        {"id": "fav", "label": "Marcar favorito", "slot": "toggle_favorite"},
        {"id": "skin", "label": "Tema", "submenu": "skins"},
        {"id": "font", "label": "Fuente", "submenu": "fonts"},
    ],
    "Ayuda": [
        {"id": "about", "label": "Acerca de Danko TV", "slot": "about"},
    ],
}

PANELS = {
    "sidebar_order": ["search", "groups", "channels"],
    "video_overlay": ["now_playing", "status"],
}
