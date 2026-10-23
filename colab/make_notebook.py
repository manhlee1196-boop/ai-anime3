"""Sinh notebook Colab từng bước đồng bộ bộ cài >=1.0.7.

Chạy: python3 colab/make_notebook.py. Notebook xuất ra không cần import generator.
"""
import json
from pathlib import Path

from notebook_support import (API_SAMPLE_SOURCE, BOOTSTRAP_SOURCE, BRANCH,
                              WORKFLOW_GUIDE)

# Nhánh cũ từng ghi cứng trong template; thay bằng BRANCH (nhánh đang checkout)
# đúng một lần lúc ghi file, để "Run all" tải mã mới nhất.
LEGACY_BRANCH = "arena/88f01d31-ai-anime3"

HERE = Path(__file__).resolve().parent
OUT = HERE / "WAI_Illustrious_v17_vi.ipynb"
cells = []


def md(text):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": text.splitlines(True)})


def code(text):
    cells.append({"cell_type": "code", "execution_count": None, "metadata": {},
                  "outputs": [], "source": text.splitlines(True)})


md("""# 🎨 WAI-Illustrious v17 — Google Colab · 1.0.7
### Forge Neo + tagcomplete + Prompt VN + 349.714 tag / 45.557 bản dịch

Notebook này dùng **cùng bộ cài đã kiểm tra** với notebook một ô, nhưng chia từng
stage để dễ theo dõi lỗi. Không ComfyUI, không mount Drive, không tự đổi model.

**Chạy mới từ đầu:**
1. Chọn **Runtime → Change runtime type → GPU T4** (hoặc GPU NVIDIA khác).
2. Chọn model ở Ô 1; mặc định **FP16 gốc**, checkpoint tại `/content/models`.
3. **Runtime → Run all**, hoặc chạy lần lượt Ô 1 → Ô 8. Forge chạy nền, Ô 8 có thể
   kết thúc sau launch/verify; không bị chặn ở một ô chạy mãi.
4. Mở link public và dùng tab **Prompt VN**. Ô 9/10/11 mặc định chỉ in hướng dẫn,
   không tự sinh ảnh hay mở thêm server.

**Tunnel mặc định `share` (Gradio):** mở link `gradio.live` được in ra; Cloudflare
vẫn có trong dropdown để chọn khi cần. Sau khi đổi từ Cloudflare, người dùng báo
ảnh hiển thị nhanh hơn và chưa thấy lỗi HTML/JSON; đây không phải benchmark hay
bảo đảm mọi mạng. Không giảm độ phân giải/chất lượng ảnh để đổi tunnel.
Nếu phiên hiện tại đã ổn với Gradio share, **không cần cài lại hoặc restart**.

**Error hàng loạt / traceback Matplotlib backend?** Từ 1.0.5 dùng backend Agg
riêng cho Forge con, không đổi notebook inline hay tải lại weights/Torch.
Xem [ô cập nhật chỉ phần mềm](https://github.com/manhlee1196-boop/ai-anime3/blob/arena/88f01d31-ai-anime3/colab/INSTALL.md#error-hàng-loạt--matplotlib-backend-inline-colab-105).

**API đã có WAI nhưng dropdown Checkpoint trống?** Từ 1.0.4 đã vá schema cmd-flags
và khởi tạo sẵn danh sách checkpoint. Dùng [ô cập nhật phần mềm trong runtime hiện tại](https://github.com/manhlee1196-boop/ai-anime3/blob/arena/88f01d31-ai-anime3/colab/INSTALL.md#api-đã-có-wai-nhưng-dropdown-trống--cmd-flags-500-104),
không tải lại model/Torch hay xóa runtime.

Nếu muốn môi trường hoàn toàn mới khi đang dùng phiên cũ, **tải ảnh về trước** rồi
chọn **Runtime → Disconnect and delete runtime**, kết nối lại và bật GPU. Notebook
không tự xóa thư mục cũ. Chạy lại trong cùng phiên sẽ tiếp tục/cập nhật an toàn.

| Model | Ghi chú |
|---|---|
| `fp16` ⭐ | WAI v17 gốc pruned, 6,46 GiB; VAE tích hợp; SHA256 đã biết; khuyên dùng |
| `fp8` / `int8` | Bản lượng tử hóa cộng đồng, thử nghiệm; CFG 6.5 / 25 bước |
| `hswq` | Turbo merge cộng đồng, thử nghiệm; CFG 1 / 10 bước, không dùng CFG FP16 |

Cần khoảng **25 GB trống**, **10–25 phút** cho lần cài đầu tùy mạng/runtime. T4 không
có tensor core FP8; model nhỏ hơn không bảo đảm nhanh hơn. Chưa benchmark GPU thật.
Dữ liệu `/content` mất khi kết thúc runtime; không có thủ thuật giữ runtime luôn hoạt động.
Mặc định phân loại `general`; negative prompt không bảo đảm lọc mọi nội dung.
Tuân thủ giấy phép model, pháp luật và điều khoản Google Colab.
""")

