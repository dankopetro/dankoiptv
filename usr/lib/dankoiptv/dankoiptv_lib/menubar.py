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
import logging
import traceback
from PyQt6 import QtGui
from functools import partial
from dankoiptv_lib.i18n import _, ngettext
from dankoiptv_lib.options import read_option

logger = logging.getLogger(__name__)


class DankoData:
    menubar_ready = False
    first_run = False
    first_run1 = False
    menubars = {}
    data = {}
    cur_vf_filters = []
    keyboard_sequences = []
    str_offset = " " * 44


def ast_mpv_seek(secs):
    logger.info(f"Seeking to {secs} seconds")
    DankoData.player.command("seek", secs)


def ast_mpv_speed(spd):
    logger.info(f"Set speed to {spd}")
    DankoData.player.speed = spd


def danko_trackset(track, type1):
    DankoData.danko_track_set(track, type1)
    DankoData.redraw_menubar()


def send_mpv_command(name, act, cmd):
    logger.info(f'Sending mpv command: "{name} {act} \\"{cmd}\\""')
    DankoData.player.command(name, act, cmd)


def get_active_vf_filters():
    return DankoData.cur_vf_filters


def apply_vf_filter(vf_filter, e_l):
    try:
        if e_l.isChecked():
            send_mpv_command(
                vf_filter.split("::::::::")[0], "add", vf_filter.split("::::::::")[1]
            )
            DankoData.cur_vf_filters.append(vf_filter)
        else:
            send_mpv_command(
                vf_filter.split("::::::::")[0], "remove", vf_filter.split("::::::::")[1]
            )
            DankoData.cur_vf_filters.remove(vf_filter)
    except Exception:
        exc = traceback.format_exc()
        logger.error("ERROR in vf-filter apply")
        logger.error("")
        logger.error(exc)
        DankoData.show_exception(exc, _("Error applying filters"))


def get_seq():
    return DankoData.keyboard_sequences


def qkeysequence(seq):
    s_e = QtGui.QKeySequence(seq)
    DankoData.keyboard_sequences.append(s_e)
    return s_e


def kbd(k_1):
    return qkeysequence(DankoData.get_keybind(k_1))


def reload_menubar_shortcuts():
    DankoData.playlists.setShortcut(kbd("show_playlists"))
    DankoData.reloadPlaylist.setShortcut(kbd("reload_playlist"))
    DankoData.m3uEditor.setShortcut(kbd("show_m3u_editor"))
    DankoData.exitAction.setShortcut(kbd("app.quit"))
    DankoData.playpause.setShortcut(kbd("mpv_play"))
    DankoData.stop.setShortcut(kbd("mpv_stop"))
    DankoData.frame_step.setShortcut(kbd("mpv_frame_step"))
    DankoData.frame_back_step.setShortcut(kbd("mpv_frame_back_step"))
    DankoData.normalSpeed.setShortcut(kbd("(lambda: set_playback_speed(1.00))"))
    DankoData.prevchannel.setShortcut(kbd("prev_channel"))
    DankoData.nextchannel.setShortcut(kbd("next_channel"))
    DankoData.fullscreen.setShortcut(kbd("mpv_fullscreen"))
    DankoData.compactmode.setShortcut(kbd("showhideeverything"))
    DankoData.csforchannel.setShortcut(kbd("main_channel_settings"))
    DankoData.screenshot.setShortcut(kbd("do_screenshot"))
    DankoData.muteAction.setShortcut(kbd("mpv_mute"))
    DankoData.volumeMinus.setShortcut(kbd("my_down_binding_execute"))
    DankoData.volumePlus.setShortcut(kbd("my_up_binding_execute"))
    DankoData.showhideplaylistAction.setShortcut(kbd("key_t"))
    DankoData.showhidectrlpanelAction.setShortcut(kbd("lowpanel_ch_1"))
    DankoData.streaminformationAction.setShortcut(kbd("open_stream_info"))
    DankoData.showepgAction.setShortcut(kbd("show_tvguide_2"))
    DankoData.forceupdateepgAction.setShortcut(kbd("force_update_epg"))
    DankoData.sortAction.setShortcut(kbd("show_sort"))
    DankoData.settingsAction.setShortcut(kbd("show_settings"))
    sec_keys_1 = [
        kbd("(lambda: mpv_seek(-10))"),
        kbd("(lambda: mpv_seek(10))"),
        kbd("(lambda: mpv_seek(-60))"),
        kbd("(lambda: mpv_seek(60))"),
        kbd("(lambda: mpv_seek(-600))"),
        kbd("(lambda: mpv_seek(600))"),
    ]
    sec_i_1 = -1
    for i_1 in DankoData.secs:
        sec_i_1 += 1
        i_1.setShortcut(qkeysequence(sec_keys_1[sec_i_1]))


