"""Config de Danko TV: ~/.config/dankotv/ (listas + ajustes shell)."""
import json
import os
import time

CONFIG_DIR = os.path.expanduser("~/.config/dankotv")
LISTS_PATH = os.path.join(CONFIG_DIR, "lists.json")
SETTINGS_PATH = os.path.join(CONFIG_DIR, "settings.json")

DEFAULT_SETTINGS = {
    "skin": "Naranja Oscuro",
    "font_family": "Ubuntu",
    "last_list": "",
    "last_group": "Todas",
    "cache_secs": 45,
}


def _ensure():
    os.makedirs(CONFIG_DIR, exist_ok=True)


def load_settings():
    _ensure()
    data = dict(DEFAULT_SETTINGS)
    try:
        if os.path.exists(SETTINGS_PATH):
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                data.update(json.load(f))
    except Exception:
        pass
    return data


def save_settings(updates):
    _ensure()
    data = load_settings()
    data.update(updates)
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.chmod(SETTINGS_PATH, 0o600)
    except Exception:
        pass


def load_lists():
    """[{name, type: m3u|xtream, url|host,user,pass, channels, groups, updated}]"""
    _ensure()
    try:
        if os.path.exists(LISTS_PATH):
            with open(LISTS_PATH, encoding="utf-8") as f:
                items = json.load(f)
                return items if isinstance(items, list) else []
    except Exception:
        pass
    return []


def save_lists(items):
    _ensure()
    try:
        with open(LISTS_PATH, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False)
        os.chmod(LISTS_PATH, 0o600)
    except Exception:
        pass


def upsert_list(entry):
    items = [e for e in load_lists() if e.get("name") != entry.get("name")]
    entry["updated"] = time.strftime("%Y-%m-%d %H:%M")
    items.insert(0, entry)
    save_lists(items)


def delete_list(name):
    save_lists([e for e in load_lists() if e.get("name") != name])