md("""## ⚙️ Ô 1 — Cấu hình

FP16 được khuyên dùng. Nếu cần token tải Civitai, thêm `CIVITAI_TOKEN` vào **Colab
Secrets**, bật Notebook access và `USE_CIVITAI_SECRET`; không dán token vào code.
Repo public không cần GitHub token. Thư mục mặc định đều trong `/content`.
""")
code('''#@title ⚙️ Model và thư mục (cài mới) { display-mode: "form" }
MODEL = "fp16" #@param ["fp16", "fp8", "int8", "hswq"]
MODEL_DIR = "/content/models" #@param {type:"string"}
TUNNEL = "share" #@param ["share", "cloudflared", "none"]
PORT = 7860 #@param {type:"integer"}
CUDA_INDEX = "auto" #@param ["auto", "cu130", "cu128", "cu126"]
RESTART = False #@param {type:"boolean"}
FALLBACK_FP16 = False #@param {type:"boolean"}
USE_CIVITAI_SECRET = False #@param {type:"boolean"}
USE_GITHUB_SECRET = False #@param {type:"boolean"}

import os
os.environ.update({
    "REPO_DIR": "/content/ai-anime3",
    "REPO_URL": "https://github.com/manhlee1196-boop/ai-anime3",
    "REPO_BRANCH": "arena/88f01d31-ai-anime3",
    "FORGE_DIR": "/content/sd-webui-forge-neo",
    "FORGE_REPO": "https://github.com/Haoming02/sd-webui-forge-classic",
    "FORGE_BRANCH": "neo",
    "MODEL_ID": MODEL, "MODEL_DIR": MODEL_DIR, "TUNNEL": TUNNEL,
    "PORT": str(PORT), "CUDA_INDEX": CUDA_INDEX,
    "VI_PROMPT_ROOT": "/content/ai-anime3",
})
# Không giữ MODEL_FILE/SHA/URL từ ô cấu hình FP16 của notebook cũ khi chọn FP8/HSWQ.
# Muốn mirror/checkpoint tùy chỉnh, dùng cờ bộ cài trong colab/INSTALL.md.
for key in ("MODEL_FILE", "MODEL_SHA256", "MODEL_URL", "MODEL_MIN_BYTES"):
    os.environ.pop(key, None)
if USE_CIVITAI_SECRET or USE_GITHUB_SECRET:
    from google.colab import userdata
    for enabled, name in ((USE_CIVITAI_SECRET, "CIVITAI_TOKEN"), (USE_GITHUB_SECRET, "GITHUB_TOKEN")):
        if enabled:
            try:
                os.environ[name] = userdata.get(name)
            except Exception:
                raise RuntimeError(f"Chưa đọc được Secret {name}; thêm secret và bật Notebook access.") from None
print(f"✔ {MODEL} · model {MODEL_DIR} · Forge {os.environ['FORGE_DIR']} · {TUNNEL}:{PORT}")''')

