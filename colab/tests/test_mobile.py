"""Hồi quy bản tối ưu điện thoại: 10 mục CSS/JS, đồng bộ file sinh, móc UI.

Stdlib thuần (không cần gradio/GPU/mạng) + ``node --check`` nếu máy có node:
  python3 colab/tests/test_mobile.py
"""
import re
import shutil
import subprocess
import tempfile
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "colab"))
from prompt_lib import mobile  # noqa: E402

COLAB = ROOT / "colab"
EXT = COLAB / "extension/vi-prompt-builder"


def read(path):
    return path.read_text(encoding="utf-8")


class MobileCssTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = mobile.mobile_css()

    def test_01_muoi_muc_day_du_va_co_banner(self):
        self.assertEqual(len(mobile.SECTIONS), 10)
        for i, (_sid, title, _body) in enumerate(mobile.SECTIONS, start=1):
            with self.subTest(muc=i):
                self.assertIn(f"Mục {i}", title)
                self.assertIn(f"Mục {i}", self.css)
        ids = [s[0] for s in mobile.SECTIONS]
        self.assertEqual(len(set(ids)), 10)

    def test_02_desktop_khong_doi(self):
        # Ngoài Mục 1 (nền) và :focus-visible ở Mục 10, mọi mục phải nằm trong @media.
        for sid, _title, body in mobile.SECTIONS:
            if sid in ("viewport-nen", "kha-dung-ngang"):
                continue
            with self.subTest(muc=sid):
                stripped = re.sub(r"/\*.*?\*/", "", body, flags=re.S).strip()
                self.assertTrue(stripped.startswith("@media"), sid)
        # Không tước quyền phóng to của người dùng ở bất cứ đâu.
        for text in (self.css, mobile.mobile_head(), mobile.mobile_js()):
            self.assertNotIn("maximum-scale", text)
            self.assertNotIn("user-scalable=no", text)

    def test_03_diem_gay_va_quy_tac_then_chot(self):
        for needle in (
            "@media (max-width: 900px)", "@media (max-width: 640px)", "@media (max-width: 480px)",
            "@media (pointer: coarse)",                       # Mục 3 cảm ứng
            "min-height: 48px", "touch-action: manipulation",
            "font-size: 16px !important",                    # Mục 4 chống iOS zoom
            "env(safe-area-inset-bottom)",                   # Mục 1/7 vùng an toàn
            "position: sticky",                              # Mục 5 cột tag + Mục 7 nút dính
            ".wai-col-main", ".wai-row-2",                   # Mục 2 một cột
            ".wai-results", ".wai-history-table", ".wai-gallery",
            "prefers-reduced-motion",                        # Mục 9
            "orientation: landscape",                        # Mục 10
            "#txt2img_generate",                             # tab gốc Forge
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.css)
        # Ngoặc CSS cân bằng (bắt lỗi gõ thiếu } làm hỏng cả file phía sau).
        self.assertEqual(self.css.count("{"), self.css.count("}"))
        # Không dựa vào class băm của Svelte (đổi theo bản Gradio).
        self.assertIsNone(re.search(r"svelte-[a-z0-9]{5,}", self.css))

    def test_04_file_sinh_dong_bo_nguon(self):
        self.assertEqual(read(EXT / "style.css"), mobile.render_style_css())
        self.assertEqual(read(EXT / "javascript/vi_mobile.js"), mobile.render_extension_js())

    def test_05_head_va_js(self):
        head = mobile.mobile_head()
        self.assertIn('name="viewport"', head)
        self.assertIn("viewport-fit=cover", head)
        self.assertIn("waiMobileApply", head)
        js = mobile.mobile_js()
        for needle in ("enterkeyhint", "autocapitalize", "autocorrect", "spellcheck",
                       "loading', 'lazy'", "pointer: coarse", "onUiLoaded"):
            with self.subTest(needle=needle):
                self.assertIn(needle, js)
        node = shutil.which("node")
        if node:
            for name, text in (("app_head", js), ("extension", read(EXT / "javascript/vi_mobile.js"))):
                with self.subTest(js=name):
                    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as fh:
                        fh.write(text)
                        tmp = fh.name
                    try:
                        proc = subprocess.run([node, "--check", tmp],
                                              capture_output=True, text=True, timeout=30)
                    finally:
                        Path(tmp).unlink(missing_ok=True)
                    self.assertEqual(proc.returncode, 0, proc.stderr)


class MobileWiringTests(unittest.TestCase):
    HOOKS = ("wai-row-main", "wai-col-main", "wai-row-2", "wai-search", "wai-results",
             "wai-prompt-box", "wai-build-action", "wai-generate-action",
             "wai-result-gallery", "wai-group-table")

    def test_06_app_doc_lap(self):
        src = read(COLAB / "prompt_builder.py")
        for hook in self.HOOKS:
            with self.subTest(hook=hook):
                self.assertIn(hook, src)
        self.assertIn("min_width=0", src)                 # bỏ min-width 320px gây tràn
        self.assertIn('_mobile_kwargs("blocks")', src)    # Gradio <6
        self.assertIn('_mobile_kwargs("launch")', src)    # Gradio >=6
        self.assertIn("BooleanOptionalAction", src)       # --mobile/--no-mobile
        self.assertIn("WAI_MOBILE_OPT", src)

    def test_07_tab_forge_va_panel_anh(self):
        tab = read(EXT / "scripts/vi_prompt_tab.py")
        for hook in self.HOOKS:
            with self.subTest(hook=hook):
                self.assertIn(hook, tab)
        self.assertIn("min_width=0", tab)
        self.assertNotIn("mobile_css", tab)               # Forge tự nạp style.css, Blocks con không nhận css
        history = read(COLAB / "prompt_lib/history_ui.py")
        for hook in ("wai-history-gallery", "wai-history-table", "wai-history-original"):
            with self.subTest(hook=hook):
                self.assertIn(hook, history)

    def test_08_bo_cai_kiem_tra_file_mobile(self):
        installer = read(COLAB / "install.sh")
        setup = read(COLAB / "setup_forge.sh")
        for name, text in (("install.sh", installer), ("setup_forge.sh", setup)):
            with self.subTest(file=name):
                self.assertIn("mobile.py", text)
                self.assertIn("style.css", text)
                self.assertIn("vi_mobile.js", text)
        # extras_ready phải đòi file mobile: bản cài cũ thiếu chúng sẽ chạy lại extras.
        extras = installer.split("extras_ready()")[1].split("}")[0]
        self.assertIn("vi-prompt-builder/style.css", extras)
        self.assertIn("vi-prompt-builder/javascript/vi_mobile.js", extras)

    def test_09_tai_lieu(self):
        doc = read(COLAB / "MOBILE.md")
        for i in range(1, 11):
            with self.subTest(muc=i):
                self.assertIn(f"Mục {i}", doc)
        self.assertIn("make_mobile_assets.py", doc)
        self.assertIn("MOBILE.md", read(COLAB / "README.md"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
