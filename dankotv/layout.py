"""Layout declarativo Danko TV: botones/menús como datos editables.

Reordenar la UI = editar estas estructuras, no el código.
Cada item: {"id", "label", "icon"(emoji/texto), "slot"(método), "tip"}.
"""

TOOLBAR = [
    {"id": "play_pause", "label": "⏯", "slot": "toggle_play", "tip": "Play/Pausa (Espacio)"},
    {"id": "stop", "label": "⏹", "slot": "stop", "tip": "Detener (S)"},
    {"id": "prev", "label": "⏮", "slot": "prev_channel", "tip": "Canal anterior (B)"},
    {"id": "next", "label": "⏭", "slot": "next_channel", "tip": "Canal siguiente (N)"},
    {"id": "rewind", "label": "−60s", "slot": "rewind", "tip": "Atrasar 60s (coma ,)"},
    {"id": "forward", "label": "+60s", "slot": "forward", "tip": "Adelantar 60s (punto .)"},
    {"id": "live", "label": "VIVO", "slot": "go_live", "tip": "Volver al borde del vivo"},
    {"id": "record", "label": "⏺", "slot": "toggle_record", "tip": "Grabar (R)"},
    {"id": "save_last", "label": "5 min", "slot": "save_last_5", "tip": "Guardar últimos 5 min del buffer (B)"},
    {"id": "save_range", "label": "Rango", "slot": "save_range_custom", "tip": "Guardar desde hace X min hasta hace Y min (G)"},
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
        {"id": "guide", "label": "Guía de programación", "slot": "open_guide", "tip": "Grilla EPG con buscadores"},
        {"id": "restart", "label": "Ver desde el inicio", "slot": "play_from_start", "tip": "Repetición del programa actual (si el proveedor tiene catchup)"},
        {"id": "save_last", "label": "⏪ Guardar últimos 5 min…", "slot": "save_last_5", "tip": "Guarda los últimos 5 min del buffer (solo con buffer activo)"},
        {"id": "save_range", "label": "⏪ Guardar rango…", "slot": "save_range_custom", "tip": "Guarda un segmento del buffer (desde hace X min hasta hace Y min)"},
        {"id": "epg_plus", "label": "Hora EPG +1h", "slot": "epg_shift_more", "tip": "Adelantar horarios EPG de esta lista"},
        {"id": "epg_minus", "label": "Hora EPG −1h", "slot": "epg_shift_less", "tip": "Atrasar horarios EPG de esta lista"},
        {"id": "fs2", "label": "Pantalla completa", "slot": "toggle_fullscreen"},
        {"id": "fav", "label": "Marcar favorito", "slot": "toggle_favorite"},
    ],
    "Opciones": [
        {"id": "skin", "label": "Tema", "submenu": "skins", "tip": "Tema de la interfaz"},
        {"id": "font", "label": "Fuente", "submenu": "fonts", "tip": "Fuente del texto"},
        {"id": "buffer", "label": "Buffer del vivo…", "submenu": "buffer",
         "tip": "Minutos de vivo que se pueden rebobinar (por defecto 30)"},
        {"id": "rec_dir", "label": "Carpeta de grabaciones…", "slot": "pick_rec_dir",
         "tip": "Dónde se guardan los .mp4 de ⏺ (default: ~/Videos/DankoTV)"},
        {"id": "export_lists", "label": "Exportar listas…", "slot": "export_lists",
         "tip": "Copia listas + canales + favoritos a una carpeta"},
    ],
    "Ayuda": [
        {"id": "about", "label": "Acerca de Danko TV", "slot": "about"},
    ],
}

PANELS = {
    "sidebar_order": ["search", "groups", "channels"],
    "video_overlay": ["now_playing", "status"],
}
