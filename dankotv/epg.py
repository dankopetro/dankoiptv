"""EPG para Danko TV: XMLTV (listas M3U) + short_epg (Xtream).

Caché en disco (~/.config/dankotv/epg/) con TTL 6h. Todo bloqueante: llamar
desde hilos worker con el patrón _Bridge (ver home.py). Sin EPG disponible
devuelve listas vacías, nunca excepciones hacia la UI.
"""
import base64
import hashlib
import json
import logging
import os
import time
from urllib.parse import urlparse, parse_qs

from . import config as cfg
from . import engine

log = logging.getLogger("dankotv.epg")

CACHE_TTL = 6 * 3600
SHORT_LIMIT = 8
# Los paneles Xtream etiquetan hora local como si fuera UTC: todo llega 3h
# temprano (verificado en Android 19/09). Se corrige acá una sola vez.
TZ_SHIFT = int(cfg.load_settings().get("epg_shift_hours", 3)) * 3600


def _cache_dir():
    d = os.path.join(os.path.expanduser("~"), ".config", "dankotv", "epg")
    os.makedirs(d, exist_ok=True)
    return d


def decode_b64(s):
    if not s:
        return ""
    try:
        pad = "=" * (-len(s) % 4)
        return base64.b64decode(s + pad).decode("utf-8", errors="replace").strip()
    except Exception:
        return str(s)


def stream_id_from_url(url):
    """ID numérico final de una URL de stream Xtream (`.../12345` o `.ts`)."""
    try:
        path = (url or "").split("?", 1)[0].rstrip("/")
        last = path.rsplit("/", 1)[-1]
        m = "".join(ch for ch in last if ch.isdigit() or ch == ".")
        num = m.split(".")[0]
        return int(num) if num else None
    except Exception:
        return None


def xtream_creds_from_m3u(url):
    """(host, user, pass) desde una URL M3U `get.php?username=U&password=P`."""
    try:
        q = parse_qs(urlparse(url).query)
        user = (q.get("username") or [""])[0]
        pw = (q.get("password") or [""])[0]
        if not user or not pw:
            return None
        p = urlparse(url)
        return (f"{p.scheme or 'http'}://{p.netloc}", user, pw)
    except Exception:
        return None


def _epg_cache_path(key):
    return os.path.join(_cache_dir(), hashlib.sha256(key.encode()).hexdigest() + ".json")


def _cache_get(key):
    try:
        p = _epg_cache_path(key)
        if os.path.isfile(p) and time.time() - os.path.getmtime(p) < CACHE_TTL:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        log.warning("epg caché leer: %s", e)
    return None


def _cache_put(key, obj):
    try:
        with open(_epg_cache_path(key), "w", encoding="utf-8") as f:
            json.dump(obj, f)
    except Exception as e:
        log.warning("epg caché escribir: %s", e)


def fetch_short_epg(host, user, password, stream_id, limit=SHORT_LIMIT):
    """Ahora/siguiente de un stream Xtream. Epoch UTC + shift -> epoch local."""
    import requests

    out = []
    try:
        url = (f"{host.rstrip('/')}/player_api.php?username={user}"
               f"&password={password}&action=get_short_epg"
               f"&stream_id={stream_id}&limit={limit}")
        r = requests.get(url, timeout=(10, 15),
                         headers={"User-Agent": "Mozilla/5.0"})
        data = r.json() if r.ok else {}
        for it in data.get("epg_listings") or []:
            try:
                start = int(it.get("start_timestamp")) + TZ_SHIFT
                stop = int(it.get("stop_timestamp")) + TZ_SHIFT
            except (TypeError, ValueError):
                continue
            out.append({
                "title": decode_b64(it.get("title")),
                "desc": decode_b64(it.get("description")),
                "start": start,
                "stop": stop,
            })
    except Exception as e:
        log.warning("short_epg %s: %s", stream_id, e)
    return sorted(out, key=lambda p: p["start"])


def load_xmltv(epg_url):
    """Parsea el XMLTV con el motor base. Devuelve epg_array o {}."""
    engine.ensure_engine_path()
    key = "xmltv:" + (epg_url or "")
    arr = _cache_get(key + ":parsed")
    if arr is not None:
        return arr
    try:
        from dankoiptv_lib.epg import load_epg
        from dankoiptv_lib.epg_xmltv import parse_as_xmltv
        import io

        raw = load_epg(epg_url, headers={"User-Agent": "Mozilla/5.0"})
        if isinstance(raw, bytes):
            raw = io.BytesIO(raw)
        arr = parse_as_xmltv(raw, {"epgoffset": 0}) or {}
        # sets no serializan: guardar solo lo necesario
        slim = {"epg": arr.get("epg", {}), "names": arr.get("names", {}),
                "ids": {k: sorted(v) for k, v in (arr.get("ids") or {}).items()}}
        _cache_put(key + ":parsed", slim)
        return slim
    except Exception as e:
        log.warning("xmltv %s: %s", epg_url, e)
        return {}


