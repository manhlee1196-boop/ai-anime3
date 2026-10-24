#!/usr/bin/env python3
"""Checkpoint: kiểm tra container, đăng ký file, cấu hình preset và đối chiếu API.

Chỉ dùng stdlib, không import Forge/torch, không nạp tensor vào RAM/GPU. SHA256 và
header hợp lệ KHÔNG chứng minh model sinh ảnh được; dùng --smoke-test trên Colab.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import math
import os
import re
import shutil
import struct
import tempfile
import uuid
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

CHECKPOINT_API_VERSION = 1
MAX_HEADER = 100_000_000  # giới hạn của định dạng safetensors
DTYPE_BITS = {"BOOL": 8, "U8": 8, "I8": 8, "I16": 16, "U16": 16, "I32": 32,
              "U32": 32, "I64": 64, "U64": 64, "F16": 16, "BF16": 16,
              "F32": 32, "F64": 64, "F8_E4M3": 8, "F8_E5M2": 8,
              "F8_E4M3FN": 8, "F8_E4M3FNUZ": 8, "F8_E5M2FNUZ": 8,
              "F8_E8M0": 8, "F4": 4, "F6_E2M3": 6, "F6_E3M2": 6}


class CheckpointError(ValueError):
    pass


def read_object(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CheckpointError(f"Không đọc được JSON {path.name} ({type(exc).__name__}); giữ nguyên file.") from exc
    if not isinstance(data, dict):
        raise CheckpointError(f"{path.name} phải là JSON object; giữ nguyên file.")
    return data


def atomic_json(path: Path, data: dict, backup_kind: str = "") -> None:
    if path.exists() and read_object(path) == data:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and backup_kind:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        backup = path.with_name(f"{path.name}.wai-{backup_kind}-backup-{stamp}-{uuid.uuid4().hex[:8]}")
        shutil.copy2(path, backup)
        backup.chmod(0o600)
        print(f"Backup: {backup}")
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.wai-", delete=False) as f:
            tmp = Path(f.name)
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(path)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _unique_object(pairs):
    data = {}
    for key, value in pairs:
        if key in data:
            raise CheckpointError("Header safetensors có khóa JSON trùng nhau.")
        data[key] = value
    return data


def inspect_safetensors(path: str | Path, sha: str = "", min_bytes: int = 0, allow_download_temp=False) -> dict:
    path = Path(path)
    filename_ok = path.suffix.lower() == ".safetensors"
    if allow_download_temp and path.name.lower().endswith(".safetensors.part"):
        filename_ok = True  # chỉ kiểm container đã tải xong; KHÔNG đăng ký .part
    if not filename_ok or not path.is_file():
        raise CheckpointError(f"Không có checkpoint .safetensors hoàn chỉnh: {path}")
    size = path.stat().st_size
    if size < max(10, min_bytes):
        raise CheckpointError(f"Checkpoint quá nhỏ/tải dở: {size:,} byte, cần ≥{max(10, min_bytes):,}.")
    with path.open("rb") as f:
        prefix = f.read(8)
        if prefix.startswith((b"version ", b"<!DOCTYP", b"<html", b"{\"error")):
            raise CheckpointError("File là pointer Git LFS/HTML/lỗi API, không phải trọng số model.")
        header_size = int.from_bytes(prefix, "little")
        if not 2 < header_size <= min(MAX_HEADER, size - 8):
            raise CheckpointError("Header safetensors không hợp lệ; file tải dở hoặc không phải safetensors.")
        try:
            header = json.loads(f.read(header_size), object_pairs_hook=_unique_object)
        except (ValueError, UnicodeError) as exc:
            raise CheckpointError("Header safetensors không phải JSON hợp lệ.") from exc
    if not isinstance(header, dict):
        raise CheckpointError("Header safetensors phải là JSON object.")
    metadata = header.get("__metadata__", {})
    if not isinstance(metadata, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in metadata.items()):
        raise CheckpointError("Metadata safetensors phải là các cặp string/string.")
    tensors = {k: v for k, v in header.items() if k != "__metadata__"}
    if not tensors:
        raise CheckpointError("Checkpoint không có tensor nào.")
    data_size = size - 8 - header_size
    intervals, dtypes = [], Counter()
    for name, tensor in tensors.items():
        if not isinstance(tensor, dict):
            raise CheckpointError("Mô tả tensor trong header không hợp lệ.")
        dtype, shape, offsets = tensor.get("dtype"), tensor.get("shape"), tensor.get("data_offsets")
        if not isinstance(dtype, str) or dtype not in DTYPE_BITS:
            raise CheckpointError(f"Dtype safetensors chưa được hỗ trợ: {str(dtype)[:40]}.")
        if not isinstance(shape, list) or any(type(n) is not int or n < 0 for n in shape):
            raise CheckpointError("Shape tensor không hợp lệ.")
        if (not isinstance(offsets, list) or len(offsets) != 2
                or any(type(n) is not int for n in offsets)):
            raise CheckpointError("Data offsets tensor không hợp lệ.")
        start, end = offsets
        expected = (math.prod(shape) * DTYPE_BITS[dtype] + 7) // 8
        if not 0 <= start <= end <= data_size or end - start != expected:
            raise CheckpointError("Tensor bị cắt ngắn/offset hoặc số byte không khớp shape/dtype.")
        intervals.append((start, end))
        dtypes[dtype] += 1
    cursor = 0
    for start, end in sorted(intervals):
        if start != cursor:
            raise CheckpointError("Tensor chồng lấn hoặc dữ liệu có khoảng trống.")
        cursor = end
    if cursor != data_size:
        raise CheckpointError("Kích thước dữ liệu tensor không khớp header (file tải dở/thừa byte).")
    if sha and not re.fullmatch(r"[a-fA-F0-9]{64}", sha):
        raise CheckpointError("SHA256 phải có 64 ký tự hex.")
    actual_sha = sha256_file(path) if sha else ""
    if sha and actual_sha != sha.lower():
        raise CheckpointError("Checkpoint không khớp SHA256 đã chọn; không đăng ký/nạp file này.")
    return {"file": str(path.absolute()), "realpath": str(path.resolve()), "bytes": size,
            "header_bytes": header_size, "tensors": len(tensors), "dtypes": dict(dtypes),
            "sha256": actual_sha,
            "sdxl_keys": any(k.startswith("conditioner.embedders.1.") for k in tensors)}


def register_checkpoint(forge_dir: Path, path: Path, sha: str) -> Path:
    """Symlink nhỏ trong đường quét mặc định; không copy GB, không đè file của user."""
    default_dir = forge_dir / "models/Stable-diffusion"
    default_dir.mkdir(parents=True, exist_ok=True)
    alias = default_dir / path.name
    source = path.resolve(strict=True)
    manifest_path = forge_dir / ".wai_checkpoint_links.json"
    manifest = read_object(manifest_path)
    records = manifest.get("links", {})
    if not isinstance(records, dict):
        raise CheckpointError("Manifest symlink checkpoint hỏng; không sửa alias không rõ nguồn.")
    if alias.exists() and os.path.samefile(alias, source):
        return alias
    if alias.is_symlink():
        old = records.get(path.name, {})
        if (not isinstance(old, dict) or old.get("link") != str(alias.absolute())
                or old.get("target") != os.readlink(alias)):
            raise CheckpointError(f"Alias {alias} là symlink không do bộ cài quản lý; không ghi đè.")
    elif alias.exists():
        # Kể cả cùng SHA, hai bản sao thật có đường dẫn khác nhau vẫn có thể
        # ghi đè title trong registry Neo. Không xóa bản của user để tạo alias.
        raise CheckpointError(f"Có file checkpoint trùng tên tại {alias}; không ghi đè/chọn nhầm. Dùng một đường dẫn model duy nhất.")
    tmp = alias.with_name(f".{alias.name}.wai-{uuid.uuid4().hex[:8]}")
    try:
        tmp.symlink_to(source)
        tmp.replace(alias)
    finally:
        tmp.unlink(missing_ok=True)
    records[path.name] = {"link": str(alias.absolute()), "target": str(source)}
    manifest["links"] = records
    atomic_json(manifest_path, manifest)
    return alias


def configure_checkpoint(forge_dir: str | Path, path: str | Path, sha: str,
                         model_id="fp16", cfg=6.0, steps=25, hires_steps=20) -> dict:
    forge_dir, path = Path(forge_dir), Path(path).absolute()
    if not sha:
        raise CheckpointError("Chưa có SHA256 checkpoint; cần metadata model.json hoặc --model-sha. Không bỏ xác minh.")
    if not math.isfinite(cfg) or not 0.1 <= cfg <= 30 or not 1 <= steps <= 150 or not 0 <= hires_steps <= 150:
        raise CheckpointError("CFG/steps profile không hợp lệ; không ghi cấu hình.")
    info = inspect_safetensors(path, sha)
    # Kiểm JSON cả hai file trước khi thay đổi gì. Không đặt lại toàn bộ UI.
    config_path, ui_path = forge_dir / "config.json", forge_dir / "ui-config.json"
    data, ui = read_object(config_path), read_object(ui_path)
    alias = register_checkpoint(forge_dir, path, sha)
    preset = "xl"  # catalog WAI v17 và custom của bộ cài đều dành cho SDXL
    data.update({"sd_model_checkpoint": path.name, "forge_preset": preset,
                 "forge_checkpoint_xl": path.name,
                 "forge_additional_modules": [], "forge_additional_modules_xl": [],
                 "forge_unet_storage_dtype": "Automatic", "forge_unet_storage_dtype_xl": "Automatic",
                 "clip_stop_at_last_layers": 2,
                 "xl_t2i_step": int(steps), "xl_i2i_step": int(steps), "xl_t2i_hr_step": int(hires_steps),
                 "xl_t2i_cfg": float(cfg), "xl_i2i_cfg": float(cfg), "xl_t2i_hr_cfg": float(cfg),
                 "xl_t2i_sampler": "Euler a", "xl_i2i_sampler": "Euler a",
                 "xl_t2i_scheduler": "Automatic", "xl_i2i_scheduler": "Automatic",
                 "xl_t2i_width": 1024, "xl_i2i_width": 1024,
                 "xl_t2i_height": 1344, "xl_i2i_height": 1344})
    # UI defaults cũ có thể khôi phục preset sd dù config.json đã chọn xl.
    # Chỉ sửa key UI Preset, giữ nguyên prompt, kích thước và mọi key UI khác.
    for key in ui:
        if key.endswith("/UI Preset/value"):
            ui[key] = preset
    atomic_json(config_path, data, "checkpoint")
    if ui_path.exists():
        atomic_json(ui_path, ui, "checkpoint")
    print(f"Checkpoint đã đăng ký: {path} → {alias}")
    print(f"Preset XL: {path.name} · {model_id} · CFG {cfg} / steps {steps} · dtype Automatic")
    return info


def api_json(base: str, endpoint: str, payload=None, timeout=12):
    url = base.rstrip("/") + endpoint
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as exc:
        raise CheckpointError(f"API {endpoint} trả HTTP {exc.code}; xem forge.log/quyền API.") from exc
    except (OSError, ValueError) as exc:
        raise CheckpointError(f"Không đọc được API {endpoint} ({type(exc).__name__}).") from exc


def registered_model(models, path: Path, sha="") -> dict:
    if not isinstance(models, list):
        raise CheckpointError("/sd-models không trả danh sách checkpoint.")
    wanted = path.resolve(strict=True)
    for m in models:
        if not isinstance(m, dict) or not isinstance(m.get("filename"), str):
            continue
        filename = Path(m["filename"])
        if filename.resolve() != wanted:
            # Hardlink cũng là cùng physical file; không nhận chỉ dựa vào basename.
            try:
                if not os.path.samefile(filename, wanted):
                    continue
            except OSError:
                continue
        remote_sha = m.get("sha256")
        if sha and remote_sha and str(remote_sha).lower() != sha.lower():
            raise CheckpointError("Forge trả hash khác checkpoint đã xác minh; không coi là đúng model.")
        return m
    raise CheckpointError("Forge chưa quét đúng đường dẫn checkpoint (không chỉ so tên file). Kiểm tra --ckpt-dirs/alias và restart.")


def selected_alias(value, model: dict) -> bool:
    if not isinstance(value, str) or not value or value.lower() == "none":
        return False
    filename = Path(model["filename"])
    title = model.get("title", "")
    names = {filename.name, filename.stem}
    names.update(v for v in (model.get("model_name"), model.get("hash"), model.get("sha256"), title)
                 if isinstance(v, str))
    if isinstance(title, str):
        names.add(title.split(" [", 1)[0])
    if model.get("hash"):
        names.add(f"{filename.stem} [{model['hash']}]")
    return value in names


def verify_api(base: str, path: str | Path, sha="", registry_only=False) -> dict:
    model = registered_model(api_json(base, "/sdapi/v1/sd-models"), Path(path), sha)
    if registry_only:
        return model
    options = api_json(base, "/sdapi/v1/options")
    if not isinstance(options, dict):
        raise CheckpointError("/options không trả JSON object.")
    if not selected_alias(options.get("sd_model_checkpoint"), model):
        raise CheckpointError("Checkpoint tồn tại nhưng sd_model_checkpoint chưa chọn đúng model.")
    if options.get("forge_preset") != "xl" or not selected_alias(options.get("forge_checkpoint_xl"), model):
        raise CheckpointError("Preset XL chưa chọn đúng checkpoint (forge_checkpoint_xl trống/sai); không báo cài xong.")
    return {"model": model, "selected": options.get("sd_model_checkpoint"), "preset": options.get("forge_preset")}


def validate_png(image: bytes, width: int, height: int) -> None:
    if image[:8] != b"\x89PNG\r\n\x1a\n":
        raise CheckpointError("Ảnh thử không phải PNG.")
    offset, has_header, has_data, has_end = 8, False, False, False
    while offset + 12 <= len(image):
        length = int.from_bytes(image[offset:offset+4], "big")
        kind = image[offset+4:offset+8]
        end = offset + 12 + length
        if end > len(image):
            raise CheckpointError("PNG bị cắt ngắn.")
        data = image[offset+8:offset+8+length]
        crc = int.from_bytes(image[offset+8+length:end], "big")
        if binascii.crc32(kind + data) & 0xffffffff != crc:
            raise CheckpointError("PNG có CRC sai.")
        if not has_header and kind != b"IHDR":
            raise CheckpointError("PNG thiếu IHDR đầu tiên.")
        if kind == b"IHDR":
            if has_header or length != 13 or struct.unpack(">II", data[:8]) != (width, height):
                raise CheckpointError("Kích thước/header PNG không khớp ảnh thử.")
            has_header = True
        elif kind == b"IDAT":
            has_data = has_data or bool(data)
        elif kind == b"IEND":
            if length != 0:
                raise CheckpointError("IEND PNG không hợp lệ.")
            has_end = True
            offset = end
            break
        offset = end
    if not has_header or not has_data or not has_end or offset != len(image):
        raise CheckpointError("PNG thiếu dữ liệu/kết thúc hoặc thừa byte.")


def smoke_test(base: str, path: str | Path, sha: str, output: str | Path) -> dict:
    if not re.fullmatch(r"[a-fA-F0-9]{64}", sha):
        raise CheckpointError("Sinh thử cần SHA256 đã xác minh của checkpoint.")
    verify_api(base, path, sha)
    payload = {"prompt": "masterpiece, best quality, rating_general, general, landscape, mountains, no humans",
               "negative_prompt": "nsfw, rating_explicit, lowres", "steps": 1, "cfg_scale": 1.0,
               "width": 256, "height": 256, "seed": 12345, "batch_size": 1, "n_iter": 1,
               "sampler_name": "Euler a", "enable_hr": False,
               "save_images": False, "send_images": True,
               "override_settings": {"clip_stop_at_last_layers": 2, "samples_format": "png"}}
    # 1 bước 256×256: nếu quá 10 phút thì checkpoint kẹt (nạp/VRAM), không chờ 30 phút nữa.
    response = api_json(base, "/sdapi/v1/txt2img", payload, timeout=600)
    if not isinstance(response, dict) or not isinstance(response.get("images"), list) or not response["images"]:
        raise CheckpointError("Sinh thử không trả ảnh; chưa chứng minh checkpoint nạp được.")
    try:
        image = base64.b64decode(response["images"][0].split(",", 1)[-1], validate=True)
        validate_png(image, 256, 256)
        info = response.get("info", {})
        if isinstance(info, str):
            info = json.loads(info)
        if not isinstance(info, dict):
            raise ValueError("bad info")
    except (ValueError, TypeError, AttributeError) as exc:
        raise CheckpointError("Kết quả sinh thử không phải PNG/info hợp lệ.") from exc
    model_hash = info.get("sd_model_hash")
    if model_hash is None or model_hash == "":
        # Một số Neo chưa có shorthash ở lần nạp đầu, nhưng forge_model_reload
        # ghi sd_checkpoint_hash đầy đủ sau khi nạp. Không sửa nguồn/hashes cache.
        loaded = api_json(base, "/sdapi/v1/options")
        model_hash = loaded.get("sd_checkpoint_hash") if isinstance(loaded, dict) else None
    if (not isinstance(model_hash, str) or not re.fullmatch(r"[a-fA-F0-9]{8,64}", model_hash)
            or not sha.lower().startswith(model_hash.lower())):
        raise CheckpointError("Ảnh thử thiếu/sai hash model; không xác nhận đã nạp đúng checkpoint.")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_name(f".{output.name}.{uuid.uuid4().hex[:8]}")
    try:
        tmp.write_bytes(image)
        tmp.replace(output)
    finally:
        tmp.unlink(missing_ok=True)
    print(f"Đã sinh thử 256×256 / 1 step bằng checkpoint hash {model_hash}: {output}")
    return info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("file"); validate.add_argument("--sha", default="")
    validate.add_argument("--min-bytes", type=int, default=0); validate.add_argument("--quiet", action="store_true")
    validate.add_argument("--download-temp", action="store_true")
    configure = commands.add_parser("configure")
    configure.add_argument("forge_dir"); configure.add_argument("file"); configure.add_argument("--sha", required=True)
    configure.add_argument("--model-id", default="fp16")
    configure.add_argument("--cfg", type=float, default=6.0); configure.add_argument("--steps", type=int, default=25)
    configure.add_argument("--hires-steps", type=int, default=20)
    verify = commands.add_parser("api")
    verify.add_argument("base"); verify.add_argument("file"); verify.add_argument("--sha", default="")
    verify.add_argument("--registry-only", action="store_true")
    smoke = commands.add_parser("smoke")
    smoke.add_argument("base"); smoke.add_argument("file"); smoke.add_argument("--sha", required=True)
    smoke.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            result = inspect_safetensors(args.file, args.sha, args.min_bytes, args.download_temp)
            if not args.quiet:
                print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "configure":
            configure_checkpoint(args.forge_dir, args.file, args.sha, args.model_id, args.cfg, args.steps, args.hires_steps)
        elif args.command == "api":
            result = verify_api(args.base, args.file, args.sha, args.registry_only)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "smoke":
            smoke_test(args.base, args.file, args.sha, args.output)
    except (CheckpointError, OSError) as exc:
        parser.exit(1, f"✖ Checkpoint: {exc}\n")


if __name__ == "__main__":
    main()
