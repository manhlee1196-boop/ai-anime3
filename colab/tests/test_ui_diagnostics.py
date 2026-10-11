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


if __name__ == "__main__":
    unittest.main(verbosity=2)
