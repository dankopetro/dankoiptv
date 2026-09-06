# -*- coding: utf-8 -*-
"""PyQt6 UI — categorías, persistencia híbrida, recarga, WA_NativeWindow + skins naranja."""
import threading
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QLineEdit, QPushButton, QLabel, QSplitter, QFrame,
    QMessageBox, QInputDialog, QComboBox, QStatusBar, QMenuBar
)
from PyQt6.QtGui import QFont, QAction

from .player import IPTVPlayer
from .iptv import PlaylistParser
from .config import load_config, save_config, save_cache, load_cache

DISPLAY_LIMIT = 2000

# Skins — naranja oscuro default, dark mode; fuente Ubuntu/Noto
SKINS = {
    "Naranja Oscuro": {"accent": "#FF6A00", "accent2": "#FF8C32", "bg": "#121212", "panel": "#1E1E1E", "sel": "#2A1A0A", "text": "#EAEAEA", "sub": "#B0A090"},
    "Naranja Neón": {"accent": "#FF7A00", "accent2": "#FFB347", "bg": "#0F0F0F", "panel": "#1A1A1A", "sel": "#331A00", "text": "#FFF0E0", "sub": "#CCAA80"},
    "Ámbar Dorado": {"accent": "#FFAB00", "accent2": "#FFD740", "bg": "#1A160F", "panel": "#24200F", "sel": "#332A0A", "text": "#FFF8E0", "sub": "#C9B080"},
    "Azul Nocturno": {"accent": "#00A8FF", "accent2": "#4DB8FF", "bg": "#0F1419", "panel": "#1A2430", "sel": "#0A1E33", "text": "#E0F0FF", "sub": "#80A0B8"},
    "Verde Esmeralda": {"accent": "#00C853", "accent2": "#69F0AE", "bg": "#0F1A14", "panel": "#1A2E22", "sel": "#0A3320", "text": "#E0FFE8", "sub": "#80B898"},
    "Violeta Neón": {"accent": "#7C4DFF", "accent2": "#B388FF", "bg": "#14101E", "panel": "#1E1A2E", "sel": "#1A0A33", "text": "#F0E6FF", "sub": "#A080C0"},
    "Rojo Carmesí": {"accent": "#FF1744", "accent2": "#FF616F", "bg": "#1A1014", "panel": "#2E1A1E", "sel": "#330A14", "text": "#FFE0E6", "sub": "#C08090"},
}
FONTS = ["Ubuntu", "Noto Sans", "Sans Serif"]


class _SignalBridge(QObject):
    done = pyqtSignal(object)

def _app_font(family="Ubuntu"):
    f = QFont(family, 10)
    f.setWeight(QFont.Weight.DemiBold)
    # fallback si no existe Ubuntu, usa Noto Sans
    if family == "Ubuntu" and "Ubuntu" not in [f.family() for f in [QFont("Ubuntu")]]:
        f = QFont("Noto Sans", 10); f.setWeight(QFont.Weight.DemiBold)
    return f

def _skin_stylesheet(skin, font_family):
    c = SKINS.get(skin, SKINS["Naranja Oscuro"])
    return f"""
    QMainWindow, QWidget {{ background: {c['bg']}; color: {c['text']}; font-family: '{font_family}'; }}
    QSplitter::handle {{ background: {c['panel']}; }}
    QListWidget {{ background: {c['panel']}; border: 1px solid {c['accent']}; border-radius: 8px; padding: 4px; }}
    QListWidget::item:selected {{ background: {c['sel']}; color: {c['accent2']}; border-left: 3px solid {c['accent']}; }}
    QLineEdit, QComboBox {{ background: {c['panel']}; border: 1px solid {c['accent']}; border-radius: 6px; padding: 6px; color: {c['text']}; }}
    QLineEdit:focus, QComboBox:focus {{ border: 1px solid {c['accent2']}; }}
    QPushButton {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {c['accent']}, stop:1 {c['accent2']}); color: #0A0A0A; border: none; border-radius: 7px; padding: 7px 12px; font-weight: 600; }}
    QPushButton:hover {{ background: {c['accent2']}; }}
    QPushButton:pressed {{ background: {c['accent']}; }}
    QStatusBar {{ background: {c['panel']}; border-top: 1px solid {c['accent']}; }}
    QMenuBar {{ background: {c['panel']}; border-bottom: 1px solid {c['accent']}; }}
    QMenuBar::item:selected {{ background: {c['sel']}; color: {c['accent2']}; }}
    QMenu {{ background: {c['panel']}; border: 1px solid {c['accent']}; }}
    QMenu::item:selected {{ background: {c['sel']}; color: {c['accent2']}; }}
    QFrame#videoFrame {{ border: 2px solid {c['accent']}; border-radius: 10px; }}
    QLabel#title {{ color: {c['accent']}; }}
    """

class DankoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        from . import __version__
        self.setWindowTitle(f"Dankoiptv {__version__}")
        self.resize(1280, 720)
        self.channels = []
        self.filtered = []
        self.player = None
        self._cfg = load_config()
        self._bridge = _SignalBridge()
        # skin + font desde config
        self._skin = self._cfg.get("skin", "Naranja Oscuro")
        self._font_family = self._cfg.get("font_family", "Ubuntu")
        # aplicar fuente y skin global
        try:
            from PyQt6.QtWidgets import QApplication
            QApplication.instance().setFont(_app_font(self._font_family))
        except Exception:
            pass
        self._apply_skin()
        self.init_ui()
        self.setStatusBar(QStatusBar())
        self._load_initial()

    def _apply_skin(self):
        try:
            self.setStyleSheet(_skin_stylesheet(self._skin, self._font_family))
            # reaplicar fuente
            from PyQt6.QtWidgets import QApplication
            if QApplication.instance():
                QApplication.instance().setFont(_app_font(self._font_family))
        except Exception:
            pass

    def init_ui(self):
        # menubar con Ajustes -> Skins/Font
        try:
            mb = QMenuBar(self)
            self.setMenuBar(mb)
            m_aj = mb.addMenu("Ajustes")
            m_skin = m_aj.addMenu("Tema (Skin)")
            for name in SKINS.keys():
                act = QAction(name, self, checkable=True)
                act.setChecked(name == self._skin)
                act.triggered.connect(lambda _, n=name: self._set_skin(n))
                m_skin.addAction(act)
            m_font = m_aj.addMenu("Fuente")
            for fn in FONTS:
                act = QAction(fn, self, checkable=True)
                act.setChecked(fn == self._font_family)
                act.triggered.connect(lambda _, f=fn: self._set_font(f))
                m_font.addAction(act)
        except Exception:
            pass

        central = QWidget(self)
        self.setCentralWidget(central)
        main = QHBoxLayout(central)
        main.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main.addWidget(splitter)

        sidebar = QWidget()
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(10, 10, 10, 10)
        title = QLabel("Dankoiptv")
        title.setObjectName("title")
        tf = QFont(self._font_family, 18); tf.setWeight(QFont.Weight.Bold)
        title.setFont(tf)
        sl.addWidget(title)
        # selector rápido de skin en sidebar también
        self.skin_combo = QComboBox()
        for k in SKINS.keys():
            self.skin_combo.addItem(k)
        self.skin_combo.setCurrentText(self._skin)
        self.skin_combo.currentTextChanged.connect(self._set_skin)
        sl.addWidget(self.skin_combo)
        self.font_combo = QComboBox()
        for fn in FONTS:
            self.font_combo.addItem(fn)
        self.font_combo.setCurrentText(self._font_family)
        self.font_combo.currentTextChanged.connect(self._set_font)
        sl.addWidget(self.font_combo)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar canal...")
        self.search.textChanged.connect(self.filter_channels)
        sl.addWidget(self.search)

        self.group_combo = QComboBox()
        self.group_combo.addItem("Todas")
        self.group_combo.currentTextChanged.connect(self.filter_channels)
        sl.addWidget(self.group_combo)

        btn_row = QHBoxLayout()
        self.load_btn = QPushButton("Cargar URL")
        self.load_btn.clicked.connect(self.prompt_load_playlist)
        btn_row.addWidget(self.load_btn)
        self.reload_btn = QPushButton("↻ Recargar")
        self.reload_btn.setToolTip("Re-descarga la URL guardada")
        self.reload_btn.clicked.connect(self.reload_playlist)
        btn_row.addWidget(self.reload_btn)
        sl.addLayout(btn_row)

        self.channel_list = QListWidget()
        self.channel_list.itemClicked.connect(self.on_channel_selected)
        self.channel_list.itemDoubleClicked.connect(self.on_channel_selected)
        sl.addWidget(self.channel_list)
        splitter.addWidget(sidebar)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        # contenedor de video con doble clic para maximizar/fullscreen (AGENTS: ventana embebida, no proceso externo)
        class VideoFrame(QFrame):
            def __init__(self, parent_win):
                super().__init__()
                self._win = parent_win
                self.setStyleSheet("background-color: black;")
                self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
                self.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors, True)
            def mouseDoubleClickEvent(self, ev):
                try:
                    if self._win.isFullScreen():
                        self._win.showNormal()
                    else:
                        self._win.showFullScreen()
                except Exception:
                    pass
                super().mouseDoubleClickEvent(ev)
        self.video_frame = VideoFrame(self)
        self.video_frame.setObjectName("videoFrame")
        rl.addWidget(self.video_frame, stretch=1)
        self._is_full = False

        ctrl = QWidget()
        cl = QHBoxLayout(ctrl)
        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self.resume_playback)
        cl.addWidget(self.play_btn)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_playback)
        cl.addWidget(self.stop_btn)
        self.fs_btn = QPushButton("⛶ Fullscreen")
        self.fs_btn.setToolTip("Doble clic en video también alterna pantalla completa (Esc para salir)")
        self.fs_btn.clicked.connect(self.toggle_fullscreen)
        cl.addWidget(self.fs_btn)
        cl.addStretch()
        self.now_label = QLabel("Sin reproducción")
        self.now_label.setStyleSheet("color: #888;")
        cl.addWidget(self.now_label)
        rl.addWidget(ctrl)
        splitter.addWidget(right)
        splitter.setSizes([360, 920])

    def showEvent(self, event):
        super().showEvent(event)
        if not self.player and self.isVisible():
            # crear player sin bloquear UI; categorías funcionan aunque mpv falle
            try:
                wid = int(self.video_frame.winId())
                if wid == 0:
                    raise RuntimeError("winId inválido (0) — ventana aún no nativa")
                self.player = IPTVPlayer(wid=wid, cache_secs=int(self._cfg.get("cache_secs", 45)))
                self.statusBar().showMessage("Reproductor listo", 3000)
            except Exception as e:
                # no modal bloqueante: permite usar lista/categorías igual
                self.player = None
                self.statusBar().showMessage(f"mpv no disponible: {e} — categorías sí funcionan. Instala: sudo apt install libmpv2 mpv", 8000)
                # aviso no bloqueante una sola vez
                if not hasattr(self, "_mpv_warned"):
                    self._mpv_warned = True
                    QMessageBox.warning(self, "mpv", f"No se pudo iniciar mpv:\n{e}\n\nLa lista y categorías funcionan, pero el video no.\n\nSolución:\n  sudo apt update && sudo apt install libmpv2 mpv\n\nLog: ~/.config/dankoiptv/mpv_diag.log\nLuego reabre Dankoiptv.")

    # --- categorías + filtrado ---
    def rebuild_groups(self):
        groups = sorted({c.group for c in self.channels if c.group})
        cur = self.group_combo.currentText()
        self.group_combo.blockSignals(True)
        self.group_combo.clear()
        self.group_combo.addItem("Todas")
        for g in groups:
            self.group_combo.addItem(g)
        # restaurar selección previa si existe
        saved = self._cfg.get("last_group", "Todas")
        idx = self.group_combo.findText(saved)
        if idx >= 0:
            self.group_combo.setCurrentIndex(idx)
        elif cur in groups or cur == "Todas":
            idx2 = self.group_combo.findText(cur)
            if idx2 >= 0: self.group_combo.setCurrentIndex(idx2)
        self.group_combo.blockSignals(False)

    def filter_channels(self, *_):
        q = self.search.text().lower().strip()
        grp = self.group_combo.currentText()
        out = self.channels
        if grp != "Todas":
            out = [c for c in out if c.group == grp]
        if q:
            out = [c for c in out if q in c.name.lower()]
        self.filtered = out
        self.update_list()

    def update_list(self):
        self.channel_list.clear()
        total = len(self.filtered)
        show = self.filtered[:DISPLAY_LIMIT]
        for ch in show:
            self.channel_list.addItem(ch.name)
        if total > DISPLAY_LIMIT:
            self.channel_list.addItem(f"— y {total - DISPLAY_LIMIT} más (filtra por categoría/búsqueda) —")
            self.channel_list.item(self.channel_list.count()-1).setFlags(self.channel_list.item(self.channel_list.count()-1).flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.statusBar().showMessage(f"{total}/{len(self.channels)} canales — {self.group_combo.count()-1} categorías" + (f" (mostrando {min(total, DISPLAY_LIMIT)})" if total>DISPLAY_LIMIT else ""), 6000)

    def set_channels(self, channels, save=True):
        self.channels = channels
        if save and channels:
            save_cache(channels)
        self.rebuild_groups()
        self.filter_channels()
        if channels:
            self.statusBar().showMessage(f"Cargados {len(channels)} canales en {len({c.group for c in channels})} categorías", 5000)

    # --- carga híbrida ---
    def _load_initial(self):
        cached, fresh = load_cache(max_age_hours=24)
        if cached:
            self.set_channels(cached, save=False)
            self.statusBar().showMessage(f"Cache: {len(cached)} canales — recargando en segundo plano..." if not fresh else f"Cache fresca: {len(cached)} canales", 4000)
        url = self._cfg.get("last_playlist_url", "")
        if url:
            # si no hay cache, bloquear con mensaje; si hay, background
            if not cached:
                self.statusBar().showMessage("Descargando lista...")
                threading.Thread(target=self._fetch_and_set, args=(url,), daemon=True).start()
            else:
                if not fresh:
                    threading.Thread(target=self._fetch_and_set, args=(url,), daemon=True).start()
        elif not cached:
            self.statusBar().showMessage("Usa 'Cargar URL' para cargar tu lista M3U", 6000)

    def _fetch_and_set(self, url):
        channels = PlaylistParser.fetch_playlist_with_timeout(url, timeout=120)
        # cruzar al hilo Qt vía señal (QTimer desde worker no tiene event loop)
        def _done(chs):
            if chs:
                self.set_channels(chs, save=True)
                self.statusBar().showMessage(f"Actualizados {len(chs)} canales", 5000)
            else:
                self.statusBar().showMessage("Fallo al descargar — se mantiene cache", 6000)
        # usar bridge signal para thread-safe
        try:
            self._bridge.done.disconnect()
        except Exception:
            pass
        self._bridge.done.connect(_done)
        self._bridge.done.emit(channels)

    def prompt_load_playlist(self):
        url, ok = QInputDialog.getText(self, "Cargar lista", "URL M3U (http...):", text=self._cfg.get("last_playlist_url", ""))
        if not ok or not url.strip():
            return
        url = url.strip()
        save_config({"last_playlist_url": url})
        self._cfg["last_playlist_url"] = url
        self.statusBar().showMessage(f"Descargando {url[:60]}... (87 MB puede tardar 15-20s)")
        self.load_btn.setEnabled(False)
        def worker():
            channels = PlaylistParser.fetch_playlist_with_timeout(url, timeout=120)
            def _done(chs):
                self.load_btn.setEnabled(True)
                if not chs:
                    QMessageBox.warning(self, "Error", "No se pudo descargar o parsear la lista.\nVerifica la URL.")
                    self.statusBar().showMessage("Error al cargar lista", 5000)
                    return
                self.set_channels(chs, save=True)
                QMessageBox.information(self, "OK", f"Cargados {len(chs)} canales en {len({c.group for c in chs})} categorías.")
            try: self._bridge.done.disconnect()
            except Exception: pass
            self._bridge.done.connect(_done)
            self._bridge.done.emit(channels)
        threading.Thread(target=worker, daemon=True).start()

    def reload_playlist(self):
        url = (self._cfg.get("last_playlist_url") or "").strip()
        if not url:
            QMessageBox.information(self, "Recargar", "No hay URL guardada. Usa 'Cargar URL' primero.")
            return
        self.statusBar().showMessage("Recargando...")
        self.reload_btn.setEnabled(False)
        def worker():
            channels = PlaylistParser.fetch_playlist_with_timeout(url, timeout=120)
            def _done(chs):
                self.reload_btn.setEnabled(True)
                if not chs:
                    QMessageBox.warning(self, "Recargar", "Fallo al recargar. Se mantiene la lista actual.")
                    return
                self.set_channels(chs, save=True)
                self.statusBar().showMessage(f"Recargados {len(chs)} canales", 5000)
            try: self._bridge.done.disconnect()
            except Exception: pass
            self._bridge.done.connect(_done)
            self._bridge.done.emit(channels)
        threading.Thread(target=worker, daemon=True).start()

    def on_channel_selected(self, item):
        row = self.channel_list.row(item)
        if 0 <= row < len(self.filtered):
            ch = self.filtered[row]
            if not self.player:
                # intentar recrear player por si era fallo transitorio de wid
                try:
                    wid = int(self.video_frame.winId())
                    self.player = IPTVPlayer(wid=wid, cache_secs=int(self._cfg.get("cache_secs", 45)))
                    self.statusBar().showMessage("Reproductor reiniciado", 3000)
                except Exception as e:
                    QMessageBox.warning(self, "Reproductor", f"mpv no disponible:\n{e}\n\nInstala libmpv2: sudo apt install libmpv2 mpv")
                    return
            self.now_label.setText(ch.name)
            self.statusBar().showMessage(f"Reproduciendo: {ch.name} [{ch.group}]", 4000)
            try:
                self.player.play(ch.url, is_live=True)
            except Exception as e:
                QMessageBox.warning(self, "Reproducción", f"Error: {e}")

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def keyPressEvent(self, ev):
        from PyQt6.QtCore import Qt as _Qt
        if ev.key() == _Qt.Key.Key_Escape and self.isFullScreen():
            self.showNormal()
            return
        if ev.key() == _Qt.Key.Key_F11:
            self.toggle_fullscreen()
            return
        super().keyPressEvent(ev)

    def mouseDoubleClickEvent(self, ev):
        # doble clic en cualquier parte también alterna fullscreen (como pide el usuario)
        self.toggle_fullscreen()
        super().mouseDoubleClickEvent(ev)

    def resume_playback(self):
        if self.player and self.player.current_url:
            try:
                self.player.play(self.player.current_url, is_live=True)
            except Exception as e:
                from PyQt6.QtWidgets import QMessageBox as _MB
                _MB.warning(self, "Play", f"Error al reproducir: {e}")

    def stop_playback(self):
        if self.player:
            try:
                self.player.stop()
            except Exception:
                pass
            self.now_label.setText("Sin reproducción")
        # asegurar que player siga válido para próximo play (evita segfault)
        if self.player and (not self.player.mpv or not self.player.mpv.handle):
            self.player = None
            self.statusBar().showMessage("Reproductor reiniciará en próximo Play", 3000)

    def _set_skin(self, name):
        if name not in SKINS:
            return
        self._skin = name
        save_config({"skin": name})
        self._cfg["skin"] = name
        self._apply_skin()
        # actualizar combos sin loop
        try:
            self.skin_combo.blockSignals(True); self.skin_combo.setCurrentText(name); self.skin_combo.blockSignals(False)
        except Exception:
            pass
        self.statusBar().showMessage(f"Tema: {name}", 3000)

    def _set_font(self, fam):
        self._font_family = fam
        save_config({"font_family": fam})
        self._cfg["font_family"] = fam
        self._apply_skin()
        try:
            self.font_combo.blockSignals(True); self.font_combo.setCurrentText(fam); self.font_combo.blockSignals(False)
        except Exception:
            pass
        self.statusBar().showMessage(f"Fuente: {fam}", 3000)

    def closeEvent(self, event):
        save_config({"last_group": self.group_combo.currentText(), "skin": self._skin, "font_family": self._font_family})
        if self.player:
            try:
                self.player.stop()
                self.player.mpv.terminate()
            except Exception:
                pass
        event.accept()
