"""Pantalla inicial Danko TV: Mis listas + diálogo Nueva lista."""
import threading
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QPushButton, QLabel, QDialog, QLineEdit, QTabWidget, QMessageBox,
    QFormLayout, QDialogButtonBox, QSplitter, QFrame, QListWidgetItem,
)

from . import config as cfg
from . import engine


class _Bridge(QObject):
    done = pyqtSignal(object)

    def __init__(self, callback=None, parent=None):
        super().__init__(parent)
        self.callback = callback
        if callback:
            self.done.connect(self._handle)

    def _handle(self, res):
        if self.callback:
            if isinstance(res, tuple):
                self.callback(*res)
            else:
                self.callback(res)


def load_spec(spec, parent, on_done):
    """Carga canales de un spec {type m3u|xtream,...} en hilo.
    on_done(ok, channels, groups, err) corre en hilo Qt."""
    bridge = _Bridge(on_done, parent)

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


class NewListDialog(QDialog):
    """Nueva lista: nombre + URL M3U o credenciales Xtream + probar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nueva lista")
        self.resize(480, 340)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Ej: Mi proveedor")
        form.addRow("Nombre:", self.name_edit)
        lay.addLayout(form)

        self.tabs = QTabWidget()
        # M3U
        m3u_w = QWidget()
        ml = QVBoxLayout(m3u_w)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("http://proveedor:8080/get.php?username=...&type=m3u_plus")
        ml.addWidget(QLabel("URL de la lista M3U:"))
        ml.addWidget(self.url_edit)
        self.tabs.addTab(m3u_w, "M3U (URL)")
        # Xtream
        xt_w = QWidget()
        xl = QFormLayout(xt_w)
        self.host_edit = QLineEdit()
        self.host_edit.setPlaceholderText("http://proveedor:8080")
        self.user_edit = QLineEdit()
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        xl.addRow("Servidor:", self.host_edit)
        xl.addRow("Usuario:", self.user_edit)
        xl.addRow("Clave:", self.pass_edit)
        self.tabs.addTab(xt_w, "Xtream")
        lay.addWidget(self.tabs)

        self.status = QLabel("")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)

        row = QHBoxLayout()
        self.test_btn = QPushButton("Probar conexión")
        self.test_btn.clicked.connect(self.test_connection)
        row.addWidget(self.test_btn)
        row.addStretch()
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Save).setText("Guardar")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        row.addWidget(btns)
        lay.addLayout(row)
        self._tested = None

    def spec(self):
        name = self.name_edit.text().strip()
        if not name:
            return None, "Ponle un nombre a la lista."
        if self.tabs.currentIndex() == 0:
            url = self.url_edit.text().strip()
            if not url:
                return None, "Pega la URL M3U."
            return {"name": name, "type": "m3u", "url": url}, ""
        host = self.host_edit.text().strip()
        user = self.user_edit.text().strip()
        pwd = self.pass_edit.text()
        if not (host and user and pwd):
            return None, "Completa servidor, usuario y clave."
        return {"name": name, "type": "xtream", "host": host, "user": user, "pass": pwd}, ""

    def test_connection(self):
        spec, err = self.spec()
        if err:
            self.status.setText(err)
            return
        self.test_btn.setEnabled(False)
        self.status.setText("Probando...")

        def on_done(ok, msg):
            self.test_btn.setEnabled(True)
            self._tested = ok
            self.status.setText(msg)

        bridge = _Bridge(on_done, self)

        def work():
            try:
                if spec["type"] == "m3u":
                    ch, _gr = engine.load_m3u(spec["url"])
                else:
                    ch, _gr = engine.load_xtream(spec["host"], spec["user"], spec["pass"])
                bridge.done.emit((True, f"OK: {len(ch)} canales encontrados."))
            except Exception as e:
                bridge.done.emit((False, f"Fallo: {e}"))

        threading.Thread(target=work, daemon=True).start()

    def accept(self):
        spec, err = self.spec()
        if err:
            QMessageBox.warning(self, "Nueva lista", err)
            return
        self._spec = spec
        super().accept()


class HomeWindow(QMainWindow):
    open_list = pyqtSignal(dict)
    back_main = pyqtSignal()

    def __init__(self, version=""):
        super().__init__()
        self._ver = version
        self.setWindowTitle(f"Danko TV {version} — Mis listas")
        self.resize(760, 520)
        central = QWidget(self)
        self.setCentralWidget(central)
        lay = QVBoxLayout(central)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)

        head = QHBoxLayout()
        title = QLabel("Danko TV")
        title.setObjectName("title")
        tf = QFont()
        tf.setPointSize(22)
        tf.setBold(True)
        title.setFont(tf)
        head.addWidget(title)
        head.addStretch()
        ver = QLabel(version)
        ver.setObjectName("muted")
        head.addWidget(ver)
        lay.addLayout(head)

        sub = QLabel("Tus listas IPTV — elige una para ver sus canales")
        sub.setObjectName("muted")
        lay.addWidget(sub)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._open_selected)
        lay.addWidget(self.list_widget, stretch=1)

        row = QHBoxLayout()
        self.back_btn = QPushButton("← Volver")
        self.back_btn.clicked.connect(self.back_main.emit)
        row.addWidget(self.back_btn)
        self.add_btn = QPushButton("＋ Nueva lista")
        self.add_btn.clicked.connect(self.add_list)
        row.addWidget(self.add_btn)
        self.open_btn = QPushButton("Abrir ▶")
        self.open_btn.clicked.connect(self._open_selected)
        row.addWidget(self.open_btn)
        self.del_btn = QPushButton("Eliminar")
        self.del_btn.clicked.connect(self.delete_selected)
        row.addWidget(self.del_btn)
        row.addStretch()
        lay.addLayout(row)
        self.refresh()

    def refresh(self):
        self.list_widget.clear()
        for e in cfg.load_lists():
            n = e.get("channels", 0)
            item = QListWidgetItem(f"📺  {e.get('name')}   ·   {e.get('type','m3u').upper()}   ·   {n} canales   ·   {e.get('updated','')}")
            item.setData(Qt.ItemDataRole.UserRole, e)
            self.list_widget.addItem(item)

    def add_list(self):
        dlg = NewListDialog(self)
        if dlg.exec():
            self.load_and_store(dlg._spec)

    def load_and_store(self, spec):
        box = QMessageBox(self)
        box.setWindowTitle("Cargando lista")
        box.setText(f"Descargando '{spec['name']}'... (puede tardar unos segundos)")
        box.setStandardButtons(QMessageBox.StandardButton.NoButton)
        box.show()

        def done(ok, ch, gr, err):
            box.close()
            box.deleteLater()
            if not ok or not ch:
                msg = QMessageBox(self)
                msg.setWindowTitle("Error")
                msg.setText(f"No se pudo cargar la lista.\n{err}")
                msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                msg.show()
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(5000, msg.close)
                return
            entry = dict(spec)
            entry["channels"] = len(ch)
            entry["groups"] = len(gr)
            cfg.upsert_list(entry)
            # cache en memoria de la sesión (canales completos)
            self._session_cache = getattr(self, "_session_cache", {})
            self._session_cache[entry["name"]] = (ch, gr)
            self.refresh()
            self.open_list.emit(entry)

        load_spec(spec, self, done)

    def _open_selected(self, *_):
        item = self.list_widget.currentItem()
        if not item:
            return
        entry = item.data(Qt.ItemDataRole.UserRole)
        if entry["name"] in getattr(self, "_session_cache", {}):
            self.open_list.emit(entry)
        else:
            # recargar canales de la lista guardada
            self.load_and_store({k: entry[k] for k in ("name", "type", "url", "host", "user", "pass") if k in entry})

    def delete_selected(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        entry = item.data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(self, "Eliminar", f"¿Eliminar '{entry['name']}'?") == QMessageBox.StandardButton.Yes:
            cfg.delete_list(entry["name"])
            self.refresh()
