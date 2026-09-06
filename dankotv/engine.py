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


ensure_engine_path()


def fetch_text(url, timeout=120):
    import requests

    resp = requests.get(url, timeout=(10, timeout))
    resp.raise_for_status()
    return resp.content.decode("utf-8-sig", errors="replace")


def norm_m3u(ch):
    return {
        "title": ch.get("title") or ch.get("orig_title") or "Sin nombre",
        "group": ch.get("tvg-group") or "General",
        "url": ch.get("url") or "",
        "logo": ch.get("tvg-logo") or "",
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
    channels = [norm_m3u(c) for c in raw if isinstance(c, dict) and c.get("url")]
    groups = sorted({c["group"] for c in channels if c["group"]})
    return channels, groups


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
            }
        )
    groups = sorted({c["group"] for c in channels if c["group"]})
    return channels, groups
