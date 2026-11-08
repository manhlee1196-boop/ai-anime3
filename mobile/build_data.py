#!/usr/bin/env python3
"""Sinh dữ liệu gọn cho app điện thoại từ chính các CSV của repo.

App điện thoại (PWA/APK) không đọc được 350.000 dòng CSV 9 MB trên máy yếu, nên
file này nén lại thành **một** `tags.json` (kèm `tags.json.gz`) đủ để tra tag
tiếng Việt <-> tiếng Anh, xếp nhóm prompt và chọn tham số mặc định.

Nội dung sinh ra (tất cả đều suy từ nguồn thật trong repo, không chép tay):

* `tags`        — `[tag, post_count, category, group_index, vi|0]`, sắp theo độ phổ
  biến giảm dần. Lấy mọi tag có `post_count >= --min-count` **hoặc** có bản dịch
  tiếng Việt (để gõ tiếng Việt cho tag hiếm vẫn ra).
* `groups`      — thứ tự nhóm chuẩn Illustrious/WAI (`prompt_lib/groups.py`).
* `presets`     — chất lượng / negative / phân loại / kích thước / tham số WAI
  (`prompt_lib/system_tags.py`), cùng 12 công thức phong cách (`styles.py`).
* `styles`      — 506 tag phong cách vẽ trong `style_tags.csv`.
* `quick`       — vài tag phổ biến nhất của mỗi nhóm để làm chip gợi ý.

Dùng:

    python3 mobile/build_data.py                 # ghi mobile/app/data/tags.json(.gz)
    python3 mobile/build_data.py --min-count 500 # ít tag hơn, file nhẹ hơn
    python3 mobile/build_data.py --check         # kiểm file đã sinh có khớp không
"""

import argparse
import csv
import gzip
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "colab"))

from prompt_lib import system_tags as ST  # noqa: E402
from prompt_lib.groups import BROWSE_GROUPS, GROUP_LABELS, GROUP_ORDER, classify  # noqa: E402
from prompt_lib.index import CATEGORY_NAMES  # noqa: E402
from prompt_lib.styles import PRESETS as STYLE_PRESETS  # noqa: E402

TAGS_CSV = "danbooru_e621.csv"
VI_CSV = "danbooru_e621_vi_translation.csv"
STYLE_CSV = "style_tags.csv"
OUT_DIR = ROOT / "mobile" / "app" / "data"
OUT_JSON = OUT_DIR / "tags.json"
OUT_GZ = OUT_DIR / "tags.json.gz"

DEFAULT_MIN_COUNT = 200          # đủ phủ tag phổ biến, giữ file ~4 MB / ~1,4 MB gz
QUICK_PER_GROUP = 10
SIZE_PRESETS_ORDER = list(ST.SIZE_PRESETS.items())


def read_csv(name):
    """Đọc CSV ở thư mục gốc repo; báo lỗi rõ nếu thiếu."""
    path = ROOT / name
    if not path.is_file():
        raise SystemExit(f"❌ Thiếu {path}. Chạy lệnh này ở trong repo ai-anime3.")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.reader(handle))


def load_translations():
    """`tag tiếng Anh -> nghĩa tiếng Việt` (45.557 dòng của bản dịch thật)."""
    out = {}
    for row in read_csv(VI_CSV):
        if len(row) >= 2 and row[0].strip() and row[1].strip():
            out[row[0].strip()] = row[1].strip()
    return out


def load_tags():
    """`[(tag, category, post_count)]` từ file tag gốc."""
    out = []
    for row in read_csv(TAGS_CSV):
        if len(row) < 3 or not row[0].strip():
            continue
        try:
            category, post_count = int(row[1]), int(row[2])
        except ValueError:
            continue
        out.append((row[0].strip(), category, post_count))
    return out


def load_styles():
    """506 tag phong cách vẽ: `[tag, vi, nhóm]`, sắp theo độ phổ biến."""
    rows = read_csv(STYLE_CSV)
    out = []
    for row in rows[1:]:
        if len(row) < 5:
            continue
        try:
            count = int(row[3])
        except ValueError:
            count = 0
        out.append((count, [row[0].strip(), row[1].strip(), row[4].strip()]))
    out.sort(key=lambda item: (-item[0], item[1][0]))
    return [item[1] for item in out]


def git_ref():
    """Chọn `ref` đưa vào link Colab — phải tồn tại trên GitHub và không chứa dấu '/'.

    Colab tải notebook qua `github.com/<repo>/blob/<ref>/<path>`; nhánh có dấu '/'
    (arena/..., feature/...) bị mã hoá %2F và Colab thường không mở được. Thứ tự ưu
    tiên: WAI_COLAB_REF (đặt tay) → tag của CI (GITHUB_REF_NAME khi build từ tag)
    → WAI_COLAB_BRANCH → nhánh hiện tại nếu không có '/' → commit SHA.
    """
    for env in ("WAI_COLAB_REF", "GITHUB_REF_NAME", "WAI_COLAB_BRANCH"):
        value = (os.environ.get(env) or "").strip()
        if value and "/" not in value:
            return value, "tag" if env == "GITHUB_REF_NAME" else "ref"
    try:
        branch = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        branch = ""
    if branch and branch != "HEAD" and "/" not in branch:
        return branch, "branch"
    try:
        sha = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--short=12", "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        sha = ""
    # không có git (bản zip): 'main' là mặc định của GitHub — có thể 404 notebook,
    # nên dùng luôn tag của bản phát hành gần nhất nếu biết.
    return (sha or "main"), "commit"


