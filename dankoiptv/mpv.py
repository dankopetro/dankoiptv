# -*- coding: utf-8 -*-
"""Robust libmpv ctypes binding — wid INT64, FLAG separados, locks sin deadlock."""
import ctypes
import ctypes.util
import logging
import threading

log = logging.getLogger("dankoiptv.mpv")

def _find_libmpv():
    tried = []
    # 1) find_library
    try:
        lib = ctypes.util.find_library("mpv")
        tried.append(f"find_library -> {lib}")
        if lib:
            try:
                h = ctypes.CDLL(lib, mode=ctypes.RTLD_GLOBAL)
                log.info(f"libmpv loaded via find_library: {lib}")
                return h
            except Exception as e:
                tried.append(f"{lib}: {e}")
    except Exception as e:
        tried.append(f"find_library error: {e}")
    # 2) paths absolutos explícitos (más robusto dentro de AppImage)
    for path in ["/usr/lib/x86_64-linux-gnu/libmpv.so.2", "/usr/lib/x86_64-linux-gnu/libmpv.so.1", "libmpv.so.2", "libmpv.so.1"]:
        try:
            h = ctypes.CDLL(path, mode=ctypes.RTLD_GLOBAL)
            log.info(f"libmpv loaded via {path}")
            return h
        except Exception as e:
            tried.append(f"{path}: {e}")
    raise RuntimeError("No se encontró libmpv2. Instala con: sudo apt install libmpv2 mpv\nIntentos: " + " | ".join(tried))

libmpv = _find_libmpv()

libmpv.mpv_create.restype = ctypes.c_void_p
libmpv.mpv_initialize.argtypes = [ctypes.c_void_p]
libmpv.mpv_initialize.restype = ctypes.c_int
libmpv.mpv_terminate_destroy.argtypes = [ctypes.c_void_p]
libmpv.mpv_command.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p)]
libmpv.mpv_command.restype = ctypes.c_int
libmpv.mpv_set_option_string.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
libmpv.mpv_set_option_string.restype = ctypes.c_int
libmpv.mpv_set_option.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p]
libmpv.mpv_set_option.restype = ctypes.c_int
libmpv.mpv_get_property.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p]
libmpv.mpv_get_property.restype = ctypes.c_int
libmpv.mpv_set_property.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p]
libmpv.mpv_set_property.restype = ctypes.c_int
libmpv.mpv_observe_property.argtypes = [ctypes.c_void_p, ctypes.c_ulonglong, ctypes.c_char_p, ctypes.c_int]
libmpv.mpv_observe_property.restype = ctypes.c_int
libmpv.mpv_wait_event.argtypes = [ctypes.c_void_p, ctypes.c_double]
libmpv.mpv_wait_event.restype = ctypes.c_void_p
try:
    libmpv.mpv_error_string.argtypes = [ctypes.c_int]
    libmpv.mpv_error_string.restype = ctypes.c_char_p
except Exception:
    pass
try:
    libmpv.mpv_free.argtypes = [ctypes.c_void_p]
except Exception:
    pass

MPV_FORMAT_NONE = 0
MPV_FORMAT_STRING = 1
MPV_FORMAT_OSD_STRING = 2
MPV_FORMAT_FLAG = 3
MPV_FORMAT_INT64 = 4
MPV_FORMAT_DOUBLE = 5

class MpvEvent(ctypes.Structure):
    _fields_ = [("event_id", ctypes.c_int), ("error", ctypes.c_int), ("reply_userdata", ctypes.c_ulonglong), ("data", ctypes.c_void_p)]

class MpvEventProperty(ctypes.Structure):
    _fields_ = [("name", ctypes.c_char_p), ("format", ctypes.c_int), ("data", ctypes.c_void_p)]

def _err_str(code):
    try:
        s = libmpv.mpv_error_string(code)
        return s.decode() if s else str(code)
    except Exception:
        return str(code)

