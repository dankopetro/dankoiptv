# -*- coding: utf-8 -*-
"""
IPTV playlist parser and Xtream API client with timeout protection for huge lists.
"""
import logging
import requests
import re
import sys
import time

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
        current_group = "General"
        current_name = ""
        current_logo = ""
        current_tvg_id = ""

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("#EXTINF:"):
                # Parse metadata
                group_match = re.search(r'group-title="([^"]*)"', line)
                if group_match:
                    current_group = group_match.group(1)
                logo_match = re.search(r'tvg-logo="([^"]*)"', line)
                if logo_match:
                    current_logo = logo_match.group(1)
                id_match = re.search(r'tvg-id="([^"]*)"', line)
                if id_match:
                    current_tvg_id = id_match.group(1)
                
                parts = line.split(",")
                if parts:
                    current_name = parts[-1].strip()
            elif not line.startswith("#"):
                if current_name:
                    channels.append(Channel(current_name, line, current_group, current_logo, current_tvg_id))
                current_name = ""
                current_logo = ""
                current_tvg_id = ""
        return channels

    @staticmethod
    def fetch_playlist_with_timeout(url, timeout=120):
        """Downloads large M3U playlists with extended timeout protection."""
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return PlaylistParser.parse_m3u_text(resp.text)
        except Exception as e:
            log.error(f"Failed to fetch playlist from {url}: {e}")
            return []

class XtreamClient:
    def __init__(self, host, username, password):
        self.host = host.rstrip('/')
        self.username = username
        self.password = password
        self.base_url = f"{self.host}/player_api.php?username={self.username}&password={self.password}"

    def authenticate(self):
        try:
            resp = requests.get(self.base_url, timeout=15)
            data = resp.json()
            return data.get("user_info", {}).get("auth") == 1
        except Exception as e:
            log.error(f"Xtream auth failed: {e}")
            return False

    def get_live_streams(self):
        try:
            url = f"{self.base_url}&action=get_live_streams"
            resp = requests.get(url, timeout=30)
            streams = resp.json()
            channels = []
            for s in streams:
                stream_id = s.get("stream_id")
                name = s.get("name", "Unknown")
                logo = s.get("stream_icon", "")
                category_id = s.get("category_id", "General")
                stream_url = f"{self.host}/live/{self.username}/{self.password}/{stream_id}.ts"
                channels.append(Channel(name, stream_url, str(category_id), logo))
            return channels
        except Exception as e:
            log.error(f"Failed to get Xtream live streams: {e}")
            return []
