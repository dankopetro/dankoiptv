# -*- coding: utf-8 -*-
"""
Main entry point for Dankoiptv.
"""
import sys
import logging
from PyQt6.QtWidgets import QApplication
from .ui import DankoWindow

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    app = QApplication(sys.argv)
    app.setApplicationName("Dankoiptv")
    
    window = DankoWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
