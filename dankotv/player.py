"""Reproductor Danko TV: libmpv embebido + motor seamless AGENTS §3."""
import logging
import threading
import time

from PyQt6.QtCore import QObject, pyqtSignal

from .engine import ensure_engine_path

ensure_engine_path()
from thirdparty import mpv as mpv_mod

log = logging.getLogger("dankotv.player")


class _PlayerBridge(QObject):
    """Puente mpv (hilos libmpv) → Qt (hilo GUI). Señales, no colas: el
    delivery en el hilo Qt lo garantiza Qt mismo."""
    eof_reached = pyqtSignal(bool)
    file_loaded = pyqtSignal()
    end_file = pyqtSignal(str)
    time_pos = pyqtSignal(float)
    seekable = pyqtSignal(bool)
    paused_for_cache = pyqtSignal(bool)


class SeamlessPlayer:
    """Una instancia mpv reutilizada. Live: keep-open + eof cascade."""

    def __init__(self, wid=None, cache_secs=45):
        self._wid = wid
        self._cache_secs = cache_secs
        self.current_url = ""
        self.is_live = True
        self._cascade = 0
        self._last_eof = 0
        self._reloading = False
        self._armed = True
        self._err_retries = 0
        self.on_double_click = None  # MainWindow lo setea: maximizar video
        self.on_eof = None           # MainWindow: cascade visible (opcional)
        self.on_position = None      # MainWindow: tira "AHORA 1:23:45" (opcional)
        self.on_cache_pause = None   # MainWindow: aviso "cargando…" (opcional)
        self._build_player()

    def _base_options(self):
        opts = dict(
            osc=True,
            hwdec="no",
            ytdl=False,
            title="Danko TV",
            **{"force-window": True},
            **{"audio-client-name": "dankotv"},
            **{"input-vo-keyboard": False},
            loglevel="info",
            **{
                "script-opts": (
                    "osc-layout=slimbox,osc-seekbarstyle=bar,"
                    "osc-deadzonesize=0,osc-minmousemove=3,osc-idlescreen=no"
                )
            },
        )
        if self._wid:
            opts["wid"] = str(int(self._wid))
        return opts

    def _build_player(self):
        self.mpv = mpv_mod.MPV(**self._base_options())
        if self._cache_secs:
            try:
                self.mpv.demuxer_readahead_secs = self._cache_secs
                self.mpv.cache_secs = self._cache_secs
            except Exception:
                pass
        # Time-shift del vivo: se puede arrastrar la barra HACIA ATRÁS dentro
        # de lo ya reproducido (buffer de demuxer). Sin esto mpv rechaza el
        # seek en vivo (force-seekable=False del motor seamless).
        try:
            self.mpv.force_seekable = True
        except Exception:
            pass
        try:
            self.mpv.cache = True
        except Exception:
            pass
        # Puente de eventos al hilo Qt (señales; ver _PlayerBridge).
        self._bridge = _PlayerBridge()
        self._bridge.eof_reached.connect(self._on_eof)
        self._bridge.file_loaded.connect(self._on_loaded)
        self._bridge.end_file.connect(self._on_end_file)
        self._bridge.time_pos.connect(self._on_time_pos)
        self._bridge.seekable.connect(self._on_seekable)
        self._bridge.paused_for_cache.connect(self._on_paused_for_cache)
        try:
            self.mpv.loop = False
        except Exception:
            pass

        @self.mpv.property_observer("eof-reached")
        def _eof(_name, value):
            self._bridge.eof_reached.emit(value is True)

        @self.mpv.event_callback("file-loaded")
        def _loaded(_event):
            self._bridge.file_loaded.emit()

        @self.mpv.event_callback("end_file")
        def _end(_event):
            try:
                d = _event.as_dict()
                reason = bytes(d.get("reason", b"")).decode("utf-8", "replace") if "reason" in d else ""
            except Exception:
                reason = ""
            self._bridge.end_file.emit(reason)

        # Posición de reproducción → tira "AHORA" y estado del time-shift.
        @self.mpv.property_observer("time-pos")
        def _tpos(_name, value):
            try:
                self._bridge.time_pos.emit(float(value) if value is not None else -1.0)
            except Exception:
                pass

        # ¿Se puede seekear en este archivo? (live con buffer = sí)
        @self.mpv.property_observer("seekable")
        def _seekable(_name, value):
            try:
                self._bridge.seekable.emit(bool(value))
            except Exception:
                pass

        @self.mpv.property_observer("paused-for-cache")
        def _paused_cache(_name, value):
            try:
                self._bridge.paused_for_cache.emit(bool(value))
            except Exception:
                pass

        # mpv captura el mouse del video embebido: el doble clic llega
        # aquí, no al QWidget. Se reenvía al hilo Qt vía singleShot.
        try:
            @self.mpv.on_key_press("MBTN_LEFT_DBL")
            def _dbl(*_a):
                cb = self.on_double_click
                if cb:
                    try:
                        from PyQt6.QtCore import QTimer

                        QTimer.singleShot(0, cb)
                    except Exception:
                        pass
        except Exception as e:
            log.warning("dblclick binding failed: %s", e)

        @self.mpv.event_callback("end_file")
        def _end(_event):
            try:
                reason = ""
                d = _event.as_dict()
                if "reason" in d:
                    reason = bytes(d["reason"]).decode("utf-8", "replace")
            except Exception:
                reason = ""
            if "error" in reason:
                self._on_error()

    # --- API ---
    def play(self, url, is_live=True):
        self.current_url = url
        self.is_live = is_live
        self._armed = True
        self._cascade = 0
        try:
            if is_live:
                self.mpv.keep_open = True
                self.mpv.keep_open_pause = False
                self.mpv.loop_playlist = "no"
                # force-seekable solo si el buffer de rebobinado está activo;
                # en .ts directo vivo forzar seekable entrecorta la reproducción.
                self.mpv.force_seekable = bool(self._buffer_mins and self._cache_secs > 45)
            else:
                self.mpv.keep_open = False
                self.mpv.force_seekable = True
                self.mpv.loop_playlist = "no"
        except Exception as e:
            log.warning("seamless opts failed: %s", e)
        log.info("Playing %s: %s", "LIVE" if is_live else "VOD", url[:80])
        self.mpv.play(url)

    def set_cache_secs(self, secs):
        """Ajusta el buffer de rebobinado en caliente (segundos). 0 = dejar
        el default. Solo aplica a la próxima recarga/abertura del stream."""
        self._cache_secs = int(secs)
        try:
            if self._cache_secs:
                self.mpv.demuxer_readahead_secs = self._cache_secs
                self.mpv.cache_secs = self._cache_secs
        except Exception:
            pass

    def seek_relative(self, delta_s):
        """Seek relativo (segundos, negativo = atrás)."""
        try:
            self.mpv.command("seek", delta_s, "relative")
        except Exception as e:
            log.warning("seek failed: %s", e)

    def seek_absolute(self, secs):
        """Seek absoluto (segundos desde el inicio del archivo)."""
        try:
            self.mpv.command("seek", secs, "absolute")
        except Exception as e:
            log.warning("seek failed: %s", e)

    @property
    def position(self):
        """Posición actual en segundos (0.0 si no hay nada cargado)."""
        try:
            return float(self.mpv.time_pos or 0.0)
        except Exception:
            return 0.0

    @property
    def duration(self):
        """Duración total (0.0 si se desconoce)."""
        try:
            return float(self.mpv.duration or 0.0)
        except Exception:
            return 0.0

    @property
    def paused(self):
        try:
            return bool(self.mpv.pause)
        except Exception:
            return False

    @paused.setter
    def paused(self, value):
        try:
            self.mpv.pause = bool(value)
        except Exception:
            pass

    def stop(self):
        self._armed = False
        self._reloading = False
        try:
            self.mpv.keep_open = False
        except Exception:
            pass
        try:
            self.mpv.command("stop")
        except Exception as e:
            log.warning("stop failed: %s", e)

    def toggle_fullscreen_mpv(self):
        try:
            self.mpv.command("cycle", "fullscreen")
        except Exception:
            pass

    def terminate(self):
        try:
            self.mpv.terminate()
        except Exception:
            pass

    # --- seamless engine (slots de Qt; llegan por la señal del bridge) ---
    def _on_eof(self, value):
        if not value or not self._armed or not self.is_live:
            return
        if not self.current_url:
            return
        now = time.time()
        self._cascade = self._cascade + 1 if (now - self._last_eof) < 20 else 0
        self._last_eof = now
        delay = min(self._cascade * 2, 8)
        log.info("Stream EOF - seamless reload in %ss (cascade %s)", delay, self._cascade)
        if self.on_eof:
            try:
                self.on_eof(delay, self._cascade)
            except Exception:
                pass
        if not self._reloading:
            threading.Thread(
                target=self._reload_worker, args=(delay,), daemon=True
            ).start()

    def _on_loaded(self):
        self._err_retries = 0
        self._cascade = 0

    def _on_end_file(self, reason):
        if "error" in reason:
            self._on_error()

    def _on_time_pos(self, pos):
        if self.on_position:
            try:
                self.on_position(pos)
            except Exception:
                pass

    def _on_seekable(self, value):
        # Sin callback asignado no hay nada que hacer (igual se emite barato)
        pass

    def _on_paused_for_cache(self, value):
        if self.on_cache_pause:
            try:
                self.on_cache_pause(value)
            except Exception:
                pass

    def _reload_worker(self, delay):
        self._reloading = True
        if delay:
            time.sleep(delay)
        self._reloading = False
        if self._armed and self.current_url:
            try:
                self.mpv.play(self.current_url)
            except Exception as e:
                log.warning("seamless reload failed: %s", e)

    def _on_error(self):
        self._err_retries += 1
        if self._armed and self.is_live and self._err_retries <= 10:
            delay = min(2 ** (self._err_retries - 1), 30)
            log.warning(
                "Playback error, retry %s/10 in %ss", self._err_retries, delay
            )

            def _w():
                time.sleep(delay)
                if self._armed and self.current_url:
                    try:
                        self.mpv.play(self.current_url)
                    except Exception as e:
                        log.warning("error retry failed: %s", e)

            threading.Thread(target=_w, daemon=True).start()
