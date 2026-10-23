"""Sinh notebook Colab một ô cài đặt: python3 colab/make_install_notebook.py.

Cấu hình dùng form Colab (dropdown model), credential đọc từ Colab Secrets.
Không lưu token trong source/output notebook. Nhánh mặc định là nhánh checkout.
"""

import json
import os
import subprocess
from pathlib import Path

from notebook_support import BOOTSTRAP_SOURCE, BRANCH, WORKFLOW_GUIDE

HERE = Path(__file__).resolve().parent
OUT = HERE / "WAI_v17_1click.ipynb"


INTRO = """# ⚡ WAI-Illustrious v17 — bộ cài Colab một ô · 1.0.7

**Cài mới từ đầu:** bật GPU rồi dùng **Runtime → Run all** (chỉ có 1 ô code).
Nếu đang dùng phiên cũ và muốn môi trường hoàn toàn mới, **tải ảnh cần giữ về trước**,
rồi chọn **Runtime → Disconnect and delete runtime**, kết nối lại và bật GPU.
Notebook không tự xóa repo/model/ảnh và không cần mount Google Drive.

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

**Tunnel mặc định `share` (Gradio):** mở link `gradio.live` được in ra; Cloudflare
vẫn có trong dropdown để chọn khi cần. Sau khi đổi từ Cloudflare, người dùng báo
ảnh hiển thị nhanh hơn và chưa thấy lỗi HTML/JSON; đây không phải benchmark hay
bảo đảm mọi mạng. Không giảm độ phân giải/chất lượng ảnh để đổi tunnel.
Nếu phiên hiện tại đã ổn với Gradio share, **không cần cài lại hoặc restart**.

**Error hàng loạt / traceback Matplotlib backend?** Từ 1.0.5 dùng backend Agg
riêng cho Forge con, không đổi notebook inline hay tải lại weights/Torch.
Xem [ô cập nhật chỉ phần mềm](https://github.com/manhlee1196-boop/ai-anime3/blob/arena/88f01d31-ai-anime3/colab/INSTALL.md#error-hàng-loạt--matplotlib-backend-inline-colab-105).

**API đã có WAI nhưng dropdown Checkpoint trống?** Từ 1.0.4 đã vá cmd-flags/schema
và khởi tạo sẵn danh sách từ registry. Dùng [ô cập nhật phần mềm trong runtime hiện tại](https://github.com/manhlee1196-boop/ai-anime3/blob/arena/88f01d31-ai-anime3/colab/INSTALL.md#api-đã-có-wai-nhưng-dropdown-trống--cmd-flags-500-104),
không tải lại model/Torch hay xóa runtime.

Dự trù **25 GB trống** và khoảng **10–25 phút** cho lần đầu (tuỳ tốc độ mạng/runtime).
Chạy lại ô được: bỏ qua phần đã cài hợp lệ, kiểm tra lại model và API, không chạy trùng Forge.
Ô cài luôn tải script mới từ đúng nhánh và kiểm tra **phiên bản ≥1.0.7 + cú pháp Bash**.
Nếu mất mạng, chỉ dùng cache đã đạt kiểm tra; **không âm thầm chạy cache <1.0.7**.

> Dữ liệu `/content` mất khi runtime kết thúc — tải ảnh về trước khi ngắt phiên.
> Tuân thủ điều khoản Colab và giấy phép model; không dùng cách cài này để né hạn chế
> của dịch vụ. Hệ thống mặc định mức `general`; negative prompt không bảo đảm lọc hoàn toàn nội dung.
"""

CELL = r'''#@title 🎨 Cài mới WAI v17 + Forge Neo + Prompt VN (>=1.0.7) { display-mode: "form" }
MODEL = "fp16" #@param ["fp16", "fp8", "int8", "hswq"]
MODEL_DIR = "/content/models" #@param {type:"string"}
TUNNEL = "share" #@param ["share", "cloudflared", "none"]
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

__BOOTSTRAP__
dest = Path("/content/install.sh")
download_installer(dest, BRANCH, env)

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
    print("▶ Chuẩn: 832×1216, Hires tắt. Chọn ảnh/seed rồi dùng Hoàn thiện.")
    print("▶ Dùng nút Thay mục Việt → tag Anh; giữ tag khác/trọng số, không xóa toàn bộ prompt.")
'''.replace("__BOOTSTRAP__", BOOTSTRAP_SOURCE).replace("__BRANCH__", BRANCH)

AFTER = WORKFLOW_GUIDE + """\n## Lệnh dùng sau khi cài

Dán vào một ô Colab mới khi cần:

```bash
!bash /content/install.sh --status                         # trạng thái + link
!bash /content/install.sh --doctor                         # kiểm tra, không cài/sửa gì
!bash /content/install.sh --diagnostics                    # checkpoint/preset/đường dẫn API
!bash /content/install.sh --only verify --smoke-test       # nạp trọng số + sinh 1 ảnh thử
!bash /content/install.sh --only model,extras              # sửa model/extension
!bash /content/install.sh --only launch,verify --restart   # khởi động lại, giữ tunnel đã chọn
!bash /content/install.sh --tunnel share --only launch,verify --restart  # đổi sang Gradio share
!bash /content/install.sh --model fp8 --only model,launch,verify  # đổi model
```

Đợi tác vụ sinh ảnh kết thúc trước khi restart/đổi tunnel; mở **link mới** sau đó.
Bộ cài nhớ tunnel đã chọn; notebook cũ có thể vẫn đặt `TUNNEL="cloudflared"`,
hãy chọn `share` trong form trước khi chạy lại. Không tự fallback/đổi tunnel.

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
        "colab": {"provenance": [], "gpuType": "T4", "name": "WAI v17 — Colab một ô 1.0.7"},
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
# Link INSTALL.md trong phần hướng dẫn phải trỏ đúng nhánh đang checkout.
text = json.dumps(notebook, ensure_ascii=False, indent=1).replace(
    "arena/88f01d31-ai-anime3", BRANCH)
OUT.write_text(text + "\n", encoding="utf-8")
print(f"Đã sinh {OUT.name}: 1 ô code, 2 ô hướng dẫn, nhánh {BRANCH}")
