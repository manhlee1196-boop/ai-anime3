#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lọc các tag **phong cách vẽ** ra khỏi kho tag Danbooru + e621.

Đầu vào : danbooru_e621.csv                 (tag, category, post_count, aliases)
          danbooru_e621_vi_translation.csv  (tag, nghĩa tiếng Việt)
Đầu ra  : style_tags.csv                    (tag, vi, category, post_count, nhom, nguon_vi)

Tag phong cách vẽ ở đây gồm 7 nhóm:
  chat_lieu      chất liệu truyền thống (màu nước, sơn dầu, chì, than, mực...)
  so_hoa         chất liệu số & CG (photoshop, clip studio, blender, pixel art...)
  ky_thuat       kỹ thuật hoàn thiện (cel shading, line art, hatching, palette...)
  anh_sang       ánh sáng (backlighting, rim lighting, dramatic lighting...)
  truong_phai    trường phái / mỹ thuật (ukiyo-e, art nouveau, ấn tượng, lập thể...)
  the_loai       phong cách thể loại (anime, manga, toon, chibi, realistic...)
  thoi_ky        thời kỳ & thiết kế (1970s-2000s, retro, y2k, vaporwave...)
  tac_gia        phong cách tác giả / series, đuôi `_(style)` (zun, araki hirohiko...)

Chạy:
    python3 tools/find_style_tags.py             # ghi style_tags.csv + in tóm tắt
    python3 tools/find_style_tags.py --markdown  # in bảng Markdown để dán vào tài liệu
    python3 tools/find_style_tags.py --check     # chỉ kiểm tag có thật trong CSV (CI)
