#!/usr/bin/env python3
"""Kiểm tra bộ cài không cần mạng/GPU: python3 colab/tests/test_install_sh.py.

CLI + metadata API bằng fixture + vòng đời cài/resume bằng stage stub. Riêng
stage model chạy script thật với checkpoint safetensors nhỏ trên HTTP server
cục bộ trong cùng tiến trình test; server và thư mục tạm được dọn ở cuối.
Không clone/cài Forge/PyTorch thật và không sửa checkout hiện tại.
Để chạy cùng guard upstream thật đã tải về (AST, không import torch):
FORGE_VERSION_GUARD_SOURCE=/path/modules/launch_utils.py python3 colab/tests/test_install_sh.py
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTALL = ROOT / "colab/install.sh"
SETUP = ROOT / "colab/setup_forge.sh"
PASS, FAIL = [], []
SHA_FP16 = "f116b0c78ff441467b0cdc8f1936e1ed18ea31e9997c7b132b1b8db533f0bd04"


def check(label, condition, detail=""):
    (PASS if condition else FAIL).append(label)
    print(f"  {'✔' if condition else '✘'} {label}")
    if not condition:
        print("    ", detail)


def cli(args, env=None, script=INSTALL, timeout=30):
    return subprocess.run(["bash", str(script), *args], cwd=ROOT, env={**os.environ, **(env or {})},
                          text=True, capture_output=True, timeout=timeout)


def source_call(script, command, env=None):
    return subprocess.run(["bash", "-c", 'source "$1"; shift; ' + command, "test", str(script)],
                          cwd=ROOT, env={**os.environ, **(env or {})}, text=True,
                          capture_output=True, timeout=30)


def compat_fixture(forge):
    import sys
    sys.path.insert(0, str(ROOT / "colab"))
    import forge_compat
    for relative, _marker, old, _new in forge_compat.PATCHES:
        path = forge / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        prefix = "def flags_fixture():\n    for key in _options:\n" if relative.endswith("models.py") else "def make_checkpoint_manager_ui():\n"
        path.write_text(prefix + old + "\n")


def executable(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def extract_py(script, function):
    lines = script.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(function + "()"))
    begin = next(i for i in range(start, len(lines)) if "<<'PYEOF'" in lines[i])
    end = next(i for i in range(begin + 1, len(lines)) if lines[i] == "PYEOF")
    return "\n".join(lines[begin + 1:end])


def file(name, sha, primary=True, file_id=1, url=None):
    return {"id": file_id, "name": name, "sizeKB": 4167000.0,
            "hashes": {"SHA256": sha}, "metadata": {"format": "SafeTensor", "fp": "fp8"},
            "primary": primary, "downloadUrl": url or "https://civitai.com/api/download/models/123"}


FIXTURES = {
    "2451718": {"modelVersions": [{"id": 123, "name": "WAI-V17-MIX", "files": [
        file("waiIllustriousSDXL_v170_fp8_e4m3.safetensors", "f" * 64, False, 9002),
        file("waiIllustriousSDXL_v170_int8_convrot.safetensors", "a" * 64),
    ]}]},
    "2698106": {"modelVersions": [{"id": 234, "name": "v17.0 base", "files": [
        file("waiIllustriousSDXL_v170_hswq_r32_turbo.safetensors", "b" * 64,
             url="https://civitai.com/api/download/models/234?fileId=9101"),
    ]}]},
    "827184": {"modelVersions": [{"id": 2883731, "name": "v17.0", "files": [
        file("waiIllustriousSDXL_v170.safetensors", SHA_FP16),
    ]}]},
    "empty": {"modelVersions": []},
    "renamed": {"modelVersions": [{"id": 789, "name": "v18", "files": [
        file("waiIllustriousSDXL_v180_fp8_e4m3.safetensors", "c" * 64),
    ]}]},
    "nohash": {"modelVersions": [{"id": 111, "files": [file("x.safetensors", "")]}]},
}
HTTP_MODE = 200
REQUESTS = []


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def fake_urlopen(req, timeout=None):
    REQUESTS.append(req)
    if HTTP_MODE != 200:
        raise urllib.error.HTTPError(req.full_url, HTTP_MODE, "fixture", {}, None)
    key = req.full_url.rsplit("/", 1)[-1]
    return Response(json.dumps(FIXTURES[key]).encode())


def embedded(code, argv, env=None, opener=fake_urlopen):
    old_argv, old_out, old_err = sys.argv, sys.stdout, sys.stderr
    old_env = dict(os.environ)
    old_urlopen = urllib.request.urlopen
    out, err = io.StringIO(), io.StringIO()
    sys.argv, sys.stdout, sys.stderr = argv, out, err
    os.environ.update(env or {})
    urllib.request.urlopen = opener
    rc = 0
    try:
        exec(compile(code, "<installer embedded>", "exec"), {"__name__": "__main__"})
    except SystemExit as exc:
        rc = int(exc.code or 0)
    finally:
        sys.argv, sys.stdout, sys.stderr = old_argv, old_out, old_err
        os.environ.clear()
        os.environ.update(old_env)
        urllib.request.urlopen = old_urlopen
    return rc, out.getvalue(), err.getvalue()


def test_cli():
    print("1) CLI và validation (không cài gì)")
    for script in (INSTALL, SETUP):
        r = subprocess.run(["bash", "-n", str(script)], capture_output=True)
        check(f"{script.name}: cú pháp hợp lệ", r.returncode == 0, r.stderr)
    check("install.sh có quyền thực thi", os.access(INSTALL, os.X_OK))
    check("--version", cli(["--version"]).stdout.strip() == "install.sh 1.0.6")
    r = cli(["--help"])
    check("--help có chọn model và chẩn đoán", r.returncode == 0 and all(x in r.stdout for x in
          ("fp16", "fp8", "int8", "hswq", "--doctor", "--only", "--no-launch")))
    check("Danh sách stage đúng thứ tự", cli(["--list-stages"]).stdout.split() ==
          ["preflight", "repo", "forge", "torch", "model", "extras", "launch", "verify"])
    for args in (["--unknown"], ["--model"], ["--only"], ["--model", "--no-launch"],
                 ["--model", "gguf"], ["--only", "bogus"], ["--tunnel", "bad"],
                 ["--port", "99999"], ["--port", "x"], ["--cuda", "cu999"],
                 ["--model-file", "../model.safetensors"], ["--model-sha", "wrong"]):
        r = cli(args, timeout=5)
        check(f"Từ chối input sai: {' '.join(args)}", r.returncode == 2, r.stdout + r.stderr)
    r = cli(["--print-models"])
    check("Catalog liệt kê 4 bản v17 (không gọi mạng)", r.returncode == 0 and all(x in r.stdout for x in
          ("fp16", "fp8", "int8", "hswq", "v170", "sm75")))
    check("Catalog cảnh báo tham số HSWQ khác", "CFG 1.0" in r.stdout)


def test_tunnel_defaults(tmp):
    print("1b) Tunnel mặc định, ưu tiên cấu hình và cờ launch (offline)")
    state = tmp / "tunnel-settings"
    state.mkdir()
    settings = state / "settings.json"
    env = {k: v for k, v in os.environ.items() if k != "TUNNEL"}
    env.update(STATE_DIR=str(state), PY=sys.executable)

    def inspect(args=(), given=None, save=False):
        command = ('source "$1"; shift; load_saved_settings; parse_args "$@"; '
                   + ('save_settings; ' if save else '')
                   + 'printf "%s\\n" "$TUNNEL"')
        return subprocess.run(["bash", "-c", command, "test", str(INSTALL), *args],
                              cwd=ROOT, env={**env, **(given or {})},
                              capture_output=True, text=True, timeout=10)

    result = inspect()
    check("Cài mới không có config/env/cờ → Gradio share", result.returncode == 0 and result.stdout.strip() == "share", result.stderr)
    for tunnel in ("cloudflared", "share", "none"):
        settings.write_text(json.dumps({"TUNNEL": tunnel, "MODEL_ID": "fp16"}))
        before = settings.read_bytes()
        result = inspect()
        check(f"Giữ tunnel đã lưu: {tunnel} (không sửa settings)",
              result.returncode == 0 and result.stdout.strip() == tunnel and settings.read_bytes() == before,
              result.stdout + result.stderr)
    settings.write_text(json.dumps({"TUNNEL": "cloudflared"}))
    result = inspect(given={"TUNNEL": "share"})
    check("Environment share thắng Cloudflare đã lưu", result.returncode == 0 and result.stdout.strip() == "share", result.stderr)
    for tunnel in ("share", "cloudflared", "none"):
        result = inspect(("--tunnel", tunnel), given={"TUNNEL": "none" if tunnel != "none" else "share"})
        check(f"Cờ --tunnel {tunnel} thắng environment/config", result.returncode == 0 and result.stdout.strip() == tunnel, result.stderr)
    result = inspect(("--tunnel", "share"), save=True)
    saved = json.loads(settings.read_text())
    resumed = inspect()
    check("Đổi sang share được nhớ cho lần launch tiếp theo",
          result.returncode == 0 and saved["TUNNEL"] == "share" and resumed.stdout.strip() == "share",
          result.stdout + result.stderr)

    for tunnel in ("share", "cloudflared", "none"):
        result = source_call(SETUP, 'launch_args', {"TUNNEL": tunnel, "PY": sys.executable})
        args = result.stdout.strip().split()
        check(f"Neo launch {tunnel}: --share chỉ có khi chọn share",
              result.returncode == 0 and ("--share" in args) == (tunnel == "share"), result.stderr)
    result = source_call(SETUP, 'fetch() { return 99; }; start_cloudflared', {"TUNNEL": "share"})
    check("Gradio share không tải/chạy Cloudflare", result.returncode == 0 and not result.stdout, result.stderr)


def test_metadata():
    global HTTP_MODE
    print("2) Metadata Civitai/HuggingFace bằng fixture")
    script = INSTALL.read_text()
    code = extract_py(script, "civitai_resolve")
    rc, out, err = embedded(code, ["resolve", "2451718", "waiIllustriousSDXL_v170_fp8_e4m3.safetensors"])
    fields = out.strip("\n").split("\x1f")
    check("FP8: resolve đúng file, đủ 6 trường", rc == 0 and len(fields) == 6, err)
    if len(fields) == 6:
        check("File không primary → chọn đúng fileId", fields[0].endswith("fileId=9002"), fields)
        check("SHA256 từ API", fields[1] == "f" * 64, fields)
        check("sizeKB quy đổi đúng sang bytes", fields[2] == str(int(4167000.0 * 1024)), fields)
        check("VersionId được giữ", fields[5] == "123", fields)
    rc, out, _ = embedded(code, ["resolve", "2451718", "waiIllustriousSDXL_v170_int8_convrot.safetensors"])
    check("INT8 primary không nối fileId khác", rc == 0 and "fileId=" not in out)
    rc, out, _ = embedded(code, ["resolve", "2698106", "waiIllustriousSDXL_v170_hswq_r32_turbo.safetensors"])
    check("HSWQ URL có fileId không nối trùng", rc == 0 and out.count("fileId=") == 1)
    rc, out, _ = embedded(code, ["resolve", "827184", "waiIllustriousSDXL_v170.safetensors"])
    check("FP16 khớp hash/phiên bản v17 đã biết", rc == 0 and SHA_FP16 in out and "2883731" in out)
    rc, _, err = embedded(code, ["resolve", "empty", "x.safetensors"])
    check("API rỗng → báo cần quyền/token, không đoán", rc == 5 and "NSFW" in err)
    for status in (401, 403):
        HTTP_MODE = status
        rc, _, err = embedded(code, ["resolve", "827184", "waiIllustriousSDXL_v170.safetensors"])
        check(f"HTTP {status}: gợi ý CIVITAI_TOKEN", rc == 3 and "CIVITAI_TOKEN" in err)
    HTTP_MODE = 200
    rc, _, err = embedded(code, ["resolve", "renamed", "waiIllustriousSDXL_v170_fp8_e4m3.safetensors"])
    check("Tên v17 biến mất → KHÔNG tự lấy v18 dù cùng precision", rc == 6 and "Không tự" in err)
    rc, _, _ = embedded(code, ["resolve", "nohash", "x.safetensors"])
    check("Không có hash → không coi là file đã xác minh", rc == 7)
    embedded(code, ["resolve", "827184", "waiIllustriousSDXL_v170.safetensors"],
             env={"CIVITAI_TOKEN": "fixture-only-token"})
    check("Credential được gửi bằng Authorization (không URL)",
          REQUESTS[-1].get_header("Authorization") == "Bearer fixture-only-token" and
          "fixture-only-token" not in REQUESTS[-1].full_url)

    hf = extract_py(script, "hf_lfs_sha256")
    seen = []
    def pointer(req, timeout=None):
        seen.append(req.full_url if hasattr(req, "full_url") else str(req))
        return Response(f"version https://git-lfs.github.com/spec/v1\noid sha256:{SHA_FP16}\nsize 6938812416\n".encode())
    rc, out, _ = embedded(hf, ["hf", "https://huggingface.co/a/b/resolve/main/x.safetensors"], opener=pointer)
    check("HF pointer dùng /raw/ thay vì tải file /resolve/", bool(seen) and "/raw/" in seen[0])
    check("HF đọc đúng SHA256 từ pointer LFS", rc == 0 and out.strip() == SHA_FP16)


# Một safetensors nhỏ (1 tensor F32) để test downloader/checksum mà không tải 7 GB.
HEADER = json.dumps({"fixture": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]}},
                    separators=(",", ":")).encode()
HEADER += b" " * (-len(HEADER) % 8)
DATA = struct.pack("<Q", len(HEADER)) + HEADER + struct.pack("<f", 1)
SHA = hashlib.sha256(DATA).hexdigest()


def test_model_and_torch(tmp):
    print("3) Stage model/Torch thật, downloader/venv giả lập")
    env = {"MODEL_DIR": str(tmp / "model"), "MODEL_FILE": "fixture.safetensors",
           "MODEL_SHA256": SHA, "MODEL_MIN_BYTES": "1", "MODEL_URL": "https://fixture.invalid/model",
           "WAI_RUNTIME_DIR": str(tmp), "FORGE_DIR": str(tmp / "forge")}
    part = tmp / "model/fixture.safetensors.part"
    dest = tmp / "model/fixture.safetensors"
    partial_code = "fetch() { printf 'partial' > \"$2\"; return 22; }; stage_model"
    r = source_call(SETUP, partial_code, env)
    check("Tải lỗi: trả nonzero", r.returncode != 0, r.stdout + r.stderr)
    check("Giữ .part khi rớt mạng, không tạo checkpoint dở", part.exists() and not dest.exists())
    data_file = tmp / "data.bin"
    data_file.write_bytes(DATA)
    r = source_call(SETUP, 'fetch() { cp "$FIXTURE_DATA" "$2"; }; stage_model',
                    {**env, "FIXTURE_DATA": str(data_file)})
    check("Chạy lại: xác minh hash rồi đổi tên nguyên tử", r.returncode == 0 and dest.read_bytes() == DATA and not part.exists(), r.stdout + r.stderr)
    r = source_call(SETUP, 'fetch() { exit 88; }; stage_model', env)
    check("Model đã có đúng SHA → không tải lại", r.returncode == 0, r.stdout + r.stderr)
    r = source_call(SETUP, 'fetch() { printf bad > "$2"; }; stage_model',
                    {**env, "MODEL_FILE": "bad.safetensors"})
    check("Tải xong sai SHA → báo lỗi, không nhận file hỏng", r.returncode != 0 and not (tmp / "model/bad.safetensors").exists())
    r = source_call(SETUP, 'stage_model', {**env, "MODEL_SHA256": ""})
    check("SHA rỗng không bị thay bằng hash FP16; bị từ chối", r.returncode != 0 and "Thiếu SHA256" in r.stderr)
    r = source_call(SETUP, 'launch_args', {**env, "MODEL_DIR": str(tmp / "models with spaces"), "TUNNEL": "none"})
    import shlex
    args = shlex.split(r.stdout)
    check("Forge nhận --ckpt-dirs kể cả path có dấu cách", r.returncode == 0 and
          args[args.index("--ckpt-dirs") + 1] == str(tmp / "models with spaces"), r.stdout)
    check("Forge bind --listen + API, không dùng cờ medvram cũ", "--listen" in args and "--api" in args and "--medvram" not in args)

    # Wheel giả lập: cu130 cài được, is_available có thể True nhưng kernel vẫn hỏng.
    state, trace = tmp / "torch-index", tmp / "torch-trace"
    executable(tmp / "forge/venv/bin/python", '''#!/usr/bin/env bash
if [[ "$1" == -m ]]; then
  echo "$*" >> "$TORCH_TRACE"
  last="${!#}"; echo "${last##*/}" > "$TORCH_STATE"
  exit 0
fi
[[ -f "$TORCH_STATE" ]] || exit 1
[[ "$(cat "$TORCH_STATE")" != cu130 ]]
''')
    e = {**env, "TORCH_INDEX": "cu130", "TORCH_STATE": str(state), "TORCH_TRACE": str(trace)}
    r = source_call(SETUP, 'stage_torch', e)
    text = trace.read_text() if trace.exists() else ""
    check("CUDA kernel cu130 lỗi → thực sự hạ về cu128", r.returncode == 0 and state.read_text().strip() == "cu128", r.stdout + r.stderr)
    check("Downgrade có --force-reinstall để pip không giữ bản mới hỏng", text.count("--force-reinstall") == 2, text)
    check("Torch env được lưu đúng trong runtime dir", (tmp / ".wai_torch_env").exists() and "TORCH_INDEX=cu128" in (tmp / ".wai_torch_env").read_text())
    state.unlink(); trace.unlink()
    r = source_call(SETUP, 'stage_torch', {**e, "TORCH_INDEX": "cu126"})
    check("--cuda cu126 thắng giá trị cu128 đã lưu", r.returncode == 0 and "cu126" in trace.read_text() and "cu128" not in trace.read_text())


def test_config_version(tmp):
    print("4) Forge VERSION_UID / prepare_launch không tương tác")
    forge = tmp / "version-guard/forge"
    runtime = tmp / "version-guard/runtime"
    source = forge / "modules/launch_utils.py"
    source.parent.mkdir(parents=True)
    # Fixture rút gọn đúng các nhánh của verify_version(); không import engine GPU.
    guard = '''
import json, os
from types import SimpleNamespace
from typing import Any, Final
VERSION_UID: Final[str] = "PY313"
args = SimpleNamespace(ui_settings_file="config.json")
def verify_version():
    if not os.path.isfile(args.ui_settings_file):
        with open(args.ui_settings_file, "w", encoding="utf-8") as file:
            json.dump({"VERSION_UID": VERSION_UID}, file)
        return
    with open(args.ui_settings_file, encoding="utf-8") as file:
        settings = json.load(file)
    if settings.get("VERSION_UID", None) == VERSION_UID:
        return
    input("Press Enter to Continue...")
'''
    if upstream := os.environ.get("FORGE_VERSION_GUARD_SOURCE"):
        guard = Path(upstream).read_text(encoding="utf-8")
        print(f"   Dùng hàm verify_version/UID nguyên bản của Forge: {upstream}")
    uid_node = next(n for n in ast.parse(guard).body
                    if (isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id == "VERSION_UID")
                    or (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "VERSION_UID" for t in n.targets)))
    initial_uid = ast.literal_eval(uid_node.value)
    declaration = ast.get_source_segment(guard, uid_node)
    source.write_text(guard, encoding="utf-8")
    compat_fixture(forge)
    python = forge / "venv/bin/python"
    python.parent.mkdir(parents=True)
    python.symlink_to(sys.executable)
    cfg, ui = forge / "config.json", forge / "ui-config.json"
    original = {"tac_tagFile": "danbooru_e621.csv",
                "tac_translation.translationFile": "danbooru_e621_vi_translation_wai.csv",
                "tac_translation.searchByTranslation": True,
                "tac_translation.oldFormat": False,
                "clip_stop_at_last_layers": 2, "sd_model_checkpoint": "fixture.safetensors"}
    cfg.write_text(json.dumps(original, ensure_ascii=False))
    before = cfg.read_bytes()
    ui.write_text('{"custom_ui":"giữ nguyên"}')
    ui_before = ui.read_bytes()
    model = tmp / "version-guard/models/fixture.safetensors"
    model.parent.mkdir(parents=True); model.write_bytes(DATA)
    env = {"FORGE_DIR": str(forge), "WAI_RUNTIME_DIR": str(runtime), "TUNNEL": "none",
           "MODEL_DIR": str(model.parent), "MODEL_FILE": model.name, "MODEL_SHA256": SHA, "MODEL_MIN_BYTES": "1"}
    # Trích AST UID + hàm nguyên bản: không import các module engine/torch,
    # không thay input() và vẫn chạy thật với stdin=/dev/null như launch-bg.
    run_guard = """
