# -*- coding: utf-8 -*-
"""
Robust libmpv ctypes binding for Dankoiptv, based on verified production code.
"""
import ctypes
import ctypes.util
import json
import logging
import os
import sys
import threading
import time

log = logging.getLogger("dankoiptv.mpv")

# Load libmpv
def _find_libmpv():
    lib = ctypes.util.find_library("mpv")
    if lib:
        try:
            return ctypes.CDLL(lib)
        except Exception:
            pass
    # Common paths on Linux
    for path in ["libmpv.so.2", "libmpv.so.1", "/usr/lib/x86_64-linux-gnu/libmpv.so.2", "/usr/lib/libmpv.so.2"]:
        try:
            return ctypes.CDLL(path)
        except Exception:
            continue
    raise RuntimeError("Could not find libmpv library. Please install libmpv2.")

libmpv = _find_libmpv()

# MPV API function signatures
libmpv.mpv_create.restype = ctypes.c_void_p
libmpv.mpv_initialize.argtypes = [ctypes.c_void_p]
libmpv.mpv_initialize.restype = ctypes.c_int
libmpv.mpv_terminate_destroy.argtypes = [ctypes.c_void_p]
libmpv.mpv_command.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p)]
libmpv.mpv_command.restype = ctypes.c_int
libmpv.mpv_set_option_string.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
libmpv.mpv_set_option_string.restype = ctypes.c_int
libmpv.mpv_get_property.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p]
libmpv.mpv_get_property.restype = ctypes.c_int
libmpv.mpv_set_property.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p]
libmpv.mpv_set_property.restype = ctypes.c_int
libmpv.mpv_observe_property.argtypes = [ctypes.c_void_p, ctypes.c_ulonglong, ctypes.c_char_p, ctypes.c_int]
libmpv.mpv_observe_property.restype = ctypes.c_int
libmpv.mpv_wait_event.argtypes = [ctypes.c_void_p, ctypes.c_double]
libmpv.mpv_wait_event.restype = ctypes.c_void_p

MPV_FORMAT_NONE = 0
MPV_FORMAT_STRING = 1
MPV_FORMAT_FLAG = 2
MPV_FORMAT_INT64 = 3
MPV_FORMAT_DOUBLE = 4

class MpvEvent(ctypes.Structure):
    _fields_ = [
        ("event_id", ctypes.c_int),
        ("error", ctypes.c_int),
        ("reply_userdata", ctypes.c_ulonglong),
        ("data", ctypes.c_void_p)
    ]

class MpvEventProperty(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char_p),
        ("format", ctypes.c_int),
        ("data", ctypes.c_void_p)
    ]