md("""## Ô 2 — Lấy bộ cài mới và repo đúng nhánh

Bootstrap thử raw GitHub rồi API, kiểm **phiên bản ≥1.0.7** và cú pháp trước khi
chạy. Không chạy cache <1.0.7. Bộ cài clone đầy đủ kho prompt + thư viện mới + JS
thay Việt → Anh; repo sẵn có được fast-forward khi sạch/cùng nhánh, không reset hard.
Không đổi sang main/master hoặc xóa repo có thay đổi của bạn.
""")
code('''import os, subprocess
''' + BOOTSTRAP_SOURCE + '''
INSTALLER = Path("/content/install.sh")
download_installer(INSTALLER, os.environ["REPO_BRANCH"], dict(os.environ))


def run_install(stages, launch=False, restart=False, smoke=False):
    args = ["bash", str(INSTALLER), "--only", stages, "--model", MODEL,
            "--model-dir", MODEL_DIR, "--branch", os.environ["REPO_BRANCH"],
            "--port", str(PORT), "--tunnel", TUNNEL, "--cuda", CUDA_INDEX]
    if not launch:
        args.append("--no-launch")
    if restart:
        args.append("--restart")
    if smoke:
        args.append("--smoke-test")
    if FALLBACK_FP16:
        args.append("--fallback-fp16")
    subprocess.run(args, env=dict(os.environ), check=True)


run_install("repo")
# Stage sau ưu tiên setup_forge.sh trong repo. Từ chối trộn checkout/bộ cài cũ.
checked_installer_version((Path(os.environ["REPO_DIR"]) / "colab/install.sh").read_bytes())
print("✔ Repo/bộ cài đủ phiên bản; tiếp tục Ô 3 → Ô 8.")''')

for number, stage, title, description in (
    (3, "preflight", "Kiểm tra GPU, driver và ổ đĩa", "Kiểm NVIDIA GPU, đường dẫn, dung lượng và mạng. Chưa tải checkpoint hay cài Torch."),
    (4, "forge", "Cài Forge Neo", "Dùng Python 3.13 riêng qua uv; giữ thư mục và cấu hình sẵn có."),
    (5, "torch", "Cài PyTorch phù hợp GPU", "Bộ cài chọn cu130/cu128/cu126 theo driver và kiểm kernel CUDA, không chỉ cuda.is_available()."),
    (6, "model", "Tải và xác minh checkpoint WAI v17", "Tải tiếp .part; xác minh SHA256 + header safetensors. Chỉ đúng biến thể/file v17, không tự đổi model khi nguồn lỗi."),
    (7, "extras", "Cắm tagcomplete + Prompt VN mới", "Chép CSV/JS mới, cấu hình dịch 2 cột, CLIP stop 2, styles và upscaler anime. Thư viện editing/workflow phải có đủ trước khi thay extension."),
):
    md(f"## Ô {number} — {title}\n\n{description}\n")
    code(f'run_install("{stage}")')

md("""## Ô 8 — Khởi chạy nền + kiểm tra checkpoint/API

Chờ bộ cài in link `gradio.live` (mặc định) hoặc `trycloudflare.com` (khi chọn), mở link mới và chọn **Prompt VN**.
Ô này kết thúc khi API/verify đạt; Forge/tunnel tiếp tục chạy nền trong runtime.
Không tự sinh ảnh để chứng minh trọng số đã nạp; bước đó là tùy chọn Ô 9.
Nếu dùng phiên cũ, bật `RESTART=True` ở Ô 1 để nạp extension/JS mới rồi reload cứng UI.
""" + WORKFLOW_GUIDE)
code('run_install("launch,verify", launch=True, restart=RESTART)')

