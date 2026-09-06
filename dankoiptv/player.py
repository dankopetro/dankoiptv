# -*- coding: utf-8 -*-
"""
Player wrapper with production-verified seamless reconnection algorithm.
"""
import logging
import threading
import time
from .mpv import MPV

log = logging.getLogger("dankoiptv.player")

class IPTVPlayer:
    def __init__(self, wid=None, cache_secs=45):
        options = {
            "osc": "yes",
            "hwdec": "no",
            "ytdl": "no",
            "force-window": "yes",
            "cache": "yes",
            "demuxer-max-bytes": "150M",
            "demuxer-readahead-secs": str(cache_secs),
            "cache-secs": str(cache_secs),
            "loglevel": "info"
        }
        self.mpv = MPV(wid=wid, options=options)
        self.is_live = True
        self.current_url = None
        self._cascade_count = 0
        self._last_eof_time = 0
        self._reconnecting = False
        self._stopped_intentionally = False

        # Setup observers and callbacks
        self.mpv.register_property_observer("eof-reached", self._on_eof_changed)
        self.mpv.register_event_callback(0, self._on_event) # MPV_EVENT_NONE / generic

    def play(self, url, is_live=True):
        self.current_url = url
        self.is_live = is_live
        self._stopped_intentionally = False
        self._cascade_count = 0

        if is_live:
            self.mpv.set_property("keep-open", True)
            self.mpv.set_property("keep-open-pause", False)
            self.mpv.set_property("loop-playlist", "no")
            self.mpv.set_property("force-seekable", False)
        else:
            self.mpv.set_property("keep-open", False)
            self.mpv.set_property("force-seekable", True)

        log.info(f"Playing {'LIVE' if is_live else 'VOD'}: {url}")
        self.mpv.play(url)

    def stop(self):
        self._stopped_intentionally = True
        self.mpv.set_property("keep-open", False)
        self.mpv.stop()

    def _on_eof_changed(self, val):
        if not self.is_live or self._stopped_intentionally:
            return
        if val is True:
            now = time.time()
            if now - self._last_eof_time < 20:
                self._cascade_count += 1
            else:
                self._cascade_count = 0
            self._last_eof_time = now

            delay = min(self._cascade_count * 2, 8)
            log.info(f"Stream EOF detected - seamless reload in {delay}s (cascade {self._cascade_count})")
            
            if not self._reconnecting:
                threading.Thread(target=self._seamless_reload_worker, args=(delay,), daemon=True).start()

    def _seamless_reload_worker(self, delay):
        self._reconnecting = True
        if delay > 0:
            time.sleep(delay)
        if not self._stopped_intentionally and self.current_url:
            log.info(f"Reloading live stream: {self.current_url}")
            self.mpv.play(self.current_url)
        self._reconnecting = False

    def _on_event(self, ev):
        pass
