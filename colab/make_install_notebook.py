"""Sinh notebook Colab một ô cài đặt: python3 colab/make_install_notebook.py.

Cấu hình dùng form Colab (dropdown model), credential đọc từ Colab Secrets.
Không lưu token trong source/output notebook. Nhánh mặc định là nhánh checkout.
"""

import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "WAI_v17_1click.ipynb"


def current_branch():
    r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                       cwd=HERE.parent, capture_output=True, text=True, timeout=15)
    branch = r.stdout.strip()
    return branch if r.returncode == 0 and branch != "HEAD" else "main"


BRANCH = os.environ.get("WAI_BRANCH") or current_branch()

INTRO = """# ⚡ WAI-Illustrious v17 — bộ cài Colab một ô

**Forge Neo + tagcomplete + kho prompt tiếng Việt + tab Prompt VN** được cài bằng
một lần chạy ô dưới. Mặc định lưu model và ảnh trong `/content`, **không mount Drive**.

1. **Runtime → Change runtime type → GPU T4** (hoặc GPU NVIDIA khác).
2. Chọn **MODEL** trong dropdown; sửa **MODEL_DIR** nếu cần, rồi chạy ô (Shift+Enter).
3. Khi kiểm tra đạt, mở link public được in ra, dùng tab **Prompt VN**.
4. Có thể bật `SMOKE_TEST=True` để buộc nạp checkpoint bằng **1 ảnh thử 256×256/1 step**;
   có sử dụng GPU, không phải benchmark/ảnh chất lượng. Không bật cùng `NO_LAUNCH`.

| MODEL | Dung lượng xấp xỉ | Ghi chú |
|---|---|---|
| `fp16` ⭐ | 6,46 GiB | **Khuyến nghị**: bản gốc FP16 pruned; SHA256 đã biết; mirror HuggingFace |
| `fp8` | 4,07 GiB | FP8 e4m3 cộng đồng — **thử nghiệm** |
| `int8` | 4,39 GiB | INT8 convrot cộng đồng — **thử nghiệm** |
| `hswq` | 4,43 GiB | HSWQ turbo merge — **thử nghiệm**, CFG 1 / 10 bước |

FP16 bản gốc **đã là pruned**, không phải một biến thể khác. Ba bản cộng đồng lấy
URL và SHA256 của **đúng file v17** từ Civitai API lúc cài; cần quyền tải phù hợp.
Bộ cài không tự đổi phiên bản/model khi API lỗi, trừ khi bạn bật `FALLBACK_FP16`.
**T4 không có tensor core FP8**; lượng tử hoá không đồng nghĩa sinh ảnh nhanh hơn.
Chưa kiểm chứng sinh ảnh với các biến thể cộng đồng trên Colab.

**Nếu Civitai cần token:** thêm `CIVITAI_TOKEN` vào **Secrets** (biểu tượng chìa khoá
bên trái Colab), bật Notebook access rồi chọn `USE_CIVITAI_SECRET=True`. Không viết
API token vào source/lệnh/output notebook. Repo này public nên **không cần GitHub token**.

Dự trù **25 GB trống** và khoảng **10–25 phút** cho lần đầu (tuỳ tốc độ mạng/runtime).
Chạy lại ô được: bỏ qua phần đã cài hợp lệ, kiểm tra lại model và API, không chạy trùng Forge.

> Dữ liệu `/content` mất khi runtime kết thúc — tải ảnh về trước khi ngắt phiên.
> Tuân thủ điều khoản Colab và giấy phép model; không dùng cách cài này để né hạn chế
> của dịch vụ. Hệ thống mặc định mức `general`; negative prompt không bảo đảm lọc hoàn toàn nội dung.
"""