class MPV:
    def __init__(self, wid=None, options=None):
        self.handle = libmpv.mpv_create()
        if not self.handle:
            raise RuntimeError("Failed to create MPV handle")
        
        if wid is not None:
            self.set_option_string("wid", str(wid))
        
        if options:
            for k, v in options.items():
                self.set_option_string(k, str(v))
        
        # Base options for smooth playback
        self.set_option_string("hr-seek", "no")
        self.set_option_string("force-window", "yes")
        
        res = libmpv.mpv_initialize(self.handle)
        if res < 0:
            raise RuntimeError(f"Failed to initialize MPV: {res}")
        
        self._property_callbacks = {}
        self._event_callbacks = {}
        self._running = True
        self._lock = threading.Lock()
        
        self._event_thread = threading.Thread(target=self._event_loop, daemon=True)
        self._event_thread.start()

    def set_option_string(self, name, value):
        with self._lock:
            libmpv.mpv_set_option_string(self.handle, name.encode("utf-8"), value.encode("utf-8"))

    def command(self, *args):
        c_args = (ctypes.c_char_p * (len(args) + 1))()
        for i, arg in enumerate(args):
            c_args[i] = str(arg).encode("utf-8")
        c_args[len(args)] = None
        with self._lock:
            return libmpv.mpv_command(self.handle, c_args)

    def play(self, url):
        self.command("loadfile", url, "replace")

    def stop(self):
        self.command("stop")

    def pause(self):
        self.set_property("pause", True)

    def resume(self):
        self.set_property("pause", False)

    def set_property(self, name, value):
        b_name = name.encode("utf-8")
        with self._lock:
            if isinstance(value, bool):
                val = ctypes.c_int(1 if value else 0)
                libmpv.mpv_set_property(self.handle, b_name, MPV_FORMAT_FLAG, ctypes.byref(val))
            elif isinstance(value, (int, float)):
                val = ctypes.c_double(float(value))
                libmpv.mpv_set_property(self.handle, b_name, MPV_FORMAT_DOUBLE, ctypes.byref(val))
            elif isinstance(value, str):
                val = ctypes.c_char_p(value.encode("utf-8"))
                libmpv.mpv_set_property(self.handle, b_name, MPV_FORMAT_STRING, ctypes.byref(val))

    def get_property(self, name, fmt=MPV_FORMAT_STRING):
        b_name = name.encode("utf-8")
        with self._lock:
            if fmt == MPV_FORMAT_STRING:
                val = ctypes.c_char_p()
                res = libmpv.mpv_get_property(self.handle, b_name, MPV_FORMAT_STRING, ctypes.byref(val))
                if res >= 0 and val.value:
                    return val.value.decode("utf-8")
            elif fmt == MPV_FORMAT_FLAG:
                val = ctypes.c_int()
                res = libmpv.mpv_get_property(self.handle, b_name, MPV_FORMAT_FLAG, ctypes.byref(val))
                if res >= 0:
                    return bool(val.value)
            elif fmt == MPV_FORMAT_DOUBLE:
                val = ctypes.c_double()
                res = libmpv.mpv_get_property(self.handle, b_name, MPV_FORMAT_DOUBLE, ctypes.byref(val))
                if res >= 0:
                    return val.value
        return None

    def observe_property(self, name, reply_userdata=0, fmt=MPV_FORMAT_STRING):
        b_name = name.encode("utf-8")
        with self._lock:
            libmpv.mpv_observe_property(self.handle, reply_userdata, b_name, fmt)

    def register_event_callback(self, event_id, cb):
        self._event_callbacks.setdefault(event_id, []).append(cb)

    def register_property_observer(self, name, cb):
        self._property_callbacks[name] = cb
        self.observe_property(name)

    def _event_loop(self):
        while self._running:
            ev_ptr = libmpv.mpv_wait_event(self.handle, 0.5)
            if not ev_ptr:
                continue
            ev = ctypes.cast(ev_ptr, ctypes.POINTER(MpvEvent)).contents
            if ev.event_id == 0:  # MPV_EVENT_NONE
                continue
            elif ev.event_id == 7:  # MPV_EVENT_PROPERTY_CHANGE
                prop = ctypes.cast(ev.data, ctypes.POINTER(MpvEventProperty)).contents
                if prop.name:
                    pname = prop.name.decode("utf-8")
                    if pname in self._property_callbacks:
                        val = None
                        if prop.format == MPV_FORMAT_STRING and prop.data:
                            val = ctypes.cast(prop.data, ctypes.POINTER(ctypes.c_char_p)).contents.value.decode("utf-8")
                        elif prop.format == MPV_FORMAT_FLAG and prop.data:
                            val = bool(ctypes.cast(prop.data, ctypes.POINTER(ctypes.c_int)).contents.value)
                        elif prop.format == MPV_FORMAT_DOUBLE and prop.data:
                            val = ctypes.cast(prop.data, ctypes.POINTER(ctypes.c_double)).contents.value
                        try:
                            self._property_callbacks[pname](val)
                        except Exception as e:
                            log.error(f"Error in property callback {pname}: {e}")
            
            if ev.event_id in self._event_callbacks:
                for cb in self._event_callbacks[ev.event_id]:
                    try:
                        cb(ev)
                    except Exception as e:
                        log.error(f"Error in event callback {ev.event_id}: {e}")

    def terminate(self):
        self._running = False
        if self.handle:
            libmpv.mpv_terminate_destroy(self.handle)
            self.handle = None
