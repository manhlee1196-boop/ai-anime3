"""Sinh các file mà sd-webui-tagcomplete và Forge cần, từ kho prompt của repo.

Tagcomplete chỉ quét MỘT thư mục (`<extension>/tags/`) cho cả ba loại file
(tag file / translation file / extra file — xác minh từ `scripts/shared_paths.py`
và `scripts/tag_autocomplete_helper.py` của extension), nên script này chỉ việc
ghi ra đúng tên file, còn notebook sẽ chép cả ba vào thư mục đó.

Kết quả (trong `colab/assets/`):
  wai-illustrious-system-tags.csv        extra file: tag rating/quality/source...
                                         mà danh sách Danbooru không có
  danbooru_e621_vi_translation_wai.csv   translation 2 cột: bản dịch của kho
                                         + tag hệ thống, để Forge hiện nghĩa tiếng Việt
  styles.csv                             4 Style bấm được trong Forge (theo mức phân loại)

Chạy:  python3 colab/make_tagcomplete_assets.py
"""

import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
ASSETS = os.path.join(HERE, "assets")

sys.path.insert(0, HERE)

from prompt_lib.builder import PromptBuilder                           # noqa: E402
from prompt_lib.index import TagIndex                                  # noqa: E402
from prompt_lib.system_tags import SYSTEM_TAGS, SYSTEM_TAG_CATEGORIES  # noqa: E402

EXTRA_TAGS_CSV = "wai-illustrious-system-tags.csv"
TRANSLATION_CSV = "danbooru_e621_vi_translation_wai.csv"
STYLES_CSV = "styles.csv"

MAIN_TAG_CSV = os.path.join(ROOT, "danbooru_e621.csv")
MAIN_TRANSLATION_CSV = os.path.join(ROOT, "danbooru_e621_vi_translation.csv")


def read_column(path, column=0):
    if not os.path.exists(path):
        return set()
    with open(path, newline="", encoding="utf-8") as f:
        return {row[column] for row in csv.reader(f) if row and len(row) > column}


def forms(tag):
    """Tag hệ thống có thể xuất hiện ở dạng có khoảng trắng hoặc có gạch dưới."""
    out = [tag]
    alt = tag.replace(" ", "_")
    if alt != tag:
        out.append(alt)
    return out


def write_extra_tags(path, main_tags):
    """Extra file: cùng định dạng 4 cột như tag file chính.

    Chỉ ghi những tag KHÔNG có trong danh sách chính, để khỏi trùng kết quả gợi ý.
    """
    written = skipped = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        for tag, (vi, group) in sorted(SYSTEM_TAGS.items()):
            if any(form in main_tags for form in forms(tag)):
                skipped += 1
                continue
            writer.writerow([tag, SYSTEM_TAG_CATEGORIES.get(group, 5), 0, ""])
            written += 1
    return written, skipped


def write_translation(path, main_tags, translated):
    """Translation 2 cột = bản dịch của repo + nghĩa tiếng Việt của tag hệ thống.

    Khoá phải khớp đúng dạng tag xuất hiện trong tag file, và không được trùng với
    khoá đã có sẵn (nếu trùng, tagcomplete sẽ lấy dòng cuối nên dễ sinh nghĩa sai).
    """
    copied = added = 0
    with open(path, "w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out, lineterminator="\n")
        if os.path.exists(MAIN_TRANSLATION_CSV):
            with open(MAIN_TRANSLATION_CSV, newline="", encoding="utf-8") as src:
                for row in csv.reader(src):
                    if len(row) >= 2 and row[1].strip():
                        writer.writerow([row[0], row[1]])
                        copied += 1
        for tag, (vi, _group) in sorted(SYSTEM_TAGS.items()):
            underscored = tag.replace(" ", "_")
            in_main = underscored in main_tags or tag in main_tags
            # nếu tag nằm trong danh sách chính thì dùng đúng dạng của danh sách chính
            if in_main:
                # dùng đúng dạng đang có trong tag file chính
                keys = [f for f in forms(tag) if f in main_tags] or [underscored]
            else:
                # tag chỉ nằm trong extra file: ghi cả hai dạng cho chắc
                keys = forms(tag)
            for key in dict.fromkeys(keys):
                if key in translated:
                    continue
                writer.writerow([key, vi])
                translated.add(key)
                added += 1
    return copied, added


def main():
    os.makedirs(ASSETS, exist_ok=True)
    if not os.path.exists(MAIN_TAG_CSV):
        raise SystemExit(f"Thiếu {MAIN_TAG_CSV} — chạy từ thư mục gốc repo.")
    if not os.path.exists(MAIN_TRANSLATION_CSV):
        # KHÔNG được im lặng: nếu thiếu, file translation sinh ra chỉ còn vài chục
        # dòng tag hệ thống và tính năng tìm bằng tiếng Việt sẽ chết mà không báo lỗi.
        raise SystemExit(
            f"Thiếu {MAIN_TRANSLATION_CSV}.\n"
            "Hãy build kho prompt trước:  python3 tools/build_vi.py")
    index = TagIndex(ROOT)
    builder = PromptBuilder(index)
    main_tags = read_column(MAIN_TAG_CSV, 0)
    translated = read_column(MAIN_TRANSLATION_CSV, 0)

    n_extra, n_skip = write_extra_tags(os.path.join(ASSETS, EXTRA_TAGS_CSV), main_tags)
    n_copy, n_add = write_translation(os.path.join(ASSETS, TRANSLATION_CSV),
                                      main_tags, set(translated))
    styles = builder.styles_csv()
    with open(os.path.join(ASSETS, STYLES_CSV), "w", encoding="utf-8") as f:
        f.write(styles)

    # tự kiểm tra: không được trùng khoá trong translation
    keys = read_column(os.path.join(ASSETS, TRANSLATION_CSV), 0)
    with open(os.path.join(ASSETS, TRANSLATION_CSV), newline="", encoding="utf-8") as f:
        total = sum(1 for row in csv.reader(f) if row)
    assert total == len(keys), f"trùng khoá translation: {total} dòng nhưng chỉ {len(keys)} khoá"

    print(f"Đã ghi vào {ASSETS}:")
    print(f"  {EXTRA_TAGS_CSV:<38} {n_extra:>6} tag hệ thống mới "
          f"(bỏ qua {n_skip} tag đã có trong kho)")
    print(f"  {TRANSLATION_CSV:<38} {n_copy:>6} dòng từ kho + {n_add} dòng tag hệ thống "
          f"= {total} dòng, không trùng khoá")
    print(f"  {STYLES_CSV:<38} {len(styles.splitlines()) - 1:>6} style cho Forge")
    print("\nChép 3 file này vào <forge>/extensions/a1111-sd-webui-tagcomplete/tags/")
    print("(styles.csv thì chép vào thư mục gốc của Forge).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