CELL = r'''#@title 🎨 Cài WAI v17 + Forge Neo + prompt tiếng Việt { display-mode: "form" }
MODEL = "fp16" #@param ["fp16", "fp8", "int8", "hswq"]
MODEL_DIR = "/content/models" #@param {type:"string"}
TUNNEL = "cloudflared" #@param ["cloudflared", "share", "none"]
PORT = 7860 #@param {type:"integer"}
CUDA_INDEX = "auto" #@param ["auto", "cu130", "cu128", "cu126"]
NO_LAUNCH = False #@param {type:"boolean"}
RESTART = False #@param {type:"boolean"}
SMOKE_TEST = False #@param {type:"boolean"}
FALLBACK_FP16 = False #@param {type:"boolean"}
USE_CIVITAI_SECRET = False #@param {type:"boolean"}
USE_GITHUB_SECRET = False #@param {type:"boolean"}
BRANCH = "__BRANCH__"

import os
import signal
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

env = dict(os.environ)
if USE_CIVITAI_SECRET or USE_GITHUB_SECRET:
    from google.colab import userdata
    for enabled, name in ((USE_CIVITAI_SECRET, "CIVITAI_TOKEN"),
                          (USE_GITHUB_SECRET, "GITHUB_TOKEN")):
        if enabled:
            try:
                env[name] = userdata.get(name)
            except Exception:
                raise RuntimeError(f"Chưa đọc được Secret {name}; thêm secret và bật Notebook access.") from None

owner_repo = "manhlee1196-boop/ai-anime3"
raw = f"https://raw.githubusercontent.com/{owner_repo}/{BRANCH}/colab/install.sh"
api = (f"https://api.github.com/repos/{owner_repo}/contents/colab/install.sh?ref="
       + urllib.parse.quote(BRANCH, safe=""))
dest = Path("/content/install.sh")
dest.parent.mkdir(parents=True, exist_ok=True)

# Lấy file mới qua raw GitHub; dự phòng API GitHub. Ghi nguyên tử, không chạy file dở.
downloaded = False
for url in (raw, api):
    headers = {"Accept": "application/vnd.github.raw", "User-Agent": "wai-colab-installer/1.0"}
    if env.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {env['GITHUB_TOKEN']}"
    try:
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read()
        if not data.startswith(b"#!/usr/bin/env bash") or len(data) < 5000:
            raise ValueError("Không phải script bộ cài đầy đủ")
        tmp = dest.with_suffix(".sh.tmp")
        tmp.write_bytes(data)
        subprocess.run(["bash", "-n", str(tmp)], check=True, capture_output=True)
        tmp.replace(dest)
        downloaded = True
        break
    except (OSError, ValueError, subprocess.CalledProcessError, urllib.error.URLError):
        continue
if not downloaded:
    if dest.exists() and dest.stat().st_size > 5000:
        print("⚠ Không lấy được bản mới; dùng bộ cài đã có trong /content.")
    else:
        raise RuntimeError("Không tải được install.sh. Kiểm tra mạng/nhánh; hoặc upload file colab/install.sh vào /content.")

args = ["bash", str(dest), "--model", MODEL, "--model-dir", MODEL_DIR,
        "--branch", BRANCH, "--port", str(PORT), "--tunnel", TUNNEL, "--cuda", CUDA_INDEX]
if NO_LAUNCH:
    args.append("--no-launch")
if RESTART:
    args.append("--restart")
if SMOKE_TEST:
    args.append("--smoke-test")
if FALLBACK_FP16:
    args.append("--fallback-fp16")

print(f"▶ Cài model {MODEL}; lưu ở {MODEL_DIR}; tunnel {TUNNEL}.", flush=True)
# Stream log về output Colab; shell trả lỗi thật nếu một bước thất bại.
process = subprocess.Popen(args, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, bufsize=1, start_new_session=True)
try:
    for line in process.stdout:
        print(line, end="", flush=True)
    rc = process.wait()
except KeyboardInterrupt:
    os.killpg(process.pid, signal.SIGTERM)
    process.wait()
    print("Đã dừng. Chạy lại ô để tiếp tục; phần model .part đã tải được giữ lại.")
    raise
finally:
    process.stdout.close()

if rc:
    raise RuntimeError(f"Bộ cài dừng với mã {rc}. Xem lỗi ở trên hoặc chạy !bash /content/install.sh --doctor.")
if NO_LAUNCH:
    print("✅ Cài xong, chưa mở Forge. Khởi động: !bash /content/install.sh --only launch,verify")
else:
    print("✅ Các bước đã đạt. Mở link public ở trên → dùng tab Prompt VN.")
'''.replace("__BRANCH__", BRANCH)

AFTER = """## Lệnh dùng sau khi cài

Dán vào một ô Colab mới khi cần:

```bash
!bash /content/install.sh --status                         # trạng thái + link
!bash /content/install.sh --doctor                         # kiểm tra, không cài/sửa gì
!bash /content/install.sh --diagnostics                    # checkpoint/preset/đường dẫn API
!bash /content/install.sh --only verify --smoke-test       # nạp trọng số + sinh 1 ảnh thử
!bash /content/install.sh --only model,extras              # sửa model/extension
!bash /content/install.sh --only launch,verify --restart   # khởi động lại
!bash /content/install.sh --model fp8 --only model,launch,verify  # đổi model
```

Token Civitai vẫn cần được đọc từ Secrets và truyền qua environment cho lệnh tải.
Xem `colab/INSTALL.md` để biết cách truyền secret cho một ô Bash mới.
Khi đổi model, bộ cài chỉ dừng/khởi động lại process Forge **do chính nó quản lý**,
không tự đóng dịch vụ khác đang chiếm cổng. CFG/steps của **Prompt VN và app Gradio**
tự đổi theo profile model đã lưu (HSWQ mặc định CFG 1 / 10 bước).

Model, ảnh, log và marker đều trong `/content`; **không có bước mount Drive**.
Nguồn biến thể: Civitai model 827184 (gốc), 2451718 (FP8/INT8), 2698106 (HSWQ).
Các kiểm tra cài đặt không thay thế một lần sinh ảnh thật trên GPU.
"""

notebook = {
    "nbformat": 4, "nbformat_minor": 0,
    "metadata": {
        "colab": {"provenance": [], "gpuType": "T4", "name": "WAI v17 — bộ cài một ô"},
        "accelerator": "GPU",
        "kernelspec": {"name": "python3", "display_name": "Python 3"},
        "language_info": {"name": "python"},
    },
    "cells": [
        {"cell_type": "markdown", "metadata": {"id": "intro"}, "source": INTRO.splitlines(True)},
        {"cell_type": "code", "execution_count": None, "outputs": [],
         "metadata": {"id": "install", "cellView": "form"}, "source": CELL.splitlines(True)},
        {"cell_type": "markdown", "metadata": {"id": "after"}, "source": AFTER.splitlines(True)},
    ],
}
OUT.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(f"Đã sinh {OUT.name}: 1 ô code, 2 ô hướng dẫn, nhánh {BRANCH}")
