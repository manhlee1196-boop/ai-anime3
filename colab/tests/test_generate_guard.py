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
                                 GenerationJob, advice_for, api_flags, busy_message, describe_error,
                                 format_duration, interrupt, log_hint, payload_warnings,
                                 ping, progress_info, read_timeout, status_line, timeouts,
                                 wait_diagnosis)
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

    def test_04_broken_endpoint_is_silent_but_explained(self):
        def boom(*a, **k):
            raise requests.exceptions.ConnectionError("down")
        for info in (progress_info("http://x", get=boom),
                     progress_info("", get=boom),
                     progress_info("http://x", get=lambda *a, **k: FakeResponse([], 404)),
                     progress_info("http://x", get=lambda *a, **k: FakeResponse([1, 2]))):
            self.assertFalse(info["available"])
            self.assertIn("reason", info)
            self.assertNotIn("prompt", str(info).lower())   # không lộ dữ liệu người dùng

    def test_05_busy_message_and_status_line(self):
        info = {"busy": True, "progress": 0.4, "eta": 95, "step": 9, "steps": 25}
        self.assertIn("đang bận", busy_message(info))
        self.assertIn("1m 35s", busy_message(info))
        self.assertEqual(busy_message({}), "")
        line = status_line(72, info)
        self.assertIn("01:12", line)
        self.assertIn("bước 9/25", line)
        self.assertIn("(40%)", line)
        # job đã nhận nhưng chưa bắt đầu (job_count=0) — khác hẳn "không đọc được"
        idle = {"available": True, "busy": False, "reason": ""}
        self.assertIn("chưa bắt đầu job", status_line(3, idle))

    def test_06_advice_only_when_stalled(self):
        running = {"busy": True, "progress": 0.2, "eta": 10}
        self.assertEqual(advice_for(20, running, stalled=10), "")
        self.assertIn("Không nhích bước", advice_for(200, running, stalled=120))
        idle = {"available": True, "busy": False, "reason": ""}
        self.assertIn("nạp checkpoint", advice_for(45, idle, stalled=0))
        self.assertEqual(advice_for(5, idle, stalled=0), "")
        # không đọc được tiến trình: nói rõ là app vẫn chờ, kèm cách kiểm tra
        self.assertIn("Không đọc được tiến trình",
                      advice_for(45, {"available": False, "reason": "HTTP 404"}, stalled=0))

    def test_07_format_duration(self):
        self.assertEqual(format_duration(9), "9s")
        self.assertEqual(format_duration(95), "1m 35s")
        self.assertEqual(format_duration(3725), "1h 02m")
        self.assertEqual(format_duration("rác"), "?")


