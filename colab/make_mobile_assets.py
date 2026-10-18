"""Sinh file mobile cho extension Forge từ prompt_lib/mobile.py — nguồn duy nhất.

Forge/A1111 tự nạp ``style.css`` ở thư mục gốc extension và mọi ``*.js`` trong
``javascript/``, nên tab "Prompt VN" (và cả txt2img/img2img gốc) nhận bản tối
ưu điện thoại mà không cần Blocks(css=...) (Blocks con trong tab của Forge
không được gắn css riêng).

    python3 colab/make_mobile_assets.py            # ghi 2 file vào extension/
    python3 colab/make_mobile_assets.py --check    # chỉ kiểm tra đồng bộ (CI)

App độc lập ``prompt_builder.py`` KHÔNG đọc hai file này; nó lấy trực tiếp
``mobile_css()``/``mobile_head()`` nên hai bề mặt không bao giờ lệch nội dung.
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from prompt_lib.mobile import render_extension_js, render_style_css  # noqa: E402

TARGETS = {
    HERE / "extension/vi-prompt-builder/style.css": render_style_css,
    HERE / "extension/vi-prompt-builder/javascript/vi_mobile.js": render_extension_js,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="không ghi file; thoát khác 0 nếu file đích lệch nguồn")
    args = parser.parse_args()

    stale = []
    for path, render in TARGETS.items():
        content = render()
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == content:
            print(f"✔ Đã đồng bộ: {path.relative_to(HERE.parent)}")
            continue
        stale.append(path)
        if not args.check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            print(f"✎ Đã sinh: {path.relative_to(HERE.parent)} ({len(content)} ký tự)")
    if args.check and stale:
        for path in stale:
            print(f"✗ Lệch nguồn: {path.relative_to(HERE.parent)} — chạy lại không có --check")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
