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
    "favorites": {},
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


def upsert_list(entry, old_name=None):
    items = load_lists()
    drop = old_name or entry.get("name")
    items = [e for e in items if e.get("name") != drop]
    entry["updated"] = time.strftime("%Y-%m-%d %H:%M")
    items.insert(0, entry)
    save_lists(items)
    if old_name and old_name != entry.get("name"):
        rename_favorites(old_name, entry.get("name"))


def delete_list(name):
    save_lists([e for e in load_lists() if e.get("name") != name])
    favs = dict(load_settings().get("favorites") or {})
    if name in favs:
        del favs[name]
        save_settings({"favorites": favs})


def favorites_for(list_name):
    favs = load_settings().get("favorites") or {}
    return list(favs.get(list_name) or [])


def set_favorites(list_name, urls):
    favs = dict(load_settings().get("favorites") or {})
    favs[list_name] = list(urls)
    save_settings({"favorites": favs})


def rename_favorites(old_name, new_name):
    if not old_name or not new_name or old_name == new_name:
        return
    favs = dict(load_settings().get("favorites") or {})
    if old_name in favs:
        favs[new_name] = favs.pop(old_name)
        save_settings({"favorites": favs})


def toggle_favorite(list_name, url):
    if not list_name or not url:
        return False
    cur = favorites_for(list_name)
    if url in cur:
        cur = [u for u in cur if u != url]
        on = False
    else:
        cur.append(url)
        on = True
    set_favorites(list_name, cur)
    return on
