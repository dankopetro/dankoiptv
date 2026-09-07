# -*- coding: utf-8 -*-
"""Persistencia: config.json + cache híbrida para listas M3U."""
import json
import os
import time
import logging

log = logging.getLogger("dankoiptv.config")

CONFIG_DIR = os.path.expanduser("~/.config/dankoiptv")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
CACHE_PATH = os.path.join(CONFIG_DIR, "cache.json")
# Compat: settings.json legacy
LEGACY_PATH = os.path.join(CONFIG_DIR, "settings.json")

DEFAULTS = {
    "last_playlist_url": "",
    "last_group": "Todas",
    "cache_secs": 45,
    "window_geometry": "",
}

def _ensure_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)

def load_config():
    _ensure_dir()
    data = dict(DEFAULTS)
    # legacy fallback
    src = CONFIG_PATH if os.path.exists(CONFIG_PATH) else (LEGACY_PATH if os.path.exists(LEGACY_PATH) else None)
    if src:
        try:
            with open(src, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                data.update({k: v for k, v in loaded.items() if k in DEFAULTS or k == "last_playlist_url"})
        except Exception as e:
            log.warning(f"load_config failed: {e}")
    return data

def save_config(updates):
    _ensure_dir()
    cfg = load_config()
    cfg.update(updates)
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.chmod(CONFIG_PATH, 0o600)
    except Exception as e:
        log.error(f"save_config failed: {e}")

# --- Cache híbrida ---
def save_cache(channels):
    """channels: list[Channel] -> cache.json"""
    _ensure_dir()
    try:
        payload = {
            "timestamp": time.time(),
            "channels": [{"name": c.name, "url": c.url, "group": c.group, "logo": c.logo, "tvg_id": c.tvg_id} for c in channels],
        }
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        os.chmod(CACHE_PATH, 0o600)
    except Exception as e:
        log.error(f"save_cache failed: {e}")

def load_cache(max_age_hours=24):
    """Retorna (channels, is_fresh) o (None, False) si no hay cache."""
    if not os.path.exists(CACHE_PATH):
        return None, False
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
        ts = payload.get("timestamp", 0)
        is_fresh = (time.time() - ts) < (max_age_hours * 3600)
        from .iptv import Channel
        channels = [Channel(d["name"], d["url"], d.get("group", "General"), d.get("logo", ""), d.get("tvg_id", "")) for d in payload.get("channels", [])]
        return channels, is_fresh
    except Exception as e:
        log.warning(f"load_cache failed: {e}")
        return None, False
