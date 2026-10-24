#!/usr/bin/env python3
"""Chẩn đoán Colab chỉ đọc: checkpoint, Forge/preset, API, venv và GPU.

Không tải model, mount Drive, khởi động server, ghi config/marker hay sinh ảnh.
Không in toàn bộ config, cmdline hoặc log (có thể chứa token/password/prompt riêng).
"""
from __future__ import annotations

import argparse
import ast
import base64
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import time
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


# --------------------------------------------------- transport Gradio (queue)
# "Connection errored out." là câu của @gradio/client (bundle 4.40.0), không phải Forge:
#   - `/queue/data` (SSE) trả HTTP khác 200, hoặc luồng SSE bị cắt  -> message này
#   - với app khai `protocol: "ws"`: WebSocket `/queue/join` đóng KHÔNG sạch -> message này
# Gradio 4 tự khai `protocol: "sse_v3"`, nên transport thật là **một kết nối SSE dài**;
# khi app có `gr.State`/unload, server bật `connect_heartbeat` → mỗi tab giữ kết nối đó
# mãi. Tunnel/proxy cắt kết nối rảnh = lỗi trên, dù process Forge vẫn khoẻ.
# Các hàm dưới chỉ mở kết nối, ghi mã/latency rồi đóng — không chạy function nào, không
# sinh ảnh, không in nội dung/header/config.
TRANSPORT_HINTS = {
    "on_dinh": "Kết nối queue mở được — transport bình thường.",
    "chi_sse": ("WebSocket bị chặn nhưng SSE còn chạy: Gradio lùi về SSE nên UI vẫn dùng "
                "được, chỉ dễ rớt khi mạng đổi. Dấu hiệu proxy/tunnel chặn WS."),
    "stream_treo": ("Mở được `/queue/data` nhưng không nhận được byte nào trong thời gian chờ: "
                    "tunnel/proxy đang giữ kết nối mà không chuyển dữ liệu (buffering)."),
    "queue_loi": ("`/queue/data` trả HTTP lỗi: tunnel/proxy chặn, hoặc Forge đã restart và "
                  "session cũ không còn — tải lại trang, vẫn lỗi thì restart để lấy link mới."),
    "tunnel_chan": ("Cả WebSocket lẫn SSE đều không mở được: tunnel/proxy đang cắt kết nối "
                    "dài — đổi tunnel hoặc restart để lấy link mới."),
    "khong_ket_noi": "Không kết nối được tới host — mạng/DNS/tunnel, không phải Forge.",
    "khong_ro": "Không kết luận được, xem mã lỗi ở trên.",
}


def _split_base(base):
    parts = urlsplit(base if "://" in base else "http://" + str(base))
    scheme = (parts.scheme or "http").lower()
    host = parts.hostname
    if not host:
        raise ValueError("URL không có host")
    return scheme, host, parts.port or (443 if scheme == "https" else 80), (parts.path or "").rstrip("/")


def _net_kind(exc):
    reason = getattr(exc, "reason", exc)
    if isinstance(reason, socket.gaierror):
        return "dns"
    if isinstance(reason, ssl.SSLCertVerificationError):
        return "tls_certificate"
    if isinstance(reason, ssl.SSLError):
        return "tls"
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return "timeout"
    if isinstance(reason, ConnectionRefusedError):
        return "connection_refused"
    if isinstance(reason, ConnectionResetError):
        return "connection_reset"
    return "network_unknown"


def ui_protocol(base, timeout=8):
    """Đọc 2 khoá transport từ `/config` (không in toàn bộ config)."""
    try:
        data = api_json(base, "/config", timeout=timeout)
    except CheckpointError as exc:
        return {"loi": str(exc)}
    if not isinstance(data, dict):
        return {"loi": "config không phải JSON object"}
    return {"protocol": data.get("protocol") or "?",
            "connect_heartbeat": bool(data.get("connect_heartbeat")),
            "co_state": any(c.get("type") == "state" for c in data.get("components") or [])}


