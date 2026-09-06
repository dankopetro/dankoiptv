# -*- coding: utf-8 -*-
"""PyQt6 UI — categorías, persistencia híbrida, recarga, WA_NativeWindow."""
import threading
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QLineEdit, QPushButton, QLabel, QSplitter, QFrame,
    QMessageBox, QInputDialog, QComboBox, QStatusBar
)
from PyQt6.QtGui import QFont

from .player import IPTVPlayer
from .iptv import PlaylistParser
from .config import load_config, save_config, save_cache, load_cache


class DankoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dankoiptv")
        self.resize(1280, 720)
        self.channels = []
        self.filtered = []
        self.player = None
        self._cfg = load_config()
        self.init_ui()
        self.setStatusBar(QStatusBar())
        # carga híbrida: cache inmediata + refresh background
        self._load_initial()

    def init_ui(self):
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
        title.setFont(QFont("Sans Serif", 16, QFont.Weight.Bold))
        sl.addWidget(title)

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
        self.video_frame = QFrame()
        self.video_frame.setStyleSheet("background-color: black;")
        self.video_frame.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.video_frame.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors, True)
        rl.addWidget(self.video_frame, stretch=1)

        ctrl = QWidget()
        cl = QHBoxLayout(ctrl)
        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self.resume_playback)
        cl.addWidget(self.play_btn)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_playback)
        cl.addWidget(self.stop_btn)
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
            try:
                wid = int(self.video_frame.winId())
                self.player = IPTVPlayer(wid=wid, cache_secs=int(self._cfg.get("cache_secs", 45)))
            except Exception as e:
                QMessageBox.warning(self, "mpv", f"No se pudo iniciar mpv: {e}\nInstala libmpv2.")

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
        for ch in self.filtered:
            self.channel_list.addItem(ch.name)
        self.statusBar().showMessage(f"{len(self.filtered)}/{len(self.channels)} canales — {self.group_combo.count()-1} categorías", 5000)

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
        # volver al hilo UI
        def done():
            if channels:
                self.set_channels(channels, save=True)
                self.statusBar().showMessage(f"Actualizados {len(channels)} canales", 5000)
            else:
                self.statusBar().showMessage("Fallo al descargar — se mantiene cache", 6000)
        # QTimer para cruzar al hilo Qt sin señal custom
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, done)

    def prompt_load_playlist(self):
        url, ok = QInputDialog.getText(self, "Cargar lista", "URL M3U (http...):", text=self._cfg.get("last_playlist_url", ""))
        if not ok or not url.strip():
            return
        url = url.strip()
        save_config({"last_playlist_url": url})
        self._cfg["last_playlist_url"] = url
        self.statusBar().showMessage("Descargando...")
        self.load_btn.setEnabled(False)
        def worker():
            channels = PlaylistParser.fetch_playlist_with_timeout(url, timeout=120)
            from PyQt6.QtCore import QTimer
            def done():
                self.load_btn.setEnabled(True)
                if not channels:
                    QMessageBox.warning(self, "Error", "No se pudo descargar o parsear la lista.\nVerifica la URL.")
                    self.statusBar().showMessage("Error al cargar lista", 5000)
                    return
                self.set_channels(channels, save=True)
                QMessageBox.information(self, "OK", f"Cargados {len(channels)} canales en {len({c.group for c in channels})} categorías.")
            QTimer.singleShot(0, done)
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
            from PyQt6.QtCore import QTimer
            def done():
                self.reload_btn.setEnabled(True)
                if not channels:
                    QMessageBox.warning(self, "Recargar", "Fallo al recargar. Se mantiene la lista actual.")
                    return
                self.set_channels(channels, save=True)
                self.statusBar().showMessage(f"Recargados {len(channels)} canales", 5000)
            QTimer.singleShot(0, done)
        threading.Thread(target=worker, daemon=True).start()

    def on_channel_selected(self, item):
        row = self.channel_list.row(item)
        if 0 <= row < len(self.filtered):
            ch = self.filtered[row]
            if not self.player:
                QMessageBox.warning(self, "Reproductor", "Reproductor no iniciado aún.")
                return
            self.now_label.setText(ch.name)
            self.statusBar().showMessage(f"Reproduciendo: {ch.name} [{ch.group}]", 4000)
            try:
                self.player.play(ch.url, is_live=True)
            except Exception as e:
                QMessageBox.warning(self, "Reproducción", f"Error: {e}")

    def resume_playback(self):
        if self.player and self.player.current_url:
            self.player.play(self.player.current_url, is_live=True)

    def stop_playback(self):
        if self.player:
            self.player.stop()
            self.now_label.setText("Sin reproducción")

    def closeEvent(self, event):
        save_config({"last_group": self.group_combo.currentText()})
        if self.player:
            try:
                self.player.stop()
                self.player.mpv.terminate()
            except Exception:
                pass
        event.accept()