def init_menubar(data):
    # File

    DankoData.playlists = QtGui.QAction(_("&Playlists"), data)
    DankoData.playlists.setShortcut(kbd("show_playlists"))
    DankoData.playlists.triggered.connect(lambda: DankoData.show_playlists())

    DankoData.reloadPlaylist = QtGui.QAction(_("&Update current playlist"), data)
    DankoData.reloadPlaylist.setShortcut(kbd("reload_playlist"))
    DankoData.reloadPlaylist.triggered.connect(lambda: DankoData.reload_playlist())

    DankoData.m3uEditor = QtGui.QAction(
        _("P&laylist editor") + DankoData.str_offset, data
    )
    DankoData.m3uEditor.setShortcut(kbd("show_m3u_editor"))
    DankoData.m3uEditor.triggered.connect(lambda: DankoData.show_m3u_editor())

    DankoData.exitAction = QtGui.QAction(_("&Exit"), data)
    DankoData.exitAction.setShortcut(kbd("app.quit"))
    DankoData.exitAction.triggered.connect(lambda: DankoData.app_quit())

    # Play

    DankoData.playpause = QtGui.QAction(_("&Play / Pause"), data)
    DankoData.playpause.setShortcut(kbd("mpv_play"))
    DankoData.playpause.triggered.connect(lambda: DankoData.mpv_play())

    DankoData.stop = QtGui.QAction(_("&Stop"), data)
    DankoData.stop.setShortcut(kbd("mpv_stop"))
    DankoData.stop.triggered.connect(lambda: DankoData.mpv_stop())

    DankoData.frame_step = QtGui.QAction(_("&Frame step"), data)
    DankoData.frame_step.setShortcut(kbd("mpv_frame_step"))
    DankoData.frame_step.triggered.connect(lambda: DankoData.mpv_frame_step())

    DankoData.frame_back_step = QtGui.QAction(_("Fra&me back step"), data)
    DankoData.frame_back_step.setShortcut(kbd("mpv_frame_back_step"))
    DankoData.frame_back_step.triggered.connect(lambda: DankoData.mpv_frame_back_step())

    DankoData.secs = []
    sec_keys = [
        kbd("(lambda: mpv_seek(-10))"),
        kbd("(lambda: mpv_seek(10))"),
        kbd("(lambda: mpv_seek(-60))"),
        kbd("(lambda: mpv_seek(60))"),
        kbd("(lambda: mpv_seek(-600))"),
        kbd("(lambda: mpv_seek(600))"),
    ]
    sec_i18n = [
        ngettext("-%d second", "-%d seconds", 10) % 10,
        ngettext("+%d second", "+%d seconds", 10) % 10,
        ngettext("-%d minute", "-%d minutes", 1) % 1,
        ngettext("+%d minute", "+%d minutes", 1) % 1,
        ngettext("-%d minute", "-%d minutes", 10) % 10,
        ngettext("+%d minute", "+%d minutes", 10) % 10,
    ]
    sec_i = -1
    for i in ((10, "seconds", 10), (1, "minutes", 60), (10, "minutes", 600)):
        for k in ("-", "+"):
            sec_i += 1
            sec = QtGui.QAction(sec_i18n[sec_i], data)
            sec.setShortcut(qkeysequence(sec_keys[sec_i]))
            sec.triggered.connect(
                partial(ast_mpv_seek, i[2] * -1 if k == "-" else i[2])
            )
            DankoData.secs.append(sec)

    DankoData.normalSpeed = QtGui.QAction(_("&Normal speed"), data)
    DankoData.normalSpeed.triggered.connect(partial(ast_mpv_speed, 1.00))
    DankoData.normalSpeed.setShortcut(kbd("(lambda: set_playback_speed(1.00))"))

    DankoData.spds = []

    for spd in (0.25, 0.5, 0.75, 1.25, 1.5, 1.75):
        spd_action = QtGui.QAction(f"{spd}x", data)
        spd_action.triggered.connect(partial(ast_mpv_speed, spd))
        DankoData.spds.append(spd_action)

    DankoData.prevchannel = QtGui.QAction(_("&Previous"), data)
    DankoData.prevchannel.triggered.connect(lambda: DankoData.prev_channel())
    DankoData.prevchannel.setShortcut(kbd("prev_channel"))

    DankoData.nextchannel = QtGui.QAction(_("&Next"), data)
    DankoData.nextchannel.triggered.connect(lambda: DankoData.next_channel())
    DankoData.nextchannel.setShortcut(kbd("next_channel"))

    # Video
    DankoData.fullscreen = QtGui.QAction(_("&Fullscreen"), data)
    DankoData.fullscreen.triggered.connect(lambda: DankoData.mpv_fullscreen())
    DankoData.fullscreen.setShortcut(kbd("mpv_fullscreen"))

    DankoData.compactmode = QtGui.QAction(_("&Compact mode"), data)
    DankoData.compactmode.triggered.connect(lambda: DankoData.showhideeverything())
    DankoData.compactmode.setShortcut(kbd("showhideeverything"))

    DankoData.csforchannel = QtGui.QAction(
        _("&Video settings") + DankoData.str_offset, data
    )
    DankoData.csforchannel.triggered.connect(lambda: DankoData.main_channel_settings())
    DankoData.csforchannel.setShortcut(kbd("main_channel_settings"))

    DankoData.screenshot = QtGui.QAction(_("&Screenshot"), data)
    DankoData.screenshot.triggered.connect(lambda: DankoData.do_screenshot())
    DankoData.screenshot.setShortcut(kbd("do_screenshot"))

    # Video filters
    DankoData.vf_postproc = QtGui.QAction(_("&Postprocessing"), data)
    DankoData.vf_postproc.setCheckable(True)

    DankoData.vf_deblock = QtGui.QAction(_("&Deblock"), data)
    DankoData.vf_deblock.setCheckable(True)

    DankoData.vf_dering = QtGui.QAction(_("De&ring"), data)
    DankoData.vf_dering.setCheckable(True)

    DankoData.vf_debanding = QtGui.QAction(
        _("Debanding (&gradfun)") + DankoData.str_offset, data
    )
    DankoData.vf_debanding.setCheckable(True)

    DankoData.vf_noise = QtGui.QAction(_("Add n&oise"), data)
    DankoData.vf_noise.setCheckable(True)

    DankoData.vf_phase = QtGui.QAction(_("&Autodetect phase"), data)
    DankoData.vf_phase.setCheckable(True)

    # Audio

    DankoData.muteAction = QtGui.QAction(_("&Mute audio"), data)
    DankoData.muteAction.triggered.connect(lambda: DankoData.mpv_mute())
    DankoData.muteAction.setShortcut(kbd("mpv_mute"))

    DankoData.volumeMinus = QtGui.QAction(_("V&olume -"), data)
    DankoData.volumeMinus.triggered.connect(lambda: DankoData.my_down_binding_execute())
    DankoData.volumeMinus.setShortcut(kbd("my_down_binding_execute"))

    DankoData.volumePlus = QtGui.QAction(_("Vo&lume +"), data)
    DankoData.volumePlus.triggered.connect(lambda: DankoData.my_up_binding_execute())
    DankoData.volumePlus.setShortcut(kbd("my_up_binding_execute"))

    # Audio filters

    DankoData.af_extrastereo = QtGui.QAction(_("&Extrastereo"), data)
    DankoData.af_extrastereo.setCheckable(True)

    DankoData.af_karaoke = QtGui.QAction(_("&Karaoke"), data)
    DankoData.af_karaoke.setCheckable(True)

    DankoData.af_earvax = QtGui.QAction(
        _("&Headphone optimization") + DankoData.str_offset, data
    )
    DankoData.af_earvax.setCheckable(True)

    DankoData.af_volnorm = QtGui.QAction(_("Volume &normalization"), data)
    DankoData.af_volnorm.setCheckable(True)

    # View

    DankoData.showhideplaylistAction = QtGui.QAction(_("Show/hide playlist"), data)
    DankoData.showhideplaylistAction.triggered.connect(
        lambda: DankoData.showhideplaylist()
    )
    DankoData.showhideplaylistAction.setShortcut(kbd("key_t"))

    DankoData.showhidectrlpanelAction = QtGui.QAction(
        _("Show/hide controls panel"), data
    )
    DankoData.showhidectrlpanelAction.triggered.connect(lambda: DankoData.lowpanel_ch_1())
    DankoData.showhidectrlpanelAction.setShortcut(kbd("lowpanel_ch_1"))

    DankoData.streaminformationAction = QtGui.QAction(_("Stream Information"), data)
    DankoData.streaminformationAction.triggered.connect(
        lambda: DankoData.open_stream_info()
    )
    DankoData.streaminformationAction.setShortcut(kbd("open_stream_info"))

    DankoData.showepgAction = QtGui.QAction(_("TV guide"), data)
    DankoData.showepgAction.triggered.connect(lambda: DankoData.show_tvguide_2())
    DankoData.showepgAction.setShortcut(kbd("show_tvguide_2"))

    DankoData.multiepgAction = QtGui.QAction(_("Multi-EPG"), data)
    DankoData.multiepgAction.triggered.connect(lambda: DankoData.show_multi_epg())
    DankoData.multiepgAction.setShortcut(kbd("show_multi_epg"))

    DankoData.forceupdateepgAction = QtGui.QAction(_("&Update TV guide"), data)
    DankoData.forceupdateepgAction.triggered.connect(lambda: DankoData.force_update_epg())
    DankoData.forceupdateepgAction.setShortcut(kbd("force_update_epg"))

    # Options

    DankoData.sortAction = QtGui.QAction(_("&Channel sort"), data)
    DankoData.sortAction.triggered.connect(lambda: DankoData.show_sort())
    DankoData.sortAction.setShortcut(kbd("show_sort"))

    DankoData.shortcutsAction = QtGui.QAction("&" + _("Shortcuts"), data)
    DankoData.shortcutsAction.triggered.connect(lambda: DankoData.show_shortcuts())

    DankoData.settingsAction = QtGui.QAction(_("&Settings"), data)
    DankoData.settingsAction.triggered.connect(lambda: DankoData.show_settings())
    DankoData.settingsAction.setShortcut(kbd("show_settings"))

    # Help
    DankoData.aboutAction = QtGui.QAction(_("&About Dankoiptv"), data)
    DankoData.aboutAction.triggered.connect(lambda: DankoData.show_help())

    # Empty (track list)
    def get_empty_action():
        empty_action = QtGui.QAction("<{}>".format(_("empty")), data)
        empty_action.setEnabled(False)
        return empty_action

    DankoData.get_empty_action = get_empty_action

    # Filters mapping
    DankoData.filter_mapping = {
        "vf::::::::lavfi=[pp]": DankoData.vf_postproc,
        "vf::::::::lavfi=[pp=vb/hb]": DankoData.vf_deblock,
        "vf::::::::lavfi=[pp=dr]": DankoData.vf_dering,
        "vf::::::::lavfi=[gradfun]": DankoData.vf_debanding,
        "vf::::::::lavfi=[noise=alls=9:allf=t]": DankoData.vf_noise,
        "vf::::::::lavfi=[phase=A]": DankoData.vf_phase,
        "af::::::::lavfi=[extrastereo]": DankoData.af_extrastereo,
        "af::::::::lavfi=[stereotools=mlev=0.015625]": DankoData.af_karaoke,
        "af::::::::lavfi=[earwax]": DankoData.af_earvax,
        "af::::::::lavfi=[acompressor]": DankoData.af_volnorm,
    }
    for vf_filter in DankoData.filter_mapping:
        DankoData.filter_mapping[vf_filter].triggered.connect(
            partial(apply_vf_filter, vf_filter, DankoData.filter_mapping[vf_filter])
        )


