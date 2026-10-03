"""Snapshot de listas Danko TV: última descarga exitosa en SQLite.

Si una recarga falla (sin red, proveedor caído), la app muestra la copia
guardada en vez de dejar la lista vacía. Sin dependencias (sqlite3 stdlib).
"""
import logging
import os
import sqlite3
import time

log = logging.getLogger("dankotv.store")

DB_PATH = os.path.join(os.path.expanduser("~"), ".config", "dankotv", "channels.db")
BATCH = 2000


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    cx = sqlite3.connect(DB_PATH, timeout=30)
    cx.execute("PRAGMA journal_mode=WAL")
    cx.execute("""CREATE TABLE IF NOT EXISTS channels
        (list_name TEXT, title TEXT, grp TEXT, url TEXT, logo TEXT, tvg_id TEXT)""")
    cx.execute("CREATE INDEX IF NOT EXISTS idx_ch_list ON channels(list_name)")
    cx.execute("""CREATE TABLE IF NOT EXISTS meta
        (list_name TEXT PRIMARY KEY, saved_at REAL)""")
    return cx


def save_snapshot(name, channels):
    """Reemplazo atómico de la copia. Corre en hilo worker, no en UI."""
    if not name:
        return
    try:
        cx = _connect()
        with cx:
            cx.execute("DELETE FROM channels WHERE list_name=?", (name,))
            cx.executemany(
                "INSERT INTO channels(list_name,title,grp,url,logo,tvg_id)"
                " VALUES (?,?,?,?,?,?)",
                [(
                    name,
                    (c.get("title") or "")[:500],
                    (c.get("group") or "")[:200],
                    c.get("url") or "",
                    (c.get("logo") or "")[:500],
                    (c.get("tvg_id") or "")[:200],
                ) for c in (channels or [])],
            )
            cx.execute("INSERT OR REPLACE INTO meta(list_name,saved_at) VALUES (?,?)",
                       (name, time.time()))
        cx.close()
        log.info("snapshot %s: %d canales", name, len(channels or []))
    except Exception as e:
        log.warning("snapshot guardar %s: %s", name, e)


def load_snapshot(name):
    """(channels, groups, saved_at) o ([], [], 0) si no hay copia."""
    try:
        cx = _connect()
        row = cx.execute("SELECT saved_at FROM meta WHERE list_name=?", (name,)).fetchone()
        if not row:
            cx.close()
            return [], [], 0
        rows = cx.execute(
            "SELECT title,grp,url,logo,tvg_id FROM channels WHERE list_name=?", (name,)).fetchall()
        cx.close()
        channels = [{"title": t, "group": g, "url": u, "logo": lo, "tvg_id": tv}
                    for t, g, u, lo, tv in rows]
        groups = sorted({c["group"] for c in channels if c["group"]})
        return channels, groups, row[0]
    except Exception as e:
        log.warning("snapshot leer %s: %s", name, e)
        return [], [], 0


def drop_snapshot(name):
    try:
        cx = _connect()
        with cx:
            cx.execute("DELETE FROM channels WHERE list_name=?", (name,))
            cx.execute("DELETE FROM meta WHERE list_name=?", (name,))
        cx.close()
    except Exception:
        pass


def rename_snapshot(old, new):
    if not old or not new or old == new:
        return
    try:
        cx = _connect()
        with cx:
            cx.execute("UPDATE channels SET list_name=? WHERE list_name=?", (new, old))
            cx.execute("UPDATE meta SET list_name=? WHERE list_name=?", (new, old))
        cx.close()
    except Exception:
        pass
