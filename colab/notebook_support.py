"""Nội dung dùng chung khi sinh notebook; các ô đã xuất không cần import file này."""

MIN_INSTALLER_VERSION = "1.0.7"

BOOTSTRAP_SOURCE = r'''import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

MIN_INSTALLER_VERSION = "__MIN_VERSION__"


def checked_installer_version(data):
    if not data.startswith(b"#!/usr/bin/env bash") or len(data) < 5000:
        raise ValueError("Không phải script bộ cài đầy đủ")
    match = re.search(rb'^INSTALLER_VERSION=[\'"](\d+\.\d+\.\d+)[\'"]$', data, re.M)
    if not match:
        raise ValueError("Không đọc được phiên bản bộ cài")
    version = match[1].decode("ascii")
    if tuple(map(int, version.split("."))) < tuple(map(int, MIN_INSTALLER_VERSION.split("."))):
        raise ValueError(f"Bộ cài quá cũ; cần từ {MIN_INSTALLER_VERSION}")
    return version


def download_installer(dest, branch, env):
    owner_repo = "manhlee1196-boop/ai-anime3"
    raw = f"https://raw.githubusercontent.com/{owner_repo}/{branch}/colab/install.sh"
    api = (f"https://api.github.com/repos/{owner_repo}/contents/colab/install.sh?ref="
           + urllib.parse.quote(branch, safe=""))
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".sh.tmp")
    for url in (raw, api):
        headers = {"Accept": "application/vnd.github.raw", "User-Agent": "wai-colab-installer/1.0.7"}
        if env.get("GITHUB_TOKEN"):
            headers["Authorization"] = f"Bearer {env['GITHUB_TOKEN']}"
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read()
            version = checked_installer_version(data)
            tmp.write_bytes(data)
            subprocess.run(["bash", "-n", str(tmp)], check=True, capture_output=True)
            tmp.replace(dest)
            print(f"✔ Đã lấy bộ cài {version} từ nhánh {branch}.", flush=True)
            return version
        except (OSError, ValueError, subprocess.CalledProcessError, urllib.error.URLError):
            continue
        finally:
            if tmp.exists():
                tmp.unlink()  # chỉ file tạm do ô này tạo; không đụng model/repo/ảnh
    # Mất mạng chỉ dùng cache đủ mới/hợp lệ; bản 1.0.7 cần source bảng ảnh đã tạo.
    try:
        version = checked_installer_version(dest.read_bytes())
        subprocess.run(["bash", "-n", str(dest)], check=True, capture_output=True)
    except (OSError, ValueError, subprocess.CalledProcessError):
        raise RuntimeError(
            f"Không lấy được bộ cài >= {MIN_INSTALLER_VERSION}. Kiểm tra mạng hoặc mở lại notebook mới; "
            "chưa chạy cài đặt và không xóa dữ liệu cũ."
        ) from None
    print(f"⚠ Không lấy được bản mới; dùng cache đã kiểm tra {version} trong /content.", flush=True)
    return version
'''.replace("__MIN_VERSION__", MIN_INSTALLER_VERSION)

WORKFLOW_GUIDE = """### Quy trình mới trong Prompt VN (1.0.3)

1. Nhập `1girl, (áo dài:1.2), tóc dài`, chọn kết quả hoặc bấm **Thay mục Việt → tag Anh**.
   Kết quả thay tại chỗ: `1girl, (ao_dai:1.2), long_hair`; giữ tag khác/trọng số,
   không giữ cả chữ Việt + Anh hoặc tự xóa toàn bộ prompt.
2. **Dựng prompt**, bắt đầu **Nháp** hoặc **Chuẩn**, mặc định **832×1216, Hires tắt**.
3. Chọn một ảnh trong Gallery → **Dùng seed của ảnh đã chọn** (không chọn ảnh lưới).
4. Chuyển **Hoàn thiện**: Hires 1.5×, denoise 0.35, tự đặt **1 ảnh/lượt** và giữ sampler.
   Preset áp lại steps/CFG; cùng seed không bảo đảm ảnh giữ nguyên khi thay tham số.

| Mức | FP16 | FP8/INT8 | HSWQ | Hires |
|---|---|---|---|---|
| Nháp | 18 bước / CFG 6 | 18 / 6.5 | 10 / 1 | Tắt |
| Chuẩn | 25 / 6 | 25 / 6.5 | 10 / 1 | Tắt |
| Hoàn thiện | 25 / 6 | 25 / 6.5 | 10 / 1 | 1.5×, denoise .35; 20 bước (HSWQ 10) |

Nhiều ảnh chạy tuần tự (`batch_size=1`), không tăng batch để tiết kiệm VRAM.
Đây là preset ứng dụng, chưa phải benchmark tốc độ/chất lượng trên GPU Colab.
**Sinh ảnh** trong Prompt VN dùng các tham số trên; **Đưa vào txt2img** chỉ chuyển
prompt, không chuyển sampling. Điền txt2img mặc định ghép/thay mục tương ứng;
**Thay toàn bộ** phải bật rõ ràng và có **Hoàn tác** trong phiên trình duyệt.

### 🗂️ Bảng ảnh đã tạo (1.0.7)

Trong **Prompt VN → Ảnh đã tạo**, bấm **Làm mới** để xem ảnh cũ từ output của
Forge (txt2img/img2img), ảnh mới từ Prompt VN và ví dụ notebook. Có thumbnail,
12/24 ảnh mỗi trang, bảng thời gian/seed/kích thước/dung lượng. Chọn thumbnail
hoặc một dòng để **xem/tải ảnh gốc** và **Dùng seed ảnh lịch sử**.
Chỉ điền seed, không tự thay prompt/sampling; ảnh lưới/ảnh không có seed không
được dùng lại seed. File gốc/metadata không bị sửa, thumbnail WebP chỉ là preview.

Chỉ mục SQLite/preview lưu trên đĩa; State chỉ giữ id nhỏ, không tích lũy toàn bộ
PIL/base64. Lịch sử đọc lại được sau restart Forge, nhưng `/content` vẫn mất khi
xóa runtime. Không tự mount Drive. Album này **không phải bản vá đã xác định cho
RAM của Forge tăng sau nhiều ảnh**. Người có link UI cũng có thể xem album.
"""