def websocket_probe(base, timeout=8):
    """Thử nâng cấp WebSocket tới `<base>/queue/join`; `{"http": 101}` là thông."""
    try:
        scheme, host, port, prefix = _split_base(base)
    except ValueError as exc:
        return {"http": 0, "loai": "url", "chi_tiet": str(exc)[:60]}
    key = base64.b64encode(os.urandom(16)).decode()
    request = "\r\n".join([
        f"GET {prefix}/queue/join?session_hash={os.urandom(16).hex()} HTTP/1.1",
        f"Host: {host}", "Upgrade: websocket", "Connection: Upgrade",
        f"Sec-WebSocket-Key: {key}", "Sec-WebSocket-Version: 13",
        f"Origin: {scheme}://{host}", "", ""]).encode()
    started = time.monotonic()
    raw = None
    try:
        raw = socket.create_connection((host, port), timeout=timeout)
        if scheme == "https":
            raw = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
        raw.sendall(request)
        head = raw.recv(128).split(b"\r\n", 1)[0].decode(errors="replace")
    except (OSError, ValueError) as exc:
        return {"http": 0, "loai": _net_kind(exc), "chi_tiet": type(exc).__name__}
    finally:
        if raw is not None:
            try:
                raw.close()
            except OSError:
                pass
    parts = head.split()
    try:
        code = int(parts[1])
    except (IndexError, ValueError):
        return {"http": 0, "loai": "phan_hoi_la", "chi_tiet": head[:40]}
    return {"http": code, "ms": int((time.monotonic() - started) * 1000)}


def sse_probe(base, timeout=8):
    """Mở `/queue/data` như trình duyệt, ghi có nhận byte đầu hay không (không in nội dung)."""
    url = base.rstrip("/") + "/queue/data?session_hash=" + os.urandom(16).hex()
    opener = urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(url, headers={"Accept": "text/event-stream",
                                                   "User-Agent": "wai-readonly-transport-probe"})
    started = time.monotonic()
    response = None
    try:
        response = opener.open(request, timeout=timeout)
        status = response.status
        try:
            first = response.readline()
        except (TimeoutError, socket.timeout):
            return {"http": status, "su_kien_dau": False, "loai": "timeout_doc",
                    "ms": int((time.monotonic() - started) * 1000)}
        return {"http": status, "su_kien_dau": bool(first),
                "ms": int((time.monotonic() - started) * 1000)}
    except urllib.error.HTTPError as exc:
        code = exc.code
        exc.close()
        return {"http": code, "su_kien_dau": False}
    except (OSError, ValueError) as exc:
        return {"http": 0, "su_kien_dau": False, "loai": _net_kind(exc),
                "chi_tiet": type(exc).__name__}
    finally:
        if response is not None:
            try:
                response.close()
            except OSError:
                pass


def transport_probe(base, timeout=8):
    """Đo transport mà app thực sự dùng (SSE với Gradio 4, WS nếu config khai ws)."""
    info = ui_protocol(base, timeout=timeout)
    protocol = str(info.get("protocol") or "?")
    result = {"protocol": protocol, "connect_heartbeat": info.get("connect_heartbeat"), "sse": None}
    if protocol.startswith("sse"):
        result["websocket"] = {"bo_qua": "app khai protocol sse — không dùng WebSocket"}
        result["sse"] = sse_probe(base, timeout=timeout)
        sse = result["sse"]
        if sse.get("su_kien_dau"):
            kind = "on_dinh"
        elif sse.get("http") and sse["http"] != 200:
            kind = "queue_loi"
        elif sse.get("http") == 200:
            kind = "stream_treo"
        elif sse.get("loai") in ("dns", "timeout", "connection_refused", "tls",
                                 "tls_certificate", "connection_reset", "network_unknown"):
            kind = "khong_ket_noi"
        else:
            kind = "khong_ro"
    else:
        result["websocket"] = websocket_probe(base, timeout=timeout)
        result["sse"] = sse_probe(base, timeout=timeout)
        ws, sse = result["websocket"], result["sse"]
        if ws.get("http") == 101:
            kind = "on_dinh"
        elif sse.get("su_kien_dau"):
            kind = "chi_sse"
        elif ws.get("http") or sse.get("http"):
            kind = "tunnel_chan"
        elif ws.get("loai") in ("dns", "timeout", "connection_refused", "tls",
                                "tls_certificate", "connection_reset", "network_unknown"):
            kind = "khong_ket_noi"
        else:
            kind = "khong_ro"
    result["ket_luan"] = kind
    result["goi_y"] = TRANSPORT_HINTS[kind]
    if result.get("connect_heartbeat"):
        result["goi_y"] += (" App có `gr.State` nên mỗi tab giữ một kết nối SSE thường trực; "
                            "đóng bớt tab và tránh để tab ngủ.")
    return result


