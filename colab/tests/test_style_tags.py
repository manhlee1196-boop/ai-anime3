#!/usr/bin/env python3
"""Hồi quy danh sách tag phong cách vẽ (`style_tags.csv`), stdlib/CPU, không GPU."""
import csv
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "colab"))
import find_style_tags as style  # noqa: E402
from prompt_lib.styles import PRESETS, StyleLibrary, missing_tags  # noqa: E402

HEADER = ["tag", "vi", "category", "post_count", "nhom", "nguon_vi"]


class StyleTags(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tags = style.load_tags()
        cls.vi = style.load_vi()
        cls.groups = style.collect(cls.tags)

    def test_01_every_tag_exists_in_repository(self):
        """Mọi tag khai báo trong GROUPS phải có thật trong danbooru_e621.csv."""
        for gid, label, names in self.groups:
            self.assertTrue(names, f"nhóm {gid} ({label}) rỗng")
            for tag in names:
                self.assertIn(tag, self.tags, f"{tag} không có trong danbooru_e621.csv")

    def test_02_csv_matches_regenerated_rows(self):
        """style_tags.csv phải khớp đúng thứ tự/khoảng trắng khi sinh lại."""
        rows = style.rows_for(self.groups, self.tags, self.vi)
        with (ROOT / "style_tags.csv").open(encoding="utf-8", newline="") as f:
            got = list(csv.reader(f))
        self.assertEqual(got[0], HEADER)
        self.assertEqual(len(got) - 1, len(rows))
        for number, (want, have) in enumerate(zip(rows, got[1:]), 1):
            self.assertEqual(have, want, f"dòng {number} lệch")

    def test_03_no_tag_appears_twice(self):
        seen = set()
        for gid, label, names in self.groups:
            for tag in names:
                self.assertNotIn(tag, seen, f"{tag} bị lặp (nhóm {gid})")
                seen.add(tag)

    def test_04_every_style_suffix_tag_is_listed(self):
        """Không bỏ sót tag nào có đuôi _(style)."""
        listed = {t for _g, _l, names in self.groups for t in names}
        wanted = style.author_style_tags(self.tags)
        self.assertEqual(wanted - listed, set())
        self.assertGreater(len(wanted), 200)

    def test_05_translation_or_suggestion(self):
        """Tag thiếu bản dịch trong repo phải có nghĩa gợi ý, và được đánh dấu goi_y."""
        rows = style.rows_for(self.groups, self.tags, self.vi)
        for tag, meaning, _cat, _count, _group, source in rows:
            if tag in self.vi:
                self.assertEqual(source, "csv")
                self.assertEqual(meaning, self.vi[tag])
            else:
                self.assertEqual(source, "goi_y", f"{tag} thiếu cả bản dịch lẫn gợi ý")
                self.assertTrue(meaning)

    def test_06_style_library_loads_csv(self):
        """Mục chọn phong cách (prompt_lib.styles) đọc đúng style_tags.csv."""
        lib = StyleLibrary(ROOT)
        self.assertEqual(len(lib), len(style.rows_for(self.groups, self.tags, self.vi)))
        self.assertEqual(len(lib.groups()), 9)
        self.assertEqual(missing_tags(lib), set())
        for group in lib.groups():
            self.assertTrue(lib.entries(group), f"nhóm {group} rỗng")
            self.assertTrue(all(item.vi for item in lib.entries(group)))

    def test_07_style_library_search_and_labels(self):
        lib = StyleLibrary(ROOT)
        self.assertEqual([i.tag for i in lib.search("màu nước")][:1], ["watercolor_(medium)"])
        self.assertEqual([i.tag for i in lib.search("nuoc")][:1], ["watercolor_(medium)"])
        labels = lib.choices("Ánh sáng")
        self.assertEqual(len(lib.tags_of(labels)), len(labels))
        self.assertEqual(lib.tag_of(labels[0]), lib.tags_of(labels)[0])
        self.assertEqual(lib.tags_of([]), [])

    def test_08_presets_only_use_real_tags(self):
        """Mọi tag trong 12 công thức sẵn đều có thật và thuộc đúng kho phong cách."""
        lib = StyleLibrary(ROOT)
        self.assertEqual(len(PRESETS), 12)
        for name in lib.preset_names():
            tags = lib.preset(name)
            self.assertTrue(tags, f"công thức {name} rỗng")
            for tag in tags:
                self.assertIn(tag, lib.items, f"{tag} (công thức {name}) không có trong CSV")
            self.assertTrue(lib.preset_note(name), f"công thức {name} thiếu ghi chú")

    def test_09_counts_match_source_file(self):
        """post_count/category trong CSV phải đúng như file gốc."""
        with (ROOT / "style_tags.csv").open(encoding="utf-8", newline="") as f:
            for tag, _vi, category, count, _group, _src in list(csv.reader(f))[1:]:
                self.assertEqual((int(category), int(count)), self.tags[tag], tag)

    def test_10_all_tags_visible_by_default(self):
        """Không tag nào bị ẩn: nhóm mặc định "Tất cả" trả đủ 506 tag, tìm không cắt."""
        lib = StyleLibrary(ROOT)
        total = len(lib)
        self.assertEqual(total, 506)
        label = lib.all_label()
        self.assertTrue(lib.is_all(None) and lib.is_all(label) and lib.is_all("Tất cả"))
        self.assertFalse(lib.is_all("Ánh sáng"))
        self.assertEqual(lib.group_choices()[0], label)
        self.assertEqual(len(lib.choices()), total)
        self.assertEqual(len(lib.choices(label)), total)
        self.assertEqual(lib.group_count(label), total)
        # gõ tìm: trả mọi tag khớp, không cắt còn 80 như trước
        self.assertGreater(len(lib.choices(None, "a")), 80)
        self.assertEqual([i.tag for i in lib.search("màu nước", limit=0)][:1],
                         ["watercolor_(medium)"])
        # chọn công thức: tag công thức đứng đầu và vẫn còn đủ phần còn lại
        preset = lib.preset("Pixel art game cũ")
        labels = [lib.info(t).label() for t in preset]
        merged = lib.choices_with(labels)
        self.assertEqual(merged[:len(labels)], labels)
        self.assertEqual(len(merged), total)
        self.assertEqual(len(set(merged)), total)
        # in được tag của 12 công thức để người dùng đọc trước khi áp
        md = lib.presets_markdown()
        self.assertIn("watercolor_(medium)", md)
        self.assertEqual(len(lib.preset_lines()), 12)


if __name__ == "__main__":
    unittest.main(verbosity=2)
