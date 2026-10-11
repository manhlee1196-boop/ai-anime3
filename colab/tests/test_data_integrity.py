#!/usr/bin/env python3
"""Kiểm tính toàn vẹn toàn bộ CSV đã xuất; không build/ghi lại dữ liệu."""
import csv
import itertools
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import build_vi as build  # noqa: E402


class DataIntegrity(unittest.TestCase):
    def test_01_all_rows_four_columns_and_identity(self):
        translations = {}
        with (ROOT / "danbooru_e621_vi_translation.csv").open(encoding="utf-8", newline="") as f:
            for row in csv.reader(f):
                self.assertEqual(len(row), 2)
                self.assertTrue(row[0] and row[1])
                self.assertNotIn(row[0], translations)
                translations[row[0]] = row[1]
        self.assertEqual(len(translations), 45513)
        seen, last_count, total = set(), float("inf"), 0
        with ((ROOT / "danbooru_e621.csv").open(encoding="utf-8", newline="") as original,
              (ROOT / "danbooru_e621_nounderscore.csv").open(encoding="utf-8", newline="") as no_under,
              (ROOT / "danbooru_e621_vi.csv").open(encoding="utf-8", newline="") as vietnamese):
            for number, rows in enumerate(itertools.zip_longest(csv.reader(original), csv.reader(no_under), csv.reader(vietnamese)), 1):
                a, b, c = rows
                self.assertTrue(all(r is not None and len(r) == 4 for r in rows), f"Dòng {number}: thiếu/khác số cột")
                tag, category, count, aliases = a
                self.assertNotIn(tag, seen)
                seen.add(tag)
                self.assertTrue(count.isdigit() and int(count) >= 0)
                self.assertLessEqual(int(count), last_count, f"Sai thứ tự post_count tại {tag}")
                last_count = int(count)
                self.assertEqual(b[1:3], a[1:3])
                self.assertEqual(c[1:3], a[1:3])
                self.assertEqual(b[0], build.spaced(tag))
                self.assertEqual(b[3], ",".join(build.spaced_aliases([x for x in aliases.split(",") if x])))
                self.assertEqual(c[0], translations.get(tag, build.spaced(tag)))
                self.assertIn(tag, c[3].split(","))
                if category in {"1", "3", "4", "8", "9", "10", "11"}:
                    self.assertEqual(c[0], build.spaced(tag))
                    self.assertNotIn(tag, translations)
                total += 1
        self.assertEqual(total, 349714)
        self.assertTrue(set(translations).issubset(seen))

    def test_02_unicode_and_ascii_emoticons(self):
        for tag in ("ಠ_ಠ", "^_^", "0_0", "o_o", "|_|", "._.", "<_<", ">_o"):
            self.assertEqual(build.spaced(tag), tag)
            self.assertEqual(build.spaced_aliases([tag]), [tag])
        self.assertEqual(build.spaced("holding_sword"), "holding sword")

    def test_03_translation_regression(self):
        with (ROOT / "danbooru_e621_vi_translation.csv").open(encoding="utf-8", newline="") as f:
            meanings = dict(csv.reader(f))
        for tag, vi in {"holding_sword": "cầm kiếm", "ao_dai": "áo dài", "deer_antlers": "gạc hươu",
                        "egyptian_vulture": "kền kền Ai Cập", "deer_taur": "hươu dạng nhân mã"}.items():
            self.assertEqual(meanings[tag], vi)

    def test_04_original_matches_specified_source_if_available(self):
        source = ROOT / "tools/source_merged_2026-10-01.csv"
        if not source.exists():
            self.skipTest("File nguồn tải lại được, không lưu trong Git")
        with (source.open(encoding="utf-8", newline="") as src,
              (ROOT / "danbooru_e621.csv").open(encoding="utf-8", newline="") as output):
            for number, pair in enumerate(itertools.zip_longest(csv.reader(src), csv.reader(output)), 1):
                self.assertEqual(pair[0], pair[1], f"Bản gốc không khớp nguồn tại dòng {number}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
