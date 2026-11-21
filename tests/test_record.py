"""Tests de grabación Danko TV (python3 -m unittest discover -s tests).

El test de stream real (test_live_ts) necesita red: se salta con
DANKO_REC_LIVE=0 (default en CI/sin red es 1 — acá corre con red).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dankotv import record  # noqa: E402

LIVE_URL = "http://vip.4kiptv.pro/gQUkHt52/jAZUsz6/1057402"  # .ts directo
HLS_URL = "http://vip.4kiptv.pro:2095/live/gQUkHt52/jAZUsz6/1057402.m3u8"


class BuildCmdTest(unittest.TestCase):
    def test_ts_directo_sin_live_start_index(self):
        """Bug 14/11: -live_start_index en .ts directo = ffmpeg aborta."""
        cmd = record.build_cmd(LIVE_URL, "/tmp/x.ts", live=True)
        self.assertIn("-re", cmd)
        self.assertNotIn("-live_start_index", cmd)

    def test_hls_si_lleva_live_start_index(self):
        cmd = record.build_cmd(HLS_URL, "/tmp/x.ts", live=True)
        self.assertIn("-re", cmd)
        i = cmd.index("-live_start_index")
        self.assertEqual(cmd[i + 1], "-1")

    def test_hls_con_query_tambien(self):
        cmd = record.build_cmd(HLS_URL + "?token=abc", "/tmp/x.ts", live=True)
        self.assertIn("-live_start_index", cmd)

    def test_archivo_sin_opciones_live(self):
        """live=False (repetición/archivo): copia rápida, sin -re."""
        cmd = record.build_cmd("http://x/pelicula.mp4", "/tmp/x.mp4", live=False)
        self.assertNotIn("-re", cmd)
        self.assertNotIn("-live_start_index", cmd)

    def test_is_hls(self):
        self.assertTrue(record._is_hls(HLS_URL))
        self.assertTrue(record._is_hls("http://x/a.M3U8?y=1"))
        self.assertFalse(record._is_hls(LIVE_URL))
        self.assertFalse(record._is_hls("http://x/a.mp4"))


class RebasedCmdTest(unittest.TestCase):
    """start(skip_secs) → ffmpeg con -ss tras -re (descarta el adelanto)."""

    def test_skip_pasa_ss_tras_re(self):
        cmd = record.rebased_cmd(LIVE_URL, 30, "/tmp/x.ts", live=True)
        i_re = cmd.index("-re")
        i_ss = cmd.index("-ss")
        self.assertGreater(i_ss, i_re, "-ss debe ir después de -re")
        self.assertEqual(cmd[i_ss + 1], "30")
        # .ts directo: sin -live_start_index (regla del bug 14/11)
        self.assertNotIn("-live_start_index", cmd)

    def test_skip_hls_mantiene_live_start_index(self):
        cmd = record.rebased_cmd(HLS_URL, 12, "/tmp/x.ts", live=True)
        self.assertIn("-live_start_index", cmd)
        self.assertIn("-ss", cmd)

    def test_sin_skip_cero(self):
        cmd = record.rebased_cmd(LIVE_URL, 0, "/tmp/x.ts", live=True)
        self.assertNotIn("-ss", cmd)

    def test_skip_negativo_ignorado(self):
        cmd = record.rebased_cmd(LIVE_URL, -5, "/tmp/x.ts", live=True)
        self.assertNotIn("-ss", cmd)


class RecDirTest(unittest.TestCase):
    def test_default_sin_setting(self):
        from dankotv import config
        old = config.load_settings
        config.load_settings = lambda: {"rec_dir": ""}
        try:
            self.assertEqual(record.rec_dir(), record.REC_DIR)
        finally:
            config.load_settings = old

    def test_setting_personalizada(self):
        from dankotv import config
        old = config.load_settings
        config.load_settings = lambda: {"rec_dir": "/tmp/mis grabaciones"}
        try:
            self.assertEqual(record.rec_dir(), "/tmp/mis grabaciones")
        finally:
            config.load_settings = old


@unittest.skipUnless(record.ffmpeg_ok(), "ffmpeg no instalado")
class RecorteTest(unittest.TestCase):
    """Trim del .ts grabado a [start, start+keep) sin recodificar."""

    def test_duration_y_recorte_de_archivo_real(self):
        tmp = tempfile.mkdtemp(prefix="dankotrim_")
        try:
            # Archivo de 3s: 90 frames a 30fps de color + 1s de silencio.
            # -g 30: keyframe cada segundo (como los streams IPTV reales,
            # GOP ~2s); sin esto el generador deja UN SOLO keyframe y
            # cualquier corte posterior pierde el video.
            ts = os.path.join(tmp, "b.ts")
            subprocess.run(
                ["ffmpeg", "-nostats", "-loglevel", "error",
                 "-f", "lavfi", "-i", "testsrc=size=160x120:rate=30",
                 "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                 "-t", "3", "-c:v", "libx264", "-preset", "ultrafast",
                 "-g", "30", "-pix_fmt", "yuv420p", "-c:a", "aac", "-y", ts],
                capture_output=True, timeout=60)
            self.assertTrue(os.path.isfile(ts), "no se creó el .ts")
            dur = record.duration_seconds(ts)
            self.assertGreater(dur, 2.5, f"duración rara: {dur}")
            self.assertLess(dur, 3.5, f"duración rara: {dur}")

            mp4 = os.path.join(tmp, "c.mp4")
            final = record.trim_and_remux(ts, mp4, start_s=1.0, keep_s=1.0)
            self.assertEqual(final, mp4)
            self.assertTrue(os.path.isfile(mp4))
            self.assertGreater(os.path.getsize(mp4), 5000, "recorte vacío")
            # el .ts se borra luego del recorte OK
            self.assertFalse(os.path.exists(ts))
            # duración del recorte ~1s (±0.5)
            d2 = record.duration_seconds(mp4)
            self.assertGreater(d2, 0.5, f"recorte corto: {d2}")
            self.assertLess(d2, 1.6, f"recorte largo: {d2}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_recorte_fuera_de_rango(self):
        """start+keep mayor que la duración: recorta hasta el final."""
        tmp = tempfile.mkdtemp(prefix="dankotrim2_")
        try:
            ts = os.path.join(tmp, "b.ts")
            subprocess.run(
                ["ffmpeg", "-nostats", "-loglevel", "error",
                 "-f", "lavfi", "-i", "testsrc=size=160x120:rate=30",
                 "-t", "2", "-c:v", "libx264", "-preset", "ultrafast",
                 "-g", "30", "-pix_fmt", "yuv420p", "-y", ts],
                capture_output=True, timeout=60)
            mp4 = os.path.join(tmp, "c.mp4")
            final = record.trim_and_remux(ts, mp4, start_s=0.5, keep_s=999)
            self.assertEqual(final, mp4)
            d2 = record.duration_seconds(mp4)
            self.assertGreater(d2, 0.5, f"recorte raro: {d2}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


@unittest.skipUnless(os.environ.get("DANKO_REC_LIVE", "1") == "1",
                     "DANKO_REC_LIVE=0 (red deshabilitada)")
@unittest.skipUnless(record.ffmpeg_ok(), "ffmpeg no instalado")
class LiveStreamTest(unittest.TestCase):
    """Integración: grabar el stream .ts real unos segundos (red)."""

    def test_start_crea_ts_y_stop_da_mp4(self):
        tmp = tempfile.mkdtemp(prefix="dankorec_")
        old_dir = record.rec_dir
        old_log = record.REC_LOG
        record.rec_dir = lambda: tmp
        record.REC_LOG = os.path.join(tmp, "record.log")
        try:
            proc, ts, mp4 = record.start(LIVE_URL, "test canal", live=True)
            try:
                # ffmpeg debe seguir vivo (el bug lo mataba en <1s)
                self.assertIsNone(proc.poll(),
                                  "ffmpeg murió al abrir: " +
                                  record._tail_rec_log())
                time.sleep(5)
                self.assertTrue(os.path.isfile(ts), "no se creó el .ts")
                self.assertGreater(os.path.getsize(ts), 100_000,
                                   ".ts vacío/chico a los 5s")
            finally:
                final = record.stop(proc, ts, mp4)
            self.assertTrue(final and os.path.isfile(final),
                            "stop no devolvió archivo: " +
                            record._tail_rec_log())
            self.assertGreater(os.path.getsize(final), 100_000)
            # mp4 debe tener tracks A/V
            if final.endswith(".mp4"):
                import subprocess
                r = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries",
                     "stream=codec_type", "-of", "csv=p=0", final],
                    capture_output=True, text=True)
                self.assertIn("video", r.stdout)
                self.assertIn("audio", r.stdout)
        finally:
            record.rec_dir = old_dir
            record.REC_LOG = old_log
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
