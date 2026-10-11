#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sinh các bản CSV danbooru+e621 cho sd-webui-tagcomplete.

Đầu vào : tools/source_merged_2026-10-01.csv   (4 cột: tag,category,post_count,aliases)
Đầu ra  : danbooru_e621.csv                     bản gốc phục hồi
          danbooru_e621_nounderscore.csv        bản đã bỏ dấu gạch dưới
          danbooru_e621_vi.csv                  bản tiếng Việt (4 cột, dùng được ngay)
          danbooru_e621_vi_translation.csv      bản dịch 2 cột cho tính năng Translation

Chạy    : python3 tools/build_vi.py
"""

import csv
import os
import sys
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
SRC = os.path.join(BASE, "source_merged_2026-10-01.csv")

sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "dict"))

from vi_rules import translate_by_rules  # noqa: E402
from vi_compose import Composer  # noqa: E402
from vi_general import VI_GENERAL  # noqa: E402
from vi_e621 import VI_E621  # noqa: E402
from vi_meta import VI_META  # noqa: E402
from vi_species import VI_LORE, VI_SPECIES  # noqa: E402
from vi_extra import (  # noqa: E402
    VI_EXTRA_E621,
    VI_EXTRA_GENERAL,
    VI_EXTRA_SPECIES,
    VI_EXTRA_STEMS,
)
from vi_extra2 import VI_EXTRA_E621_2, VI_EXTRA_GENERAL_2  # noqa: E402
from vi_extra3 import EMOTICONS, VI_EXTRA_E621_3, VI_EXTRA_GENERAL_3  # noqa: E402
from vi_extra4 import VI_EXTRA_SPECIES_2  # noqa: E402
from vi_extra5 import VI_EXTRA_E621_5, VI_EXTRA_GENERAL_5  # noqa: E402

def _merge(*dicts):
    """Gộp nhiều từ điển; từ điển đứng sau ưu tiên hơn."""
    out = {}
    for d in dicts:
        out.update(d)
    return out


# category -> từ điển thủ công
BY_CAT = {
    "0": _merge(VI_GENERAL, VI_EXTRA_GENERAL, VI_EXTRA_GENERAL_2,
               VI_EXTRA_GENERAL_3, EMOTICONS,
               VI_EXTRA_GENERAL_5),               # General (danbooru)
    "5": VI_META,                                   # Meta (danbooru)
    "7": _merge(VI_E621, VI_EXTRA_E621, VI_EXTRA_E621_2,
               VI_EXTRA_E621_3, EMOTICONS,
               VI_EXTRA_E621_5),                  # General (e621)
    "12": _merge(VI_SPECIES, VI_EXTRA_SPECIES, VI_EXTRA_SPECIES_2),  # Species (e621)
    "14": VI_META,                                  # Meta (e621)
    "15": VI_LORE,                                  # Lore (e621)
}
TRANSLATABLE = set(BY_CAT)

# tra cứu hợp nhất, dùng cho quy tắc mẫu và cho tag lệch category.
# Ưu tiên: từ điển đúng category > các từ điển khác > hình vị gốc.
MERGED = {}
for d in [VI_GENERAL, VI_E621, VI_META, VI_SPECIES, VI_LORE,
          VI_EXTRA_GENERAL, VI_EXTRA_E621, VI_EXTRA_SPECIES,
          VI_EXTRA_GENERAL_2, VI_EXTRA_E621_2,
          VI_EXTRA_GENERAL_3, VI_EXTRA_E621_3, EMOTICONS,
          VI_EXTRA_SPECIES_2, VI_EXTRA_STEMS,
          VI_EXTRA_GENERAL_5, VI_EXTRA_E621_5]:
    for k, v in d.items():
        MERGED.setdefault(k, v)

OUT_ORIG = os.path.join(ROOT, "danbooru_e621.csv")
OUT_NOUNDER = os.path.join(ROOT, "danbooru_e621_nounderscore.csv")
OUT_VI = os.path.join(ROOT, "danbooru_e621_vi.csv")
OUT_TRANS = os.path.join(ROOT, "danbooru_e621_vi_translation.csv")


# Emoticon: dấu `_` là nét vẽ của khuôn mặt chứ không phải dấu ngăn cách từ,
# nên GIỮ NGUYÊN (`^_^` mà đổi thành `^ ^` thì hỏng tag).
# Các tag dạng handle/tên riêng có `_` (h&k_g11, k_98, u2_(5798239)...) vẫn bỏ `_`.
EMOTICON_KEEP = {k for k in EMOTICONS if "_" in k} | {
    ">_o", "u_u", "<_<", ">_<;", "o_x", "o_0", "o_<", "<|>_<|>", "<o>_<o>",
    "\u0ca0_\u0ca0", "m0_0m_c", "0o0_w_o0", "19_0v0", "a-o_a", "t_t", "6_9",
    "+_-", "3_3", "._.", "t_k", "u_o", "o_3", "x_3", "^o^", "o_o;", "-_-",
}
EMOTICON_KEEP = {k.encode().decode("unicode_escape") for k in EMOTICON_KEEP}


def spaced(tag):
    """Bỏ dấu gạch dưới, giữ nguyên ngoặc/gạch chéo/gạch nối và emoticon."""
    if tag in EMOTICON_KEEP:
        return tag
    return tag.replace("_", " ")


def spaced_aliases(aliases):
    if not aliases:
        return aliases
    return [a.replace("_", " ") for a in aliases]


# bộ ghép đệ quy cho tag tổ hợp chưa có trong từ điển (dùng chung MERGED)
COMPOSER = Composer(MERGED.get)


def translate(tag, cat):
    """Trả về (bản dịch tiếng Việt, nguồn dịch: dict | rule | compose | none)."""
    d = BY_CAT.get(cat)
    if d is not None:
        v = d.get(tag)
        if v:
            return v, "dict"
    v = MERGED.get(tag)
    if v:
        return v, "dict"
    v = translate_by_rules(tag, MERGED.get)
    if v:
        return v, "rule"
    v = COMPOSER.translate(tag)
    if v:
        return v, "compose"
    return None, "none"


def main():
    if not os.path.exists(SRC):
        sys.exit("Thiếu file nguồn: " + SRC)

    stats = Counter()
    counts = Counter()
    rows_out = 0
    trans_rows = 0
    f_orig = open(OUT_ORIG, "w", newline="", encoding="utf-8")
    f_nu = open(OUT_NOUNDER, "w", newline="", encoding="utf-8")
    f_vi = open(OUT_VI, "w", newline="", encoding="utf-8")
    f_tr = open(OUT_TRANS, "w", newline="", encoding="utf-8")
    w_orig = csv.writer(f_orig, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    w_nu = csv.writer(f_nu, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    w_vi = csv.writer(f_vi, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    w_tr = csv.writer(f_tr, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")

    with open(SRC, "r", newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) < 4:
                row = row + [""] * (4 - len(row))
            tag, cat, count, alias_field = row[0], row[1], row[2], row[3]
            aliases = [a for a in alias_field.split(",") if a]

            # (a) bản gốc phục hồi
            w_orig.writerow([tag, cat, count, alias_field])

            # (b) bản bỏ dấu gạch dưới
            w_nu.writerow([spaced(tag), cat, count, ",".join(spaced_aliases(aliases))])

            # (c) bản tiếng Việt
            pc = int(count) if count.isdigit() else 0
            if cat in TRANSLATABLE:
                vi, how = translate(tag, cat)
                stats["cat_" + cat + "_" + how] += 1
                counts["cat_" + cat + "_" + how] += pc
                counts["cat_" + cat + "_total"] += pc
            else:
                vi, how = None, "proper"
                stats["proper_name"] += 1

            if vi is None:
                vi = spaced(tag)
            alias_out = []
            for a in [tag, spaced(tag)] + spaced_aliases(aliases):
                if a and a not in alias_out:
                    alias_out.append(a)
            w_vi.writerow([vi, cat, count, ",".join(alias_out)])
            # file translation chỉ giữ dòng có bản dịch thật, đúng định dạng 2 cột
            # `<English tag>,<Translation>` của sd-webui-tagcomplete
            if vi != spaced(tag):
                w_tr.writerow([tag, vi])
                trans_rows += 1
            rows_out += 1

    for f in (f_orig, f_nu, f_vi, f_tr):
        f.close()

    print("Đã ghi {} dòng vào 4 file CSV.".format(rows_out))
    print("File translation: {} dòng có bản dịch tiếng Việt thật.".format(trans_rows))
    print("\nThống kê bản dịch (phủ = % tổng post_count của category):")
    print("  {:>5} {:>8} {:>9} {:>8} {:>7} {:>9} {:>8}".format(
        "cat", "số tag", "từ điển", "quy tắc", "tổ hợp", "chưa dịch", "phủ"))
    for c in ["0", "5", "7", "12", "14", "15"]:
        d = stats["cat_%s_dict" % c]
        r = stats["cat_%s_rule" % c]
        p = stats["cat_%s_compose" % c]
        n = stats["cat_%s_none" % c]
        tot = d + r + p + n
        wt = counts["cat_%s_total" % c]
        wc = wt - counts["cat_%s_none" % c]
        pct = wc * 100.0 / wt if wt else 0
        print("  {:>5} {:>8} {:>9} {:>8} {:>7} {:>9} {:>7.2f}%".format(c, tot, d, r, p, n, pct))
    print("  tên riêng (chỉ bỏ dấu gạch dưới): {} tag".format(stats["proper_name"]))


if __name__ == "__main__":
    main()
