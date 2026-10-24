#!/usr/bin/env python3
"""Hồi quy chống "treo" khi sinh ảnh — stdlib + CPU, không GPU/Forge thật.

Kiểm tra: timeout tách connect/read, đọc /progress, huỷ job, cảnh báo cấu hình dễ kẹt,
job chạy thread nền, và câu lỗi nói rõ việc cần làm (không lộ body/config).
"""
import os
import sys
import time
import unittest
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "colab"))

from prompt_lib.generate import (DEFAULT_CONNECT_TIMEOUT, DEFAULT_READ_TIMEOUT,  # noqa: E402
                                 GenerationJob, advice_for, busy_message, describe_error,
                                 format_duration, interrupt, payload_warnings, progress_info,
                                 read_timeout, status_line, timeouts)
from prompt_lib.workflow import generation_error  # noqa: E402


class FakeResponse:
    def __init__(self, data=None, code=200):
        self._data = data if data is not None else {}
        self.status_code = code

    def raise_for_status(self):
        if self.status_code >= 400:
            error = requests.exceptions.HTTPError(f"{self.status_code} error")
            error.response = self
            raise error

    def json(self):
        return self._data


class Timeouts(unittest.TestCase):
    def test_01_connect_short_read_long(self):
        connect, read = timeouts({})
        self.assertEqual(connect, DEFAULT_CONNECT_TIMEOUT)
        self.assertEqual(read, DEFAULT_READ_TIMEOUT)
        self.assertLess(connect, read)

    def test_02_env_override_is_clamped(self):
        self.assertEqual(read_timeout({"WAI_GEN_TIMEOUT": "1800"}), 1800)
        self.assertEqual(read_timeout({"WAI_GEN_TIMEOUT": "5"}), 60)       # quá ngắn -> sàn
        self.assertEqual(read_timeout({"WAI_GEN_TIMEOUT": "99999"}), 3600)  # quá dài -> trần
        self.assertEqual(read_timeout({"WAI_GEN_TIMEOUT": "rác"}), DEFAULT_READ_TIMEOUT)
        self.assertEqual(read_timeout({"WAI_GEN_TIMEOUT": "600.0"}), 600)


class Progress(unittest.TestCase):
    def test_03_parse_idle_and_running(self):
        idle = {"progress": 0, "eta_relative": 0, "state": {"job_count": 0}}
        info = progress_info("http://x", get=lambda *a, **k: FakeResponse(idle))
        self.assertFalse(info["busy"])
        self.assertEqual(info["progress"], 0.0)

        running = {"progress": 0.36, "eta_relative": 12.4,
                   "state": {"job_count": 1, "sampling_step": 9, "sampling_steps": 25}}
        info = progress_info("http://x/", get=lambda *a, **k: FakeResponse(running))
        self.assertTrue(info["busy"])
        self.assertEqual((info["step"], info["steps"]), (9, 25))
        self.assertAlmostEqual(info["progress"], 0.36)

    def test_04_broken_endpoint_is_silent(self):
        def boom(*a, **k):
            raise requests.exceptions.ConnectionError("down")
        self.assertEqual(progress_info("http://x", get=boom), {})
        self.assertEqual(progress_info("", get=boom), {})
        self.assertEqual(progress_info("http://x", get=lambda *a, **k: FakeResponse([], 404)), {})
        self.assertEqual(progress_info("http://x", get=lambda *a, **k: FakeResponse([1, 2])), {})

    def test_05_busy_message_and_status_line(self):
        info = {"busy": True, "progress": 0.4, "eta": 95, "step": 9, "steps": 25}
        self.assertIn("đang bận", busy_message(info))
        self.assertIn("1m 35s", busy_message(info))
        self.assertEqual(busy_message({}), "")
        line = status_line(72, info)
        self.assertIn("01:12", line)
        self.assertIn("bước 9/25", line)
        self.assertIn("(40%)", line)
        self.assertIn("đang chờ Forge", status_line(3, {}))

    def test_06_advice_only_when_stalled(self):
        running = {"busy": True, "progress": 0.2, "eta": 10}
        self.assertEqual(advice_for(20, running, stalled=10), "")
        self.assertIn("Không nhích bước", advice_for(200, running, stalled=120))
        self.assertIn("nạp checkpoint", advice_for(45, {}, stalled=0))

    def test_07_format_duration(self):
        self.assertEqual(format_duration(9), "9s")
        self.assertEqual(format_duration(95), "1m 35s")
        self.assertEqual(format_duration(3725), "1h 02m")
        self.assertEqual(format_duration("rác"), "?")


