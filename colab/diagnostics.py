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
import re
import socket
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from urllib.parse import urlsplit
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


def checkpoint_ui_summary(config):
    """Chỉ trích checkpoint từ Gradio /config; không đưa prompt/auth/config khác vào báo cáo."""
    if not isinstance(config, dict) or not isinstance(config.get("components"), list):
        return {"loi": "Config UI không đúng định dạng Gradio"}
    checkpoints = []
    for component in config["components"]:
        if not isinstance(component, dict):
            continue
        props = component.get("props", {})
        if not isinstance(props, dict) or props.get("elem_id") != "setting_sd_model_checkpoint":
            continue
        choices = props.get("choices") or []
        if not isinstance(choices, list):
            choices = []
        values = [c[1] if isinstance(c, (list, tuple)) and len(c) == 2 else c for c in choices]
        value = props.get("value")
        checkpoints.append({"component_id": component.get("id"), "choices_count": len(choices),
                            "choices": choices[:60], "value": value,
                            "value_in_choices": value is not None and value in values})
    return {"tim_thay_dropdown": bool(checkpoints), "checkpoints": checkpoints}


def validate_public_url(value):
    """Chỉ nhận origin tunnel, không gửi request tới URL chứa auth/query/path."""
    if not value:
        return ""
    parts = urlsplit(value)
    if (parts.scheme != "https" or parts.username is not None or parts.password is not None
            or parts.query or parts.fragment or parts.path not in ("", "/")
            or not re.fullmatch(r"[a-z0-9-]+\.(trycloudflare\.com|gradio\.live)", parts.netloc)):
        raise ValueError("Chỉ nhận link https trycloudflare.com/gradio.live không chứa auth/query/path.")
    return "https://" + parts.netloc


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # chỉ ghi status; không theo URL redirect có thể chứa thông tin riêng


def http_status(base, endpoint):
    """Không in response body/header/request hay gọi sinh ảnh."""
    try:
        opener = urllib.request.build_opener(_NoRedirect)
        request = urllib.request.Request(base.rstrip("/") + endpoint, headers={"User-Agent": "wai-readonly-ui-diagnostics"})
        with opener.open(request, timeout=6) as response:
            return {"http": response.status}
    except urllib.error.HTTPError as exc:
        code = exc.code
        exc.close()
        return {"http": code}
    except (OSError, ValueError) as exc:
        reason = getattr(exc, "reason", exc)
        kind = "network_unknown"
        if isinstance(reason, socket.gaierror):
            kind = "dns"
        elif isinstance(reason, ssl.SSLCertVerificationError):
            kind = "tls_certificate"
        elif isinstance(reason, ssl.SSLError):
            kind = "tls"
        elif isinstance(reason, (TimeoutError, socket.timeout)):
            kind = "timeout"
        elif isinstance(reason, ConnectionRefusedError):
            kind = "connection_refused"
        return {"loi": type(exc).__name__, "loai": kind}  # không dump URL/body/secret trong exception


def ui_transport(base):
    return {path: http_status(base, path) for path in ("/", "/config", "/info?all_endpoints=True")}


# Trang relay của gradio.live trả HTTP 200 nhưng nội dung là "No interface is running right now"
# (khi tunnel còn sống mà app local đã chết/chưa đăng ký). Vì status 200 nên phải đọc **phân
# loại** của trang, không thể chỉ nhìn mã HTTP. Không bao giờ in nội dung trang.
SHARE_DEAD_MARKERS = (
    "no interface is running right now",
    "no blocks has been configured for this app",
    "interface is not running",
)
GRADIO_MARKERS = (
    "<gradio-app",
    "window.gradio_config",
    'id="gradio"',
    "/gradio/",
    "gradio/api",
)

PAGE_HINTS = {
    "gradio_song": "Trang Gradio trả về bình thường.",
    "share_het": ("Relay còn sống nhưng app local đã chết hoặc chưa đăng ký với tunnel "
                  "(trang 'No interface is running right now'). Link này không dùng được nữa."),
    "html_khac": ("Trả HTML nhưng không phải Gradio — có thể là trang lỗi của proxy/tunnel "
                  "hoặc dịch vụ khác đang chiếm cổng."),
    "khong_phai_html": "Trả nội dung không phải HTML (JSON/text) — không phải trang giao diện.",
    "loi": "Không kết nối được để đọc trang.",
}