# ------------------------------------------------------- CPU khi không sinh ảnh
# Trong repo không có vòng lặp nền: không `while True`, không `setInterval`, không
# `gr.Timer`, không thread thường trú (`GenerationJob` chỉ sống trong lúc sinh ảnh).
# Vì vậy CPU cao khi rảnh đến từ process/thread khác — phải đo mới biết. Các hàm dưới
# chỉ ĐỌC `/proc` và `/proc/net/tcp`, không ptrace, không cần quyền root, không in
# cmdline/environ (có thể chứa token).
TUNNEL_MARKERS = ("frpc", "cloudflared")


def _stat_ticks(stat_path):
    """Đọc `(ppid, tên, utime+stime)` từ một file stat của /proc; None nếu không đọc được."""
    try:
        raw = Path(stat_path).read_text(errors="replace")
    except OSError:
        return None
    head, sep, tail = raw.rpartition(")")   # tên process có thể chứa khoảng trắng/ngoặc
    if not sep:
        return None
    name = head[head.find("(") + 1:]
    fields = tail.split()
    try:
        # Sau comm: state(0) ppid(1) … utime(11) stime(12)
        return {"ppid": int(fields[1]), "name": name,
                "ticks": int(fields[11]) + int(fields[12])}
    except (IndexError, ValueError):
        return None


def _cpu_tree(proc_root="/proc", root_pid=None):
    """Chụp tick CPU của process trong cây `root_pid` và các thread của chính nó."""
    processes, threads = {}, {}
    try:
        pids = [entry.name for entry in Path(proc_root).iterdir() if entry.name.isdigit()]
    except OSError:
        return {"processes": processes, "threads": threads}
    for pid in pids:
        info = _stat_ticks(Path(proc_root) / pid / "stat")
        if info:
            info["pid"] = int(pid)
            processes[int(pid)] = info
    keep = set()
    if root_pid in processes:
        keep.add(root_pid)
        growing = True
        while growing:
            growing = False
            for pid, info in processes.items():
                if pid not in keep and info["ppid"] in keep:
                    keep.add(pid)
                    growing = True
        # Lấy thread của MỌI process trong cây: forge.pid có thể là shell bọc python.
        for pid in keep:
            try:
                for task in (Path(proc_root) / str(pid) / "task").iterdir():
                    if not task.name.isdigit():
                        continue
                    info = _stat_ticks(task / "stat")
                    if info:
                        threads[info["name"] + f"#{task.name}"] = info["ticks"]
            except OSError:
                continue
    processes = {pid: info for pid, info in processes.items() if pid in keep}
    return {"processes": processes, "threads": threads}


def ui_clients(port, tcp_files=None):
    """Số kết nối ESTABLISHED vào cổng UI: mỗi tab Gradio đang mở là một client poll."""
    total = 0
    wanted = f":{int(port):04X}"
    for name in (tcp_files or ("/proc/net/tcp", "/proc/net/tcp6")):
        try:
            lines = Path(name).read_text(errors="replace").splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            fields = line.split()
            if len(fields) > 3 and fields[1].endswith(wanted) and fields[3] == "01":
                total += 1
    return total


