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


def _wait_open(proc, ts_path, seconds=2.0):
    """Espera a que ffmpeg abra el stream. Devuelve True si sigue vivo o
    dejó archivo (modo archivo puede terminar descargando todo)."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        if proc.poll() is not None:
            return os.path.isfile(ts_path) and os.path.getsize(ts_path) > 0
        time.sleep(0.2)
    return True


def start(url, title, live=True):
    """Inicia ffmpeg. live=True: ritmo 1:1 desde el borde (HLS no corre).
    live=False (repetición/archivo): copia rápida del archivo completo.
    Devuelve (proc, ts_path, mp4_path) o lanza RuntimeError."""
    if not ffmpeg_ok():
        raise RuntimeError("Falta ffmpeg (sudo apt install ffmpeg)")
    if not url:
        raise RuntimeError("Sin URL para grabar.")
    ts_path, mp4_path = _paths(title)
    cmd = build_cmd(url, ts_path, live)
    log.info("REC start: %s", ts_path)
    _append_rec_log(f"REC start live={live} url={url}\n")
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
