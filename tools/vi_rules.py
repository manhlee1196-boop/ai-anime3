# -*- coding: utf-8 -*-
"""Bộ quy tắc dịch tag theo mẫu (pattern rules).

`translate_by_rules(tag, lookup)` trả về bản dịch tiếng Việt nếu tag khớp một
mẫu có thể suy diễn an toàn, ngược lại trả về None.

Nguyên tắc an toàn: chỉ ghép bản dịch khi MỌI thành phần của tag đều tra được
trong bảng hình vị / từ điển. Tag không nhận diện được sẽ giữ nguyên tiếng Anh
(và chỉ thay `_` bằng khoảng trắng) ở tầng build.
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "dict"))

from vi_morphemes import (  # noqa: E402
    COLORS,
    LANGUAGES,
    LORE_SUFFIX,
    LORE_WORD,
    NUMBERS,
    SITES,
    SIZES,
)

RE_CENTURY = re.compile(r"^(\d{1,2})(?:st|nd|rd|th)_century$")
RE_YEAR = re.compile(r"^(1[0-9]{3}|20[0-9]{2}|21[0-9]{2})$")
RE_RATIO = re.compile(r"^(\d{1,4}):(\d{1,4})$")
RE_BAD_LINK = re.compile(r"^bad_(.+)_(link|id)$")
RE_SITE_SAMPLE = re.compile(r"^(.+)_sample$")
RE_LORE = re.compile(r"^(.+)/?\(lore\)$")
RE_PAREN = re.compile(r"^(.+)_\((.+)\)$")
RE_COMMENTARY = re.compile(r"^(.+)_commentary$")
RE_TEXT = re.compile(r"^(.+)_text$")
RE_AUDIO = re.compile(r"^(.+)_audio$")
RE_DESC = re.compile(r"^(.+)_description$")
RE_REQUEST = re.compile(r"^(.+)_request$")
RE_CHECK = re.compile(r"^check_(.+)$")
RE_HAS_REV = re.compile(r"^has_(.+)_revision$")
RE_NO = re.compile(r"^no_(.+)$")
RE_MONO = re.compile(r"^(.+)_monochrome$")
RE_AND_COLORS = re.compile(r"^([a-z\-]+)_and_([a-z\-]+)$")
RE_VERSION_AT = re.compile(r"^(.*)_version_at_(source|paywall)$")

RE_SLASH = re.compile(r"^([a-z0-9\-]+(?:_[a-z0-9\-]+)*)/([a-z0-9\-]+(?:_[a-z0-9\-]+)*)$")
RE_ON = re.compile(r"^(.+)_on_(.+)$")
RE_PEN = re.compile(r"^(.+)_penetrating_(.+)$")
RE_HUMANOID = re.compile(r"^(.+)_humanoid$")
RE_HUMANOID2 = re.compile(r"^humanoid_(.+)$")
RE_AND = re.compile(r"^(.+)_and_(.+)$")
RE_OF = re.compile(r"^(.+)_of_(.+)$")


def _two_parts(rule, joiner_fmt, lookup):
    m = rule
    if not m:
        return None
    a = lookup(m.group(1))
    b = lookup(m.group(2))
    if a and b:
        return joiner_fmt.format(a, b)
    return None



_COLORS_BY_LEN = sorted(COLORS, key=len, reverse=True)
_SIZES_BY_LEN = sorted(SIZES, key=len, reverse=True)
_NUMBERS_BY_LEN = sorted(NUMBERS, key=len, reverse=True)
_LORE_BY_LEN = sorted(LORE_WORD, key=len, reverse=True)

ARTWORK_SUFFIX = {
    "artwork": "tác phẩm làm bằng {}",
    "medium": "chất liệu {}",
}


def _title(name):
    """Viết hoa tử tế tên phần mềm/trang web: `paint_tool_sai` -> `Paint Tool SAI`."""
    known = {
        "sai": "SAI", "gimp": "GIMP", "ibispaint": "ibisPaint",
        "photoshop": "Photoshop", "krita": "Krita", "procreate": "Procreate",
        "zbrush": "ZBrush", "blender": "Blender", "maya": "Maya",
        "unity": "Unity", "aseprite": "Aseprite", "piskel": "Piskel",
        "inkscape": "Inkscape", "paint": "Paint", "flash": "Flash",
        "live2d": "Live2D", "cubism": "Cubism", "miku": "Miku",
        "mikumikudance": "MikuMikuDance", "mmd": "MMD",
    }
    parts = re.split(r"[_\- ]+", name)
    out = []
    for p in parts:
        out.append(known.get(p.lower(), p.capitalize()))
    return " ".join(out)


def translate_lore(base):
    """Dịch phần lõi của tag `X_(lore)`: hỗ trợ `A_and_B`."""
    base = base.strip().rstrip("_")
    if base in LORE_WORD:
        return LORE_WORD[base]
    # thử tách theo `_and_`
    if "_and_" in base:
        left, _, right = base.partition("_and_")
        if left in LORE_WORD and right in LORE_WORD:
            return "{} và {}".format(LORE_WORD[left], LORE_WORD[right])
    # thử khớp dài nhất rồi khớp phần còn lại
    for k in _LORE_BY_LEN:
        if base.startswith(k + "_") or base.endswith("_" + k):
            rest = base[len(k) + 1:] if base.startswith(k + "_") else base[: -(len(k) + 1)]
            sub = translate_lore(rest)
            if sub:
                head = LORE_WORD[k]
                return "{} {}".format(head, sub) if base.endswith("_" + k) else "{} {}".format(sub, head)
    return None


def translate_by_rules(tag, lookup):
    """Trả về bản dịch tiếng Việt của `tag` theo mẫu, hoặc None."""

    # ---- cat 15 Lore -------------------------------------------------------
    m = RE_LORE.match(tag)
    if m:
        v = translate_lore(m.group(1))
        if v:
            return v + LORE_SUFFIX

    # ---- tỉ lệ khung hình, năm, thế kỷ -------------------------------------
    m = RE_RATIO.match(tag)
    if m:
        return "tỉ lệ khung hình {}:{}".format(m.group(1), m.group(2))
    m = RE_CENTURY.match(tag)
    if m:
        return "thế kỷ " + m.group(1)
    if RE_YEAR.match(tag):
        return "năm " + tag

    # ---- phần mềm / chất liệu: `X_(artwork)`, `X_(medium)` -----------------
    m = RE_PAREN.match(tag)
    if m and m.group(2) in ARTWORK_SUFFIX:
        inner = lookup(m.group(1))
        name = inner if inner else _title(m.group(1))
        return ARTWORK_SUFFIX[m.group(2)].format(name)

    # ---- liên kết hỏng ------------------------------------------------------
    m = RE_BAD_LINK.match(tag)
    if m:
        site = m.group(1)
        name = SITES.get(site) or SITES.get(site.replace("_", "-"))
        if not name:
            name = _title(site)
        if m.group(2) == "id":
            return "mã {} hỏng".format(name)
        return "liên kết {} hỏng".format(name)

    # ---- bản mẫu từ trang ---------------------------------------------------
    m = RE_SITE_SAMPLE.match(tag)
    if m:
        site = m.group(1)
        name = SITES.get(site) or SITES.get(site.replace("_", "-"))
        if name:
            return "bản mẫu từ " + name

    # ---- chú thích / chữ / âm thanh / mô tả theo ngôn ngữ -------------------
    m = RE_COMMENTARY.match(tag)
    if m and m.group(1) in LANGUAGES:
        return "chú thích " + LANGUAGES[m.group(1)]
    m = RE_TEXT.match(tag)
    if m and m.group(1) in LANGUAGES:
        return "chữ " + LANGUAGES[m.group(1)]
    m = RE_AUDIO.match(tag)
    if m and m.group(1) in LANGUAGES:
        return "âm thanh " + LANGUAGES[m.group(1)]
    m = RE_DESC.match(tag)
    if m and m.group(1) in LANGUAGES:
        return "mô tả " + LANGUAGES[m.group(1)]

    # ---- phiên bản ở nguồn / sau tường trả phí ------------------------------
    m = RE_VERSION_AT.match(tag)
    if m:
        head = lookup(m.group(1)) or lookup(m.group(1) + "_version")
        where = "ở nguồn" if m.group(2) == "source" else "sau tường trả phí"
        if head:
            return "{} {}".format(head, where)

    # ---- bản chỉnh sửa: `has_X_revision` ------------------------------------
    m = RE_HAS_REV.match(tag)
    if m:
        v = lookup(m.group(1)) or lookup(tag)
        if v:
            return "có bản chỉnh sửa " + v

    # ---- yêu cầu bổ sung: `X_request` ---------------------------------------
    m = RE_REQUEST.match(tag)
    if m:
        v = lookup(m.group(1))
        if v:
            return "yêu cầu bổ sung " + v
        if m.group(1) in LANGUAGES:
            return "yêu cầu " + LANGUAGES[m.group(1)]

    # ---- kiểm tra: `check_X` -------------------------------------------------
    m = RE_CHECK.match(tag)
    if m:
        v = lookup(m.group(1))
        if v:
            return "cần kiểm tra " + v

    # ---- không có: `no_X` ----------------------------------------------------
    m = RE_NO.match(tag)
    if m:
        v = lookup(m.group(1))
        if v:
            return "không có " + v
        if m.group(1) in SIZES:
            return "không có " + SIZES[m.group(1)]

    # ---- đơn sắc: `X_monochrome` ---------------------------------------------
    m = RE_MONO.match(tag)
    if m and m.group(1) in COLORS:
        return "đơn sắc màu " + COLORS[m.group(1)]

    # ---- cặp màu: `red_and_white` --------------------------------------------
    m = RE_AND_COLORS.match(tag)
    if m and m.group(1) in COLORS and m.group(2) in COLORS:
        return "{} và {}".format(COLORS[m.group(1)], COLORS[m.group(2)])

    # ---- cặp giới tính / loài: `male/female`, `gynomorph/male` ----------------
    m = RE_SLASH.match(tag)
    if m:
        a = lookup(m.group(1))
        b = lookup(m.group(2))
        if a and b:
            return a + "/" + b

    # ---- `X_and_Y` -----------------------------------------------------------
    v = _two_parts(RE_AND.match(tag), "{} và {}", lookup)
    if v:
        return v

    # ---- `A_on_B`, `A_penetrating_B` ----------------------------------------
    v = _two_parts(RE_ON.match(tag), "{} trên {}", lookup)
    if v:
        return v
    v = _two_parts(RE_PEN.match(tag), "{} xâm nhập {}", lookup)
    if v:
        return v

    # ---- `X_humanoid` (species e621) ----------------------------------------
    m = RE_HUMANOID.match(tag)
    if m:
        v = lookup(m.group(1))
        if v:
            return "{} hình người".format(v)
    m = RE_HUMANOID2.match(tag)
    if m:
        v = lookup(m.group(1))
        if v:
            return "hình người {}".format(v)

    # ---- màu + danh từ: `red_eyes` -------------------------------------------
    for color in _COLORS_BY_LEN:
        if tag.startswith(color + "_"):
            rest = tag[len(color) + 1:]
            v = lookup(rest)
            if v:
                return "{} màu {}".format(v, COLORS[color])
        if tag.endswith("_" + color):
            head = tag[: -(len(color) + 1)]
            v = lookup(head)
            if v:
                return "{} màu {}".format(v, COLORS[color])

    # ---- số đếm + danh từ: `two_boys` ----------------------------------------
    for num in _NUMBERS_BY_LEN:
        if tag.startswith(num + "_"):
            v = lookup(tag[len(num) + 1:])
            if v:
                return "{} {}".format(NUMBERS[num], v)

    # ---- tính từ + danh từ: `long_hair`, `huge_breasts` ----------------------
    for size in _SIZES_BY_LEN:
        if tag.startswith(size + "_"):
            v = lookup(tag[len(size) + 1:])
            if v:
                # tiếng Việt đặt tính từ sau danh từ
                return "{} {}".format(v, SIZES[size])

    return None
