#!/usr/bin/env python3
"""Chẩn đoán Colab chỉ đọc: checkpoint, Forge/preset, API, venv và GPU.

Không tải model, mount Drive, khởi động server, ghi config/marker hay sinh ảnh.
Không in toàn bộ config, cmdline hoặc log (có thể chứa token/password/prompt riêng).
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from checkpoint_tools import CheckpointError, api_json, inspect_safetensors, verify_api

CONFIG_FIELDS = ("VERSION_UID", "sd_model_checkpoint", "forge_preset", "forge_checkpoint_xl",
                 "forge_unet_storage_dtype", "forge_unet_storage_dtype_xl", "clip_stop_at_last_layers",
                 "forge_additional_modules", "forge_additional_modules_xl", "sd_checkpoint_hash")
FLAG_FIELDS = ("ckpt_dirs", "data_dir", "model_ref", "ui_settings_file", "ui_config_file", "port", "listen", "api")
MODEL_FIELDS = ("filename", "title", "model_name", "hash", "sha256")


def _json_file(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _run(argv, timeout=15):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip() if result.returncode == 0 else "không có/chưa sẵn sàng"
    except (OSError, subprocess.TimeoutExpired):
        return "không có/chưa sẵn sàng"


def _source_uid(path):
    try:
        for node in ast.parse(Path(path).read_text(encoding="utf-8")).body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "VERSION_UID":
                return ast.literal_eval(node.value)
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "VERSION_UID" for t in node.targets):
                return ast.literal_eval(node.value)
    except (OSError, ValueError, SyntaxError):
        pass
    return "không đọc được"


def collect(repo_dir, forge_dir, model_dir, model_file, state_dir, port):
    repo, forge, models, state = map(Path, (repo_dir, forge_dir, model_dir, state_dir))
    cached = _json_file(state / "model.json")
    filename = model_file or cached.get("file") or "waiIllustriousSDXL_v170.safetensors"
    # Không dùng path từ cache nếu không còn là basename hợp lệ.
    if not isinstance(filename, str) or Path(filename).name != filename:
        filename = "waiIllustriousSDXL_v170.safetensors"
    selected = models / filename
    sha = cached.get("sha256", "") if cached.get("dir") == str(models) and cached.get("file") == filename else ""
    report = {
        "thoi_diem_utc": datetime.now(timezone.utc).isoformat(),
        "luu_y": "Chỉ đọc; header không thay thế SHA256 hoặc sinh ảnh thật. Không in token/config/log đầy đủ.",
        "repo": {"path": str(repo), "commit": _run(["git", "-C", str(repo), "rev-parse", "HEAD"])},
        "forge": {"path": str(forge), "commit": _run(["git", "-C", str(forge), "rev-parse", "HEAD"]),
                  "version_uid_trong_ma": _source_uid(forge / "modules/launch_utils.py")},
        "checkpoint_du_kien": {"file": str(selected), "sha256_da_luu": sha, "sha_da_kiem_tra_trong_chan_doan": False},
        "config": {k: v for k, v in _json_file(forge / "config.json").items() if k in CONFIG_FIELDS},
        "gpu": _run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"]),
    }
    files, seen = [], set()
    for folder in (models, forge / "models/Stable-diffusion"):
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*.safetensors*")):
            if str(path) in seen:
                continue
            seen.add(str(path))
            entry = {"file": str(path), "symlink": path.is_symlink()}
            try:
                entry["bytes"] = path.stat().st_size
                entry["realpath"] = str(path.resolve())
                if path.suffix.lower() == ".safetensors":
                    entry["header"] = inspect_safetensors(path)
                else:
                    entry["trang_thai"] = "file tải dở/temp, Forge KHÔNG nhận nó là checkpoint"
            except (OSError, CheckpointError) as exc:
                entry["loi"] = str(exc)
            files.append(entry)
            if len(files) >= 60:
                break
        if len(files) >= 60:
            break
    report["files_checkpoint"] = files
    venv = forge / "venv/bin/python"
    version_code = '''import importlib.metadata as m,json,sys
packages={}
for name in ('torch','torchvision','gradio','safetensors','huggingface-hub'):
    try: packages[name]=m.version(name)
    except m.PackageNotFoundError: packages[name]='chưa cài'
print(json.dumps({'python':sys.version,'packages':packages}))'''
    versions = _run([str(venv), "-c", version_code])
    try:
        report["venv"] = json.loads(versions)
    except ValueError:
        report["venv"] = "không có/chưa đọc được package metadata"
    base = f"http://127.0.0.1:{int(port)}"
    api = {}
    for endpoint, label, fields in (("/sdapi/v1/cmd-flags", "cmd_flags", FLAG_FIELDS),
                                     ("/sdapi/v1/options", "options", CONFIG_FIELDS)):
        try:
            data = api_json(base, endpoint)
            api[label] = {k: v for k, v in data.items() if k in fields} if isinstance(data, dict) else "JSON sai kiểu"
        except CheckpointError as exc:
            api[label] = {"loi": str(exc)}
    try:
        data = api_json(base, "/sdapi/v1/sd-models")
        api["models"] = [{k: m.get(k) for k in MODEL_FIELDS} for m in data[:60] if isinstance(m, dict)] if isinstance(data, list) else "JSON sai kiểu"
        verify_api(base, selected, sha)
        api["checkpoint_da_dang_ky_va_chon"] = True
    except (CheckpointError, OSError) as exc:
        api["checkpoint_da_dang_ky_va_chon"] = False
        api["loi_checkpoint"] = str(exc)
    report["api"] = api
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-dir", default="/content/ai-anime3")
    parser.add_argument("--forge-dir", default="/content/sd-webui-forge-neo")
    parser.add_argument("--model-dir", default="/content/models")
    parser.add_argument("--model-file", default="")
    parser.add_argument("--state-dir", default="/content/.wai_state")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    report = collect(args.repo_dir, args.forge_dir, args.model_dir, args.model_file, args.state_dir, args.port)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    for name in ("CIVITAI_TOKEN", "GITHUB_TOKEN", "HF_TOKEN", "FORGE_API_AUTH"):
        token = os.environ.get(name)
        if token:
            text = text.replace(token, "<redacted>")
    print(text)


if __name__ == "__main__":
    main()