def populate_menubar(
    i, menubar, data, track_list=None, playing_channel=None, get_keybind=None
):
    # File

    if get_keybind:
        DankoData.get_keybind = get_keybind

    if not DankoData.menubar_ready:
        init_menubar(data)
        DankoData.menubar_ready = True

    file_menu = menubar.addMenu(_("&File"))
    file_menu.addAction(DankoData.playlists)
    file_menu.addSeparator()
    file_menu.addAction(DankoData.reloadPlaylist)
    file_menu.addAction(DankoData.forceupdateepgAction)
    file_menu.addSeparator()
    file_menu.addAction(DankoData.m3uEditor)
    file_menu.addAction(DankoData.exitAction)

    # Play

    play_menu = menubar.addMenu(_("&Play"))
    play_menu.addAction(DankoData.playpause)
    play_menu.addAction(DankoData.stop)
    play_menu.addAction(DankoData.frame_step)
    play_menu.addAction(DankoData.frame_back_step)
    play_menu.addSeparator()
    for sec in DankoData.secs:
        play_menu.addAction(sec)
    play_menu.addSeparator()

    speed_menu = play_menu.addMenu(_("Speed"))
    speed_menu.addAction(DankoData.normalSpeed)
    for spd_action1 in DankoData.spds:
        speed_menu.addAction(spd_action1)
    play_menu.addSeparator()
    play_menu.addAction(DankoData.prevchannel)
    play_menu.addAction(DankoData.nextchannel)

    # Video

    video_menu = menubar.addMenu(_("&Video"))
    video_track_menu = video_menu.addMenu(_("&Track"))
    video_track_menu.clear()
    video_menu.addAction(DankoData.fullscreen)
    video_menu.addAction(DankoData.compactmode)
    video_menu.addAction(DankoData.csforchannel)
    DankoData.video_menu_filters = video_menu.addMenu(_("F&ilters"))
    DankoData.video_menu_filters.addAction(DankoData.vf_postproc)
    DankoData.video_menu_filters.addAction(DankoData.vf_deblock)
    DankoData.video_menu_filters.addAction(DankoData.vf_dering)
    DankoData.video_menu_filters.addAction(DankoData.vf_debanding)
    DankoData.video_menu_filters.addAction(DankoData.vf_noise)
    DankoData.video_menu_filters.addAction(DankoData.vf_phase)
    video_menu.addSeparator()
    video_menu.addAction(DankoData.screenshot)

    # Audio

    audio_menu = menubar.addMenu(_("&Audio"))
    audio_track_menu = audio_menu.addMenu(_("&Track"))
    audio_track_menu.clear()
    DankoData.audio_menu_filters = audio_menu.addMenu(_("F&ilters"))
    DankoData.audio_menu_filters.addAction(DankoData.af_extrastereo)
    DankoData.audio_menu_filters.addAction(DankoData.af_karaoke)
    DankoData.audio_menu_filters.addAction(DankoData.af_earvax)
    DankoData.audio_menu_filters.addAction(DankoData.af_volnorm)
    audio_menu.addSeparator()
    audio_menu.addAction(DankoData.muteAction)
    audio_menu.addSeparator()
    audio_menu.addAction(DankoData.volumeMinus)
    audio_menu.addAction(DankoData.volumePlus)

    # Subtitles
    subtitles_menu = menubar.addMenu(_("&Subtitles"))
    sub_track_menu = subtitles_menu.addMenu(_("&Track"))
    sub_track_menu.clear()

    # View

    view_menu = menubar.addMenu(_("Vie&w"))
    view_menu.addAction(DankoData.showhideplaylistAction)
    view_menu.addAction(DankoData.showhidectrlpanelAction)
    view_menu.addAction(DankoData.streaminformationAction)
    view_menu.addAction(DankoData.showepgAction)
    view_menu.addAction(DankoData.multiepgAction)

    # Options

    options_menu = menubar.addMenu(_("&Options"))
    options_menu.addAction(DankoData.sortAction)
    options_menu.addSeparator()
    options_menu.addAction(DankoData.shortcutsAction)
    options_menu.addAction(DankoData.settingsAction)

    # Help

    help_menu = menubar.addMenu(_("&Help"))
    help_menu.addAction(DankoData.aboutAction)

    DankoData.menubars[i] = [video_track_menu, audio_track_menu, sub_track_menu]


