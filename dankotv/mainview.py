"""Vista principal Danko TV: video embebido + canales, layout declarativo."""
import threading
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QAction
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QListWidget,
    QLineEdit, QPushButton, QLabel, QSplitter, QFrame, QComboBox,
    QStatusBar, QMenuBar, QListWidgetItem, QMessageBox, QSlider,
)

from . import config as cfg
from . import engine
from . import layout as L
from . import skins
from .home import NewListDialog, load_spec
from .player import SeamlessPlayer

DISPLAY_LIMIT = 2000


class _Bridge(QObject):
    done = pyqtSignal(object)


class VideoFrame(QFrame):
    def __init__(self, win):
        super().__init__()
        self._win = win
        self.setObjectName("videoFrame")
        self.setStyleSheet("background-color: black;")
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors, True)

    def mouseDoubleClickEvent(self, ev):
        try:
            self._win.toggle_fullscreen()
        except Exception:
            pass
        super().mouseDoubleClickEvent(ev)


class MainWindow(QMainWindow):
    back_home = pyqtSignal()

    def __init__(self, entry=None, channels=None, groups=None, version=""):
        super().__init__()
        self.entry = entry or {}
        self.channels = channels or []
        self.filtered = []
        self._ver = version
        self._cfg = cfg.load_settings()
        self.player = None
        self._playing_idx = -1
        self._bridge = _Bridge()
        self.resize(1280, 720)
        self._build_ui()
        self.setStatusBar(QStatusBar())
        self.set_list(self.entry, self.channels, groups or [])

    def set_list(self, entry, channels, groups):
        """Carga una lista en la vista principal."""
        self.entry = entry or {}
        self.channels = channels or []
        name = self.entry.get("name", "")
        self.setWindowTitle(f"Danko TV {self._ver} — {name}" if name else f"Danko TV {self._ver} — Sin lista")
        self._set_groups(groups or [])
        self.filter_channels()
        if self.channels:
            self.statusBar().showMessage(f"Lista '{name}': {len(self.channels)} canales", 5000)

    # --- UI construida desde layout.py ---
    def _build_ui(self):
        self._video_max = False
        mb = QMenuBar(self)
        self.menubar = mb
        self.setMenuBar(mb)
        for menu_name, items in L.MENUS.items():
            m = mb.addMenu(menu_name)
            for it in items:
                act = QAction(it["label"], self)
                act.setToolTip(it.get("tip", ""))
                slot = getattr(self, it["slot"], None)
                if slot:
                    act.triggered.connect(slot)
                m.addAction(act)

        central = QWidget(self)
        self.setCentralWidget(central)
        main = QHBoxLayout(central)
        main.setContentsMargins(8, 8, 8, 8)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main.addWidget(splitter)

        side = QWidget()
        self.sidebar = side
        sl = QVBoxLayout(side)
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔎 Buscar canal...")
        self.search.textChanged.connect(self.filter_channels)
        sl.addWidget(self.search)
        self.group_combo = QComboBox()
        self.group_combo.currentTextChanged.connect(self.filter_channels)
        sl.addWidget(self.group_combo)
        self.channel_list = QListWidget()
        self.channel_list.itemClicked.connect(self.on_select)
        self.channel_list.itemDoubleClicked.connect(self.on_select)
        sl.addWidget(self.channel_list, stretch=1)
        splitter.addWidget(side)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self.video_frame = VideoFrame(self)
        rl.addWidget(self.video_frame, stretch=1)

        self.now_label = QLabel("Sin reproducción")
        self.now_label.setObjectName("muted")
        rl.addWidget(self.now_label)

        self.toolbar = QWidget()
        bar = QHBoxLayout(self.toolbar)
        bar.setContentsMargins(0, 0, 0, 0)
        for it in L.TOOLBAR:
            b = QPushButton(it["label"])
            b.setToolTip(it.get("tip", ""))
            slot = getattr(self, it["slot"], None)
            if slot:
                b.clicked.connect(slot)
            bar.addWidget(b)
        bar.addStretch()
        self.vol = QSlider(Qt.Orientation.Horizontal)
        self.vol.setRange(0, 200)
        self.vol.setValue(100)
        self.vol.setFixedWidth(120)
        self.vol.valueChanged.connect(self._on_volume)
        bar.addWidget(QLabel("🔊"))
        bar.addWidget(self.vol)
        rl.addWidget(self.toolbar)
        splitter.addWidget(right)
        splitter.setSizes([360, 920])

    # --- slots del layout declarativo ---
    def toggle_play(self):
        if not self.player:
            return
        try:
            paused = self.player.mpv.pause
            self.player.mpv.pause = not paused
        except Exception:
            pass

    def stop(self):
        if self.player:
            try:
                self.player.stop()
            except Exception:
                pass
            self.now_label.setText("Sin reproducción")

    def prev_channel(self):
        self._step(-1)

    def next_channel(self):
        self._step(1)

    def _step(self, d):
        if not self.filtered:
            return
        idx = (self._playing_idx + d) % len(self.filtered)
        item = self.channel_list.item(min(idx, self.channel_list.count() - 1))
        if item:
            self.channel_list.setCurrentItem(item)
            self.on_select(item)

    def toggle_record(self):
        self.statusBar().showMessage("Grabación: disponible en 0.2", 4000)

    def screenshot(self):
        if self.player:
            try:
                self.player.mpv.command("screenshot")
                self.statusBar().showMessage("Captura guardada", 3000)
            except Exception as e:
                self.statusBar().showMessage(f"Captura fallo: {e}", 3000)

    def toggle_mute(self):
        if self.player:
            try:
                self.player.mpv.mute = not self.player.mpv.mute
            except Exception:
                pass

    def toggle_fullscreen(self):
        """MAXIMIZA EL VIDEO: oculta sidebar/menús y el video llena la ventana.
        ⛶, doble clic, F11 o Esc alternan."""
        self._video_max = not self._video_max
        self.sidebar.setVisible(not self._video_max)
        self.menubar.setVisible(not self._video_max)
        self.statusBar().setVisible(not self._video_max)
        self.now_label.setVisible(not self._video_max)
        if self._video_max:
            self.statusBar().showMessage("Video maximizado — doble clic o Esc para salir", 3000)
            self.statusBar().setVisible(True)

    def go_home(self):
        self.back_home.emit()

    def add_list(self):
        """Pequeño menú para llenar la lista IPTV (nombre + URL/Xtream)."""
        dlg = NewListDialog(self)
        if not dlg.exec():
            return
        spec = dlg._spec
        self.statusBar().showMessage(f"Descargando '{spec['name']}'...")
        self.setEnabled(False)

        def done(ok, ch, gr, err):
            self.setEnabled(True)
            if not ok or not ch:
                QMessageBox.warning(self, "Error", f"No se pudo cargar la lista.\n{err}")
                self.statusBar().showMessage("Sin lista — usa Listas > Nueva lista", 6000)
                return
            entry = dict(spec)
            entry["channels"] = len(ch)
            entry["groups"] = len(gr)
            cfg.upsert_list(entry)
            self.set_list(entry, ch, gr)

        load_spec(spec, self, done)

    def reload_list(self):
        if not self.entry.get("name") or not self.entry.get("type"):
            self.add_list()
            return
        spec = {k: self.entry[k] for k in ("name", "type", "url", "host", "user", "pass") if k in self.entry}
        self.statusBar().showMessage("Recargando lista...")
        self.setEnabled(False)

        def work():
            try:
                if spec["type"] == "m3u":
                    ch, gr = engine.load_m3u(spec["url"])
                else:
                    ch, gr = engine.load_xtream(spec["host"], spec["user"], spec["pass"])
                self._bridge.done.emit((True, ch, gr, ""))
            except Exception as e:
                self._bridge.done.emit((False, [], [], str(e)))

        def done(res):
            self.setEnabled(True)
            ok, ch, gr, err = res
            if not ok:
                QMessageBox.warning(self, "Recargar", f"Fallo al recargar.\n{err}")
                return
            self.channels = ch
            entry = dict(self.entry)
            entry["channels"] = len(ch)
            entry["groups"] = len(gr)
            cfg.upsert_list(entry)
            self._set_groups(gr)
            self.filter_channels()
            self.statusBar().showMessage(f"Recargados {len(ch)} canales", 5000)

        try:
            self._bridge.done.disconnect()
        except Exception:
            pass
        self._bridge.done.connect(done)
        threading.Thread(target=work, daemon=True).start()

    def cycle_skin(self):
        names = skins.SKIN_NAMES
        cur = self._cfg.get("skin", skins.DEFAULT_SKIN)
        nxt = names[(names.index(cur) + 1) % len(names)] if cur in names else names[0]
        self._apply_skin(nxt, self._cfg.get("font_family"))

    def cycle_font(self):
        fams = skins.available_fonts()
        cur = self._cfg.get("font_family", skins.DEFAULT_FONT)
        nxt = fams[(fams.index(cur) + 1) % len(fams)] if cur in fams else fams[0]
        self._apply_skin(self._cfg.get("skin"), nxt)

    def _apply_skin(self, skin, font):
        from PyQt6.QtWidgets import QApplication

        skin, fam = skins.apply_look(QApplication.instance(), skin, font)
        cfg.save_settings({"skin": skin, "font_family": fam})
        self._cfg["skin"] = skin
        self._cfg["font_family"] = fam
        self.statusBar().showMessage(f"Tema {skin} · {fam}", 3000)

    def about(self):
        QMessageBox.about(self, "Danko TV", f"<b>Danko TV {self._ver}</b><br>Reproductor IPTV con reconexión seamless.")

    # --- canales ---
    def _set_groups(self, groups):
        self.group_combo.blockSignals(True)
        self.group_combo.clear()
        self.group_combo.addItem("Todas")
        for g in groups:
            self.group_combo.addItem(g)
        saved = self._cfg.get("last_group", "Todas")
        idx = self.group_combo.findText(saved)
        if idx >= 0:
            self.group_combo.setCurrentIndex(idx)
        self.group_combo.blockSignals(False)

    def filter_channels(self, *_):
        q = self.search.text().lower().strip()
        grp = self.group_combo.currentText()
        out = self.channels
        if grp != "Todas":
            out = [c for c in out if c.get("group") == grp]
        if q:
            out = [c for c in out if q in c.get("title", "").lower()]
        self.filtered = out
        self.channel_list.clear()
        for ch in out[:DISPLAY_LIMIT]:
            QListWidgetItem(f"{'🔴 ' if False else ''}{ch.get('title')}", self.channel_list)
        if len(out) > DISPLAY_LIMIT:
            it = QListWidgetItem(f"— y {len(out) - DISPLAY_LIMIT} más (filtra para ver) —")
            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.statusBar().showMessage(f"{len(out)}/{len(self.channels)} canales · {self.group_combo.count()-1} categorías", 5000)

    def on_select(self, item):
        row = self.channel_list.row(item)
        if row < 0 or row >= len(self.filtered):
            return
        ch = self.filtered[row]
        self._playing_idx = row
        if not self.player:
            try:
                wid = int(self.video_frame.winId())
                self.player = SeamlessPlayer(wid=wid if wid else None, cache_secs=int(self._cfg.get("cache_secs", 45)))
                self.player.on_double_click = self.toggle_fullscreen
            except Exception as e:
                QMessageBox.warning(self, "Video", f"No se pudo iniciar mpv:\n{e}\nsudo apt install libmpv2 mpv")
                return
        self.now_label.setText(f"▶ {ch.get('title')}  [{ch.get('group')}]")
        try:
            self.player.play(ch.get("url"), is_live=True)
        except Exception as e:
            QMessageBox.warning(self, "Video", f"Error: {e}")

    def _on_volume(self, v):
        if self.player:
            try:
                self.player.mpv.volume = v
            except Exception:
                pass

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Escape and self._video_max:
            self.toggle_fullscreen()
            return
        if ev.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen()
            return
        if ev.key() == Qt.Key.Key_Space:
            self.toggle_play()
            return
        super().keyPressEvent(ev)

    def showEvent(self, event):
        super().showEvent(event)
        cfg.save_settings({"last_list": self.entry.get("name", ""), "last_group": self.group_combo.currentText()})

    def closeEvent(self, event):
        cfg.save_settings({"last_group": self.group_combo.currentText()})
        if self.player:
            try:
                self.player.stop()
                self.player.terminate()
            except Exception:
                pass
        event.accept()
