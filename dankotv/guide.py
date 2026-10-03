"""Guía de programación Danko TV: grilla completa con ambos buscadores."""
import threading

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget,
    QListWidgetItem, QLabel, QStatusBar, QMessageBox,
)

from .home import _Bridge


class GuideWindow(QDialog):
    """Grilla EPG de los canales candidatos (solo filas con datos).

    candidates: canales a escanear (la vista principal pasa su lista ya
    filtrada por grupo/búsqueda, con tope). Doble clic sintoniza el canal.
    """

    def __init__(self, parent, entry, candidates, on_pick=None):
        super().__init__(parent)
        self.entry = entry or {}
        self.candidates = candidates or []
        self.on_pick = on_pick
        self._rows = []  # [(channel, [programmes])]
        self._by_url = {}
        name = self.entry.get("name", "")
        self.setWindowTitle(f"Guía — {name}" if name else "Guía")
        self.resize(760, 520)
        lay = QVBoxLayout(self)

        filt = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔎 Buscar canal...")
        self.search.textChanged.connect(self._apply_filters)
        filt.addWidget(self.search, stretch=2)
        self.gsearch = QLineEdit()
        self.gsearch.setPlaceholderText("🔎 Buscar categoría...")
        self.gsearch.textChanged.connect(self._apply_filters)
        filt.addWidget(self.gsearch, stretch=1)
        lay.addLayout(filt)

        self.info = QLabel("Cargando guía...")
        self.info.setObjectName("muted")
        lay.addWidget(self.info)

        self.rows = QListWidget()
        self.rows.itemDoubleClicked.connect(self._pick)
        lay.addWidget(self.rows, stretch=1)

        self.status = QStatusBar()
        lay.addWidget(self.status)
        self._scan()

    def _scan(self):
        bridge = _Bridge(self._on_scan, self)

        def work():
            try:
                from . import epg as epgmod

                rows = epgmod.guide_rows(self.entry, self.candidates)
                bridge.done.emit((rows, ""))
            except Exception as e:
                bridge.done.emit(([], str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _on_scan(self, rows, err):
        self._rows = rows or []
        self._by_url = {c.get("url"): c for c, _ in self._rows}
        if err:
            self.info.setText(f"Guía no disponible ({err})")
        elif not self._rows:
            self.info.setText("Sin datos de programación para estos canales "
                              "(el proveedor no publica EPG).")
        else:
            self.info.setText(f"{len(self._rows)} canales con programación "
                              f"(de {len(self.candidates)} escaneados).")
        self._apply_filters()

    def _apply_filters(self):
        try:
            from . import epg as epgmod

            q = self.search.text().lower().strip()
            gq = self.gsearch.text().lower().strip()
            self.rows.clear()
            n = 0
            for ch, progs in self._rows:
                if q and q not in (ch.get("title") or "").lower():
                    continue
                if gq and gq not in (ch.get("group") or "").lower():
                    continue
                for p in progs:
                    txt = (f"{epgmod.fmt_time(p.get('start'))} "
                           f"{p.get('title')} — {ch.get('title')} "
                           f"[{ch.get('group')}]")
                    it = QListWidgetItem(txt, self.rows)
                    it.setData(Qt.ItemDataRole.UserRole, ch.get("url"))
                    n += 1
                    if n >= 2000:
                        break
                if n >= 2000:
                    break
            self.status.showMessage(f"{n} programas", 4000)
        except Exception:
            pass

    def _pick(self, item):
        url = item.data(Qt.ItemDataRole.UserRole) if item else None
        ch = self._by_url.get(url) if url else None
        if not ch:
            return
        try:
            if self.on_pick:
                self.on_pick(ch)
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Guía", f"No se pudo sintonizar:\n{e}")
