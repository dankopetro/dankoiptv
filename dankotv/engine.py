"""Carga de listas reutilizando el motor base (M3UParser + XTream)."""
import logging
import os
import sys

log = logging.getLogger("dankotv.engine")

ENGINE_PATHS = [
    "/usr/lib/dankoiptv",  # instalado por .deb dankoiptv
]


def _repo_engine():
    here = os.path.dirname(os.path.abspath(__file__))
    cand = os.path.join(os.path.dirname(here), "usr", "lib", "dankoiptv")
    if os.path.exists(os.path.join(cand, "dankoiptv.py")):
        return cand
    return None


def ensure_engine_path():
    for p in ENGINE_PATHS:
        if os.path.exists(os.path.join(p, "dankoiptv.py")) and p not in sys.path:
            sys.path.insert(0, p)
    repo = _repo_engine()
    if repo and repo not in sys.path:
        sys.path.insert(0, repo)
    # AppDir/AppImage/.deb: el motor puede ir junto al shell en sys.path
    for p in list(sys.path):
        if not p or not os.path.isdir(p):
            continue
        cand = os.path.join(p, "dankoiptv", "dankoiptv.py")
        engine_dir = os.path.join(p, "dankoiptv")
        if os.path.exists(cand) and engine_dir not in sys.path:
            sys.path.insert(0, engine_dir)


ensure_engine_path()


def fetch_text(url, timeout=120):
    import requests

    resp = requests.get(url, timeout=(10, timeout))
    resp.raise_for_status()
    return resp.content.decode("utf-8-sig", errors="replace")


def classify_error(err):
    """Texto amable para fallos de descarga (no borrar nada: ver store.py)."""
    s = str(err or "")
    if "401" in s:
        return "Credenciales rechazadas (401: cuenta incorrecta o dada de baja)."
    if "403" in s or "429" in s:
        return ("Servidor rechazó los pedidos (bloqueo temporal por demasiados "
                "intentos). Esperá un rato antes de recargar.")
    if "404" in s:
        return ("Lista no encontrada (404: URL/cuenta caída o bloqueo temporal "
                "del servidor). Probá más tarde.")
    low = s.lower()
    if "timeout" in low or "timed out" in low or "connection" in low:
        return ("Sin respuesta del servidor (puede estar caído o bloqueando "
                "temporalmente). Probá más tarde.")
    return s


def probe_m3u(url):
    """Validación liviana: solo los primeros bytes (no descarga la lista)."""
    import requests

    r = requests.get(url, headers={"Range": "bytes=0-4095",
                                   "User-Agent": "Mozilla/5.0"},
                     timeout=(10, 20))
    if r.status_code in (200, 206) and r.content:
        if b"#EXTM3U" in r.content[:8192].upper():
            return True, "OK: la URL responde (la descarga completa se hace al guardar)."
        return True, "OK: el servidor responde (verificá que sea una lista M3U)."
    raise RuntimeError(f"HTTP {r.status_code}")


def probe_xtream(host, username, password):
    """Validación liviana: solo auth (no descarga categorías ni streams)."""
    import requests

    r = requests.get(f"{host.rstrip('/')}/player_api.php?username={username}&password={password}",
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=(10, 20))
    try:
        data = r.json()
    except Exception:
        raise RuntimeError(f"HTTP {r.status_code}")
    if isinstance(data, dict) and (data.get("user_info") or {}).get("auth") == 1:
        return True, "OK: usuario válido (las listas se descargan al guardar)."
    raise RuntimeError("HTTP 401 (credenciales rechazadas)")


def norm_m3u(ch):
    return {
        "title": ch.get("title") or ch.get("orig_title") or "Sin nombre",
        "group": ch.get("tvg-group") or "General",
        "url": ch.get("url") or "",
        "logo": ch.get("tvg-logo") or "",
        "tvg_id": ch.get("tvg-ID") or ch.get("tvg-id") or "",
    }


def load_m3u(url, progress=None):
    from dankoiptv_lib.playlist_m3u import M3UParser

    if progress:
        progress("Descargando lista...")
    text = fetch_text(url)
    if progress:
        progress("Parseando canales...")
    parser = M3UParser(udp_proxy="")
    parsed = parser.parse_m3u(text)
    raw = parsed[0] if isinstance(parsed, (list, tuple)) else parsed
    epg_url = ""
    if isinstance(parsed, (list, tuple)) and len(parsed) > 1 and parsed[1]:
        epg_url = str(parsed[1]).split(",")[0].strip()
    channels = [norm_m3u(c) for c in raw if isinstance(c, dict) and c.get("url")]
    groups = sorted({c["group"] for c in channels if c["group"]})
    return channels, groups, epg_url


def load_xtream(host, username, password, progress=None):
    from thirdparty.xtream import XTream

    host = host.rstrip("/")

    def status(msg, _gui_only=False):
        if progress:
            progress(str(msg))
        log.info("xtream: %s", msg)

    xt = XTream(status, "dankotv", username, password, host)
    if progress:
        progress("Autenticando...")
    ok = xt.load_iptv()
    if not ok or not getattr(xt, "state", {}).get("authenticated", True):
        raise RuntimeError("Xtream: autenticación fallida (revisa host/usuario/clave)")
    channels = []
    for ch in getattr(xt, "channels", []):
        url = getattr(ch, "url", "") or ""
        if not url:
            continue
        channels.append(
            {
                "title": getattr(ch, "title", "") or getattr(ch, "name", "") or "Sin nombre",
                "group": getattr(ch, "group_title", "") or "General",
                "url": url,
                "logo": getattr(ch, "logo", "") or "",
                "tvg_id": "",
            }
        )
    groups = sorted({c["group"] for c in channels if c["group"]})
    return channels, groups