def page_kind(base, timeout=8):
    """Đọc `/` (tối đa 256 KiB) và phân loại trang: `gradio_song`, `share_het`, `html_khac`…

    Chỉ trả về mã HTTP + loại trang + gợi ý. Không trả body, header hay bất kỳ chuỗi nào
    của người dùng, nên an toàn để in trong log/chẩn đoán.
    """
    def result(kind, **extra):
        data = {"loai": kind, "goi_y": PAGE_HINTS.get(kind, "")}
        data.update(extra)
        return data

    try:
        opener = urllib.request.build_opener(_NoRedirect)
        request = urllib.request.Request(base.rstrip("/") + "/",
                                         headers={"User-Agent": "wai-readonly-ui-diagnostics"})
        with opener.open(request, timeout=timeout) as response:
            status = response.status
            raw = response.read(256 * 1024)
            content_type = (response.headers.get("Content-Type") or "").lower()
    except urllib.error.HTTPError as exc:
        code = exc.code
        exc.close()
        return result("loi", http=code)
    except (OSError, ValueError) as exc:
        reason = getattr(exc, "reason", exc)
        kind = "network_unknown"
        if isinstance(reason, socket.gaierror):
            kind = "dns"
        elif isinstance(reason, ssl.SSLCertVerificationError):
            kind = "tls_certificate"
        elif isinstance(reason, ssl.SSLError):
            kind = "tls"
        elif isinstance(reason, (TimeoutError, socket.timeout)):
            kind = "timeout"
        elif isinstance(reason, ConnectionRefusedError):
            kind = "connection_refused"
        return result("loi", http=0, loai_loi=kind)

    text = raw.decode("utf-8", errors="replace").lower()
    if any(marker in text for marker in SHARE_DEAD_MARKERS):
        return result("share_het", http=status)
    if any(marker in text for marker in GRADIO_MARKERS):
        return result("gradio_song", http=status)
    if "html" in content_type or text.lstrip().startswith("<"):
        return result("html_khac", http=status)
    return result("khong_phai_html", http=status)


def ui_verdict(local, public=None, port=7860):
    """Kết luận + việc cần làm dựa trên kết quả `page_kind`.

    `local`/`public` là dict của `page_kind` (hoặc None). Trả list dòng tiếng Việt.
    """
    lines = []
    local_kind = (local or {}).get("loai")
    public_kind = (public or {}).get("loai")

    if local_kind == "gradio_song":
        lines.append(f"✅ Forge local (`127.0.0.1:{port}`) đang chạy và trả trang Gradio bình thường.")
    elif local_kind == "share_het":
        lines.append("⚠️ Ngay cả link local cũng trả trang 'No interface is running right now' — "
                     "tiến trình Gradio chưa đăng ký giao diện (launch lỗi hoặc đang khởi động lại).")
    elif local_kind == "loi":
        detail = (local or {}).get("loai_loi") or (local or {}).get("http")
        lines.append(f"❌ Không mở được Forge local (`127.0.0.1:{port}`, {detail}). Forge chưa chạy "
                     "hoặc đã chết: `bash /content/install.sh --only launch,verify --restart`.")
    elif local_kind:
        lines.append(f"🟡 Link local trả `{local_kind}` — xem `--diagnostics` để biết chi tiết.")

    if public is None:
        return lines
    if public_kind == "gradio_song":
        lines.append("✅ Link public đang trỏ đúng giao diện.")
    elif public_kind == "share_het":
        lines.append("❌ **Link public đã chết** (đúng lỗi 'No interface is running right now'): "
                     "relay `gradio.live` còn sống nhưng app local đã khởi động lại hoặc đã chết, "
                     "nên tunnel không còn nối vào giao diện nào.")
        if local_kind == "gradio_song":
            lines.append("👉 Forge vẫn chạy: dùng `http://127.0.0.1:%d` (hoặc IP LAN) trong lúc này, "
                         "rồi tạo link mới bằng `bash /content/install.sh --only launch,verify --restart`."
                         % port)
            lines.append("   Mỗi lần restart, link `gradio.live` **đổi** — link cũ vĩnh viễn hỏng, "
                         "đừng lưu bookmark.")
        else:
            lines.append("👉 Chạy `bash /content/install.sh --only launch,verify --restart` rồi lấy "
                         "link mới trong output; nếu vẫn hỏng, đổi `TUNNEL=cloudflared`.")
    elif public_kind == "loi":
        lines.append("❌ Không mở được link public (mạng/DNS/tunnel). Xem `--diagnostics`; "
                     "thử `TUNNEL=cloudflared` nếu `gradio.live` bị chặn.")
    elif public_kind:
        lines.append(f"🟡 Link public trả `{public_kind}` — tunnel có thể đang trỏ sai dịch vụ.")
    return lines


