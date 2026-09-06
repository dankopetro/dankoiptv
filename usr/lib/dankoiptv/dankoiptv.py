#
# Copyright (c) 2021, 2022 Astroncia
# Copyright (c) 2023-2025 liya <liyaliya@tutamail.com>
#
# This file is part of dankoiptv.
#
# dankoiptv is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# dankoiptv is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with dankoiptv. If not, see <https://www.gnu.org/licenses/>.
#
# The Font Awesome pictograms are licensed under the CC BY 4.0 License.
# Font Awesome Free 5.15.4 by @fontawesome - https://fontawesome.com
# https://creativecommons.org/licenses/by/4.0/
#
import os
import re
import sys
import json
import math
import time
import atexit
import locale
import signal
import urllib
import hashlib
import logging
import os.path
import datetime
import textwrap
import threading
import traceback
import subprocess
import urllib.parse
import gc
gc.disable()
import dankoiptv_lib.environ  # noqa: F401
from pathlib import Path
from functools import partial
from gi.repository import Gio, GLib
from PyQt6 import QtGui, QtCore, QtWidgets
from multiprocessing import Manager, get_context, active_children
from dankoiptv_lib.qt_info import get_qt_info
from dankoiptv_lib.qt_exception import show_exception
from dankoiptv_lib.args import loglevel, parsed_args
from dankoiptv_lib.i18n import _, load_qt_translations
from dankoiptv_lib.kill_process_childs import kill_process_childs
from dankoiptv_lib.epg import (
    epg_worker,
    epg_is_in_date,
    worker_get_epg_id,
    worker_get_epg_icon,
    worker_get_all_epg_names,
    worker_get_epg_programmes,
    worker_get_current_programme,
    worker_check_programmes_actual,
)
from dankoiptv_lib.gui import DankoGUIClass, show_window, move_window_to_center
from dankoiptv_lib.xdg import CACHE_DIR, LOCAL_DIR, SAVE_FOLDER_DEFAULT
from dankoiptv_lib.misc import (
    WINDOW_SIZE,
    TVGUIDE_WIDTH,
    DOCKWIDGET_PLAYLIST_WIDTH,
    DOCKWIDGET_CONTROLPANEL_HEIGHT_LOW,
    DOCKWIDGET_CONTROLPANEL_HEIGHT_HIGH,
    DankoData,
    decode,
    convert_size,
    format_bytes,
    format_seconds,
    get_current_time,
    is_youtube_url,
)
from dankoiptv_lib.mpris import start_mpris, mpris_seeked, emit_mpris_change
from dankoiptv_lib.record import (
    record,
    init_record,
    stop_record,
    is_ffmpeg_recording,
    terminate_record_process,
)
from dankoiptv_lib.catchup import (
    get_catchup_url,
    format_catchup_array,
    parse_specifiers_in_url,
)
from dankoiptv_lib.inhibit import inhibit, register, uninhibit
from dankoiptv_lib.menubar import (
    get_seq,
    get_first_run,
    update_menubar,
    populate_menubar,
    init_menubar_player,
    get_active_vf_filters,
    init_dankoiptv_lib_menubar,
    reload_menubar_shortcuts,
)
from dankoiptv_lib.threads import execute_in_main_thread
from dankoiptv_lib.options import read_option, write_option
from dankoiptv_lib.keybinds import (
    main_keybinds_default,
    main_keybinds_internal,
    main_keybinds_translations,
)
from dankoiptv_lib.playlist import load_playlist
from dankoiptv_lib.mpv_options import get_mpv_options
from dankoiptv_lib.channel_logos import channel_logos_worker
from dankoiptv_lib.settings import parse_settings, get_epg_url
from dankoiptv_lib.gui_playlists import Data as gui_playlists_data
from dankoiptv_lib.gui_playlists import (
    show_playlists,
    playlist_selected,
    create_playlists_window,
)
from dankoiptv_lib.playlist_editor import PlaylistEditor
from dankoiptv_lib.stream_info import stream_info, open_stream_info, monitor_playback
from thirdparty import mpv

if sys.version_info < (3, 9, 0):
    show_exception("Python 3.9 or newer required")
    sys.exit(1)

logger = logging.getLogger("dankoiptv")
mpv_logger = logging.getLogger("mpv")

APP_VERSION = "__DEB_VERSION__"

if parsed_args.version:
    print(f"Dankoiptv {APP_VERSION}")
    sys.exit(0)