import ast, json, os, sys
from types import SimpleNamespace
from typing import Any, Final
nodes = ast.parse(open(sys.argv[1], encoding="utf-8").read()).body
uid = next(n for n in nodes
           if (isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id == "VERSION_UID")
           or (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "VERSION_UID" for t in n.targets)))
verify = next(n for n in nodes if isinstance(n, ast.FunctionDef) and n.name == "verify_version")
namespace = {"json": json, "os": os, "Any": Any, "Final": Final,
             "args": SimpleNamespace(ui_settings_file=sys.argv[2])}
exec(compile(ast.Module(body=[uid, verify], type_ignores=[]), sys.argv[1], "exec"), namespace)
namespace["verify_version"]()
"""
    def verify():
        return subprocess.run([sys.executable, "-c", run_guard, str(source), str(cfg)],
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10)

    r = verify()
    check("Tái hiện config do v1.0.0 tạo → verify_version gặp EOFError", r.returncode != 0 and "EOFError" in r.stderr)
    r = source_call(SETUP, "prepare_launch", env)
    check("prepare_launch thật tự bổ sung UID trước khi chạy Forge", r.returncode == 0 and json.loads(cfg.read_text())["VERSION_UID"] == initial_uid, r.stdout+r.stderr)
    updated = json.loads(cfg.read_text())
    check("Sửa UID giữ nguyên tagcomplete, checkpoint và CLIP", all(updated.get(k) == v for k, v in original.items()))
    backups = list(forge.glob("config.json.wai-backup-*"))
    check("Sao lưu nguyên bản config thiếu UID trước khi sửa", len(backups) == 1 and backups[0].read_bytes() == before)
    check("Không sửa/xoá ui-config.json hay checkpoint", ui.read_bytes() == ui_before and model.read_bytes() == DATA)
    r = verify()
    check("Guard Forge vượt qua với stdin đóng — không cần Enter", r.returncode == 0 and "Press Enter" not in r.stdout, r.stdout+r.stderr)
    snapshot = cfg.read_bytes()
    r = source_call(SETUP, "ensure_config_version", env)
    check("Guard sửa chạy lại idempotent, không tạo backup thừa", r.returncode == 0 and cfg.read_bytes() == snapshot and len(list(forge.glob("config.json.wai-backup-*"))) == 1)

    old = {**original, "VERSION_UID": "LEGACY"}
    cfg.write_text(json.dumps(old)); before = cfg.read_bytes()
    r = source_call(SETUP, "prepare_launch", env)
    check("UID cũ thật sự → không gắn nhãn phiên bản mới để lách guard", r.returncode != 0 and cfg.read_bytes() == before and "Không tự đổi VERSION_UID" in r.stderr, r.stdout+r.stderr)
    cfg.write_text(json.dumps({**original, "VERSION_UID": None})); before = cfg.read_bytes()
    r = source_call(SETUP, "ensure_config_version", env)
    check("UID có mặt nhưng null cũng không tự coi là cấu hình mới", r.returncode != 0 and cfg.read_bytes() == before)
    legacy = {**original, "legacy_backend_option": True}
    cfg.write_text(json.dumps(legacy)); before = cfg.read_bytes()
    r = source_call(SETUP, "ensure_config_version", env)
    check("Config legacy không UID + tùy chọn khác → giữ nguyên, yêu cầu backup/reset", r.returncode != 0 and cfg.read_bytes() == before)
    cfg.write_text("{broken-json"); before = cfg.read_bytes()
    r = source_call(SETUP, "ensure_config_version", env)
    check("JSON hỏng không bị ghi đè", r.returncode != 0 and cfg.read_bytes() == before)

    cfg.unlink()
    # Thay UID và kiểu khai báo để chứng minh đọc AST, không hardcode PY313.
    source.write_text(guard.replace(declaration, 'VERSION_UID = "NEXT_UID_FOR_TEST"', 1), encoding="utf-8")
    r = source_call(SETUP, "prepare_launch", env)
    check("Clone mới: UID được đọc từ mã Forge, cả khai báo Assign", r.returncode == 0 and json.loads(cfg.read_text())["VERSION_UID"] == "NEXT_UID_FOR_TEST", r.stdout+r.stderr)
    r = verify()
    check("UID khác trong fixture vẫn vượt qua đúng guard của fixture đó", r.returncode == 0, r.stdout+r.stderr)
    source.write_text('VERSION_UID = "dynamic" + "uid"\n')
    before = cfg.read_bytes()
    r = source_call(SETUP, "ensure_config_version", env)
    check("UID không còn hằng chuỗi → báo lỗi, không đoán/ghi đè", r.returncode != 0 and cfg.read_bytes() == before)

    # Luồng cài mới: chạy stage extras thật, chỉ stub tài nguyên/extension để
    # không tải mạng hay import Gradio. Config writer của extras phải giữ UID.
    source.write_text(guard, encoding="utf-8"); cfg.unlink()
    repo = tmp / "version-guard/repo"
    (repo / "colab/extension/vi-prompt-builder/scripts").mkdir(parents=True)
    (repo / "danbooru_e621.csv").write_text("fixture,0,100,\n")
    (repo / "colab/extension/vi-prompt-builder/scripts/vi_prompt_tab.py").write_text("# fixture\n")
    for name in ("prompt_lib/editing.py", "prompt_lib/workflow.py", "extension/vi-prompt-builder/javascript/vi_prompt.js"):
        path = repo / "colab" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# fixture\n")
    (repo / "colab/make_tagcomplete_assets.py").write_text(
        "from pathlib import Path\n"
        "p=Path('colab/assets'); p.mkdir(parents=True, exist_ok=True)\n"
        "(p/'wai-illustrious-system-tags.csv').write_text('fixture,0,100,\\n')\n"
        "(p/'danbooru_e621_vi_translation_wai.csv').write_text('fixture,nghĩa\\n')\n"
    )
    (forge / "extensions/a1111-sd-webui-tagcomplete").mkdir(parents=True)
    upscaler = forge / "models/ESRGAN"
    upscaler.mkdir(parents=True)
    (upscaler / "RealESRGAN_x4plus_anime_6B.pth").write_bytes(b"fixture")
    r = source_call(SETUP, "stage_extras", {**env, "REPO_DIR": str(repo), "UPSCALER_DIR": str(upscaler)})
    guard_result = verify()
    check("Cài mới: stage extras thật tạo config có UID, giữ nó qua writer và vượt guard",
          r.returncode == 0 and json.loads(cfg.read_text()).get("VERSION_UID") == initial_uid
          and json.loads(cfg.read_text()).get("tac_translation.searchByTranslation") is True
          and guard_result.returncode == 0, r.stdout+r.stderr+guard_result.stderr)
    installed_js = forge / "extensions/vi-prompt-builder/javascript/vi_prompt.js"
    source_js = repo / "colab/extension/vi-prompt-builder/javascript/vi_prompt.js"
    check("Stage extras chép cả adapter JS và marker repo", installed_js.read_bytes() == source_js.read_bytes()
          and (forge / "extensions/vi-prompt-builder/.repo_root").read_text().strip() == str(repo))
    before = cfg.read_bytes(), installed_js.read_bytes()
    (repo / "colab/prompt_lib/workflow.py").unlink()
    r = source_call(SETUP, "stage_extras", {**env, "REPO_DIR": str(repo), "UPSCALER_DIR": str(upscaler)})
    check("Repo thiếu workflow → dừng sớm, giữ config/extension đang có", r.returncode != 0
          and "thiếu colab/prompt_lib/workflow.py" in r.stderr
          and before == (cfg.read_bytes(), installed_js.read_bytes()), r.stdout + r.stderr)


def test_lifecycle(tmp):
    print("5) Cài → chạy lại → sửa file thiếu → đổi model (offline)")
    home = tmp / "lifecycle"
    repo, forge, state, runtime = (home / x for x in ("repo", "forge", "state", "runtime"))
    colab = repo / "colab"
    colab.mkdir(parents=True)
    shutil.copy2(INSTALL, colab / "install.sh")
    for name in ("checkpoint_tools.py", "diagnostics.py", "forge_compat.py"):
        shutil.copy2(ROOT / "colab" / name, colab / name)
    for f in ("danbooru_e621.csv", "danbooru_e621_nounderscore.csv", "danbooru_e621_vi.csv",
              "danbooru_e621_vi_translation.csv", "colab/prompt_lib/index.py",
              "colab/prompt_lib/editing.py", "colab/prompt_lib/workflow.py"):
        p = repo / f; p.parent.mkdir(parents=True, exist_ok=True); p.write_text("fixture\n")
    compat_fixture(forge)
    import forge_compat
    forge_compat.apply(forge)  # stage forge/extras bên dưới là stub; check vẫn chạy thật
    trace, ready = home / "trace", home / "api-ready"
    downloads = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/model"):
                body, code = DATA, 200
                downloads.append(self.path)
            elif self.path.endswith("/sd-models") and ready.exists():
                filename = ready.read_text().strip()
                body = json.dumps([{"filename": filename, "title": Path(filename).name,
                                    "model_name": Path(filename).stem, "sha256": SHA}]).encode(); code = 200
            elif self.path.endswith("/cmd-flags") and ready.exists():
                body = json.dumps({"port": self.server.server_port, "api": True}).encode(); code = 200
            elif self.path.endswith("/options") and ready.exists():
                body = json.dumps({"sd_model_checkpoint": Path(ready.read_text().strip()).name,
                                   "forge_preset": "xl", "forge_checkpoint_xl": Path(ready.read_text().strip()).name}).encode(); code = 200
            else:
                body, code = b"not ready", 503
            self.send_response(code); self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body)
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    port = server.server_port
    stub = r'''#!/usr/bin/env bash
SETUP_API_VERSION=2
set -euo pipefail
printf '%s\n' "$1" >> "$TRACE_FILE"
if [[ "${FAIL_STAGE:-}" == "$1" ]]; then exit 42; fi
case "$1" in
  forge)
    mkdir -p "$FORGE_DIR/venv/bin"
    printf 'print("fixture")\n' > "$FORGE_DIR/launch.py"
    printf '#!/usr/bin/env bash\nexit 0\n' > "$FORGE_DIR/venv/bin/python"
    chmod +x "$FORGE_DIR/venv/bin/python" ;;
  torch) : ;;
  model) exec bash "$REAL_SETUP" model ;;
  extras)
    d="$FORGE_DIR/extensions/a1111-sd-webui-tagcomplete/tags"
    mkdir -p "$d" "$FORGE_DIR/extensions/vi-prompt-builder/scripts" "$FORGE_DIR/extensions/vi-prompt-builder/javascript"
    for f in danbooru_e621.csv wai-illustrious-system-tags.csv danbooru_e621_vi_translation_wai.csv; do echo fixture > "$d/$f"; done
    echo fixture > "$FORGE_DIR/extensions/vi-prompt-builder/scripts/vi_prompt_tab.py"
    echo fixture > "$FORGE_DIR/extensions/vi-prompt-builder/javascript/vi_prompt.js"
    echo style > "$FORGE_DIR/styles.csv"
    echo '{"tac_tagFile":"danbooru_e621.csv","tac_translation.translationFile":"danbooru_e621_vi_translation_wai.csv","tac_translation.searchByTranslation":true,"tac_translation.oldFormat":false}' > "$FORGE_DIR/config.json"
    echo "fixture credential: ${CIVITAI_TOKEN:-}; ?token=${CIVITAI_TOKEN:-}" ;;
  launch-bg) printf '%s\n' "$MODEL_DIR/$MODEL_FILE" > "$API_READY_FILE" ;;
  stop) rm -f "$API_READY_FILE" ;;
esac
'''
    executable(colab / "setup_forge.sh", stub)
    env = {"REPO_DIR": str(repo), "FORGE_DIR": str(forge), "MODEL_DIR": str(home / "models with spaces"),
           "STATE_DIR": str(state), "WAI_RUNTIME_DIR": str(runtime), "WAI_LOG": str(home / "install.log"),
           "REAL_SETUP": str(SETUP), "TRACE_FILE": str(trace), "API_READY_FILE": str(ready),
           "MODEL_MIN_BYTES": "1", "PORT": str(port), "TUNNEL": "none", "CIVITAI_TOKEN": "fixture-only-secret"}
    install = colab / "install.sh"
    url = f"http://127.0.0.1:{port}/model.safetensors"
    base = ["--skip", "preflight", "--model-url", url, "--model-sha", SHA, "--no-launch"]
    try:
        r = cli(base, env, install)
        check("Luồng cài đầy đủ trả thành công", r.returncode == 0 and "Mọi kiểm tra đều đạt" in r.stdout, r.stdout + r.stderr)
        check("Stage chạy đúng thứ tự", trace.read_text().splitlines() == ["forge", "torch", "model", "extras"], trace.read_text())
        check("Marker verify chỉ được ghi sau kiểm tra đạt", (state / "verify.ok").exists())
        check("Profile model được lưu cho app độc lập", json.loads((colab / "assets/model_profile.json").read_text())["WAI_PROFILE_MODEL_ID"] == "fp16")
        check("Token không xuất hiện trong log/output/state", all("fixture-only-secret" not in text for text in
              (r.stdout, (home / "install.log").read_text(), (state / "settings.json").read_text(), (state / "model.json").read_text())))
        before_count = len(downloads); trace.write_text("")
        r = cli(base, env, install)
        check("Chạy lại vẫn thành công (SETUP được khởi tạo lại)", r.returncode == 0, r.stdout + r.stderr)
        check("Chạy lại không cài lại Forge/torch/extras hợp lệ", trace.read_text().splitlines() == ["model"], trace.read_text())
        check("Chạy lại không tải lại checkpoint đã xác minh", len(downloads) == before_count)
        missing = forge / "extensions/a1111-sd-webui-tagcomplete/tags/danbooru_e621_vi_translation_wai.csv"
        missing.unlink(); trace.write_text("")
        r = cli(base, env, install)
        check("Marker cũ nhưng file dịch mất → tự cắm lại extras", r.returncode == 0 and missing.exists() and "extras" in trace.read_text(), r.stdout + r.stderr)
        missing_js = forge / "extensions/vi-prompt-builder/javascript/vi_prompt.js"
        missing_js.unlink(); trace.write_text("")
        r = cli(base, env, install)
        check("Marker cũ nhưng adapter JS mất → tự cắm lại extras", r.returncode == 0 and missing_js.exists() and "extras" in trace.read_text(), r.stdout + r.stderr)
        trace.write_text("")
        r = cli(["--model", "fp8", "--only", "model", "--model-url", url, "--model-sha", SHA, "--no-launch"], env, install)
        check("Đổi FP8 không bỏ qua stage model bởi marker FP16", r.returncode == 0 and trace.read_text().splitlines() == ["model"], r.stdout + r.stderr)
        saved = json.loads((state / "settings.json").read_text())
        check("Nhớ biến thể vừa chọn, giữ thư mục model tùy chọn", saved["MODEL_ID"] == "fp8" and saved["MODEL_DIR"] == env["MODEL_DIR"])
        check("FP8 lưu đúng tên checkpoint", (Path(env["MODEL_DIR"]) / "waiIllustriousSDXL_v170_fp8_e4m3.safetensors").exists())
        trace.write_text("")
        r = cli(["--only", "launch,verify"], env, install)
        check("--only launch đọc model/cache đã lưu, không hỏi API Civitai", r.returncode == 0 and trace.read_text().splitlines() == ["launch-bg"], r.stdout + r.stderr)
        r = cli(["--only", "launch,verify"], env, install)
        check("API đang chạy đúng cấu hình → không khởi động trùng", r.returncode == 0 and trace.read_text().splitlines() == ["launch-bg"], r.stdout + r.stderr)
        r = cli(["--only", "launch", "--restart"], env, install)
        check("Không tự dừng dịch vụ không do bộ cài quản lý", r.returncode != 0 and "không do bộ cài quản lý" in r.stdout, r.stdout + r.stderr)
        trace.write_text("")
        r = cli(["--only", "torch,extras", "--no-launch"], {**env, "FAIL_STAGE": "torch"}, install)
        check("Stage torch lỗi 42 được truyền ra exit code thật", r.returncode == 42, r.stdout + r.stderr)
        check("Stage lỗi không có marker và không chạy bước kế tiếp", not (state / "torch.ok").exists() and trace.read_text().splitlines() == ["torch"])
        missing.unlink()
        r = cli(["--only", "verify", "--no-launch"], env, install)
        check("Kiểm tra hỏng → exit nonzero, không báo cài thành công", r.returncode != 0 and "Các bước được chọn đã hoàn tất" not in r.stdout, r.stdout + r.stderr)
        check("Kiểm tra hỏng không ghi verify.ok", not (state / "verify.ok").exists())
        # Kiểm tra --doctor thật, nhưng network probes dùng curl fixture tránh internet.
        tools = home / "tools"
        executable(tools / "curl", '#!/usr/bin/env bash\nif [[ "$*" == *" -I "* || "${!#}" == -I ]]; then echo 200; exit 0; fi\nexit 7\n')
        executable(tools / "nvidia-smi", '#!/usr/bin/env bash\nexit 1\n')
        settings_before = {p.name: p.read_bytes() for p in state.iterdir() if p.is_file()}
        r = cli(["--doctor", "--no-launch"], {**env, "PATH": str(tools) + os.pathsep + os.environ["PATH"]}, install)
        settings_after = {p.name: p.read_bytes() for p in state.iterdir() if p.is_file()}
        check("Doctor báo hết vấn đề rồi mới trả nonzero (không dừng ngay ở GPU)", r.returncode == 1 and "Trạng thái cài đặt" in r.stdout and "kiểm tra cài đặt chưa đạt" in r.stderr, r.stdout + r.stderr)
        check("Doctor không thay marker/cấu hình", settings_before == settings_after)
        trace_before = trace.read_text()
        r = cli(["--status"], env, install)
        check("Status chỉ đọc, hiển thị biến thể đã nhớ", r.returncode == 0 and "fp8" in r.stdout and trace.read_text() == trace_before)
        r = cli(["--clean"], env, install)
        check("Clean chỉ xoá .ok, giữ model/state JSON", r.returncode == 0 and not list(state.glob("*.ok")) and (state / "model.json").exists() and list(Path(env["MODEL_DIR"]).glob("*.safetensors")))
        # Repo không đủ CSV + có thay đổi local: phải báo lỗi, không xoá/reset dữ liệu.
        local = repo / "my_notes.txt"; local.write_text("keep my notes")
        (repo / "danbooru_e621.csv").unlink()
        r = cli(["--only", "repo", "--no-launch"], env, install)
        check("Repo không hợp lệ không bị rm -rf/reset hard", r.returncode != 0 and local.read_text() == "keep my notes")
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def test_notebook():
    print("6) Notebook một ô và nguồn sinh")
    r = subprocess.run([sys.executable, str(ROOT / "colab/make_install_notebook.py")],
                       cwd=ROOT, text=True, capture_output=True, timeout=20)
    check("Generator notebook chạy được", r.returncode == 0, r.stderr)
    nb = json.loads((ROOT / "colab/WAI_v17_1click.ipynb").read_text())
    cells = [c for c in nb["cells"] if c["cell_type"] == "code"]
    check("Đúng một ô code để cài cả hệ thống", len(cells) == 1)
    source = "".join(cells[0]["source"])
    import ast
    ast.parse(source)
    check("Ô code Python hợp lệ, không có outputs đã chạy", cells[0]["outputs"] == [])
    check("Dropdown đủ 4 model, storage /content", all(x in source for x in ("fp16", "fp8", "int8", "hswq", "/content/models")))
    check("Token đọc từ Colab Secrets, không ghi literal", "userdata.get(name)" in source and 'GITHUB_TOKEN = "' not in source)
    check("Không mount Drive", "drive.mount" not in source)
    check("Bootstrap có raw GitHub và API dự phòng", "raw.githubusercontent.com" in source and "api.github.com" in source)
    check("Metadata notebook chọn GPU T4", nb["metadata"]["accelerator"] == "GPU" and nb["metadata"]["colab"]["gpuType"] == "T4")


def main():
    test_cli()
    test_metadata()
    with tempfile.TemporaryDirectory(prefix="wai-installer-test-") as directory:
        tmp = Path(directory)
        test_tunnel_defaults(tmp)
        test_model_and_torch(tmp)
        test_config_version(tmp)
        test_lifecycle(tmp)
    test_notebook()
    print("\n" + "=" * 68)
    if FAIL:
        print(f"HỎNG {len(FAIL)}/{len(PASS) + len(FAIL)} kiểm tra:", "; ".join(FAIL))
        return 1
    print(f"TẤT CẢ {len(PASS)} KIỂM TRA ĐỀU ĐẠT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
