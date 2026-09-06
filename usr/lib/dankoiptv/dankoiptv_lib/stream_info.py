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
import time
import logging
import traceback
from PyQt6 import QtWidgets
from dankoiptv_lib.i18n import _
from dankoiptv_lib.misc import DankoData
from dankoiptv_lib.gui import move_window_to_center

logger = logging.getLogger(__name__)

# https://github.com/linuxmint/hypnotix/blob/f6101999c98773c68fedba2e46f61bb04b4cce5b/usr/lib/hypnotix/hypnotix.py

AUDIO_SAMPLE_FORMATS = {
    "u16": "unsigned 16 bits",
    "s16": "signed 16 bits",
    "s16p": "signed 16 bits, planar",
    "flt": "float",
    "float": "float",
    "fltp": "float, planar",
    "floatp": "float, planar",
    "dbl": "double",
    "dblp": "double, planar",
}


class stream_info:
    data = {}
    video_properties = {}
    audio_properties = {}
    video_bitrates = []
    audio_bitrates = []


def on_bitrate(prop, bitrate):
    try:
        if not bitrate or prop not in ["video-bitrate", "audio-bitrate"]:
            return

        if _("Average Bitrate") in stream_info.video_properties:
            if _("Average Bitrate") in stream_info.audio_properties:
                if not DankoData.streaminfo_win_visible:
                    return

        rates = {
            "video": stream_info.video_bitrates,
            "audio": stream_info.audio_bitrates,
        }
        rate = "video"
        if prop == "audio-bitrate":
            rate = "audio"

        rates[rate].append(int(bitrate) / 1000.0)
        rates[rate] = rates[rate][-30:]
        br = sum(rates[rate]) / float(len(rates[rate]))

        if rate == "video":
            stream_info.video_properties[_("General")][_("Average Bitrate")] = (
                "%.f " + _("kbps")
            ) % br
        else:
            stream_info.audio_properties[_("General")][_("Average Bitrate")] = (
                "%.f " + _("kbps")
            ) % br
    except Exception:
        if not DankoData.bitrate_failed:
            DankoData.bitrate_failed = True
            logger.warning("on_bitrate FAILED with exception!")
            logger.warning(traceback.format_exc())


def on_video_params(property1, params):
    try:
        if not params or not isinstance(params, dict):
            return
        if "w" in params and "h" in params:
            stream_info.video_properties[_("General")][
                _("Dimensions")
            ] = "{}x{}".format(params["w"], params["h"])
        if "aspect" in params:
            aspect = round(float(params["aspect"]), 2)
            stream_info.video_properties[_("General")][_("Aspect")] = "%s" % aspect
        if "pixelformat" in params:
            stream_info.video_properties[_("Color")][_("Pixel Format")] = params[
                "pixelformat"
            ]
        if "gamma" in params:
            stream_info.video_properties[_("Color")][_("Gamma")] = params["gamma"]
        if "average-bpp" in params:
            stream_info.video_properties[_("Color")][_("Bits Per Pixel")] = params[
                "average-bpp"
            ]
    except Exception:
        pass


def on_video_format(property1, vformat):
    try:
        if not vformat:
            return
        stream_info.video_properties[_("General")][_("Codec")] = vformat
    except Exception:
        pass


def on_audio_params(property1, params):
    try:
        if not params or not isinstance(params, dict):
            return
        if "channels" in params:
            layout_channels = params["channels"]
            if "5.1" in layout_channels or "7.1" in layout_channels:
                layout_channels += " " + _("surround sound")
            stream_info.audio_properties[_("Layout")][_("Channels")] = layout_channels
        if "samplerate" in params:
            sr = float(params["samplerate"]) / 1000.0
            stream_info.audio_properties[_("General")][_("Sample Rate")] = (
                "%.1f KHz" % sr
            )
        if "format" in params:
            fmt = params["format"]
            fmt = AUDIO_SAMPLE_FORMATS.get(fmt, fmt)
            stream_info.audio_properties[_("General")][_("Format")] = fmt
        if "channel-count" in params:
            stream_info.audio_properties[_("Layout")][_("Channel Count")] = params[
                "channel-count"
            ]
    except Exception:
        pass