API_SAMPLE_SOURCE = r'''#@title 🖼️ Ví dụ API — chỉ sinh khi bật RUN_API_SAMPLE { display-mode: "form" }
RUN_API_SAMPLE = False #@param {type:"boolean"}
MODE = "Nháp" #@param ["Nháp", "Chuẩn", "Hoàn thiện"]
SELECTED_TAGS = "1girl, (áo dài:1.2), tóc dài, cherry_blossoms, looking_at_viewer" #@param {type:"string"}
SEED = -1 #@param {type:"integer"}
IMAGE_COUNT = 1 #@param {type:"integer"}


def generate_notebook_sample():
    import os
    import sys
    from datetime import datetime
    from pathlib import Path
    import requests

    repo = Path(os.environ["REPO_DIR"])
    sys.path.insert(0, str(repo / "colab"))
    from prompt_lib import PromptBuilder, TagIndex, WAI_DEFAULTS
    from prompt_lib.api import decode_generation_response
    from prompt_lib.editing import convert_tags
    from prompt_lib.generate import read_timeout, timeouts
    from prompt_lib.workflow import (WORKFLOW_PRESETS, workflow_settings, validate_generation,
                                     generation_metadata, generation_error, seed_at)

    label = next(label for label, mode in WORKFLOW_PRESETS.items()
                 if mode == {"Nháp": "draft", "Chuẩn": "standard", "Hoàn thiện": "final"}[MODE])
    steps, cfg, sampler, hires, scale, hr_steps, denoise = workflow_settings(label)
    if hires and SEED == -1:
        raise ValueError("Hoàn thiện: nhập seed của ảnh đã chọn ở lần Nháp/Chuẩn trước; không dùng seed ảnh lưới.")
    index = TagIndex(repo)
    builder = PromptBuilder(index)
    converted, changes, unknown = convert_tags(SELECTED_TAGS, index)
    print("Tag sau thay Việt → Anh:", converted)
    if unknown:
        print("Mục chưa rõ được giữ nguyên:", ", ".join(unknown))
    out = builder.assemble(converted, rating_id="general", quality_preset="Ngắn gọn")
    negative = builder.negative("general", "WAI khuyến nghị (ngắn)")
    payload = validate_generation(builder.payload(out["prompt"], negative, {
        "steps": steps, "cfg_scale": cfg, "sampler_name": sampler, "seed": SEED,
        "width": 832, "height": 1216, "enable_hr": hires, "hr_scale": scale,
        "hr_second_pass_steps": hr_steps, "denoising_strength": denoise,
        "batch_size": 1, "n_iter": 1 if hires else IMAGE_COUNT,
        "override_settings": {"clip_stop_at_last_layers": WAI_DEFAULTS["clip_skip"]},
        "save_images": True, "send_images": True,
    }))
    url = f'http://127.0.0.1:{os.environ.get("PORT", "7860")}'
    print(f"▶ {MODE}: {steps} bước / CFG {cfg} / {sampler} / Hires {hires}; {payload['n_iter']} ảnh tuần tự.")
    try:
        if hires:
            response = requests.get(url + "/sdapi/v1/upscalers", timeout=15)
            response.raise_for_status()
            builder.fix_upscaler(payload, [item["name"] for item in response.json() if item.get("name")])
        # connect ngắn + read dài (WAI_GEN_TIMEOUT, mặc định 15 phút) để không treo 30 phút
        response = requests.post(url + "/sdapi/v1/txt2img", json=payload, timeout=timeouts())
        response.raise_for_status()
        images, info = decode_generation_response(response.json())  # info JSON-string + PNG → PIL
    except Exception as exc:
        raise RuntimeError(generation_error(exc, timeout=read_timeout())) from None
    metadata = generation_metadata(info, payload, len(images))
    output = repo / "colab" / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    paths = []
    for i, image in enumerate(images):
        image_seed = seed_at(metadata, i)
        suffix = f"seed{image_seed}" if image_seed is not None else "grid-or-unknown-seed"
        path = output / f"wai17_{stamp}_{i}_{suffix}.png"
        image.save(path, format="PNG")
        paths.append(str(path))
        print("✔ Đã lưu", path)
    print("Seed từng ảnh (trừ grid):", metadata["seeds"], "· grid offset:", metadata["grid_offset"])
    print("Ảnh /content mất khi kết thúc runtime; tải về trước khi ngắt.")
    return {"metadata": metadata, "paths": paths, "converted_tags": converted}


if RUN_API_SAMPLE:
    API_LAST_RESULT = generate_notebook_sample()
else:
    print("Bỏ qua sinh ảnh API. Dùng tab Prompt VN, hoặc bật RUN_API_SAMPLE khi Forge đã chạy.")
'''


# ------------------------------------------------------------------ nhánh nguồn
import os
import subprocess
from pathlib import Path as _Path


def current_branch():
    """Nhánh đang checkout — notebook Colab phải tải đúng nhánh này."""
    root = _Path(__file__).resolve().parent.parent
    try:
        r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root,
                           capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return "main"
    branch = r.stdout.strip()
    return branch if r.returncode == 0 and branch and branch != "HEAD" else "main"


BRANCH = os.environ.get("WAI_BRANCH") or current_branch()