class Job(unittest.TestCase):
    def test_08_job_runs_in_background_and_reports(self):
        calls = []

        def slow_post(url, json=None, timeout=None):
            calls.append((url, timeout))
            time.sleep(0.6)
            return FakeResponse({"images": ["x"], "info": "{}"})

        job = GenerationJob("http://127.0.0.1:7860/", {"width": 8}, post=slow_post)
        self.assertFalse(job.done)
        job.start()
        self.assertEqual(job.endpoint, "http://127.0.0.1:7860/sdapi/v1/txt2img")
        # thread nền: vòng lặp UI vẫn chạy được trong lúc chờ
        ticks = 0
        while not job.done and ticks < 40:
            time.sleep(0.05)
            ticks += 1
        self.assertTrue(job.done)
        self.assertIsNone(job.error)
        self.assertEqual(job.response.json()["images"], ["x"])
        self.assertGreater(job.elapsed, 0.4)
        self.assertEqual(calls[0][1], timeouts())

    def test_09_http_error_is_captured_not_raised(self):
        job = GenerationJob("http://x", {}, post=lambda *a, **k: FakeResponse({}, 500)).start()
        self.assertTrue(job.wait(5))
        self.assertIsInstance(job.error, requests.exceptions.HTTPError)

    def test_10_progress_tracks_stall(self):
        step = {"value": 1}

        def get(url, **kwargs):
            return FakeResponse({"progress": 0.1, "eta_relative": 5,
                                 "state": {"job_count": 1, "sampling_step": step["value"],
                                           "sampling_steps": 25}})

        job = GenerationJob("http://x", {}, post=lambda *a, **k: FakeResponse({}))
        job.progress(get=get)["stalled"]
        first = job.progress(get=get)["stalled"]
        step["value"] = 2
        job.progress(get=get)
        self.assertGreaterEqual(first, 0)
        self.assertLess(job.progress(get=get)["stalled"], 1.0)


class Interrupt(unittest.TestCase):
    def test_11_interrupt_sends_post(self):
        seen = []

        def post(url, timeout=None):
            seen.append(url)
            return FakeResponse({})

        ok, message = interrupt("http://127.0.0.1:7860/", post=post)
        self.assertTrue(ok)
        self.assertIn("huỷ", message.lower())
        self.assertEqual(seen, ["http://127.0.0.1:7860/sdapi/v1/interrupt"])

    def test_12_interrupt_failure_is_reported(self):
        ok, message = interrupt("http://x", post=lambda *a, **k: FakeResponse({}, 404))
        self.assertFalse(ok)
        self.assertIn("không nhận lệnh huỷ", message.lower())
        ok, message = interrupt("http://x", post=lambda *a, **k: (_ for _ in ()).throw(
            requests.exceptions.ConnectionError("down")))
        self.assertFalse(ok)
        self.assertIn("Không gửi được", message)


class Warnings(unittest.TestCase):
    def test_13_hires_and_oversize(self):
        warns = payload_warnings({"width": 832, "height": 1216, "enable_hr": True,
                                  "hr_scale": 1.5, "steps": 25})
        self.assertTrue(any("Hires" in w for w in warns))
        self.assertEqual(payload_warnings({"width": 832, "height": 1216, "steps": 25}), [])
        big = payload_warnings({"width": 1536, "height": 1536, "steps": 50})
        self.assertTrue(any("1,3 MP" in w for w in big))
        self.assertTrue(any("bước" in w for w in big))


class Errors(unittest.TestCase):
    def test_14_timeout_explains_what_to_do(self):
        message = describe_error(requests.exceptions.ReadTimeout("x"), timeout=900)
        self.assertIn("không trả lời", message)
        self.assertIn("15m", message)
        self.assertIn("WAI_GEN_TIMEOUT", message)
        self.assertIn("Huỷ job", message)

    def test_15_connection_and_api_off(self):
        message = describe_error(requests.exceptions.ConnectionError("x"))
        self.assertIn("--api", message)
        response = FakeResponse({"detail": "Not Found"}, 404)
        error = requests.exceptions.HTTPError("404")
        error.response = response
        self.assertIn("--api", describe_error(error))
        message = describe_error(requests.exceptions.ConnectTimeout("x"))
        self.assertIn("khởi động", message)

    def test_16_generation_error_keeps_oom_and_hides_body(self):
        # đường cũ (ValueError chứa "out of memory") vẫn phải ra câu VRAM
        self.assertIn("Hết VRAM", generation_error(ValueError("CUDA out of memory; SECRET")))
        self.assertNotIn("SECRET", generation_error(ValueError("CUDA out of memory; SECRET")))
        response = FakeResponse({"detail": "CUDA out of memory at step 12 SECRET_CONFIG"}, 500)
        error = requests.exceptions.HTTPError("500")
        error.response = response
        message = generation_error(error)
        self.assertIn("Hết VRAM", message)
        self.assertNotIn("SECRET_CONFIG", message)
        # ReadTimeout: câu mới thay cho câu chung chung
        message = generation_error(requests.exceptions.ReadTimeout("x"), timeout=600)
        self.assertIn("không trả lời", message)
        self.assertIn("10m", message)

    def test_17_500_without_oom_points_to_log(self):
        response = FakeResponse({"detail": "something else"}, 500)
        error = requests.exceptions.HTTPError("500")
        error.response = response
        message = generation_error(error)
        self.assertIn("500", message)
        self.assertIn("log", message.lower())
        self.assertNotIn("something else", message)


if __name__ == "__main__":
    unittest.main(verbosity=2)