md("""## 🔧 Ô 9 (tùy chọn) — Chẩn đoán và sinh ảnh kiểm tra

Chỉ bật `RUN_DIAGNOSTICS` khi cần xem checkpoint/preset/API. `SMOKE_TEST` dùng GPU
để nạp trọng số và sinh **1 ảnh 256×256 / 1 step**, không phải benchmark/chất lượng.
Mặc định cả hai tắt nên **Run all không tự sinh ảnh**.
""")
code('''#@title 🔧 Kiểm tra thêm (tùy chọn) { display-mode: "form" }
RUN_DIAGNOSTICS = False #@param {type:"boolean"}
SMOKE_TEST = False #@param {type:"boolean"}
if RUN_DIAGNOSTICS:
    subprocess.run(["bash", str(INSTALLER), "--diagnostics"], check=True)
if SMOKE_TEST:
    run_install("verify", launch=True, smoke=True)
if not RUN_DIAGNOSTICS and not SMOKE_TEST:
    print("Bỏ qua chẩn đoán/sinh ảnh thử. Launch + verify đã chạy ở Ô 8.")''')

md("""## 🖼️ Ô 10 (tùy chọn) — Sinh ảnh bằng API theo quy trình mới

Bật `RUN_API_SAMPLE` khi muốn dùng API thay cho tab Prompt VN. Mặc định **Nháp,
832×1216, Hires tắt**, steps/CFG theo model đã chọn. Nhiều ảnh chạy tuần tự.
Sau lượt Nháp/Chuẩn, chọn seed của ảnh thật (không phải grid), nhập `SEED` và chọn
Hoàn thiện để sinh 1 ảnh Hires. Mã dùng bộ giải mã chung cho info JSON-string và
PNG/PIL, không dùng ví dụ API cũ bật Hires ngay hoặc cố định CFG FP16 cho HSWQ.
""")
code(API_SAMPLE_SOURCE)

md("""## 🧩 Ô 11 (tùy chọn) — App Prompt VN độc lập

Không cần ô này để dùng tab Prompt VN đã cài trong Forge. Nếu muốn app riêng,
bật `START_PROMPT_APP`; ô kiểm tra PID/cổng trước để tránh chạy server trùng.
App dùng venv Forge, không cài lại Gradio/Torch. Chỉ dùng một nơi để sinh ảnh tại
một thời điểm; queue của app riêng không chặn mọi client GPU khác.
""")
code('''#@title 🧩 App soạn prompt riêng (không tự mở khi Run all) { display-mode: "form" }
START_PROMPT_APP = False #@param {type:"boolean"}


def start_prompt_app():
    import os, socket, subprocess, time
    from pathlib import Path
    repo = Path(os.environ["REPO_DIR"])
    python = Path(os.environ["FORGE_DIR"]) / "venv/bin/python"
    script = repo / "colab/prompt_builder.py"
    pid_file = Path("/content/prompt_builder.pid")
    log = Path("/content/prompt_builder.log")
    if not python.is_file() or not script.is_file():
        raise RuntimeError("Chưa có Forge/app; chạy Ô 1 → Ô 8 trước.")
    owned = False
    try:
        pid = int(pid_file.read_text().strip())
        parts = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\\0")
        owned = os.fsencode(script) in parts
    except (OSError, ValueError):
        pass
    if not owned:
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", 7861)) == 0:
                raise RuntimeError("Cổng 7861 do dịch vụ khác dùng; không tự đóng dịch vụ đó.")
        env = dict(os.environ)
        for key in ("GITHUB_TOKEN", "CIVITAI_TOKEN"):
            env.pop(key, None)
        with log.open("w") as stream:
            process = subprocess.Popen(
                [str(python), "-u", str(script), "--forge-url", f"http://127.0.0.1:{PORT}",
                 "--host", "0.0.0.0", "--port", "7861", "--share"],
                cwd=repo, env=env, stdout=stream, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, start_new_session=True,
            )
        pid_file.write_text(str(process.pid))
    else:
        print("✔ App do notebook quản lý đang chạy; không mở server trùng.")
    for _ in range(90):
        text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
        link = next((line.strip() for line in text.splitlines() if "gradio.live" in line), None)
        if link:
            print("✔ Link app:", link)
            return
        if "Traceback" in text:
            raise RuntimeError("App lỗi; xem /content/prompt_builder.log riêng, không chia sẻ log có dữ liệu riêng.")
        if not owned and process.poll() is not None:
            raise RuntimeError("App đã dừng; xem /content/prompt_builder.log.")
        time.sleep(2)
    raise RuntimeError("Chưa có link sau 180 giây; xem log trước khi thử lại, không mở trùng process.")


if START_PROMPT_APP:
    start_prompt_app()
else:
    print("Bỏ qua app riêng. Dùng tab Prompt VN trong link Forge ở Ô 8.")''')

