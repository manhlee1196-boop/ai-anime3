#!/usr/bin/env python3
"""Hồi quy route `/vi-mobile` do extension Forge phục vụ.

    python3 mobile/tests/test_mobile_route.py     # cần fastapi (pip install fastapi)

Kiểm tra: extension gắn được app tĩnh vào FastAPI của Forge, `/vi-mobile` chuyển hướng
sang `/vi-mobile/`, và index.html/CSS/JS/icon/dữ liệu tag đều trả 200. Không cần GPU,
không cần Gradio thật (gradio được giả lập tối thiểu để import extension).
"""

import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXT_PATH = ROOT / "colab/extension/vi-prompt-builder/scripts/vi_prompt_tab.py"

try:
    from fastapi import FastAPI                      # noqa: F401
    from fastapi.testclient import TestClient         # noqa: F401
    HAVE_FASTAPI = True
except Exception:                                     # noqa: BLE001
    HAVE_FASTAPI = False

GR_NAMES = ("Accordion Button Checkbox CheckboxGroup Dataframe Dropdown Markdown Row Slider "
            "State Tab Tabs Textbox SelectData Blocks Column Gallery Number").split()


def install_fakes():
    """Forge + Gradio tối thiểu để import được extension (chỉ cần API, không cần UI)."""
    class FakeScript:
        alwayson = False
        create_group = True
        section = None
        sorting_priority = 0

    fake_scripts = types.ModuleType("modules.scripts")
    fake_scripts.Script = FakeScript
    fake_scripts.AlwaysVisible = object()
    modules = types.ModuleType("modules")
    modules.scripts = fake_scripts
    sys.modules["modules"] = modules
    sys.modules["modules.scripts"] = fake_scripts

    gradio = types.ModuleType("gradio")
    gradio.__version__ = "4.40.0"
    for name in GR_NAMES:
        setattr(gradio, name, type(name, (), {}))
    gradio.update = lambda **kwargs: kwargs
    sys.modules["gradio"] = gradio


def load_extension():
    spec = importlib.util.spec_from_file_location("vi_prompt_tab_route", EXT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(HAVE_FASTAPI, "cần fastapi để kiểm tra route (pip install fastapi)")
class MobileRoute(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_fakes()
        sys.path.insert(0, str(ROOT / "colab"))
        cls.ext = load_extension()
        cls.app = FastAPI()
        cls.ext.serve_mobile_app(None, cls.app)
        cls.client = TestClient(cls.app)

    def test_01_extension_finds_mobile_app(self):
        self.assertEqual(Path(self.ext.mobile_app_dir()), ROOT / "mobile" / "app")
        self.assertEqual(self.ext.MOBILE_ROUTE, "/vi-mobile")
        # extension không được tự dựng tab riêng (tab "Prompt VN" đã bỏ)
        self.assertFalse(hasattr(self.ext, "on_ui_tabs"))

    def test_02_root_redirects_to_trailing_slash(self):
        response = self.client.get("/vi-mobile", follow_redirects=False)
        self.assertEqual(response.status_code, 307)
        self.assertEqual(response.headers["location"], "/vi-mobile/")

    def test_03_index_is_the_mobile_app(self):
        response = self.client.get("/vi-mobile/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("<title>Anime3", response.text)
        self.assertIn('id="generateBtn"', response.text)

    def test_04_assets_are_served(self):
        for path in ("styles.css", "js/core.js", "js/ui.js", "manifest.webmanifest",
                     "icons/icon-192.png", "sw.js"):
            response = self.client.get(f"/vi-mobile/{path}")
            self.assertEqual(response.status_code, 200, path)
            self.assertGreater(len(response.content), 200, path)

    def test_05_tag_data_is_served_compressed(self):
        response = self.client.get("/vi-mobile/data/tags.json.gz")
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.content), 500_000)
        self.assertEqual(response.content[:2], b"\x1f\x8b")


if __name__ == "__main__":
    unittest.main(verbosity=2)
