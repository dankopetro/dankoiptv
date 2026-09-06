"""Entry Danko TV: Home (Mis listas) -> Vista principal."""
import locale
import os
import sys

os.environ["LC_NUMERIC"] = "C"
try:
    locale.setlocale(locale.LC_NUMERIC, "C")
except Exception:
    pass

# motor base en sys.path (instalado o repo)
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ENGINE = os.path.join(os.path.dirname(_HERE), "usr", "lib", "dankoiptv")
for _p in ("/usr/lib/dankoiptv", _REPO_ENGINE):
    if os.path.exists(os.path.join(_p, "dankoiptv.py")) and _p not in sys.path:
        sys.path.insert(0, _p)
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import logging
from PyQt6.QtWidgets import QApplication

from dankotv import __version__
from dankotv import config as cfg
from dankotv import skins
from dankotv.home import HomeWindow
from dankotv.mainview import MainWindow


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    app = QApplication(sys.argv)
    app.setApplicationName("Danko TV")
    try:
        locale.setlocale(locale.LC_NUMERIC, "C")
    except Exception:
        pass
    settings = cfg.load_settings()
    skins.apply_look(app, settings.get("skin"), settings.get("font_family"))

    state = {"main": None}
    home = HomeWindow(version=__version__)

    def open_entry(entry):
        ch_gr = home._session_cache.get(entry["name"])
        if not ch_gr:
            return
        ch, gr = ch_gr
        main = MainWindow(entry, ch, gr, version=__version__)

        def back():
            main.close()
            home.refresh()
            home.show()

        main.back_home.connect(back)
        state["main"] = main
        home.hide()
        main.show()

    home.open_list.connect(open_entry)
    home.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
