"""Chẩn đoán UI chỉ đọc, stdlib + HTTP giả lập; không Forge/Torch/GPU.

python3 colab/tests/test_ui_diagnostics.py
"""
import json
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "colab"))
import diagnostics as diag


class UIDiagnostics(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wai-ui-diagnostics-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.gets, self.posts = [], []
        self.routes = {
            "/": (200, {"private": "DO_NOT_PRINT"}),
            "/config": (200, {"components": []}),
            "/info?all_endpoints=True": (500, {"error": "DO_NOT_PRINT"}),
            "/sdapi/v1/loras": (200, []),
            "/sdapi/v1/embeddings": (200, {"loaded": {}, "skipped": {}}),
        }
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                owner.gets.append(self.path)
                code, data = owner.routes.get(self.path, (404, {"private": "DO_NOT_PRINT"}))
                body = json.dumps(data).encode()
                self.send_response(code)
                if code == 302:
                    self.send_header("Location", "/private-redirect?token=DO_NOT_PRINT")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def do_POST(self):
                owner.posts.append(self.path)
                self.send_response(405)
                self.end_headers()
            def log_message(self, *args):
                pass
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def test_01_public_url_rejects_auth_query_redirect_targets_and_non_tunnel(self):
        for url in ("https://abc.trycloudflare.com/", "https://abc-123.gradio.live"):
            self.assertEqual(diag.validate_public_url(url), url.rstrip("/"))
        for url in ("http://abc.trycloudflare.com", "https://user:pass@abc.trycloudflare.com",
                    "https://abc.trycloudflare.com?token=secret", "https://abc.trycloudflare.com/#secret",
                    "https://abc.trycloudflare.com/info", "https://abc.trycloudflare.com:443",
                    "https://abc.trycloudflare.com.evil.test", "https://127.0.0.1", "https://other.test"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                diag.validate_public_url(url)

    def test_02_http_status_does_not_dump_body_or_follow_redirect_and_only_gets(self):
        result = diag.ui_transport(self.base)
        self.assertEqual(result["/"], {"http": 200})
        self.assertEqual(result["/info?all_endpoints=True"], {"http": 500})
        self.assertNotIn("DO_NOT_PRINT", json.dumps(result))
        self.routes["/redirect"] = (302, {})
        self.assertEqual(diag.http_status(self.base, "/redirect"), {"http": 302})
        self.assertFalse(any("private-redirect" in url for url in self.gets))
        self.assertEqual(self.posts, [])

    def test_03_optional_zero_counts_honest_and_private_names_omitted(self):
        result = diag.optional_assets(self.base)
        self.assertEqual(result["loras"], {"count": 0})
        self.assertEqual(result["textual_inversion"], {"loaded_count": 0, "skipped_count": 0})
        self.routes["/sdapi/v1/loras"] = (200, [{"name": "PRIVATE_LORA"}])
        self.routes["/sdapi/v1/embeddings"] = (200, {"loaded": {"PRIVATE_TI": {}}, "skipped": {}})
        result = diag.optional_assets(self.base)
        self.assertEqual(result["loras"]["count"], 1)
        self.assertEqual(result["textual_inversion"]["loaded_count"], 1)
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.routes["/sdapi/v1/loras"] = (404, {"token": "DO_NOT_PRINT"})
        self.assertIn("HTTP 404", diag.optional_assets(self.base)["loras"]["loi"])

    def test_04_traceback_projection_omits_exception_message_source_and_private_log(self):
        log = self.root / "forge.log"
        log.write_text('''private prompt: MUST_NOT_APPEAR
https://example.test/?token=MUST_NOT_APPEAR
Traceback (most recent call last):
  File "/content/forge/venv/lib/python3.13/site-packages/gradio_client/utils.py", line 123, in get_type
    raise TypeError("MUST_NOT_APPEAR")
TypeError: argument of type 'bool' is not iterable
Traceback (most recent call last):
  File "/content/forge/modules/model.py", line 42, in infer
    print("MUST_NOT_APPEAR")
ValueError: private prompt and token MUST_NOT_APPEAR
''')
        before = log.read_bytes()
        result = diag.traceback_summary(log)
        self.assertTrue(result["co_log"])
        self.assertEqual(result["tracebacks"][0]["signature"], "schema_bool_not_iterable")
        self.assertEqual(result["tracebacks"][0]["frames"][0]["file"], "gradio_client/utils.py")
        self.assertEqual(result["tracebacks"][1]["exception_type"], "ValueError")
        self.assertNotIn("MUST_NOT_APPEAR", json.dumps(result))
        self.assertNotIn("private prompt", json.dumps(result))
        self.assertEqual(before, log.read_bytes())
        self.assertFalse(diag.traceback_summary(self.root / "missing.log")["co_log"])

    def test_05_large_tail_keeps_at_most_six_errors_and_eight_frames(self):
        log = self.root / "forge.log"
        block = "Traceback (most recent call last):\n" + ''.join(
            f'  File "/content/forge/modules/frame{i}.py", line {i + 1}, in callback\n' for i in range(12))
        log.write_text("OLD_PRIVATE_PREFIX\n" * 30_000 + (block + "RuntimeError: CUDA out of memory.\n") * 9)
        result = diag.traceback_summary(log)
        self.assertEqual(len(result["tracebacks"]), 6)
        self.assertTrue(all(len(x["frames"]) == 8 for x in result["tracebacks"]))
        self.assertTrue(all(x["signature"] == "out_of_memory" for x in result["tracebacks"]))
        self.assertNotIn("OLD_PRIVATE", json.dumps(result))

    def test_06_collect_invalid_url_does_no_io_or_network(self):
        with patch.object(diag, "_run", side_effect=AssertionError("Must not run")), \
                patch.object(diag, "api_json", side_effect=AssertionError("Must not fetch")), \
                self.assertRaises(ValueError):
            diag.collect(self.root, self.root, self.root, "", self.root, 7860, public_url="https://user:pass@abc.trycloudflare.com")


    def test_07_indented_forge_matplotlib_exception_is_classified_without_message(self):
        log = self.root / "forge.log"
        log.write_text("""*** Error loading script
    Traceback (most recent call last):
      File "/content/venv/lib/python3.13/site-packages/matplotlib/__init__.py", line 1292, in <module>
        rcParams['backend'] = os.environ.get('MPLBACKEND')
      File "/content/venv/lib/python3.13/site-packages/matplotlib/__init__.py", line 784, in __setitem__
        raise ValueError('PRIVATE')
    ValueError: Key backend: 'module://matplotlib_inline.backend_inline' is not a valid value for backend; PRIVATE
""")
        result = diag.traceback_summary(log)
        self.assertEqual(result["tracebacks"][0]["exception_type"], "ValueError")
        self.assertEqual(result["tracebacks"][0]["signature"], "matplotlib_backend_invalid")
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertNotIn("module://", json.dumps(result))

    def test_08_network_reason_and_owned_process_graphics_environment_are_private(self):
        import os, socket, ssl, urllib.error
        for reason, kind in ((socket.gaierror(-2, "PRIVATE"), "dns"),
                             (ssl.SSLCertVerificationError(1, "PRIVATE"), "tls_certificate"),
                             (TimeoutError("PRIVATE"), "timeout"),
                             (ConnectionRefusedError("PRIVATE"), "connection_refused")):
            with patch.object(diag.urllib.request, "build_opener") as opener:
                opener.return_value.open.side_effect = urllib.error.URLError(reason)
                result = diag.http_status(self.base, "/")
            self.assertEqual(result["loai"], kind)
            self.assertNotIn("PRIVATE", json.dumps(result))
        runtime = self.root / "runtime"; runtime.mkdir()
        (runtime / "forge.pid").write_text(str(os.getpid()))
        forge = self.root / "forge"
        with patch.object(Path, "read_bytes", side_effect=[b"python\0foreign.py\0"]) as reads:
            result = diag.process_graphics_env(forge, runtime)
        self.assertEqual(reads.call_count, 1)
        self.assertEqual(result["forge_process"], "chua_xac_nhan")
        with patch.object(Path, "read_bytes", side_effect=[
                b"python\0" + str(forge / "launch.py").encode() + b"\0",
                b"CIVITAI_TOKEN=PRIVATE\0MPLBACKEND=Agg\0OTHER=PRIVATE\0"]):
            result = diag.process_graphics_env(forge, runtime)
        self.assertEqual(result["forge_process"], "Agg")
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertEqual(diag._backend_category("module://PRIVATE"), "backend_khac_da_an")

    def test_09_page_kind_separates_live_gradio_from_dead_share_relay(self):
        # Relay gradio.live trả 200 + trang "No interface is running right now"; nếu chỉ nhìn
        # mã HTTP thì tưởng link còn sống. Test này ghim lại phân loại + không rò nội dung.
        html = {
            "live": "<html><head></head><body><gradio-app>PRIVATE_TITLE</gradio-app></body></html>",
            "dead": "<html><body><h1>No interface is running right now</h1>PRIVATE_BODY</body></html>",
            "other": "<html><body>502 Bad Gateway PRIVATE_BODY</body></html>",
        }
        for name, expected in (("live", "gradio_song"), ("dead", "share_het"), ("other", "html_khac")):
            with patch.object(diag.urllib.request, "build_opener") as opener:
                response = opener.return_value.open.return_value.__enter__.return_value
                response.status = 200
                response.headers = {"Content-Type": "text/html; charset=utf-8"}
                response.read.return_value = html[name].encode()
                result = diag.page_kind(self.base)
            self.assertEqual(result["loai"], expected, name)
            self.assertEqual(result["http"], 200)
            self.assertNotIn("PRIVATE", json.dumps(result), name)

    def test_10_ui_verdict_gives_recovery_when_public_link_is_dead(self):
        live = {"loai": "gradio_song", "http": 200}
        dead = {"loai": "share_het", "http": 200}
        broken = {"loai": "loi", "http": 0, "loai_loi": "dns"}
        text = "\n".join(diag.ui_verdict(live, dead, 7860))
        self.assertIn("Link public đã chết", text)
        self.assertIn("127.0.0.1:7860", text)
        self.assertIn("--restart", text)
        self.assertIn("gradio.live", text)
        text = "\n".join(diag.ui_verdict(live, live, 7860))
        self.assertIn("Link public đang trỏ đúng giao diện", text)
        text = "\n".join(diag.ui_verdict(broken, broken, 7860))
        self.assertIn("Không mở được Forge local", text)
        self.assertIn("cloudflared", "\n".join(diag.ui_verdict(broken, dead, 7860)))
        # Khi local chết thì không được khuyên mở 127.0.0.1 như thể nó sống.
        self.assertNotIn("Forge vẫn chạy", "\n".join(diag.ui_verdict(broken, dead, 7860)))

    def test_12_cpu_report_finds_the_process_that_burns_cpu(self):
        # /proc giả: đọc theo tick, không sleep thật, không cần Forge/GPU.
        import subprocess

        def stat_line(pid, name, ppid, utime):
            rest = ["S", str(ppid)] + ["0"] * 9 + [str(utime), "0"]
            return f"{pid} ({name}) " + " ".join(rest) + "\n"

        proc = self.root / "proc"
        cases = {
            "4242": ("python", 1, 100, 160),      # 60 tick / 2s / 100Hz = 30%
            "4243": ("frpc", 4242, 0, 100),       # 100 tick / 2s = 50%
            "5000": ("bash", 1, 0, 0),            # ngoài cây: phải bị loại
        }
        for pid, (name, ppid, first, second) in cases.items():
            (proc / pid).mkdir(parents=True)
            (proc / pid / "stat").write_text(stat_line(pid, name, ppid, first))
        for tid, name, first in (("4244", "python", 0), ("4245", "wai-generate", 0)):
            (proc / "4242" / "task" / tid).mkdir(parents=True)
            (proc / "4242" / "task" / tid / "stat").write_text(stat_line("4242", name, 1, first))

        def finish_sample(_seconds):
            for pid, (_name, _ppid, _first, second) in cases.items():
                (proc / pid / "stat").write_text(stat_line(pid, cases[pid][0], cases[pid][1], second))
            (proc / "4242" / "task" / "4244" / "stat").write_text(stat_line("4242", "python", 1, 40))

        meminfo = self.root / "meminfo"
        meminfo.write_text("MemTotal:       12582912 kB\nMemAvailable:    6291456 kB\n")
        vmstat = self.root / "vmstat"
        vmstat.write_text("pgscan_direct 0\npgsteal_direct 0\npgscan_kswapd 0\npgsteal_kswapd 0\n")
        tcp = self.root / "tcp"
        tcp.write_text("  sl  local_address rem_address   st\n" + "".join(
            f"   {i}: 0100007F:1EB4 0100007F:9C40 01 0:0 0:0 1 0 0\n" for i in range(4)))
        report = diag.cpu_report(4242, port=7860, seconds=2.0, proc_root=str(proc),
                                 sleep=finish_sample, tcp_files=(str(tcp),),
                                 meminfo=str(meminfo), vmstat=str(vmstat))
        self.assertEqual(report["tong_cpu"], 80.0)
        self.assertEqual(report["processes"][0]["ten"], "frpc")
        self.assertEqual(report["processes"][0]["cpu"], 50.0)
        self.assertNotIn(5000, [row["pid"] for row in report["processes"]])
        self.assertEqual(report["client_ui"], 4)
        self.assertEqual(report["threads"][0], {"ten": "python#4244", "cpu": 20.0})
        self.assertEqual(report["ket_luan"], "tunnel")

        missing = diag.cpu_report(999999, proc_root=str(proc), seconds=0.01, sleep=lambda _s: None)
        self.assertIn("loi", missing)                      # PID cũ/không tồn tại

        # Không có tunnel nhưng nhiều tab UI mở -> chỉ đúng thủ phạm khác.
        only_python = self.root / "proc2"
        (only_python / "4242").mkdir(parents=True)
        (only_python / "4242" / "stat").write_text(stat_line("4242", "python", 1, 100))
        report = diag.cpu_report(4242, port=7860, seconds=2.0, proc_root=str(only_python),
                                 sleep=lambda _s: (only_python / "4242" / "stat").write_text(
                                     stat_line("4242", "python", 1, 160)),
                                 tcp_files=(str(tcp),),
                                 meminfo=str(meminfo), vmstat=str(vmstat))
        self.assertEqual(report["tong_cpu"], 30.0)
        self.assertEqual(report["ket_luan"], "nhieu_client")
        self.assertIn("4 kết nối UI", report["goi_y"])

        # RAM cạn: kernel thu hồi liên tục -> CPU tăng dần dù không sinh ảnh.
        tight = self.root / "meminfo-tight"
        tight.write_text("MemTotal:       12582912 kB\nMemAvailable:     409600 kB\n")
        churn = self.root / "vmstat-churn"
        churn.write_text("pgscan_direct 0\npgsteal_direct 0\n")

        def burn_reclaim(_seconds):
            (only_python / "4242" / "stat").write_text(stat_line("4242", "python", 1, 260))
            churn.write_text("pgscan_direct 12000\npgsteal_direct 8000\n")

        report = diag.cpu_report(4242, port=7860, seconds=2.0, proc_root=str(only_python),
                                 sleep=burn_reclaim, tcp_files=(str(tcp),),
                                 meminfo=str(tight), vmstat=str(churn))
        self.assertEqual(report["ket_luan"], "thieu_ram")
        self.assertEqual(report["ram_con_lai_mb"], 400)
        self.assertEqual(report["thu_hoi_trang_giay"], 10000)
        self.assertIn("RAM cạn", report["goi_y"])

        # CLI: thiếu forge.pid phải nói rõ, không traceback.
        result = subprocess.run([sys.executable, str(ROOT / "colab/diagnostics.py"), "--cpu",
                                 "--runtime-dir", str(self.root / "empty")],
                                text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 2)
        self.assertIn("forge.pid", json.loads(result.stdout)["loi"])

    def test_11_collect_records_page_kind_and_verdict(self):
        with patch.object(diag, "_run", return_value=""), \
                patch.object(diag, "api_json", return_value={"models": []}), \
                patch.object(diag, "ui_transport", return_value={"/": {"http": 200}}), \
                patch.object(diag, "optional_assets", return_value={}), \
                patch.object(diag, "page_kind", side_effect=[{"loai": "gradio_song", "http": 200},
                                                             {"loai": "share_het", "http": 200}]), \
                patch.object(diag, "process_graphics_env", return_value={}), \
                patch.object(diag, "traceback_summary", return_value={}):
            report = diag.collect(self.root, self.root, self.root, "", self.root, 7860,
                                  public_url="https://abc-123.gradio.live")
        self.assertEqual(report["ui_page_local"]["loai"], "gradio_song")
        self.assertEqual(report["ui_page_public"]["loai"], "share_het")
        self.assertIn("Link public đã chết", "\n".join(report["ket_luan_ui"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