def colab_info():
    """Link notebook Colab để app mở bằng một nút."""
    repo = (os.environ.get("WAI_REPO_SLUG") or "manhlee1196-boop/ai-anime3").strip()
    ref, kind = git_ref()
    notebook = "colab/WAI_v17_1click.ipynb"
    return {
        "repo": repo,
        "branch": ref,
        "ref": ref,
        "ref_kind": kind,
        "notebook": notebook,
        "url": f"https://colab.research.google.com/github/{repo}/blob/"
               f"{quote(ref, safe='')}/{notebook}",
        # lệnh dán vào Colab khi cần kiểm tra/lấy link mới
        "cmd_status": "bash /content/install.sh --status",
        "cmd_restart": "bash /content/install.sh --only launch,verify --restart",
    }


def build_payload(min_count=DEFAULT_MIN_COUNT):
    """Dựng dict dữ liệu cho app (hàm thuần, dùng lại được trong test)."""
    translations = load_translations()
    tags = load_tags()
    tags.sort(key=lambda item: (-item[2], item[0]))
    group_index = {name: i for i, name in enumerate(GROUP_ORDER)}
    fallback_group = len(GROUP_ORDER) - 1

    rows = []
    for tag, category, post_count in tags:
        vi = translations.get(tag)
        if post_count < min_count and not vi:
            continue
        group = group_index.get(classify(tag, category), fallback_group)
        rows.append([tag, post_count, category, group, vi or 0])

    # Chip gợi ý: tag phổ biến nhất của mỗi nhóm duyệt thư viện.
    quick = {}
    wanted = set(BROWSE_GROUPS)
    for tag, post_count, _category, group, vi in rows:
        name = GROUP_ORDER[group]
        if name not in wanted:
            continue
        bucket = quick.setdefault(name, [])
        if len(bucket) < QUICK_PER_GROUP:
            bucket.append([tag, vi])

    payload = {
        "v": 1,
        "min_count": min_count,
        "source": f"{TAGS_CSV} + {VI_CSV}",
        "groups": list(GROUP_ORDER),
        "group_labels": [GROUP_LABELS.get(name, name) for name in GROUP_ORDER],
        "browse_groups": list(BROWSE_GROUPS),
        "categories": {str(key): value for key, value in CATEGORY_NAMES.items()},
        "presets": {
            "quality": ST.QUALITY_PRESETS,
            "negative": ST.NEGATIVE_PRESETS,
            "ratings": ST.RATINGS,
            "sizes": [[label, list(size)] for label, size in SIZE_PRESETS_ORDER],
            "defaults": {
                key: ST.WAI_DEFAULTS[key]
                for key in ("steps", "cfg_scale", "sampler_name", "scheduler", "clip_skip",
                            "width", "height", "batch_size", "enable_hr", "hr_upscaler",
                            "hr_scale", "hr_second_pass_steps", "denoising_strength")
            },
            "samplers": ["Euler a", "Euler", "DPM++ 2M", "DPM++ 2M SDE", "DPM++ 3M SDE",
                         "UniPC", "LCM", "DDIM"],
            "style_presets": [[name, list(tags_), note]
                              for name, (tags_, note) in STYLE_PRESETS.items()],
        },
        "colab": colab_info(),
        "styles": load_styles(),
        "quick": quick,
        "tags": rows,
    }
    return payload


def dump(payload):
    """Chuỗi JSON gọn, ổn định giữa các lần chạy (để `--check` so sánh được)."""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=False)


def write(payload):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    text = dump(payload)
    raw = text.encode("utf-8")
    OUT_JSON.write_bytes(raw + b"\n")
    # Bản nén để điện thoại tải nhanh qua tunnel Colab (app tự giải nén nếu được).
    with gzip.GzipFile(filename="", mode="wb", fileobj=OUT_GZ.open("wb"), mtime=0) as gz:
        gz.write(raw)
    return len(raw), OUT_GZ.stat().st_size


def check(payload):
    """Trả về danh sách lỗi khi file đã sinh không khớp dữ liệu hiện tại."""
    problems = []
    if not OUT_JSON.is_file():
        return [f"thiếu {OUT_JSON.relative_to(ROOT)}"]
    expected = dump(payload).encode("utf-8")
    actual = OUT_JSON.read_bytes().rstrip(b"\n")
    if actual != expected:
        problems.append(f"{OUT_JSON.relative_to(ROOT)} không khớp CSV — chạy lại "
                        f"`python3 mobile/build_data.py`")
    if not OUT_GZ.is_file():
        problems.append(f"thiếu {OUT_GZ.relative_to(ROOT)}")
    else:
        with gzip.open(OUT_GZ, "rb") as handle:
            if handle.read() != expected:
                problems.append(f"{OUT_GZ.relative_to(ROOT)} không khớp bản .json")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description="Sinh dữ liệu tag cho app điện thoại.")
    parser.add_argument("--min-count", type=int, default=DEFAULT_MIN_COUNT,
                        help=f"ngưỡng post_count tối thiểu (mặc định {DEFAULT_MIN_COUNT})")
    parser.add_argument("--check", action="store_true",
                        help="chỉ kiểm tra file đã sinh, không ghi")
    args = parser.parse_args(argv)

    payload = build_payload(args.min_count)
    if args.check:
        problems = check(payload)
        if problems:
            for problem in problems:
                print(f"❌ {problem}")
            return 1
        print(f"✅ {OUT_JSON.relative_to(ROOT)} khớp "
              f"{len(payload['tags']):,} tag")
        return 0

    raw_size, gz_size = write(payload)
    print(f"✅ {OUT_JSON.relative_to(ROOT)}: {len(payload['tags']):,} tag · "
          f"{raw_size / 1e6:.2f} MB · gz {gz_size / 1e6:.2f} MB · "
          f"{len(payload['styles'])} tag phong cách · min_count={args.min_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