def on_audio_codec(property1, codec):
    try:
        if not codec:
            return
        stream_info.audio_properties[_("General")][_("Codec")] = codec.split()[0]
    except Exception:
        pass


def monitor_playback():
    try:
        DankoData.player.wait_until_playing()
        DankoData.player.observe_property("video-params", on_video_params)
        DankoData.player.observe_property("video-format", on_video_format)
        DankoData.player.observe_property("audio-params", on_audio_params)
        DankoData.player.observe_property("audio-codec", on_audio_codec)
        DankoData.player.observe_property("video-bitrate", on_bitrate)
        DankoData.player.observe_property("audio-bitrate", on_bitrate)
    except Exception:
        pass


def process_stream_info(
    stream_info_count,
    stream_info_name,
    stream_properties,
):
    stream_information_label = QtWidgets.QLabel()
    stream_information_label.setFont(DankoData.DankoGUI.font_bold)
    stream_information_label.setText(stream_info_name)
    DankoData.DankoGUI.stream_information_layout.addWidget(
        stream_information_label, stream_info_count, 0
    )

    for stream_information_data in stream_properties:
        stream_info_count += 1
        stream_info_widget1 = QtWidgets.QLabel()
        stream_info_widget2 = QtWidgets.QLabel()
        stream_info_widget1.setText(str(stream_information_data))
        stream_info_widget2.setText(str(stream_properties[stream_information_data]))

        if (
            str(stream_information_data) == _("Average Bitrate")
            and stream_properties == stream_info.video_properties[_("General")]
        ):
            stream_info.data["video"] = [stream_info_widget2, stream_properties]

        if (
            str(stream_information_data) == _("Average Bitrate")
            and stream_properties == stream_info.audio_properties[_("General")]
        ):
            stream_info.data["audio"] = [stream_info_widget2, stream_properties]

        DankoData.DankoGUI.stream_information_layout.addWidget(
            stream_info_widget1, stream_info_count, 0
        )
        DankoData.DankoGUI.stream_information_layout.addWidget(
            stream_info_widget2, stream_info_count, 1
        )
    return stream_info_count + 1


def open_stream_info():
    if DankoData.playing_channel:
        for stream_info_i in reversed(
            range(DankoData.DankoGUI.stream_information_layout.count())
        ):
            DankoData.DankoGUI.stream_information_layout.itemAt(
                stream_info_i
            ).widget().setParent(None)

        stream_props = [
            stream_info.video_properties[_("General")],
            stream_info.video_properties[_("Color")],
            stream_info.audio_properties[_("General")],
            stream_info.audio_properties[_("Layout")],
        ]

        stream_info_video_lbl = QtWidgets.QLabel("\n" + _("Video"))
        stream_info_video_lbl.setFont(DankoData.DankoGUI.font_bold_medium)
        DankoData.DankoGUI.stream_information_layout.addWidget(
            stream_info_video_lbl, 0, 0
        )
        stream_info_count = 1
        stream_info_count = process_stream_info(
            stream_info_count, _("General"), stream_props[0]
        )
        stream_info_count = process_stream_info(
            stream_info_count, _("Color"), stream_props[1]
        )
        stream_info_audio_lbl = QtWidgets.QLabel("\n" + _("Audio"))
        stream_info_audio_lbl.setFont(DankoData.DankoGUI.font_bold_medium)
        DankoData.DankoGUI.stream_information_layout.addWidget(
            stream_info_audio_lbl, stream_info_count, 0
        )
        stream_info_count += 1
        stream_info_count = process_stream_info(
            stream_info_count, _("General"), stream_props[2]
        )
        stream_info_count = process_stream_info(
            stream_info_count, _("Layout"), stream_props[3]
        )

        if not DankoData.DankoGUI.streaminfo_win.isVisible():
            DankoData.DankoGUI.streaminfo_win.show()
            move_window_to_center(DankoData.DankoGUI.streaminfo_win)
        else:
            DankoData.DankoGUI.streaminfo_win.hide()
    else:
        DankoData.state.show()
        DankoData.state.setTextDanko("{}!".format(_("No channel selected")))
        DankoData.time_stop = time.time() + 1