class ProgressSources(unittest.TestCase):
    """Symptom "đang chờ Forge trả ảnh": phải nói rõ vì sao, không im lặng."""

    def test_18_falls_back_to_internal_progress(self):
        seen = []

        def get(url, **kwargs):
            seen.append(url)
            if url.endswith("/sdapi/v1/progress"):
                return FakeResponse({}, 404)
            return FakeResponse({"progress": 0.5, "eta_relative": 30,
                                 "state": {"job_count": 1, "sampling_step": 12,
                                           "sampling_steps": 25}})

        info = progress_info("http://x", get=get)
        self.assertTrue(info["available"])
        self.assertEqual(info["source"], "/internal/progress")
        self.assertTrue(info["busy"])
        self.assertEqual(info["step"], 12)
        self.assertIn("bước 12/25", status_line(45, info))
        self.assertEqual(len(seen), 2)

    def test_19_both_endpoints_missing_explains_why(self):
        info = progress_info("http://x", get=lambda *a, **k: FakeResponse({}, 404))
        self.assertFalse(info["available"])
        self.assertEqual(info["reason"], "HTTP 404")
        self.assertFalse(info["maybe_busy"])
        line = status_line(45, info)
        self.assertIn("chưa đọc được tiến trình", line)
        self.assertIn("Chẩn đoán", line)
        self.assertIn("Không đọc được tiến trình", advice_for(60, info))

    def test_20_slow_progress_means_busy_not_broken(self):
        def slow(*args, **kwargs):
            import requests as rq
            raise rq.exceptions.ReadTimeout("slow")

        info = progress_info("http://x", get=slow)
        self.assertTrue(info["maybe_busy"])
        line = status_line(40, info)
        self.assertIn("đang chạy", line)
        self.assertIn("đừng bấm lại", line)
        self.assertIn("không trả lời kịp", advice_for(60, info))

    def test_21_job_accepted_but_not_started(self):
        info = progress_info("http://x", get=lambda *a, **k: FakeResponse(
            {"progress": 0, "state": {"job_count": 0}}))
        self.assertTrue(info["available"])
        self.assertFalse(info["busy"])
        self.assertIn("chưa bắt đầu job", status_line(30, info))
        self.assertIn("quá 2 phút", status_line(150, info))
        self.assertIn("nạp checkpoint", advice_for(40, info))

    def test_22_ping_distinguishes_dead_from_alive(self):
        self.assertTrue(ping("http://x", get=lambda *a, **k: FakeResponse({}))["alive"])
        self.assertFalse(ping("http://x", get=lambda *a, **k: FakeResponse({}, 502))["alive"])
        dead = ping("http://x", get=lambda *a, **k: (_ for _ in ()).throw(
            __import__("requests").exceptions.ConnectionError("down")))
        self.assertFalse(dead["alive"])
        self.assertIn("ConnectionError", dead["detail"])

    def test_23_diagnosis_covers_three_cases(self):
        running = {"available": True, "busy": True, "progress": 0.4, "step": 9,
                   "steps": 25, "eta": 12, "source": "/sdapi/v1/progress"}
        text = "\n".join(wait_diagnosis("http://x", elapsed=60, info=running,
                                        ping_result={"alive": True, "detail": "ok"},
                                        log={"co_log": False, "path": "", "lines": []}))
        self.assertIn("đang chạy", text)
        self.assertIn("40%", text)

        broken = {"available": False, "reason": "HTTP 404", "maybe_busy": False}
        text = "\n".join(wait_diagnosis("http://x", elapsed=95, info=broken,
                                        ping_result={"alive": False, "detail": "ConnectionError"},
                                        log={"co_log": True, "path": "/content/forge.log",
                                             "lines": ["Hết VRAM (CUDA out of memory)"]}))
        self.assertIn("HTTP 404", text)
        self.assertIn("không phản hồi", text)
        self.assertIn("Hết VRAM", text)
        self.assertIn("Việc nên làm", text)

        slow = {"available": False, "reason": "quá thời gian", "maybe_busy": True}
        text = "\n".join(wait_diagnosis("http://x", elapsed=60, info=slow,
                                        ping_result={"alive": True, "detail": "ok"},
                                        log={"co_log": False, "path": "", "lines": []}))
        self.assertIn("không trả lời kịp", text)

    def test_27_ping_falls_back_to_root_when_options_busy(self):
        calls = []

        def get(url, **kwargs):
            calls.append(url)
            if url.endswith("/sdapi/v1/options"):
                import requests as rq
                raise rq.exceptions.ReadTimeout("busy")
            if url.endswith("/sdapi/v1/cmd-flags"):
                return FakeResponse({}, 404)
            return FakeResponse({}, 200)

        result = ping("http://x", get=get)
        self.assertTrue(result["alive"])
        self.assertEqual(result["path"], "/")
        self.assertEqual(len(calls), 3)

    def test_25_cmd_flags_identifies_foreign_server(self):
        ok = api_flags("http://x", get=lambda *a, **k: FakeResponse({"api_only": True}))
        self.assertTrue(ok["available"] and ok["api_only"])
        missing = api_flags("http://x", get=lambda *a, **k: FakeResponse({}, 404))
        self.assertFalse(missing["available"])
        self.assertEqual(missing["reason"], "HTTP 404")

        def boom(*a, **k):
            raise __import__("requests").exceptions.ConnectionError("down")

        self.assertEqual(api_flags("http://x", get=boom)["reason"], "ConnectionError")
        self.assertFalse(api_flags("")["available"])

    def test_26_diagnosis_flags_api_off(self):
        info = {"available": False, "reason": "HTTP 404", "maybe_busy": False}
        text = "\n".join(wait_diagnosis(
            "http://x", elapsed=90, info=info,
            ping_result={"alive": True, "detail": "ok"},
            log={"co_log": False, "path": "", "lines": []},
            flags={"available": False, "reason": "HTTP 404"}))
        self.assertIn("--api", text)
        text = "\n".join(wait_diagnosis(
            "http://x", elapsed=90, info=info,
            ping_result={"alive": True, "detail": "ok"},
            log={"co_log": False, "path": "", "lines": []},
            flags={"available": True, "api_only": False, "now": False}))
        self.assertIn("cmd-flags", text)
        self.assertIn("ảnh vẫn sinh bình thường", text)

    def test_24_log_hint_reads_signatures_only(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "forge.log"
            path.write_text("loading model\nRuntimeError: CUDA out of memory\nSECRET_TOKEN=abc\n")
            hint = log_hint(str(path))
        self.assertTrue(hint["co_log"])
        self.assertIn("Hết VRAM (CUDA out of memory)", hint["lines"])
        self.assertIn("Đang nạp checkpoint/model", hint["lines"])
        self.assertNotIn("SECRET_TOKEN", " ".join(hint["lines"]))
        self.assertFalse(log_hint(str(Path(tmp) / "missing.log"))["co_log"])


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
