"""Kiểm tra compat với mã Neo nguyên bản + FastAPI/Gradio thật, không Torch/GPU.

NEO_COMPAT_SOURCE=tools/work .venv/bin/python colab/tests/test_forge_compat.py
"""
import ast
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "colab"))
import forge_compat as compat

SOURCE = Path(os.environ.get("NEO_COMPAT_SOURCE", ROOT / "tools/work"))
SOURCES = {
    "modules/api/models.py": "current_modules_api_models.py",
    "modules_forge/main_entry.py": "current_modules_forge_main_entry.py",
}


def extract_function(source, name, namespace):
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), "neo-cpu", "exec"), namespace)


class CompatTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wai-compat-")
        self.addCleanup(self.tmp.cleanup)
        self.forge = Path(self.tmp.name)
        for relative, filename in SOURCES.items():
            original = SOURCE / filename
            if not original.is_file():
                self.skipTest(f"Cần mã Neo nguyên bản: {original}")
            destination = self.forge / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(original.read_bytes())
        self.before = {path: (self.forge / path).read_bytes() for path in SOURCES}

    def tearDown(self):
        self.tmp.cleanup()

    def test_01_guarded_patch_backup_idempotency_and_check(self):
        self.assertFalse(compat.check(self.forge))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(compat.apply(self.forge), 2)
            self.assertEqual(compat.apply(self.forge), 0)
        self.assertTrue(compat.check(self.forge))
        for path, data in self.before.items():
            backups = list((self.forge / path).parent.glob((self.forge / path).name + ".wai-compat-*.bak"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), data)
            ast.parse((self.forge / path).read_text())
        self.assertFalse((self.forge / "config.json").exists())

    def test_02_unknown_ui_source_does_not_partially_patch_api(self):
        path = self.forge / "modules_forge/main_entry.py"
        path.write_text(path.read_text().replace("label=\"Checkpoint\"", "label=\"Other\"", 1))
        with self.assertRaises(compat.CompatError):
            compat.apply(self.forge)
        self.assertEqual((self.forge / "modules/api/models.py").read_bytes(), self.before["modules/api/models.py"])
        self.assertFalse(list(self.forge.rglob("*.bak")))

    def test_03_marker_tampering_rejected(self):
        with contextlib.redirect_stdout(io.StringIO()):
            compat.apply(self.forge)
        path = self.forge / "modules/api/models.py"
        path.write_text(path.read_text().replace("Optional[flag.type]", "str"))
        with self.assertRaises(compat.CompatError):
            compat.check(self.forge)

    def test_04_original_api_500_with_port_int_becomes_200_without_losing_types(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from pydantic import Field, create_model
        from typing import Optional
        import argparse
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--port", type=int, default=None)
        parser.add_argument("--reserve-vram", type=float, default=None)
        parser.add_argument("--listen", action="store_true")
        parser.add_argument("--ckpt-dirs", action="append", default=[])
        opts = parser.parse_args(["--port", "7860", "--reserve-vram", "0.8", "--listen", "--ckpt-dirs", "/content/models"])
        def client_for(source):
            tree = ast.parse(source)
            start = next(i for i, n in enumerate(tree.body) if isinstance(n, ast.Assign)
                         and any(isinstance(t, ast.Name) and t.id == "flags" for t in n.targets))
            end = next(i for i in range(start, len(tree.body)) if isinstance(tree.body[i], ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == "FlagsModel" for t in tree.body[i].targets))
            namespace = {"__name__": "compat_cpu", "parser": parser, "Field": Field, "create_model": create_model, "Optional": Optional}
            exec(compile(ast.Module(body=tree.body[start:end + 1], type_ignores=[]), "FlagsModel", "exec"), namespace)
            app = FastAPI()
            app.add_api_route("/sdapi/v1/cmd-flags", lambda: vars(opts), response_model=namespace["FlagsModel"])
            return TestClient(app, raise_server_exceptions=False)
        with client_for(self.before["modules/api/models.py"].decode()) as client:
            self.assertEqual(client.get("/sdapi/v1/cmd-flags").status_code, 500)
        with contextlib.redirect_stdout(io.StringIO()):
            compat.apply(self.forge)
        with client_for((self.forge / "modules/api/models.py").read_text()) as client:
            response = client.get("/sdapi/v1/cmd-flags")
            self.assertEqual(response.status_code, 200, response.text)
            result = response.json()
            self.assertEqual(result["port"], 7860)
            self.assertEqual(result["reserve_vram"], 0.8)
            self.assertTrue(result["listen"])
            self.assertEqual(result["ckpt_dirs"], ["/content/models"])

    def test_05_real_gradio_dropdown_has_model_before_any_browser_callback(self):
        import gradio as gr
        from gradio.context import Context
        def ToolButton(tooltip=None, **kwargs):
            return gr.Button(**kwargs)
        name = "waiIllustriousSDXL_v170.safetensors"
        for use_short in (False, True):
            model = types.SimpleNamespace(name=name, short_title="waiIllustriousSDXL_v170 [f116b0c78f]")
            choice = model.short_title if use_short else model.name
            def create(source):
                opts = types.SimpleNamespace(sd_model_checkpoint=name, forge_preset="xl", sd_checkpoint_dropdown_use_short=use_short)
                namespace = {"gr": gr, "Context": Context,
                             "shared": types.SimpleNamespace(opts=opts),
                             "sd_models": types.SimpleNamespace(checkpoints_list={name: model}, select_checkpoint=lambda: model),
                             "PresetArch": types.SimpleNamespace(choices=lambda: [("SDXL", "xl")]),
                             "ui_common": types.SimpleNamespace(ToolButton=ToolButton, refresh_symbol="↻"),
                             "refresh_models": lambda: ([choice], []),
                             "forge_unet_storage_dtype_options": {"Automatic": (None, False)},
                             "checkpoint_change": lambda *args: None, "modules_change": lambda *args: None,
                             "dtype_change": lambda *args: None}
                extract_function(source, "make_checkpoint_manager_ui", namespace)
                with gr.Blocks() as app:
                    namespace["make_checkpoint_manager_ui"]()
                return namespace["ui_checkpoint"], app.get_config_file()
            with self.subTest(use_short=use_short):
                old, _ = create(self.before["modules_forge/main_entry.py"].decode())
                self.assertEqual(old.choices, [])
                self.assertIsNone(old.value)
                if not compat.check(self.forge):
                    with contextlib.redirect_stdout(io.StringIO()):
                        compat.apply(self.forge)
                fixed, config = create((self.forge / "modules_forge/main_entry.py").read_text())
                self.assertEqual(fixed.value, choice)
                self.assertEqual(fixed.choices, [(choice, choice)])
                component = next(c for c in config["components"] if c["props"].get("elem_id") == "setting_sd_model_checkpoint")
                self.assertEqual(component["props"]["value"], choice)
                self.assertEqual(len(component["props"]["choices"]), 1)

    def test_06_no_registered_models_keeps_dropdown_empty_honestly(self):
        # Source guard và bootstrap không tự bịa checkpoint hoặc fallback tên khác.
        with contextlib.redirect_stdout(io.StringIO()):
            compat.apply(self.forge)
        text = (self.forge / "modules_forge/main_entry.py").read_text()
        self.assertIn("_wai_ckpt_value = None", text)
        self.assertIn("if _wai_ckpt is not None:", text)
        self.assertIn("if _wai_ckpt_value not in _wai_ckpt_choices:", text)
        import gradio as gr
        namespace = {"gr": gr, "refresh_models": lambda: ([], []),
                     "sd_models": types.SimpleNamespace(select_checkpoint=lambda: None),
                     "shared": types.SimpleNamespace(opts=types.SimpleNamespace(sd_checkpoint_dropdown_use_short=False))}
        exec("def construct():\n" + compat.UI_NEW + "\n    return ui_checkpoint\n", namespace)
        with gr.Blocks():
            dropdown = namespace["construct"]()
        self.assertEqual(dropdown.choices, [])
        self.assertIsNone(dropdown.value)



    def test_07_existing_backup_collision_preserves_both_sources(self):
        import hashlib
        path = self.forge / "modules/api/models.py"
        backup = path.with_name(path.name + ".wai-compat-" + hashlib.sha256(path.read_bytes()).hexdigest()[:12] + ".bak")
        backup.write_bytes(b"foreign backup")
        with self.assertRaises(compat.CompatError), contextlib.redirect_stdout(io.StringIO()):
            compat.apply(self.forge)
        for relative, before in self.before.items():
            self.assertEqual((self.forge / relative).read_bytes(), before)
        self.assertEqual(backup.read_bytes(), b"foreign backup")

    def test_08_late_write_failure_rolls_back_first_source(self):
        original_atomic = compat._atomic_bytes
        def atomic(path, data, mode):
            if str(path).endswith("main_entry.py"):
                raise OSError("fixture write failure")
            return original_atomic(path, data, mode)
        with patch.object(compat, "_atomic_bytes", side_effect=atomic), self.assertRaises(OSError), contextlib.redirect_stdout(io.StringIO()):
            compat.apply(self.forge)
        for relative, before in self.before.items():
            self.assertEqual((self.forge / relative).read_bytes(), before)

    def test_09_readonly_ui_diagnostics_and_flags_do_not_dump_private_data(self):
        import diagnostics
        config = {"private": "auth-secret", "components": [
            {"id": 5, "props": {"elem_id": "txt2img_prompt", "value": "private prompt"}},
            {"id": 10, "props": {"elem_id": "setting_sd_model_checkpoint", "choices": [["wai", "wai"]], "value": "wai", "unrelated": "secret"}},
        ]}
        result = diagnostics.checkpoint_ui_summary(config)
        self.assertTrue(result["tim_thay_dropdown"])
        self.assertTrue(result["checkpoints"][0]["value_in_choices"])
        self.assertNotIn("private", str(result))
        self.assertNotIn("secret", str(result))
        config["components"][1]["props"]["value"] = None
        self.assertFalse(diagnostics.checkpoint_ui_summary(config)["checkpoints"][0]["value_in_choices"])
        import checkpoint_tools
        with patch.object(checkpoint_tools, "api_json", return_value={"port": 7860, "auth": "secret"}):
            self.assertEqual(compat.verify_flags("http://127.0.0.1:7860"), 7860)
        for flags in ({"port": "7860"}, {"port": True}, {"port": 7861}, None):
            with patch.object(checkpoint_tools, "api_json", return_value=flags), self.assertRaises(compat.CompatError):
                compat.verify_flags("http://127.0.0.1:7860")


    def test_10_original_ui_loadsave_keeps_populated_value_with_none_or_stale_default(self):
        import gradio as gr
        import json
        import math
        loadsave_source = (SOURCE / "current_modules_ui_loadsave.py").read_text()
        tree = ast.parse(loadsave_source)
        nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in ("radio_choices", "UiLoadsave")]
        namespace = {"gr": gr, "json": json, "os": os, "math": math, "ToolButton": gr.Button,
                     "InputAccordionImpl": type("AccordionFixture", (), {}),
                     "errors": types.SimpleNamespace(display=lambda *args: None)}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "neo-ui-loadsave", "exec"), namespace)
        choice = "waiIllustriousSDXL_v170.safetensors"
        for saved_value in (None, "old-missing.safetensors"):
            defaults = self.forge / "ui-config.json"
            defaults.write_text(json.dumps({"webui/Checkpoint/value": saved_value, "txt2img/Prompt/value": "private prompt"}))
            before = defaults.read_bytes()
            with gr.Blocks():
                dropdown = gr.Dropdown(label="Checkpoint", choices=[choice], value=choice, elem_id="setting_sd_model_checkpoint")
                loadsave = namespace["UiLoadsave"](str(defaults))
                loadsave.add_component("webui/Checkpoint", dropdown)
            self.assertEqual(dropdown.value, choice)
            self.assertEqual(defaults.read_bytes(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