Path(LOCAL_DIR).mkdir(parents=True, exist_ok=True)
Path(SAVE_FOLDER_DEFAULT).mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":

    def exit_handler(*args):
        try:
            try:
                if DankoData.epg_pool:
                    try:
                        DankoData.epg_pool.close()
                        DankoData.epg_pool = None
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                if multiprocessing_manager:
                    multiprocessing_manager.shutdown()
            except Exception:
                pass
            for process_3 in active_children():
                try:
                    process_3.kill()
                except Exception:
                    try:
                        process_3.terminate()
                    except Exception:
                        pass
            try:
                uninhibit()
            except Exception:
                pass
            try:
                for process_3 in active_children():
                    try:
                        process_3.kill()
                    except Exception:
                        try:
                            process_3.terminate()
                        except Exception:
                            pass
            except Exception:
                pass
            try:
                stop_record()
            except Exception:
                pass
            try:
                for rec_1 in sch_recordings:
                    do_stop_record(rec_1)
            except Exception:
                pass
            try:
                if DankoData.mpris_loop:
                    DankoData.mpris_running = False
                    DankoData.mpris_loop.quit()
            except Exception:
                pass
            try:
                if multiprocessing_manager:
                    multiprocessing_manager.shutdown()
            except Exception:
                pass
            try:
                for process_3 in active_children():
                    try:
                        process_3.kill()
                    except Exception:
                        try:
                            process_3.terminate()
                        except Exception:
                            pass
            except Exception:
                pass
            if not DankoData.exiting:
                DankoData.exiting = True
                logger.info("Exiting")
            if not DankoData.do_save_settings:
                kill_process_childs(os.getpid())
        except BaseException:
            pass

    atexit.register(exit_handler)
    signal.signal(signal.SIGTERM, exit_handler)
    signal.signal(signal.SIGINT, exit_handler)

    if not QtWidgets.QApplication.instance():
        app = QtWidgets.QApplication(sys.argv)
    else:
        app = QtWidgets.QApplication.instance()

    app.setDesktopFileName("dankoiptv")
    load_qt_translations(app)

    # This is necessary since PyQT stomps over the locale settings needed by libmpv.
    # This needs to happen after importing PyQT before
    # creating the first mpv.MPV instance.
    locale.setlocale(locale.LC_NUMERIC, "C")

    try:
        logger.info(f"Version: {APP_VERSION}")
        logger.info(f"Python {sys.version.strip()}")
        logger.info(f"Qt {get_qt_info(app)}")

        multiprocessing_manager = Manager()
        DankoData.mp_manager_dict = multiprocessing_manager.dict()

        if not os.path.isfile(str(Path(LOCAL_DIR, "favplaylist.m3u"))):
            file01 = open(str(Path(LOCAL_DIR, "favplaylist.m3u")), "w", encoding="utf8")
            file01.write("#EXTM3U\n#EXTINF:-1,-\nhttp://255.255.255.255\n")
            file01.close()

        DankoData.channel_sets = {}

        def save_channel_sets():
            file2 = open(
                str(Path(LOCAL_DIR, "channelsettings.json")), "w", encoding="utf8"
            )
            file2.write(json.dumps(DankoData.channel_sets))
            file2.close()

        if not os.path.isfile(str(Path(LOCAL_DIR, "channelsettings.json"))):
            save_channel_sets()
        else:
            file1 = open(str(Path(LOCAL_DIR, "channelsettings.json")), encoding="utf8")
            DankoData.channel_sets = json.loads(file1.read())
            file1.close()

        DankoData.settings, settings_loaded = parse_settings()

        DankoData.favourite_sets = []

        def save_favourite_sets():
            favourite_sets_2 = {}
            if os.path.isfile(Path(LOCAL_DIR, "favouritechannels.json")):
                with open(
                    Path(LOCAL_DIR, "favouritechannels.json"), encoding="utf8"
                ) as fsetfile:
                    favourite_sets_2 = json.loads(fsetfile.read())
            if DankoData.settings["m3u"]:
                favourite_sets_2[DankoData.settings["m3u"]] = DankoData.favourite_sets
            file2 = open(
                Path(LOCAL_DIR, "favouritechannels.json"), "w", encoding="utf8"
            )
            file2.write(json.dumps(favourite_sets_2))
            file2.close()

        if not os.path.isfile(str(Path(LOCAL_DIR, "favouritechannels.json"))):
            save_favourite_sets()
        else:
            file1 = open(Path(LOCAL_DIR, "favouritechannels.json"), encoding="utf8")
            favourite_sets1 = json.loads(file1.read())
            if DankoData.settings["m3u"] in favourite_sets1:
                DankoData.favourite_sets = favourite_sets1[DankoData.settings["m3u"]]
            file1.close()

        DankoData.player_tracks = {}

        def save_player_tracks():
            player_tracks_2 = {}
            if os.path.isfile(Path(LOCAL_DIR, "tracks.json")):
                with open(
                    Path(LOCAL_DIR, "tracks.json"), encoding="utf8"
                ) as tracks_file0:
                    player_tracks_2 = json.loads(tracks_file0.read())
            if DankoData.settings["m3u"]:
                player_tracks_2[DankoData.settings["m3u"]] = DankoData.player_tracks
            tracks_file1 = open(Path(LOCAL_DIR, "tracks.json"), "w", encoding="utf8")
            tracks_file1.write(json.dumps(player_tracks_2))
            tracks_file1.close()

        if os.path.isfile(str(Path(LOCAL_DIR, "tracks.json"))):
            tracks_file = open(Path(LOCAL_DIR, "tracks.json"), encoding="utf8")
            player_tracks1 = json.loads(tracks_file.read())
            if DankoData.settings["m3u"] in player_tracks1:
                DankoData.player_tracks = player_tracks1[DankoData.settings["m3u"]]
            tracks_file.close()

        # https://www.qt.io/blog/dark-mode-on-windows-11-with-qt-6.5#before-qt-65
        current_palette = QtGui.QPalette()
        is_dark_theme = (
            current_palette.color(QtGui.QPalette.ColorRole.WindowText).lightness()
            > current_palette.color(QtGui.QPalette.ColorRole.Window).lightness()
        )
        if is_dark_theme:
            logger.info("Detected dark window theme")
            DankoData.use_dark_icon_theme = True
        else:
            DankoData.use_dark_icon_theme = False

        def get_epg_name(channel_name):
            epg_name = ""
            if (
                DankoData.settings["m3u"] in DankoData.channel_sets
                and channel_name in DankoData.channel_sets[DankoData.settings["m3u"]]
            ):
                if (
                    "epgname"
                    in DankoData.channel_sets[DankoData.settings["m3u"]][channel_name]
                ):
                    if DankoData.channel_sets[DankoData.settings["m3u"]][channel_name][
                        "epgname"
                    ]:
                        epg_name = DankoData.channel_sets[DankoData.settings["m3u"]][
                            channel_name
                        ]["epgname"]
            return epg_name

        def _get_epg_id(tvg_id, tvg_name, channel_name):
            ret = None
            if not DankoData.epg_pool_running:
                try:
                    ret = worker_get_epg_id(
                        tvg_id,
                        tvg_name,
                        channel_name,
                        get_epg_name(channel_name),
                        DankoData.epg_array,
                    )
                except Exception:
                    logger.warning("get_epg_id failed")
            return ret

        def get_epg_id(_data):
            if isinstance(_data, dict):
                _epg_title = (
                    _data["orig_title"] if "orig_title" in _data else _data["title"]
                )
                return _get_epg_id(_data["tvg-ID"], _data["tvg-name"], _epg_title)
            elif isinstance(_data, str):
                if _data in DankoData.array:
                    _epg_title = (
                        DankoData.array[_data]["orig_title"]
                        if "orig_title" in DankoData.array[_data]
                        else DankoData.array[_data]["title"]
                    )
                    return _get_epg_id(
                        DankoData.array[_data]["tvg-ID"],
                        DankoData.array[_data]["tvg-name"],
                        _epg_title,
                    )
                else:
                    return _get_epg_id("", "", _data)
            else:
                # logger.warning("get_epg_id failed - unknown type passed")
                return None

        def get_epg_programmes(epg_id):
            ret = None
            if not DankoData.epg_pool_running:
                try:
                    ret = worker_get_epg_programmes(epg_id, DankoData.epg_array)
                except Exception:
                    logger.warning("get_epg_programmes failed")
            return ret

        def get_epg_icon(epg_id):
            ret = None
            if not DankoData.epg_pool_running:
                try:
                    ret = worker_get_epg_icon(epg_id, DankoData.epg_array)
                except Exception:
                    logger.warning("get_epg_programmes failed")
            return ret

        def check_programmes_actual():
            ret = None
            if not DankoData.epg_pool_running:
                try:
                    ret = worker_check_programmes_actual(DankoData.epg_array)
                except Exception:
                    logger.warning("check_programmes_actual failed")
            return ret

        def get_all_epg_names():
            ret = None
            if not DankoData.epg_pool_running:
                try:
                    ret = worker_get_all_epg_names(DankoData.epg_array)
                except Exception:
                    logger.warning("get_all_epg_names failed")
            return ret

        def get_current_programme(epg_id):
            ret = None
            if not DankoData.epg_pool_running:
                try:
                    ret = worker_get_current_programme(epg_id, DankoData.epg_array)
                except Exception:
                    logger.warning("get_current_programme failed")
            return ret

        def purge_epg_cache():
            if not DankoData.epg_pool_running:
                logger.info("Purging EPG cache")
                for epg_cache_filename in os.listdir(Path(CACHE_DIR, "epg")):
                    epg_cache_file = Path(CACHE_DIR, "epg", epg_cache_filename)
                    if os.path.isfile(epg_cache_file):
                        os.remove(epg_cache_file)

        def force_update_epg_act():
            logger.info("Force update EPG triggered")
            purge_epg_cache()
            thread_epg_update_2 = threading.Thread(target=epg_update, daemon=True)
            thread_epg_update_2.start()

        def mainwindow_isvisible():
            try:
                return win.isVisible()
            except Exception:
                return False

        DankoGUI = DankoGUIClass()
        DankoData.DankoGUI = DankoGUI

        # Dankoiptv: aplicar skin naranja + fuente Ubuntu al arranque
        try:
            from dankoiptv_lib.skins import apply_look as _apply_look

            _apply_look()
        except Exception:
            logger.warning("Could not apply Dankoiptv skin")
            logger.warning(traceback.format_exc())

        channels = {}

        playlist_editor = PlaylistEditor()

        def show_playlist_editor():
            if playlist_editor.isVisible():
                playlist_editor.hide()
            else:
                move_window_to_center(playlist_editor)
                playlist_editor.show()

        save_folder = DankoData.settings["save_folder"]

        if not os.path.isdir(str(Path(save_folder))):
            try:
                Path(save_folder).mkdir(parents=True, exist_ok=True)
            except Exception:
                logger.warning("Failed to create save folder!")
                show_exception("Failed to create save folder!")
                save_folder = SAVE_FOLDER_DEFAULT
                if not os.path.isdir(str(Path(save_folder))):
                    Path(save_folder).mkdir(parents=True, exist_ok=True)

        if not os.access(save_folder, os.W_OK | os.X_OK):
            save_folder = SAVE_FOLDER_DEFAULT
            logger.warning(
                "Save folder is not writable (os.access), using default save folder"
            )
            show_exception(
                "Save folder is not writable (os.access), using default save folder"
            )

        if not DankoData.settings["scrrecnosubfolders"]:
            try:
                Path(save_folder, "screenshots").mkdir(parents=True, exist_ok=True)
                Path(save_folder, "recordings").mkdir(parents=True, exist_ok=True)
            except Exception:
                save_folder = SAVE_FOLDER_DEFAULT
                logger.warning(
                    "Save folder is not writable (subfolders), "
                    "using default save folder"
                )
                show_exception(
                    "Save folder is not writable (subfolders), "
                    "using default save folder"
                )
        else:
            if os.path.isdir(str(Path(save_folder, "screenshots"))):
                try:
                    os.rmdir(str(Path(save_folder, "screenshots")))
                except Exception:
                    pass
            if os.path.isdir(str(Path(save_folder, "recordings"))):
                try:
                    os.rmdir(str(Path(save_folder, "recordings")))
                except Exception:
                    pass

        def getArrayItem(arr_item):
            arr_item_ret = None
            if arr_item:
                if arr_item in DankoData.array:
                    arr_item_ret = DankoData.array[arr_item]
                elif arr_item in DankoData.movies:
                    arr_item_ret = DankoData.movies[arr_item]
                else:
                    try:
                        if " ::: " in arr_item:
                            arr_item_split = arr_item.split(" ::: ")
                            for season_name in DankoData.series[
                                arr_item_split[2]
                            ].seasons.keys():
                                season = DankoData.series[arr_item_split[2]].seasons[
                                    season_name
                                ]
                                if season.name == arr_item_split[1]:
                                    for episode_name in season.episodes.keys():
                                        episode = season.episodes[episode_name]
                                        if episode.title == arr_item_split[0]:
                                            arr_item_ret = {
                                                "title": episode.title,
                                                "tvg-name": "",
                                                "tvg-ID": "",
                                                "tvg-logo": "",
                                                "tvg-group": _("All channels"),
                                                "tvg-url": "",
                                                "catchup": "default",
                                                "catchup-source": "",
                                                "catchup-days": "7",
                                                "useragent": "",
                                                "referer": "",
                                                "url": episode.url,
                                            }
                                            break
                                    break
                    except Exception:
                        logger.warning("Exception in getArrayItem (series)")
                        logger.warning(traceback.format_exc())
            return arr_item_ret

        if os.path.isfile(str(Path(LOCAL_DIR, "sortchannels.json"))):
            with open(
                str(Path(LOCAL_DIR, "sortchannels.json")), encoding="utf8"
            ) as channel_sort_file1:
                channel_sort3 = json.loads(channel_sort_file1.read())
                if DankoData.settings["m3u"] in channel_sort3:
                    DankoData.channel_sort = channel_sort3[DankoData.settings["m3u"]]

        groups, m3u_exists, xt = load_playlist()

        def sigint_handler(*args):
            if DankoData.mpris_loop:
                DankoData.mpris_running = False
                DankoData.mpris_loop.quit()
            app.quit()

        signal.signal(signal.SIGINT, sigint_handler)
        signal.signal(signal.SIGTERM, sigint_handler)

        DankoGUI.create_windows()
        create_playlists_window()

        def resettodefaults_btn_clicked():
            resettodefaults_btn_clicked_msg = QtWidgets.QMessageBox.question(
                None,
                "dankoiptv",
                _("Are you sure?"),
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.Yes,
            )
            if (
                resettodefaults_btn_clicked_msg
                == QtWidgets.QMessageBox.StandardButton.Yes
            ):
                logger.info("Restoring default keybinds")
                DankoData.main_keybinds = main_keybinds_default.copy()
                DankoGUI.shortcuts_table.setRowCount(len(DankoData.main_keybinds))
                keybind_i = -1
                for keybind in DankoData.main_keybinds:
                    keybind_i += 1
                    DankoGUI.shortcuts_table.setItem(
                        keybind_i,
                        0,
                        get_widget_item(main_keybinds_translations[keybind]),
                    )
                    if isinstance(DankoData.main_keybinds[keybind], str):
                        keybind_str = DankoData.main_keybinds[keybind]
                    else:
                        keybind_str = QtGui.QKeySequence(
                            DankoData.main_keybinds[keybind]
                        ).toString()
                    kbd_widget = get_widget_item(keybind_str)
                    kbd_widget.setToolTip(_("Double click to change"))
                    DankoGUI.shortcuts_table.setItem(keybind_i, 1, kbd_widget)
                DankoGUI.shortcuts_table.resizeColumnsToContents()
                hotkeys_file_1 = open(
                    str(Path(LOCAL_DIR, "hotkeys.json")), "w", encoding="utf8"
                )
                hotkeys_file_1.write(
                    json.dumps({"current_profile": {"keys": DankoData.main_keybinds}})
                )
                hotkeys_file_1.close()
                reload_keybinds()

        DankoGUI.resettodefaults_btn.clicked.connect(resettodefaults_btn_clicked)

        class KeySequenceEdit(QtWidgets.QKeySequenceEdit):
            def keyPressEvent(self, event):
                super().keyPressEvent(event)
                self.setKeySequence(QtGui.QKeySequence(self.keySequence()))

        DankoGUI.keyseq = KeySequenceEdit()

        def keyseq_ok_clicked():
            if DankoData.selected_shortcut_row != -1:
                sel_keyseq = DankoGUI.keyseq.keySequence().toString()
                search_value = DankoGUI.shortcuts_table.item(
                    DankoData.selected_shortcut_row, 0
                ).text()
                shortcut_taken = False
                for sci1 in range(DankoGUI.shortcuts_table.rowCount()):
                    if sci1 != DankoData.selected_shortcut_row:
                        if DankoGUI.shortcuts_table.item(sci1, 1).text() == sel_keyseq:
                            shortcut_taken = True
                forbidden_hotkeys = [
                    "Return",
                    "Key.Key_MediaNext",
                    "Key.Key_MediaPause",
                    "Key.Key_MediaPlay",
                    "Key.Key_MediaPrevious",
                    "Key.Key_MediaRecord",
                    "Key.Key_MediaStop",
                    "Key.Key_MediaTogglePlayPause",
                    "Key.Key_Play",
                    "Key.Key_Stop",
                    "Key.Key_VolumeDown",
                    "Key.Key_VolumeMute",
                    "Key.Key_VolumeUp",
                ]
                if sel_keyseq in forbidden_hotkeys:
                    shortcut_taken = True
                if not shortcut_taken:
                    DankoGUI.shortcuts_table.item(
                        DankoData.selected_shortcut_row, 1
                    ).setText(sel_keyseq)
                    for name55, value55 in main_keybinds_translations.items():
                        if value55 == search_value:
                            DankoData.main_keybinds[name55] = sel_keyseq
                            hotkeys_file = open(
                                str(Path(LOCAL_DIR, "hotkeys.json")),
                                "w",
                                encoding="utf8",
                            )
                            hotkeys_file.write(
                                json.dumps(
                                    {
                                        "current_profile": {
                                            "keys": DankoData.main_keybinds
                                        }
                                    }
                                )
                            )
                            hotkeys_file.close()
                            reload_keybinds()
                    DankoGUI.shortcuts_win_2.hide()
                else:
                    msg_shortcut_taken = QtWidgets.QMessageBox(
                        QtWidgets.QMessageBox.Icon.Warning,
                        "dankoiptv",
                        _("Shortcut already used"),
                        QtWidgets.QMessageBox.StandardButton.Ok,
                    )
                    msg_shortcut_taken.exec()

        def epg_win_checkbox_changed():
            DankoGUI.tvguide_lbl_2.verticalScrollBar().setSliderPosition(
                DankoGUI.tvguide_lbl_2.verticalScrollBar().minimum()
            )
            DankoGUI.tvguide_lbl_2.setText(_("No TV guide for channel"))
            try:
                ch_3 = DankoGUI.epg_win_checkbox.currentText()
                ch_3_guide = update_tvguide(
                    ch_3, True, date_selected=DankoData.epg_selected_date
                ).replace("!@#$%^^&*(", "\n")
                ch_3_guide = ch_3_guide.replace("\n", "<br>").replace("<br>", "", 1)
                if ch_3_guide.strip():
                    DankoGUI.tvguide_lbl_2.setText(ch_3_guide)
                else:
                    DankoGUI.tvguide_lbl_2.setText(_("No TV guide for channel"))
            except Exception:
                exc = traceback.format_exc()
                logger.warning("Exception in epg_win_checkbox_changed")
                logger.warning(exc)
                show_exception(exc)

        def showonlychplaylist_chk_clk():
            update_tvguide_2()

        def tvguide_channelfilter_do():
            try:
                filter_txt3 = DankoGUI.tvguidechannelfilter.text()
            except Exception:
                filter_txt3 = ""
            for item6 in range(DankoGUI.epg_win_checkbox.count()):
                if (
                    filter_txt3.lower().strip()
                    in DankoGUI.epg_win_checkbox.itemText(item6).lower().strip()
                ):
                    DankoGUI.epg_win_checkbox.view().setRowHidden(item6, False)
                else:
                    DankoGUI.epg_win_checkbox.view().setRowHidden(item6, True)

        def epg_date_changed(epg_date):
            DankoData.epg_selected_date = datetime.datetime.fromordinal(
                epg_date.toPyDate().toordinal()
            )
            epg_win_checkbox_changed()

        DankoData.archive_epg = None

        def do_open_archive(link):
            if "#__archive__" in link:
                archive_json = json.loads(
                    urllib.parse.unquote_plus(link.split("#__archive__")[1])
                )
                arr1 = getArrayItem(archive_json[0])
                arr1 = format_catchup_array(arr1)

                channel_url = getArrayItem(archive_json[0])["url"]
                start_time = archive_json[1]
                end_time = archive_json[2]
                prog_index = archive_json[3]

                if "#__rewind__" not in link:
                    DankoData.archive_epg = archive_json

                catchup_id = ""
                try:
                    current_programmes = None
                    epg_id = get_epg_id(archive_json[0])
                    if epg_id:
                        programmes = get_epg_programmes(epg_id)
                        if programmes:
                            current_programmes = programmes

                    if current_programmes:
                        if "catchup-id" in current_programmes[int(prog_index)]:
                            catchup_id = current_programmes[int(prog_index)][
                                "catchup-id"
                            ]
                except Exception:
                    logger.warning("do_open_archive / catchup_id parsing failed")
                    logger.warning(traceback.format_exc())

                arr2 = arr1

                if DankoData.is_xtream:
                    arr2["catchup"] = "xc"

                play_url = get_catchup_url(
                    channel_url, arr2, start_time, end_time, catchup_id
                )

                itemClicked_event(
                    archive_json[0], play_url, True, is_rewind=(len(archive_json) == 5)
                )
                setChannelText("({}) {}".format(_("Archive"), archive_json[0]), True)
                DankoGUI.progress.hide()
                DankoGUI.start_label.setText("")
                DankoGUI.start_label.hide()
                DankoGUI.stop_label.setText("")
                DankoGUI.stop_label.hide()
                DankoGUI.epg_win.hide()

                return False

        def esw_input_edit():
            esw_input_text = DankoGUI.esw_input.text().lower()
            for est_w in range(0, DankoGUI.esw_select.count()):
                if (
                    DankoGUI.esw_select.item(est_w)
                    .text()
                    .lower()
                    .startswith(esw_input_text)
                ):
                    DankoGUI.esw_select.item(est_w).setHidden(False)
                else:
                    DankoGUI.esw_select.item(est_w).setHidden(True)

        def esw_select_clicked(item1):
            DankoGUI.epg_select_win.hide()
            if item1.text():
                DankoGUI.epgname_lbl.setText(item1.text())
            else:
                DankoGUI.epgname_lbl.setText(_("Default"))

        def ext_open_btn_clicked():
            write_option("extplayer", DankoGUI.ext_player_txt.text().strip())
            DankoGUI.ext_win.close()
            try:
                subprocess.Popen(
                    DankoGUI.ext_player_txt.text().strip().split(" ")
                    + [getArrayItem(DankoData.item_selected)["url"]]
                )
            except Exception:
                logger.warning("Failed to open external player!")
                logger.warning(traceback.format_exc())
                show_exception(
                    traceback.format_exc(), _("Failed to open external player!")
                )

        DankoGUI.create4()

        DankoData.epg_selected_date = datetime.datetime.fromordinal(
            datetime.date.today().toordinal()
        )

        DankoGUI.keyseq_cancel.clicked.connect(DankoGUI.shortcuts_win_2.hide)
        DankoGUI.keyseq_ok.clicked.connect(keyseq_ok_clicked)
        DankoGUI.tvguidechannelfiltersearch.clicked.connect(tvguide_channelfilter_do)
        DankoGUI.tvguidechannelfilter.returnPressed.connect(tvguide_channelfilter_do)
        DankoGUI.showonlychplaylist_chk.clicked.connect(showonlychplaylist_chk_clk)
        DankoGUI.epg_win_checkbox.currentIndexChanged.connect(epg_win_checkbox_changed)
        DankoGUI.epg_select_date.activated.connect(epg_date_changed)
        DankoGUI.epg_select_date.clicked.connect(epg_date_changed)
        DankoGUI.tvguide_lbl_2.label.linkActivated.connect(do_open_archive)
        DankoGUI.esw_button.clicked.connect(esw_input_edit)
        DankoGUI.esw_select.itemDoubleClicked.connect(esw_select_clicked)
        DankoGUI.ext_open_btn.clicked.connect(ext_open_btn_clicked)

        extplayer = read_option("extplayer")
        if extplayer is None:
            extplayer = "mpv"
        DankoGUI.ext_player_txt.setText(extplayer)

        DankoData.playlists_saved = {}

        if os.path.isfile(str(Path(LOCAL_DIR, "playlists.json"))):
            playlists_json = open(
                str(Path(LOCAL_DIR, "playlists.json")), encoding="utf8"
            )
            DankoData.playlists_saved = json.loads(playlists_json.read())
            playlists_json.close()

        DankoData.time_stop = 0

        DankoData.ffmpeg_processes = []

        init_record(show_exception, DankoData.ffmpeg_processes)

        def convert_time(times_1):
            yr = time.strftime("%Y", time.localtime())
            yr = yr[0] + yr[1]
            times_1_sp = times_1.split(" ")
            times_1_sp_0 = times_1_sp[0].split(".")
            times_1_sp_0[2] = yr + times_1_sp_0[2]
            times_1_sp[0] = ".".join(times_1_sp_0)
            return " ".join(times_1_sp)

        def programme_clicked(item):
            times = item.text().split("\n")[0]
            start_time = convert_time(times.split(" - ")[0])
            end_time = convert_time(times.split(" - ")[1])
            DankoGUI.starttime_w.setDateTime(
                QtCore.QDateTime.fromString(start_time, "d.M.yyyy hh:mm")
            )
            DankoGUI.endtime_w.setDateTime(
                QtCore.QDateTime.fromString(end_time, "d.M.yyyy hh:mm")
            )

        def addrecord_clicked():
            selected_channel = DankoGUI.choosechannel_ch.currentText()
            start_time_r = (
                DankoGUI.starttime_w.dateTime().toPyDateTime().strftime("%d.%m.%y %H:%M")
            )
            end_time_r = (
                DankoGUI.endtime_w.dateTime().toPyDateTime().strftime("%d.%m.%y %H:%M")
            )
            DankoGUI.schedulers.addItem(
                _("Channel") + ": " + selected_channel + "\n"
                "{}: ".format(_("Start record time")) + start_time_r + "\n"
                "{}: ".format(_("End record time")) + end_time_r + "\n"
            )

        sch_recordings = {}

        def do_start_record(name1):
            ch_name = name1.split("_")[0]
            ch = ch_name.replace(" ", "_")
            for char in FORBIDDEN_CHARS:
                ch = ch.replace(char, "")
            cur_time = datetime.datetime.now().strftime("%d%m%Y_%H%M%S")
            if not DankoData.settings["scrrecnosubfolders"]:
                out_file = str(
                    Path(
                        save_folder,
                        "recordings",
                        f"recording_-_{cur_time}_-_{ch}.ts",
                    )
                )
            else:
                out_file = str(
                    Path(
                        save_folder,
                        f"recording_-_{cur_time}_-_{ch}.ts",
                    )
                )
            return [
                record(
                    getArrayItem(ch_name)["url"],
                    out_file,
                    ch_name,
                    f"Referer: {DankoData.settings['referer']}",
                    get_ua_ref_for_channel,
                    True,
                ),
                time.time(),
                out_file,
                ch_name,
            ]

        def do_stop_record(name2):
            if name2 in sch_recordings:
                ffmpeg_process = sch_recordings[name2][0]
                if ffmpeg_process:
                    terminate_record_process(ffmpeg_process)

        def record_post_action_after():
            logger.info("Record via scheduler ended, executing post-action...")
            # 0 - nothing to do
            if DankoGUI.praction_choose.currentIndex() == 1:  # 1 - Press Stop
                mpv_stop()

        def record_post_action():
            while True:
                if is_recording_func() is True:
                    break
                time.sleep(1)
            execute_in_main_thread(partial(record_post_action_after))

        def record_timer_2():
            try:
                activerec_list_value = (
                    DankoGUI.activerec_list.verticalScrollBar().value()
                )
                DankoGUI.activerec_list.clear()
                for sch0 in sch_recordings:
                    counted_time0 = format_seconds(
                        time.time() - sch_recordings[sch0][1]
                    )
                    channel_name0 = sch_recordings[sch0][3]
                    file_name0 = sch_recordings[sch0][2]
                    file_size0 = "WAITING"
                    if os.path.isfile(file_name0):
                        file_size0 = convert_size(os.path.getsize(file_name0))
                    DankoGUI.activerec_list.addItem(
                        channel_name0 + "\n" + counted_time0 + " " + file_size0
                    )
                DankoGUI.activerec_list.verticalScrollBar().setValue(
                    activerec_list_value
                )
                pl_text = "REC / " + _("Scheduler")
                if DankoGUI.activerec_list.count() != 0:
                    DankoData.recViaScheduler = True
                    DankoGUI.lbl2.setText(pl_text)
                    DankoGUI.lbl2.show()
                else:
                    if DankoData.recViaScheduler:
                        logger.info(
                            "Record via scheduler ended, waiting"
                            " for ffmpeg process completion..."
                        )
                        thread_record_post_action = threading.Thread(
                            target=record_post_action, daemon=True
                        )
                        thread_record_post_action.start()
                    DankoData.recViaScheduler = False
                    if DankoGUI.lbl2.text() == pl_text:
                        DankoGUI.lbl2.hide()
            except Exception:
                pass

        def record_timer():
            try:
                if DankoData.is_recording != DankoData.is_recording_old:
                    DankoData.is_recording_old = DankoData.is_recording
                    if DankoData.is_recording:
                        execute_in_main_thread(
                            partial(
                                DankoGUI.btn_record.setIcon, DankoGUI.record_stop_icon
                            )
                        )
                    else:
                        execute_in_main_thread(
                            partial(DankoGUI.btn_record.setIcon, DankoGUI.record_icon)
                        )
                status = _("No planned recordings")
                sch_items = [
                    str(DankoGUI.schedulers.item(i1).text())
                    for i1 in range(DankoGUI.schedulers.count())
                ]
                i3 = -1
                for sch_item in sch_items:
                    i3 += 1
                    status = _("Waiting for record")
                    sch_item = [i2.split(": ")[1] for i2 in sch_item.split("\n") if i2]
                    channel_name_rec = sch_item[0]
                    current_time = time.strftime("%d.%m.%y %H:%M", time.localtime())
                    start_time_1 = sch_item[1]
                    end_time_1 = sch_item[2]
                    array_name = (
                        str(channel_name_rec)
                        + "_"
                        + str(start_time_1)
                        + "_"
                        + str(end_time_1)
                    )
                    if start_time_1 == current_time:
                        if array_name not in sch_recordings:
                            st_planned = (
                                "Starting planned record"
                                + " (start_time='{}' end_time='{}' channel='{}')"
                            )
                            logger.info(
                                st_planned.format(
                                    start_time_1, end_time_1, channel_name_rec
                                )
                            )
                            sch_recordings[array_name] = do_start_record(array_name)
                            DankoData.ffmpeg_processes.append(sch_recordings[array_name])
                    if end_time_1 == current_time:
                        if array_name in sch_recordings:
                            DankoGUI.schedulers.takeItem(i3)
                            stop_planned = (
                                "Stopping planned record"
                                + " (start_time='{}' end_time='{}' channel='{}')"
                            )
                            logger.info(
                                stop_planned.format(
                                    start_time_1, end_time_1, channel_name_rec
                                )
                            )
                            do_stop_record(array_name)
                            sch_recordings.pop(array_name)
                    if sch_recordings:
                        status = _("Recording")
                DankoGUI.statusrec_lbl.setText("{}: {}".format(_("Status"), status))
            except Exception:
                pass

        def delrecord_clicked():
            schCurrentRow = DankoGUI.schedulers.currentRow()
            if schCurrentRow != -1:
                sch_index = "_".join(
                    [
                        xs.split(": ")[1]
                        for xs in DankoGUI.schedulers.item(schCurrentRow)
                        .text()
                        .split("\n")
                        if xs
                    ]
                )
                DankoGUI.schedulers.takeItem(schCurrentRow)
                if sch_index in sch_recordings:
                    do_stop_record(sch_index)
                    sch_recordings.pop(sch_index)

        def scheduler_channelfilter_do():
            try:
                filter_txt2 = DankoGUI.schedulerchannelfilter.text()
            except Exception:
                filter_txt2 = ""
            for item5 in range(DankoGUI.choosechannel_ch.count()):
                if (
                    filter_txt2.lower().strip()
                    in DankoGUI.choosechannel_ch.itemText(item5).lower().strip()
                ):
                    DankoGUI.choosechannel_ch.view().setRowHidden(item5, False)
                else:
                    DankoGUI.choosechannel_ch.view().setRowHidden(item5, True)

        DankoGUI.create_scheduler_widgets(get_current_time())

        def save_sort():
            DankoData.channel_sort = [
                DankoGUI.sort_list.item(z0).text()
                for z0 in range(DankoGUI.sort_list.count())
            ]
            channel_sort2 = {}
            if os.path.isfile(Path(LOCAL_DIR, "sortchannels.json")):
                with open(
                    Path(LOCAL_DIR, "sortchannels.json"), encoding="utf8"
                ) as file5:
                    channel_sort2 = json.loads(file5.read())
            channel_sort2[DankoData.settings["m3u"]] = DankoData.channel_sort
            with open(
                Path(LOCAL_DIR, "sortchannels.json"), "w", encoding="utf8"
            ) as channel_sort_file:
                channel_sort_file.write(json.dumps(channel_sort2))
            DankoGUI.sort_win.hide()

        DankoGUI.create_sort_widgets()
        DankoGUI.save_sort_btn.clicked.connect(save_sort)

        DankoGUI.tvguide_sch.itemClicked.connect(programme_clicked)
        DankoGUI.addrecord_btn.clicked.connect(addrecord_clicked)
        DankoGUI.delrecord_btn.clicked.connect(delrecord_clicked)
        DankoGUI.schedulerchannelfiltersearch.clicked.connect(scheduler_channelfilter_do)
        DankoGUI.schedulerchannelfilter.returnPressed.connect(scheduler_channelfilter_do)

        def save_folder_select():
            folder_name = QtWidgets.QFileDialog.getExistingDirectory(
                DankoGUI.settings_win,
                _("Select folder for recordings and screenshots"),
                options=QtWidgets.QFileDialog.Option.ShowDirsOnly,
            )
            if folder_name:
                DankoGUI.save_folder_widget.setText(folder_name)

        # Channel settings window
        def epgname_btn_action():
            prog_ids_0 = get_all_epg_names()
            if not prog_ids_0:
                prog_ids_0 = set()
            DankoGUI.esw_select.clear()
            DankoGUI.esw_select.addItem("")
            for prog_ids_0_dat in prog_ids_0:
                DankoGUI.esw_select.addItem(prog_ids_0_dat)
            esw_input_edit()
            move_window_to_center(DankoGUI.epg_select_win)
            DankoGUI.epg_select_win.show()

        DankoGUI.epgname_btn.clicked.connect(epgname_btn_action)

        default_user_agent = (
            DankoData.settings["playlist_useragent"]
            if DankoData.settings["playlist_useragent"]
            else DankoData.settings["ua"]
        )
        logger.info(f"Default User-Agent: {default_user_agent}")
        default_referer = (
            DankoData.settings["playlist_referer"]
            if DankoData.settings["playlist_referer"]
            else DankoData.settings["referer"]
        )
        if default_referer:
            logger.info(f"Default HTTP referer: {default_referer}")
        else:
            logger.info("Default HTTP referer: (empty)")

        def hideLoading():
            DankoData.is_loading = False
            loading.hide()
            DankoGUI.loading_movie.stop()
            DankoGUI.loading1.hide()
            execute_in_main_thread(partial(idle_on_metadata))

        def showLoading():
            DankoData.is_loading = True
            DankoGUI.centerwidget(DankoGUI.loading1)
            loading.show()
            DankoGUI.loading_movie.start()
            DankoGUI.loading1.show()
            execute_in_main_thread(partial(idle_on_metadata))

        def on_before_play():
            DankoGUI.streaminfo_win.hide()
            stream_info.video_properties.clear()
            stream_info.video_properties[_("General")] = {}
            stream_info.video_properties[_("Color")] = {}

            stream_info.audio_properties.clear()
            stream_info.audio_properties[_("General")] = {}
            stream_info.audio_properties[_("Layout")] = {}

            stream_info.video_bitrates.clear()
            stream_info.audio_bitrates.clear()

        def get_ua_ref_for_channel(channel_name1):
            useragent_ref = (
                DankoData.settings["playlist_useragent"]
                if DankoData.settings["playlist_useragent"]
                else DankoData.settings["ua"]
            )
            referer_ref = (
                DankoData.settings["playlist_referer"]
                if DankoData.settings["playlist_referer"]
                else DankoData.settings["referer"]
            )
            if channel_name1:
                channel_item = getArrayItem(channel_name1)
                if channel_item:
                    useragent_ref = (
                        channel_item["useragent"]
                        if "useragent" in channel_item and channel_item["useragent"]
                        else (
                            DankoData.settings["playlist_useragent"]
                            if DankoData.settings["playlist_useragent"]
                            else DankoData.settings["ua"]
                        )
                    )
                    referer_ref = (
                        channel_item["referer"]
                        if "referer" in channel_item and channel_item["referer"]
                        else (
                            DankoData.settings["playlist_referer"]
                            if DankoData.settings["playlist_referer"]
                            else DankoData.settings["referer"]
                        )
                    )
            if DankoData.settings["m3u"] in DankoData.channel_sets:
                channel_set = DankoData.channel_sets[DankoData.settings["m3u"]]
                if channel_name1 and channel_name1 in channel_set:
                    channel_config = channel_set[channel_name1]
                    if (
                        "ua" in channel_config
                        and channel_config["ua"]
                        and channel_config["ua"]
                        != (
                            DankoData.settings["playlist_useragent"]
                            if DankoData.settings["playlist_useragent"]
                            else DankoData.settings["ua"]
                        )
                    ):
                        useragent_ref = channel_config["ua"]
                    if (
                        "ref" in channel_config
                        and channel_config["ref"]
                        and channel_config["ref"]
                        != (
                            DankoData.settings["playlist_referer"]
                            if DankoData.settings["playlist_referer"]
                            else DankoData.settings["referer"]
                        )
                    ):
                        referer_ref = channel_config["ref"]
            return useragent_ref, referer_ref

        def mpv_override_play(arg_override_play, channel_name1=""):
            on_before_play()
            useragent_ref, referer_ref = get_ua_ref_for_channel(channel_name1)
            DankoData.player.user_agent = useragent_ref
            if referer_ref:
                originURL = ""
                if referer_ref.endswith("/"):
                    originURL = referer_ref[:-1]
                if originURL:
                    DankoData.player.http_header_fields = (
                        f"Referer: {referer_ref},Origin: {originURL}"
                    )
                else:
                    DankoData.player.http_header_fields = f"Referer: {referer_ref}"
            else:
                DankoData.player.http_header_fields = ""

            if not arg_override_play.endswith("/main.png"):
                logger.info(f"Using User-Agent: {DankoData.player.user_agent}")
                cur_ref = ""
                try:
                    for ref1 in DankoData.player.http_header_fields:
                        if ref1.startswith("Referer: "):
                            ref1 = ref1.replace("Referer: ", "", 1)
                            cur_ref = ref1
                except Exception:
                    pass
                if cur_ref:
                    logger.info(f"Using HTTP Referer: {cur_ref}")
                else:
                    logger.info("Using HTTP Referer: (empty)")

            DankoData.player.pause = False
            try:
                DankoData.player.ytdl = is_youtube_url(arg_override_play)
            except Exception:
                logger.warning("Could not toggle mpv ytdl option")
                logger.warning(traceback.format_exc())
            DankoData.player.play(parse_specifiers_in_url(arg_override_play))
            if DankoData.event_handler:
                try:
                    DankoData.event_handler.on_metadata()
                except Exception:
                    pass

        def mpv_override_stop(ignore=False):
            # Al parar, restaurar keep-open=no (si no, el logo main.png loopea)
            try:
                DankoData.player.keep_open = False
            except Exception:
                pass
            try:
                DankoData._seamless_armed = False
            except Exception:
                pass
            DankoData.player.command("stop")
            if not ignore:
                logger.info("Disabling deinterlace for main.png")
                DankoData.player.deinterlace = False
            DankoData.player.play(str(Path(DankoGUI.icons_folder, "main.png")))
            DankoData.player.pause = True
            if DankoData.event_handler:
                try:
                    DankoData.event_handler.on_metadata()
                except Exception:
                    pass

        def mpv_override_volume(volume_val):
            DankoData.player.volume = volume_val
            DankoData.volume = volume_val
            if DankoData.event_handler:
                try:
                    DankoData.event_handler.on_volume()
                except Exception:
                    pass

        def mpv_override_mute(mute_val):
            DankoData.player.mute = mute_val
            if DankoData.event_handler:
                try:
                    DankoData.event_handler.on_volume()
                except Exception:
                    pass

        def stopPlayer(ignore=False):
            try:
                mpv_override_stop(ignore)
            except Exception:
                DankoData.player.loop = True
                mpv_override_play(str(Path(DankoGUI.icons_folder, "main.png")))
                DankoData.player.pause = True

        def setVideoAspect(va):
            if va == 0:
                va = -1
            try:
                DankoData.player.video_aspect_override = va
            except Exception:
                DankoData.player.video_aspect = va

        def getVideoAspect():
            try:
                va1 = DankoData.player.video_aspect_override
            except Exception:
                va1 = DankoData.player.video_aspect
            return va1

        def doPlay(play_url1, ua_ch=default_user_agent, channel_name_0=""):
            DankoData.do_play_args = (play_url1, ua_ch, channel_name_0)
            logger.info(f"Playing channel: {channel_name_0}")
            logger.debug(f"URL: {play_url1}")
            loading.setText(_("Loading..."))
            loading.setFont(DankoGUI.font_italic_medium)
            showLoading()
            DankoData.player.loop = False
            # Dankoiptv seamless engine (AGENTS §3): live congela último frame
            # sin negro; VOD mantiene seek. PROHIBIDOS prefetch-playlist y
            # stream-lavf-o=reconnect (rebobinan, verificado empíricamente).
            try:
                DankoData._seamless_armed = True
                if DankoData.playing_group == 0:
                    DankoData.player.keep_open = True
                    DankoData.player.keep_open_pause = False
                    DankoData.player.loop_playlist = "no"
                    DankoData.player.force_seekable = False
                else:
                    DankoData.player.keep_open = False
                    DankoData.player.force_seekable = True
                    DankoData.player.loop_playlist = "no"
            except Exception:
                logger.warning("Could not set seamless live options")
                logger.warning(traceback.format_exc())
            mpv_override_play(play_url1, channel_name_0)
            thread_set_player_settings = threading.Thread(
                target=set_player_settings, args=(channel_name_0,), daemon=True
            )
            thread_set_player_settings.start()
            thread_monitor_playback = threading.Thread(
                target=monitor_playback, daemon=True
            )
            thread_monitor_playback.start()

        def channel_settings_save():
            channel_3 = DankoGUI.title.text()
            if DankoData.settings["m3u"] not in DankoData.channel_sets:
                DankoData.channel_sets[DankoData.settings["m3u"]] = {}
            DankoData.channel_sets[DankoData.settings["m3u"]][channel_3] = {
                "deinterlace": DankoGUI.deinterlace_chk.isChecked(),
                "ua": DankoGUI.useragent_choose.text(),
                "ref": DankoGUI.referer_choose_custom.text(),
                "group": DankoGUI.group_text.text(),
                "hidden": DankoGUI.hidden_chk.isChecked(),
                "contrast": DankoGUI.contrast_choose.value(),
                "brightness": DankoGUI.brightness_choose.value(),
                "hue": DankoGUI.hue_choose.value(),
                "saturation": DankoGUI.saturation_choose.value(),
                "gamma": DankoGUI.gamma_choose.value(),
                "videoaspect": DankoGUI.videoaspect_choose.currentIndex(),
                "zoom": DankoGUI.zoom_choose.currentIndex(),
                "panscan": DankoGUI.panscan_choose.value(),
                "epgname": (
                    DankoGUI.epgname_lbl.text()
                    if DankoGUI.epgname_lbl.text() != _("Default")
                    else ""
                ),
            }
            save_channel_sets()
            if DankoData.playing_channel == channel_3:
                DankoData.player.deinterlace = DankoGUI.deinterlace_chk.isChecked()
                DankoData.player.contrast = DankoGUI.contrast_choose.value()
                DankoData.player.brightness = DankoGUI.brightness_choose.value()
                DankoData.player.hue = DankoGUI.hue_choose.value()
                DankoData.player.saturation = DankoGUI.saturation_choose.value()
                DankoData.player.gamma = DankoGUI.gamma_choose.value()
                DankoData.player.video_zoom = DankoGUI.zoom_vars[
                    list(DankoGUI.zoom_vars)[DankoGUI.zoom_choose.currentIndex()]
                ]
                DankoData.player.panscan = DankoGUI.panscan_choose.value()
                setVideoAspect(
                    DankoGUI.videoaspect_vars[
                        list(DankoGUI.videoaspect_vars)[
                            DankoGUI.videoaspect_choose.currentIndex()
                        ]
                    ]
                )
            execute_in_main_thread(partial(redraw_channels))
            DankoGUI.channels_win.close()

        DankoGUI.save_btn.clicked.connect(channel_settings_save)

        DankoGUI.channels_win.setCentralWidget(DankoGUI.wid)

        def save_settings():
            settings_arr = DankoGUI.get_settings()
            with open(
                str(Path(LOCAL_DIR, "settings.json")), "w", encoding="utf8"
            ) as settings_file:
                settings_file.write(json.dumps(settings_arr))
            DankoGUI.settings_win.hide()
            DankoData.do_save_settings = True
            app.quit()

        DankoData.save_settings = save_settings

        def reset_channel_settings():
            if os.path.isfile(str(Path(LOCAL_DIR, "channelsettings.json"))):
                os.remove(str(Path(LOCAL_DIR, "channelsettings.json")))
            if os.path.isfile(str(Path(LOCAL_DIR, "favouritechannels.json"))):
                os.remove(str(Path(LOCAL_DIR, "favouritechannels.json")))
            if os.path.isfile(str(Path(LOCAL_DIR, "sortchannels.json"))):
                os.remove(str(Path(LOCAL_DIR, "sortchannels.json")))
            save_settings()

        def do_clear_logo_cache():
            logger.info("Clearing channel logos cache...")
            if os.path.isdir(Path(CACHE_DIR, "logo")):
                channel_logos = os.listdir(Path(CACHE_DIR, "logo"))
                for channel_logo in channel_logos:
                    if os.path.isfile(Path(CACHE_DIR, "logo", channel_logo)):
                        os.remove(Path(CACHE_DIR, "logo", channel_logo))
            logger.info("Channel logos cache cleared!")

        def close_settings():
            DankoGUI.settings_win.hide()
            if not win.isVisible():
                if not gui_playlists_data.playlists_win.isVisible():
                    myExitHandler_before()
                    sys.exit(0)

        DankoGUI.ssave.clicked.connect(save_settings)
        DankoGUI.sreset.clicked.connect(reset_channel_settings)
        DankoGUI.clear_logo_cache.clicked.connect(do_clear_logo_cache)
        DankoGUI.sclose.clicked.connect(close_settings)
        DankoGUI.sfolder.clicked.connect(save_folder_select)

        DankoGUI.set_from_settings()

        DankoGUI.settings_win.scroll.setWidget(DankoGUI.wid2)

        def set_url_text():
            DankoGUI.url_text.setText(DankoData.playing_url)
            DankoGUI.url_text.setCursorPosition(0)
            if DankoGUI.streaminfo_win.isVisible():
                DankoGUI.streaminfo_win.hide()

        DankoGUI.streaminfo_win.setCentralWidget(DankoGUI.streaminfo_win_widget)

        def show_license():
            if not DankoGUI.license_win.isVisible():
                move_window_to_center(DankoGUI.license_win)
                DankoGUI.license_win.show()
            else:
                DankoGUI.license_win.hide()

        DankoGUI.licensebox_close_btn.clicked.connect(DankoGUI.license_win.close)
        DankoGUI.license_win.setCentralWidget(DankoGUI.licensewin_widget)

        def aboutqt_show():
            QtWidgets.QMessageBox.aboutQt(DankoGUI.help_win, "dankoiptv")
            DankoGUI.help_win.raise_()
            DankoGUI.help_win.setFocus(QtCore.Qt.FocusReason.PopupFocusReason)
            DankoGUI.help_win.activateWindow()

        DankoGUI.license_btn.clicked.connect(show_license)
        DankoGUI.aboutqt_btn.clicked.connect(aboutqt_show)
        DankoGUI.close_btn.clicked.connect(DankoGUI.help_win.close)

        DankoGUI.help_win.setCentralWidget(DankoGUI.helpwin_widget)

        def shortcuts_table_clicked(row1, column1):
            if column1 == 1:  # keybind
                sc1_text = DankoGUI.shortcuts_table.item(row1, column1).text()
                DankoGUI.keyseq.setKeySequence(sc1_text)
                DankoData.selected_shortcut_row = row1
                DankoGUI.keyseq.setFocus()
                move_window_to_center(DankoGUI.shortcuts_win_2)
                DankoGUI.shortcuts_win_2.show()

        DankoGUI.shortcuts_table.cellDoubleClicked.connect(shortcuts_table_clicked)

        def get_widget_item(widget_str):
            twi = QtWidgets.QTableWidgetItem(widget_str)
            twi.setFlags(twi.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
            return twi

        def show_shortcuts():
            if not DankoGUI.shortcuts_win.isVisible():
                DankoGUI.shortcuts_table.setRowCount(len(DankoData.main_keybinds))
                keybind_i = -1
                for keybind in DankoData.main_keybinds:
                    keybind_i += 1
                    DankoGUI.shortcuts_table.setItem(
                        keybind_i,
                        0,
                        get_widget_item(main_keybinds_translations[keybind]),
                    )
                    if isinstance(DankoData.main_keybinds[keybind], str):
                        keybind_str = DankoData.main_keybinds[keybind]
                    else:
                        keybind_str = QtGui.QKeySequence(
                            DankoData.main_keybinds[keybind]
                        ).toString()
                    kbd_widget = get_widget_item(keybind_str)
                    kbd_widget.setToolTip(_("Double click to change"))
                    DankoGUI.shortcuts_table.setItem(keybind_i, 1, kbd_widget)
                DankoGUI.shortcuts_table.resizeColumnsToContents()
                move_window_to_center(DankoGUI.shortcuts_win)
                DankoGUI.shortcuts_win.show()
            else:
                DankoGUI.shortcuts_win.hide()

        def show_settings():
            if not DankoGUI.settings_win.isVisible():
                move_window_to_center(DankoGUI.settings_win)
                DankoGUI.settings_win.show()
            else:
                DankoGUI.settings_win.hide()

        DankoData.show_settings = show_settings

        def show_help():
            if not DankoGUI.help_win.isVisible():
                move_window_to_center(DankoGUI.help_win)
                DankoGUI.help_win.show()
            else:
                DankoGUI.help_win.hide()

        def show_sort():
            if not DankoGUI.sort_win.isVisible():
                DankoGUI.sort_list.clear()
                for sort_label_ch in (
                    DankoData.array_sorted
                    if not DankoData.channel_sort
                    else DankoData.channel_sort
                ):
                    DankoGUI.sort_list.addItem(sort_label_ch)

                move_window_to_center(DankoGUI.sort_win)
                DankoGUI.sort_win.show()
            else:
                DankoGUI.sort_win.hide()

        def reload_playlist():
            logger.info("Reloading playlist...")
            save_settings()

        def set_mpv_osc(osc_value):
            if osc_value != DankoData.osc:
                DankoData.osc = osc_value
                DankoData.player.osc = osc_value

        def init_mpv_player():
            DankoData.player = mpv.MPV(
                **options,
                log_handler=my_log,
            )
            DankoData.force_turnoff_osc = not DankoData.player.osc

            logger.info(f"{DankoData.player.mpv_version}")

            DankoGUI.textbox.setText(get_about_text())

            if DankoData.settings["cache_secs"] != 0:
                DankoData.player.demuxer_readahead_secs = DankoData.settings["cache_secs"]
                DankoData.player.cache_secs = DankoData.settings["cache_secs"]
                logger.info(f"Cache set to {DankoData.player.cache_secs}s")
            else:
                logger.info("Using default cache settings")
            DankoData.player.user_agent = default_user_agent
            _referer = (
                DankoData.settings["playlist_referer"]
                if DankoData.settings["playlist_referer"]
                else DankoData.settings["referer"]
            )
            if _referer:
                referer = _referer
                originURL = ""
                if referer.endswith("/"):
                    originURL = referer[:-1]
                if originURL:
                    DankoData.player.http_header_fields = (
                        f"Referer: {referer},Origin: {originURL}"
                    )
                else:
                    DankoData.player.http_header_fields = f"Referer: {referer}"
                logger.info(f"HTTP referer: '{referer}'")
            else:
                logger.info("No HTTP referer set up")
            mpv_override_volume(100)
            DankoData.player.loop = True

            try:
                populate_menubar(
                    0,
                    win.menu_bar_qt,
                    win,
                    DankoData.player.track_list,
                    DankoData.playing_channel,
                    get_keybind,
                )
                populate_menubar(
                    1,
                    DankoData.right_click_menu,
                    win,
                    DankoData.player.track_list,
                    DankoData.playing_channel,
                    get_keybind,
                )
            except Exception:
                logger.warning("populate_menubar failed")
                show_exception(traceback.format_exc(), "populate_menubar failed")
            redraw_menubar()

            @DankoData.player.property_observer("duration")
            def duration_observer(_name, value):
                try:
                    if DankoData.old_playing_url != DankoData.playing_url:
                        DankoData.old_playing_url = DankoData.playing_url
                        DankoData.event_handler.on_metadata()
                except Exception:
                    pass

            @DankoData.player.property_observer("current-vo")
            def vo_observer(_name, value):
                try:
                    if value.strip() == "sdl" and not (
                        "vo" in options_custom
                        and str(options_custom["vo"]).strip() == "sdl"
                    ):
                        logger.info("sdl video output detected, switching to x11")
                        DankoData.player.vo = "x11"
                except Exception:
                    pass

            def seek_event_callback():
                if (
                    DankoData.player
                    and DankoData.mpris_ready
                    and DankoData.mpris_running
                    and not DankoData.stopped
                ):
                    (
                        playback_status,
                        mpris_trackid,
                        artUrl,
                        player_position,
                    ) = get_mpris_metadata()
                    mpris_seeked(player_position)

            @DankoData.player.event_callback("seek")
            def seek_event(event):
                execute_in_main_thread(partial(seek_event_callback))

            @DankoData.player.event_callback("file-loaded")
            def file_loaded_2(event):
                execute_in_main_thread(partial(file_loaded_callback))

            @DankoData.player.event_callback("end_file")
            def ready_handler_2(event):
                _event = event.as_dict()
                if "reason" in _event and "error" in decode(_event["reason"]):
                    execute_in_main_thread(partial(end_file_error_callback))
                else:
                    execute_in_main_thread(partial(end_file_callback))

            # Dankoiptv seamless engine: con keep-open el EOF ya NO dispara
            # end-file; observamos eof-reached (NODE → bool real) y recargamos
            # con backoff en cascada manteniendo el último frame en pantalla.
            @DankoData.player.property_observer("eof-reached")
            def eof_reached_observer(_name, value):
                execute_in_main_thread(partial(eof_reached_handler, value))

            @DankoData.player.on_key_press("MBTN_RIGHT")
            def my_mouse_right():
                execute_in_main_thread(partial(my_mouse_right_callback))

            @DankoData.player.on_key_press("MBTN_LEFT")
            def my_mouse_left():
                execute_in_main_thread(partial(my_mouse_left_callback))

            @DankoData.player.on_key_press("MBTN_LEFT_DBL")
            def my_leftdbl_binding():
                mpv_fullscreen()

            @DankoData.player.on_key_press("MBTN_FORWARD")
            def my_forward_binding():
                next_channel()

            @DankoData.player.on_key_press("MBTN_BACK")
            def my_back_binding():
                prev_channel()

            @DankoData.player.on_key_press("WHEEL_UP")
            def my_up_binding():
                my_up_binding_execute()

            @DankoData.player.on_key_press("WHEEL_DOWN")
            def my_down_binding():
                my_down_binding_execute()

            def pause_handler():
                try:
                    if not DankoData.player.pause:
                        DankoGUI.btn_playpause.setIcon(
                            QtGui.QIcon(str(Path(DankoGUI.icons_folder, "pause.png")))
                        )
                        DankoGUI.btn_playpause.setToolTip(_("Pause"))
                    else:
                        DankoGUI.btn_playpause.setIcon(
                            QtGui.QIcon(str(Path(DankoGUI.icons_folder, "play.png")))
                        )
                        DankoGUI.btn_playpause.setToolTip(_("Play"))
                    if DankoData.event_handler:
                        try:
                            DankoData.event_handler.on_playpause()
                        except Exception:
                            pass
                except Exception:
                    pass

            def async_pause_handler(*args, **kwargs):
                execute_in_main_thread(partial(pause_handler))

            DankoData.player.observe_property("pause", async_pause_handler)

            def danko_track_set(track, type1):
                logger.info(f"Set {type1} track to {track}")
                if DankoData.playing_channel not in DankoData.player_tracks:
                    DankoData.player_tracks[DankoData.playing_channel] = {}
                if type1 == "vid":
                    DankoData.player.vid = track
                    DankoData.player_tracks[DankoData.playing_channel]["vid"] = track
                elif type1 == "aid":
                    DankoData.player.aid = track
                    DankoData.player_tracks[DankoData.playing_channel]["aid"] = track
                elif type1 == "sid":
                    DankoData.player.sid = track
                    DankoData.player_tracks[DankoData.playing_channel]["sid"] = track

            init_menubar_player(
                DankoData.player,
                mpv_play,
                mpv_stop,
                prev_channel,
                next_channel,
                mpv_fullscreen,
                showhideeverything,
                main_channel_settings,
                show_settings,
                show_help,
                do_screenshot,
                mpv_mute,
                showhideplaylist,
                lowpanel_ch_1,
                open_stream_info,
                app.quit,
                redraw_menubar,
                QtGui.QIcon(
                    QtGui.QIcon(str(Path(DankoGUI.icons_folder, "circle.png"))).pixmap(
                        8, 8
                    )
                ),
                my_up_binding_execute,
                my_down_binding_execute,
                show_playlist_editor,
                show_playlists,
                show_sort,
                show_exception,
                force_update_epg_act,
                get_keybind,
                show_tvguide_2,
                show_multi_epg,
                reload_playlist,
                show_shortcuts,
                danko_track_set,
                mpv_frame_step,
                mpv_frame_back_step,
            )

            volume_option1 = read_option("volume")
            if volume_option1 is not None:
                logger.info(f"Set volume to {vol_remembered}")
                DankoGUI.volume_slider.setValue(vol_remembered)
                mpv_volume_set()
            else:
                DankoGUI.volume_slider.setValue(100)
                mpv_volume_set()

        def set_label_width(label, width):
            if width > 0:
                label.setFixedWidth(width)

        class MainWindow(QtWidgets.QMainWindow):
            oldpos = None
            oldpos1 = None

            def __init__(self, parent=None):
                super().__init__(parent)
                self.windowWidth = self.width()
                self.windowHeight = self.height()
                self.container = None
                self.listWidget = None
                self.moviesWidget = None
                self.seriesWidget = None
                self.createMenuBar_mw()

                class Container(QtWidgets.QWidget):
                    def mousePressEvent(self, event3):
                        if event3.button() == QtCore.Qt.MouseButton.LeftButton:
                            execute_in_main_thread(partial(my_mouse_left_callback))
                        elif event3.button() == QtCore.Qt.MouseButton.RightButton:
                            execute_in_main_thread(partial(my_mouse_right_callback))
                        elif event3.button() in [
                            QtCore.Qt.MouseButton.BackButton,
                            QtCore.Qt.MouseButton.XButton1,
                            QtCore.Qt.MouseButton.ExtraButton1,
                        ]:
                            prev_channel()
                        elif event3.button() in [
                            QtCore.Qt.MouseButton.ForwardButton,
                            QtCore.Qt.MouseButton.XButton2,
                            QtCore.Qt.MouseButton.ExtraButton2,
                        ]:
                            next_channel()
                        else:
                            super().mousePressEvent(event3)

                    def mouseDoubleClickEvent(self, event3):
                        if event3.button() == QtCore.Qt.MouseButton.LeftButton:
                            mpv_fullscreen()

                    def wheelEvent(self, event3):
                        if event3.angleDelta().y() > 0:
                            my_up_binding_execute()
                        else:
                            my_down_binding_execute()
                        event3.accept()

                # Dankoiptv fix: instanciar la clase Container (con
                # mouseDoubleClickEvent → fullscreen) en vez de un QWidget
                # plano que ignoraba el doble clic sobre el video.
                self.container = Container(self)
                self.setCentralWidget(self.container)
                self.container.setAttribute(
                    QtCore.Qt.WidgetAttribute.WA_DontCreateNativeAncestors
                )
                self.container.setAttribute(QtCore.Qt.WidgetAttribute.WA_NativeWindow)
                self.container.setFocus()
                self.container.setStyleSheet(
                    """
                    background-color: #C0C6CA;
                """
                )

            def resize_rewind(self):
                rewind_normal_offset = 150
                rewind_fullscreen_offset = 180
                if DankoData.settings["panelposition"] == 2:
                    dockWidget_playlist_cur_width = 0
                else:
                    dockWidget_playlist_cur_width = dockWidget_playlist.width()

                if not DankoData.fullscreen:
                    if not dockWidget_controlPanel.isVisible():
                        set_label_width(
                            DankoGUI.rewind,
                            self.windowWidth - dockWidget_playlist_cur_width + 58,
                        )
                        DankoGUI.rewind.move(
                            int(
                                ((self.windowWidth - DankoGUI.rewind.width()) / 2)
                                - (dockWidget_playlist_cur_width / 1.7)
                            ),
                            int(
                                (self.windowHeight - DankoGUI.rewind.height())
                                - rewind_fullscreen_offset
                            ),
                        )
                    else:
                        set_label_width(
                            DankoGUI.rewind,
                            self.windowWidth - dockWidget_playlist_cur_width + 58,
                        )
                        DankoGUI.rewind.move(
                            int(
                                ((self.windowWidth - DankoGUI.rewind.width()) / 2)
                                - (dockWidget_playlist_cur_width / 1.7)
                            ),
                            int(
                                (self.windowHeight - DankoGUI.rewind.height())
                                - dockWidget_controlPanel.height()
                                - rewind_normal_offset
                            ),
                        )
                else:
                    set_label_width(DankoGUI.rewind, DankoGUI.controlpanel_widget.width())
                    rewind_position_x = (
                        DankoGUI.controlpanel_widget.pos().x() - win.pos().x()
                    )
                    if rewind_position_x < 0:
                        rewind_position_x = 0
                    DankoGUI.rewind.move(
                        rewind_position_x,
                        int(
                            (self.windowHeight - DankoGUI.rewind.height())
                            - rewind_fullscreen_offset
                        ),
                    )

            def update(self):
                if DankoData.settings["panelposition"] == 2:
                    dockWidget_playlist_cur_width2 = 0
                else:
                    dockWidget_playlist_cur_width2 = dockWidget_playlist.width()

                self.windowWidth = self.width()
                self.windowHeight = self.height()
                if DankoData.settings["panelposition"] in (0, 2):
                    DankoData.tvguide_lbl.move(2, DankoGUI.tvguide_lbl_offset)
                else:
                    DankoData.tvguide_lbl.move(
                        win.width() - DankoData.tvguide_lbl.width(),
                        DankoGUI.tvguide_lbl_offset,
                    )
                self.resize_rewind()
                if not DankoData.fullscreen:
                    if not dockWidget_controlPanel.isVisible():
                        set_label_width(
                            DankoData.state,
                            self.windowWidth - dockWidget_playlist_cur_width2 + 58,
                        )
                        DankoData.state.move(
                            int(
                                ((self.windowWidth - DankoData.state.width()) / 2)
                                - (dockWidget_playlist_cur_width2 / 1.7)
                            ),
                            int((self.windowHeight - DankoData.state.height()) - 20),
                        )
                        h = 0
                        h2 = 10
                    else:
                        set_label_width(
                            DankoData.state,
                            self.windowWidth - dockWidget_playlist_cur_width2 + 58,
                        )
                        DankoData.state.move(
                            int(
                                ((self.windowWidth - DankoData.state.width()) / 2)
                                - (dockWidget_playlist_cur_width2 / 1.7)
                            ),
                            int(
                                (self.windowHeight - DankoData.state.height())
                                - dockWidget_controlPanel.height()
                                - 10
                            ),
                        )
                        h = dockWidget_controlPanel.height()
                        h2 = 20
                else:
                    set_label_width(DankoData.state, self.windowWidth)
                    DankoData.state.move(
                        int((self.windowWidth - DankoData.state.width()) / 2),
                        int((self.windowHeight - DankoData.state.height()) - 20),
                    )
                    h = 0
                    h2 = 10
                if dockWidget_playlist.isVisible():
                    if DankoData.settings["panelposition"] in (0, 2):
                        DankoGUI.lbl2.move(0, DankoGUI.lbl2_offset)
                    else:
                        DankoGUI.lbl2.move(
                            DankoData.tvguide_lbl.width() + DankoGUI.lbl2.width(),
                            DankoGUI.lbl2_offset,
                        )
                else:
                    DankoGUI.lbl2.move(0, DankoGUI.lbl2_offset)
                if DankoData.state.isVisible():
                    state_h = DankoData.state.height()
                else:
                    state_h = 15
                DankoData.tvguide_lbl.setFixedHeight(
                    (self.windowHeight - state_h - h) - 40 - state_h + h2
                )

            def resizeEvent(self, event):
                try:
                    self.update()
                except Exception:
                    pass
                QtWidgets.QMainWindow.resizeEvent(self, event)

            def closeEvent(self, event1):
                try:
                    DankoData.player.vo = "null"
                except Exception:
                    pass
                if DankoGUI.streaminfo_win.isVisible():
                    DankoGUI.streaminfo_win.hide()
                if DankoData.settings["panelposition"] == 2:
                    dockWidget_playlist.hide()

            def createMenuBar_mw(self):
                self.menu_bar_qt = self.menuBar()
                init_dankoiptv_lib_menubar(self, app, self.menu_bar_qt)

        win = MainWindow()
        win.setMinimumSize(1, 1)
        win.setWindowTitle("Dankoiptv")
        win.setWindowIcon(DankoGUI.main_icon)
        DankoGUI.win = win

        DankoGUI.create3()

        window_data = read_option("window")
        if window_data:
            win.setGeometry(
                window_data["x"], window_data["y"], window_data["w"], window_data["h"]
            )
        else:
            DankoData.needs_resize = True
            win.resize(WINDOW_SIZE[0], WINDOW_SIZE[1])
            move_window_to_center(win)

        def get_curwindow_pos():
            try:
                win_geometry = win.screen().availableGeometry()
            except Exception:
                win_geometry = QtWidgets.QDesktopWidget().screenGeometry(win)
            win_width = win_geometry.width()
            win_height = win_geometry.height()
            logger.debug(f"Screen size: {win_width}x{win_height}")
            return (
                win_width,
                win_height,
            )

        def showLoading2():
            if not DankoGUI.loading2.isVisible():
                DankoGUI.centerwidget(DankoGUI.loading2, 50)
                DankoGUI.loading_movie2.stop()
                DankoGUI.loading_movie2.start()
                DankoGUI.loading2.show()

        def hideLoading2():
            if DankoGUI.loading2.isVisible():
                DankoGUI.loading2.hide()
                DankoGUI.loading_movie2.stop()

        def show_progress(prog):
            if not DankoData.settings["hidetvprogram"] and (
                prog and not DankoData.playing_archive
            ):
                prog_percentage = round(
                    (time.time() - prog["start"])
                    / (prog["stop"] - prog["start"])
                    * 100,
                    2,
                )
                prog_title = prog["title"]
                prog_start = prog["start"]
                prog_stop = prog["stop"]
                prog_start_time = datetime.datetime.fromtimestamp(prog_start).strftime(
                    "%H:%M"
                )
                prog_stop_time = datetime.datetime.fromtimestamp(prog_stop).strftime(
                    "%H:%M"
                )
                DankoGUI.progress.setValue(int(prog_percentage))
                DankoGUI.progress.setFormat(str(prog_percentage) + "% " + prog_title)
                DankoGUI.progress.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
                DankoGUI.start_label.setText(prog_start_time)
                DankoGUI.stop_label.setText(prog_stop_time)
                if not DankoData.fullscreen:
                    DankoGUI.progress.show()
                    DankoGUI.start_label.show()
                    DankoGUI.stop_label.show()
            else:
                DankoGUI.progress.hide()
                DankoGUI.start_label.setText("")
                DankoGUI.start_label.hide()
                DankoGUI.stop_label.setText("")
                DankoGUI.stop_label.hide()

        def set_mpv_title():
            try:
                DankoData.player.title = win.windowTitle()
            except Exception:
                pass

        def setChannelText(channelText, do_channel_set=False):
            chTextStrip = channelText.strip()
            if chTextStrip:
                win.setWindowTitle(f"{chTextStrip} - Dankoiptv")
            else:
                win.setWindowTitle("Dankoiptv")
            execute_in_main_thread(partial(set_mpv_title))
            if not do_channel_set:
                DankoGUI.channel.setText(f"{chr(9654)} {channelText}")
                DankoGUI.channel.show()
            if (
                DankoData.fullscreen
                and chTextStrip
                and not DankoData.dockWidget_playlistVisible
            ):
                DankoData.state.show()
                DankoData.state.setTextDanko(chTextStrip)
                DankoData.time_stop = time.time() + 1

        def idle_on_metadata():
            try:
                DankoData.event_handler.on_metadata()
            except Exception:
                pass

        def set_player_settings(j):
            try:
                logger.info("Waiting for channel load...")
                try:
                    DankoData.player.wait_until_playing()
                except Exception:
                    pass
                if j == DankoData.playing_channel:
                    logger.info(f"Setting player settings for channel: {j}")
                    execute_in_main_thread(partial(idle_on_metadata))
                    if (
                        DankoData.settings["m3u"] in DankoData.channel_sets
                        and j in DankoData.channel_sets[DankoData.settings["m3u"]]
                    ):
                        d = DankoData.channel_sets[DankoData.settings["m3u"]][j]
                        DankoData.player.deinterlace = d["deinterlace"]
                        if "ua" not in d:
                            d["ua"] = ""
                        if "ref" not in d:
                            d["ref"] = ""
                        if "contrast" in d:
                            DankoData.player.contrast = d["contrast"]
                        else:
                            DankoData.player.contrast = 0
                        if "brightness" in d:
                            DankoData.player.brightness = d["brightness"]
                        else:
                            DankoData.player.brightness = 0
                        if "hue" in d:
                            DankoData.player.hue = d["hue"]
                        else:
                            DankoData.player.hue = 0
                        if "saturation" in d:
                            DankoData.player.saturation = d["saturation"]
                        else:
                            DankoData.player.saturation = 0
                        if "gamma" in d:
                            DankoData.player.gamma = d["gamma"]
                        else:
                            DankoData.player.gamma = 0
                        if "videoaspect" in d:
                            setVideoAspect(
                                DankoGUI.videoaspect_vars[
                                    list(DankoGUI.videoaspect_vars)[d["videoaspect"]]
                                ]
                            )
                        else:
                            setVideoAspect(
                                DankoGUI.videoaspect_vars[
                                    DankoGUI.videoaspect_def_choose.itemText(
                                        DankoData.settings["videoaspect"]
                                    )
                                ]
                            )
                        if "zoom" in d:
                            DankoData.player.video_zoom = DankoGUI.zoom_vars[
                                list(DankoGUI.zoom_vars)[d["zoom"]]
                            ]
                        else:
                            DankoData.player.video_zoom = DankoGUI.zoom_vars[
                                DankoGUI.zoom_def_choose.itemText(
                                    DankoData.settings["zoom"]
                                )
                            ]
                        if "panscan" in d:
                            DankoData.player.panscan = d["panscan"]
                        else:
                            DankoData.player.panscan = DankoData.settings["panscan"]
                    else:
                        DankoData.player.deinterlace = DankoData.settings["deinterlace"]
                        setVideoAspect(
                            DankoGUI.videoaspect_vars[
                                DankoGUI.videoaspect_def_choose.itemText(
                                    DankoData.settings["videoaspect"]
                                )
                            ]
                        )
                        DankoData.player.video_zoom = DankoGUI.zoom_vars[
                            DankoGUI.zoom_def_choose.itemText(DankoData.settings["zoom"])
                        ]
                        DankoData.player.panscan = DankoData.settings["panscan"]
                        DankoData.player.gamma = 0
                        DankoData.player.saturation = 0
                        DankoData.player.hue = 0
                        DankoData.player.brightness = 0
                        DankoData.player.contrast = 0
                    if DankoData.player.deinterlace:
                        logger.info("Deinterlace: enabled")
                    else:
                        logger.info("Deinterlace: disabled")
                    logger.info(f"Contrast: {DankoData.player.contrast}")
                    logger.info(f"Brightness: {DankoData.player.brightness}")
                    logger.info(f"Hue: {DankoData.player.hue}")
                    logger.info(f"Saturation: {DankoData.player.saturation}")
                    logger.info(f"Gamma: {DankoData.player.gamma}")
                    logger.info(f"Video aspect: {getVideoAspect()}")
                    logger.info(f"Zoom: {DankoData.player.video_zoom}")
                    logger.info(f"Panscan: {DankoData.player.panscan}")

                    if DankoData.playing_channel in DankoData.player_tracks:
                        last_track = DankoData.player_tracks[DankoData.playing_channel]
                        if "vid" in last_track:
                            logger.info(
                                f"Restoring last video track: '{last_track['vid']}'"
                            )
                            DankoData.player.vid = last_track["vid"]
                        else:
                            DankoData.player.vid = "auto"
                        if "aid" in last_track:
                            logger.info(
                                f"Restoring last audio track: '{last_track['aid']}'"
                            )
                            DankoData.player.aid = last_track["aid"]
                        else:
                            DankoData.player.aid = "auto"
                        if "sid" in last_track:
                            logger.info(
                                f"Restoring last sub track: '{last_track['sid']}'"
                            )
                            DankoData.player.sid = last_track["sid"]
                        else:
                            DankoData.player.sid = "auto"
                    else:
                        DankoData.player.vid = "auto"
                        DankoData.player.aid = "auto"
                        DankoData.player.sid = "auto"
                    execute_in_main_thread(partial(file_loaded_callback))
            except Exception:
                pass

        def itemClicked_event(item, custom_url="", archived=False, is_rewind=False):
            is_ic_ok = True
            try:
                is_ic_ok = item.text() != _("Nothing found")
            except Exception:
                pass
            if is_ic_ok:
                DankoData.playing_archive = archived
                if not archived:
                    DankoData.archive_epg = None
                    DankoGUI.rewind_slider.setValue(100)
                    DankoData.rewind_value = DankoGUI.rewind_slider.value()
                else:
                    if not is_rewind:
                        DankoGUI.rewind_slider.setValue(0)
                        DankoData.rewind_value = DankoGUI.rewind_slider.value()
                try:
                    j = item.data(QtCore.Qt.ItemDataRole.UserRole)
                except Exception:
                    j = item
                if not j:
                    return
                DankoData.playing_channel = j
                DankoData.playing_group = playmode_selector.currentIndex()
                DankoData.item_selected = j
                array_item = None
                try:
                    array_item = getArrayItem(j)
                    play_url = array_item["url"]
                except Exception:
                    play_url = custom_url
                if archived:
                    play_url = custom_url
                MAX_CHAN_SIZE = 35
                channel_name = j
                if len(channel_name) > MAX_CHAN_SIZE:
                    channel_name = channel_name[: MAX_CHAN_SIZE - 3] + "..."
                setChannelText("  " + channel_name)
                current_prog = None
                if get_epg_url() and array_item:
                    epg_id = get_epg_id(array_item)
                    if epg_id:
                        programme = get_current_programme(epg_id)
                        if programme:
                            current_prog = programme
                DankoData.current_prog1 = current_prog
                show_progress(current_prog)
                if DankoGUI.start_label.isVisible():
                    dockWidget_controlPanel.setFixedHeight(
                        DOCKWIDGET_CONTROLPANEL_HEIGHT_HIGH
                    )
                else:
                    dockWidget_controlPanel.setFixedHeight(
                        DOCKWIDGET_CONTROLPANEL_HEIGHT_LOW
                    )
                inhibit()
                DankoData.playing = True
                win.update()
                DankoData.playing_url = play_url
                execute_in_main_thread(partial(set_url_text))
                ua_choose = default_user_agent
                if (
                    DankoData.settings["m3u"] in DankoData.channel_sets
                    and j in DankoData.channel_sets[DankoData.settings["m3u"]]
                ):
                    ua_choose = DankoData.channel_sets[DankoData.settings["m3u"]][j]["ua"]
                if not custom_url:
                    doPlay(play_url, ua_choose, j)
                else:
                    doPlay(custom_url, ua_choose, j)
                execute_in_main_thread(partial(redraw_channels))

        def itemSelected_event(item):
            try:
                n_1 = item.data(QtCore.Qt.ItemDataRole.UserRole)
                DankoData.item_selected = n_1
                update_tvguide(n_1)
            except Exception:
                pass

        def mpv_play():
            DankoData.player.pause = not DankoData.player.pause

        def mpv_stop():
            DankoData.playing_channel = ""
            DankoData.playing_group = -1
            DankoData.playing_url = ""
            execute_in_main_thread(partial(set_url_text))
            hideLoading()
            setChannelText("")
            uninhibit()
            DankoData.playing = False
            stopPlayer()
            DankoData.player.loop = True
            DankoData.player.deinterlace = False
            mpv_override_play(str(Path(DankoGUI.icons_folder, "main.png")))
            DankoData.player.pause = True
            DankoGUI.channel.setText("")
            DankoGUI.channel.hide()
            DankoGUI.progress.hide()
            DankoGUI.start_label.hide()
            DankoGUI.stop_label.hide()
            DankoGUI.start_label.setText("")
            DankoGUI.stop_label.setText("")
            dockWidget_controlPanel.setFixedHeight(DOCKWIDGET_CONTROLPANEL_HEIGHT_LOW)
            win.update()
            execute_in_main_thread(partial(redraw_channels))
            redraw_menubar()

        def esc_handler():
            if DankoData.fullscreen:
                mpv_fullscreen()

        DankoData.currentWidthHeight = [
            win.geometry().x(),
            win.geometry().y(),
            win.width(),
            win.height(),
        ]
        DankoData.currentMaximized = win.isMaximized()

        def idle_mpv_fullscreen():
            if not DankoData.fullscreen:
                # Entering fullscreen
                if not DankoData.fullscreen_locked:
                    DankoData.fullscreen_locked = True
                    rewind_layout_offset = 10
                    DankoGUI.rewind_layout.setContentsMargins(
                        rewind_layout_offset, 0, rewind_layout_offset - 50, 0
                    )
                    DankoData.isControlPanelVisible = dockWidget_controlPanel.isVisible()
                    DankoData.isPlaylistVisible = dockWidget_playlist.isVisible()
                    setShortcutState(True)
                    DankoData.currentWidthHeight = [
                        win.geometry().x(),
                        win.geometry().y(),
                        win.width(),
                        win.height(),
                    ]
                    DankoData.currentMaximized = win.isMaximized()
                    DankoGUI.channelfilter.usePopup = False
                    win.menu_bar_qt.hide()
                    DankoData.fullscreen = True
                    dockWidget_playlist.hide()
                    DankoGUI.label_video_data.hide()
                    DankoGUI.label_avsync.hide()
                    for lbl3 in DankoGUI.controlpanel_btns:
                        if lbl3 not in DankoGUI.show_lbls_fullscreen:
                            lbl3.hide()
                    DankoGUI.progress.hide()
                    DankoGUI.start_label.hide()
                    DankoGUI.stop_label.hide()
                    dockWidget_controlPanel.hide()
                    dockWidget_controlPanel.setFixedHeight(
                        DOCKWIDGET_CONTROLPANEL_HEIGHT_LOW
                    )
                    win.update()
                    win.raise_()
                    win.setFocus(QtCore.Qt.FocusReason.PopupFocusReason)
                    win.activateWindow()
                    win.showFullScreen()
                    if DankoData.settings["panelposition"] == 1:
                        tvguide_close_lbl.move(
                            get_curwindow_pos()[0] - DankoData.tvguide_lbl.width() - 40,
                            DankoGUI.tvguide_lbl_offset,
                        )
                    DankoGUI.centerwidget(DankoGUI.loading1)
                    DankoGUI.centerwidget(DankoGUI.loading2, 50)
                    DankoData.fullscreen_locked = False
            else:
                # Leaving fullscreen
                if not DankoData.fullscreen_locked:
                    DankoData.fullscreen_locked = True
                    DankoGUI.rewind_layout.setContentsMargins(100, 0, 50, 0)
                    setShortcutState(False)
                    if DankoData.state.isVisible() and DankoData.state.text().startswith(
                        _("Volume")
                    ):
                        DankoData.state.hide()
                    win.menu_bar_qt.show()
                    hide_playlist_fullscreen()
                    hide_controlpanel_fullscreen()
                    dockWidget_playlist.setWindowOpacity(1)
                    dockWidget_playlist.hide()
                    dockWidget_controlPanel.setWindowOpacity(1)
                    dockWidget_controlPanel.hide()
                    DankoData.fullscreen = False
                    if DankoData.state.text().endswith(
                        "{} F".format(_("To exit fullscreen mode press"))
                    ):
                        DankoData.state.setTextDanko("")
                        if not DankoData.gl_is_static:
                            DankoData.state.hide()
                            win.update()
                    if (
                        not DankoData.player.pause
                        and DankoData.playing
                        and DankoGUI.start_label.text()
                    ):
                        DankoGUI.progress.show()
                        DankoGUI.start_label.show()
                        DankoGUI.stop_label.show()
                        dockWidget_controlPanel.setFixedHeight(
                            DOCKWIDGET_CONTROLPANEL_HEIGHT_HIGH
                        )
                    DankoGUI.label_video_data.show()
                    DankoGUI.label_avsync.show()
                    for lbl3 in DankoGUI.controlpanel_btns:
                        if lbl3 not in DankoGUI.show_lbls_fullscreen:
                            lbl3.show()
                    dockWidget_controlPanel.show()
                    dockWidget_playlist.show()
                    win.update()
                    if not DankoData.currentMaximized:
                        win.showNormal()
                    else:
                        win.showMaximized()
                    win.setGeometry(
                        DankoData.currentWidthHeight[0],
                        DankoData.currentWidthHeight[1],
                        DankoData.currentWidthHeight[2],
                        DankoData.currentWidthHeight[3],
                    )
                    if not DankoData.isPlaylistVisible:
                        show_hide_playlist()
                    if DankoData.settings["panelposition"] == 1:
                        tvguide_close_lbl.move(
                            win.width() - DankoData.tvguide_lbl.width() - 40,
                            DankoGUI.tvguide_lbl_offset,
                        )
                    DankoGUI.centerwidget(DankoGUI.loading1)
                    DankoGUI.centerwidget(DankoGUI.loading2, 50)
                    if DankoData.isControlPanelVisible:
                        dockWidget_controlPanel.show()
                    else:
                        dockWidget_controlPanel.hide()
                    if DankoData.compact_mode:
                        win.menu_bar_qt.hide()
                        setShortcutState(True)
                    dockWidget_playlist.lower()
                    DankoData.fullscreen_locked = False
            try:
                DankoData.event_handler.on_fullscreen()
            except Exception:
                pass

        def mpv_fullscreen():
            execute_in_main_thread(partial(idle_mpv_fullscreen))

        def is_show_volume():
            showdata = DankoData.fullscreen
            if not DankoData.fullscreen and win.isVisible():
                showdata = not dockWidget_controlPanel.isVisible()
            return showdata and not DankoGUI.controlpanel_widget.isVisible()

        def show_volume(v1):
            if is_show_volume():
                DankoData.state.show()
                if isinstance(v1, str):
                    DankoData.state.setTextDanko(v1)
                else:
                    DankoData.state.setTextDanko("{}: {}%".format(_("Volume"), int(v1)))

        def mpv_mute():
            DankoData.time_stop = time.time() + 3
            if DankoData.player.mute:
                if DankoData.old_value > 50:
                    DankoGUI.btn_volume.setIcon(
                        QtGui.QIcon(str(Path(DankoGUI.icons_folder, "volume.png")))
                    )
                else:
                    DankoGUI.btn_volume.setIcon(
                        QtGui.QIcon(str(Path(DankoGUI.icons_folder, "volume-low.png")))
                    )
                mpv_override_mute(False)
                DankoGUI.volume_slider.setValue(DankoData.old_value)
                show_volume(DankoData.old_value)
            else:
                DankoGUI.btn_volume.setIcon(
                    QtGui.QIcon(str(Path(DankoGUI.icons_folder, "mute.png")))
                )
                mpv_override_mute(True)
                DankoData.old_value = DankoGUI.volume_slider.value()
                DankoGUI.volume_slider.setValue(0)
                show_volume(_("Volume off"))

        def mpv_volume_set():
            DankoData.time_stop = time.time() + 3
            vol = int(DankoGUI.volume_slider.value())
            try:
                if vol == 0:
                    show_volume(_("Volume off"))
                else:
                    show_volume(vol)
            except NameError:
                pass
            mpv_override_volume(vol)
            if vol == 0:
                mpv_override_mute(True)
                DankoGUI.btn_volume.setIcon(
                    QtGui.QIcon(str(Path(DankoGUI.icons_folder, "mute.png")))
                )
            else:
                mpv_override_mute(False)
                if vol > 50:
                    DankoGUI.btn_volume.setIcon(
                        QtGui.QIcon(str(Path(DankoGUI.icons_folder, "volume.png")))
                    )
                else:
                    DankoGUI.btn_volume.setIcon(
                        QtGui.QIcon(str(Path(DankoGUI.icons_folder, "volume-low.png")))
                    )

        class PlaylistDockWidget(QtWidgets.QDockWidget):
            def enterEvent(self, event4):
                DankoData.check_playlist_visible = True

            def leaveEvent(self, event4):
                DankoData.check_playlist_visible = False

        dockWidget_playlist = PlaylistDockWidget(win)

        win.listWidget = QtWidgets.QListWidget()
        win.moviesWidget = QtWidgets.QListWidget()
        win.seriesWidget = QtWidgets.QListWidget()

        def tvguide_close_lbl_func(*args, **kwargs):
            hide_tvguide()

        DankoData.tvguide_lbl = DankoGUI.ScrollableLabel(win)
        DankoData.tvguide_lbl.move(0, DankoGUI.tvguide_lbl_offset)
        DankoData.tvguide_lbl.setFixedWidth(TVGUIDE_WIDTH)
        DankoData.tvguide_lbl.hide()

        DankoGUI.set_widget_opacity(DankoData.tvguide_lbl, DankoGUI.DEFAULT_OPACITY)

        class ClickableLabel(QtWidgets.QLabel):
            def __init__(self, whenClicked, win, parent=None):
                QtWidgets.QLabel.__init__(self, win)
                self._whenClicked = whenClicked

            def mouseReleaseEvent(self, event):
                self._whenClicked(event)

        tvguide_close_lbl = ClickableLabel(tvguide_close_lbl_func, win)
        tvguide_close_lbl.setPixmap(
            QtGui.QIcon(str(Path(DankoGUI.icons_folder, "close.png"))).pixmap(32, 32)
        )
        tvguide_close_lbl.setStyleSheet(
            "background-color: {};".format(
                "black" if DankoData.use_dark_icon_theme else "white"
            )
        )
        tvguide_close_lbl.resize(32, 32)
        if DankoData.settings["panelposition"] in (0, 2):
            tvguide_close_lbl.move(
                DankoData.tvguide_lbl.width() + 5, DankoGUI.tvguide_lbl_offset
            )
        else:
            tvguide_close_lbl.move(
                win.width() - DankoData.tvguide_lbl.width() - 40,
                DankoGUI.tvguide_lbl_offset,
            )
            DankoGUI.lbl2.move(
                DankoData.tvguide_lbl.width() + DankoGUI.lbl2.width(), DankoGUI.lbl2_offset
            )
        tvguide_close_lbl.hide()

        DankoGUI.set_widget_opacity(tvguide_close_lbl, DankoGUI.DEFAULT_OPACITY)

        DankoData.current_group = _("All channels")

        DankoData.mp_manager_dict["logos_inprogress"] = False
        DankoData.mp_manager_dict["logos_completed"] = False
        DankoData.mp_manager_dict["logosmovie_inprogress"] = False
        DankoData.mp_manager_dict["logosmovie_completed"] = False
        logos_cache = {}

        def get_pixmap_from_filename(pixmap_filename):
            if pixmap_filename in logos_cache:
                return logos_cache[pixmap_filename]
            else:
                try:
                    if os.path.isfile(pixmap_filename):
                        icon_pixmap = QtGui.QIcon(pixmap_filename).pixmap(
                            QtCore.QSize(32, 32)
                        )
                        if icon_pixmap.isNull():
                            raise Exception("icon_pixmap is null")
                        if not icon_pixmap.height():
                            raise Exception("icon_pixmap height is 0")
                        logos_cache[pixmap_filename] = icon_pixmap
                        icon_pixmap = None
                        return logos_cache[pixmap_filename]
                    else:
                        if pixmap_filename:
                            DankoData.broken_logos.add(pixmap_filename)
                        return None
                except Exception:
                    if pixmap_filename:
                        DankoData.broken_logos.add(pixmap_filename)
                    return None

        def timer_logos_update():
            try:
                if not DankoData.timer_logos_update_lock:
                    DankoData.timer_logos_update_lock = True
                    if DankoData.mp_manager_dict["logos_completed"]:
                        DankoData.mp_manager_dict["logos_completed"] = False
                        execute_in_main_thread(partial(redraw_channels))
                    if DankoData.mp_manager_dict["logosmovie_completed"]:
                        DankoData.mp_manager_dict["logosmovie_completed"] = False
                        update_movie_icons()
                    DankoData.timer_logos_update_lock = False
            except Exception:
                pass

        all_channels_lang = _("All channels")
        favourites_lang = _("Favourites")

        def get_page_count(array_len):
            return max(1, math.ceil(array_len / 100))

        max_width = win.listWidget.sizeHint().width()

        def generate_channels():
            channel_logos_request = {}

            try:
                idx = (DankoGUI.page_box.value() - 1) * 100
            except Exception:
                idx = 0

            # Group and favourites filter
            array_filtered = []
            for j1 in DankoData.array_sorted:
                group1 = DankoData.array[j1]["tvg-group"]
                if DankoData.current_group != all_channels_lang:
                    if DankoData.current_group == favourites_lang:
                        if j1 not in DankoData.favourite_sets:
                            continue
                    else:
                        if group1 != DankoData.current_group:
                            continue
                array_filtered.append(j1)

            ch_array = [
                x13
                for x13 in array_filtered
                if DankoData.search.lower().strip() in x13.lower().strip()
            ]
            ch_array = ch_array[idx : idx + 100]
            try:
                if DankoData.search:
                    DankoGUI.page_box.setMaximum(get_page_count(len(ch_array)))
                    DankoGUI.of_lbl.setText(f"/ {get_page_count(len(ch_array))}")
                else:
                    DankoGUI.page_box.setMaximum(get_page_count(len(array_filtered)))
                    DankoGUI.of_lbl.setText(f"/ {get_page_count(len(array_filtered))}")
            except Exception:
                pass
            res = {}
            k0 = -1
            k = 0
            for i in ch_array:
                k0 += 1
                k += 1
                prog = ""
                orig_category = ""
                orig_desc = ""
                prog_desc = ""

                epg_id = get_epg_id(DankoData.array[i])
                epg_found = False

                if epg_id:
                    current_prog = get_current_programme(epg_id)
                    if current_prog and current_prog["start"] != 0:
                        epg_found = True
                        start_time = datetime.datetime.fromtimestamp(
                            current_prog["start"]
                        ).strftime("%H:%M")
                        stop_time = datetime.datetime.fromtimestamp(
                            current_prog["stop"]
                        ).strftime("%H:%M")
                        t_t = time.time()
                        percentage = round(
                            (t_t - current_prog["start"])
                            / (current_prog["stop"] - current_prog["start"])
                            * 100,
                            2,
                        )
                        if DankoData.settings["hideepgpercentage"]:
                            prog = current_prog["title"]
                        else:
                            prog = str(percentage) + "% " + current_prog["title"]
                        try:
                            if current_prog["desc"]:
                                orig_desc = current_prog["desc"]
                                prog_desc = "\n\n" + textwrap.fill(
                                    current_prog["desc"], 100
                                )
                            else:
                                orig_desc = ""
                                prog_desc = ""
                        except Exception:
                            orig_desc = ""
                            prog_desc = ""
                        try:
                            if current_prog["category"]:
                                orig_category = current_prog["category"]
                        except Exception:
                            orig_category = ""
                    else:
                        start_time = ""
                        stop_time = ""
                        t_t = time.time()
                        percentage = 0
                        prog = ""
                        orig_desc = ""
                        prog_desc = ""
                        orig_category = ""
                MyPlaylistWidget = DankoGUI.PlaylistWidget(DankoGUI)
                channel_name = i

                original_channel_name = channel_name

                if DankoData.settings["channellogos"] != 3:
                    try:
                        channel_logo1 = ""
                        if "tvg-logo" in DankoData.array[i]:
                            channel_logo1 = DankoData.array[i]["tvg-logo"]

                        epg_logo1 = ""
                        if epg_id:
                            epg_icon = get_epg_icon(epg_id)
                            if epg_icon:
                                epg_logo1 = epg_icon

                        req_data_ua, req_data_ref = get_ua_ref_for_channel(
                            original_channel_name
                        )
                        channel_logos_request[DankoData.array[i]["title"]] = [
                            channel_logo1,
                            epg_logo1,
                            req_data_ua,
                            req_data_ref,
                        ]
                    except Exception:
                        logger.warning(f"Exception in channel logos (channel '{i}')")
                        logger.warning(traceback.format_exc())

                unicode_play_symbol = chr(9654) + " "
                append_symbol = ""
                if DankoData.playing_channel == channel_name:
                    append_symbol = unicode_play_symbol
                MyPlaylistWidget.name_label.setText(
                    append_symbol + str(k) + ". " + channel_name
                )
                orig_prog = prog
                try:
                    tooltip_group = "{}: {}".format(
                        _("Group"), DankoData.array[i]["tvg-group"]
                    )
                except Exception:
                    tooltip_group = "{}: {}".format(_("Group"), _("All channels"))
                if (
                    epg_found
                    and orig_prog
                    and not DankoData.settings["hideepgfromplaylist"]
                ):
                    desc1 = ""
                    wrap_desc = 40
                    if orig_desc:
                        if DankoData.settings["description_view"] == 0:
                            desc_wrapped = textwrap.fill(
                                (f"({orig_category}) " if orig_category else "")
                                + orig_desc,
                                wrap_desc,
                            ).split("\n")
                            if len(desc_wrapped) > 2:
                                desc_wrapped = desc_wrapped[:2]
                                desc_wrapped[1] = desc_wrapped[1][:-3] + "..."
                            desc_wrapped = "<br>".join(desc_wrapped)
                            desc1 = "<br>" + desc_wrapped
                        elif DankoData.settings["description_view"] == 1:
                            desc1 = "<br>" + "<br>".join(
                                textwrap.fill(
                                    (
                                        (f"({orig_category}) " if orig_category else "")
                                        + orig_desc
                                    ),
                                    wrap_desc,
                                ).split("\n")
                            )
                    MyPlaylistWidget.setDescription(
                        "<i>" + prog + "</i>" + desc1,
                        (
                            f"<b>{i}</b>" + f"<br>{tooltip_group}<br><br>"
                            "<i>" + orig_prog + "</i>" + prog_desc
                        ).replace("\n", "<br>"),
                    )
                    MyPlaylistWidget.showDescription()
                    try:
                        if start_time:
                            MyPlaylistWidget.progress_label.setText(start_time)
                            MyPlaylistWidget.end_label.setText(stop_time)
                            MyPlaylistWidget.progress_bar.setValue(int(percentage))
                        else:
                            MyPlaylistWidget.progress_bar.hide()
                    except Exception:
                        logger.warning("Async EPG load problem, ignoring")
                else:
                    MyPlaylistWidget.setDescription(
                        "", f"<b>{i}</b><br>{tooltip_group}"
                    )
                    MyPlaylistWidget.progress_bar.hide()
                    MyPlaylistWidget.hideDescription()

                MyPlaylistWidget.setPixmap(DankoGUI.tv_icon)

                if DankoData.settings["channellogos"] != 3:  # Do not load any logos
                    try:
                        if (
                            f"LOGO:::{original_channel_name}"
                            in DankoData.mp_manager_dict
                        ):
                            if DankoData.settings["channellogos"] == 0:  # Prefer M3U
                                first_loaded = False
                                if DankoData.mp_manager_dict[
                                    f"LOGO:::{original_channel_name}"
                                ][0]:
                                    channel_logo = get_pixmap_from_filename(
                                        DankoData.mp_manager_dict[
                                            f"LOGO:::{original_channel_name}"
                                        ][0]
                                    )
                                    if channel_logo:
                                        first_loaded = True
                                        MyPlaylistWidget.setPixmap(channel_logo)
                                if not first_loaded:
                                    channel_logo = get_pixmap_from_filename(
                                        DankoData.mp_manager_dict[
                                            f"LOGO:::{original_channel_name}"
                                        ][1]
                                    )
                                    if channel_logo:
                                        MyPlaylistWidget.setPixmap(channel_logo)
                            elif DankoData.settings["channellogos"] == 1:  # Prefer EPG
                                first_loaded = False
                                if DankoData.mp_manager_dict[
                                    f"LOGO:::{original_channel_name}"
                                ][1]:
                                    channel_logo = get_pixmap_from_filename(
                                        DankoData.mp_manager_dict[
                                            f"LOGO:::{original_channel_name}"
                                        ][1]
                                    )
                                    if channel_logo:
                                        first_loaded = True
                                        MyPlaylistWidget.setPixmap(channel_logo)
                                if not first_loaded:
                                    channel_logo = get_pixmap_from_filename(
                                        DankoData.mp_manager_dict[
                                            f"LOGO:::{original_channel_name}"
                                        ][0]
                                    )
                                    if channel_logo:
                                        MyPlaylistWidget.setPixmap(channel_logo)
                            elif (
                                DankoData.settings["channellogos"] == 2
                            ):  # Do not load from EPG (only M3U)
                                if DankoData.mp_manager_dict[
                                    f"LOGO:::{original_channel_name}"
                                ][0]:
                                    channel_logo = get_pixmap_from_filename(
                                        DankoData.mp_manager_dict[
                                            f"LOGO:::{original_channel_name}"
                                        ][0]
                                    )
                                    if channel_logo:
                                        MyPlaylistWidget.setPixmap(channel_logo)
                    except Exception:
                        logger.warning("Set channel logos failed with exception")
                        logger.warning(traceback.format_exc())

                myQListWidgetItem = QtWidgets.QListWidgetItem()
                myQListWidgetItem.setData(QtCore.Qt.ItemDataRole.UserRole, i)
                myQListWidgetItem.setSizeHint(
                    QtCore.QSize(
                        win.listWidget.sizeHint().width(),
                        MyPlaylistWidget.sizeHint().height(),
                    )
                )
                res[k0] = [myQListWidgetItem, MyPlaylistWidget, k0, i]
            j1 = DankoData.playing_channel
            if j1:
                current_programme = None
                epg_id = get_epg_id(j1)
                if epg_id:
                    programme = get_current_programme(epg_id)
                    if programme:
                        current_programme = programme
                show_progress(current_programme)

            # Fetch channel logos
            try:
                if DankoData.settings["channellogos"] != 3:
                    if channel_logos_request != DankoData.channel_logos_request_old:
                        DankoData.channel_logos_request_old = channel_logos_request
                        logger.debug("Channel logos request")
                        if (
                            DankoData.channel_logos_process
                            and DankoData.channel_logos_process.is_alive()
                        ):
                            # logger.debug(
                            #     "Old channel logos request found, stopping it"
                            # )
                            DankoData.channel_logos_process.kill()
                        DankoData.channel_logos_process = get_context("spawn").Process(
                            name="[dankoiptv] channel_logos_worker",
                            target=channel_logos_worker,
                            daemon=True,
                            args=(
                                channel_logos_request,
                                DankoData.mp_manager_dict,
                            ),
                        )
                        DankoData.channel_logos_process.start()
            except Exception:
                logger.warning("Fetch channel logos failed with exception:")
                logger.warning(traceback.format_exc())

            return res

        def destroy_listwidget_items(listwidget):
            try:
                for x in range(listwidget.count()):
                    try:
                        listwidget.itemWidget(listwidget.item(x)).destroy()
                    except Exception:
                        pass
            except Exception:
                pass

        def redraw_channels():
            DankoData.row0 = win.listWidget.currentRow()
            val0 = win.listWidget.verticalScrollBar().value()
            win.listWidget.clear()
            channels_1 = generate_channels()
            update_tvguide()
            if channels_1:
                for channel_1 in channels_1.values():
                    channel_3 = channel_1
                    win.listWidget.addItem(channel_3[0])
                    win.listWidget.setItemWidget(channel_3[0], channel_3[1])
            else:
                win.listWidget.addItem(_("Nothing found"))
            win.listWidget.setCurrentRow(DankoData.row0)
            win.listWidget.verticalScrollBar().setValue(val0)

        def group_change(self):
            DankoData.comboboxIndex = DankoData.combobox.currentIndex()
            DankoData.current_group = groups[self]
            if not DankoData.first_change:
                DankoData.first_change = True
            else:
                execute_in_main_thread(partial(redraw_channels))

        def playmode_change(self=False):
            DankoData.playmodeIndex = playmode_selector.currentIndex()
            if not DankoData.first_playmode_change:
                DankoData.first_playmode_change = True
            else:
                tv_widgets = [DankoData.combobox, win.listWidget, DankoGUI.widget4]
                movies_widgets = [movies_combobox, win.moviesWidget]
                series_widgets = [win.seriesWidget]
                # Clear search text when play mode is changed
                # (TV channels, movies, series)
                try:
                    DankoGUI.channelfilter.setText("")
                    DankoGUI.channelfiltersearch.click()
                except Exception:
                    pass
                if playmode_selector.currentIndex() == 0:
                    # TV channels
                    for lbl5 in movies_widgets:
                        lbl5.hide()
                    for lbl6 in series_widgets:
                        lbl6.hide()
                    for lbl4 in tv_widgets:
                        lbl4.show()
                    try:
                        DankoGUI.channelfilter.setPlaceholderText(_("Search channel"))
                    except Exception:
                        pass
                if playmode_selector.currentIndex() == 1:
                    # Movies
                    for lbl4 in tv_widgets:
                        lbl4.hide()
                    for lbl6 in series_widgets:
                        lbl6.hide()
                    for lbl5 in movies_widgets:
                        lbl5.show()
                    try:
                        DankoGUI.channelfilter.setPlaceholderText(_("Search movie"))
                    except Exception:
                        pass
                if playmode_selector.currentIndex() == 2:
                    # Series
                    for lbl4 in tv_widgets:
                        lbl4.hide()
                    for lbl5 in movies_widgets:
                        lbl5.hide()
                    for lbl6 in series_widgets:
                        lbl6.show()
                    try:
                        DankoGUI.channelfilter.setPlaceholderText(_("Search series"))
                    except Exception:
                        pass

        channels = generate_channels()
        for channel in channels:
            win.listWidget.addItem(channels[channel][0])
            win.listWidget.setItemWidget(channels[channel][0], channels[channel][1])

        def sort_upbtn_clicked():
            curIndex = DankoGUI.sort_list.currentRow()
            if curIndex != -1 and curIndex > 0:
                curItem = DankoGUI.sort_list.takeItem(curIndex)
                DankoGUI.sort_list.insertItem(curIndex - 1, curItem)
                DankoGUI.sort_list.setCurrentRow(curIndex - 1)

        def sort_downbtn_clicked():
            curIndex1 = DankoGUI.sort_list.currentRow()
            if curIndex1 != -1 and curIndex1 < DankoGUI.sort_list.count() - 1:
                curItem1 = DankoGUI.sort_list.takeItem(curIndex1)
                DankoGUI.sort_list.insertItem(curIndex1 + 1, curItem1)
                DankoGUI.sort_list.setCurrentRow(curIndex1 + 1)

        DankoGUI.create_sort_widgets2()

        DankoGUI.sort_upbtn.clicked.connect(sort_upbtn_clicked)
        DankoGUI.sort_downbtn.clicked.connect(sort_downbtn_clicked)

        def tvguide_context_menu():
            update_tvguide()
            DankoData.tvguide_lbl.show()
            tvguide_close_lbl.show()

        def settings_context_menu():
            if DankoGUI.channels_win.isVisible():
                DankoGUI.channels_win.close()
            DankoGUI.title.setText(str(DankoData.item_selected))
            if (
                DankoData.settings["m3u"] in DankoData.channel_sets
                and DankoData.item_selected
                in DankoData.channel_sets[DankoData.settings["m3u"]]
            ):
                DankoGUI.deinterlace_chk.setChecked(
                    DankoData.channel_sets[DankoData.settings["m3u"]][
                        DankoData.item_selected
                    ]["deinterlace"]
                )
                try:
                    DankoGUI.useragent_choose.setText(
                        DankoData.channel_sets[DankoData.settings["m3u"]][
                            DankoData.item_selected
                        ]["ua"]
                    )
                except Exception:
                    DankoGUI.useragent_choose.setText("")
                try:
                    DankoGUI.referer_choose_custom.setText(
                        DankoData.channel_sets[DankoData.settings["m3u"]][
                            DankoData.item_selected
                        ]["ref"]
                    )
                except Exception:
                    DankoGUI.referer_choose_custom.setText("")
                try:
                    DankoGUI.group_text.setText(
                        DankoData.channel_sets[DankoData.settings["m3u"]][
                            DankoData.item_selected
                        ]["group"]
                    )
                except Exception:
                    DankoGUI.group_text.setText("")
                try:
                    DankoGUI.hidden_chk.setChecked(
                        DankoData.channel_sets[DankoData.settings["m3u"]][
                            DankoData.item_selected
                        ]["hidden"]
                    )
                except Exception:
                    DankoGUI.hidden_chk.setChecked(False)
                try:
                    DankoGUI.contrast_choose.setValue(
                        DankoData.channel_sets[DankoData.settings["m3u"]][
                            DankoData.item_selected
                        ]["contrast"]
                    )
                except Exception:
                    DankoGUI.contrast_choose.setValue(0)
                try:
                    DankoGUI.brightness_choose.setValue(
                        DankoData.channel_sets[DankoData.settings["m3u"]][
                            DankoData.item_selected
                        ]["brightness"]
                    )
                except Exception:
                    DankoGUI.brightness_choose.setValue(0)
                try:
                    DankoGUI.hue_choose.setValue(
                        DankoData.channel_sets[DankoData.settings["m3u"]][
                            DankoData.item_selected
                        ]["hue"]
                    )
                except Exception:
                    DankoGUI.hue_choose.setValue(0)
                try:
                    DankoGUI.saturation_choose.setValue(
                        DankoData.channel_sets[DankoData.settings["m3u"]][
                            DankoData.item_selected
                        ]["saturation"]
                    )
                except Exception:
                    DankoGUI.saturation_choose.setValue(0)
                try:
                    DankoGUI.gamma_choose.setValue(
                        DankoData.channel_sets[DankoData.settings["m3u"]][
                            DankoData.item_selected
                        ]["gamma"]
                    )
                except Exception:
                    DankoGUI.gamma_choose.setValue(0)
                try:
                    DankoGUI.videoaspect_choose.setCurrentIndex(
                        DankoData.channel_sets[DankoData.settings["m3u"]][
                            DankoData.item_selected
                        ]["videoaspect"]
                    )
                except Exception:
                    DankoGUI.videoaspect_choose.setCurrentIndex(0)
                try:
                    DankoGUI.zoom_choose.setCurrentIndex(
                        DankoData.channel_sets[DankoData.settings["m3u"]][
                            DankoData.item_selected
                        ]["zoom"]
                    )
                except Exception:
                    DankoGUI.zoom_choose.setCurrentIndex(0)
                try:
                    DankoGUI.panscan_choose.setValue(
                        DankoData.channel_sets[DankoData.settings["m3u"]][
                            DankoData.item_selected
                        ]["panscan"]
                    )
                except Exception:
                    DankoGUI.panscan_choose.setValue(0)
                try:
                    epgname_saved = DankoData.channel_sets[DankoData.settings["m3u"]][
                        DankoData.item_selected
                    ]["epgname"]
                    if not epgname_saved:
                        epgname_saved = _("Default")
                    DankoGUI.epgname_lbl.setText(epgname_saved)
                except Exception:
                    DankoGUI.epgname_lbl.setText(_("Default"))
            else:
                DankoGUI.deinterlace_chk.setChecked(DankoData.settings["deinterlace"])
                DankoGUI.hidden_chk.setChecked(False)
                DankoGUI.contrast_choose.setValue(0)
                DankoGUI.brightness_choose.setValue(0)
                DankoGUI.hue_choose.setValue(0)
                DankoGUI.saturation_choose.setValue(0)
                DankoGUI.gamma_choose.setValue(0)
                DankoGUI.videoaspect_choose.setCurrentIndex(0)
                DankoGUI.zoom_choose.setCurrentIndex(0)
                DankoGUI.panscan_choose.setValue(0)
                DankoGUI.useragent_choose.setText("")
                DankoGUI.referer_choose_custom.setText("")
                DankoGUI.group_text.setText("")
                DankoGUI.epgname_lbl.setText(_("Default"))
            move_window_to_center(DankoGUI.channels_win)
            DankoGUI.channels_win.show()

        def tvguide_favourites_add():
            if DankoData.item_selected in DankoData.favourite_sets:
                isdelete_fav_msg = QtWidgets.QMessageBox.question(
                    None,
                    "dankoiptv",
                    str(_("Delete from favourites")) + "?",
                    QtWidgets.QMessageBox.StandardButton.Yes
                    | QtWidgets.QMessageBox.StandardButton.No,
                    QtWidgets.QMessageBox.StandardButton.Yes,
                )
                if isdelete_fav_msg == QtWidgets.QMessageBox.StandardButton.Yes:
                    DankoData.favourite_sets.remove(DankoData.item_selected)
            else:
                DankoData.favourite_sets.append(DankoData.item_selected)
            save_favourite_sets()
            execute_in_main_thread(partial(redraw_channels))

        def open_external_player():
            move_window_to_center(DankoGUI.ext_win)
            DankoGUI.ext_win.show()

        def tvguide_hide():
            DankoData.tvguide_lbl.setText("")
            DankoData.tvguide_lbl.hide()
            tvguide_close_lbl.hide()

        def favoritesplaylistsep_add():
            ps_data = getArrayItem(DankoData.item_selected)
            str1 = "#EXTINF:-1"
            if ps_data["tvg-name"]:
                str1 += f" tvg-name=\"{ps_data['tvg-name']}\""
            if ps_data["tvg-ID"]:
                str1 += f" tvg-id=\"{ps_data['tvg-ID']}\""
            if ps_data["tvg-logo"]:
                str1 += f" tvg-logo=\"{ps_data['tvg-logo']}\""
            if ps_data["tvg-group"]:
                str1 += f" tvg-group=\"{ps_data['tvg-group']}\""
            if ps_data["tvg-url"]:
                str1 += f" tvg-url=\"{ps_data['tvg-url']}\""
            else:
                str1 += f" tvg-url=\"{DankoData.settings['epg']}\""
            if ps_data["catchup"]:
                str1 += f" catchup=\"{ps_data['catchup']}\""
            if ps_data["catchup-source"]:
                str1 += f" catchup-source=\"{ps_data['catchup-source']}\""
            if ps_data["catchup-days"]:
                str1 += f" catchup-days=\"{ps_data['catchup-days']}\""

            str_append = ""
            if ps_data["useragent"]:
                str_append += f"#EXTVLCOPT:http-user-agent={ps_data['useragent']}\n"
            if ps_data["referer"]:
                str_append += f"#EXTVLCOPT:http-referrer={ps_data['referer']}\n"

            str1 += f",{DankoData.item_selected}\n{str_append}{ps_data['url']}\n"
            file03 = open(str(Path(LOCAL_DIR, "favplaylist.m3u")), encoding="utf8")
            file03_contents = file03.read()
            file03.close()
            if file03_contents == "#EXTM3U\n#EXTINF:-1,-\nhttp://255.255.255.255\n":
                file04 = open(
                    str(Path(LOCAL_DIR, "favplaylist.m3u")), "w", encoding="utf8"
                )
                file04.write("#EXTM3U\n" + str1)
                file04.close()
            else:
                if str1 in file03_contents:
                    playlistsep_del_msg = QtWidgets.QMessageBox.question(
                        None,
                        "dankoiptv",
                        _("Remove channel from Favourites+?"),
                        QtWidgets.QMessageBox.StandardButton.Yes
                        | QtWidgets.QMessageBox.StandardButton.No,
                        QtWidgets.QMessageBox.StandardButton.Yes,
                    )
                    if playlistsep_del_msg == QtWidgets.QMessageBox.StandardButton.Yes:
                        new_data = file03_contents.replace(str1, "")
                        if new_data == "#EXTM3U\n":
                            new_data = "#EXTM3U\n#EXTINF:-1,-\nhttp://255.255.255.255\n"
                        file05 = open(
                            str(Path(LOCAL_DIR, "favplaylist.m3u")),
                            "w",
                            encoding="utf8",
                        )
                        file05.write(new_data)
                        file05.close()
                else:
                    file02 = open(
                        str(Path(LOCAL_DIR, "favplaylist.m3u")), "w", encoding="utf8"
                    )
                    file02.write(file03_contents + str1)
                    file02.close()

        def show_context_menu(pos):
            is_continue = True
            try:
                is_continue = win.listWidget.selectedItems()[0].text() != _(
                    "Nothing found"
                )
            except Exception:
                pass
            try:
                if is_continue:
                    self = win.listWidget
                    itemSelected_event(self.selectedItems()[0])
                    menu = QtWidgets.QMenu(self)
                    menu.addAction(_("TV guide"), tvguide_context_menu)
                    menu.addAction(_("Hide TV guide"), tvguide_hide)
                    menu.addAction(_("Favourites"), tvguide_favourites_add)
                    menu.addAction(
                        _("Favourites+ (separate playlist)"), favoritesplaylistsep_add
                    )
                    menu.addAction(_("Open in external player"), open_external_player)
                    menu.addAction(_("Video settings"), settings_context_menu)
                    menu.exec(self.mapToGlobal(pos))
            except Exception:
                pass

        win.listWidget.setContextMenuPolicy(
            QtCore.Qt.ContextMenuPolicy.CustomContextMenu
        )
        win.listWidget.customContextMenuRequested.connect(show_context_menu)
        win.listWidget.currentItemChanged.connect(itemSelected_event)
        win.listWidget.itemClicked.connect(itemSelected_event)
        win.listWidget.itemDoubleClicked.connect(itemClicked_event)

        def enterPressed():
            currentItem1 = win.listWidget.currentItem()
            if currentItem1:
                itemClicked_event(currentItem1)

        shortcuts = {}
        shortcuts_return = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key.Key_Return),
            win.listWidget,
            activated=enterPressed,
        )

        def get_movie_text(movie_1):
            movie_1_txt = ""
            try:
                movie_1_txt = movie_1.text()
            except Exception:
                pass
            try:
                movie_1_txt = movie_1.data(QtCore.Qt.ItemDataRole.UserRole)
            except Exception:
                pass
            if not movie_1_txt:
                movie_1_txt = ""
            return movie_1_txt

        def channelfilter_do():
            try:
                filter_txt1 = DankoGUI.channelfilter.text()
            except Exception:
                filter_txt1 = ""
            DankoData.search = filter_txt1
            if DankoData.playmodeIndex == 0:  # TV channels
                execute_in_main_thread(partial(redraw_channels))
            elif DankoData.playmodeIndex == 1:  # Movies
                for item3 in range(win.moviesWidget.count()):
                    if (
                        filter_txt1.lower().strip()
                        in get_movie_text(win.moviesWidget.item(item3)).lower().strip()
                    ):
                        win.moviesWidget.item(item3).setHidden(False)
                    else:
                        win.moviesWidget.item(item3).setHidden(True)
            elif DankoData.playmodeIndex == 2:  # Series
                try:
                    redraw_series()
                except Exception:
                    logger.warning("redraw_series FAILED")
                for item4 in range(win.seriesWidget.count()):
                    if (
                        filter_txt1.lower().strip()
                        in win.seriesWidget.item(item4).text().lower().strip()
                    ):
                        win.seriesWidget.item(item4).setHidden(False)
                    else:
                        win.seriesWidget.item(item4).setHidden(True)

        loading = QtWidgets.QLabel(_("Loading..."))
        loading.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        loading.setFont(DankoGUI.font_italic_medium)
        hideLoading()

        loading.setFont(DankoGUI.font_12_bold)
        DankoData.combobox = QtWidgets.QComboBox()
        DankoData.combobox.currentIndexChanged.connect(group_change)

        if DankoData.settings["sort_categories"] == 1:
            groups_sorted = sorted(groups)
        elif DankoData.settings["sort_categories"] == 2:
            groups_sorted = sorted(groups, reverse=True)
        else:
            groups_sorted = groups

        if DankoData.settings["sort_categories"] in (1, 2):
            groups_sorted.remove(_("All channels"))
            DankoData.combobox.addItem(_("All channels"))

            groups_sorted.remove(_("Favourites"))
            DankoData.combobox.addItem(_("Favourites"))

        DankoData.groups_sorted = groups_sorted

        for group in groups_sorted:
            DankoData.combobox.addItem(group)

        def update_movie_icons():
            if DankoData.settings["channellogos"] != 3:  # Do not load any logos
                try:
                    for item4 in range(win.moviesWidget.count()):
                        movie_name = get_movie_text(win.moviesWidget.item(item4))
                        if movie_name:
                            if f"LOGOmovie:::{movie_name}" in DankoData.mp_manager_dict:
                                if DankoData.mp_manager_dict[
                                    f"LOGOmovie:::{movie_name}"
                                ][0]:
                                    movie_logo = get_pixmap_from_filename(
                                        DankoData.mp_manager_dict[
                                            f"LOGOmovie:::{movie_name}"
                                        ][0]
                                    )
                                    if movie_logo:
                                        win.moviesWidget.itemWidget(
                                            win.moviesWidget.item(item4)
                                        ).setPixmap(movie_logo)
                except Exception:
                    logger.warning("Set movie logos failed with exception")
                    logger.warning(traceback.format_exc())

        def movies_group_change():
            if DankoData.movies:
                current_movies_group = movies_combobox.currentText()
                if current_movies_group:
                    destroy_listwidget_items(win.moviesWidget)
                    win.moviesWidget.clear()
                    DankoData.currentMoviesGroup = {}
                    movie_logos_request = {}
                    for movies1 in DankoData.movies:
                        if "tvg-group" in DankoData.movies[movies1]:
                            if (
                                DankoData.movies[movies1]["tvg-group"]
                                == current_movies_group
                            ):
                                MovieWidget = DankoGUI.PlaylistWidget(DankoGUI)
                                MovieWidget.name_label.setText(
                                    DankoData.movies[movies1]["title"]
                                )
                                MovieWidget.progress_bar.hide()
                                MovieWidget.hideDescription()
                                MovieWidget.setPixmap(DankoGUI.movie_icon)
                                myMovieQListWidgetItem = QtWidgets.QListWidgetItem()
                                myMovieQListWidgetItem.setData(
                                    QtCore.Qt.ItemDataRole.UserRole,
                                    DankoData.movies[movies1]["title"],
                                )
                                myMovieQListWidgetItem.setSizeHint(
                                    MovieWidget.sizeHint()
                                )
                                win.moviesWidget.addItem(myMovieQListWidgetItem)
                                win.moviesWidget.setItemWidget(
                                    myMovieQListWidgetItem, MovieWidget
                                )
                                DankoData.currentMoviesGroup[
                                    DankoData.movies[movies1]["title"]
                                ] = DankoData.movies[movies1]
                                req_data_ua1, req_data_ref1 = get_ua_ref_for_channel(
                                    DankoData.movies[movies1]["title"]
                                )
                                movie_logo1 = ""
                                if "tvg-logo" in DankoData.movies[movies1]:
                                    movie_logo1 = DankoData.movies[movies1]["tvg-logo"]
                                movie_logos_request[
                                    DankoData.movies[movies1]["title"]
                                ] = [
                                    movie_logo1,
                                    "",
                                    req_data_ua1,
                                    req_data_ref1,
                                ]
                    # Fetch movie logos
                    try:
                        if DankoData.settings["channellogos"] != 3:
                            if movie_logos_request != DankoData.movie_logos_request_old:
                                DankoData.movie_logos_request_old = movie_logos_request
                                logger.debug("Movie logos request")
                                if (
                                    DankoData.movie_logos_process
                                    and DankoData.movie_logos_process.is_alive()
                                ):
                                    # logger.debug(
                                    #     "Old movie logos request found, stopping it"
                                    # )
                                    DankoData.movie_logos_process.kill()
                                DankoData.movie_logos_process = get_context(
                                    "spawn"
                                ).Process(
                                    name="[dankoiptv] channel_logos_worker_for_movie",
                                    target=channel_logos_worker,
                                    daemon=True,
                                    args=(
                                        movie_logos_request,
                                        DankoData.mp_manager_dict,
                                        "movie",
                                    ),
                                )
                                DankoData.movie_logos_process.start()
                    except Exception:
                        logger.warning("Fetch movie logos failed with exception:")
                        logger.warning(traceback.format_exc())
                    update_movie_icons()
            else:
                destroy_listwidget_items(win.moviesWidget)
                win.moviesWidget.clear()
                win.moviesWidget.addItem(_("Nothing found"))

        def movies_play(mov_item):
            if get_movie_text(mov_item) in DankoData.currentMoviesGroup:
                itemClicked_event(
                    get_movie_text(mov_item),
                    DankoData.currentMoviesGroup[get_movie_text(mov_item)]["url"],
                )

        win.moviesWidget.itemDoubleClicked.connect(movies_play)

        movies_groups = []
        movies_combobox = QtWidgets.QComboBox()
        for movie_combobox in DankoData.movies:
            if "tvg-group" in DankoData.movies[movie_combobox]:
                if DankoData.movies[movie_combobox]["tvg-group"] not in movies_groups:
                    movies_groups.append(DankoData.movies[movie_combobox]["tvg-group"])
        for movie_group in movies_groups:
            movies_combobox.addItem(movie_group)
        movies_combobox.currentIndexChanged.connect(movies_group_change)
        movies_group_change()

        def redraw_series():
            DankoData.serie_selected = False
            win.seriesWidget.clear()
            if DankoData.series:
                for serie2 in DankoData.series:
                    win.seriesWidget.addItem(serie2)
            else:
                win.seriesWidget.addItem(_("Nothing found"))

        def series_change_pt2(sel_serie):
            DankoGUI.channelfilter.setDisabled(False)
            DankoGUI.channelfiltersearch.setDisabled(False)
            win.seriesWidget.clear()
            win.seriesWidget.addItem("< " + _("Back"))
            win.seriesWidget.item(0).setForeground(QtCore.Qt.GlobalColor.blue)
            for season_name in DankoData.series[sel_serie].seasons.keys():
                season = DankoData.series[sel_serie].seasons[season_name]
                season_item = QtWidgets.QListWidgetItem()
                season_item.setText(season.name)
                season_item.setFont(DankoGUI.font_bold)
                win.seriesWidget.addItem(season_item)
                for episode_name in season.episodes.keys():
                    episode = season.episodes[episode_name]
                    episode_item = QtWidgets.QListWidgetItem()
                    episode_item.setText(episode.title)
                    episode_item.setData(
                        QtCore.Qt.ItemDataRole.UserRole,
                        episode.url
                        + ":::::::::::::::::::"
                        + season.name
                        + ":::::::::::::::::::"
                        + sel_serie,
                    )
                    win.seriesWidget.addItem(episode_item)
            DankoData.serie_selected = True

        def series_loading():
            DankoGUI.channelfilter.setDisabled(True)
            DankoGUI.channelfiltersearch.setDisabled(True)
            win.seriesWidget.clear()
            win.seriesWidget.addItem(_("Loading..."))

        def series_load(sel_serie):
            if not DankoData.series[sel_serie].seasons:
                logger.info(f"Fetching data for serie '{sel_serie}'")
                execute_in_main_thread(partial(series_loading))
                try:
                    xt.get_series_info_by_id(DankoData.series[sel_serie])
                    logger.info(
                        f"Fetching data for serie '{sel_serie}' completed"
                        f", seasons: {len(DankoData.series[sel_serie].seasons)}"
                    )
                except Exception:
                    logger.warning(f"Fetching data for serie '{sel_serie}' FAILED")
            execute_in_main_thread(partial(series_change_pt2, sel_serie))

        def series_change(series_item):
            sel_serie = series_item.text()
            if sel_serie == "< " + _("Back"):
                redraw_series()
            elif sel_serie != _("Loading..."):
                if DankoData.serie_selected:
                    try:
                        serie_data = series_item.data(QtCore.Qt.ItemDataRole.UserRole)
                        if serie_data:
                            series_name = serie_data.split(":::::::::::::::::::")[2]
                            season_name = serie_data.split(":::::::::::::::::::")[1]
                            serie_url = serie_data.split(":::::::::::::::::::")[0]
                            itemClicked_event(
                                sel_serie
                                + " ::: "
                                + season_name
                                + " ::: "
                                + series_name,
                                serie_url,
                            )
                    except Exception:
                        pass
                else:
                    thread_series_load = threading.Thread(
                        target=series_load, args=(sel_serie,), daemon=True
                    )
                    thread_series_load.start()

        win.seriesWidget.itemDoubleClicked.connect(series_change)

        redraw_series()

        playmode_selector = QtWidgets.QComboBox()
        playmode_selector.currentIndexChanged.connect(playmode_change)
        for playmode in [_("TV channels"), _("Movies"), _("Series")]:
            playmode_selector.addItem(playmode)

        def focusOutEvent_after(
            playlist_widget_visible,
            controlpanel_widget_visible,
            channelfiltersearch_has_focus,
        ):
            DankoGUI.channelfilter.usePopup = False
            DankoGUI.playlist_widget.setWindowFlags(
                QtCore.Qt.WindowType.CustomizeWindowHint
                | QtCore.Qt.WindowType.FramelessWindowHint
                | QtCore.Qt.WindowType.X11BypassWindowManagerHint
            )
            DankoGUI.controlpanel_widget.setWindowFlags(
                QtCore.Qt.WindowType.CustomizeWindowHint
                | QtCore.Qt.WindowType.FramelessWindowHint
                | QtCore.Qt.WindowType.X11BypassWindowManagerHint
            )
            if playlist_widget_visible:
                DankoGUI.playlist_widget.show()
            if controlpanel_widget_visible:
                DankoGUI.controlpanel_widget.show()
            if channelfiltersearch_has_focus:
                DankoGUI.channelfiltersearch.click()

        def mainthread_timer_2(t2):
            time.sleep(0.05)
            execute_in_main_thread(t2)

        def mainthread_timer(t1):
            thread_mainthread_timer_2 = threading.Thread(
                target=mainthread_timer_2, daemon=True
            )
            thread_mainthread_timer_2.start()

        class MyLineEdit(QtWidgets.QLineEdit):
            usePopup = False
            click_event = QtCore.pyqtSignal()

            def mousePressEvent(self, event1):
                if event1.button() == QtCore.Qt.MouseButton.LeftButton:
                    self.click_event.emit()
                else:
                    super().mousePressEvent(event1)

            def focusOutEvent(self, event2):
                super().focusOutEvent(event2)
                if DankoData.fullscreen:
                    playlist_widget_visible1 = DankoGUI.playlist_widget.isVisible()
                    controlpanel_widget_visible1 = (
                        DankoGUI.controlpanel_widget.isVisible()
                    )
                    channelfiltersearch_has_focus1 = (
                        DankoGUI.channelfiltersearch.hasFocus()
                    )
                    focusOutEvent_after_partial = partial(
                        focusOutEvent_after,
                        playlist_widget_visible1,
                        controlpanel_widget_visible1,
                        channelfiltersearch_has_focus1,
                    )
                    mainthread_timer_1 = partial(
                        mainthread_timer, focusOutEvent_after_partial
                    )
                    execute_in_main_thread(mainthread_timer_1)

        def channelfilter_clicked():
            if DankoData.fullscreen:
                playlist_widget_visible1 = DankoGUI.playlist_widget.isVisible()
                controlpanel_widget_visible1 = DankoGUI.controlpanel_widget.isVisible()
                DankoGUI.channelfilter.usePopup = True
                DankoGUI.playlist_widget.setWindowFlags(
                    QtCore.Qt.WindowType.CustomizeWindowHint
                    | QtCore.Qt.WindowType.FramelessWindowHint
                    | QtCore.Qt.WindowType.X11BypassWindowManagerHint
                    | QtCore.Qt.WindowType.Popup
                )
                DankoGUI.controlpanel_widget.setWindowFlags(
                    QtCore.Qt.WindowType.CustomizeWindowHint
                    | QtCore.Qt.WindowType.FramelessWindowHint
                    | QtCore.Qt.WindowType.X11BypassWindowManagerHint
                    | QtCore.Qt.WindowType.Popup
                )
                if playlist_widget_visible1:
                    DankoGUI.playlist_widget.show()
                if controlpanel_widget_visible1:
                    DankoGUI.controlpanel_widget.show()

        def page_change():
            win.listWidget.verticalScrollBar().setValue(0)
            redraw_channels()
            try:
                DankoGUI.page_box.clearFocus()
            except Exception:
                pass

        DankoGUI.create2(
            get_page_count(len(DankoData.array)),
            channelfilter_clicked,
            channelfilter_do,
            page_change,
            MyLineEdit,
            playmode_selector,
            DankoData.combobox,
            movies_combobox,
            loading,
        )

        if DankoData.settings["panelposition"] == 2:
            dockWidget_playlist.resize(
                DOCKWIDGET_PLAYLIST_WIDTH, dockWidget_playlist.height()
            )
            playlist_label = QtWidgets.QLabel(_("Playlist"))
            playlist_label.setFont(DankoGUI.font_12_bold)
            dockWidget_playlist.setTitleBarWidget(playlist_label)
        else:
            dockWidget_playlist.setFixedWidth(DOCKWIDGET_PLAYLIST_WIDTH)
            dockWidget_playlist.setTitleBarWidget(QtWidgets.QWidget())
        if DankoData.settings["panelposition"] == 2:
            gripWidget = QtWidgets.QWidget()
            gripLayout = QtWidgets.QVBoxLayout()
            gripLayout.setContentsMargins(0, 0, 0, 0)
            gripLayout.setSpacing(0)
            gripLayout.addWidget(DankoGUI.widget)
            gripLayout.addWidget(
                QtWidgets.QSizeGrip(DankoGUI.widget),
                0,
                QtCore.Qt.AlignmentFlag.AlignBottom
                | QtCore.Qt.AlignmentFlag.AlignRight,
            )
            gripWidget.setLayout(gripLayout)
            dockWidget_playlist.setWidget(gripWidget)
        else:
            dockWidget_playlist.setWidget(DankoGUI.widget)
        dockWidget_playlist.setFloating(DankoData.settings["panelposition"] == 2)
        dockWidget_playlist.setFeatures(
            QtWidgets.QDockWidget.DockWidgetFeature.NoDockWidgetFeatures
        )
        if DankoData.settings["panelposition"] == 0:
            win.addDockWidget(
                QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dockWidget_playlist
            )
        elif DankoData.settings["panelposition"] == 1:
            win.addDockWidget(
                QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, dockWidget_playlist
            )
        elif DankoData.settings["panelposition"] == 2:
            separate_playlist_data = read_option("separate_playlist")
            if separate_playlist_data:
                dockWidget_playlist.setGeometry(
                    separate_playlist_data["x"],
                    separate_playlist_data["y"],
                    separate_playlist_data["w"],
                    separate_playlist_data["h"],
                )
            else:
                dockWidget_playlist.resize(dockWidget_playlist.width(), win.height())
                dockWidget_playlist.move(
                    win.pos().x() + win.width() - dockWidget_playlist.width() + 25,
                    win.pos().y(),
                )

        FORBIDDEN_CHARS = ('"', "*", ":", "<", ">", "?", "\\", "/", "|", "[", "]")

        def do_screenshot():
            if DankoData.playing_channel:
                DankoData.state.show()
                DankoData.state.setTextDanko(_("Doing screenshot..."))
                ch = DankoData.playing_channel.replace(" ", "_")
                for char in FORBIDDEN_CHARS:
                    ch = ch.replace(char, "")
                cur_time = datetime.datetime.now().strftime("%d%m%Y_%H%M%S")
                file_name = "screenshot_-_" + cur_time + "_-_" + ch + ".png"
                if not DankoData.settings["scrrecnosubfolders"]:
                    file_path = str(Path(save_folder, "screenshots", file_name))
                else:
                    file_path = str(Path(save_folder, file_name))
                try:
                    DankoData.player.screenshot_to_file(file_path, includes="subtitles")
                    DankoData.state.show()
                    DankoData.state.setTextDanko(_("Screenshot saved!"))
                except Exception:
                    DankoData.state.show()
                    DankoData.state.setTextDanko(_("Screenshot saving error!"))
                DankoData.time_stop = time.time() + 1
            else:
                DankoData.state.show()
                DankoData.state.setTextDanko("{}!".format(_("No channel selected")))
                DankoData.time_stop = time.time() + 1

        def update_tvguide(
            channel_1="",
            do_return=False,
            show_all_guides=False,
            mark_integers=False,
            date_selected=None,
        ):
            if DankoData.array:
                if not channel_1:
                    if DankoData.item_selected:
                        channel_2 = DankoData.item_selected
                    else:
                        channel_2 = sorted(DankoData.array.items())[0][0]
                else:
                    channel_2 = channel_1
                try:
                    channel_1_item = getArrayItem(channel_1)
                except Exception:
                    channel_1_item = None
                txt = _("No TV guide for channel")
                newline_symbol = "\n"
                if do_return:
                    newline_symbol = "!@#$%^^&*("

                current_programmes = None
                epg_id = get_epg_id(channel_2)
                if epg_id:
                    programmes = get_epg_programmes(epg_id)
                    if programmes:
                        current_programmes = programmes

                if current_programmes:
                    txt = newline_symbol
                    for pr in current_programmes:
                        override_this = False
                        if show_all_guides:
                            override_this = pr["start"] < time.time() + 1
                        else:
                            override_this = pr["stop"] > time.time() - 1
                        archive_btn = ""
                        if date_selected is not None:
                            override_this = epg_is_in_date(pr, date_selected)
                        if override_this:
                            use_placeholder = "%d.%m.%y %H:%M"
                            if mark_integers:
                                use_placeholder = "%d.%m.%Y %H:%M:%S"
                            start_2 = (
                                datetime.datetime.fromtimestamp(pr["start"]).strftime(
                                    use_placeholder
                                )
                                + " - "
                            )
                            stop_2 = (
                                datetime.datetime.fromtimestamp(pr["stop"]).strftime(
                                    use_placeholder
                                )
                                + "\n"
                            )
                            try:
                                title_2 = pr["title"] if "title" in pr else ""
                            except Exception:
                                title_2 = ""
                            try:
                                desc_2 = (
                                    ("\n" + pr["desc"] + "\n") if "desc" in pr else ""
                                )
                            except Exception:
                                desc_2 = ""
                            attach_1 = ""
                            if mark_integers:
                                try:
                                    marked_integer = current_programmes.index(pr)
                                except Exception:
                                    marked_integer = -1
                                attach_1 = f" ({marked_integer})"
                            if (
                                date_selected is not None
                                and DankoGUI.showonlychplaylist_chk.isChecked()
                            ):
                                try:
                                    catchup_days2 = int(channel_1_item["catchup-days"])
                                except Exception:
                                    catchup_days2 = 7
                                # support for seconds
                                if catchup_days2 < 1000:
                                    catchup_days2 = catchup_days2 * 86400
                                if (
                                    pr["start"] < time.time() + 1
                                    and not (
                                        time.time() > pr["start"]
                                        and time.time() < pr["stop"]
                                    )
                                    and pr["stop"] > time.time() - catchup_days2
                                ):
                                    archive_link = urllib.parse.quote_plus(
                                        json.dumps(
                                            [
                                                channel_1,
                                                datetime.datetime.fromtimestamp(
                                                    pr["start"]
                                                ).strftime("%d.%m.%Y %H:%M:%S"),
                                                datetime.datetime.fromtimestamp(
                                                    pr["stop"]
                                                ).strftime("%d.%m.%Y %H:%M:%S"),
                                                current_programmes.index(pr),
                                            ]
                                        )
                                    )
                                    archive_btn = (
                                        '\n<a href="#__archive__'
                                        + archive_link
                                        + '">'
                                        + _("Open archive")
                                        + "</a>"
                                    )
                            start_symbl = ""
                            stop_symbl = ""
                            if DankoData.use_dark_icon_theme:
                                start_symbl = '<span style="color: white;">'
                                stop_symbl = "</span>"
                            use_epg_color = "green"
                            if time.time() > pr["start"] and time.time() < pr["stop"]:
                                use_epg_color = "red"
                            txt += (
                                f'<span style="color: {use_epg_color};">'
                                + start_2
                                + stop_2
                                + "</span>"
                                + start_symbl
                                + "<b>"
                                + title_2
                                + "</b>"
                                + archive_btn
                                + desc_2
                                + attach_1
                                + stop_symbl
                                + newline_symbol
                            )
                if txt == newline_symbol or not txt:
                    txt = _("No TV guide for channel")
                if do_return:
                    return txt
                txt = txt.replace("\n", "<br>").replace("<br>", "", 1)
                DankoData.tvguide_lbl.setText(txt)
            return ""

        def show_tvguide():
            if DankoData.tvguide_lbl.isVisible():
                DankoData.tvguide_lbl.setText("")
                DankoData.tvguide_lbl.hide()
                tvguide_close_lbl.hide()
            else:
                update_tvguide()
                DankoData.tvguide_lbl.show()
                tvguide_close_lbl.show()

        def hide_tvguide():
            if DankoData.tvguide_lbl.isVisible():
                DankoData.tvguide_lbl.setText("")
                DankoData.tvguide_lbl.hide()
                tvguide_close_lbl.hide()

        def update_tvguide_2():
            DankoGUI.epg_win_checkbox.clear()
            if DankoGUI.showonlychplaylist_chk.isChecked():
                DankoGUI.epg_win_count.setText(
                    "({}: {})".format(_("channels"), len(DankoData.array_sorted))
                )
                for channel_0 in DankoData.array_sorted:
                    DankoGUI.epg_win_checkbox.addItem(channel_0)
            else:
                epg_names = get_all_epg_names()
                if not epg_names:
                    epg_names = set()
                DankoGUI.epg_win_count.setText(
                    "({}: {})".format(_("channels"), len(epg_names))
                )
                for channel_0 in epg_names:
                    DankoGUI.epg_win_checkbox.addItem(channel_0)

        def show_tvguide_2():
            if DankoGUI.epg_win.isVisible():
                DankoGUI.epg_win.hide()
            else:
                epg_index = DankoGUI.epg_win_checkbox.currentIndex()
                update_tvguide_2()
                if epg_index != -1:
                    DankoGUI.epg_win_checkbox.setCurrentIndex(epg_index)
                move_window_to_center(DankoGUI.epg_win)
                DankoGUI.epg_win.show()

        def get_channels_page(group, page):
            if isinstance(DankoData.array_sorted, list):
                channels = DankoData.array_sorted
            else:
                channels = list(DankoData.array_sorted.keys())
            if group and group != _("All channels"):
                if group == _("Favourites"):
                    channels = [
                        channel
                        for channel in channels
                        if channel in DankoData.favourite_sets
                    ]
                else:
                    channels = [
                        channel
                        for channel in channels
                        if DankoData.array[channel]["tvg-group"] == group
                    ]
            channels_on_page = 10
            page_start = (page * channels_on_page) - channels_on_page
            page_end = page * channels_on_page
            return channels[page_start:page_end]

        def show_multi_epg():
            if DankoGUI.multiepg_win.isVisible():
                DankoGUI.multiepg_win.hide()
            else:
                DankoGUI.multiepg_win._set(
                    getArrayItem=getArrayItem,
                    get_epg_id=get_epg_id,
                    get_epg_programmes=get_epg_programmes,
                    epg_is_in_date=epg_is_in_date,
                    font_bold=DankoGUI.font_bold,
                    font_italic=DankoGUI.font_italic,
                    get_channels_page=get_channels_page,
                    is_dark_theme=is_dark_theme,
                )
                DankoGUI.multiepg_win.first()
                DankoGUI.multiepg_win.show()

        def show_archive():
            if not DankoGUI.epg_win.isVisible():
                show_tvguide_2()
                find_channel = DankoData.item_selected
                if not find_channel:
                    find_channel = DankoData.playing_channel
                if find_channel:
                    try:
                        find_channel_index = DankoGUI.epg_win_checkbox.findText(
                            find_channel, QtCore.Qt.MatchFlag.MatchExactly
                        )
                    except Exception:
                        find_channel_index = -1
                    if find_channel_index != -1:
                        DankoGUI.epg_win_checkbox.setCurrentIndex(find_channel_index)
                epg_date_changed(DankoGUI.epg_select_date.selectedDate())
            else:
                DankoGUI.epg_win.hide()

        def start_record(ch1, url3):
            orig_channel_name = ch1
            if not DankoData.is_recording:
                DankoData.is_recording = True
                DankoGUI.lbl2.show()
                DankoGUI.lbl2.setText(_("Preparing record"))
                ch = ch1.replace(" ", "_")
                for char in FORBIDDEN_CHARS:
                    ch = ch.replace(char, "")
                cur_time = datetime.datetime.now().strftime("%d%m%Y_%H%M%S")
                if not DankoData.settings["scrrecnosubfolders"]:
                    out_file = str(
                        Path(
                            save_folder,
                            "recordings",
                            f"recording_-_{cur_time}_-_{ch}.ts",
                        )
                    )
                else:
                    out_file = str(
                        Path(
                            save_folder,
                            f"recording_-_{cur_time}_-_{ch}.ts",
                        )
                    )
                DankoData.record_file = out_file
                record(
                    url3,
                    out_file,
                    orig_channel_name,
                    f"Referer: {DankoData.settings['referer']}",
                    get_ua_ref_for_channel,
                )
            else:
                DankoData.is_recording = False
                DankoData.recording_time = 0
                stop_record()
                DankoGUI.lbl2.setText("")
                DankoGUI.lbl2.hide()

        def do_record():
            if DankoData.playing_channel:
                start_record(DankoData.playing_channel, DankoData.playing_url)
            else:
                DankoData.time_stop = time.time() + 1
                DankoData.state.show()
                DankoData.state.setTextDanko(_("No channel selected for record"))

        def my_log(mpv_loglevel1, component, message):
            mpv_log_str = f"[{mpv_loglevel1}] {component}: {message}"

            if "Invalid video timestamp: " not in str(mpv_log_str):
                if "[debug] " in str(mpv_log_str) or "[trace] " in str(mpv_log_str):
                    mpv_logger.debug(str(mpv_log_str).strip())
                elif "[warn] " in str(mpv_log_str):
                    mpv_logger.warning(str(mpv_log_str).strip())
                elif "[error] " in str(mpv_log_str):
                    mpv_logger.error(str(mpv_log_str).strip())
                elif "[fatal] " in str(mpv_log_str):
                    mpv_logger.critical(str(mpv_log_str).strip())
                else:
                    mpv_logger.info(str(mpv_log_str).strip())

            if "stream: Failed to open" in mpv_log_str:
                execute_in_main_thread(partial(end_file_error_callback, True))

        def playLastChannel():
            isPlayingLast = False
            if (
                os.path.isfile(str(Path(LOCAL_DIR, "lastchannels.json")))
                and DankoData.settings["openprevchannel"]
            ):
                try:
                    lastfile_1 = open(
                        str(Path(LOCAL_DIR, "lastchannels.json")), encoding="utf8"
                    )
                    lastfile_1_dat = json.loads(lastfile_1.read())
                    lastfile_1.close()
                    if lastfile_1_dat[0] in DankoData.array_sorted:
                        isPlayingLast = True
                        DankoData.player.user_agent = lastfile_1_dat[2]
                        setChannelText("  " + lastfile_1_dat[0])
                        itemClicked_event(lastfile_1_dat[0])
                        setChannelText("  " + lastfile_1_dat[0])
                        try:
                            if lastfile_1_dat[3] < DankoData.combobox.count():
                                DankoData.combobox.setCurrentIndex(lastfile_1_dat[3])
                        except Exception:
                            pass
                        try:
                            win.listWidget.setCurrentRow(lastfile_1_dat[4])
                        except Exception:
                            pass
                except Exception:
                    if os.path.isfile(str(Path(LOCAL_DIR, "lastchannels.json"))):
                        os.remove(str(Path(LOCAL_DIR, "lastchannels.json")))
            return isPlayingLast

        options, options_custom = get_mpv_options(
            {
                "osc": True,
                "hwdec": "no",
                "ytdl": False,
                "title": "Dankoiptv",
                "force-window": True,
                "force-seekable": True,
                "audio-client-name": "dankoiptv",
                "wid": str(int(win.container.winId())),
                "loglevel": "info" if loglevel.lower() != "debug" else "debug",
                "script-opts": "osc-layout=slimbox,osc-seekbarstyle=bar,"
                "osc-deadzonesize=0,osc-minmousemove=3,osc-idlescreen=no",
            },
            DankoData.settings["mpv_options"],
        )

        logger.info(f"Custom mpv options: {json.dumps(options_custom)}")

        def get_about_text():
            about_txt = f"<b>Dankoiptv {APP_VERSION}</b>"
            about_txt += "<br><br>" + _("IPTV player with EPG support")
            about_txt += f"<br><br>Python {sys.version.strip()}"
            about_txt += f"<br>Qt {get_qt_info(app)}"
            about_txt += f"<br>{DankoData.player.mpv_version}"
            return about_txt

        def main_channel_settings():
            if DankoData.playing_channel:
                DankoData.item_selected = DankoData.playing_channel
                settings_context_menu()
            else:
                msg = QtWidgets.QMessageBox(
                    QtWidgets.QMessageBox.Icon.Warning,
                    "dankoiptv",
                    _("No channel selected"),
                    QtWidgets.QMessageBox.StandardButton.Ok,
                )
                msg.exec()

        def idle_showhideplaylist():
            if not DankoData.fullscreen:
                try:
                    show_hide_playlist()
                except Exception:
                    pass

        def showhideplaylist():
            execute_in_main_thread(partial(idle_showhideplaylist))

        def idle_lowpanel_ch_1():
            if not DankoData.fullscreen:
                try:
                    lowpanel_ch()
                except Exception:
                    pass

        def lowpanel_ch_1():
            execute_in_main_thread(partial(idle_lowpanel_ch_1))

        def showhideeverything():
            if not DankoData.fullscreen:
                if dockWidget_playlist.isVisible():
                    DankoData.compact_mode = True
                    dockWidget_playlist.hide()
                    dockWidget_controlPanel.hide()
                    win.menu_bar_qt.hide()
                else:
                    DankoData.compact_mode = False
                    dockWidget_playlist.show()
                    dockWidget_controlPanel.show()
                    win.menu_bar_qt.show()

        def timer_bitrate():
            try:
                if DankoGUI.streaminfo_win.isVisible():
                    if "video" in stream_info.data:
                        stream_info.data["video"][0].setText(
                            stream_info.data["video"][1][_("Average Bitrate")]
                        )
                    if "audio" in stream_info.data:
                        stream_info.data["audio"][0].setText(
                            stream_info.data["audio"][1][_("Average Bitrate")]
                        )
            except Exception:
                pass

        def is_recording_func():
            ret_code_rec = False
            if DankoData.ffmpeg_processes:
                ret_code_array = []
                for ffmpeg_process_1 in DankoData.ffmpeg_processes:
                    if ffmpeg_process_1[0].processId() == 0:
                        ret_code_array.append(True)
                        DankoData.ffmpeg_processes.remove(ffmpeg_process_1)
                    else:
                        ret_code_array.append(False)
                ret_code_rec = False not in ret_code_array
            else:
                ret_code_rec = True
            return ret_code_rec

        win.oldpos = None

        def redraw_menubar():
            try:
                update_menubar(
                    DankoData.player.track_list,
                    DankoData.playing_channel,
                    DankoData.settings["m3u"],
                )
            except Exception:
                logger.warning("redraw_menubar failed")
                show_exception(traceback.format_exc(), "redraw_menubar failed")

        DankoData.right_click_menu = QtWidgets.QMenu()

        def do_reconnect():
            if DankoData.playing_channel:
                logger.info("Reconnecting to stream")
                try:
                    doPlay(*DankoData.do_play_args)
                except Exception:
                    logger.warning("Failed reconnecting to stream - no known URL")

        def do_reconnect_async():
            time.sleep(1)
            execute_in_main_thread(partial(do_reconnect))

        # --- Dankoiptv seamless engine (AGENTS §3): eof-reached + cascade ---
        DankoData._last_eof_time = 0
        DankoData._eof_cascade = 0
        DankoData._seamless_reloading = False
        DankoData._seamless_armed = True
        DankoData._err_retries = 0

        def seamless_reload_worker(delay):
            DankoData._seamless_reloading = True
            if delay > 0:
                time.sleep(delay)
            DankoData._seamless_reloading = False
            try:
                if (
                    DankoData._seamless_armed
                    and DankoData.playing_group == 0
                    and DankoData.playing_channel
                ):
                    execute_in_main_thread(partial(do_reconnect))
            except Exception:
                logger.warning("seamless_reload_worker failed")
                logger.warning(traceback.format_exc())

        def eof_reached_handler(value):
            try:
                if value is not True:
                    return
                if not getattr(DankoData, "_seamless_armed", True):
                    return
                if DankoData.playing_group != 0 or not DankoData.playing_channel:
                    return
                if DankoData.is_loading:
                    return
                now = time.time()
                if now - DankoData._last_eof_time < 20:
                    DankoData._eof_cascade += 1
                else:
                    DankoData._eof_cascade = 0
                DankoData._last_eof_time = now
                delay = min(DankoData._eof_cascade * 2, 8)
                logger.info(
                    f"Stream EOF - seamless reload in {delay}s "
                    f"(cascade {DankoData._eof_cascade})"
                )
                if not DankoData._seamless_reloading:
                    thread_seamless = threading.Thread(
                        target=seamless_reload_worker, args=(delay,), daemon=True
                    )
                    thread_seamless.start()
            except Exception:
                logger.warning("eof_reached_handler failed")
                logger.warning(traceback.format_exc())

        def end_file_error_callback(no_reconnect=False):
            # Errores reales (no EOF): backoff exponencial 2^n cap 30s,
            # máximo 10 reintentos; overlay "Playing error" solo si se rinde.
            DankoData._err_retries = getattr(DankoData, "_err_retries", 0) + 1
            if (
                not no_reconnect
                and DankoData.settings["autoreconnection"]
                and DankoData.playing_group == 0
                and DankoData._err_retries <= 10
            ):
                delay = min(2 ** (DankoData._err_retries - 1), 30)

                def _err_backoff_worker(d):
                    time.sleep(d)
                    execute_in_main_thread(partial(do_reconnect))

                logger.warning(
                    f"Playback error, retry {DankoData._err_retries}/10 in {delay}s..."
                )
                thread_do_reconnect_async = threading.Thread(
                    target=_err_backoff_worker, args=(delay,), daemon=True
                )
                thread_do_reconnect_async.start()
                return
            if DankoData._err_retries > 10:
                logger.warning("Giving up after 10 retries")
            logger.warning("Playing error!")
            if not DankoData.is_loading:
                mpv_stop()
            else:
                DankoData.resume_playback = not DankoData.player.pause
                mpv_stop()

            DankoGUI.channel.setText("")
            DankoGUI.channel.hide()
            loading.setText(_("Playing error"))
            loading.setFont(DankoGUI.font_bold_medium)
            showLoading()
            DankoGUI.loading1.hide()
            DankoGUI.loading_movie.stop()

        def end_file_callback():
            if win.isVisible():
                if DankoData.playing_channel and DankoData.player.path is None:
                    if (
                        DankoData.settings["autoreconnection"]
                        and DankoData.playing_group == 0
                    ):
                        logger.warning("Connection to stream lost, waiting 1 sec...")
                        do_reconnect_async()
                    elif not DankoData.is_loading:
                        mpv_stop()

        def file_loaded_callback():
            # file_loaded resetea contadores de reintentos (AGENTS §3)
            DankoData._err_retries = 0
            DankoData._eof_cascade = 0
            if DankoData.playing_channel:
                redraw_menubar()

        def my_mouse_right_callback():
            DankoData.right_click_menu.exec(QtGui.QCursor.pos())

        def my_mouse_left_callback():
            if DankoData.right_click_menu.isVisible():
                DankoData.right_click_menu.hide()
            elif DankoData.settings["hideplaylistbyleftmouseclick"]:
                show_hide_playlist()

        def idle_my_up_binding_execute():
            volume = int(DankoData.player.volume + DankoData.settings["volumechangestep"])
            volume = min(volume, 200)
            DankoGUI.volume_slider.setValue(volume)
            mpv_volume_set()

        def my_up_binding_execute():
            execute_in_main_thread(partial(idle_my_up_binding_execute))

        def idle_my_down_binding_execute():
            volume = int(DankoData.player.volume - DankoData.settings["volumechangestep"])
            volume = max(volume, 0)
            DankoData.time_stop = time.time() + 3
            show_volume(volume)
            DankoGUI.volume_slider.setValue(volume)
            mpv_volume_set()

        def my_down_binding_execute():
            execute_in_main_thread(partial(idle_my_down_binding_execute))

        class ControlPanelDockWidget(QtWidgets.QDockWidget):
            def enterEvent(self, event4):
                DankoData.check_controlpanel_visible = True

            def leaveEvent(self, event4):
                DankoData.check_controlpanel_visible = False

        dockWidget_controlPanel = ControlPanelDockWidget(win)

        dockWidget_playlist.setObjectName("dockWidget_playlist")
        dockWidget_controlPanel.setObjectName("dockWidget_controlPanel")

        def open_recording_folder():
            absolute_path = Path(save_folder).absolute()
            xdg_open = subprocess.Popen(["xdg-open", str(absolute_path)])
            xdg_open.wait()

        def open_recording_folder_async():
            thread_open_recording_folder = threading.Thread(
                target=open_recording_folder, daemon=True
            )
            thread_open_recording_folder.start()

        def go_channel(i1):
            pause_state = DankoData.player.pause
            if DankoData.resume_playback:
                DankoData.resume_playback = False
                pause_state = False
            row = win.listWidget.currentRow()
            if row == -1:
                row = DankoData.row0
            next_row = row + i1
            if next_row < 0:
                # Previous page
                if DankoGUI.page_box.value() - 1 == 0:
                    next_row = 0
                else:
                    DankoGUI.page_box.setValue(DankoGUI.page_box.value() - 1)
                    next_row = win.listWidget.count()
            elif next_row > win.listWidget.count() - 1:
                # Next page
                if DankoGUI.page_box.value() + 1 > DankoGUI.page_box.maximum():
                    next_row = row
                else:
                    DankoGUI.page_box.setValue(DankoGUI.page_box.value() + 1)
                    next_row = 0
            next_row = max(next_row, 0)
            next_row = min(next_row, win.listWidget.count() - 1)
            chk_pass = True
            try:
                chk_pass = win.listWidget.item(next_row).text() != _("Nothing found")
            except Exception:
                pass
            if chk_pass:
                win.listWidget.setCurrentRow(next_row)
                itemClicked_event(win.listWidget.currentItem())
            DankoData.player.pause = pause_state

        def prev_channel():
            execute_in_main_thread(partial(go_channel, -1))

        def next_channel():
            execute_in_main_thread(partial(go_channel, 1))

        def get_keybind(func1):
            return DankoData.main_keybinds[func1]

        def mpris_set_volume(val):
            DankoGUI.volume_slider.setValue(int(val * 100))
            mpv_volume_set()

        def mpris_seek(val):
            if DankoData.playing_channel:
                DankoData.player.command("seek", val)

        def mpris_set_position(track_id, val):
            if (
                DankoData.player
                and DankoData.mpris_ready
                and DankoData.mpris_running
                and not DankoData.stopped
            ):
                (
                    playback_status,
                    mpris_trackid,
                    artUrl,
                    player_position,
                ) = get_mpris_metadata()
                if track_id == mpris_trackid:
                    DankoData.player.time_pos = val

        def get_playlist_hash(playlist):
            return hashlib.sha512(playlist["m3u"].encode("utf-8")).hexdigest()

        def get_playlists():
            prefix = "/page/codeberg/liya/dankoiptv_lib/Playlist/"
            current_playlist = (f"{prefix}Unknown", _("Unknown"), "")
            current_playlist_name = _("Unknown")
            for playlist in DankoData.playlists_saved:
                if (
                    DankoData.playlists_saved[playlist]["m3u"]
                    == DankoData.settings["m3u"]
                ):
                    current_playlist_name = playlist
                    current_playlist = (
                        f"{prefix}"
                        f"{get_playlist_hash(DankoData.playlists_saved[playlist])}",
                        playlist,
                        "",
                    )
                    break
            return (
                current_playlist_name,
                current_playlist,
                [
                    (
                        f"{prefix}{get_playlist_hash(DankoData.playlists_saved[x])}",
                        x,
                        "",
                    )
                    for x in DankoData.playlists_saved
                ],
            )

        def mpris_select_playlist(playlist_to_select):
            (
                _current_playlist_name,
                _current_playlist,
                playlists,
            ) = get_playlists()
            for playlist in playlists:
                if playlist[0] == playlist_to_select:
                    playlist_selected(f"playlist:{playlist[1]}")
                    break

        try:

            def mpris_callback(mpris_data):
                if (
                    mpris_data[0] == "org.mpris.MediaPlayer2"
                    and mpris_data[1] == "Raise"
                ):
                    execute_in_main_thread(partial(lambda: show_window(win)))
                elif (
                    mpris_data[0] == "org.mpris.MediaPlayer2"
                    and mpris_data[1] == "Quit"
                ):
                    QtCore.QTimer.singleShot(
                        100, lambda: execute_in_main_thread(partial(key_quit))
                    )
                elif (
                    mpris_data[0] == "org.mpris.MediaPlayer2.Player"
                    and mpris_data[1] == "Next"
                ):
                    execute_in_main_thread(partial(next_channel))
                elif (
                    mpris_data[0] == "org.mpris.MediaPlayer2.Player"
                    and mpris_data[1] == "Previous"
                ):
                    execute_in_main_thread(partial(prev_channel))
                elif (
                    mpris_data[0] == "org.mpris.MediaPlayer2.Player"
                    and mpris_data[1] == "Pause"
                ):
                    if not DankoData.player.pause:
                        execute_in_main_thread(partial(mpv_play))
                elif (
                    mpris_data[0] == "org.mpris.MediaPlayer2.Player"
                    and mpris_data[1] == "PlayPause"
                ):
                    execute_in_main_thread(partial(mpv_play))
                elif (
                    mpris_data[0] == "org.mpris.MediaPlayer2.Player"
                    and mpris_data[1] == "Stop"
                ):
                    execute_in_main_thread(partial(mpv_stop))
                elif (
                    mpris_data[0] == "org.mpris.MediaPlayer2.Player"
                    and mpris_data[1] == "Play"
                ):
                    if DankoData.player.pause:
                        execute_in_main_thread(partial(mpv_play))
                elif (
                    mpris_data[0] == "org.mpris.MediaPlayer2.Player"
                    and mpris_data[1] == "Seek"
                ):
                    # microseconds to seconds
                    execute_in_main_thread(
                        partial(mpris_seek, mpris_data[2][0] / 1000000)
                    )
                elif (
                    mpris_data[0] == "org.mpris.MediaPlayer2.Player"
                    and mpris_data[1] == "SetPosition"
                ):
                    track_id = mpris_data[2][0]
                    position = mpris_data[2][1] / 1000000  # microseconds to seconds
                    if track_id != "/page/codeberg/liya/dankoiptv_lib/Track/NoTrack":
                        execute_in_main_thread(
                            partial(mpris_set_position, track_id, position)
                        )
                elif (
                    mpris_data[0] == "org.mpris.MediaPlayer2.Player"
                    and mpris_data[1] == "OpenUri"
                ):
                    mpris_play_url = mpris_data[2].unpack()[0]
                    execute_in_main_thread(
                        partial(itemClicked_event, mpris_play_url, mpris_play_url)
                    )
                elif (
                    mpris_data[0] == "org.mpris.MediaPlayer2.Playlists"
                    and mpris_data[1] == "ActivatePlaylist"
                ):
                    execute_in_main_thread(
                        partial(mpris_select_playlist, mpris_data[2].unpack()[0])
                    )
                elif (
                    mpris_data[0] == "org.mpris.MediaPlayer2.Playlists"
                    and mpris_data[1] == "GetPlaylists"
                ):
                    (
                        _current_playlist_name,
                        _current_playlist,
                        playlists,
                    ) = get_playlists()
                    return GLib.Variant.new_tuple(GLib.Variant("a(oss)", playlists))
                elif (
                    mpris_data[0] == "org.freedesktop.DBus.Properties"
                    and mpris_data[1] == "Set"
                ):
                    mpris_data_params = mpris_data[2].unpack()
                    if (
                        mpris_data_params[0] == "org.mpris.MediaPlayer2"
                        and mpris_data_params[1] == "Fullscreen"
                    ):
                        if mpris_data_params[2]:
                            # Enable fullscreen
                            if not DankoData.fullscreen:
                                execute_in_main_thread(partial(mpv_fullscreen))
                        else:
                            # Disable fullscreen
                            if DankoData.fullscreen:
                                execute_in_main_thread(partial(mpv_fullscreen))
                    elif (
                        mpris_data_params[0] == "org.mpris.MediaPlayer2.Player"
                        and mpris_data_params[1] == "LoopStatus"
                    ):
                        # Not implemented
                        pass
                    elif (
                        mpris_data_params[0] == "org.mpris.MediaPlayer2.Player"
                        and mpris_data_params[1] == "Rate"
                    ):
                        execute_in_main_thread(
                            partial(set_playback_speed, mpris_data_params[2])
                        )
                    elif (
                        mpris_data_params[0] == "org.mpris.MediaPlayer2.Player"
                        and mpris_data_params[1] == "Shuffle"
                    ):
                        # Not implemented
                        pass
                    elif (
                        mpris_data_params[0] == "org.mpris.MediaPlayer2.Player"
                        and mpris_data_params[1] == "Volume"
                    ):
                        execute_in_main_thread(
                            partial(mpris_set_volume, mpris_data_params[2])
                        )
                # Always responding None, even if unknown command called
                # to prevent freezing
                return None

            def get_mpris_metadata():
                if DankoData.playing_channel:
                    if DankoData.player.pause or DankoData.is_loading:
                        playback_status = "Paused"
                    else:
                        playback_status = "Playing"
                else:
                    playback_status = "Stopped"
                playing_url_hash = hashlib.sha512(
                    DankoData.playing_url.encode("utf-8")
                ).hexdigest()
                mpris_trackid = (
                    f"/page/codeberg/liya/dankoiptv_lib/Track/{playing_url_hash}"
                    if DankoData.playing_url
                    else "/page/codeberg/liya/dankoiptv_lib/Track/NoTrack"
                )
                artUrl = ""
                if DankoData.playing_channel in DankoData.array:
                    if "tvg-logo" in DankoData.array[DankoData.playing_channel]:
                        if DankoData.array[DankoData.playing_channel]["tvg-logo"]:
                            artUrl = DankoData.array[DankoData.playing_channel][
                                "tvg-logo"
                            ]
                # Position in microseconds
                player_position = (
                    DankoData.player.duration * 1000000
                    if DankoData.player.duration
                    else 0
                )
                return playback_status, mpris_trackid, artUrl, player_position

            def get_mpris_options():
                if (
                    DankoData.player
                    and DankoData.mpris_ready
                    and DankoData.mpris_running
                    and not DankoData.stopped
                ):
                    (
                        playback_status,
                        mpris_trackid,
                        artUrl,
                        player_position,
                    ) = get_mpris_metadata()
                    current_playlist_name, current_playlist, playlists = get_playlists()
                    return {
                        "org.mpris.MediaPlayer2": {
                            "CanQuit": GLib.Variant("b", True),
                            "Fullscreen": GLib.Variant("b", DankoData.fullscreen),
                            "CanSetFullscreen": GLib.Variant("b", True),
                            "CanRaise": GLib.Variant("b", True),
                            "HasTrackList": GLib.Variant("b", False),
                            "Identity": GLib.Variant("s", "dankoiptv"),
                            "DesktopEntry": GLib.Variant("s", "dankoiptv"),
                            "SupportedUriSchemes": GLib.Variant(
                                "as",
                                ("file", "http", "https", "rtp", "udp"),
                            ),
                            "SupportedMimeTypes": GLib.Variant(
                                "as",
                                (
                                    "audio/mpeg",
                                    "audio/x-mpeg",
                                    "video/mpeg",
                                    "video/x-mpeg",
                                    "video/x-mpeg-system",
                                    "video/mp4",
                                    "audio/mp4",
                                    "video/x-msvideo",
                                    "video/quicktime",
                                    "application/ogg",
                                    "application/x-ogg",
                                    "video/x-ms-asf",
                                    "video/x-ms-asf-plugin",
                                    "application/x-mplayer2",
                                    "video/x-ms-wmv",
                                    "video/x-google-vlc-plugin",
                                    "audio/x-wav",
                                    "audio/3gpp",
                                    "video/3gpp",
                                    "audio/3gpp2",
                                    "video/3gpp2",
                                    "video/x-flv",
                                    "video/x-matroska",
                                    "audio/x-matroska",
                                    "application/xspf+xml",
                                ),
                            ),
                        },
                        "org.mpris.MediaPlayer2.Player": {
                            "PlaybackStatus": GLib.Variant("s", playback_status),
                            "LoopStatus": GLib.Variant("s", "None"),
                            "Rate": GLib.Variant("d", DankoData.player.speed),
                            "Shuffle": GLib.Variant("b", False),
                            "Metadata": GLib.Variant(
                                "a{sv}",
                                {
                                    "mpris:trackid": GLib.Variant("o", mpris_trackid),
                                    "mpris:artUrl": GLib.Variant("s", artUrl),
                                    "mpris:length": GLib.Variant("x", player_position),
                                    "xesam:url": GLib.Variant(
                                        "s", DankoData.playing_url
                                    ),
                                    "xesam:title": GLib.Variant(
                                        "s", DankoData.playing_channel
                                    ),
                                },
                            ),
                            "Volume": GLib.Variant(
                                "d", float(DankoData.player.volume / 100)
                            ),
                            "Position": GLib.Variant(
                                "x",
                                DankoData.player.time_pos * 1000000
                                if DankoData.player.time_pos
                                else 0,
                            ),
                            "MinimumRate": GLib.Variant("d", 0.01),
                            "MaximumRate": GLib.Variant("d", 5.0),
                            "CanGoNext": GLib.Variant("b", True),
                            "CanGoPrevious": GLib.Variant("b", True),
                            "CanPlay": GLib.Variant("b", True),
                            "CanPause": GLib.Variant("b", True),
                            "CanSeek": GLib.Variant("b", True),
                            "CanControl": GLib.Variant("b", True),
                        },
                        "org.mpris.MediaPlayer2.Playlists": {
                            "PlaylistCount": GLib.Variant("u", len(playlists)),
                            "Orderings": GLib.Variant("as", ("UserDefined",)),
                            "ActivePlaylist": GLib.Variant(
                                "(b(oss))",
                                (
                                    True,
                                    GLib.Variant(
                                        "(oss)",
                                        current_playlist,
                                    ),
                                ),
                            ),
                        },
                    }
                else:
                    return {}

            def wait_until():
                while True:
                    if win.isVisible() or DankoData.stopped:
                        return True
                    else:
                        time.sleep(0.1)
                return False

            def mpris_loop_start():
                wait_until()
                if not DankoData.stopped:
                    try:
                        mpris_owner_bus_id = start_mpris(
                            os.getpid(), mpris_callback, get_mpris_options
                        )
                        DankoData.mpris_ready = True
                        DankoData.mpris_running = True
                        DankoData.mpris_loop.run()
                        Gio.bus_unown_name(mpris_owner_bus_id)
                    except Exception:
                        logger.warning("MPRIS loop error!")
                        logger.warning(traceback.format_exc())

            DankoData.mpris_loop = GLib.MainLoop()
            mpris_thread = threading.Thread(target=mpris_loop_start)
            mpris_thread.start()

            class MPRISEventHandler:
                def on_metadata(self):
                    if (
                        DankoData.player
                        and DankoData.mpris_ready
                        and DankoData.mpris_running
                        and not DankoData.stopped
                    ):
                        (
                            playback_status,
                            mpris_trackid,
                            artUrl,
                            player_position,
                        ) = get_mpris_metadata()
                        execute_in_main_thread(
                            partial(
                                emit_mpris_change,
                                "org.mpris.MediaPlayer2.Player",
                                {
                                    "PlaybackStatus": GLib.Variant(
                                        "s", playback_status
                                    ),
                                    "Rate": GLib.Variant("d", DankoData.player.speed),
                                    "Metadata": GLib.Variant(
                                        "a{sv}",
                                        {
                                            "mpris:trackid": GLib.Variant(
                                                "o", mpris_trackid
                                            ),
                                            "mpris:artUrl": GLib.Variant("s", artUrl),
                                            "mpris:length": GLib.Variant(
                                                "x", player_position
                                            ),
                                            "xesam:url": GLib.Variant(
                                                "s", DankoData.playing_url
                                            ),
                                            "xesam:title": GLib.Variant(
                                                "s", DankoData.playing_channel
                                            ),
                                        },
                                    ),
                                },
                            )
                        )

                def on_playpause(self):
                    if (
                        DankoData.player
                        and DankoData.mpris_ready
                        and DankoData.mpris_running
                        and not DankoData.stopped
                    ):
                        (
                            playback_status,
                            mpris_trackid,
                            artUrl,
                            player_position,
                        ) = get_mpris_metadata()
                        execute_in_main_thread(
                            partial(
                                emit_mpris_change,
                                "org.mpris.MediaPlayer2.Player",
                                {"PlaybackStatus": GLib.Variant("s", playback_status)},
                            )
                        )

                def on_volume(self):
                    if (
                        DankoData.player
                        and DankoData.mpris_ready
                        and DankoData.mpris_running
                        and not DankoData.stopped
                    ):
                        execute_in_main_thread(
                            partial(
                                emit_mpris_change,
                                "org.mpris.MediaPlayer2.Player",
                                {
                                    "Volume": GLib.Variant(
                                        "d", float(DankoData.player.volume / 100)
                                    )
                                },
                            )
                        )

                def on_fullscreen(self):
                    if (
                        DankoData.player
                        and DankoData.mpris_ready
                        and DankoData.mpris_running
                        and not DankoData.stopped
                    ):
                        execute_in_main_thread(
                            partial(
                                emit_mpris_change,
                                "org.mpris.MediaPlayer2",
                                {"Fullscreen": GLib.Variant("b", DankoData.fullscreen)},
                            )
                        )

            DankoData.event_handler = MPRISEventHandler()
        except Exception:
            logger.warning(traceback.format_exc())
            logger.warning("Failed to set up MPRIS!")

        def update_scheduler_programme():
            channel_list_2 = [channel_name for channel_name in DankoData.array_sorted]
            ch_choosed = DankoGUI.choosechannel_ch.currentText()
            DankoGUI.tvguide_sch.clear()
            if ch_choosed in channel_list_2:
                tvguide_got = re.sub(
                    "<[^<]+?>", "", update_tvguide(ch_choosed, True)
                ).split("!@#$%^^&*(")[2:]
                for tvguide_el in tvguide_got:
                    if tvguide_el:
                        DankoGUI.tvguide_sch.addItem(tvguide_el)

        def show_scheduler():
            if DankoGUI.scheduler_win.isVisible():
                DankoGUI.scheduler_win.hide()
            else:
                DankoGUI.choosechannel_ch.clear()
                channel_list = [channel_name for channel_name in DankoData.array_sorted]
                for channel1 in channel_list:
                    DankoGUI.choosechannel_ch.addItem(channel1)
                if DankoData.item_selected in channel_list:
                    DankoGUI.choosechannel_ch.setCurrentIndex(
                        channel_list.index(DankoData.item_selected)
                    )
                DankoGUI.choosechannel_ch.currentIndexChanged.connect(
                    update_scheduler_programme
                )
                update_scheduler_programme()
                move_window_to_center(DankoGUI.scheduler_win)
                DankoGUI.scheduler_win.show()

        def mpv_volume_set_custom():
            mpv_volume_set()

        DankoGUI.btn_playpause.clicked.connect(mpv_play)
        DankoGUI.btn_stop.clicked.connect(mpv_stop)
        DankoGUI.btn_fullscreen.clicked.connect(mpv_fullscreen)
        DankoGUI.btn_open_recordings_folder.clicked.connect(open_recording_folder_async)
        DankoGUI.btn_record.clicked.connect(do_record)
        DankoGUI.btn_show_scheduler.clicked.connect(show_scheduler)
        DankoGUI.btn_volume.clicked.connect(mpv_mute)
        DankoGUI.volume_slider.valueChanged.connect(mpv_volume_set_custom)
        DankoGUI.btn_screenshot.clicked.connect(do_screenshot)
        DankoGUI.btn_show_archive.clicked.connect(show_archive)
        DankoGUI.btn_multiepg.clicked.connect(show_multi_epg)
        DankoGUI.btn_tv_guide.clicked.connect(show_tvguide)
        DankoGUI.btn_prev_channel.clicked.connect(prev_channel)
        DankoGUI.btn_next_channel.clicked.connect(next_channel)

        dockWidget_controlPanel.setTitleBarWidget(QtWidgets.QWidget())
        dockWidget_controlPanel.setWidget(DankoGUI.controlpanel_dock_widget)
        dockWidget_controlPanel.setFloating(False)
        dockWidget_controlPanel.setFixedHeight(DOCKWIDGET_CONTROLPANEL_HEIGHT_HIGH)
        dockWidget_controlPanel.setFeatures(
            QtWidgets.QDockWidget.DockWidgetFeature.NoDockWidgetFeatures
        )
        win.addDockWidget(
            QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, dockWidget_controlPanel
        )

        DankoGUI.progress.hide()
        DankoGUI.start_label.hide()
        DankoGUI.stop_label.hide()
        dockWidget_controlPanel.setFixedHeight(DOCKWIDGET_CONTROLPANEL_HEIGHT_LOW)

        DankoData.state = QtWidgets.QLabel(win)
        DankoData.state.setStyleSheet("background-color: #a2a3a3;")
        DankoData.state.setFont(DankoGUI.font_12_bold)
        DankoData.state.setWordWrap(True)
        DankoData.state.move(50, 50)
        DankoData.state.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        DankoGUI.set_widget_opacity(DankoData.state, DankoGUI.DEFAULT_OPACITY)

        class Slider(QtWidgets.QSlider):
            def getRewindTime(self):
                s_start = None
                s_stop = None
                s_index = None
                if DankoData.archive_epg:
                    s_start = datetime.datetime.strptime(
                        DankoData.archive_epg[1], "%d.%m.%Y %H:%M:%S"
                    ).timestamp()
                    s_stop = datetime.datetime.strptime(
                        DankoData.archive_epg[2], "%d.%m.%Y %H:%M:%S"
                    ).timestamp()
                    s_index = DankoData.archive_epg[3]
                else:
                    if get_epg_url() and DankoData.playing_channel:
                        prog1 = None
                        epg_id = get_epg_id(DankoData.playing_channel)
                        if epg_id:
                            programmes = get_epg_programmes(epg_id)
                            if programmes:
                                prog1 = programmes
                        if prog1:
                            for pr in prog1:
                                if (
                                    time.time() > pr["start"]
                                    and time.time() < pr["stop"]
                                ):
                                    s_start = pr["start"]
                                    s_stop = (
                                        datetime.datetime.now().timestamp()
                                    )  # pr["stop"]
                                    s_index = prog1.index(pr)
                if not s_start:
                    return None
                return (
                    s_start + (self.value() / 100) * (s_stop - s_start),
                    s_stop,
                    s_index,
                )

            def mouseMoveEvent(self, event1):
                if DankoData.playing_channel:
                    rewind_time = self.getRewindTime()
                    if rewind_time:
                        QtWidgets.QToolTip.showText(
                            self.mapToGlobal(event1.pos()),
                            datetime.datetime.fromtimestamp(rewind_time[0]).strftime(
                                "%H:%M:%S"
                            ),
                        )
                super().mouseMoveEvent(event1)

            def doMouseReleaseEvent(self):
                if DankoData.playing_channel:
                    QtWidgets.QToolTip.hideText()
                    rewind_time = self.getRewindTime()
                    if rewind_time:
                        DankoData.rewind_value = self.value()
                        do_open_archive(
                            "#__rewind__#__archive__"
                            + urllib.parse.quote_plus(
                                json.dumps(
                                    [
                                        DankoData.playing_channel,
                                        datetime.datetime.fromtimestamp(
                                            rewind_time[0]
                                        ).strftime("%d.%m.%Y %H:%M:%S"),
                                        datetime.datetime.fromtimestamp(
                                            rewind_time[1]
                                        ).strftime("%d.%m.%Y %H:%M:%S"),
                                        rewind_time[2],
                                        True,
                                    ]
                                )
                            )
                        )

            def mouseReleaseEvent(self, event1):
                self.doMouseReleaseEvent()
                super().mouseReleaseEvent(event1)

        DankoGUI.create_rewind(Slider)

        def set_text_state(text="", is_previous=False):
            if is_previous:
                text = DankoData.previous_text
            else:
                DankoData.previous_text = text
            if DankoData.gl_is_static:
                br = "    "
                if not text or not DankoData.static_text:
                    br = ""
                text = DankoData.static_text + br + text
            win.update()
            DankoData.state.setText(text)

        def set_text_static(is_static):
            DankoData.static_text = ""
            DankoData.gl_is_static = is_static

        DankoData.state.setTextDanko = set_text_state
        DankoData.state.setStaticDanko = set_text_static
        DankoData.state.hide()

        def getUserAgent():
            try:
                userAgent2 = DankoData.player.user_agent
            except Exception:
                userAgent2 = default_user_agent
            return userAgent2

        def saveLastChannel():
            if DankoData.playing_url and playmode_selector.currentIndex() == 0:
                current_group_0 = 0
                if DankoData.combobox.currentIndex() != 0:
                    try:
                        current_group_0 = groups.index(
                            DankoData.array[DankoData.playing_channel]["tvg-group"]
                        )
                    except Exception:
                        pass
                current_channel_0 = 0
                try:
                    current_channel_0 = win.listWidget.currentRow()
                except Exception:
                    pass
                lastfile = open(
                    str(Path(LOCAL_DIR, "lastchannels.json")), "w", encoding="utf8"
                )
                lastfile.write(
                    json.dumps(
                        [
                            DankoData.playing_channel,
                            DankoData.playing_url,
                            getUserAgent(),
                            current_group_0,
                            current_channel_0,
                        ]
                    )
                )
                lastfile.close()
            else:
                if os.path.isfile(str(Path(LOCAL_DIR, "lastchannels.json"))):
                    os.remove(str(Path(LOCAL_DIR, "lastchannels.json")))

        def cur_win_width():
            w1_width = 0
            for app_scr in app.screens():
                w1_width += app_scr.size().width()
            return w1_width

        def cur_win_height():
            w1_height = 0
            for app_scr in app.screens():
                w1_height += app_scr.size().height()
            return w1_height

        def myExitHandler_before():
            try:
                for broken_logo in DankoData.broken_logos:
                    if os.path.isfile(broken_logo):
                        os.remove(broken_logo)
                channel_logos = os.listdir(Path(CACHE_DIR, "logo"))
                for channel_logo in channel_logos:
                    if os.path.isfile(
                        Path(CACHE_DIR, "logo", channel_logo)
                    ) and channel_logo.endswith(".png"):
                        os.remove(Path(CACHE_DIR, "logo", channel_logo))
                if DankoData.epg_pool:
                    try:
                        DankoData.epg_pool.close()
                        DankoData.epg_pool = None
                    except Exception:
                        pass
                uninhibit()
                if DankoData.comboboxIndex != -1:
                    write_option(
                        "comboboxindex",
                        {
                            "m3u": DankoData.settings["m3u"],
                            "index": DankoData.comboboxIndex,
                        },
                    )
                try:
                    if get_first_run():
                        write_option("vf_filters", get_active_vf_filters())
                except Exception:
                    pass
                try:
                    if not DankoData.first_start:
                        write_option(
                            "window",
                            {
                                "x": win.geometry().x(),
                                "y": win.geometry().y(),
                                "w": win.width(),
                                "h": win.height(),
                            },
                        )
                        if DankoData.settings["panelposition"] == 2:
                            write_option(
                                "separate_playlist",
                                {
                                    "x": dockWidget_playlist.geometry().x(),
                                    "y": dockWidget_playlist.geometry().y(),
                                    "w": dockWidget_playlist.width(),
                                    "h": dockWidget_playlist.height(),
                                },
                            )
                except Exception:
                    pass
                try:
                    write_option(
                        "compactstate",
                        {
                            "compact_mode": DankoData.compact_mode,
                            "playlist_hidden": DankoData.playlist_hidden,
                            "controlpanel_hidden": DankoData.controlpanel_hidden,
                        },
                    )
                except Exception:
                    pass
                try:
                    if DankoGUI.save_fullscreenPlaylistWidth:
                        write_option(
                            "fullscreen_playlist_width",
                            DankoGUI.save_fullscreenPlaylistWidth,
                        )
                    if DankoGUI.save_fullscreenPlaylistHeight:
                        write_option(
                            "fullscreen_playlist_height",
                            DankoGUI.save_fullscreenPlaylistHeight,
                        )
                except Exception:
                    pass
                try:
                    write_option("volume", int(DankoData.volume))
                except Exception:
                    pass
                save_player_tracks()
                saveLastChannel()
                stop_record()
                for rec_1 in sch_recordings:
                    do_stop_record(rec_1)
                if DankoData.mpris_loop:
                    DankoData.mpris_running = False
                    DankoData.mpris_loop.quit()
                DankoData.stopped = True
                if multiprocessing_manager:
                    multiprocessing_manager.shutdown()
                for process_3 in active_children():
                    try:
                        process_3.kill()
                    except Exception:
                        try:
                            process_3.terminate()
                        except Exception:
                            pass
            except Exception:
                logger.warning(traceback.format_exc())
            exit_handler()

        def myExitHandler():
            myExitHandler_before()
            if not DankoData.do_save_settings:
                sys.exit(0)

        def get_catchup_days(is_seconds=False):
            try:
                catchup_days1 = min(
                    max(
                        1,
                        max(
                            int(DankoData.array[xc1]["catchup-days"])
                            for xc1 in DankoData.array
                            if "catchup-days" in DankoData.array[xc1]
                        ),
                    ),
                    7,
                )
            except Exception:
                catchup_days1 = 7
            if is_seconds:
                catchup_days1 = 86400 * (catchup_days1 + 1)
            return catchup_days1

        logger.info(f"catchup-days = {get_catchup_days()}")

        def timer_channels_redraw():
            DankoData.ic += 0.1

            # redraw every 15 seconds
            if DankoData.ic > (
                14.9 if not DankoData.mp_manager_dict["logos_inprogress"] else 2.9
            ):
                DankoData.ic = 0
                execute_in_main_thread(partial(redraw_channels))
            DankoData.ic3 += 0.1

            if DankoData.ic3 > (
                14.9 if not DankoData.mp_manager_dict["logosmovie_inprogress"] else 2.9
            ):
                DankoData.ic3 = 0
                update_movie_icons()

        def thread_tvguide_update_start():
            DankoData.state.setStaticDanko(True)
            DankoData.state.show()
            DankoData.static_text = _("Updating TV guide...")
            DankoData.state.setTextDanko("")
            DankoData.time_stop = time.time() + 3

        def thread_tvguide_update_error():
            DankoData.static_text = ""
            DankoData.state.setStaticDanko(False)
            DankoData.state.show()
            DankoData.state.setTextDanko(_("TV guide update error!"))
            DankoData.time_stop = time.time() + 3

        def thread_tvguide_update_outdated():
            DankoData.static_text = ""
            DankoData.state.setStaticDanko(False)
            DankoData.state.show()
            DankoData.state.setTextDanko(_("EPG is outdated!"))
            DankoData.time_stop = time.time() + 3

        def thread_tvguide_update_end():
            DankoData.static_text = ""
            DankoData.state.setStaticDanko(False)
            DankoData.state.show()
            DankoData.state.setTextDanko(_("TV guide update done!"))
            DankoData.time_stop = time.time() + 0.5

        def timer_record():
            try:
                DankoData.ic1 += 0.1
                if DankoData.ic1 > 0.9:
                    DankoData.ic1 = 0
                    # executing every second
                    if DankoData.is_recording:
                        if not DankoData.recording_time:
                            DankoData.recording_time = time.time()
                        record_time = format_seconds(
                            time.time() - DankoData.recording_time
                        )
                        if os.path.isfile(DankoData.record_file):
                            record_size = convert_size(
                                os.path.getsize(DankoData.record_file)
                            )
                            DankoGUI.lbl2.setText(
                                "REC " + record_time + " - " + record_size
                            )
                        else:
                            DankoData.recording_time = time.time()
                            DankoGUI.lbl2.setText(_("Waiting for record"))
                win.update()
                if (time.time() > DankoData.time_stop) and DankoData.time_stop != 0:
                    DankoData.time_stop = 0
                    if not DankoData.gl_is_static:
                        DankoData.state.hide()
                        win.update()
                    else:
                        DankoData.state.setTextDanko("")
            except Exception:
                pass

        def do_reconnect_stream():
            # Último recurso: el motor seamless (eof-reached + cascade) es el
            # mecanismo primario; este poller solo actúa tras 30s de buffer
            # agotado (antes 5s, causaba reloads prematuros).
            if DankoData._seamless_reloading:
                DankoData.x_conn = None
                return
            if (DankoData.playing_channel and not DankoData.is_loading) and (
                DankoData.player.cache_buffering_state == 0
            ):
                logger.info("Reconnecting to stream (buffer exhausted 30s)")
                try:
                    doPlay(*DankoData.do_play_args)
                except Exception:
                    logger.warning("Failed reconnecting to stream - no known URL")
            DankoData.x_conn = None

        def check_connection():
            if DankoData.settings["autoreconnection"]:
                if DankoData.playing_group == 0:
                    if not DankoData.connprinted:
                        DankoData.connprinted = True
                        logger.info("Connection loss detector enabled")
                    try:
                        if (
                            DankoData.playing_channel and not DankoData.is_loading
                        ) and DankoData.player.cache_buffering_state == 0:
                            if not DankoData.x_conn:
                                logger.warning(
                                    "Connection to stream lost, waiting 30 secs..."
                                )
                                DankoData.x_conn = QtCore.QTimer()
                                DankoData.x_conn.timeout.connect(do_reconnect_stream)
                                DankoData.x_conn.start(30000)
                    except Exception:
                        logger.warning("Failed to set connection loss detector!")
            else:
                if not DankoData.connprinted:
                    DankoData.connprinted = True
                    logger.info("Connection loss detector disabled")

        def timer_check_tvguide_obsolete():
            try:
                if win.isVisible():
                    check_connection()
                    try:
                        if DankoData.player.video_bitrate:
                            bitrate_arr = [
                                _("bps") + " ",
                                _("kbps"),
                                _("Mbps"),
                                _("Gbps"),
                                _("Tbps"),
                            ]
                            video_bitrate = " - " + str(
                                format_bytes(DankoData.player.video_bitrate, bitrate_arr)
                            )
                        else:
                            video_bitrate = ""
                    except Exception:
                        video_bitrate = ""
                    try:
                        audio_codec = DankoData.player.audio_codec.split(" ")[0].strip()
                    except Exception:
                        audio_codec = "no audio"
                    try:
                        codec = DankoData.player.video_codec.split(" ")[0].strip()
                        width = DankoData.player.width
                        height = DankoData.player.height
                    except Exception:
                        codec = "png"
                        width = 800
                        height = 600
                    if DankoData.player.avsync:
                        avsync = str(round(DankoData.player.avsync, 2))
                        deavsync = round(DankoData.player.avsync, 2)
                        if deavsync < 0:
                            deavsync = deavsync * -1
                        if deavsync > 0.999:
                            avsync = f"<span style='color: #B58B00;'>{avsync}</span>"
                    else:
                        avsync = "0.0"
                    if (
                        not (codec.lower() == "png" and width == 800 and height == 600)
                    ) and (width and height):
                        if DankoData.settings["hidebitrateinfo"]:
                            DankoGUI.label_video_data.setText("")
                            DankoGUI.label_avsync.setText("")
                        else:
                            DankoGUI.label_video_data.setText(
                                f"  {width}x{height}"
                                f" - {codec} / {audio_codec}{video_bitrate} -"
                            )
                            DankoGUI.label_avsync.setText(f"A-V {avsync}")
                        if loading.text() == _("Loading..."):
                            hideLoading()
                    else:
                        DankoGUI.label_video_data.setText("")
                        DankoGUI.label_avsync.setText("")
                    DankoData.ic2 += 0.1
                    if DankoData.ic2 > 29.9:
                        DankoData.ic2 = 0
                        if (
                            get_epg_url()
                            and not DankoData.epg_pool_running
                            and not DankoData.epg_failed
                        ):
                            is_actual = True
                            if DankoData.epg_update_date != 0:
                                is_actual = (
                                    time.time() - DankoData.epg_update_date
                                ) < 86400  # 1 day
                            if not check_programmes_actual() or not is_actual:
                                logger.info("EPG is outdated, updating it...")
                                purge_epg_cache()
                                thread_epg_update_3 = threading.Thread(
                                    target=epg_update, daemon=True
                                )
                                thread_epg_update_3.start()
            except Exception:
                pass

        def timer_tvguide_progress():
            try:
                if not DankoData.thread_tvguide_progress_lock:
                    DankoData.thread_tvguide_progress_lock = True
                    try:
                        if DankoData.epg_pool_running:
                            if (
                                "epg_progress" in DankoData.mp_manager_dict
                                and DankoData.mp_manager_dict["epg_progress"]
                            ):
                                DankoData.static_text = DankoData.mp_manager_dict[
                                    "epg_progress"
                                ]
                                DankoData.state.setTextDanko(is_previous=True)
                    except Exception:
                        pass
                    DankoData.thread_tvguide_progress_lock = False
            except Exception:
                pass

        def timer_update_time():
            try:
                DankoGUI.scheduler_clock.setText(get_current_time())
            except Exception:
                pass

        def timer_osc():
            try:
                if win.isVisible():
                    if DankoData.playing_url:
                        try:
                            if not DankoData.force_turnoff_osc:
                                set_mpv_osc(True)
                            else:
                                set_mpv_osc(False)
                        except Exception:
                            pass
                    else:
                        try:
                            set_mpv_osc(False)
                        except Exception:
                            pass
            except Exception:
                pass

        dockWidget_playlist.installEventFilter(win)

        DankoData.prev_cursor = QtGui.QCursor.pos()

        def timer_cursor():
            show_cursor = False
            cursor_offset = (
                QtGui.QCursor.pos().x()
                - DankoData.prev_cursor.x()
                + QtGui.QCursor.pos().y()
                - DankoData.prev_cursor.y()
            )
            if cursor_offset < 0:
                cursor_offset = cursor_offset * -1
            if cursor_offset > 5:
                DankoData.prev_cursor = QtGui.QCursor.pos()
                if (time.time() - DankoData.last_cursor_moved) > 0.3:
                    DankoData.last_cursor_moved = time.time()
                    DankoData.last_cursor_time = time.time() + 1
                    show_cursor = True
            show_cursor_really = True
            if not show_cursor:
                show_cursor_really = time.time() < DankoData.last_cursor_time
            if DankoData.fullscreen:
                try:
                    if show_cursor_really:
                        win.container.unsetCursor()
                    else:
                        win.container.setCursor(QtCore.Qt.CursorShape.BlankCursor)
                except Exception:
                    pass
            else:
                try:
                    win.container.unsetCursor()
                except Exception:
                    pass

        class SizeGrip(QtWidgets.QSizeGrip):
            def mousePressEvent(self, event):
                DankoGUI.playlistFullscreenIsResized = True
                super().mousePressEvent(event)

            def mouseReleaseEvent(self, mouseEvent):
                DankoGUI.playlistFullscreenIsResized = False
                super().mouseReleaseEvent(mouseEvent)
                DankoGUI.fullscreenPlaylistWidth = DankoGUI.playlist_widget.width()
                DankoGUI.fullscreenPlaylistHeight = DankoGUI.playlist_widget.height()
                DankoGUI.save_fullscreenPlaylistWidth = DankoGUI.fullscreenPlaylistWidth
                DankoGUI.save_fullscreenPlaylistHeight = DankoGUI.fullscreenPlaylistHeight

        sizeGrip = SizeGrip(DankoGUI.playlist_widget)

        def show_playlist_fullscreen():
            if not DankoGUI.fullscreenPlaylistHeight:
                DankoGUI.fullscreenPlaylistHeight = win.height() - 50

            if DankoData.settings["panelposition"] in (0, 2):
                DankoGUI.playlist_widget.move(
                    win.mapToGlobal(
                        QtCore.QPoint(win.width() - DankoGUI.fullscreenPlaylistWidth, 0)
                    )
                )
            else:
                DankoGUI.playlist_widget.move(win.mapToGlobal(QtCore.QPoint(0, 0)))

            DankoGUI.playlist_widget.resize(
                DankoGUI.fullscreenPlaylistWidth, DankoGUI.fullscreenPlaylistHeight
            )

            if DankoData.settings["enabletransparency"]:
                DankoGUI.playlist_widget.setWindowOpacity(0.75)
            DankoGUI.playlist_widget.setWindowFlags(
                QtCore.Qt.WindowType.CustomizeWindowHint
                | QtCore.Qt.WindowType.FramelessWindowHint
                | QtCore.Qt.WindowType.X11BypassWindowManagerHint
            )
            DankoGUI.pl_layout.addWidget(DankoGUI.widget)
            DankoGUI.pl_layout.addWidget(
                sizeGrip,
                0,
                QtCore.Qt.AlignmentFlag.AlignBottom | QtCore.Qt.AlignmentFlag.AlignLeft,
            )
            DankoGUI.playlist_widget.show()

        def hide_playlist_fullscreen():
            DankoGUI.pl_layout.removeWidget(DankoGUI.widget)
            DankoGUI.pl_layout.removeWidget(sizeGrip)
            dockWidget_playlist.setWidget(DankoGUI.widget)
            DankoGUI.playlist_widget.hide()

        def resizeandmove_controlpanel():
            lb2_width = 0
            DankoGUI.controlpanel_widget.setFixedWidth(
                win.screen().availableGeometry().width()
            )
            for lb2_wdg in DankoGUI.show_lbls_fullscreen:
                if (
                    DankoGUI.controlpanel_layout.indexOf(lb2_wdg) != -1
                    and lb2_wdg.isVisible()
                ):
                    lb2_width += lb2_wdg.width() + 10
            DankoGUI.controlpanel_widget.setFixedWidth(lb2_width + 30)
            p_3 = (
                win.container.frameGeometry().center()
                - QtCore.QRect(
                    QtCore.QPoint(), DankoGUI.controlpanel_widget.sizeHint()
                ).center()
            )
            DankoGUI.controlpanel_widget.move(
                win.mapToGlobal(QtCore.QPoint(p_3.x() - 100, win.height() - 100))
            )

        def show_controlpanel_fullscreen():
            if not DankoData.VOLUME_SLIDER_WIDTH:
                DankoData.VOLUME_SLIDER_WIDTH = DankoGUI.volume_slider.width()
            DankoGUI.volume_slider.setFixedWidth(DankoData.VOLUME_SLIDER_WIDTH)
            if DankoData.settings["enabletransparency"]:
                DankoGUI.controlpanel_widget.setWindowOpacity(0.75)
            if DankoGUI.channelfilter.usePopup:
                DankoGUI.controlpanel_widget.setWindowFlags(
                    QtCore.Qt.WindowType.CustomizeWindowHint
                    | QtCore.Qt.WindowType.FramelessWindowHint
                    | QtCore.Qt.WindowType.X11BypassWindowManagerHint
                    | QtCore.Qt.WindowType.Popup
                )
            else:
                DankoGUI.controlpanel_widget.setWindowFlags(
                    QtCore.Qt.WindowType.CustomizeWindowHint
                    | QtCore.Qt.WindowType.FramelessWindowHint
                    | QtCore.Qt.WindowType.X11BypassWindowManagerHint
                )
            DankoGUI.cp_layout.addWidget(DankoGUI.controlpanel_dock_widget)
            resizeandmove_controlpanel()
            DankoGUI.controlpanel_widget.show()
            resizeandmove_controlpanel()

        def hide_controlpanel_fullscreen():
            if DankoData.VOLUME_SLIDER_WIDTH:
                DankoGUI.volume_slider.setFixedWidth(DankoData.VOLUME_SLIDER_WIDTH)
            DankoGUI.cp_layout.removeWidget(DankoGUI.controlpanel_dock_widget)
            dockWidget_controlPanel.setWidget(DankoGUI.controlpanel_dock_widget)
            DankoGUI.controlpanel_widget.hide()
            DankoGUI.rewind.hide()

        def timer_afterrecord():
            try:
                cur_recording = False
                if not DankoGUI.lbl2.isVisible():
                    if "REC / " not in DankoGUI.lbl2.text():
                        cur_recording = is_ffmpeg_recording() is False
                    else:
                        cur_recording = is_recording_func() is not True
                    if cur_recording:
                        showLoading2()
                    else:
                        hideLoading2()
            except Exception:
                pass

        def timer_shortcuts():
            try:
                if not DankoData.fullscreen:
                    menubar_new_st = win.menuBar().isVisible()
                    if menubar_new_st != DankoData.menubar_state:
                        DankoData.menubar_state = menubar_new_st
                        if DankoData.menubar_state:
                            setShortcutState(False)
                        else:
                            setShortcutState(True)
            except Exception:
                pass

        def timer_mouse():
            try:
                if win.isVisible():
                    if (
                        DankoData.state.isVisible()
                        and DankoData.state.text().startswith(_("Volume"))
                        and not is_show_volume()
                    ):
                        DankoData.state.hide()
                    DankoGUI.label_volume.setText(f"{int(DankoData.player.volume)}%")
                    if DankoData.settings["panelposition"] != 2:
                        dockWidget_playlist.setFixedWidth(DOCKWIDGET_PLAYLIST_WIDTH)
                    if DankoData.fullscreen:
                        cur_pos = QtGui.QCursor.pos()
                        is_inside_window = (
                            (
                                cur_pos.x() > win.pos().x() - 1
                                and cur_pos.x() < (win.pos().x() + win.width())
                            )
                            and (
                                cur_pos.y() > win.pos().y() - 1
                                and cur_pos.y() < (win.pos().y() + win.height())
                            )
                            and (win.hasFocus() or DankoData.dockWidget_playlistVisible)
                        )

                        cursor_x = win.container.mapFromGlobal(QtGui.QCursor.pos()).x()
                        win_width = win.width()
                        if DankoData.settings["panelposition"] in (0, 2):
                            is_cursor_x = cursor_x > win_width - (
                                DankoGUI.fullscreenPlaylistWidth + 10
                            )
                        else:
                            is_cursor_x = cursor_x < (
                                DankoGUI.fullscreenPlaylistWidth + 10
                            )
                        if (
                            is_cursor_x and cursor_x < win_width and is_inside_window
                        ) or DankoGUI.playlistFullscreenIsResized:
                            if not DankoData.dockWidget_playlistVisible:
                                DankoData.dockWidget_playlistVisible = True
                                show_playlist_fullscreen()
                        else:
                            DankoData.dockWidget_playlistVisible = False
                            hide_playlist_fullscreen()

                        cursor_y = win.container.mapFromGlobal(QtGui.QCursor.pos()).y()
                        win_height = win.height()
                        is_cursor_y = cursor_y > win_height - (
                            dockWidget_controlPanel.height() + 250
                        )
                        if is_cursor_y and cursor_y < win_height and is_inside_window:
                            if not DankoData.dockWidget_controlPanelVisible:
                                DankoData.dockWidget_controlPanelVisible = True
                                show_controlpanel_fullscreen()
                        else:
                            DankoData.dockWidget_controlPanelVisible = False
                            hide_controlpanel_fullscreen()
                    if DankoData.settings["rewindenable"]:
                        cur_pos = QtGui.QCursor.pos()
                        is_inside_window = (
                            cur_pos.x() > win.pos().x() - 1
                            and cur_pos.x() < (win.pos().x() + win.width())
                        ) and (
                            cur_pos.y() > win.pos().y() - 1
                            and cur_pos.y() < (win.pos().y() + win.height())
                        )

                        cursor_y = win.container.mapFromGlobal(QtGui.QCursor.pos()).y()
                        win_height = win.height()
                        is_cursor_y = cursor_y > win_height - (
                            dockWidget_controlPanel.height() + 250
                        )
                        if (
                            is_cursor_y
                            and cursor_y < win_height
                            and is_inside_window
                            and DankoData.playing_channel
                            and DankoData.playing_channel in DankoData.array
                            and DankoData.current_prog1
                            and not DankoData.check_playlist_visible
                            and not DankoData.check_controlpanel_visible
                        ):
                            if not DankoData.rewindWidgetVisible:
                                DankoData.rewindWidgetVisible = True
                                win.resize_rewind()
                                DankoGUI.rewind.show()
                        else:
                            DankoData.rewindWidgetVisible = False
                            if DankoGUI.rewind.isVisible():
                                if DankoData.rewind_value:
                                    if (
                                        DankoData.rewind_value
                                        != DankoGUI.rewind_slider.value()
                                    ):
                                        DankoGUI.rewind_slider.doMouseReleaseEvent()
                                DankoGUI.rewind.hide()
            except Exception:
                pass

        def idle_show_hide_playlist():
            if not DankoData.fullscreen:
                if dockWidget_playlist.isVisible():
                    DankoData.playlist_hidden = True
                    dockWidget_playlist.hide()
                else:
                    DankoData.playlist_hidden = False
                    dockWidget_playlist.show()

        def show_hide_playlist():
            execute_in_main_thread(partial(idle_show_hide_playlist))

        def lowpanel_ch():
            if dockWidget_controlPanel.isVisible():
                DankoData.controlpanel_hidden = True
                dockWidget_controlPanel.hide()
            else:
                DankoData.controlpanel_hidden = False
                dockWidget_controlPanel.show()

        def key_quit():
            DankoGUI.settings_win.close()
            DankoGUI.shortcuts_win.close()
            DankoGUI.shortcuts_win_2.close()
            win.close()
            DankoGUI.help_win.close()
            DankoGUI.streaminfo_win.close()
            DankoGUI.license_win.close()
            myExitHandler()
            app.quit()

        def dockwidget_controlpanel_resize_timer():
            try:
                if DankoGUI.start_label.text() and DankoGUI.start_label.isVisible():
                    if (
                        dockWidget_controlPanel.height()
                        != DOCKWIDGET_CONTROLPANEL_HEIGHT_HIGH
                    ):
                        dockWidget_controlPanel.setFixedHeight(
                            DOCKWIDGET_CONTROLPANEL_HEIGHT_HIGH
                        )
                else:
                    if (
                        dockWidget_controlPanel.height()
                        != DOCKWIDGET_CONTROLPANEL_HEIGHT_LOW
                    ):
                        dockWidget_controlPanel.setFixedHeight(
                            DOCKWIDGET_CONTROLPANEL_HEIGHT_LOW
                        )
            except Exception:
                pass

        def set_playback_speed(spd):
            try:
                logger.info(f"Set speed to {spd}")
                DankoData.player.speed = spd
                try:
                    DankoData.event_handler.on_metadata()
                except Exception:
                    pass
            except Exception:
                logger.warning("set_playback_speed failed")

        def mpv_seek(secs):
            try:
                if DankoData.playing_channel:
                    logger.info(f"Seeking to {secs} seconds")
                    DankoData.player.command("seek", secs)
            except Exception:
                logger.warning("mpv_seek failed")

        def mpv_frame_step():
            logger.info("frame-step")
            DankoData.player.command("frame-step")

        def mpv_frame_back_step():
            logger.info("frame-back-step")
            DankoData.player.command("frame-back-step")

        funcs = {
            "show_sort": show_sort,
            "key_t": show_hide_playlist,
            "esc_handler": esc_handler,
            "mpv_fullscreen": mpv_fullscreen,
            "mpv_fullscreen_2": mpv_fullscreen,
            "open_stream_info": open_stream_info,
            "mpv_mute": mpv_mute,
            "key_quit": key_quit,
            "mpv_play": mpv_play,
            "mpv_stop": mpv_stop,
            "do_screenshot": do_screenshot,
            "show_tvguide": show_tvguide,
            "do_record": do_record,
            "prev_channel": prev_channel,
            "next_channel": next_channel,
            "(lambda: my_up_binding())": (lambda: my_up_binding_execute()),
            "(lambda: my_down_binding())": (lambda: my_down_binding_execute()),
            "show_timeshift": show_archive,
            "show_scheduler": show_scheduler,
            "showhideeverything": showhideeverything,
            "show_settings": show_settings,
            "(lambda: set_playback_speed(1.00))": (lambda: set_playback_speed(1.00)),
            "app.quit": app.quit,
            "show_playlists": show_playlists,
            "reload_playlist": reload_playlist,
            "force_update_epg": force_update_epg_act,
            "main_channel_settings": main_channel_settings,
            "show_m3u_editor": show_playlist_editor,
            "my_down_binding_execute": my_down_binding_execute,
            "my_up_binding_execute": my_up_binding_execute,
            "(lambda: mpv_seek(-10))": (lambda: mpv_seek(-10)),
            "(lambda: mpv_seek(10))": (lambda: mpv_seek(10)),
            "(lambda: mpv_seek(-60))": (lambda: mpv_seek(-60)),
            "(lambda: mpv_seek(60))": (lambda: mpv_seek(60)),
            "(lambda: mpv_seek(-600))": (lambda: mpv_seek(-600)),
            "(lambda: mpv_seek(600))": (lambda: mpv_seek(600)),
            "lowpanel_ch_1": lowpanel_ch_1,
            "show_tvguide_2": show_tvguide_2,
            "show_multi_epg": show_multi_epg,
            "do_record_1_INTERNAL": do_record,
            "mpv_mute_1_INTERNAL": mpv_mute,
            "mpv_play_1_INTERNAL": mpv_play,
            "mpv_play_2_INTERNAL": mpv_play,
            "mpv_play_3_INTERNAL": mpv_play,
            "mpv_play_4_INTERNAL": mpv_play,
            "mpv_stop_1_INTERNAL": mpv_stop,
            "mpv_stop_2_INTERNAL": mpv_stop,
            "next_channel_1_INTERNAL": next_channel,
            "prev_channel_1_INTERNAL": prev_channel,
            "(lambda: my_up_binding())_INTERNAL": (lambda: my_up_binding_execute()),
            "(lambda: my_down_binding())_INTERNAL": (lambda: my_down_binding_execute()),
            "mpv_frame_step": mpv_frame_step,
            "mpv_frame_back_step": mpv_frame_back_step,
        }

        if os.path.isfile(str(Path(LOCAL_DIR, "hotkeys.json"))):
            try:
                with open(
                    str(Path(LOCAL_DIR, "hotkeys.json")), encoding="utf8"
                ) as hotkeys_file_tmp:
                    hotkeys_tmp = json.loads(hotkeys_file_tmp.read())[
                        "current_profile"
                    ]["keys"]
                    DankoData.main_keybinds = hotkeys_tmp
                    logger.info("hotkeys.json found, using it as hotkey settings")
            except Exception:
                logger.warning("failed to read hotkeys.json, using default shortcuts")
                DankoData.main_keybinds = main_keybinds_default.copy()
        else:
            logger.info("No hotkeys.json found, using default hotkeys")
            DankoData.main_keybinds = main_keybinds_default.copy()

        seq = get_seq()

        def setShortcutState(st1):
            DankoData.shortcuts_state = st1
            for shortcut_arr in shortcuts:
                for shortcut in shortcuts[shortcut_arr]:
                    if shortcut.key() in seq:
                        shortcut.setEnabled(st1)

        def reload_keybinds():
            for shortcut_1 in shortcuts:
                if not shortcut_1.endswith("_INTERNAL"):
                    sc_new_keybind = QtGui.QKeySequence(get_keybind(shortcut_1))
                    for shortcut_2 in shortcuts[shortcut_1]:
                        shortcut_2.setKey(sc_new_keybind)
            reload_menubar_shortcuts()

        all_keybinds = DankoData.main_keybinds.copy()
        all_keybinds.update(main_keybinds_internal)
        for kbd in all_keybinds:
            if kbd in funcs:
                shortcuts[kbd] = [
                    # Main window
                    QtGui.QShortcut(
                        QtGui.QKeySequence(all_keybinds[kbd]), win, activated=funcs[kbd]
                    ),
                    # Control panel widget
                    QtGui.QShortcut(
                        QtGui.QKeySequence(all_keybinds[kbd]),
                        DankoGUI.controlpanel_widget,
                        activated=funcs[kbd],
                    ),
                    # Playlist widget
                    QtGui.QShortcut(
                        QtGui.QKeySequence(all_keybinds[kbd]),
                        DankoGUI.playlist_widget,
                        activated=funcs[kbd],
                    ),
                ]
            else:
                logger.warning(f"Unknown keybind {kbd}!")
        all_keybinds = False

        setShortcutState(False)

        app.aboutToQuit.connect(myExitHandler)

        vol_remembered = 100
        volume_option = read_option("volume")
        if volume_option is not None:
            vol_remembered = int(volume_option)
            DankoData.volume = vol_remembered

        def restore_compact_state():
            try:
                compactstate = read_option("compactstate")
                if compactstate:
                    if compactstate["compact_mode"]:
                        showhideeverything()
                    else:
                        if compactstate["playlist_hidden"]:
                            show_hide_playlist()
                        if compactstate["controlpanel_hidden"]:
                            lowpanel_ch()
            except Exception:
                pass

        def epg_update():
            if get_epg_url():
                if DankoData.epg_pool_running:
                    logger.info("EPG already updating")
                else:
                    if DankoData.first_boot:
                        DankoData.first_boot = False
                        if DankoData.settings["donotupdateepg"]:
                            logger.info("EPG update at boot disabled")
                            return

                    DankoData.epg_update_date = time.time()
                    DankoData.epg_pool_running = True
                    execute_in_main_thread(partial(thread_tvguide_update_start))

                    DankoData.epg_pool = get_context("spawn").Pool(1)
                    (
                        epg_failed,
                        epg_outdated,
                        DankoData.epg_array,
                    ) = DankoData.epg_pool.apply(
                        epg_worker,
                        (
                            get_epg_url(),
                            DankoData.settings,
                            DankoData.mp_manager_dict,
                        ),
                    )

                    DankoData.epg_pool.close()
                    DankoData.epg_pool = None

                    if epg_outdated:
                        execute_in_main_thread(partial(thread_tvguide_update_outdated))
                    elif epg_failed:
                        execute_in_main_thread(partial(thread_tvguide_update_error))
                    else:
                        execute_in_main_thread(partial(thread_tvguide_update_end))
                    DankoData.epg_failed = epg_outdated or epg_failed
                    DankoData.epg_pool_running = False

                    execute_in_main_thread(partial(redraw_channels))

        if DankoData.settings["m3u"] and m3u_exists:
            show_window(win)
            init_mpv_player()
            try:
                combobox_index1 = read_option("comboboxindex")
                if combobox_index1:
                    if combobox_index1["m3u"] == DankoData.settings["m3u"]:
                        if combobox_index1["index"] < DankoData.combobox.count():
                            DankoData.combobox.setCurrentIndex(combobox_index1["index"])
            except Exception:
                pass

            register()

            def after_mpv_init():
                if DankoData.needs_resize:
                    logger.debug("Fix window size")
                    win.resize(WINDOW_SIZE[0], WINDOW_SIZE[1])
                    move_window_to_center(win)
                if not playLastChannel():
                    logger.info("Show splash")
                    mpv_override_play(str(Path(DankoGUI.icons_folder, "main.png")))
                    DankoData.player.pause = True
                else:
                    logger.info("Playing last channel")
                restore_compact_state()

            after_mpv_init()

            DankoGUI.fullscreenPlaylistWidth = read_option("fullscreen_playlist_width")
            DankoGUI.fullscreenPlaylistHeight = read_option("fullscreen_playlist_height")

            if not DankoGUI.fullscreenPlaylistWidth:
                DankoGUI.fullscreenPlaylistWidth = DOCKWIDGET_PLAYLIST_WIDTH

            timers_array = {}
            timers = {
                timer_shortcuts: 25,
                timer_mouse: 50,
                timer_cursor: 50,
                timer_channels_redraw: 100,
                timer_record: 100,
                timer_osc: 100,
                timer_check_tvguide_obsolete: 100,
                timer_tvguide_progress: 100,
                timer_update_time: 1000,
                timer_logos_update: 1000,
                record_timer: 1000,
                record_timer_2: 1000,
                timer_afterrecord: 50,
                timer_bitrate: 5000,
                dockwidget_controlpanel_resize_timer: 50,
            }
            for timer in timers:
                timers_array[timer] = QtCore.QTimer()
                timers_array[timer].timeout.connect(timer)
                timers_array[timer].start(timers[timer])

            thread_epg_update_1 = threading.Thread(target=epg_update, daemon=True)
            thread_epg_update_1.start()
        else:
            DankoData.first_start = True
            show_playlists()
            move_window_to_center(gui_playlists_data.playlists_win)
            gui_playlists_data.playlists_win.show()

        app_exit_code = app.exec()
        if DankoData.do_save_settings:
            start_args = sys.argv
            if "python" not in sys.executable:
                start_args.pop(0)
            subprocess.Popen([sys.executable] + start_args)
        sys.exit(app_exit_code)
    except Exception:
        show_exception(traceback.format_exc())
        try:
            myExitHandler_before()
        except Exception:
            pass
        try:
            app.quit()
        except Exception:
            pass
        for process_4 in active_children():
            try:
                process_4.kill()
            except Exception:
                try:
                    process_4.terminate()
                except Exception:
                    pass
        kill_process_childs(os.getpid())
        sys.exit(1)
