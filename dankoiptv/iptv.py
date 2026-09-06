# -*- coding: utf-8 -*-
"""M3U parser robusto + Xtream con categorías."""
import logging
import re
import requests

log = logging.getLogger("dankoiptv.iptv")

class Channel:
    def __init__(self, name, url, group="General", logo="", tvg_id=""):
        self.name = name
        self.url = url
        self.group = group
        self.logo = logo
        self.tvg_id = tvg_id

class PlaylistParser:
    @staticmethod
    def parse_m3u_text(text):
        channels = []
        cur_group = "General"
        cur_name = ""
        cur_logo = ""
        cur_tvg = ""
        # Soporta BOM utf-8
        if text.startswith("\ufeff"):
            text = text.lstrip("\ufeff")
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#EXTINF:"):
                # group-title con "" o '' o sin comillas, tolerante a espacios
                m = re.search(r'group-title\s*=\s*"([^"]*)"', line)
                if not m: m = re.search(r"group-title\s*=\s*'([^']*)'", line)
                if not m: m = re.search(r'group-title\s*=\s*([^\s,]+)', line)
                if m:
                    cur_group = m.group(1).strip() or cur_group
                m2 = re.search(r'tvg-logo\s*=\s*"([^"]*)"', line)
                if not m2: m2 = re.search(r"tvg-logo\s*=\s*'([^']*)'", line)
                cur_logo = m2.group(1).strip() if m2 else ""
                m3 = re.search(r'tvg-id\s*=\s*"([^"]*)"', line)
                if not m3: m3 = re.search(r"tvg-id\s*=\s*'([^']*)'", line)
                cur_tvg = m3.group(1).strip() if m3 else ""
                # nombre tras última coma (estándar) — si no hay coma, usar tvg-name
                if "," in line:
                    cur_name = line.rsplit(",", 1)[-1].strip()
                else:
                    mn = re.search(r'tvg-name\s*=\s*"([^"]*)"', line)
                    cur_name = mn.group(1).strip() if mn else ""
                if not cur_name:
                    cur_name = cur_tvg or "Unknown"
            elif line.startswith("#EXTGRP:"):
                cur_group = line[len("#EXTGRP:"):].strip() or cur_group
            elif not line.startswith("#"):
                if cur_name:
                    channels.append(Channel(cur_name, line, cur_group or "General", cur_logo, cur_tvg))
                cur_name = ""; cur_logo = ""; cur_tvg = ""
        return channels

    @staticmethod
    def fetch_playlist_with_timeout(url, timeout=120):
        try:
            # timeout=(connect, read) + stream para listas enormes 88MB
            resp = requests.get(url, timeout=(10, timeout), stream=False)
            resp.raise_for_status()
            # decodifica con utf-8-sig para BOM
            text = resp.content.decode("utf-8-sig", errors="replace")
            return PlaylistParser.parse_m3u_text(text)
        except Exception as e:
            log.error(f"fetch playlist failed {url[:60]}...: {e}")
            return []

class XtreamClient:
    def __init__(self, host, username, password):
        self.host = host.rstrip("/")
        self.username = username
        self.password = password
        self.base_url = f"{self.host}/player_api.php?username={self.username}&password={self.password}"

    def authenticate(self):
        try:
            resp = requests.get(self.base_url, timeout=15)
            return resp.json().get("user_info", {}).get("auth") == 1
        except Exception as e:
            log.error(f"Xtream auth failed: {e}")
            return False

    def get_live_categories(self):
        try:
            resp = requests.get(f"{self.base_url}&action=get_live_categories", timeout=15)
            return {str(c.get("category_id")): c.get("category_name", "General") for c in resp.json()}
        except Exception as e:
            log.warning(f"get_live_categories: {e}")
            return {}

    def get_live_streams(self):
        try:
            cat_map = self.get_live_categories()
            resp = requests.get(f"{self.base_url}&action=get_live_streams", timeout=30)
            channels = []
            for s in resp.json():
                sid = s.get("stream_id")
                name = s.get("name", "Unknown")
                logo = s.get("stream_icon", "")
                cid = str(s.get("category_id", ""))
                group = cat_map.get(cid, cid or "General")
                url = f"{self.host}/live/{self.username}/{self.password}/{sid}.ts"
                channels.append(Channel(name, url, group, logo, str(sid)))
            return channels
        except Exception as e:
            log.error(f"Xtream get_live_streams: {e}")
            return []
