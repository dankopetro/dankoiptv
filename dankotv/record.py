"""Grabación Danko TV: ffmpeg -c copy a .ts + remux auto a .mp4.

El .mp4 directo es frágil (índice al final: si se corta, archivo muerto);
por eso se graba .ts resistente y al detener se convierte a .mp4 en segundos
sin recodificar. Subprocess puro, sin Qt.

Lección 14/11/2026 (bug "no guardó nada"): -live_start_index es opción
EXCLUSIVA del demuxer HLS; en streams .ts directos ffmpeg aborta en <1s
("Option live_start_index not found") sin crear el archivo. Solo se pasa
con URLs .m3u8, y si igual falla con esa opción se reintenta una vez sin
ella. stderr de ffmpeg SIEMPRE a ~/.config/dankotv/record.log (antes
DEVNULL: el error era invisible).
"""
import logging
import os
import re
import shutil
import subprocess
import threading
import time

log = logging.getLogger("dankotv.record")

REC_DIR = os.path.join(os.path.expanduser("~"), "Videos", "DankoTV")
CONFIG_DIR = os.path.expanduser("~/.config/dankotv")
REC_LOG = os.path.join(CONFIG_DIR, "record.log")
REC_LOG_MAX = 200 * 1024  # rotación: máx 200KB


def rec_dir():
    """Carpeta de grabaciones: settings["rec_dir"] si se eligió en
    Opciones > Carpeta de grabaciones…; si no, ~/Videos/DankoTV."""
    try:
        from . import config
        d = (config.load_settings().get("rec_dir") or "").strip()
        if d:
            return os.path.expanduser(d)
    except Exception:
        pass
    return REC_DIR


def ffmpeg_ok():
    return shutil.which("ffmpeg") is not None


def safe_name(title):
    s = re.sub(r"[^\w\d\- ]+", "", title or "canal", flags=re.UNICODE).strip()
    s = re.sub(r"\s+", "_", s)
    return (s or "canal")[:60]


