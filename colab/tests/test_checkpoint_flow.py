#!/usr/bin/env python3
"""Hồi quy checkpoint/preset/API, stdlib + HTTP cục bộ; không GPU/model thật.

FORGE_AUDIT_SOURCE_DIR=tools/work python3 colab/tests/test_checkpoint_flow.py
cho phép chạy cả hàm preset + scanner + selector nguyên bản từ mã Forge đã tải về.
"""
from __future__ import annotations

import ast
import base64
import binascii
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import threading
import types
import unittest
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "colab"))
import checkpoint_tools as cp  # noqa: E402
import diagnostics  # noqa: E402


def safetensors(header=None, data=b"\x00\x00\x00\x00"):
    if header is None:
        header = {"fixture": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]}}
    raw = json.dumps(header, separators=(",", ":")).encode()
    raw += b" " * (-len(raw) % 8)
    return struct.pack("<Q", len(raw)) + raw + data


def png():
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", binascii.crc32(kind + data) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 256, 256, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress((b"\x00" + b"\xff" * (256 * 3)) * 256)) + chunk(b"IEND", b""))


def selected_nodes(path, names, namespace):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    if len(nodes) != len(names):
        raise AssertionError(f"Mã upstream thiếu hàm/class: {names}")
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


class CheckpointFlow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wai-checkpoint-test-")
        self.root = Path(self.tmp.name)
        self.forge = self.root / "forge"
        self.forge.mkdir()
        self.model = self.root / "models with spaces/fixture.safetensors"
        self.model.parent.mkdir()
        self.model.write_bytes(safetensors())
        self.sha = cp.sha256_file(self.model)
        self.config = self.forge / "config.json"
        self.config.write_text(json.dumps({"VERSION_UID": "PY313", "sd_model_checkpoint": self.model.name,
                                          "tac_active": True, "user_setting": "giữ nguyên"}))
        self.ui = self.forge / "ui-config.json"
        self.ui.write_text(json.dumps({"webui/UI Preset/value": "sd", "txt2img/Prompt/value": "my private prompt",
                                      "txt2img/Width/value": 832}))

    def tearDown(self):
        self.tmp.cleanup()

    def test_01_valid_container_and_hash(self):
        info = cp.inspect_safetensors(self.model, self.sha)
        self.assertEqual((info["tensors"], info["dtypes"]), (1, {"F32": 1}))
        self.assertEqual(info["sha256"], self.sha)

    def test_02_pointer_html_truncated_wrong_sha(self):
        for body in (b"version https://git-lfs.github.com/spec/v1\noid sha256:abcdef\n",
                     b"<!DOCTYPE html><html>401</html>", safetensors()[:-1], b"\x00" * 16):
            with self.subTest(body=body[:10]):
                self.model.write_bytes(body)
                with self.assertRaises(cp.CheckpointError):
                    cp.inspect_safetensors(self.model)
        self.model.write_bytes(safetensors())
        with self.assertRaises(cp.CheckpointError):
            cp.inspect_safetensors(self.model, "0" * 64)

    def test_03_temp_file_not_registered(self):
        partial = self.model.with_suffix(".safetensors.part")
        self.model.rename(partial)
        with self.assertRaises(cp.CheckpointError):
            cp.inspect_safetensors(partial)
        self.assertEqual(cp.inspect_safetensors(partial, self.sha, allow_download_temp=True)["sha256"], self.sha)
        with self.assertRaises(cp.CheckpointError):
            cp.configure_checkpoint(self.forge, partial, self.sha)
        self.assertFalse((self.forge / "models/Stable-diffusion/fixture.safetensors.part").exists())

    def test_04_invalid_shapes_offsets_and_metadata(self):
        for header in ({}, {"a": {"dtype": "F32", "shape": [2], "data_offsets": [0, 4]}},
                       {"a": {"dtype": "F32", "shape": [-1], "data_offsets": [0, 4]}},
                       {"a": {"dtype": "unknown", "shape": [1], "data_offsets": [0, 4]}},
                       {"a": {"dtype": "F32", "shape": [1], "data_offsets": [True, 4]}},
                       {"__metadata__": {"x": 1}, "a": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]}}):
            with self.subTest(header=header):
                self.model.write_bytes(safetensors(header))
                with self.assertRaises(cp.CheckpointError):
                    cp.inspect_safetensors(self.model)

    def test_05_header_bound_and_overlap(self):
        self.model.write_bytes(struct.pack("<Q", cp.MAX_HEADER + 1) + b"{}")
        with self.assertRaises(cp.CheckpointError):
            cp.inspect_safetensors(self.model)
        tensor = {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]}
        self.model.write_bytes(safetensors({"a": tensor, "b": tensor}))
        with self.assertRaises(cp.CheckpointError):
            cp.inspect_safetensors(self.model)
        self.model.write_bytes(safetensors() + b"trailing")
        with self.assertRaises(cp.CheckpointError):
            cp.inspect_safetensors(self.model)

    def test_06_config_xl_profile_and_managed_alias(self):
        before = self.config.read_bytes()
        cp.configure_checkpoint(self.forge, self.model, self.sha, "hswq", 1.0, 10, 10)
        data = cp.read_object(self.config)
        self.assertEqual(data["forge_preset"], "xl")
        self.assertEqual(data["forge_checkpoint_xl"], self.model.name)
        self.assertEqual(data["xl_t2i_cfg"], 1.0)
        self.assertEqual(data["xl_t2i_hr_step"], 10)
        self.assertEqual(data["forge_additional_modules_xl"], [])
        self.assertEqual(data["forge_unet_storage_dtype_xl"], "Automatic")
        self.assertEqual((data["VERSION_UID"], data["user_setting"], data["tac_active"]), ("PY313", "giữ nguyên", True))
        ui = cp.read_object(self.ui)
        self.assertEqual(ui["webui/UI Preset/value"], "xl")
        self.assertEqual((ui["txt2img/Prompt/value"], ui["txt2img/Width/value"]), ("my private prompt", 832))
        alias = self.forge / "models/Stable-diffusion" / self.model.name
        self.assertTrue(alias.is_symlink() and os.path.samefile(alias, self.model))
        self.assertEqual(len(list(self.model.parent.iterdir())), 1)  # không tạo bản sao hàng GB
        backups = list(self.forge.glob("config.json.wai-checkpoint-backup-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), before)
        cp.configure_checkpoint(self.forge, self.model, self.sha, "hswq", 1.0, 10, 10)
        self.assertEqual(len(list(self.forge.glob("config.json.wai-checkpoint-backup-*"))), 1)

    def test_07_no_overwrite_foreign_file_or_symlink(self):
        folder = self.forge / "models/Stable-diffusion"
        folder.mkdir(parents=True)
        alias = folder / self.model.name
        alias.write_bytes(b"other user's model")
        for is_link in (False, True):
            with self.subTest(link=is_link):
                if is_link:
                    alias.unlink(); alias.symlink_to(self.root / "not-our-target")
                with self.assertRaises(cp.CheckpointError):
                    cp.configure_checkpoint(self.forge, self.model, self.sha)
                self.assertTrue(alias.is_symlink() if is_link else alias.read_bytes() == b"other user's model")

        alias.unlink(missing_ok=True)
        alias.write_bytes(self.model.read_bytes())
        with self.assertRaises(cp.CheckpointError):
            cp.configure_checkpoint(self.forge, self.model, self.sha)
        self.assertEqual(alias.read_bytes(), self.model.read_bytes())

    def test_08_update_only_owned_link_when_model_dir_changes(self):
        cp.configure_checkpoint(self.forge, self.model, self.sha)
        other = self.root / "new model directory" / self.model.name
        other.parent.mkdir(); other.write_bytes(self.model.read_bytes())
        cp.configure_checkpoint(self.forge, other, self.sha)
        alias = self.forge / "models/Stable-diffusion" / self.model.name
        self.assertTrue(os.path.samefile(alias, other))
        self.assertTrue(self.model.exists())

    def test_09_bad_config_or_profile_preserved(self):
        before = self.config.read_bytes()
        with self.assertRaises(cp.CheckpointError):
            cp.configure_checkpoint(self.forge, self.model, self.sha, cfg=float("nan"))
        self.assertEqual(self.config.read_bytes(), before)
        self.ui.write_text("{broken")
        with self.assertRaises(cp.CheckpointError):
            cp.configure_checkpoint(self.forge, self.model, self.sha)
        self.assertEqual(self.config.read_bytes(), before)
        self.assertFalse((self.forge / "models/Stable-diffusion").exists())

    def test_10_real_prepare_launch_no_gpu(self):
        source = self.forge / "modules/launch_utils.py"
        source.parent.mkdir(); source.write_text('VERSION_UID: str = "PY313"\n')
        import forge_compat
        for relative, _marker, old, _new in forge_compat.PATCHES:
            target = self.forge / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            prefix = "def flags_fixture():\n    for key in _options:\n" if relative.endswith("models.py") else "def make_checkpoint_manager_ui():\n"
            target.write_text(prefix + old + "\n")
        py = self.forge / "venv/bin/python"
        py.parent.mkdir(parents=True); py.symlink_to(sys.executable)
        env = {**os.environ, "REPO_DIR": str(ROOT), "FORGE_DIR": str(self.forge),
               "MODEL_DIR": str(self.model.parent), "MODEL_FILE": self.model.name, "MODEL_SHA256": self.sha,
               "WAI_RUNTIME_DIR": str(self.root / "runtime"), "WAI_PROFILE_MODEL_ID": "hswq", "TUNNEL": "none", "MPLBACKEND": "module://matplotlib_inline.backend_inline"}
        command = """source "$1"; prepare_launch; [[ "$MPLBACKEND" == Agg ]]; "$FORGE_DIR/venv/bin/python" -c 'import os; assert os.environ["MPLBACKEND"] == "Agg"'"""
        result = subprocess.run(["bash", "-c", command, "test", str(ROOT / "colab/setup_forge.sh")],
                                env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(cp.read_object(self.config)["forge_checkpoint_xl"], self.model.name)
        self.assertEqual(cp.read_object(self.config)["xl_t2i_cfg"], 1.0)

    def test_11_upstream_preset_and_scanner(self):
        upstream = os.environ.get("FORGE_AUDIT_SOURCE_DIR")
        if not upstream:
            # Offline tái hiện đúng getattr: key có default None nên KHÔNG fallback.
            options = types.SimpleNamespace(sd_model_checkpoint=self.model.name, forge_checkpoint_sd=None, forge_checkpoint_xl=None)
            self.assertIsNone(getattr(options, "forge_checkpoint_sd", options.sd_model_checkpoint))
            cp.configure_checkpoint(self.forge, self.model, self.sha)
            self.assertEqual(cp.read_object(self.config)["forge_checkpoint_xl"], self.model.name)
            return
        upstream = Path(upstream)
        presets = {}
        exec(compile((upstream / "audit_modules_forge_presets.py").read_text(), "presets", "exec"), presets)
        option_ns = {"json": json, "sys": sys, "gr": types.SimpleNamespace(), "options_builtin_fields": {"data_labels", "data", "restricted_opts", "typemap"},
                     "cmd_opts": types.SimpleNamespace(freeze_settings=False, freeze_settings_in_sections=None, freeze_specific_settings=None, hide_ui_dir_config=False)}
        selected_nodes(upstream / "audit_modules_options.py", {"OptionInfo", "Options"}, option_ns)
        labels = {k: option_ns["OptionInfo"](v) for k, v in {
            "forge_preset": "sd", "sd_model_checkpoint": "", "forge_checkpoint_sd": None,
            "forge_checkpoint_xl": None, "sd_modules_dropdown_use_short": True,
        }.items()}
        opts = option_ns["Options"](labels, [])
        opts.load(str(self.config))
        ns = {"shared": types.SimpleNamespace(opts=opts, config_filename=str(self.config)),
              "gr": types.SimpleNamespace(update=lambda **kwargs: kwargs, skip=lambda: {}), "os": os,
              "module_map": {}, **{k: presets[k] for k in ("use_shift", "use_distill", "is_video")}}
        selected_nodes(upstream / "audit_modules_forge_main_entry.py", {"on_preset_change"}, ns)
        self.assertIsNone(ns["on_preset_change"]("sd")[0]["value"])  # lỗi UI v1.0.1 thật
        cp.configure_checkpoint(self.forge, self.model, self.sha)
        opts.load(str(self.config))
        self.assertEqual(ns["on_preset_change"]("xl")[0]["value"], self.model.name)
        self.assertEqual(ns["on_preset_change"]("xl")[3]["value"], 25)

        # Scanner/CheckpointInfo/selector thật của Neo, chỉ mock cache/torch host.
        scan_shared = types.SimpleNamespace(opts=types.SimpleNamespace(list_hidden_files=False, sd_model_checkpoint=self.model.name))
        util_ns = {"os": os, "re": re, "shared": scan_shared}
        selected_nodes(upstream / "audit_modules_util.py", {"natural_sort_key", "walk_files"}, util_ns)
        scan_shared.walk_files = util_ns["walk_files"]
        loader_ns = {"os": os, "shared": scan_shared}
        selected_nodes(upstream / "audit_modules_modelloader.py", {"load_models"}, loader_ns)
        sd_ns = {"os": os, "sys": sys, "re": re, "shared": scan_shared,
                 "cmd_opts": types.SimpleNamespace(ckpt_dirs=[str(self.model.parent)]),
                 "model_path": str(self.forge / "models/Stable-diffusion"),
                 "checkpoints_list": {}, "checkpoint_aliases": {},
                 "cache": types.SimpleNamespace(cached_data_for_file=lambda _a, _b, _c, fn: fn()),
                 "errors": types.SimpleNamespace(display=lambda *args, **kw: None, report=lambda *args, **kw: None),
                 "hashes": types.SimpleNamespace(sha256_from_cache=lambda name, key: cp.sha256_file(Path(name))),
                 "modelloader": types.SimpleNamespace(load_models=loader_ns["load_models"])}
        selected_nodes(upstream / "audit_modules_sd_models.py", {"CheckpointInfo", "model_hash", "read_metadata_from_safetensors", "list_models", "select_checkpoint", "checkpoint_tiles"}, sd_ns)
        sd_ns["list_models"]()
        self.assertIn(self.model.name, sd_ns["checkpoint_tiles"]())
        chosen = sd_ns["select_checkpoint"]()
        self.assertTrue(os.path.samefile(chosen.filename, self.model))
        print("✔ Hàm on_preset_change, scanner, CheckpointInfo và selector nguyên bản Forge Neo vượt hồi quy.")

    def test_12_registry_same_name_wrong_file_rejected(self):
        wrong = self.root / "wrong" / self.model.name
        wrong.parent.mkdir(); wrong.write_bytes(safetensors())
        with self.assertRaises(cp.CheckpointError):
            cp.registered_model([{"filename": str(wrong), "model_name": self.model.stem}], self.model, self.sha)
        with self.assertRaises(cp.CheckpointError):
            cp.registered_model([{"filename": str(self.model), "sha256": "0" * 64}], self.model, self.sha)

        hardlink = self.root / "hardlink.safetensors"
        os.link(self.model, hardlink)
        hardlink_entry = {"filename": str(hardlink), "sha256": self.sha}
        self.assertEqual(cp.registered_model([hardlink_entry], self.model, self.sha), hardlink_entry)

    def test_13_api_preset_smoke_and_readonly_diagnostics(self):
        cp.configure_checkpoint(self.forge, self.model, self.sha)
        state = self.root / "state"; state.mkdir()
        (state / "model.json").write_text(json.dumps({"file": self.model.name, "dir": str(self.model.parent), "sha256": self.sha}))
        options = {"sd_model_checkpoint": self.model.name, "forge_preset": "xl", "forge_checkpoint_xl": self.model.name,
                   "sd_checkpoint_hash": self.sha, "private_api_key": "MUST_NOT_APPEAR"}
        image_response = {"images": [base64.b64encode(png()).decode()], "info": json.dumps({"sd_model_hash": self.sha[:10]})}
        request_body = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(handler):
                if handler.path.endswith("/sd-models"):
                    data = [{"filename": str(self.model), "title": self.model.name, "sha256": self.sha}]
                elif handler.path.endswith("/options"):
                    data = options
                else:
                    data = {"ckpt_dirs": [str(self.model.parent)], "api_auth": "MUST_NOT_APPEAR"}
                handler.send(data)
            def do_POST(handler):
                request_body.append(json.loads(handler.rfile.read(int(handler.headers["Content-Length"]))))
                handler.send(image_response)
            def send(handler, data):
                body = json.dumps(data).encode(); handler.send_response(200)
                handler.send_header("Content-Length", str(len(body))); handler.end_headers(); handler.wfile.write(body)
            def log_message(handler, *args):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            cp.verify_api(base, self.model, self.sha)
            options["forge_checkpoint_xl"] = None
            with self.assertRaises(cp.CheckpointError):
                cp.verify_api(base, self.model, self.sha)
            cp.verify_api(base, self.model, self.sha, registry_only=True)
            options["forge_checkpoint_xl"] = self.model.name
            output = self.root / "runtime/smoke.png"
            cp.smoke_test(base, self.model, self.sha, output)
            cp.validate_png(output.read_bytes(), 256, 256)
            self.assertEqual(request_body[-1]["steps"], 1)
            self.assertFalse(request_body[-1]["enable_hr"])
            image_response["info"] = "{}"  # cold hash cache: dùng full loaded hash của Neo
            cp.smoke_test(base, self.model, self.sha, output)
            image_response["info"] = json.dumps({"sd_model_hash": "deadbeef"})
            with self.assertRaises(cp.CheckpointError):
                cp.smoke_test(base, self.model, self.sha, output)
            image_response["images"] = [base64.b64encode(b"PNG-header-only").decode()]
            with self.assertRaises(cp.CheckpointError):
                cp.smoke_test(base, self.model, self.sha, output)
            before = {str(p): p.read_bytes() for p in self.forge.rglob("*.json")}
            report = diagnostics.collect(ROOT, self.forge, self.model.parent, self.model.name, state, server.server_port)
            after = {str(p): p.read_bytes() for p in self.forge.rglob("*.json")}
            self.assertEqual(before, after)
            self.assertNotIn("MUST_NOT_APPEAR", json.dumps(report))
            self.assertTrue(report["api"]["checkpoint_da_dang_ky_va_chon"])
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)

    def test_14_cli_reject_conflicting_paths_and_invalid_smoke(self):
        for args in (("--forge-args", "--ui-settings-file /tmp/other.json"),
                     ("--forge-args", "--data-dir=/tmp/other"), ("--forge-args", "--port 9000"),
                     ("--forge-args", "'unclosed"), ("--smoke-test", "--no-launch"),
                     ("--smoke-test", "--doctor"), ("--smoke-test", "--only", "launch")):
            with self.subTest(args=args):
                result = subprocess.run(["bash", str(ROOT / "colab/install.sh"), *args],
                                        capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)


    def test_15_stale_buddy_not_preferred_and_api1_rejected(self):
        download = self.root / "download"; download.mkdir()
        install = download / "install.sh"
        install.write_bytes((ROOT / "colab/install.sh").read_bytes())
        (download / "setup_forge.sh").write_text("SETUP_API_VERSION=1\nexit 88\n")
        repo = self.root / "repo"; (repo / "colab").mkdir(parents=True)
        canonical = repo / "colab/setup_forge.sh"
        canonical.write_text("SETUP_API_VERSION=2\necho 'canonical'\n")
        env = {**os.environ, "REPO_DIR": str(repo), "FORGE_DIR": str(self.forge), "MODEL_DIR": str(self.model.parent),
               "WAI_RUNTIME_DIR": str(self.root / "runtime"), "WAI_LOG": str(self.root / "log")}
        r = subprocess.run(["bash", "-c", 'source "$1"; locate_setup; printf "%s" "$SETUP"', "test", str(install)],
                           env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(r.stdout, str(canonical))
        canonical.write_text("SETUP_API_VERSION=1\nexit 88\n")
        r = subprocess.run(["bash", "-c", 'source "$1"; run_setup stop', "test", str(install)],
                           env=env, capture_output=True, text=True, timeout=15)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("không tương thích", r.stderr)

    def test_16_existing_old_repo_can_update_before_new_file_check(self):
        repo = self.root / "repo-old"
        (repo / ".git").mkdir(parents=True)
        (repo / "colab/prompt_lib").mkdir(parents=True)
        for name in ("danbooru_e621.csv", "danbooru_e621_nounderscore.csv", "danbooru_e621_vi.csv", "danbooru_e621_vi_translation.csv"):
            (repo / name).write_text("fixture\n")
        (repo / "colab/setup_forge.sh").write_text("SETUP_API_VERSION=1\n")
        (repo / "colab/prompt_lib/index.py").write_text("# fixture\n")
        commands = r"""
source "$1"
git() {
  case "$*" in
    *"branch --show-current"*) printf 'arena/88f01d31-ai-anime3\n' ;;
    *"remote get-url origin"*) printf 'https://github.com/manhlee1196-boop/ai-anime3\n' ;;
    *"status --porcelain"*) return 0 ;;
    *) return 1 ;;
  esac
}
repo_git() {
  if [[ "$1" == fetch ]]; then
    cp "$PROJECT_SOURCE/colab/checkpoint_tools.py" "$PROJECT_SOURCE/colab/diagnostics.py" "$PROJECT_SOURCE/colab/forge_compat.py" "$REPO_DIR/colab/"
    cp "$PROJECT_SOURCE/colab/setup_forge.sh" "$REPO_DIR/colab/setup_forge.sh"
    cp "$PROJECT_SOURCE/colab/prompt_lib/editing.py" "$PROJECT_SOURCE/colab/prompt_lib/workflow.py" "$REPO_DIR/colab/prompt_lib/"
    cp "$PROJECT_SOURCE/colab/prompt_lib/history.py" "$PROJECT_SOURCE/colab/prompt_lib/history_ui.py" "$REPO_DIR/colab/prompt_lib/"
  fi
  return 0
}
stage_repo
"""
        env = {**os.environ, "REPO_DIR": str(repo), "PROJECT_SOURCE": str(ROOT), "WAI_LOG": str(self.root / "log")}
        r = subprocess.run(["bash", "-c", commands, "test", str(ROOT / "colab/install.sh")],
                           env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((repo / "colab/checkpoint_tools.py").exists())
        self.assertIn("fast-forward", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