# Preventing memory leak
def clear_menu(menu):
    for mb_action in menu.actions():
        if mb_action.isSeparator():
            mb_action.deleteLater()
        # elif mb_action.menu():
        #    clear_menu(mb_action.menu())
        #    mb_action.menu().deleteLater()
        else:
            mb_action.deleteLater()


def recursive_filter_setstate(state):
    for act in DankoData.video_menu_filters.actions():
        if not act.isSeparator():  # or act.menu():
            act.setEnabled(state)
    for act1 in DankoData.audio_menu_filters.actions():
        if not act1.isSeparator():  # or act1.menu():
            act1.setEnabled(state)


def get_first_run():
    return DankoData.first_run


def update_menubar(track_list, playing_channel, m3u):
    # Filters enable / disable
    if playing_channel:
        recursive_filter_setstate(True)
        # print(playing_channel + '::::::::::::::' + m3u)
        if not DankoData.first_run:
            DankoData.first_run = True
            try:
                vf_filters_read = read_option("vf_filters")
                if vf_filters_read:
                    for dat in vf_filters_read:
                        if dat in DankoData.filter_mapping:
                            DankoData.filter_mapping[dat].setChecked(True)
                            apply_vf_filter(dat, DankoData.filter_mapping[dat])
            except Exception:
                pass
    else:
        recursive_filter_setstate(False)
    # Track list
    for i in DankoData.menubars:
        clear_menu(DankoData.menubars[i][0])
        clear_menu(DankoData.menubars[i][1])
        clear_menu(DankoData.menubars[i][2])
        DankoData.menubars[i][0].clear()
        DankoData.menubars[i][1].clear()
        DankoData.menubars[i][2].clear()
        if track_list and playing_channel:
            if not [x for x in track_list if x["type"] == "video"]:
                DankoData.menubars[i][0].addAction(DankoData.get_empty_action())
            if not [x for x in track_list if x["type"] == "audio"]:
                DankoData.menubars[i][1].addAction(DankoData.get_empty_action())
            # Subtitles off
            sub_off_action = QtGui.QAction(_("None"), DankoData.data)
            if DankoData.player.sid == "no" or not DankoData.player.sid:
                sub_off_action.setIcon(DankoData.circle_icon)
            sub_off_action.triggered.connect(partial(danko_trackset, "no", "sid"))
            DankoData.menubars[i][2].addAction(sub_off_action)
            for track in track_list:
                if track["type"] == "video":
                    trk = QtGui.QAction(str(track["id"]), DankoData.data)
                    if track["id"] == DankoData.player.vid:
                        trk.setIcon(DankoData.circle_icon)
                    trk.triggered.connect(partial(danko_trackset, track["id"], "vid"))
                    DankoData.menubars[i][0].addAction(trk)
                if track["type"] == "audio":
                    if "lang" in track:
                        trk1 = QtGui.QAction(
                            "{} ({})".format(track["id"], track["lang"]), DankoData.data
                        )
                    else:
                        trk1 = QtGui.QAction(str(track["id"]), DankoData.data)
                    if track["id"] == DankoData.player.aid:
                        trk1.setIcon(DankoData.circle_icon)
                    trk1.triggered.connect(partial(danko_trackset, track["id"], "aid"))
                    DankoData.menubars[i][1].addAction(trk1)
                if track["type"] == "sub":
                    if "lang" in track:
                        trk2 = QtGui.QAction(
                            "{} ({})".format(track["id"], track["lang"]), DankoData.data
                        )
                    else:
                        trk2 = QtGui.QAction(str(track["id"]), DankoData.data)
                    if track["id"] == DankoData.player.sid:
                        trk2.setIcon(DankoData.circle_icon)
                    trk2.triggered.connect(partial(danko_trackset, track["id"], "sid"))
                    DankoData.menubars[i][2].addAction(trk2)
        else:
            DankoData.menubars[i][0].addAction(DankoData.get_empty_action())
            DankoData.menubars[i][1].addAction(DankoData.get_empty_action())
            DankoData.menubars[i][2].addAction(DankoData.get_empty_action())


def init_dankoiptv_lib_menubar(data, app, menubar):
    DankoData.data = data


def init_menubar_player(
    player,
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
    app_quit,
    redraw_menubar,
    circle_icon,
    my_up_binding_execute,
    my_down_binding_execute,
    show_m3u_editor,
    show_playlists,
    show_sort,
    show_exception,
    force_update_epg,
    get_keybind,
    show_tvguide_2,
    show_multi_epg,
    reload_playlist,
    show_shortcuts,
    danko_track_set,
    mpv_frame_step,
    mpv_frame_back_step,
):
    for func in locals().items():
        setattr(DankoData, func[0], func[1])