def traceback_summary(path):
    """Đọc tối đa 256 KiB cuối log; chỉ xuất loại exception/stack, bỏ source/message."""
    path = Path(path)
    try:
        with path.open("rb") as stream:
            stream.seek(0, 2)
            stream.seek(max(0, stream.tell() - 256 * 1024))
            text = stream.read(256 * 1024).decode("utf-8", errors="replace")
    except OSError:
        return {"co_log": False, "tracebacks": []}
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)
    summaries = []
    for block in text.split("Traceback (most recent call last):")[1:][-6:]:
        frames = []
        for filename, line, function in re.findall(r'File "([^"\n]+)", line (\d+), in ([^\n]+)', block):
            frames.append({"file": "/".join(filename.replace("\\", "/").split("/")[-2:]),
                           "line": int(line), "function": function.strip()[:100]})
        error = re.search(r"^[ \t]*((?:[A-Za-z_][A-Za-z0-9_]*\.)*(?:[A-Za-z_][A-Za-z0-9_]*(?:Error|Exception)|Error|Exception)):(.*)$", block, re.MULTILINE)
        signature = "khong_xac_dinh_message_da_an"
        if error:
            message = error.group(2).lower()
            if "key backend" in message and "not a valid value for backend" in message:
                signature = "matplotlib_backend_invalid"
            elif "'bool'" in message and "not iterable" in message:
                signature = "schema_bool_not_iterable"
            elif "out of memory" in message:
                signature = "out_of_memory"
            elif "no kernel image" in message:
                signature = "cuda_kernel_image_missing"
            elif "no checkpoints found" in message or "no checkpoint found" in message:
                signature = "checkpoint_not_found"
            elif "port" in message and "string" in message:
                signature = "port_schema_type"
        summaries.append({"exception_type": error.group(1) if error else "chua_co_dong_exception_trong_tail",
                          "signature": signature, "frames": frames[-8:]})
    return {"co_log": True, "tracebacks": summaries,
            "luu_y": "Không in message/source/prompt/token. Lỗi frontend JavaScript có thể không nằm trong log này."}


def _backend_category(value):
    if value is None:
        return "khong_dat"
    if value.lower() == "agg":
        return "Agg"
    if value in ("module://matplotlib_inline.backend_inline", "module://ipykernel.pylab.backend_inline"):
        return "inline_notebook"
    return "backend_khac_da_an"


def process_graphics_env(forge, runtime):
    """Không dump environ/cmdline; chỉ phân loại MPLBACKEND của notebook và PID do bộ cài quản lý."""
    result = {"diagnostics_parent": _backend_category(os.environ.get("MPLBACKEND")),
              "forge_process": "chua_xac_nhan"}
    try:
        pid = (Path(runtime) / "forge.pid").read_text().strip()
        if not pid.isdecimal() or not 0 < int(pid) < 2**31:
            return result
        proc = Path("/proc") / pid
        command = (proc / "cmdline").read_bytes().split(b"\0")
        if str(Path(forge) / "launch.py").encode() not in command:
            return result  # không đọc môi trường process không phải Forge đang quản lý
        backend = None
        for item in (proc / "environ").read_bytes().split(b"\0"):
            key, _separator, value = item.partition(b"=")
            if key == b"MPLBACKEND":
                backend = value.decode(errors="replace")
                break
        result["forge_process"] = _backend_category(backend)
    except OSError:
        pass
    return result


