# -*- coding: utf-8 -*-
"""
PyQt6 Modern User Interface for Dankoiptv.
"""
import sys
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QLineEdit, QPushButton, QLabel, QSplitter, QFrame,
    QMessageBox, QInputDialog, QTabWidget
)
from PyQt6.QtGui import QIcon, QFont

from .player import IPTVPlayer
from .iptv import PlaylistParser, Channel

class DankoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dankoiptv - Advanced IPTV Player")
        self.resize(1280, 720)
        
        self.channels = []
        self.filtered_channels = []
        
        self.init_ui()
        
        # Initialize player after UI is shown so winId is valid
        self.player = None

    def init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left sidebar (channels & groups)
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        
        title_label = QLabel("Dankoiptv")
        title_label.setFont(QFont("Sans Serif", 16, QFont.Weight.Bold))
        sidebar_layout.addWidget(title_label)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search channels...")
        self.search_input.textChanged.connect(self.filter_channels)
        sidebar_layout.addWidget(self.search_input)
        
        self.load_playlist_btn = QPushButton("Load M3U Playlist")
        self.load_playlist_btn.clicked.connect(self.prompt_load_playlist)
        sidebar_layout.addWidget(self.load_playlist_btn)
        
        self.channel_list = QListWidget()
        self.channel_list.itemClicked.connect(self.on_channel_selected)
        sidebar_layout.addWidget(self.channel_list)
        
        splitter.addWidget(sidebar)
        
        # Right area (Video container & controls)
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        self.video_frame = QFrame()
        self.video_frame.setStyleSheet("background-color: black;")
        right_layout.addWidget(self.video_frame, stretch=1)
        
        # Control bar
        control_bar = QWidget()
        control_layout = QHBoxLayout(control_bar)
        
        self.play_btn = QPushButton("Play / Reload")
        self.play_btn.clicked.connect(self.resume_playback)
        control_layout.addWidget(self.play_btn)
        
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_playback)
        control_layout.addWidget(self.stop_btn)
        
        control_layout.addStretch()
        right_layout.addWidget(control_bar)
        
        splitter.addWidget(right_container)
        splitter.setSizes([350, 930])

    def showEvent(self, event):
        super().showEvent(event)
        if not self.player:
            wid = int(self.video_frame.winId())
            self.player = IPTVPlayer(wid=wid)

    def prompt_load_playlist(self):
        url, ok = QInputDialog.getText(self, "Load Playlist", "Enter M3U URL or path:")
        if ok and url:
            if url.startswith("http"):
                channels = PlaylistParser.fetch_playlist_with_timeout(url)
            else:
                try:
                    with open(url, "r", encoding="utf-8") as f:
                        channels = PlaylistParser.parse_m3u_text(f.read())
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to read file: {e}")
                    return
            
            self.channels = channels
            self.filtered_channels = channels
            self.update_channel_list()
            QMessageBox.information(self, "Success", f"Loaded {len(channels)} channels.")

    def update_channel_list(self):
        self.channel_list.clear()
        for ch in self.filtered_channels:
            self.channel_list.addItem(ch.name)

    def filter_channels(self, text):
        text = text.lower()
        self.filtered_channels = [c for c in self.channels if text in c.name.lower()]
        self.update_channel_list()

    def on_channel_selected(self, item):
        row = self.channel_list.row(item)
        if 0 <= row < len(self.filtered_channels):
            ch = self.filtered_channels[row]
            if self.player:
                self.player.play(ch.url, is_live=True)

    def resume_playback(self):
        if self.player and self.player.current_url:
            self.player.play(self.player.current_url, is_live=True)

    def stop_playback(self):
        if self.player:
            self.player.stop()

    def closeEvent(self, event):
        if self.player:
            self.player.stop()
            self.player.mpv.terminate()
        event.accept()