class MPV:
    def __init__(self, wid=None, options=None):
        try:
            self.handle = libmpv.mpv_create()
        except Exception as e:
            raise RuntimeError(f"mpv_create excepción: {e}. Verifica libmpv2 instalado (sudo apt install libmpv2)") from e
        if not self.handle:
            raise RuntimeError("mpv_create devolvió NULL (sin memoria o libmpv dañada). Reinstala: sudo apt install --reinstall libmpv2 mpv")
        # wid como INT64 antes de initialize (evita string-embed fallos)
        if wid is not None:
            v = ctypes.c_int64(int(wid))
            rc = libmpv.mpv_set_option(self.handle, b"wid", MPV_FORMAT_INT64, ctypes.byref(v))
            if rc < 0:
                log.warning(f"mpv_set_option wid INT64 failed ({_err_str(rc)}), fallback string")
                libmpv.mpv_set_option_string(self.handle, b"wid", str(int(wid)).encode())
        if options:
            for k, v in options.items():
                rc = libmpv.mpv_set_option_string(self.handle, k.encode(), str(v).encode())
                if rc < 0:
                    log.warning(f"mpv option {k}={v} failed: {_err_str(rc)}")
        for k, v in [("hr-seek", "no"), ("force-window", "yes")]:
            libmpv.mpv_set_option_string(self.handle, k.encode(), v.encode())
        rc = libmpv.mpv_initialize(self.handle)
        if rc < 0:
            raise RuntimeError(f"mpv_initialize: {_err_str(rc)}")
        self._property_cbs = {}
        self._event_cbs = {}
        self._running = True
        self._cmd_lock = threading.Lock()
        self._ev_thread = threading.Thread(target=self._event_loop, daemon=True)
        self._ev_thread.start()

    def set_option_string(self, name, value):
        with self._cmd_lock:
            rc = libmpv.mpv_set_option_string(self.handle, name.encode(), str(value).encode())
            if rc < 0:
                log.warning(f"set_option_string {name} failed: {_err_str(rc)}")

    def command(self, *args):
        c_args = (ctypes.c_char_p * (len(args) + 1))()
        for i, a in enumerate(args):
            c_args[i] = str(a).encode()
        c_args[len(args)] = None
        with self._cmd_lock:
            rc = libmpv.mpv_command(self.handle, c_args)
        if rc < 0:
            log.warning(f"mpv command {args} failed: {_err_str(rc)}")
        return rc

    def play(self, url):
        return self.command("loadfile", url, "replace")

    def stop(self):
        return self.command("stop")

    def set_property(self, name, value):
        b = name.encode()
        with self._cmd_lock:
            if isinstance(value, bool):
                v = ctypes.c_int(1 if value else 0)
                rc = libmpv.mpv_set_property(self.handle, b, MPV_FORMAT_FLAG, ctypes.byref(v))
            elif isinstance(value, int) and name in ("wid",):
                v = ctypes.c_int64(int(value))
                rc = libmpv.mpv_set_property(self.handle, b, MPV_FORMAT_INT64, ctypes.byref(v))
            elif isinstance(value, (int, float)):
                v = ctypes.c_double(float(value))
                rc = libmpv.mpv_set_property(self.handle, b, MPV_FORMAT_DOUBLE, ctypes.byref(v))
            else:
                v = ctypes.c_char_p(str(value).encode())
                rc = libmpv.mpv_set_property(self.handle, b, MPV_FORMAT_STRING, ctypes.byref(v))
        if rc < 0:
            log.warning(f"set_property {name}={value} failed: {_err_str(rc)}")

    def get_property(self, name, fmt=MPV_FORMAT_STRING):
        b = name.encode()
        with self._cmd_lock:
            if fmt == MPV_FORMAT_STRING:
                v = ctypes.c_char_p()
                rc = libmpv.mpv_get_property(self.handle, b, MPV_FORMAT_STRING, ctypes.byref(v))
                if rc >= 0 and v.value:
                    s = v.value.decode()
                    try: libmpv.mpv_free(v)
                    except Exception: pass
                    return s
            elif fmt == MPV_FORMAT_FLAG:
                v = ctypes.c_int()
                rc = libmpv.mpv_get_property(self.handle, b, MPV_FORMAT_FLAG, ctypes.byref(v))
                if rc >= 0: return bool(v.value)
            elif fmt == MPV_FORMAT_DOUBLE:
                v = ctypes.c_double()
                rc = libmpv.mpv_get_property(self.handle, b, MPV_FORMAT_DOUBLE, ctypes.byref(v))
                if rc >= 0: return v.value
        return None

    def observe_property(self, name, reply_userdata=0, fmt=MPV_FORMAT_STRING):
        with self._cmd_lock:
            rc = libmpv.mpv_observe_property(self.handle, reply_userdata, name.encode(), fmt)
            if rc < 0:
                log.warning(f"observe {name} failed: {_err_str(rc)}")

    def register_event_callback(self, event_id, cb):
        self._event_cbs.setdefault(event_id, []).append(cb)

    def register_property_observer(self, name, cb, fmt=MPV_FORMAT_STRING):
        self._property_cbs[name] = (cb, fmt)
        self.observe_property(name, fmt=fmt)

    def _event_loop(self):
        while self._running:
            ev_ptr = libmpv.mpv_wait_event(self.handle, 0.5)
            if not ev_ptr:
                continue
            ev = ctypes.cast(ev_ptr, ctypes.POINTER(MpvEvent)).contents
            if ev.event_id == 0:
                continue
            if ev.event_id == 7 and ev.data:
                prop = ctypes.cast(ev.data, ctypes.POINTER(MpvEventProperty)).contents
                if prop.name:
                    pname = prop.name.decode()
                    if pname in self._property_cbs:
                        cb, fmt = self._property_cbs[pname]
                        val = None
                        try:
                            if prop.format == MPV_FORMAT_FLAG and prop.data:
                                val = bool(ctypes.cast(prop.data, ctypes.POINTER(ctypes.c_int)).contents.value)
                            elif prop.format == MPV_FORMAT_STRING and prop.data:
                                p = ctypes.cast(prop.data, ctypes.POINTER(ctypes.c_char_p)).contents.value
                                val = p.decode() if p else ""
                            elif prop.format == MPV_FORMAT_DOUBLE and prop.data:
                                val = ctypes.cast(prop.data, ctypes.POINTER(ctypes.c_double)).contents.value
                            elif prop.format == MPV_FORMAT_INT64 and prop.data:
                                val = ctypes.cast(prop.data, ctypes.POINTER(ctypes.c_int64)).contents.value
                        except Exception as e:
                            log.error(f"prop {pname} parse failed: {e}")
                        try:
                            cb(val)
                        except Exception as e:
                            log.error(f"prop cb {pname}: {e}")
            if ev.event_id in self._event_cbs:
                for cb in self._event_cbs[ev.event_id]:
                    try: cb(ev)
                    except Exception as e: log.error(f"event {ev.event_id}: {e}")

    def terminate(self):
        self._running = False
        if self.handle:
            libmpv.mpv_terminate_destroy(self.handle)
            self.handle = None