def optional_assets(base):
    results = {"luu_y": "LoRA và textual inversion là tùy chọn; số lượng 0 không chứng minh WAI bị thiếu."}
    try:
        data = api_json(base, "/sdapi/v1/loras", timeout=6)
        results["loras"] = {"count": len(data)} if isinstance(data, list) else {"loi": "JSON sai kiểu"}
    except CheckpointError as exc:
        results["loras"] = {"loi": str(exc)}
    try:
        data = api_json(base, "/sdapi/v1/embeddings", timeout=6)
        if not isinstance(data, dict) or not all(isinstance(data.get(k), dict) for k in ("loaded", "skipped")):
            results["textual_inversion"] = {"loi": "JSON sai kiểu"}
        else:
            results["textual_inversion"] = {k + "_count": len(data[k]) for k in ("loaded", "skipped")}
    except CheckpointError as exc:
        results["textual_inversion"] = {"loi": str(exc)}
    return results


def collect(repo_dir, forge_dir, model_dir, model_file, state_dir, port, runtime_dir=None, public_url=""):

    public_url = validate_public_url(public_url)  # trước mọi I/O/network nếu CLI URL không hợp lệ
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
    try:
        from forge_compat import check as compat_check
        report["forge"]["compat_api_ui_v1"] = compat_check(forge)
    except (OSError, ValueError, ImportError) as exc:
        report["forge"]["compat_api_ui_v1"] = {"loi": str(exc)}
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
for name in ('torch','torchvision','gradio','gradio-client','pydantic','pydantic-core','fastapi','starlette','matplotlib','matplotlib-inline','pandas','safetensors','huggingface-hub'):
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
    try:
        api["checkpoint_ui_initial_config"] = checkpoint_ui_summary(api_json(base, "/config"))
    except CheckpointError as exc:
        api["checkpoint_ui_initial_config"] = {"loi": str(exc)}
    report["api"] = api
    report["ui_transport_local"] = ui_transport(base)
    # HTTP 200 chưa đủ: trang relay "No interface is running right now" cũng là 200.
    local_page = page_kind(base)
    report["ui_page_local"] = local_page
    public_page = None
    if public_url:
        report["ui_transport_public"] = ui_transport(public_url)
        public_page = page_kind(public_url)
        report["ui_page_public"] = public_page
    report["ket_luan_ui"] = ui_verdict(local_page, public_page, port)
    report["optional_assets"] = optional_assets(base)
    if runtime_dir is not None:
        report["graphics_env"] = process_graphics_env(forge, runtime_dir)
        report["forge_log_errors"] = traceback_summary(Path(runtime_dir) / "forge.log")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-dir", default="/content/ai-anime3")
    parser.add_argument("--forge-dir", default="/content/sd-webui-forge-neo")
    parser.add_argument("--model-dir", default="/content/models")
    parser.add_argument("--model-file", default="")
    parser.add_argument("--state-dir", default="/content/.wai_state")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--runtime-dir", default="/content", help="Thư mục chứa forge.log; chỉ lấy stack đã lọc")
    parser.add_argument("--public-url", default="", help="Tùy chọn: so sánh status tunnel với local; không in body/auth/prompt")
    parser.add_argument("--check-url", default="",
                        help="Chỉ phân loại trang của một URL (gradio sống / relay hết hạn / lỗi), in JSON; "
                             "mã thoát 0=Gradio sống, 3=relay báo 'No interface', 4=lỗi/khác")
    args = parser.parse_args()
    if args.check_url:
        try:
            target = validate_public_url(args.check_url)
        except ValueError:
            # Link local (127.0.0.1) không qua validate_public_url, dùng thẳng.
            target = args.check_url.rstrip("/")
        info = page_kind(target)
        print(json.dumps(info, ensure_ascii=False))
        return 0 if info.get("loai") == "gradio_song" else (
            3 if info.get("loai") == "share_het" else 4)
    try:
        public_url = validate_public_url(args.public_url)
    except ValueError as exc:
        parser.error(str(exc))
    report = collect(args.repo_dir, args.forge_dir, args.model_dir, args.model_file, args.state_dir, args.port,
                     runtime_dir=args.runtime_dir, public_url=public_url)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    for name in ("CIVITAI_TOKEN", "GITHUB_TOKEN", "HF_TOKEN", "FORGE_API_AUTH"):
        token = os.environ.get(name)
        if token:
            text = text.replace(token, "<redacted>")
    print(text)


if __name__ == "__main__":
    sys.exit(main() or 0)
