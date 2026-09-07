"""Reproductor Danko TV: libmpv embebido + motor seamless AGENTS §3."""
import logging
import threading
import time

from .engine import ensure_engine_path

ensure_engine_path()
from thirdparty import mpv as mpv_mod

log = logging.getLogger("dankotv.player")


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
        try:
            self.mpv.loop = False
        except Exception:
            pass

        @self.mpv.property_observer("eof-reached")
        def _eof(_name, value):
            self._on_eof(value)

        @self.mpv.event_callback("file-loaded")
        def _loaded(_event):
            self._err_retries = 0
            self._cascade = 0

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
                self.mpv.force_seekable = False
            else:
                self.mpv.keep_open = False
                self.mpv.force_seekable = True
                self.mpv.loop_playlist = "no"
        except Exception as e:
            log.warning("seamless opts failed: %s", e)
        log.info("Playing %s: %s", "LIVE" if is_live else "VOD", url[:80])
        self.mpv.play(url)

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

    # --- seamless engine ---
    def _on_eof(self, value):
        if value is not True or not self._armed or not self.is_live:
            return
        if not self.current_url:
            return
        now = time.time()
        self._cascade = self._cascade + 1 if (now - self._last_eof) < 20 else 0
        self._last_eof = now
        delay = min(self._cascade * 2, 8)
        log.info("Stream EOF - seamless reload in %ss (cascade %s)", delay, self._cascade)
        if not self._reloading:
            threading.Thread(
                target=self._reload_worker, args=(delay,), daemon=True
            ).start()

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
