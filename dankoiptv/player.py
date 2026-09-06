# -*- coding: utf-8 -*-
"""Player wrapper — keep-open + eof-reached FLAG con cascade backoff."""
import logging
import threading
import time
from .mpv import MPV, MPV_FORMAT_FLAG

log = logging.getLogger("dankoiptv.player")

class IPTVPlayer:
    def __init__(self, wid=None, cache_secs=45):
        options = {
            "osc": "yes", "hwdec": "no", "ytdl": "no", "force-window": "yes",
            "cache": "yes", "demuxer-max-bytes": "150M",
            "demuxer-readahead-secs": str(cache_secs), "cache-secs": str(cache_secs),
            "loglevel": "info",
        }
        self.mpv = MPV(wid=wid, options=options)
        self.is_live = True
        self.current_url = None
        self._cascade = 0
        self._last_eof = 0
        self._reconnecting = False
        self._stopped = False
        # eof-reached es FLAG — registrar con formato correcto
        self.mpv.register_property_observer("eof-reached", self._on_eof, fmt=MPV_FORMAT_FLAG)

    def play(self, url, is_live=True):
        self.current_url = url
        self.is_live = is_live
        self._stopped = False
        self._cascade = 0
        try:
            if is_live:
                self.mpv.set_property("keep-open", True)
                self.mpv.set_property("keep-open-pause", False)
                self.mpv.set_property("loop-playlist", "no")
                self.mpv.set_property("force-seekable", False)
            else:
                self.mpv.set_property("keep-open", False)
                self.mpv.set_property("force-seekable", True)
        except Exception as e:
            log.warning(f"set_property live/vod failed: {e}")
        log.info(f"Playing {'LIVE' if is_live else 'VOD'}: {url[:80]}...")
        rc = self.mpv.play(url)
        if rc < 0:
            log.error(f"loadfile failed rc={rc}")

    def stop(self):
        self._stopped = True
        try: self.mpv.set_property("keep-open", False)
        except Exception: pass
        self.mpv.stop()

    def _on_eof(self, val):
        if not self.is_live or self._stopped:
            return
        if val is True:
            now = time.time()
            self._cascade = self._cascade + 1 if (now - self._last_eof) < 20 else 0
            self._last_eof = now
            delay = min(self._cascade * 2, 8)
            log.info(f"Stream EOF — reload in {delay}s (cascade {self._cascade})")
            if not self._reconnecting:
                threading.Thread(target=self._reload_worker, args=(delay,), daemon=True).start()

    def _reload_worker(self, delay):
        self._reconnecting = True
        if delay: time.sleep(delay)
        if not self._stopped and self.current_url:
            log.info(f"Reloading {self.current_url[:80]}...")
            self.mpv.play(self.current_url)
        self._reconnecting = False