def resolve_id(tvg_id, title, epg_array):
    """ID de guía para un canal (tvg-id directo, si no por nombre)."""
    try:
        engine.ensure_engine_path()
        from dankoiptv_lib.epg import worker_get_epg_id

        return worker_get_epg_id(tvg_id or "", "", title or "", "", epg_array or {}) or ""
    except Exception:
        # fallback local sin el motor
        if not epg_array:
            return ""
        names = epg_array.get("names") or {}
        for cand in (tvg_id or "", title or ""):
            c = cand.lower().strip()
            if c and c in names:
                return names[c]
        return ""


def now_next(programmes, now=None):
    """(actual, siguiente) de una lista ordenada por start."""
    now = now if now is not None else time.time()
    cur = nxt = None
    for p in sorted(programmes or [], key=lambda p: p.get("start", 0)):
        if p.get("start", 0) <= now < p.get("stop", 0):
            cur = p
        elif nxt is None and p.get("start", 0) >= (cur.get("stop", 0) if cur else now):
            nxt = p
    return cur, nxt


def fmt_time(ts):
    try:
        return time.strftime("%H:%M", time.localtime(ts))
    except Exception:
        return ""


def channel_now_next(entry, channel):
    """(actual, siguiente) para un canal de la lista activa. Nunca falla."""
    try:
        typ = (entry or {}).get("type", "m3u")
        url = channel.get("url") or ""
        progs = []
        if typ == "xtream":
            host, user, pw = entry.get("host", ""), entry.get("user", ""), entry.get("pass", "")
            sid = stream_id_from_url(url)
            if host and user and sid:
                progs = _short_progs(host, user, pw, sid)
        else:
            epg_url = (entry or {}).get("epg_url") or ""
            creds = xtream_creds_from_m3u((entry or {}).get("url") or "")
            if creds and not epg_url:
                # M3U Xtream sin XMLTV: short_epg directo
                host, user, pw = creds
                sid = stream_id_from_url(url)
                if sid:
                    progs = _short_progs(host, user, pw, sid)
            elif epg_url:
                arr = load_xmltv(epg_url)
                gid = resolve_id(channel.get("tvg_id"), channel.get("title"), arr)
                if gid:
                    progs = (arr.get("epg") or {}).get(gid) or []
        return now_next(progs)
    except Exception as e:
        log.warning("channel_now_next: %s", e)
        return None, None


def _short_progs(host, user, pw, sid):
    key = f"short:{host}:{sid}"
    progs = _cache_get(key)
    if progs is None:
        progs = fetch_short_epg(host, user, pw, sid)
        _cache_put(key, progs)
    return progs or []


def guide_rows(entry, channels, max_rows=60, max_scan=150, limit_per_channel=8):
    """[(channel, programmes)] solo con datos.

    Escanea por páginas con tope: cada canal sin caché cuesta 1 HTTP (~0.3s),
    así que se corta en max_scan consultas o max_rows filas. Con caché en
    disco las visitas siguientes son gratis. Llamar desde hilo worker.
    """
    rows = []
    scanned = 0
    arr = None
    typ = (entry or {}).get("type", "m3u")
    epg_url = (entry or {}).get("epg_url") or ""
    creds = None
    if typ == "xtream":
        host, user, pw = entry.get("host", ""), entry.get("user", ""), entry.get("pass", "")
    else:
        creds = xtream_creds_from_m3u((entry or {}).get("url") or "")
        if epg_url:
            arr = load_xmltv(epg_url)
            host = user = pw = "", "", ""
        elif creds:
            host, user, pw = creds
        else:
            return rows
    for ch in channels or []:
        if len(rows) >= max_rows or scanned >= max_scan:
            break
        progs = []
        if arr is not None:
            gid = resolve_id(ch.get("tvg_id"), ch.get("title"), arr)
            if gid:
                progs = ((arr.get("epg") or {}).get(gid) or [])[:limit_per_channel]
        else:
            sid = stream_id_from_url(ch.get("url") or "")
            if host and user and sid:
                scanned += 1
                progs = _short_progs(host, user, pw, sid)[:limit_per_channel]
        if progs:
            rows.append((ch, progs))
    return rows
