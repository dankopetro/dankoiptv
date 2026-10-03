"""Grabación Danko TV: ffmpeg -c copy a .ts + remux auto a .mp4.

El .mp4 directo es frágil (índice al final: si se corta, archivo muerto);
por eso se graba .ts resistente y al detener se convierte a .mp4 en segundos
sin recodificar. Subprocess puro, sin Qt.
"""
import logging
import os
import re
import shutil
import subprocess
import time

log = logging.getLogger("dankotv.record")

REC_DIR = os.path.join(os.path.expanduser("~"), "Videos", "DankoTV")


def ffmpeg_ok():
    return shutil.which("ffmpeg") is not None


def safe_name(title):
    s = re.sub(r"[^\w\d\- ]+", "", title or "canal", flags=re.UNICODE).strip()
    s = re.sub(r"\s+", "_", s)
    return (s or "canal")[:60]


def _paths(title):
    os.makedirs(REC_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    base = os.path.join(REC_DIR, f"{stamp}_{safe_name(title)}")
    return base + ".ts", base + ".mp4"


def start(url, title, live=True):
    """Inicia ffmpeg. live=True: ritmo 1:1 desde el borde (HLS no corre).
    live=False (repetición/archivo): copia rápida del archivo completo.
    Devuelve (proc, ts_path, mp4_path) o lanza RuntimeError."""
    if not ffmpeg_ok():
        raise RuntimeError("Falta ffmpeg (sudo apt install ffmpeg)")
    if not url:
        raise RuntimeError("Sin URL para grabar.")
    ts_path, mp4_path = _paths(title)
    cmd = ["ffmpeg", "-nostats", "-hide_banner", "-loglevel", "warning",
           "-user_agent", "Mozilla/5.0"]
    if live:
        # Sin esto ffmpeg devora la ventana HLS publicada más rápido que el
        # vivo (10s pared -> 47s contenido, verificado 03/10/2026).
        cmd += ["-re", "-live_start_index", "-1"]
    cmd += ["-reconnect", "1", "-reconnect_streamed", "1",
            "-reconnect_on_network_error", "1",
            "-i", url, "-map", "0", "-codec", "copy",
            "-max_muxing_queue_size", "4096", "-y", ts_path]
    log.info("REC start: %s", ts_path)
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)
    if proc.poll() is not None:
        # Terminó en <1s: en modo archivo puede ser descarga completa válida;
        # solo es fallo si no dejó nada.
        if not (os.path.isfile(ts_path) and os.path.getsize(ts_path) > 0):
            raise RuntimeError("ffmpeg no pudo abrir el stream (¿bloqueo temporal?).")
    return proc, ts_path, mp4_path


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
                return mp4_path
        log.warning("REC remux falló, queda el .ts")
        return ts_path if os.path.isfile(ts_path) else None
    except Exception as e:
        log.warning("REC remux: %s", e)
        return ts_path if os.path.isfile(ts_path) else None