md("""---
## 🚑 Xử lý sự cố / chạy lại

| Triệu chứng | Xử lý |
|---|---|
| Không có GPU | Runtime → Change runtime type → GPU T4 rồi chạy lại từ Ô 1 |
| Không lấy được bộ cài ≥1.0.7 | Kiểm mạng/mở notebook mới; không dùng cache <1.0.7 |
| Checkpoint trống / lỗi CUDA | Chạy `!bash /content/install.sh --diagnostics`; gửi phần lỗi đã che secret, không dump config/log riêng |
| Model SHA/header sai | Chạy lại Ô 6 để tải tiếp/thử đúng nguồn; không đổi MODEL_FILE thủ công |
| Tag Việt còn sau chọn | Kiểm tab Prompt VN có nút Thay mục Việt; chạy lại Ô 2 + Ô 7, bật RESTART rồi Ô 8 và reload cứng UI |
| Hết VRAM | Tắt Hires, 832×1216/1024×1024, batch 1; chờ tác vụ GPU khác, không cần tải lại checkpoint |
| Sửa phần mềm trong phiên đang có | `!bash /content/install.sh --only repo,extras,launch,verify --restart` |
| Ảnh chậm / `Unexpected token <` khi dùng Cloudflare | Đợi sinh xong, đổi `TUNNEL="share"`, bật `RESTART` rồi chạy Ô 8; mở link mới |
| Gradio share không tạo được link | Chọn `TUNNEL="cloudflared"`, bật `RESTART` rồi chạy Ô 8; không tải lại model/Torch |
| Xem link/trạng thái | `!bash /content/install.sh --status` |
| Chạy mới hoàn toàn | Tải ảnh về, Disconnect and delete runtime, kết nối lại + GPU rồi Run all notebook mới |

Đợi tác vụ sinh ảnh kết thúc trước khi restart/đổi tunnel. Phiên Gradio share đang ổn không cần chạy lại.
Bộ cài nhớ tunnel đã chọn; form notebook cũ vẫn có thể ghi đè bằng `cloudflared`.
Chạy lại stage không xóa model/ảnh/repo. Kho tag chính vẫn là bản Anh có `_`;
file dịch 2 cột, **old 3-column format tắt**. Mọi dữ liệu `/content` là tạm thời.
""")

notebook = {
    "nbformat": 4, "nbformat_minor": 0,
    "metadata": {
        "colab": {"provenance": [], "gpuType": "T4", "name": "WAI v17 — Colab từng bước 1.0.7",
                  "collapsed_sections": []},
        "kernelspec": {"name": "python3", "display_name": "Python 3"},
        "language_info": {"name": "python"}, "accelerator": "GPU",
    },
    "cells": cells,
}
# Nhánh trong notebook phải là nhánh đang checkout (xem notebook_support.BRANCH),
# để "Run all" tải đúng mã nguồn thay vì một nhánh cũ.
text = json.dumps(notebook, ensure_ascii=False, indent=1).replace(LEGACY_BRANCH, BRANCH)
OUT.write_text(text + "\n", encoding="utf-8")
print(f"Đã sinh {OUT.name}: {sum(c['cell_type'] == 'code' for c in cells)} ô code, dùng bộ cài >=1.0.7")