def _mem_available(meminfo="/proc/meminfo"):
    """(MB còn lại, MB tổng) từ /proc/meminfo; (None, None) nếu không đọc được."""
    try:
        rows = Path(meminfo).read_text(errors="replace").splitlines()
    except OSError:
        return None, None
    values = {}
    for row in rows:
        key, _sep, rest = row.partition(":")
        if rest.strip().endswith("kB"):
            try:
                values[key] = int(rest.split()[0])
            except (IndexError, ValueError):
                continue
    total, available = values.get("MemTotal"), values.get("MemAvailable")
    if total is None or available is None:
        return None, None
    return round(available / 1024), round(total / 1024)


def _reclaim_pages(vmstat="/proc/vmstat"):
    """Tổng số trang kernel đã quét/thu hồi (pgscan_*/pgsteal_*). Tăng đều = đang thiếu RAM."""
    total = 0
    try:
        rows = Path(vmstat).read_text(errors="replace").splitlines()
    except OSError:
        return None
    for row in rows:
        key, _sep, value = row.partition(" ")
        if key.startswith(("pgscan_", "pgsteal_")):
            try:
                total += int(value)
            except ValueError:
                continue
    return total


def cpu_report(root_pid, port=None, seconds=5.0, proc_root="/proc", sleep=None, tcp_files=None,
               meminfo="/proc/meminfo", vmstat="/proc/vmstat"):
    """Đo CPU cây process Forge trong `seconds` giây và nói ngay nghi phạm nào.

    `processes`/`threads` chỉ có tên process/thread (không cmdline), an toàn để dán log.
    """
    sleep = sleep or time.sleep
    root_pid = int(root_pid)
    first = _cpu_tree(proc_root, root_pid)
    first_reclaim = _reclaim_pages(vmstat)
    if not first["processes"]:
        return {"loi": f"không đọc được /proc cho PID {root_pid}",
                "goi_y": "Forge chưa chạy hoặc PID trong forge.pid đã cũ; chạy "
                         "`bash /content/install.sh --status` trước."}
    sleep(seconds)
    second = _cpu_tree(proc_root, root_pid)
    second_reclaim = _reclaim_pages(vmstat)
    available_mb, total_mb = _mem_available(meminfo)
    reclaim = None
    if first_reclaim is not None and second_reclaim is not None:
        reclaim = round(max(0, second_reclaim - first_reclaim) / max(seconds, 0.001))
    try:
        hz = os.sysconf("SC_CLK_TCK") or 100
    except (ValueError, OSError):
        hz = 100

    def percent(old, new):
        return round(max(0, new - old) / hz / seconds * 100, 1)

    processes = []
    for pid, info in first["processes"].items():
        after = second["processes"].get(pid)
        processes.append({"ten": info["name"], "pid": pid,
                          "cpu": percent(info["ticks"], after["ticks"] if after else info["ticks"])})
    processes.sort(key=lambda row: row["cpu"], reverse=True)
    threads = [{"ten": name, "cpu": percent(ticks, second["threads"].get(name, ticks))}
               for name, ticks in first["threads"].items()]
    threads.sort(key=lambda row: row["cpu"], reverse=True)
    total = round(sum(row["cpu"] for row in processes), 1)
    clients = ui_clients(port, tcp_files=tcp_files) if port else 0

    tunnel = max([row["cpu"] for row in processes
                  if any(marker in row["ten"] for marker in TUNNEL_MARKERS)] or [0.0])
    top_thread = threads[0] if threads else {"ten": "", "cpu": 0.0}
    low_ram = available_mb is not None and total_mb and available_mb < total_mb * 0.05
    heavy_reclaim = reclaim is not None and reclaim >= 2000
    if total < 5:
        verdict = "thap"
        advice = ("CPU cây Forge rất thấp khi không sinh ảnh — không phải Forge quay vòng. "
                  "Nếu Colab vẫn báo cao, nghi phạm nằm ngoài Forge: jupyter/colab agent, "
                  "`nvidia-smi`, hoặc process khác. Xem: ps -eo pid,pcpu,etime,args --sort=-pcpu | head")
    elif low_ram or heavy_reclaim:
        verdict = "thieu_ram"
        detail = []
        if available_mb is not None:
            detail.append(f"còn {available_mb} MB / {total_mb} MB")
        if reclaim is not None:
            detail.append(f"kernel thu hồi {reclaim:,} trang/giây")
        advice = (("RAM cạn (" + ", ".join(detail) + "): kernel quét/thu hồi bộ nhớ liên tục nên "
                   "CPU tăng dần dù không sinh ảnh. ") if detail else "") + \
                  ("Đóng bớt tab Forge, bấm **Làm mới** ở album rồi đóng bảng ảnh, tránh mở "
                   "nhiều app Gradio cùng lúc; chụp lại ảnh cần giữ rồi restart runtime để "
                   "giải phóng RAM. Không tải lại model.")
    elif tunnel >= 15:
        verdict = "tunnel"
        advice = ("Tunnel (frpc/cloudflared) đang tốn CPU. Restart tunnel hoặc đổi "
                  "`--tunnel share` ↔ `cloudflared`; link share cũ cũng cần bỏ.")
    elif clients >= 4:
        verdict = "nhieu_client"
        advice = (f"Có {clients} kết nối UI đang mở; mỗi tab Gradio liên tục poll "
                  "/queue/status + websocket và giữ toàn bộ component trong RAM. "
                  "Đóng bớt tab/điện thoại rồi đo lại.")
    elif top_thread["cpu"] >= 25:
        verdict = "thread_python_cao"
        advice = (f"Thread `{top_thread['ten']}` chiếm {top_thread['cpu']}% — cần stack để biết "
                  f"hàm nào: pip install py-spy && py-spy dump --pid {root_pid} "
                  "(hoặc `py-spy top --pid`), rồi chỉ dán phần Python frame.")
    else:
        verdict = "cao_khac"
        advice = ("CPU rải đều ở nhiều thread/process — nhiều khả năng do tải dựng UI "
                  "(506 tag phong cách + bảng 506 dòng) hoặc nhịp poll của Gradio; "
                  "xem thêm `ps -eLf --sort=-pcpu | head` và Chrome Task Manager (Shift+Esc).")
    return {"thoi_giay": seconds, "pid_goc": root_pid, "tong_cpu": total,
            "client_ui": clients, "ram_con_lai_mb": available_mb, "ram_tong_mb": total_mb,
            "thu_hoi_trang_giay": reclaim, "processes": processes[:8], "threads": threads[:5],
            "ket_luan": verdict, "goi_y": advice}


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
    parser.add_argument("--check-queue", default="", metavar="URL",
                        help="Đo transport Gradio của một URL (SSE /queue/data, hoặc WebSocket "
                             "/queue/join nếu app khai protocol ws); dùng khi UI báo "
                             "'Connection errored out.'")
    parser.add_argument("--cpu", action="store_true",
                        help="Đo CPU cây process Forge khi đang rảnh (chỉ đọc /proc, không ptrace)")
    parser.add_argument("--cpu-seconds", type=float, default=5.0,
                        help="Số giây lấy mẫu cho --cpu (mặc định 5)")
    parser.add_argument("--check-url", default="",
                        help="Chỉ phân loại trang của một URL (gradio sống / relay hết hạn / lỗi), in JSON; "
                             "mã thoát 0=Gradio sống, 3=relay báo 'No interface', 4=lỗi/khác")
    args = parser.parse_args()
    if args.check_queue:
        try:
            target = validate_public_url(args.check_queue)
        except ValueError:
            target = args.check_queue.rstrip("/")     # link local 127.0.0.1 dùng thẳng
        print(json.dumps(transport_probe(target), ensure_ascii=False, indent=2))
        return 0
    if args.cpu:
        try:
            pid = (Path(args.runtime_dir) / "forge.pid").read_text().strip()
            if not pid.isdecimal():
                raise ValueError
        except (OSError, ValueError):
            print(json.dumps({"loi": f"không thấy PID Forge trong {args.runtime_dir}/forge.pid",
                              "goi_y": "Chạy `bash /content/install.sh --status` để biết Forge có chạy."},
                             ensure_ascii=False))
            return 2
        print(json.dumps(cpu_report(pid, port=args.port, seconds=max(1.0, args.cpu_seconds)),
                         ensure_ascii=False, indent=2))
        return 0
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
