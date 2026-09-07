"""Vista principal Danko TV: video embebido + canales, layout declarativo."""
import threading
import time
from PyQt6.QtCore import Qt, QEvent, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QCursor, QGuiApplication, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QListWidget,
    QLineEdit, QPushButton, QLabel, QSplitter, QFrame, QComboBox,
    QStatusBar, QMenuBar, QListWidgetItem, QMessageBox, QSlider,
    QMenu, QApplication,
)

from . import config as cfg
from . import engine
from . import layout as L
from . import skins
from .home import NewListDialog, load_spec, _Bridge
from .player import SeamlessPlayer

DISPLAY_LIMIT = 2000
FS_LIST_WIDTH = 360
FS_OPACITY = 0.75
FS_CURSOR_SECS = 1.0
FS_FLAGS = (
    Qt.WindowType.CustomizeWindowHint
    | Qt.WindowType.FramelessWindowHint
    | Qt.WindowType.X11BypassWindowManagerHint
)
FS_FLAGS_INPUT = FS_FLAGS | Qt.WindowType.Popup


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
        self._playing_url = ""
        self._playing_title = ""
        self._apply_window_chrome()
        self._build_ui()
        self.setStatusBar(QStatusBar())
        self.set_list(self.entry, self.channels, groups or [])

    def _apply_window_flags(self):
        """Decoración clásica X11: minimizar, maximizar y cerrar."""
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setMaximumSize(16777215, 16777215)

    def _apply_window_chrome(self):
        self._apply_window_flags()
        w, h = 960, 540
        screen = QGuiApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            w = min(w, max(640, avail.width() - 80))
            h = min(h, max(400, avail.height() - 80))
            self.resize(w, h)
            self.move(
                avail.x() + (avail.width() - w) // 2,
                avail.y() + (avail.height() - h) // 2,
            )
        else:
            self.resize(w, h)

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
        self._refresh_fav_btn()

    # --- UI construida desde layout.py ---
    def _build_ui(self):
        self._fullscreen = False
        self._fs_locked = False
        self._fs_geom = None
        self._fs_was_max = False
        self._fs_splitter = None
        self._fs_cursor_until = 0.0
        self._fs_last_cursor = None
        mb = QMenuBar(self)
        self.menubar = mb
        self.setMenuBar(mb)
        for menu_name, items in L.MENUS.items():
            m = mb.addMenu(menu_name)
            for it in items:
                sub = it.get("submenu")
                if sub:
                    sm = m.addMenu(it["label"])
                    self._fill_choice_menu(sm, sub)
                    continue
                act = QAction(it["label"], self)
                act.setToolTip(it.get("tip", ""))
                if it.get("id") == "quit":
                    act.setShortcut(QKeySequence("Ctrl+Q"))
                slot = getattr(self, it["slot"], None)
                if slot:
                    act.triggered.connect(slot)
                m.addAction(act)

        central = QWidget(self)
        self.setCentralWidget(central)
        main = QHBoxLayout(central)
        main.setContentsMargins(8, 8, 8, 8)
        self._main_layout = main
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter = splitter
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
        self.channel_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.channel_list.customContextMenuRequested.connect(self._channel_menu)
        sl.addWidget(self.channel_list, stretch=1)
        splitter.addWidget(side)

        right = QWidget()
        self._right = right
        rl = QVBoxLayout(right)
        self._right_layout = rl
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
        self.fav_btn = QPushButton("☆")
        self.fav_btn.setObjectName("favBtn")
        self.fav_btn.setCheckable(True)
        self.fav_btn.setToolTip("Favorito (F)")
        self.fav_btn.clicked.connect(self.toggle_favorite)
        bar.addWidget(self.fav_btn)
        rl.addWidget(self.toolbar)
        splitter.addWidget(right)
        splitter.setSizes([280, 680])
        self._init_fs_shells()
        self._esc_shortcut = QShortcut(QKeySequence("Esc"), self)
        self._esc_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._esc_shortcut.setEnabled(False)
        self._esc_shortcut.activated.connect(self._on_escape)

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
        """Pantalla completa de monitor: ⛶, doble clic, F11 o Esc."""
        if self._fs_locked:
            return
        if self._fullscreen:
            self._leave_fullscreen()
        else:
            self._enter_fullscreen()

    def go_home(self):
        if self._fullscreen:
            self.toggle_fullscreen()
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

    def edit_list(self):
        if not self.entry.get("name"):
            self.add_list()
            return
        dlg = NewListDialog(self, self.entry)
        if not dlg.exec():
            return
        spec = dlg._spec
        old = dlg._old_name
        conn_keys = ("type", "url", "host", "user", "pass")
        conn_changed = any(spec.get(k) != self.entry.get(k) for k in conn_keys)
        merged = dict(self.entry)
        merged.update(spec)
        cfg.upsert_list(merged, old_name=old)
        self.entry = merged
        self.setWindowTitle(f"Danko TV {self._ver} — {merged.get('name')}")
        self.statusBar().showMessage(f"Lista '{merged.get('name')}' actualizada", 4000)
        if conn_changed:
            self.reload_list()

    def quit_app(self):
        QApplication.instance().quit()

    def reload_list(self):
        if not self.entry.get("name") or not self.entry.get("type"):
            self.add_list()
            return
        spec = {k: self.entry[k] for k in ("name", "type", "url", "host", "user", "pass") if k in self.entry}
        self.statusBar().showMessage("Recargando lista...")
        self.setEnabled(False)

        def on_done(ok, ch, gr, err):
            self.setEnabled(True)
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

        bridge = _Bridge(on_done, self)

        def work():
            try:
                if spec["type"] == "m3u":
                    ch, gr = engine.load_m3u(spec["url"])
                else:
                    ch, gr = engine.load_xtream(spec["host"], spec["user"], spec["pass"])
                bridge.done.emit((True, ch, gr, ""))
            except Exception as e:
                bridge.done.emit((False, [], [], str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _fill_choice_menu(self, menu, kind):
        grp = QActionGroup(self)
        grp.setExclusive(True)
        if kind == "skins":
            names = skins.SKIN_NAMES
            cur = self._cfg.get("skin", skins.DEFAULT_SKIN)
            self._skin_acts = []
            for name in names:
                act = QAction(name, self)
                act.setCheckable(True)
                act.setChecked(name == cur)
                act.triggered.connect(lambda _=False, n=name: self._apply_skin(n, self._cfg.get("font_family")))
                grp.addAction(act)
                menu.addAction(act)
                self._skin_acts.append(act)
        elif kind == "fonts":
            names = skins.available_fonts()
            cur = self._cfg.get("font_family", skins.DEFAULT_FONT)
            self._font_acts = []
            for name in names:
                act = QAction(name, self)
                act.setCheckable(True)
                act.setChecked(name == cur)
                act.triggered.connect(lambda _=False, n=name: self._apply_skin(self._cfg.get("skin"), n))
                grp.addAction(act)
                menu.addAction(act)
                self._font_acts.append(act)

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
        for act in getattr(self, "_skin_acts", []):
            act.setChecked(act.text() == skin)
        for act in getattr(self, "_font_acts", []):
            act.setChecked(act.text() == fam)
        self.statusBar().showMessage(f"Tema {skin} · {fam}", 3000)

    def about(self):
        QMessageBox.about(self, "Danko TV", f"<b>Danko TV {self._ver}</b><br>Reproductor IPTV con reconexión seamless.")

    # --- canales ---
    def _set_groups(self, groups):
        self.group_combo.blockSignals(True)
        self.group_combo.clear()
        self.group_combo.addItem("Todas")
        self.group_combo.addItem("★ Favoritos")
        for g in groups:
            self.group_combo.addItem(g)
        saved = self._cfg.get("last_group", "Todas")
        idx = self.group_combo.findText(saved)
        if idx >= 0:
            self.group_combo.setCurrentIndex(idx)
        self.group_combo.blockSignals(False)

    def _fav_urls(self):
        return set(cfg.favorites_for(self.entry.get("name", "")))

    def filter_channels(self, *_):
        q = self.search.text().lower().strip()
        grp = self.group_combo.currentText()
        out = self.channels
        favs = self._fav_urls()
        if grp == "★ Favoritos":
            out = [c for c in out if c.get("url") in favs]
        elif grp and grp != "Todas":
            out = [c for c in out if c.get("group") == grp]
        if q:
            out = [c for c in out if q in c.get("title", "").lower()]
        self.filtered = out
        self.channel_list.clear()
        for ch in out[:DISPLAY_LIMIT]:
            star = "★ " if ch.get("url") in favs else ""
            QListWidgetItem(f"{star}{ch.get('title')}", self.channel_list)
        if len(out) > DISPLAY_LIMIT:
            it = QListWidgetItem(f"— y {len(out) - DISPLAY_LIMIT} más (filtra para ver) —")
            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        cats = max(0, self.group_combo.count() - 2)
        self.statusBar().showMessage(f"{len(out)}/{len(self.channels)} canales · {cats} categorías", 5000)

    def _channel_at_item(self, item):
        if not item:
            return None
        row = self.channel_list.row(item)
        if row < 0 or row >= len(self.filtered):
            return None
        return self.filtered[row]

    def _channel_menu(self, pos):
        item = self.channel_list.itemAt(pos)
        ch = self._channel_at_item(item)
        if not ch:
            return
        menu = QMenu(self)
        is_fav = ch.get("url") in self._fav_urls()
        act = menu.addAction("Quitar de favoritos" if is_fav else "Agregar a favoritos")
        chosen = menu.exec(self.channel_list.mapToGlobal(pos))
        if chosen == act:
            self._toggle_fav_url(ch.get("url"), ch.get("title"))

    def toggle_favorite(self):
        ch = None
        if self._playing_url:
            for c in self.channels:
                if c.get("url") == self._playing_url:
                    ch = c
                    break
        if not ch:
            item = self.channel_list.currentItem()
            ch = self._channel_at_item(item)
        if not ch:
            self._refresh_fav_btn()
            self.statusBar().showMessage("Reproducí un canal para marcarlo favorito", 3000)
            return
        self._toggle_fav_url(ch.get("url"), ch.get("title"))

    def _toggle_fav_url(self, url, title=""):
        name = self.entry.get("name", "")
        if not name or not url:
            return
        on = cfg.toggle_favorite(name, url)
        self.filter_channels()
        self._refresh_fav_btn()
        self.statusBar().showMessage(
            f"{'★ Favorito' if on else 'Favorito quitado'}: {title}", 3000
        )

    def _refresh_fav_btn(self):
        on = bool(self._playing_url) and self._playing_url in self._fav_urls()
        self.fav_btn.blockSignals(True)
        self.fav_btn.setChecked(on)
        self.fav_btn.setText("★" if on else "☆")
        self.fav_btn.blockSignals(False)

    def on_select(self, item):
        row = self.channel_list.row(item)
        if row < 0 or row >= len(self.filtered):
            return
        ch = self.filtered[row]
        self._playing_idx = row
        self._playing_url = ch.get("url") or ""
        self._playing_title = ch.get("title") or ""
        if not self.player:
            try:
                wid = int(self.video_frame.winId())
                self.player = SeamlessPlayer(wid=wid if wid else None, cache_secs=int(self._cfg.get("cache_secs", 45)))
                self.player.on_double_click = self.toggle_fullscreen
            except Exception as e:
                QMessageBox.warning(self, "Video", f"No se pudo iniciar mpv:\n{e}\nsudo apt install libmpv2 mpv")
                return
        self.now_label.setText(f"▶ {ch.get('title')}  [{ch.get('group')}]")
        self._refresh_fav_btn()
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
        if ev.key() == Qt.Key.Key_Escape and self._fullscreen:
            self._on_escape()
            return
        if ev.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen()
            return
        if ev.key() == Qt.Key.Key_Space:
            self.toggle_play()
            return
        if ev.key() == Qt.Key.Key_F and not ev.modifiers():
            self.toggle_favorite()
            return
        super().keyPressEvent(ev)

    def showEvent(self, event):
        super().showEvent(event)
        cfg.save_settings({"last_list": self.entry.get("name", ""), "last_group": self.group_combo.currentText()})

    def closeEvent(self, event):
        cfg.save_settings({"last_group": self.group_combo.currentText()})
        if self._fullscreen:
            try:
                self._leave_fullscreen()
            except Exception:
                pass
        for w in (getattr(self, "_fs_list", None), getattr(self, "_fs_bar", None)):
            if w is not None:
                w.hide()
                w.deleteLater()
        if self.player:
            try:
                self.player.stop()
                self.player.terminate()
            except Exception:
                pass
        event.accept()

    # --- pantalla completa ---
    def _make_fs_shell(self, want_keys=False):
        w = QWidget(None)
        w.setWindowFlags(FS_FLAGS_INPUT if want_keys else FS_FLAGS)
        w.setWindowOpacity(FS_OPACITY)
        if not want_keys:
            w.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        return w

    def _init_fs_shells(self):
        self._fs_list = self._make_fs_shell(want_keys=True)
        self._fs_bar = self._make_fs_shell(want_keys=False)
        self._fs_timer = QTimer(self)
        self._fs_timer.setInterval(100)
        self._fs_timer.timeout.connect(self._fs_tick)
        self._fs_list.installEventFilter(self)
        self.search.installEventFilter(self)

    def eventFilter(self, obj, ev):
        if (
            self._fullscreen
            and ev.type() == QEvent.Type.KeyPress
            and ev.key() == Qt.Key.Key_Escape
        ):
            self._on_escape()
            return True
        return super().eventFilter(obj, ev)

    def _set_osc(self, on):
        if not self.player:
            return
        try:
            self.player.mpv.osc = bool(on)
        except Exception:
            pass

    def _enter_fullscreen(self):
        self._fs_locked = True
        try:
            self._fs_geom = [
                self.geometry().x(),
                self.geometry().y(),
                self.width(),
                self.height(),
            ]
            self._fs_was_max = self.isMaximized()
            self._fs_splitter = self.splitter.sizes()
            self.menubar.hide()
            self.statusBar().hide()
            self.now_label.hide()
            self._main_layout.setContentsMargins(0, 0, 0, 0)
            self.video_frame.setStyleSheet(
                "background-color: black; border: none; border-radius: 0;"
            )
            self._fs_list.layout().addWidget(self.sidebar)
            self._fs_bar.layout().addWidget(self.toolbar)
            self.sidebar.show()
            self.toolbar.show()
            self._fullscreen = True
            self.showFullScreen()
            self.raise_()
            self.activateWindow()
            self._set_osc(False)
            now = time.monotonic()
            self._fs_last_cursor = QCursor.pos()
            self._fs_cursor_until = now + FS_CURSOR_SECS
            self._fs_list.hide()
            self._fs_bar.hide()
            self._fs_timer.start()
            self._esc_shortcut.setEnabled(True)
        finally:
            self._fs_locked = False

    def _leave_fullscreen(self):
        self._fs_locked = True
        try:
            self._fs_timer.stop()
            self._esc_shortcut.setEnabled(False)
            try:
                self.search.clearFocus()
            except Exception:
                pass
            self._fs_list.hide()
            self._fs_bar.hide()
            self.video_frame.unsetCursor()
            self.splitter.insertWidget(0, self.sidebar)
            self._right_layout.addWidget(self.now_label)
            self._right_layout.addWidget(self.toolbar)
            self.sidebar.setMinimumWidth(0)
            self.sidebar.setMaximumWidth(16777215)
            self.sidebar.show()
            self.toolbar.show()
            self.now_label.show()
            self.menubar.show()
            self.statusBar().show()
            self._main_layout.setContentsMargins(8, 8, 8, 8)
            self.video_frame.setStyleSheet("background-color: black;")
            if self._fs_splitter:
                self.splitter.setSizes(self._fs_splitter)
            else:
                self.splitter.setSizes([280, 680])
            self._fullscreen = False
            self._set_osc(True)
            if self._fs_was_max:
                self.showMaximized()
            else:
                self.showNormal()
                if self._fs_geom:
                    self.setGeometry(*self._fs_geom)
        finally:
            self._fs_locked = False

    def _place_fs_list(self):
        g = self.geometry()
        self.sidebar.setFixedWidth(FS_LIST_WIDTH)
        self._fs_list.setWindowFlags(FS_FLAGS_INPUT)
        self._fs_list.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self._fs_list.setGeometry(g.x(), g.y(), FS_LIST_WIDTH, g.height())
        self._fs_list.show()
        self._fs_list.raise_()
        self._fs_list.activateWindow()

    def _fs_bar_geom(self):
        g = self.geometry()
        self.toolbar.adjustSize()
        hint = self.toolbar.sizeHint()
        w = min(g.width() - 24, max(hint.width() + 24, 520))
        h = max(hint.height() + 16, 56)
        x = g.x() + (g.width() - w) // 2
        y = g.y() + g.height() - h - 40
        return x, y, w, h

    def _place_fs_bar(self):
        x, y, w, h = self._fs_bar_geom()
        self._fs_bar.setGeometry(x, y, w, h)
        self._fs_bar.show()
        self._fs_bar.raise_()

    def _hide_fs_list(self):
        try:
            self.search.clearFocus()
            self.group_combo.clearFocus()
        except Exception:
            pass
        self._fs_list.hide()
        self.activateWindow()

    def _on_escape(self):
        if not self._fullscreen:
            return
        if self._fs_list.isVisible() or self._fs_bar.isVisible() or self.search.hasFocus():
            self._hide_fs_list()
            self._hide_fs_bar()
            return
        self.toggle_fullscreen()

    def _hide_fs_bar(self):
        self._fs_bar.hide()

    def _fs_tick(self):
        if not self._fullscreen:
            return
        pos = QCursor.pos()
        last = self._fs_last_cursor
        if last is None:
            last = pos
            self._fs_last_cursor = pos
        offset = abs(pos.x() - last.x()) + abs(pos.y() - last.y())
        now = time.monotonic()
        if offset > 5:
            self._fs_last_cursor = pos
            self._fs_cursor_until = now + FS_CURSOR_SECS
        geo = self.geometry()
        inside = (
            pos.x() >= geo.x()
            and pos.x() < geo.x() + geo.width()
            and pos.y() >= geo.y()
            and pos.y() < geo.y() + geo.height()
        )
        local = self.mapFromGlobal(pos)
        left_zone = inside and local.x() < FS_LIST_WIDTH + 10
        bx, by, bw, bh = self._fs_bar_geom()
        pad = 16
        bar_zone = (
            pos.x() >= bx - pad
            and pos.x() < bx + bw + pad
            and pos.y() >= by - pad
            and pos.y() < by + bh + pad
        )
        if left_zone:
            if not self._fs_list.isVisible():
                self._place_fs_list()
        elif self._fs_list.isVisible():
            self._hide_fs_list()
        if bar_zone:
            if not self._fs_bar.isVisible():
                self._place_fs_bar()
        elif self._fs_bar.isVisible():
            self._hide_fs_bar()
        try:
            if now < self._fs_cursor_until:
                self.video_frame.unsetCursor()
            else:
                self.video_frame.setCursor(Qt.CursorShape.BlankCursor)
        except Exception:
            pass
