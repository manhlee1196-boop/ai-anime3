"""Album file-backed: CPU/offline, ảnh fixture nhỏ; không model/torch/GPU.

.venv/bin/python colab/tests/test_image_history.py
"""
import dataclasses
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "colab"))
from PIL import Image, PngImagePlugin
from prompt_lib.history import ImageHistory, MAX_PAGE_SIZE, _seed_from_parameters, forge_output_roots


class ImageHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wai-history-")
        self.base = Path(self.tmp.name)
        self.output = self.base / "output"
        self.output.mkdir()
        self.cache = self.base / "cache"
        self.store = ImageHistory([self.output], self.cache)

    def tearDown(self):
        self.tmp.cleanup()

    def image(self, name="sample.png", seed=42, root=None, timestamp=1780000000):
        path = (root or self.output) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        info = PngImagePlugin.PngInfo()
        if seed is not None:
            info.add_text("parameters", f"PRIVATE-PROMPT Seed: 9999\nNegative prompt: private\nSteps: 25, Sampler: Euler a, CFG scale: 6, Seed: {seed}, Size: 32x48")
        with Image.new("RGB", (32, 48), "#abbfed") as image:
            image.save(path, pnginfo=info)
        os.utime(path, (timestamp, timestamp))
        return path

    def test_01_lazy_store_and_safe_roots(self):
        self.assertFalse(self.cache.exists())
        self.assertEqual(len(self.store.roots), 1)
        roots = forge_output_roots(self.base, {"outdir_txt2img_samples": "custom", "outdir_img2img_samples": str(self.output), "outdir_samples": ""})
        self.assertIn(self.base / "custom", roots)
        self.assertNotIn(self.base, roots)
        self.assertEqual(len(ImageHistory([self.output, self.output / "date"], self.cache).roots), 1)

    def test_02_index_header_seed_and_original_bytes_preserved(self):
        path = self.image("2026-10-12/áo dài.png")
        before = path.read_bytes()
        self.store.refresh()
        records, total, _, _ = self.store.page()
        self.assertEqual(total, 1)
        record = records[0]
        self.assertEqual(record.seed, 42)
        self.assertEqual((record.width, record.height), (32, 48))
        self.assertEqual(record.table_row()[1], "áo dài.png")
        self.assertEqual(len(record.table_row()), 5)
        thumbnail = self.store.thumbnail(record)
        self.assertIsInstance(thumbnail, str)
        with Image.open(thumbnail) as preview:
            self.assertEqual(preview.format, "WEBP")
            self.assertLessEqual(max(preview.size), 384)
            self.assertNotIn("parameters", preview.info)
        self.assertEqual(path.read_bytes(), before)
        self.assertNotIn(b"PRIVATE-PROMPT", self.store.db_path.read_bytes())
        with Image.open(path) as original:
            self.assertIn("Seed: 42", original.info["parameters"])

    def test_03_paging_newest_first_and_bounded_ids(self):
        for i in range(29):
            self.image(f"{i:03d}.png", i, timestamp=1780000000+i)
        self.store.refresh()
        records, total, number, pages = self.store.page(1, 12)
        self.assertEqual((total, number, pages, len(records)), (29, 1, 3, 12))
        self.assertEqual([r.seed for r in records], list(range(28,16,-1)))
        last, _, number, _ = self.store.page(999, 12)
        self.assertEqual((number, len(last)), (3, 5))
        large, _, _, _ = self.store.page(1, 100000)
        self.assertEqual(len(large), MAX_PAGE_SIZE)
        self.assertTrue(all(isinstance(r.path, str) for r in large))
        self.assertFalse(any(isinstance(v, Image.Image) for r in large for v in dataclasses.asdict(r).values()))

    def test_04_refresh_deduplicates_and_restart_restores(self):
        self.image()
        self.store.refresh()
        first = self.store.page()[0][0]
        for _ in range(6):
            with patch("PIL.Image.open", side_effect=AssertionError("unchanged header must not reopen")):
                self.store.refresh()
            self.assertEqual(self.store.page()[1], 1)
        other = ImageHistory([self.output], self.cache)
        self.assertEqual(other.get(first.id), first)
        self.assertEqual(other.page()[1], 1)

    def test_05_changed_and_deleted_files_do_not_serve_stale_seed(self):
        path = self.image()
        self.store.refresh()
        first = self.store.page()[0][0]
        self.image(seed=71, timestamp=1780000020)
        self.assertIsNone(self.store.get(first.id))
        self.store.refresh()
        self.assertEqual(self.store.get(first.id).seed, 71)
        path.unlink()
        self.assertIsNone(self.store.get(first.id))
        self.store.refresh()
        self.assertEqual(self.store.page()[1], 0)
        self.assertTrue(self.output.is_dir())

    def test_06_symlink_and_outside_paths_rejected(self):
        outside = self.image(root=self.base / "outside")
        (self.output / "link.png").symlink_to(outside)
        (self.output / "linked-dir").symlink_to(outside.parent, target_is_directory=True)
        self.image("inside.png")
        self.store.refresh()
        self.assertEqual(self.store.page()[1], 1)
        self.assertIsNone(self.store._safe_path(outside))
        self.assertIsNone(self.store._safe_path(self.output / "link.png"))
        self.assertIsNone(self.store.get(True))
        self.assertIsNone(self.store.get("1"))
        self.assertIsNone(self.store.get(-1))

    def test_07_grid_seed_not_reused_unknown_seed_and_sidecar(self):
        self.image("txt2img-grids/grid-0001.png", 123)
        unknown = self.image("without-info.png", None)
        sidecar = self.image("sidecar.png", None)
        sidecar.with_suffix(".txt").write_text("private\nSteps: 25, Seed: 77, Size: 32x48")
        self.image("wai17_sample_seed456.png", None)
        self.store.refresh()
        records = {Path(r.path).name: r for r in self.store.page()[0]}
        self.assertTrue(records["grid-0001.png"].is_grid)
        self.assertIsNone(records["grid-0001.png"].seed)
        self.assertIsNone(records[unknown.name].seed)
        self.assertEqual(records[sidecar.name].seed, 77)
        self.assertEqual(records["wai17_sample_seed456.png"].seed, 456)

    def test_08_corrupt_files_and_hidden_cache_not_indexed(self):
        (self.output / "bad.png").write_text("PRIVATE-NOT-AN-IMAGE")
        self.image(".wai-history/previews/hidden.png")
        self.image("normal.png")
        self.store.refresh()
        self.assertEqual(self.store.page()[1], 1)
        self.assertEqual(Path(self.store.page()[0][0].path).name, "normal.png")

    def test_09_thumbnail_big_image_guard_and_cache(self):
        original = self.image()
        before = hashlib.sha256(original.read_bytes()).hexdigest()
        self.store.refresh()
        record = self.store.page()[0][0]
        # Header fixture đã kiểm, nhưng mô phỏng kích thước rất lớn trong chỉ mục:
        # phải dùng placeholder mà không decode ảnh gốc.
        with sqlite3.connect(self.store.db_path) as con:
            con.execute("UPDATE images SET width=5000,height=5000 WHERE id=?", (record.id,))
        large = self.store.get(record.id)
        with patch("PIL.Image.open", side_effect=AssertionError("no large-image decode")):
            preview = self.store.thumbnail(large)
        self.assertTrue(Path(preview).is_file())
        with Image.open(preview) as image:
            self.assertEqual(image.size, (320, 180))
        with patch("PIL.Image.open", side_effect=AssertionError("cached preview reused")):
            self.assertEqual(self.store.thumbnail(large), preview)
        self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(), before)

    def test_10_scan_limit_preserves_previous_index(self):
        self.image("one.png")
        self.image("two.png")
        self.store.refresh()
        with patch("prompt_lib.history.MAX_SCAN_FILES", 1):
            self.store.refresh()
        self.assertTrue(self.store.scan_limited)
        self.assertEqual(self.store.page()[1], 2)

    def test_11_seed_parser_never_uses_prompt_seed_or_invalid_value(self):
        for value in (None, "Seed: 1 in prompt", "Steps: 25, Seed: -1", "Steps: 25, Seed: 4294967296", '{"seed":true}'):
            self.assertIsNone(_seed_from_parameters(value))
        self.assertEqual(_seed_from_parameters('Seed: 999\nSteps: 18, Seed: 22, Size: 832x1216'), 22)
        self.assertEqual(_seed_from_parameters('{"seed":33}'), 33)
        self.assertEqual(_seed_from_parameters('Steps: 10, Seed: 1\nSteps: 25, Seed: 2'), 2)


    def test_12_jpeg_webp_exif_seed_originals_preserved(self):
        for extension, format_name in (("jpg", "JPEG"), ("webp", "WEBP")):
            path = self.output / ("exif." + extension)
            exif = Image.Exif()
            exif[37510] = b"UNICODE\0" + "PRIVATE\nSteps: 25, Seed: 83, Size: 16x24".encode("utf-16-be")
            with Image.new("RGB", (16, 24), "white") as image:
                image.save(path, format=format_name, exif=exif)
            before = path.read_bytes()
            self.store.refresh()
            record = next(r for r in self.store.page()[0] if r.path == str(path))
            self.assertEqual(record.seed, 83)
            self.assertIsNotNone(self.store.thumbnail(record))
            self.assertEqual(path.read_bytes(), before)


    def test_13_history_db_symlink_does_not_modify_foreign_file(self):
        self.cache.mkdir()
        foreign = self.base / "foreign.sqlite3"
        foreign.write_bytes(b"KEEP-FOREIGN-FILE")
        self.store.db_path.symlink_to(foreign)
        with self.assertRaises(OSError):
            self.store.refresh()
        self.assertEqual(foreign.read_bytes(), b"KEEP-FOREIGN-FILE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
