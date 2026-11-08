"""Sinh notebook Colab tối giản: python3 colab/make_install_notebook.py.

Chỉ một ô code cho cài mới/cập nhật. Các tuỳ chọn nâng cao vẫn nằm trong install.sh
và notebook chi tiết, không làm rối màn hình chính.
"""

import json
from pathlib import Path

from notebook_support import BOOTSTRAP_SOURCE, BRANCH

HERE = Path(__file__).resolve().parent
OUT = HERE / "WAI_v17_1click.ipynb"


INTRO = """# ⚡ WAI-Illustrious v17 — Colab một ô

**Dùng:** bật **GPU T4** → chạy ô duy nhất bên dưới (**Runtime → Run all**) → mở link public được in ra.

- **FP16 + Gradio share** là mặc định khuyến nghị; chỉ đổi khi thật sự cần.
- Tự cài Forge Neo, checkpoint, tag tiếng Việt, app `/vi-mobile/` và **job nền + file stream cho Android**.
- Ảnh giữ PNG/JPEG/WebP gốc; có thể bật **S3/Cloudflare R2** bằng Colab Secrets để tải qua signed URL. Không cấu hình thì dùng file local có resume Range.
- Model/ảnh nằm trong `/content`, **không mount Drive**, không tự xóa dữ liệu cũ.
- Chạy lại ô sẽ cập nhật code/extension, giữ model đã có và khởi động lại Forge để nạp bản mới. **Đợi job hiện tại kết thúc trước khi chạy lại.**

### App Android
Mở app → **Máy chủ** → dán link public. Chẩn đoán phải có **Job nền & file stream**. App tạo `job_id`, poll trạng thái, nhận manifest nhỏ rồi tải Blob; lỗi tải file chỉ retry download, không tạo lại ảnh. Web txt2img và app dùng cùng engine.

**S3/R2 (tuỳ chọn):** thêm các Secrets `ANIME3_S3_BUCKET`, `ANIME3_S3_ENDPOINT_URL`, `ANIME3_S3_ACCESS_KEY_ID`, `ANIME3_S3_SECRET_ACCESS_KEY`; tuỳ chọn thêm `ANIME3_S3_REGION`, `ANIME3_S3_PREFIX`, `ANIME3_S3_SIGNED_TTL`. Bật quyền **Notebook access** cho các Secret đó trước khi chạy ô. Credential không nằm trong APK hay file cấu hình repo.

### Đường dẫn nhanh
- Web Forge: `<link public>/`
- App trên điện thoại không cần APK: `<link public>/vi-mobile/`
- Ảnh gốc: `/content/stable-diffusion-webui-forge/outputs/txt2img-images/`

Civitai token được đọc từ **Colab Secrets → `CIVITAI_TOKEN`** nếu có; repo public không cần GitHub token. Các tuỳ chọn CUDA/cổng/thư mục/smoke test nâng cao vẫn có trong `colab/install.sh`, không hiện ở đây.

> `/content` mất khi xóa runtime; tải ảnh cần giữ về trước. Tuân thủ điều khoản Colab và giấy phép model.
"""

CELL = r'''#@title 🎨 Cài / cập nhật WAI v17 + Forge + App Android { display-mode: "form" }
MODEL = "fp16" #@param ["fp16", "fp8", "int8", "hswq"]
TUNNEL = "share" #@param ["share", "cloudflared"]
BRANCH = "__BRANCH__"

# Mặc định gọn cho một ô; tùy chọn nâng cao dùng trực tiếp colab/install.sh.
MODEL_DIR = "/content/models"
PORT = 7860
CUDA_INDEX = "auto"

import os
import signal
import subprocess

env = dict(os.environ)
# Không thêm checkbox token: đọc secret khi có, không ghi token vào source/output.
try:
    from google.colab import userdata
    token = userdata.get("CIVITAI_TOKEN")
    if token:
        env["CIVITAI_TOKEN"] = token
except Exception:
    pass

# S3/R2 tuỳ chọn: chỉ chuyển giá trị vào environment của process cài/Forge.
# Không in, không ghi vào notebook, settings.json hoặc APK.
S3_SECRETS = (
    "ANIME3_S3_BUCKET", "ANIME3_S3_ENDPOINT_URL", "ANIME3_S3_REGION",
    "ANIME3_S3_ACCESS_KEY_ID", "ANIME3_S3_SECRET_ACCESS_KEY",
    "ANIME3_S3_PREFIX", "ANIME3_S3_SIGNED_TTL",
)
try:
    from google.colab import userdata
    for name in S3_SECRETS:
        try:
            value = userdata.get(name)
            if value:
                env[name] = value
        except Exception:
            pass
except Exception:
    pass

__BOOTSTRAP__
dest = Path("/content/install.sh")
download_installer(dest, BRANCH, env)

args = ["bash", str(dest), "--model", MODEL, "--model-dir", MODEL_DIR,
        "--branch", BRANCH, "--port", str(PORT), "--tunnel", TUNNEL,
        "--cuda", CUDA_INDEX, "--restart"]

print(f"▶ Model {MODEL}; tunnel {TUNNEL}. Giữ model/ảnh đã có, cập nhật code rồi mở Forge.", flush=True)
process = subprocess.Popen(args, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, bufsize=1, start_new_session=True)
try:
    for line in process.stdout:
        print(line, end="", flush=True)
    rc = process.wait()
except KeyboardInterrupt:
    os.killpg(process.pid, signal.SIGTERM)
    process.wait()
    print("Đã dừng. Chạy lại ô để tiếp tục; model .part và ảnh cũ được giữ.")
    raise
finally:
    process.stdout.close()

if rc:
    raise RuntimeError(f"Bộ cài dừng với mã {rc}. Đọc lỗi ngay phía trên; không cần chạy thêm ô khác.")

print("\n✅ Hoàn tất. Dùng link public mới ở phía trên.")
print("▶ Web: mở link → txt2img → Generate.")
print("▶ Android: dán link vào tab Máy chủ; chẩn đoán phải có 'Job nền & file stream'.")
print("▶ Không cài APK: mở <link public>/vi-mobile/")
'''.replace("__BOOTSTRAP__", BOOTSTRAP_SOURCE).replace("__BRANCH__", BRANCH)

AFTER = """### Chỉ khi cần kiểm tra/lấy lại link

```bash
!bash /content/install.sh --status
!bash /content/install.sh --only launch,verify --restart
```

Không cần chạy các ô chẩn đoán, ví dụ API hoặc app Gradio phụ cho thao tác tạo ảnh thông thường. Notebook `WAI_Illustrious_v17_vi.ipynb` vẫn giữ quy trình từng bước khi cần tùy biến sâu.
"""

notebook = {
    "nbformat": 4, "nbformat_minor": 0,
    "metadata": {
        "colab": {"provenance": [], "gpuType": "T4", "name": "WAI v17 — Colab một ô tối giản"},
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
print(f"Đã sinh {OUT.name}: 1 ô code tối giản, nhánh {BRANCH}")
