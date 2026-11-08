#!/usr/bin/env python3
"""Hồi quy app điện thoại: dữ liệu sinh ra, tài nguyên tĩnh và id trong HTML.

    python3 mobile/tests/test_mobile_assets.py

Không cần GPU, không cần mạng: chỉ đọc file trong repo và dựng lại dữ liệu tag.
"""

import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOBILE = ROOT / "mobile"
APP = MOBILE / "app"
sys.path.insert(0, str(ROOT / "colab"))


def load_build_data():
    spec = importlib.util.spec_from_file_location("mobile_build_data", MOBILE / "build_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILD = load_build_data()


class MobileData(unittest.TestCase):
    """Dữ liệu app phải sinh lại được từ CSV và đúng hợp đồng với JS."""

    @classmethod
    def setUpClass(cls):
        cls.payload = BUILD.build_payload(BUILD.DEFAULT_MIN_COUNT)
        cls.rows = cls.payload["tags"]
        cls.groups = cls.payload["groups"]

    def test_01_build_is_reproducible(self):
        """`--check` phải khớp: file đã commit không lệch so với CSV hiện tại."""
        problems = BUILD.check(self.payload)
        self.assertEqual(problems, [], "\n".join(problems))

    def test_02_columns_match_app_expectation(self):
        """Mỗi dòng là [tag, count, category, group, vi] — data.js đọc đúng 5 cột này."""
        for row in self.rows[:200] + self.rows[-200:]:
            self.assertEqual(len(row), 5, row)
            self.assertIsInstance(row[0], str)
            self.assertIsInstance(row[1], int)
            self.assertIsInstance(row[2], int)
            self.assertIsInstance(row[3], int)
            self.assertTrue(isinstance(row[4], str) or row[4] == 0, row)

    def test_03_tags_sorted_by_popularity(self):
        """Tag phổ biến đứng trước: danh sách mặc định của app là "phổ biến"."""
        counts = [row[1] for row in self.rows]
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_04_every_row_respects_min_count_or_has_vi(self):
        for row in self.rows:
            self.assertTrue(row[1] >= self.payload["min_count"] or row[4],
                            f"{row[0]} vừa hiếm vừa không có nghĩa tiếng Việt")

    def test_05_group_index_is_valid(self):
        for row in self.rows:
            self.assertGreaterEqual(row[3], 0)
            self.assertLess(row[3], len(self.groups), row[0])

    def test_06_presets_complete(self):
        presets = self.payload["presets"]
        for key in ("quality", "negative", "ratings", "sizes", "defaults",
                    "samplers", "style_presets"):
            self.assertIn(key, presets)
        self.assertGreaterEqual(len(presets["quality"]), 4)
        self.assertGreaterEqual(len(presets["negative"]), 4)
        self.assertEqual([r["id"] for r in presets["ratings"]],
                         ["general", "sensitive", "questionable", "explicit"])
        self.assertEqual(presets["defaults"]["steps"], 25)
        self.assertEqual(presets["defaults"]["sampler_name"], "Euler a")
        self.assertGreaterEqual(len(presets["style_presets"]), 12)
        for label, size in presets["sizes"]:
            self.assertEqual(len(size), 2, label)
            self.assertEqual(size[0] % 8, 0, label)
            self.assertEqual(size[1] % 8, 0, label)

    def test_07_styles_cover_csv(self):
        self.assertEqual(len(self.payload["styles"]), 506)
        for row in self.payload["styles"]:
            self.assertEqual(len(row), 3)
            self.assertTrue(all(row))

    def test_08_quick_chips_only_from_browse_groups(self):
        allowed = set(self.payload["browse_groups"])
        for group, items in self.payload["quick"].items():
            self.assertIn(group, allowed)
            self.assertTrue(items and len(items) <= BUILD.QUICK_PER_GROUP)

    def test_09_icon_files_exist(self):
        icons = APP / "icons"
        for name in ("icon-192.png", "icon-512.png", "maskable-512.png", "apple-touch-icon.png"):
            data = (icons / name).read_bytes()
            self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"), name)
            self.assertGreater(len(data), 1000, name)


class MobileAssets(unittest.TestCase):
    """HTML/CSS/JS phải trỏ tới file có thật, và mọi id mà ui.js dùng phải tồn tại."""

    @classmethod
    def setUpClass(cls):
        cls.html = (APP / "index.html").read_text(encoding="utf-8")
        cls.ui = (APP / "js" / "ui.js").read_text(encoding="utf-8")
        cls.ids = set(re.findall(r'\bid="([\w-]+)"', cls.html))

    def test_10_referenced_files_exist(self):
        for ref in re.findall(r'(?:src|href)="([^"#:]+)"', self.html):
            self.assertTrue((APP / ref).exists(), f"index.html trỏ tới {ref} nhưng không có")

    def test_11_manifest_matches_files(self):
        manifest = json.loads((APP / "manifest.webmanifest").read_text(encoding="utf-8"))
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["lang"], "vi")
        for icon in manifest["icons"]:
            self.assertTrue((APP / icon["src"]).exists(), icon["src"])
        self.assertEqual(manifest["scope"], "./")

    def test_12_service_worker_shell_exists(self):
        sw = (APP / "sw.js").read_text(encoding="utf-8")
        shell = re.search(r"const SHELL = \[(.*?)\];", sw, re.S).group(1)
        files = re.findall(r"'\./([^']+)'", shell)
        self.assertIn("index.html", files)
        for name in files:
            if name in ("", "."):
                continue
            self.assertTrue((APP / name).exists(), f"sw.js cache {name} nhưng không có")

    def test_13_ui_references_known_element_ids(self):
        """Bắt lỗi gõ sai id — thứ mà test Node không thấy vì không có DOM."""
        used = {name for name in re.findall(r"\$\('#([\w-]+)'\)", self.ui)
                if "${" not in name}
        # các field trong lưới "Tham số nâng cao" được dựng bằng vòng lặp id động
        dynamic = {"seed", "steps", "cfg", "batch", "clipSkip", "hrScale", "denoise"}
        missing = sorted(used - self.ids - dynamic)
        self.assertEqual(missing, [], f"ui.js dùng id không có trong index.html: {missing}")

    def test_14_html_has_no_external_dependency(self):
        """App phải chạy offline trong APK: không CDN, không font ngoài."""
        self.assertNotRegex(self.html, r'src="https?://')
        self.assertNotRegex(self.html, r'href="https?://')

    def test_15_serve_script_compiles(self):
        import py_compile
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            py_compile.compile(str(MOBILE / "serve.py"), cfile=str(Path(tmp) / "serve.pyc"),
                               doraise=True)


class MobileMock(unittest.TestCase):
    """Forge giả của serve.py phải trả PNG thật để UI hiển thị được."""

    def test_16_mock_png_is_valid(self):
        spec = importlib.util.spec_from_file_location("mobile_serve", MOBILE / "serve.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        png = module.demo_png(64, 96, 0.3)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertIn(b"IHDR", png[:32])
        # kích thước ghi trong IHDR
        width = int.from_bytes(png[16:20], "big")
        height = int.from_bytes(png[20:24], "big")
        self.assertEqual((width, height), (64, 96))

    def test_17_mock_render_returns_base64_png(self):
        import base64
        spec = importlib.util.spec_from_file_location("mobile_serve2", MOBILE / "serve.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        forge = module.MockForge()
        result = forge.render({"prompt": "1girl", "width": 256, "height": 256, "steps": 8})
        images = result["images"]
        self.assertEqual(len(images), 1)
        raw = base64.b64decode(images[0])
        self.assertTrue(raw.startswith(b"\x89PNG\r\n\x1a\n"))
        info = json.loads(result["info"])
        self.assertRegex(info["prompt"], "1girl")
        self.assertGreater(info["seed"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
