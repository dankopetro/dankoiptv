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
import json
import chardet
import logging
import traceback
from PyQt6 import QtWidgets
from dankoiptv_lib.i18n import _
from dankoiptv_lib.misc import DankoData
from dankoiptv_lib.playlist_m3u import M3UParser
from dankoiptv_lib.qt_exception import show_exception
from dankoiptv_lib.playlist_xspf import parse_xspf
from dankoiptv_lib.requests_timeout import requests_get
from dankoiptv_lib.xtream import load_xtream, convert_xtream_to_m3u, XTreamFailedClass
from thirdparty.xtream import Serie


logger = logging.getLogger(__name__)


class PlaylistsFail:
    status_code = 400


def load_playlist():
    m3u = ""
    array = {}
    groups = []

    xt = XTreamFailedClass()

    logger.info("Loading playlist...")
    if DankoData.settings["m3u"]:
        if DankoData.settings["m3u"].startswith("XTREAM::::::::::::::"):
            # XTREAM::::::::::::::username::::::::::::::password::::::::::::::url
            DankoData.is_xtream = True
            logger.info("Using XTream API")
            xt, xtream_username, xtream_password, xtream_url = load_xtream(
                DankoData.settings["m3u"]
            )
            if xt.auth_data != {}:
                try:
                    xt.load_iptv()
                    m3u = convert_xtream_to_m3u(xt.channels)
                    try:
                        m3u += convert_xtream_to_m3u(xt.movies, True, "VOD")
                    except Exception:
                        logger.warning("XTream movies parse FAILED")
                    for movie1 in xt.series:
                        if isinstance(movie1, Serie):
                            DankoData.series[movie1.name] = movie1
                    DankoData.settings["epg_temporary"] = (
                        f"{xtream_url}/xmltv.php?username="
                        f"{xtream_username}&password={xtream_password}"
                    )
                    logger.info("XTream init done")
                except Exception:
                    exc = traceback.format_exc()
                    logger.warning(exc)
                    message2 = "{}\n\n{}".format(
                        _("dankoiptv error"),
                        str(
                            "XTream API: {}\n\n{}".format(
                                _("Processing error"), str(exc)
                            )
                        ),
                    )
                    msg2 = QtWidgets.QMessageBox(
                        QtWidgets.QMessageBox.Icon.Warning,
                        _("Error"),
                        message2,
                        QtWidgets.QMessageBox.StandardButton.Ok,
                    )
                    msg2.exec()
            else:
                message1 = "{}\n\n{}".format(
                    _("dankoiptv error"),
                    str("XTream API: {}".format(_("Could not connect"))),
                )
                msg1 = QtWidgets.QMessageBox(
                    QtWidgets.QMessageBox.Icon.Warning,
                    _("Error"),
                    message1,
                    QtWidgets.QMessageBox.StandardButton.Ok,
                )
                msg1.exec()
        else:
            if os.path.isfile(DankoData.settings["m3u"]):
                DankoData.is_xtream = False
                logger.info("Playlist is local file")
                try:
                    file = open(DankoData.settings["m3u"], encoding="utf8")
                    m3u = file.read()
                    file.close()
                except Exception:
                    logger.warning("Playlist is not UTF-8 encoding")
                    logger.info("Trying to detect encoding...")
                    m3u_file = open(DankoData.settings["m3u"], "rb")
                    try:
                        m3u_file_read = m3u_file.read()
                        m3u_encoding = chardet.detect(m3u_file_read)["encoding"]
                        logger.info(f"Detected encoding: {m3u_encoding}")
                        m3u = m3u_file_read.decode(m3u_encoding)
                    except Exception:
                        logger.warning("Encoding detection error!")
                        show_exception(
                            _(
                                "Failed to load playlist - unknown "
                                "encoding! Please use playlists "
                                "in UTF-8 encoding."
                            )
                        )
                    finally:
                        m3u_file_read = None
                        m3u_file.close()
            else:
                DankoData.is_xtream = False
                logger.info("Playlist is remote URL")
                try:
                    ua = (
                        DankoData.settings["playlist_useragent"]
                        if DankoData.settings["playlist_useragent"]
                        else DankoData.settings["ua"]
                    )
                    ref = (
                        DankoData.settings["playlist_referer"]
                        if DankoData.settings["playlist_referer"]
                        else DankoData.settings["referer"]
                    )
                    originURL = ""
                    if ref and ref.endswith("/"):
                        originURL = ref[:-1]
                    headers = {"User-Agent": ua}
                    if ref:
                        headers["Referer"] = ref
                    if originURL:
                        headers["Origin"] = originURL
                    logger.info(f"Loading playlist with headers {json.dumps(headers)}")
                    try:
                        m3u_req = requests_get(
                            DankoData.settings["m3u"],
                            headers=headers,
                            timeout=(5, 15),  # connect, read timeout
                        )
                    except Exception:
                        logger.warning(traceback.format_exc())
                        m3u_req = PlaylistsFail()

                    if m3u_req.status_code != 200:
                        logger.warning("Playlist load failed, trying empty user agent")
                        m3u_req = requests_get(
                            DankoData.settings["m3u"],
                            headers={"User-Agent": ""},
                            timeout=(5, 15),  # connect, read timeout
                        )

                    logger.info(f"Status code: {m3u_req.status_code}")
                    logger.info(f"{len(m3u_req.content)} bytes")
                    m3u = m3u_req.content
                    try:
                        m3u = m3u.decode("utf-8")
                    except Exception:
                        logger.warning("Playlist is not UTF-8 encoding")
                        logger.info("Trying to detect encoding...")
                        guess_encoding = ""
                        try:
                            guess_encoding = chardet.detect(m3u)["encoding"]
                        except Exception:
                            pass
                        if guess_encoding:
                            logger.info(f"Guessed encoding: {guess_encoding}")
                            try:
                                m3u = m3u.decode(guess_encoding)
                            except Exception:
                                logger.warning("Wrong encoding guess!")
                                show_exception(
                                    _(
                                        "Failed to load playlist - unknown "
                                        "encoding! Please use playlists "
                                        "in UTF-8 encoding."
                                    )
                                )
                        else:
                            logger.warning("Unknown encoding!")
                            show_exception(
                                _(
                                    "Failed to load playlist - unknown "
                                    "encoding! Please use playlists "
                                    "in UTF-8 encoding."
                                )
                            )
                except Exception:
                    m3u = ""
                    exp3 = traceback.format_exc()
                    logger.warning("Playlist URL loading error!" + "\n" + exp3)
                    show_exception(traceback.format_exc(), _("Playlist loading error!"))

    m3u_parser = M3UParser(
        DankoData.settings["playlist_udp_proxy"]
        if DankoData.settings["playlist_udp_proxy"]
        else DankoData.settings["udp_proxy"],
    )
    if m3u:
        try:
            is_xspf = '<?xml version="' in m3u and (
                "http://xspf.org/" in m3u or "https://xspf.org/" in m3u
            )
            if not is_xspf:
                m3u_data0 = m3u_parser.parse_m3u(m3u)
            else:
                m3u_data0 = parse_xspf(m3u)
            m3u_data_got = m3u_data0[0]
            m3u_data = []
            DankoData.settings["epg_temporary"] = m3u_data0[1]

            for m3u_datai in m3u_data_got:
                if "tvg-group" in m3u_datai:
                    if (
                        m3u_datai["tvg-group"].lower() == "vod"
                        or m3u_datai["tvg-group"].lower().startswith("vod ")
                        or m3u_datai["tvg-group"].lower().endswith(" vod")
                    ):
                        DankoData.movies[m3u_datai["title"]] = m3u_datai
                    else:
                        m3u_data.append(m3u_datai)

            for m3u_line in m3u_data:
                array[m3u_line["title"]] = m3u_line
                if m3u_line["tvg-group"] not in groups:
                    groups.append(m3u_line["tvg-group"])
        except Exception:
            logger.warning("Playlist parsing error!" + "\n" + traceback.format_exc())
            show_exception(traceback.format_exc(), _("Playlist loading error!"))
            m3u = ""
            array = {}
            groups = []

    m3u_exists = not not m3u

    logger.info(
        "{} channels, {} groups, {} movies, {} series".format(
            len(array),
            len([group2 for group2 in groups if group2 != _("All channels")]),
            len(DankoData.movies),
            len(DankoData.series),
        )
    )

    for ch3 in array.copy():
        if DankoData.settings["m3u"] in DankoData.channel_sets:
            if ch3 in DankoData.channel_sets[DankoData.settings["m3u"]]:
                if "group" in DankoData.channel_sets[DankoData.settings["m3u"]][ch3]:
                    if DankoData.channel_sets[DankoData.settings["m3u"]][ch3]["group"]:
                        array[ch3]["tvg-group"] = DankoData.channel_sets[
                            DankoData.settings["m3u"]
                        ][ch3]["group"]
                        if (
                            DankoData.channel_sets[DankoData.settings["m3u"]][ch3][
                                "group"
                            ]
                            not in groups
                        ):
                            groups.append(
                                DankoData.channel_sets[DankoData.settings["m3u"]][ch3][
                                    "group"
                                ]
                            )
                if "hidden" in DankoData.channel_sets[DankoData.settings["m3u"]][ch3]:
                    if DankoData.channel_sets[DankoData.settings["m3u"]][ch3]["hidden"]:
                        array.pop(ch3)

    if _("All channels") in groups:
        groups.remove(_("All channels"))
    groups = [_("All channels"), _("Favourites")] + groups

    def sort_custom(sub):
        try:
            return DankoData.channel_sort.index(sub)
        except Exception:
            return len(array) + 10

    def doSort(arr0):
        if DankoData.settings["sort"] == 0:
            return arr0
        if DankoData.settings["sort"] == 1:
            return sorted(arr0)
        if DankoData.settings["sort"] == 2:
            return sorted(arr0, reverse=True)
        if DankoData.settings["sort"] == 3:
            try:
                return sorted(arr0, key=sort_custom)
            except Exception:
                return arr0
        return arr0

    DankoData.array = array
    DankoData.array_sorted = doSort(array)

    logger.info("Playlist loading done!")

    return groups, m3u_exists, xt
