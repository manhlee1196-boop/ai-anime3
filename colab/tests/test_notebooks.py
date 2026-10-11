"""Hồi quy notebook cài mới / version guard / API, offline + CPU; không Colab/GPU.

Chạy trong venv có requests/Pillow: .venv/bin/python colab/tests/test_notebooks.py.
"""
import ast
import base64
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "colab"))
from notebook_support import API_SAMPLE_SOURCE, BOOTSTRAP_SOURCE, MIN_INSTALLER_VERSION

INSTALLER = (ROOT / "colab/install.sh").read_bytes()
REAL_RUN = subprocess.run


def script(version="1.0.6", broken=False):
    data = INSTALLER.replace(b'INSTALLER_VERSION="1.0.6"', f'INSTALLER_VERSION="{version}"'.encode())
    return data + (b"\nif true; then\n" if broken else b"")


def notebook(name):
    return json.loads((ROOT / "colab" / name).read_text(encoding="utf-8"))


def code_cells(nb):
    return ["".join(cell["source"]) for cell in nb["cells"] if cell["cell_type"] == "code"]


class NotebookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wai-notebook-test-")
        self.root = Path(self.tmp.name)
        self.dest = self.root / "install.sh"
        self.namespace = {"subprocess": subprocess}
        exec(compile(BOOTSTRAP_SOURCE, "bootstrap", "exec"), self.namespace)
        self.requests = []

    def tearDown(self):
        self.tmp.cleanup()

    def fetcher(self, responses):
        responses = iter(responses)
        def fetch(request, timeout=30):
            self.requests.append(request)
            response = next(responses)
            if isinstance(response, Exception):
                raise response
            return io.BytesIO(response)
        return fetch

    def download(self, responses, env=None):
        with patch("urllib.request.urlopen", self.fetcher(responses)), contextlib.redirect_stdout(io.StringIO()):
            return self.namespace["download_installer"](self.dest, "arena/88f01d31-ai-anime3", env or {})

    def test_01_generated_notebooks_are_synced_valid_and_unexecuted(self):
        for generator, name in (("make_install_notebook.py", "WAI_v17_1click.ipynb"),
                                ("make_notebook.py", "WAI_Illustrious_v17_vi.ipynb")):
            path = ROOT / "colab" / name
            before = path.read_bytes()
            result = REAL_RUN([sys.executable, str(ROOT / "colab" / generator)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(before, path.read_bytes(), "Notebook phải được sinh lại trước khi commit")
            nb = notebook(name)
            self.assertEqual(nb["metadata"]["accelerator"], "GPU")
            self.assertEqual(nb["metadata"]["colab"]["gpuType"], "T4")
            for cell in nb["cells"]:
                if cell["cell_type"] == "code":
                    ast.parse("".join(cell["source"]))
                    self.assertIsNone(cell["execution_count"])
                    self.assertEqual(cell["outputs"], [])
            source = "\n".join(code_cells(nb))
            self.assertNotIn("drive.mount", source)
            self.assertIn('MIN_INSTALLER_VERSION = "1.0.6"', source)
            self.assertIn('"arena/88f01d31-ai-anime3"', source)
        self.assertEqual(len(code_cells(notebook("WAI_v17_1click.ipynb"))), 1)
        self.assertEqual(MIN_INSTALLER_VERSION, "1.0.6")

    def test_02_download_replaces_old_cache_atomically(self):
        self.dest.write_bytes(script("1.0.5"))
        self.assertEqual(self.download([INSTALLER]), "1.0.6")
        self.assertEqual(self.dest.read_bytes(), INSTALLER)
        self.assertFalse(self.dest.with_suffix(".sh.tmp").exists())

    def test_03_raw_failure_uses_api_without_credential_in_url_or_output(self):
        token = "fixture-only-secret"
        output = io.StringIO()
        with patch("urllib.request.urlopen", self.fetcher([OSError("offline"), INSTALLER])), contextlib.redirect_stdout(output):
            version = self.namespace["download_installer"](self.dest, "arena/88f01d31-ai-anime3", {"GITHUB_TOKEN": token})
        self.assertEqual(version, "1.0.6")
        self.assertIn("api.github.com", self.requests[1].full_url)
        self.assertIn("arena%2F88f01d31-ai-anime3", self.requests[1].full_url)
        self.assertTrue(all(token not in request.full_url for request in self.requests))
        self.assertNotIn(token, output.getvalue())
        self.assertEqual(self.requests[1].get_header("Authorization"), "Bearer " + token)

    def test_04_network_failure_old_cache_is_not_executed_or_deleted(self):
        old = script("1.0.5")
        self.dest.write_bytes(old)
        with self.assertRaisesRegex(RuntimeError, ">= 1.0.6"):
            self.download([OSError("offline"), OSError("offline")])
        self.assertEqual(self.dest.read_bytes(), old)

    def test_05_verified_new_cache_can_resume_offline(self):
        self.dest.write_bytes(INSTALLER)
        self.assertEqual(self.download([OSError("offline"), OSError("offline")]), "1.0.6")
        self.assertEqual(self.dest.read_bytes(), INSTALLER)

    def test_06_old_or_invalid_network_bytes_never_overwrite_cache(self):
        self.dest.write_bytes(INSTALLER)
        self.assertEqual(self.download([script("1.0.5"), script(broken=True)]), "1.0.6")
        self.assertEqual(self.dest.read_bytes(), INSTALLER)
        self.assertFalse(self.dest.with_suffix(".sh.tmp").exists())

    def test_07_broken_cache_and_no_cache_fail_before_install(self):
        for data in (None, script(broken=True), b"<!DOCTYPE html>error", script("1.0.5")):
            with self.subTest(data=data is None):
                if data is None:
                    self.dest.unlink(missing_ok=True)
                else:
                    self.dest.write_bytes(data)
                with self.assertRaises(RuntimeError):
                    self.download([OSError("offline"), OSError("offline")])

    def test_08_fresh_detailed_run_all_orders_stages_and_skips_optional_actions(self):
        nb = notebook("WAI_Illustrious_v17_vi.ipynb")
        stages = []
        repo = self.root / "repo"
        repo_install = repo / "colab/install.sh"
        def run(args, **kwargs):
            if args[:2] == ["bash", "-n"]:
                return subprocess.CompletedProcess(args, 0)  # syntax thật đã kiểm ở test 02–07
            self.assertEqual(args[:2], ["bash", str(self.dest)])
            stage = args[args.index("--only") + 1]
            stages.append(stage)
            self.assertEqual(args[args.index("--model") + 1], "fp16")
            self.assertEqual(args[args.index("--tunnel") + 1], "share")
            self.assertEqual(args[args.index("--branch") + 1], "arena/88f01d31-ai-anime3")
            self.assertTrue(kwargs.get("check"))
            if stage == "repo":
                repo_install.parent.mkdir(parents=True)
                repo_install.write_bytes(INSTALLER)
            if stage == "launch,verify":
                self.assertNotIn("--no-launch", args)
            else:
                self.assertIn("--no-launch", args)
            return subprocess.CompletedProcess(args, 0)
        namespace = {}
        with patch.dict(os.environ, {}, clear=True), patch("subprocess.run", run), \
                patch("subprocess.Popen", side_effect=AssertionError("Run all không mở thêm app")), \
                patch("urllib.request.urlopen", self.fetcher([INSTALLER])), contextlib.redirect_stdout(io.StringIO()):
            for source in code_cells(nb):
                source = source.replace('"/content/ai-anime3"', repr(str(repo)))
                source = source.replace('"/content/install.sh"', repr(str(self.dest)))
                source = source.replace('"/content/models"', repr(str(self.root / "models")))
                exec(compile(source, "notebook-cell", "exec"), namespace)
        self.assertEqual(stages, ["repo", "preflight", "forge", "torch", "model", "extras", "launch,verify"])
        self.assertFalse(namespace["RUN_API_SAMPLE"])
        self.assertFalse(namespace["START_PROMPT_APP"])
        self.assertFalse(namespace["SMOKE_TEST"])
        self.assertNotIn("API_LAST_RESULT", namespace)

    def test_09_oneclick_defaults_run_full_installer_not_only_update_stages(self):
        source = code_cells(notebook("WAI_v17_1click.ipynb"))[0].replace('"/content/install.sh"', repr(str(self.dest)))
        calls = []
        class Process:
            stdout = io.StringIO("fixture install done\n")
            pid = 123456
            def wait(self):
                return 0
        def launch(args, **kwargs):
            calls.append((args, kwargs))
            return Process()
        with patch.dict(os.environ, {}, clear=True), patch("urllib.request.urlopen", self.fetcher([INSTALLER])), \
                patch("subprocess.run", return_value=subprocess.CompletedProcess(["bash", "-n"], 0)), \
                patch("subprocess.Popen", launch), contextlib.redirect_stdout(io.StringIO()):
            exec(compile(source, "oneclick-cell", "exec"), {})
        self.assertEqual(len(calls), 1)
        args = calls[0][0]
        self.assertNotIn("--only", args)
        self.assertNotIn("--no-launch", args)
        self.assertNotIn("--smoke-test", args)
        self.assertNotIn("--fallback-fp16", args)
        self.assertEqual(args[args.index("--model") + 1], "fp16")
        self.assertEqual(args[args.index("--model-dir") + 1], "/content/models")
        self.assertEqual(args[args.index("--tunnel") + 1], "share")

    def test_10_api_sample_disabled_makes_no_requests(self):
        with patch("requests.get", side_effect=AssertionError("Không gọi API")), \
                patch("requests.post", side_effect=AssertionError("Không gọi API")), contextlib.redirect_stdout(io.StringIO()):
            namespace = {}
            exec(API_SAMPLE_SOURCE, namespace)
        self.assertNotIn("API_LAST_RESULT", namespace)

    def test_11_api_sample_profile_weights_json_string_png_and_seed(self):
        from PIL import Image
        from prompt_lib import TagIndex, WAI_DEFAULTS
        index = TagIndex(ROOT)
        png = io.BytesIO()
        Image.new("RGB", (8, 8), "white").save(png, format="PNG")
        image = base64.b64encode(png.getvalue()).decode()
        defaults = dict(WAI_DEFAULTS)
        captures, gets = [], []
        class Response:
            def raise_for_status(self):
                pass
            def json(self):
                return {"images": [image], "info": json.dumps({"seed": 42, "all_seeds": [42]})}
        def post(url, json=None, **kwargs):
            captures.append(json)
            return Response()
        try:
            with patch.dict(os.environ, {"REPO_DIR": str(self.root), "PORT": "7860"}), \
                    patch("prompt_lib.TagIndex", return_value=index), patch("requests.post", post), \
                    patch("requests.get", side_effect=lambda *args, **kwargs: gets.append(args)), \
                    contextlib.redirect_stdout(io.StringIO()):
                ns = {}
                exec(API_SAMPLE_SOURCE, ns)
                ns.update(MODE="Nháp", SEED=-1, IMAGE_COUNT=2)
                WAI_DEFAULTS.update(steps=10, cfg_scale=1.0, hr_second_pass_steps=10)
                result = ns["generate_notebook_sample"]()
                self.assertEqual(captures[-1]["steps"], 10)
                self.assertEqual(captures[-1]["cfg_scale"], 1.0)
                self.assertEqual(captures[-1]["batch_size"], 1)
                self.assertEqual(captures[-1]["n_iter"], 2)
                self.assertFalse(captures[-1]["enable_hr"])
                self.assertNotIn("hr_upscaler", captures[-1])
                self.assertIn("(ao_dai:1.2)", captures[-1]["prompt"])
                self.assertEqual(gets, [])
                self.assertEqual(result["metadata"]["seeds"], [42])
                self.assertTrue(Path(result["paths"][0]).is_file())
                self.assertIn("seed42", result["paths"][0])
                with Image.open(result["paths"][0]) as saved:
                    self.assertEqual(saved.format, "PNG")
                count = len(captures)
                ns.update(MODE="Hoàn thiện", SEED=-1)
                with self.assertRaisesRegex(ValueError, "seed"):
                    ns["generate_notebook_sample"]()
                self.assertEqual(len(captures), count)
                ns.update(MODE="Nháp", SEED=-2)
                with self.assertRaises(ValueError):
                    ns["generate_notebook_sample"]()
                self.assertEqual(len(captures), count)
        finally:
            WAI_DEFAULTS.clear()
            WAI_DEFAULTS.update(defaults)

    def test_12_oneclick_refuses_old_cache_before_starting_installer(self):
        self.dest.write_bytes(script("1.0.5"))
        source = code_cells(notebook("WAI_v17_1click.ipynb"))[0].replace('"/content/install.sh"', repr(str(self.dest)))
        with patch.dict(os.environ, {}, clear=True), \
                patch("urllib.request.urlopen", self.fetcher([OSError("offline"), OSError("offline")])), \
                patch("subprocess.Popen", side_effect=AssertionError("Không chạy script cũ")), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, ">= 1.0.6"):
                exec(compile(source, "oneclick-cell", "exec"), {})

    def test_13_final_sample_one_image_hires_and_sanitized_failure(self):
        from PIL import Image
        from prompt_lib import TagIndex, WAI_DEFAULTS
        index = TagIndex(ROOT)
        buffer = io.BytesIO()
        Image.new("RGB", (8, 8), "white").save(buffer, format="PNG")
        image = base64.b64encode(buffer.getvalue()).decode()
        captures = []
        class Response:
            def __init__(self, data):
                self.data = data
            def raise_for_status(self):
                pass
            def json(self):
                return self.data
        def post(url, json=None, **kwargs):
            captures.append(json)
            return Response({"images": [image], "info": "{\"seed\": 123, \"all_seeds\": [123]}"})
        with patch.dict(os.environ, {"REPO_DIR": str(self.root)}), \
                patch("prompt_lib.TagIndex", return_value=index), patch("requests.post", post), \
                patch("requests.get", return_value=Response([{"name": "RealESRGAN_x4plus_anime_6B"}])), \
                contextlib.redirect_stdout(io.StringIO()):
            ns = {}
            exec(API_SAMPLE_SOURCE, ns)
            ns.update(MODE="Hoàn thiện", SEED=123, IMAGE_COUNT=4)
            result = ns["generate_notebook_sample"]()
            body = captures[-1]
            self.assertEqual(body["n_iter"], 1)
            self.assertEqual(body["batch_size"], 1)
            self.assertTrue(body["enable_hr"])
            self.assertEqual(body["hr_scale"], 1.5)
            self.assertEqual(body["denoising_strength"], 0.35)
            self.assertEqual(body["hr_second_pass_steps"], WAI_DEFAULTS["hr_second_pass_steps"])
            self.assertEqual(body["override_settings"]["clip_stop_at_last_layers"], WAI_DEFAULTS["clip_skip"])
            self.assertEqual(result["metadata"]["seeds"], [123])
            with patch("requests.post", side_effect=RuntimeError("CUDA out of memory SECRET-FIXTURE")):
                with self.assertRaisesRegex(RuntimeError, "Hết VRAM") as raised:
                    ns["generate_notebook_sample"]()
                self.assertNotIn("SECRET-FIXTURE", str(raised.exception))


    def test_14_both_notebooks_honor_cloudflare_and_none_choices(self):
        for name in ("WAI_v17_1click.ipynb", "WAI_Illustrious_v17_vi.ipynb"):
            for tunnel in ("cloudflared", "none"):
                with self.subTest(notebook=name, tunnel=tunnel):
                    repo = self.root / name / tunnel
                    repo_install = repo / "colab/install.sh"
                    repo_install.parent.mkdir(parents=True)
                    repo_install.write_bytes(INSTALLER)
                    calls = []

                    def run(args, **kwargs):
                        if args[:2] != ["bash", "-n"]:
                            calls.append((args, kwargs))
                        return subprocess.CompletedProcess(args, 0)

                    class Process:
                        def __init__(self):
                            self.stdout = io.StringIO("fixture install done\n")
                            self.pid = 123456
                        def wait(self):
                            return 0

                    def launch(args, **kwargs):
                        calls.append((args, kwargs))
                        return Process()

                    # Một ô đầy đủ hoặc 2 ô config/bootstrap của notebook chi tiết;
                    # các stage/HTTP được giả lập, không clone/tải/chạy Forge.
                    cells = code_cells(notebook(name))[:2]
                    namespace = {}
                    with patch.dict(os.environ, {}, clear=True), \
                            patch("urllib.request.urlopen", self.fetcher([INSTALLER])), \
                            patch("subprocess.run", run), patch("subprocess.Popen", launch), \
                            contextlib.redirect_stdout(io.StringIO()):
                        for cell in cells:
                            cell = cell.replace('TUNNEL = "share"', f'TUNNEL = "{tunnel}"')
                            cell = cell.replace('"/content/install.sh"', repr(str(self.dest)))
                            cell = cell.replace('"/content/ai-anime3"', repr(str(repo)))
                            exec(compile(cell, "selected-tunnel", "exec"), namespace)
                    self.assertTrue(calls)
                    for args, _kwargs in calls:
                        self.assertEqual(args[args.index("--tunnel") + 1], tunnel)
                    self.assertEqual(namespace["TUNNEL"], tunnel)


if __name__ == "__main__":
    unittest.main(verbosity=2)
