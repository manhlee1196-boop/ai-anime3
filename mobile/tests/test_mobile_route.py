#!/usr/bin/env python3
"""Hồi quy route `/vi-mobile` do extension Forge phục vụ.

    python3 mobile/tests/test_mobile_route.py     # cần fastapi (pip install fastapi)

Kiểm tra: extension gắn được app tĩnh vào FastAPI của Forge, `/vi-mobile` chuyển hướng
sang `/vi-mobile/`, và index.html/CSS/JS/icon/dữ liệu tag đều trả 200. Không cần GPU,
không cần Gradio thật (gradio được giả lập tối thiểu để import extension).
"""

import base64
import importlib.util
import io
import random
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

try:
    from PIL import Image
    HAVE_PIL = True
except Exception:                                     # noqa: BLE001
    HAVE_PIL = False

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

    def test_06_mobile_api_health(self):
        response = self.client.get("/vi-mobile/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(response.json()["image_format"], "jpeg")

    @unittest.skipUnless(HAVE_PIL, "cần Pillow để kiểm tra nén ảnh")
    def test_07_txt2img_reuses_standard_handler_and_returns_jpeg(self):
        source = Image.frombytes("RGB", (96, 96), random.Random(17).randbytes(96 * 96 * 3))
        png = io.BytesIO()
        source.save(png, format="PNG")
        encoded = base64.b64encode(png.getvalue()).decode("ascii")
        calls = []
        from pydantic import BaseModel

        class Txt2ImgInput(BaseModel):
            prompt: str
            steps: int = 25
            width: int = 1024
            height: int = 1024

        class Txt2ImgOutput(BaseModel):
            images: list
            parameters: dict
            info: str

        def fake_txt2img(payload: Txt2ImgInput):
            calls.append(payload)
            return Txt2ImgOutput(images=[encoded], parameters={}, info='{"seed": 42}')

        self.app.post("/sdapi/v1/txt2img")(fake_txt2img)
        response = self.client.post("/vi-mobile/api/txt2img", json={
            "prompt": "1girl", "steps": 25, "width": 1024, "height": 1024,
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].prompt, "1girl")
        self.assertEqual(calls[0].steps, 25)
        data = response.json()
        self.assertEqual(data["mobile_image_format"], "jpeg")
        self.assertEqual(data["info"], '{"seed": 42}')
        jpeg = data["images"][0]
        self.assertTrue(jpeg.startswith("data:image/jpeg;base64,"))
        self.assertLess(len(jpeg), len(encoded), "JPEG phải nhỏ hơn PNG base64 của fixture")
        with Image.open(io.BytesIO(base64.b64decode(jpeg.split(",", 1)[1]))) as result:
            self.assertEqual(result.format, "JPEG")
            self.assertEqual(result.size, source.size)

    def test_08_mobile_api_inherits_standard_api_auth(self):
        from fastapi import Depends, FastAPI, HTTPException

        app = FastAPI()
        calls = []

        def deny():
            raise HTTPException(status_code=401, detail="auth required")

        def fake_txt2img(payload: dict):
            calls.append(payload)
            return {"images": [], "parameters": {}, "info": "{}"}

        app.post("/sdapi/v1/txt2img", dependencies=[Depends(deny)])(fake_txt2img)
        self.ext.install_mobile_api(app)
        client = TestClient(app)
        response = client.post("/vi-mobile/api/txt2img", json={"prompt": "1girl"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(calls, [], "Route mobile không được bỏ qua --api-auth")


if __name__ == "__main__":
    unittest.main(verbosity=2)
