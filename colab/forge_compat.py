#!/usr/bin/env python3
"""Bản vá tương thích Neo: cmd-flags typed None và checkpoint dropdown khởi tạo rỗng.

Chỉ stdlib; không import Forge/Torch. Vá đúng đoạn mã đã biết, backup trước khi ghi,
kiểm AST cả hai file trước khi thay. Không sửa config/prompt/model hoặc tắt validation.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import os
import tempfile
from pathlib import Path

COMPAT_VERSION = "1"
API_MARKER = "# WAI_COMPAT_FLAGS_V1"
UI_MARKER = "# WAI_COMPAT_CHECKPOINT_UI_V1"
API_OLD = '''        if _options[key].default is not None:
            _type = type(_options[key].default)
        flags.update({flag.dest: (_type, Field(default=flag.default, description=flag.help))})'''
API_NEW = '''        if _options[key].default is not None:
            _type = type(_options[key].default)
        elif flag.type in (int, float, str):  # WAI_COMPAT_FLAGS_V1
            _type = Optional[flag.type]
        flags.update({flag.dest: (_type, Field(default=flag.default, description=flag.help))})'''
UI_OLD = '''    ui_checkpoint = gr.Dropdown(label="Checkpoint", value=None, choices=None, elem_id="setting_sd_model_checkpoint", elem_classes=["model_selection"])'''
UI_NEW = '''    # WAI_COMPAT_CHECKPOINT_UI_V1: populate config before browser load callbacks.
    _wai_ckpt_choices, _wai_module_choices = refresh_models()
    _wai_ckpt = sd_models.select_checkpoint()
    _wai_ckpt_value = None
    if _wai_ckpt is not None:
        _wai_ckpt_value = _wai_ckpt.short_title if shared.opts.sd_checkpoint_dropdown_use_short else _wai_ckpt.name
    if _wai_ckpt_value not in _wai_ckpt_choices:
        _wai_ckpt_value = None
    ui_checkpoint = gr.Dropdown(label="Checkpoint", value=_wai_ckpt_value, choices=_wai_ckpt_choices, elem_id="setting_sd_model_checkpoint", elem_classes=["model_selection"])'''

PATCHES = (
    ("modules/api/models.py", API_MARKER, API_OLD, API_NEW),
    ("modules_forge/main_entry.py", UI_MARKER, UI_OLD, UI_NEW),
)


class CompatError(ValueError):
    pass


def plan(forge_dir):
    plans = []
    for relative, marker, old, new in PATCHES:
        path = Path(forge_dir) / relative
        try:
            data = path.read_bytes()
            text = data.decode("utf-8")
            ast.parse(text, filename=relative)
        except (OSError, UnicodeError, SyntaxError) as exc:
            raise CompatError(f"Không đọc được {relative} ({type(exc).__name__}); chưa vá gì.") from None
        newline = "\r\n" if "\r\n" in text else "\n"
        normalized = text.replace("\r\n", "\n")
        if marker in normalized:
            if normalized.count(marker) != 1 or normalized.count(new) != 1:
                raise CompatError(f"Marker trong {relative} không khớp bản vá; giữ nguyên file.")
            plans.append((path, data, data))
            continue
        if normalized.count(old) != 1:
            raise CompatError(f"{relative} không khớp đoạn Neo đã kiểm tra; giữ nguyên, cần rà soát phiên bản mới.")
        updated = normalized.replace(old, new, 1)
        ast.parse(updated, filename=relative)
        plans.append((path, data, updated.replace("\n", newline).encode("utf-8")))
    return plans


def _atomic_bytes(path, data, mode):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.wai-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(mode)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def apply(forge_dir):
    plans = plan(forge_dir)  # từ chối cả đợt trước khi ghi nếu một file không khớp
    changed = []
    try:
        for path, before, after in plans:
            if before == after:
                continue
            backup = path.with_name(path.name + ".wai-compat-" + hashlib.sha256(before).hexdigest()[:12] + ".bak")
            if backup.exists() and backup.read_bytes() != before:
                raise CompatError(f"Backup {backup.name} có nội dung khác; không ghi đè.")
            if not backup.exists():
                with backup.open("xb") as stream:
                    stream.write(before)
                backup.chmod(0o600)
            mode = path.stat().st_mode & 0o777
            _atomic_bytes(path, after, mode)
            changed.append((path, before, mode))
            print(f"Compat: đã vá {path.relative_to(forge_dir)} · backup {backup.name}")
    except (OSError, CompatError):
        for path, before, mode in reversed(changed):
            _atomic_bytes(path, before, mode)
        raise
    print("Compat: cmd-flags giữ đúng kiểu port; checkpoint choices/value có ngay trong config UI.")
    return len(changed)


def check(forge_dir):
    return all(before == after for _, before, after in plan(forge_dir))


def verify_flags(base_url):
    # Vẫn dùng response-model Neo đã vá; không tắt validation để giấu HTTP 500.
    from checkpoint_tools import CheckpointError, api_json
    from urllib.parse import urlsplit
    try:
        flags = api_json(base_url, "/sdapi/v1/cmd-flags")
    except CheckpointError as exc:
        raise CompatError(str(exc)) from None
    expected_port = urlsplit(base_url).port or (443 if base_url.startswith("https:") else 80)
    if not isinstance(flags, dict) or type(flags.get("port")) is not int or flags["port"] != expected_port:
        raise CompatError("cmd-flags không trả đúng port kiểu integer; chưa xác nhận API tương thích.")
    return flags["port"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("forge_dir", type=Path)
    parser.add_argument("--check", action="store_true", help="Chỉ kiểm tra marker/nội dung, không ghi")
    parser.add_argument("--api-url", default="", help="Xác nhận thêm cmd-flags trả port integer; không in toàn bộ flags")
    args = parser.parse_args()
    try:
        if args.check:
            if not check(args.forge_dir):
                print("Compat: chưa áp dụng đủ bản vá API/dropdown.")
                return 1
        else:
            apply(args.forge_dir)
        if args.api_url:
            port = verify_flags(args.api_url)
            print(f"Compat API: cmd-flags HTTP 200, port integer = {port}.")
    except (OSError, CompatError) as exc:
        print(f"Compat: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
