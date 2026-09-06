# -*- coding: utf-8 -*-
"""Robust libmpv binding — diag, fallback python-mpv, wid INT64 fix."""
import ctypes
import ctypes.util
import logging
import os
import subprocess
import threading

log = logging.getLogger("dankoiptv.mpv")

MPV_FORMAT_NONE = 0
MPV_FORMAT_STRING = 1
MPV_FORMAT_OSD_STRING = 2
MPV_FORMAT_FLAG = 3
MPV_FORMAT_INT64 = 4
MPV_FORMAT_DOUBLE = 5

def _diag():
    """Colecta diagnóstico para mensaje de error."""
    lines = []
    try:
        import dankoiptv as _pkg
        lines.append(f"dankoiptv {_pkg.__version__}")
    except Exception:
        pass
    try:
        lines.append(f"find_library(mpv)={ctypes.util.find_library('mpv')}")
    except Exception as e:
        lines.append(f"find_library error: {e}")
    for p in ["/usr/lib/x86_64-linux-gnu/libmpv.so.2", "/usr/lib/x86_64-linux-gnu/libmpv.so.2.2.0", "/usr/lib/x86_64-linux-gnu/libmpv.so.1"]:
        lines.append(f"{p} exists={os.path.exists(p)}")
    try:
        out = subprocess.run(["ldd", "/usr/lib/x86_64-linux-gnu/libmpv.so.2"], capture_output=True, text=True, timeout=3)
        if "not found" in out.stdout:
            lines.append("ldd: " + [l for l in out.stdout.splitlines() if "not found" in l][0])
        else:
            lines.append("ldd ok")
    except Exception as e:
        lines.append(f"ldd error: {e}")
    try:
        import sys
        lines.append(f"python {sys.version.split()[0]} arch={'64' if ctypes.sizeof(ctypes.c_void_p)==8 else '32'}")
    except Exception:
        pass
    try:
        lines.append(f"libmpv={getattr(libmpv, '_name', '?')}")
    except Exception:
        pass
    return " | ".join(lines)

def _load_libmpv_handle():
    """Carga libmpv priorizando rutas absolutas (AppImage no tiene ld cache)."""
    tried = []
    candidates = [
        "/usr/lib/x86_64-linux-gnu/libmpv.so.2",
        "/usr/lib/x86_64-linux-gnu/libmpv.so.2.2.0",
        "/usr/lib/x86_64-linux-gnu/libmpv.so.1",
        "libmpv.so.2",
        "libmpv.so.1",
    ]
    # find_library al final para no depender de ldconfig dentro de AppImage
    try:
        lib = ctypes.util.find_library("mpv")
        if lib and lib not in candidates:
            candidates.append(lib)
    except Exception as e:
        tried.append(f"find_library: {e}")

    last_err = None
    for cand in candidates:
        for mode in [ctypes.RTLD_GLOBAL, 0]:
            try:
                h = ctypes.CDLL(cand, mode=mode)
                h.mpv_client_api_version.restype = ctypes.c_ulong
                ver = h.mpv_client_api_version()
                if ver == 0:
                    tried.append(f"{cand} mode={mode}: api_version 0")
                    continue
                h.mpv_create.restype = ctypes.c_void_p
                # no hacer test create/destroy aquí — deja el estado global limpio
                log.info(f"libmpv OK {cand} mode={mode} api=0x{ver:x}")
                return h
            except Exception as e:
                last_err = e
                tried.append(f"{cand} mode={mode}: {e}")
    diag = _diag()
    raise RuntimeError(
        "No se pudo cargar libmpv. "
        "sudo apt update && sudo apt install --reinstall libmpv2 mpv && sudo ldconfig\n"
        f"Intentos: {' | '.join(tried)}\nDiagnóstico: {diag}\nÚltimo error: {last_err}"
    )

libmpv = _load_libmpv_handle()

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
try:
    libmpv.mpv_client_api_version.restype = ctypes.c_ulong
except Exception:
    pass

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
        # reintento por si el primer create falla por estado global (raro en AppImage)
        last = None
        for attempt in range(3):
            try:
                h = libmpv.mpv_create()
            except Exception as e:
                last = e
                h = None
            if h:
                self.handle = h
                break
            last = f"attempt {attempt+1} NULL"
            import time as _t; _t.sleep(0.05)
        else:
            # guarda diag en archivo para el usuario
            diag = _diag()
            try:
                os.makedirs(os.path.expanduser("~/.config/dankoiptv"), exist_ok=True)
                with open(os.path.expanduser("~/.config/dankoiptv/mpv_diag.log"), "w") as f:
                    f.write(diag + f"\nlast={last}\n")
            except Exception:
                pass
            raise RuntimeError(f"mpv_create devolvió NULL tras 3 intentos. {diag} | last={last}")
        if wid is not None and int(wid) != 0:
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

    def _valid(self):
        return self.handle is not None and self._running

    def set_option_string(self, name, value):
        if not self._valid():
            return
        with self._cmd_lock:
            if not self.handle:
                return
            rc = libmpv.mpv_set_option_string(self.handle, name.encode(), str(value).encode())
            if rc < 0:
                log.warning(f"set_option_string {name} failed: {_err_str(rc)}")

    def command(self, *args):
        if not self._valid():
            log.warning(f"command {args} ignored — handle invalid")
            return -1
        c_args = (ctypes.c_char_p * (len(args) + 1))()
        for i, a in enumerate(args):
            c_args[i] = str(a).encode()
        c_args[len(args)] = None
        with self._cmd_lock:
            if not self.handle:
                return -1
            rc = libmpv.mpv_command(self.handle, c_args)
        if rc < 0:
            log.warning(f"mpv command {args} failed: {_err_str(rc)}")
        return rc

    def play(self, url):
        return self.command("loadfile", url, "replace")

    def stop(self):
        return self.command("stop")

    def set_property(self, name, value):
        if not self._valid():
            return
        b = name.encode()
        with self._cmd_lock:
            if not self.handle:
                return
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
        if not self._valid():
            return None
        b = name.encode()
        with self._cmd_lock:
            if not self.handle:
                return None
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
        if not self._valid():
            return
        with self._cmd_lock:
            if not self.handle:
                return
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
            try:
                if not self.handle:
                    break
                ev_ptr = libmpv.mpv_wait_event(self.handle, 0.5)
            except Exception:
                break
            if not ev_ptr:
                continue
            try:
                ev = ctypes.cast(ev_ptr, ctypes.POINTER(MpvEvent)).contents
            except Exception:
                break
            if ev.event_id == 0:  # MPV_EVENT_NONE
                continue
            if ev.event_id == 1:  # MPV_EVENT_SHUTDOWN
                break
            if ev.event_id == 7 and ev.data:
                try:
                    prop = ctypes.cast(ev.data, ctypes.POINTER(MpvEventProperty)).contents
                except Exception:
                    continue
                if prop.name:
                    try:
                        pname = prop.name.decode()
                    except Exception:
                        continue
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
        # despertar wait_event y esperar hilo antes de destruir
        try:
            if self.handle:
                # enviar wakeup via terminate_destroy que interrumpe wait_event
                libmpv.mpv_terminate_destroy(self.handle)
        except Exception:
            pass
        try:
            if hasattr(self, '_ev_thread') and self._ev_thread.is_alive():
                self._ev_thread.join(timeout=1.0)
        except Exception:
            pass
        self.handle = None