def _paths(title):
    d = rec_dir()
    os.makedirs(d, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    base = os.path.join(d, f"{stamp}_{safe_name(title)}")
    return base + ".ts", base + ".mp4"


def _is_hls(url):
    """¿La URL es HLS? (-live_start_index solo aplica al demuxer hls)."""
    return ".m3u8" in url.split("?")[0].lower()


def _append_rec_log(text):
    """Escribe en record.log con rotación. Nunca lanza."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        if os.path.isfile(REC_LOG) and os.path.getsize(REC_LOG) > REC_LOG_MAX:
            os.replace(REC_LOG, REC_LOG + ".1")
        with open(REC_LOG, "a", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        pass


def _tail_rec_log(lines=8):
    try:
        with open(REC_LOG, encoding="utf-8", errors="replace") as f:
            return "\n".join(f.read().splitlines()[-lines:])
    except Exception:
        return ""


def build_cmd(url, ts_path, live):
    """Comando ffmpeg de grabación. live=True: ritmo 1:1 (-re) desde el
    borde; -live_start_index -1 SOLO en HLS (ver docstring)."""
    cmd = ["ffmpeg", "-nostats", "-hide_banner", "-loglevel", "warning",
           "-user_agent", "Mozilla/5.0"]
    if live:
        # Sin -re ffmpeg devora la ventana HLS publicada más rápido que el
        # vivo (10s pared -> 47s contenido, verificado 03/10/2026).
        cmd += ["-re"]
        if _is_hls(url):
            # Opción del demuxer hls: en .ts directo ffmpeg aborta
            # ("Option live_start_index not found") — bug 14/11/2026.
            cmd += ["-live_start_index", "-1"]
    cmd += ["-reconnect", "1", "-reconnect_streamed", "1",
            "-reconnect_on_network_error", "1",
            "-i", url, "-map", "0", "-codec", "copy",
            "-max_muxing_queue_size", "4096", "-y", ts_path]
    return cmd


def _spawn(cmd, log_path):
    """Arranca ffmpeg con stderr al record.log (append). Devuelve (proc, fh)."""
    fh = open(log_path, "a", encoding="utf-8", errors="replace")
    fh.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n"
             + " ".join(cmd) + "\n")
    fh.flush()
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=fh)
    # El hijo queda con su propio dup del fd; el padre puede cerrar el suyo.
    fh.close()
    return proc


def rebased_cmd(url, skip_secs, ts_path, live=True):
    """Como build_cmd pero descartando los primeros skip_secs del stream
    (para grabar DESDE el punto donde estás mirando, no desde el borde
    del vivo). Solo tiene sentido con skip_secs > 0. Respeta las mismas
    reglas de -live_start_index / -re que build_cmd."""
    if skip_secs is None or skip_secs <= 0:
        return build_cmd(url, ts_path, live)
    cmd = ["ffmpeg", "-nostats", "-hide_banner", "-loglevel", "warning",
           "-user_agent", "Mozilla/5.0"]
    if live:
        cmd += ["-re"]
        if _is_hls(url):
            cmd += ["-live_start_index", "-1"]
    cmd += ["-reconnect", "1", "-reconnect_streamed", "1",
            "-reconnect_on_network_error", "1",
            "-ss", str(int(skip_secs)), "-i", url,
            "-map", "0", "-codec", "copy",
            "-max_muxing_queue_size", "4096", "-y", ts_path]
    return cmd


def _wait_open(proc, ts_path, seconds=2.0):
    """Espera a que ffmpeg abra el stream. Devuelve True si sigue vivo o
    dejó archivo (modo archivo puede terminar descargando todo)."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        if proc.poll() is not None:
            return os.path.isfile(ts_path) and os.path.getsize(ts_path) > 0
        time.sleep(0.2)
    return True


def start(url, title, live=True, skip_secs=0):
    """Inicia ffmpeg. live=True: ritmo 1:1 desde el borde (HLS no corre).
    live=False (repetición/archivo): copia rápida del archivo completo.
    skip_secs>0: descarta los primeros segundos del stream (para grabar
    desde el punto donde estás mirando, no desde el borde del vivo).
    Devuelve (proc, ts_path, mp4_path) o lanza RuntimeError."""
    if not ffmpeg_ok():
        raise RuntimeError("Falta ffmpeg (sudo apt install ffmpeg)")
    if not url:
        raise RuntimeError("Sin URL para grabar.")
    ts_path, mp4_path = _paths(title)
    if skip_secs and skip_secs > 0:
        cmd = rebased_cmd(url, skip_secs, ts_path, live)
    else:
        cmd = build_cmd(url, ts_path, live)
    log.info("REC start: %s (skip=%ss)", ts_path, skip_secs)
    _append_rec_log(f"REC start live={live} skip={skip_secs} url={url}\n")
    proc = _spawn(cmd, REC_LOG)
    if _wait_open(proc, ts_path):
        return proc, ts_path, mp4_path
    # Falló al abrir: si fue por una opción rechazada, reintenta UNA vez
    # sin -live_start_index (cubre URLs sin .m3u8 que resultaron HLS y
    # viceversa). Cualquier otro error → dialogo con el log.
    if live and _is_hls(url):
        _append_rec_log("REC: reintento sin -live_start_index\n")
        retry = [c for c in cmd if c not in ("-live_start_index", "-1")]
        proc = _spawn(retry, REC_LOG)
        if _wait_open(proc, ts_path):
            return proc, ts_path, mp4_path
    tail = _tail_rec_log()
    raise RuntimeError(
        "ffmpeg no pudo abrir el stream.\n\nLog:\n" + (tail or "(vacío)"))


def stop(proc, ts_path, mp4_path):
    """Detiene y convierte a .mp4. Devuelve ruta final (.mp4 o .ts si falla)."""
    try:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except Exception:
                proc.kill()
    except Exception as e:
        log.warning("REC stop: %s", e)
    try:
        if os.path.isfile(ts_path) and os.path.getsize(ts_path) > 0:
            r = subprocess.run(
                ["ffmpeg", "-nostats", "-hide_banner", "-loglevel", "warning",
                 "-i", ts_path, "-codec", "copy", "-y", mp4_path],
                timeout=120, capture_output=True)
            if r.returncode == 0 and os.path.isfile(mp4_path):
                os.remove(ts_path)
                log.info("REC mp4: %s", mp4_path)
                _append_rec_log(f"REC mp4 ok: {mp4_path}\n")
                return mp4_path
            err = (r.stderr or b"").decode("utf-8", "replace").splitlines()[-8:]
            _append_rec_log("REC remux falló:\n" + "\n".join(err) + "\n")
        log.warning("REC remux falló, queda el .ts")
        return ts_path if os.path.isfile(ts_path) else None
    except Exception as e:
        log.warning("REC remux: %s", e)
        _append_rec_log(f"REC remux excepción: {e}\n")
        return ts_path if os.path.isfile(ts_path) else None


def duration_seconds(ts_path):
    """Duración del .ts en segundos (ffprobe). 0.0 si no se puede leer."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", ts_path],
            capture_output=True, text=True, timeout=15)
        return float((r.stdout or "0").strip() or 0.0)
    except Exception:
        return 0.0


def trim_and_remux(ts_path, mp4_path, start_s, keep_s, keep_source=False):
    """Corta [start_s, start_s+keep_s) del .ts y lo remuxe a .mp4.

    Lección 21/11/2026: cortar un .ts directo a .mp4 con -c copy PIERDE el
    video (PTS video arranca en 1.4s y audio en 0; ffmpeg descarta el
    primer GOP). Solución: cortar a un .ts intermedio (mismo formato, PTS
    consistentes) y de ahí remux a .mp4.
    keep_source=True: no borra ts_path (para cortes desde el buffer vivo).
    Devuelve la ruta final o lanza."""
    if not os.path.isfile(ts_path) or os.path.getsize(ts_path) == 0:
        raise RuntimeError("El archivo de grabación no existe o está vacío.")
    dur = duration_seconds(ts_path)
    if dur <= 0:
        # Sin duración conocida (ts "infinito"): usar keep_s tal cual.
        end_s = keep_s
    else:
        end_s = min(dur, start_s + keep_s)
    cut_ts = os.path.splitext(ts_path)[0] + ".cut.ts"
    cmd_cut = ["ffmpeg", "-nostats", "-hide_banner", "-loglevel", "warning",
               "-ss", f"{start_s:.2f}", "-to", f"{end_s:.2f}",
               "-i", ts_path, "-codec", "copy", "-y", cut_ts]
    r = subprocess.run(cmd_cut, timeout=300, capture_output=True)
    if r.returncode != 0 or not os.path.isfile(cut_ts) or os.path.getsize(cut_ts) == 0:
        err = (r.stderr or b"").decode("utf-8", "replace").splitlines()[-8:]
        _append_rec_log("REC recorte (ts) falló:\n" + "\n".join(err) + "\n")
        raise RuntimeError("ffmpeg no pudo recortar:\n" + "\n".join(err))
    cmd = ["ffmpeg", "-nostats", "-hide_banner", "-loglevel", "warning",
           "-i", cut_ts, "-codec", "copy", "-y", mp4_path]
    r2 = subprocess.run(cmd, timeout=300, capture_output=True)
    for f in (cut_ts, ts_path):
        if f == ts_path and keep_source:
            continue
        try:
            os.remove(f)
        except OSError:
            pass
    if r2.returncode == 0 and os.path.isfile(mp4_path):
        log.info("REC recorte %s-%ss → %s", start_s, end_s, mp4_path)
        _append_rec_log(f"REC recorte ok: {mp4_path} ({start_s:.0f}s+{keep_s:.0f}s)\n")
        return mp4_path
    err = (r2.stderr or b"").decode("utf-8", "replace").splitlines()[-8:]
    _append_rec_log("REC remux del recorte falló:\n" + "\n".join(err) + "\n")
    raise RuntimeError("ffmpeg no pudo remuxear el recorte:\n" + "\n".join(err))


# --- buffer continuo de vivo (Opción A) ---
BUFFER_DIR = os.path.join(CONFIG_DIR, "buffer")  # ~/.config/dankotv/buffer/


class LiveBuffer:
    """Graba continuamente el vivo a un .ts temporal para poder rebobinar
    y guardar los últimos X min SIN entrecortar la reproducción de mpv.

    ffmpeg escribe a ritmo real (-re) en un solo .ts. Un hilo monitor
    reinicia el archivo cuando supera max_minutes (ring buffer simple).
    Consume una conexión extra al proveedor (máx 3 en tu cuenta)."""

    def __init__(self, url, title, max_minutes=60):
        self.url = url
        self.title = title
        self.max_minutes = max_minutes
        self.proc = None
        self.ts_path = None
        self.start_wall = None
        self._active = False
        self.recording = False  # True mientras hay un recorte pendiente

    def start(self):
        self._active = True
        self._open()
        threading.Thread(target=self._monitor, daemon=True).start()

    def _open(self):
        os.makedirs(BUFFER_DIR, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        base = os.path.join(BUFFER_DIR, f"{stamp}_{safe_name(self.title)}")
        self.ts_path = base + ".ts"
        self.start_wall = time.time()
        cmd = build_cmd(self.url, self.ts_path, live=True)
        log.info("BUFFER start: %s (máx %s min)", self.ts_path, self.max_minutes)
        _append_rec_log(f"BUFFER start max={self.max_minutes} url={self.url}\n")
        self.proc = _spawn(cmd, REC_LOG)

    def _stop_proc_and_file(self):
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=8)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            self.proc = None
        if self.ts_path and os.path.isfile(self.ts_path):
            try:
                os.remove(self.ts_path)
            except OSError:
                pass
            self.ts_path = None

    def _monitor(self):
        while self._active and self.proc and self.proc.poll() is None:
            time.sleep(5)
            if self.recording:
                continue  # no reiniciar mientras se graba desde el buffer
            if self.start_wall and (time.time() - self.start_wall) > self.max_minutes * 60:
                try:
                    self._stop_proc_and_file()
                    if self._active:
                        self._open()
                except Exception:
                    log.warning("BUFFER restart falló", exc_info=True)
                    break

    def stop(self):
        self._active = False
        self._stop_proc_and_file()

    def is_active(self):
        return self._active and self.proc is not None and self.proc.poll() is None

    def duration(self):
        return duration_seconds(self.ts_path) if self.ts_path else 0.0

    def save_last(self, minutes, out_mp4):
        """Recorta los últimos `minutes` del buffer y los guarda como .mp4."""
        if not self.ts_path or not os.path.isfile(self.ts_path):
            raise RuntimeError("No hay buffer activo.")
        dur = self.duration()
        if dur <= 0:
            raise RuntimeError("Buffer vacío (todavía no hay datos).")
        keep = min(float(minutes) * 60.0, dur)
        start = max(0.0, dur - keep)
        return trim_and_remux(self.ts_path, out_mp4, start, keep, keep_source=True)

    def save_range(self, start_ago_s, end_ago_s, out_mp4, dur=None):
        """Guarda un rango del buffer: desde `start_ago_s` segundos atrás
        hasta `end_ago_s` segundos atrás (start_ago > end_ago).
        Ej. start_ago=180 (hace 3 min), end_ago=60 (hace 1 min) guarda
        el segmento de hace 3 min a hace 1 min. end_ago=0 = hasta ahora.
        `dur` se congela al abrir el diálogo para evitar desfase por el
        buffer que sigue creciendo."""
        if not self.ts_path or not os.path.isfile(self.ts_path):
            raise RuntimeError("No hay buffer activo.")
        if dur is None:
            dur = self.duration()
        if dur <= 0:
            raise RuntimeError("Buffer vacío (todavía no hay datos).")
        start = max(0.0, dur - float(start_ago_s))
        end = min(dur, dur - float(end_ago_s))
        if end <= start:
            raise RuntimeError("Rango vacío (start_ago debe ser > end_ago).")
        return trim_and_remux(self.ts_path, out_mp4, start, end - start, keep_source=True)

    def save_range_abs(self, start_s, end_s, out_mp4):
        """Guarda [start_s, end_s) en segundos absolutos del buffer.
        Usado cuando se congeló la duración en el diálogo."""
        if not self.ts_path or not os.path.isfile(self.ts_path):
            raise RuntimeError("No hay buffer activo.")
        dur = self.duration()
        if dur <= 0:
            raise RuntimeError("Buffer vacío.")
        start = max(0.0, min(start_s, dur))
        end = max(start, min(end_s, dur))
        if end <= start:
            raise RuntimeError("Rango vacío.")
        return trim_and_remux(self.ts_path, out_mp4, start, end - start, keep_source=True)

    # --- marcas exactas para grabación click-to-click ---

    def elapsed(self):
        """Segundos desde que arrancó este buffer (pared). 0 si inactivo."""
        if not self.start_wall:
            return 0.0
        return max(0.0, time.time() - self.start_wall)

    def mark(self):
        """Marca la posición actual del buffer. Devuelve segundos absolutos
        desde el inicio del buffer (pared). Usar con cut_between."""
        return self.elapsed()

    def ready(self, min_secs=0.5):
        """True cuando el buffer tiene datos reales para cortar."""
        if not self.is_active() or not self.ts_path:
            return False
        if not os.path.isfile(self.ts_path) or os.path.getsize(self.ts_path) < 32_000:
            return False
        return self.duration() >= min_secs

    def wait_ready(self, timeout=12.0, min_secs=0.5):
        """Espera a que el buffer tenga datos. Devuelve (ok, delay_s)."""
        t0 = time.time()
        deadline = t0 + timeout
        while time.time() < deadline:
            if self.ready(min_secs=min_secs):
                return True, time.time() - t0
            if not self._active:
                return False, time.time() - t0
            time.sleep(0.2)
        return self.ready(min_secs=min_secs), time.time() - t0

    def cut_between(self, start_mark, end_mark, out_mp4, offset_s=0.0):
        """Corta [start_mark, end_mark) (marcas de elapsed/mark) del buffer
        y guarda .mp4. offset_s compensa retraso conocido (positivo = el
        contenido real va adelantado respecto a la marca; se suma al inicio
        y al fin para que el archivo coincida con lo que el usuario vio)."""
        if not self.ts_path or not os.path.isfile(self.ts_path):
            raise RuntimeError("No hay buffer activo.")
        dur = self.duration()
        if dur <= 0:
            raise RuntimeError("Buffer vacío (todavía no hay datos).")
        off = float(offset_s or 0.0)
        start = max(0.0, float(start_mark) + off)
        end = min(dur, float(end_mark) + off)
        if end <= start:
            # Si el offset empujó el fin fuera, intentar sin pasarse del dur
            end = min(dur, max(start + 0.1, float(end_mark)))
        if end <= start:
            raise RuntimeError("Rango vacío en el buffer.")
        keep = end - start
        return trim_and_remux(self.ts_path, out_mp4, start, keep, keep_source=True)