"""

import argparse
import csv
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)

TAGS_CSV = os.path.join(ROOT, "danbooru_e621.csv")
VI_CSV = os.path.join(ROOT, "danbooru_e621_vi_translation.csv")
OUT_CSV = os.path.join(ROOT, "style_tags.csv")

STYLE_SUFFIX = "_(style)"

# Category tên riêng (artist / copyright / character / contributor) — không phải tag nội
# dung, không bao giờ được dịch, nên không đưa vào danh sách phong cách.
NAME_CATEGORIES = {1, 3, 4, 8, 9, 10, 11}

# --------------------------------------------------------------------- danh mục
# Thứ tự trong list = thứ tự xuất ra file/tài liệu.
GROUPS = [
    ("chat_lieu", "Chất liệu truyền thống", [
        # màu nước & sơn
        "watercolor_(medium)", "watercolor_(artwork)", "traditional_watercolor_(artwork)",
        "watercolor_pencil_(medium)", "oil_painting_(medium)", "oil_painting_(artwork)",
        "acrylic_paint_(medium)", "acrylic_painting_(artwork)", "acrylic_gouache_(medium)",
        "gouache_(medium)", "gouache_(artwork)", "painting_(medium)", "painting_(artwork)",
        "traditional_painting_(artwork)", "traditional_media_(artwork)", "simulated_traditional_(artwork)",
        # bút chì, than, phấn, sáp
        "colored_pencil_(medium)", "colored_pencil_(artwork)", "graphite_(medium)", "graphite_(artwork)",
        "charcoal_(medium)", "charcoal_(artwork)", "pastel_(medium)", "pastel_(artwork)",
        "digital_pastel_(artwork)", "crayon_(medium)", "crayon_(artwork)",
        "chalk_(medium)", "chalk_(artwork)",
        # mực & bút
        "pen_(medium)", "pen_(artwork)", "ballpoint_pen_(medium)", "nib_pen_(medium)",
        "millipen_(medium)", "fudepen_(medium)", "marker_(medium)", "marker_(artwork)",
        "brush_(medium)", "calligraphy_brush_(medium)", "color_ink_(medium)",
        "ink", "ink_(artwork)", "airbrush_(medium)", "spray_paint",
        # in ấn
        "woodcut_(artwork)", "engraving_(medium)", "engraving_(artwork)",
        "etching_(artwork)", "lithograph_(artwork)",
        # giấy & vải & thủ công
        "papercraft_(medium)", "paper_cutout_(medium)", "papercutting_(artwork)",
        "origami", "kirigami", "collage_(medium)", "collage_(artwork)",
        "embroidery_(medium)", "embroidery", "tapestry", "stained_glass", "mosaic",
        "sculpture", "sculpture_(artwork)", "clay_(medium)", "clay_(artwork)",
        "felt_(medium)", "amigurumi_(medium)", "lego",
    ]),
    ("so_hoa", "Chất liệu số & CG", [
        # phần mềm vẽ
        "digital_media_(artwork)", "digital_drawing_(artwork)", "digital_painting_(artwork)",
        "photoshop_(medium)", "adobe_photoshop_(artwork)",
        "clip_studio_paint_(medium)", "clip_studio_paint_(artwork)",
        "paint_tool_sai_(artwork)", "painttool_sai_(medium)",
        "procreate_(medium)", "procreate_(artwork)", "krita_(medium)", "krita_(artwork)",
        "ibispaint_(medium)", "ibispaint_(artwork)",
        "medibang_paint_(medium)", "medibang_paint_(artwork)",
        "firealpaca_(medium)", "firealpaca_(artwork)",
        "paint.net_(medium)", "paint.net_(artwork)",
        "microsoft_paint_(artwork)", "microsoft_paint_(medium)",
        "gimp_(medium)", "gimp_(artwork)", "inkscape_(artwork)",
        "adobe_illustrator_(medium)", "adobe_illustrator_(artwork)",
        "aseprite_(medium)", "aseprite_(artwork)", "piskel_(artwork)", "dotpict_(medium)",
        "paintstorm_(artwork)", "rebelle_(artwork)", "artrage_(artwork)",
        "corel_painter_(artwork)", "art_academy_(medium)", "art_academy_(artwork)",
        "sketchbook_(artwork)", "autodesk_sketchbook_(medium)", "opencanvas_(medium)",
        "tvpaint_(artwork)", "toon_boom_harmony_(artwork)", "moho_(artwork)",
        "flipaclip_(artwork)", "flipnote_studio_(medium)", "flipnote_studio_(artwork)",
        "wigglypaint_(artwork)", "drawpile_(artwork)",
        # 3D / render / game engine
        "3d_(artwork)", "blender_(artwork)", "blender_(medium)",
        "blender_cycles_(artwork)", "blender_eevee_(artwork)",
        "zbrush_(medium)", "zbrush_(artwork)", "autodesk_3ds_max_(artwork)",
        "autodesk_maya_(artwork)", "cinema_4d_(artwork)", "unity_(artwork)",
        "unreal_engine_(artwork)", "marmoset_toolbag_(artwork)",
        "substance_painter_(artwork)", "daz_studio_(artwork)", "koikatsu_(medium)",
        "mikumikudance_(medium)", "source_filmmaker_(artwork)",
        "live2d_cubism_(artwork)", "spine_(medium)", "blockbench_(medium)",
        # đồ hoạ vector / pixel
        "pixel_art", "pixel_(artwork)", "pixel_animation", "aseprite_(medium)",
        "ascii_art", "voxel_art", "low_poly", "vector_art", "vector_trace",
    ]),
    ("ky_thuat", "Kỹ thuật hoàn thiện", [
        # đổ bóng / rendering
        "cel_shading", "cel_rendering", "soft_shading", "simple_shading", "flat_shading",
        "no_shading", "realistic_shading", "detailed_shading", "complex_shading",
        "stylized_shading", "minimal_shading", "halftone_shading",
        "flat_colors", "flat_color", "anime_coloring",
        "shaded", "colored", "partially_colored", "spot_color", "highlights_(coloring)",
        # nét
        "line_art", "lineart", "no_lineart", "thick_lineart", "colored_line_art",
        "outline", "thick_outlines", "white_outline", "black_outline", "colored_outline",
        "sketch", "sketchy", "colored_sketch",
        # chất liệu bề mặt
        "painterly", "impasto", "chiaroscuro",
        "hatching", "crosshatching", "cross-hatching", "linear_hatching",
        "stippling", "dithering", "halftone", "screentone", "screentones",
        "hatching_(texture)", "hatching_(art)",
        # bảng màu
        "limited_palette", "restricted_palette", "neon_palette",
        "pastel_colors", "high_contrast", "gradient",
        "monochrome", "multiple_monochrome", "greyscale",
        "greyscale_with_colored_background", "sepia",
    ]),
    ("anh_sang", "Ánh sáng", [
        "lighting", "backlighting", "sidelighting", "underlighting", "rim_lighting",
        "dramatic_lighting", "realistic_lighting", "soft_lighting", "mood_lighting",
        "dappled_sunlight",
    ]),
    ("truong_phai", "Trường phái & mỹ thuật", [
        "art_nouveau", "art_deco", "ukiyo-e", "sumi-e", "nihonga", "ink_wash_painting",
        "dunhuang_style", "greek_painting_style",
        "renaissance", "impressionism", "pointillism", "cubism", "expressionism",
        "surrealism", "surreal", "pop_art", "minimalism", "abstract", "abstract_art",
        "stained_glass", "mosaic", "memphis_design", "psychedelic",
    ]),
    ("the_loai", "Phong cách thể loại", [
        "anime_style", "retro_anime_style", "manga_style", "western_comics_(style)",
        "toon_(style)", "toony", "fleischer_style_toon", "rubber_hose_style",
        "moe", "chibi", "deformed",
        "realistic", "semi-realistic", "photorealistic",
        "photo_(medium)", "photography_(artwork)",
        "official_style", "style_parody", "style_emulation",
        "alternate_art_style", "different_artstyle",
        "concept_art", "novel_illustration", "cover_art", "technical_illustration",
        "pinup_(style)", "indian_style",
    ]),
    ("thoi_ky", "Thời kỳ & thiết kế", [
        "1960s_(style)", "1970s_(style)", "1980s_(style)", "1990s_(style)", "2000s_(style)",
        "retro_artstyle", "faux_retro_artstyle",
        "y2k_(graphic_design)", "vaporwave", "synthwave",
        "graffiti", "memphis_design",
    ]),
    ("nguon_dinh_dang", "Nguồn & định dạng (dùng kèm)", [
        # không phải phong cách vẽ, nhưng hay đi kèm để ra đúng "chất" hình
        "official_art", "comic", "4koma", "yonkoma",
    ]),
    # Ghi chú: `colorful_palette` (cat 1), `outrun` và `webtoon` (cat 10) trùng tên với
# tag phong cách nhưng thực chất là tag **tên nghệ sĩ / tên series**, nên không đưa vào.
# nhóm tac_gia được thu tự động theo đuôi _(style)
    ("tac_gia", "Phong cách tác giả / series", []),
]

# Nghĩa tiếng Việt gợi ý cho tag phong cách chưa có trong
# danbooru_e621_vi_translation.csv (cột nguon_vi = "goi_y").
VI_GOI_Y = {
    "kirigami": "cắt giấy nghệ thuật (kirigami)",
    "tapestry": "thảm dệt treo tường",
    "low_poly": "đa giác thấp (low-poly)",
    "voxel_art": "nghệ thuật khối voxel",
    "complex_shading": "đổ bóng phức tạp",
    "minimal_shading": "đổ bóng tối giản",
    "painterly": "nét vẽ kiểu hội hoạ",
    "impasto": "kỹ thuật sơn dày (impasto)",
    "chiaroscuro": "tương phản sáng tối mạnh (chiaroscuro)",
    "linear_hatching": "đánh bóng bằng nét thẳng song song",
    "colorful_palette": "bảng màu rực rỡ",
    "sidelighting": "ánh sáng chiếu ngang",
    "underlighting": "ánh sáng chiếu từ dưới",
    "rim_lighting": "ánh sáng viền",
    "dramatic_lighting": "ánh sáng kịch tính",
    "mood_lighting": "ánh sáng theo tâm trạng",
    "fleischer_style_toon": "hoạt hình kiểu Fleischer (thập niên 1930)",
    "moe": "phong cách moe",
    "semi-realistic": "bán thực tế",
    "yonkoma": "truyện 4 khung (yonkoma)",
    "webtoon": "truyện tranh mạng (webtoon)",
    "style_emulation": "mô phỏng phong cách",
    "greek_painting_style": "phong cách tranh Hy Lạp cổ",
    "dunhuang_style": "phong cách tranh Đôn Hoàng",
    "faux_retro_artstyle": "phong cách vẽ cổ điển giả",
    "y2k_(graphic_design)": "thiết kế đồ hoạ Y2K",
    "vaporwave": "phong cách vaporwave",
    "synthwave": "phong cách synthwave",
    "outrun": "phong cách outrun",
    "psychedelic": "phong cách ảo giác",
    "memphis_design": "thiết kế Memphis",
    "art_deco": "trường phái Art Deco",
    "art_nouveau": "trường phái Art Nouveau",
    "nihonga": "tranh Nhật hiện đại (nihonga)",
    "impressionism": "trường phái Ấn tượng",
    "pointillism": "trường phái Điểm sắc",
    "cubism": "trường phái Lập thể",
    "expressionism": "trường phái Biểu hiện",
    "surrealism": "trường phái Siêu thực",
    "minimalism": "trường phái Tối giản",
    "abstract": "trừu tượng",
}


def vn(n):
    """Số kiểu Việt Nam: 1.359.875."""
    return f"{n:,}".replace(",", ".")


# ------------------------------------------------------------------- đọc dữ liệu
def load_tags(path=TAGS_CSV):
    """tag -> (category, post_count) từ danbooru_e621.csv."""
    tags = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.reader(f):
            if len(row) < 3:
                continue
            try:
                tags[row[0]] = (int(row[1]), int(row[2]))
            except ValueError:
                continue
    return tags


def load_vi(path=VI_CSV):
    """tag -> nghĩa tiếng Việt từ danbooru_e621_vi_translation.csv."""
    vi = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.reader(f):
            if len(row) == 2 and row[0] not in vi:
                vi[row[0]] = row[1]
    return vi


# --------------------------------------------------------------------- lọc tag
def author_style_tags(tags):
    """Mọi tag có đuôi `_(style)` — phong cách của một tác giả hoặc một series."""
    return {t for t in tags if t.endswith(STYLE_SUFFIX)}


def collect(tags):
    """Trả về list (group_id, group_label, [tag, ...]) đã sắp theo post_count."""
    out, seen = [], set()
    for gid, label, listed in GROUPS:
        names = set(listed)
        if gid == "tac_gia":
            names |= author_style_tags(tags)
        # bỏ tag không có trong kho, bỏ trùng giữa các nhóm (nhóm trước thắng)
        names = {t for t in names
                 if t in tags and t not in seen and tags[t][0] not in NAME_CATEGORIES}
        seen |= names
        out.append((gid, label, sorted(names, key=lambda t: (-tags[t][1], t))))
    return out


def rows_for(groups, tags, vi):
    """Sinh các dòng CSV: tag, vi, category, post_count, nhom, nguon_vi."""
    rows = []
    for _gid, label, names in groups:
        for tag in names:
            if tag in vi:
                meaning, source = vi[tag], "csv"
            elif tag in VI_GOI_Y:
                meaning, source = VI_GOI_Y[tag], "goi_y"
            else:
                meaning, source = "", ""
            category, count = tags[tag]
            rows.append([tag, meaning, str(category), str(count), label, source])
    return rows


def write_csv(rows, path=OUT_CSV):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["tag", "vi", "category", "post_count", "nhom", "nguon_vi"])
        writer.writerows(rows)


# ------------------------------------------------------------------------- CLI
def print_summary(groups, tags, vi):
    total = sum(len(n) for _g, _l, n in groups)
    missing = [t for _g, _l, names in groups for t in names if t not in vi]
    print(f"Kho tag            : {vn(len(tags))} tag")
    print(f"Tag phong cách vẽ  : {vn(total)} tag / {len(groups)} nhóm")
    print(f"  có bản dịch VI   : {vn(total - len(missing))}")
    print(f"  chưa dịch (gợi ý): {vn(len(missing))}")
    for gid, label, names in groups:
        top = ", ".join(f"{t} ({vn(tags[t][1])})" for t in names[:4])
        print(f"  {label:<28} {len(names):>4} tag   vd: {top}")
    if missing:
        print("\nChưa có trong danh sách dịch (đã điền gợi ý trong CSV):")
        print("  " + ", ".join(missing))


def print_markdown(groups, tags, vi, per_group=None):
    for gid, label, names in groups:
        print(f"\n### {label} ({len(names)} tag)\n")
        print("| Tag | Nghĩa | Bài đăng |")
        print("|---|---|---:|")
        for tag in names[:per_group] if per_group else names:
            meaning = vi.get(tag) or VI_GOI_Y.get(tag) or ""
            mark = "" if tag in vi else " *"
            print(f"| `{tag}` | {meaning}{mark} | {vn(tags[tag][1])} |")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Lọc tag phong cách vẽ từ kho Danbooru + e621")
    parser.add_argument("--markdown", action="store_true", help="in bảng Markdown thay vì ghi file")
    parser.add_argument("--per-group", type=int, default=0, help="giới hạn số tag mỗi nhóm khi in")
    parser.add_argument("--check", action="store_true", help="chỉ kiểm tra, không ghi file")
    parser.add_argument("--output", default=OUT_CSV, help="đường dẫn CSV đầu ra")
    args = parser.parse_args(argv)

    tags, vi = load_tags(), load_vi()
    groups = collect(tags)

    unknown = [t for _g, _l, _n in GROUPS for t in _n if t not in tags]
    if unknown:
        print(f"LỖI: {len(unknown)} tag không có trong danbooru_e621.csv: {', '.join(unknown)}")
        return 1

    if args.markdown:
        print_markdown(groups, tags, vi, args.per_group or None)
        return 0

    if args.check:
        print_summary(groups, tags, vi)
        return 0

    write_csv(rows_for(groups, tags, vi), args.output)
    print_summary(groups, tags, vi)
    print(f"\nĐã ghi {os.path.relpath(args.output, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
