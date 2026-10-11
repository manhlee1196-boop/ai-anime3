"""Sinh `colab/WAI_Illustrious_v17_vi.ipynb`.

Viết notebook bằng script thay vì sửa tay JSON để tránh lỗi escape và để nội dung
các ô luôn khớp với `setup_forge.sh`. Chạy:  python3 colab/make_notebook.py
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "WAI_Illustrious_v17_vi.ipynb")

cells = []


def md(text):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": text.splitlines(True)})


def code(text):
    cells.append({"cell_type": "code", "execution_count": None, "metadata": {},
                  "outputs": [], "source": text.splitlines(True)})


# =============================================================================
md("""# 🎨 Hệ thống tạo ảnh WAI-Illustrious v17 trên Google Colab
### kèm kho prompt tiếng Việt 349.714 tag Danbooru + e621

Notebook này dựng một hệ sinh ảnh hoàn chỉnh trên Colab:

| Thành phần | Là gì |
|---|---|
| **Model** | `waiIllustriousSDXL_v170.safetensors` — WAI-illustrious-SDXL **v17.0**, SDXL 6,5 GB, VAE tích hợp sẵn |
| **Backend** | **Forge Neo** (nhánh `neo` của `Haoming02/sd-webui-forge-classic`) — đúng phần mềm thẻ model khuyến nghị |
| **Bộ nhắc** | Kho tag Danbooru + e621 đã dịch tiếng Việt của repo này: **45.513 bản dịch** trên 349.714 tag |
| **Gõ tiếng Việt trong ô prompt** | Extension `sd-webui-tagcomplete` + file dịch 2 cột → gõ “áo dài”, “tóc dài”, “đồng phục học sinh” vẫn ra tag |
| **Tab “Prompt VN”** | Extension của repo: tra tag, xếp thứ tự prompt chuẩn Illustrious/WAI, sinh negative, sinh ảnh ngay |

**Yêu cầu:** Colab có GPU (T4 trở lên, ≥12 GB VRAM thì thoải mái hires fix), ~25 GB ổ đĩa trống.
**Thời gian:** cài đặt 8–15 phút (tải model 6,5 GB là lâu nhất), sau đó sinh ảnh ngay.

> ⚠️ Model này **có khả năng tạo nội dung người lớn**. Thẻ model ghi rõ bốn mức phân loại
> `general / sensitive / nsfw / explicit` và khuyên *chủ động thêm “nsfw” vào negative prompt*
> để lọc nội dung. Hệ thống ở đây mặc định để mức **general** và tự đẩy các mức còn lại
> sang negative. Bạn phải tự chịu trách nhiệm tuân thủ pháp luật nơi mình ở, điều khoản
> của Google Colab, và không tạo nội dung vi phạm (đặc biệt là nội dung liên quan trẻ em —
> tag `loli`/`shota` và mọi nội dung tình dục hoá trẻ vị thành niên đều bị cấm).
""")

md("""---
## ⚙️ Ô 1 — Cấu hình (sửa ở đây rồi chạy các ô bên dưới)

Mặc định đã chọn đúng theo thẻ model v17.0. Chỉ cần sửa nếu bạn biết mình muốn gì khác.
""")

code('''import os

# ---- repo chứa kho prompt + code của hệ thống này -----------------------------
os.environ["REPO_DIR"]    = "/content/ai-anime3"
os.environ["REPO_URL"]    = "https://github.com/manhlee1196-boop/ai-anime3"
os.environ["REPO_BRANCH"] = "arena/88f01d31-ai-anime3"   # đúng một nhánh, không fallback sang main/master
# Repo public không cần token GitHub. Nếu cần credential, dùng Colab Secrets,
# không dán token vào source notebook (source sẽ được lưu/chia sẻ).
USE_GITHUB_SECRET = False
USE_CIVITAI_SECRET = False
if USE_GITHUB_SECRET or USE_CIVITAI_SECRET:
    from google.colab import userdata
    for enabled, name in ((USE_GITHUB_SECRET, "GITHUB_TOKEN"), (USE_CIVITAI_SECRET, "CIVITAI_TOKEN")):
        if enabled:
            os.environ[name] = userdata.get(name)

# ---- Forge Neo ---------------------------------------------------------------
os.environ["FORGE_DIR"]    = "/content/sd-webui-forge-neo"
os.environ["FORGE_REPO"]   = "https://github.com/Haoming02/sd-webui-forge-classic"
os.environ["FORGE_BRANCH"] = "neo"
os.environ["PORT"]         = "7860"
os.environ["TUNNEL"]       = "share"        # share | cloudflared | none
os.environ["VRAM_FLAG"]    = ""             # T4 mà bị tràn VRAM thì đặt "--lowvram"

# ---- model WAI-Illustrious v17.0 (FP16 bản gốc, 6,5 GB) ----------------------
os.environ["MODEL_DIR"]  = "/content/sd-webui-forge-neo/models/Stable-diffusion"
os.environ["MODEL_FILE"] = "waiIllustriousSDXL_v170.safetensors"
# SHA256 công bố trên thẻ model Civitai (version 2883731) và khớp với mirror HF
os.environ["MODEL_SHA256"] = "f116b0c78ff441467b0cdc8f1936e1ed18ea31e9997c7b132b1b8db533f0bd04"
# CIVITAI_TOKEN (nếu bật) đã được đọc từ Secrets, không ghi literal vào notebook.

print("Cấu hình đã nạp:")
for k in ("REPO_DIR", "FORGE_DIR", "MODEL_FILE", "TUNNEL", "PORT"):
    print(f"   {k:<12} = {os.environ[k]}")''')

md("""## Ô 2 — Lấy kho prompt (clone repo này)

Cần 4 file CSV ở thư mục gốc repo (`danbooru_e621.csv`, `danbooru_e621_vi.csv`,
`danbooru_e621_nounderscore.csv`, `danbooru_e621_vi_translation.csv`) cùng thư mục
`colab/` chứa `prompt_lib`, extension và `setup_forge.sh`.
""")

code('''import os, base64, subprocess, tempfile
from pathlib import Path

repo = Path(os.environ["REPO_DIR"])
url, branch = os.environ["REPO_URL"], os.environ["REPO_BRANCH"]
required = ("danbooru_e621.csv", "danbooru_e621_vi.csv", "danbooru_e621_nounderscore.csv",
            "danbooru_e621_vi_translation.csv", "colab/setup_forge.sh", "colab/checkpoint_tools.py")
if all((repo / name).is_file() for name in required):
    print("✔ Kho prompt đã có sẵn ở", repo)
elif repo.exists() and any(repo.iterdir()):
    raise RuntimeError("Repo đã có dữ liệu nhưng thiếu file/bản mới. Cập nhật cùng nhánh; không xóa thư mục hay reset hard.")
else:
    repo.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    token = env.get("GITHUB_TOKEN", "").strip()
    if token:
        auth = base64.b64encode(("x-access-token:" + token).encode()).decode()
        env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="http.https://github.com/.extraheader",
                   GIT_CONFIG_VALUE_0="Authorization: Basic " + auth)
    with tempfile.TemporaryDirectory(prefix="wai-repo-", dir=repo.parent) as tmp:
        dest = Path(tmp) / "repo"
        result = subprocess.run(["git", "clone", "--depth", "1", "--branch", branch, url, str(dest)],
                                env=env, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError("Không clone được đúng nhánh. Kiểm tra mạng/quyền GitHub; không chuyển sang nhánh khác.")
        if not all((dest / name).is_file() for name in required):
            raise RuntimeError("Nhánh đã clone thiếu file. Giữ dữ liệu hiện tại, không chạy stage tiếp theo.")
        if repo.exists():
            repo.rmdir()  # chỉ chấp nhận thư mục rỗng; không xóa dữ liệu người dùng
        dest.rename(repo)
    print("✔ Đã clone đúng nhánh", branch)
for path in repo.glob("*.csv"):
    print(f"   {path.name}: {path.stat().st_size:,} byte")''')

md("""## Ô 3 — Kiểm tra GPU, ổ đĩa, driver

Ô này cũng quyết định sẽ cài bản PyTorch nào (`cu130` nếu driver hỗ trợ CUDA 13,
ngược lại `cu128`).
""")

code('''import os, subprocess
subprocess.run(["bash", os.path.join(os.environ["REPO_DIR"], "colab/setup_forge.sh"), "gpu"], check=True)''')

md("""## Ô 4 — Cài Forge Neo

`uv` tạo môi trường Python 3.13 riêng (Colab chỉ có 3.11/3.12), mất ~1 phút.
""")

code('''import os, subprocess
subprocess.run(["bash", os.path.join(os.environ["REPO_DIR"], "colab/setup_forge.sh"), "forge"], check=True)''')

md("""## Ô 5 — Cài PyTorch phù hợp với driver

Script thử `cu130` → `cu128` → `cu126`, import torchvision và **chạy tensor/kernel CUDA
thật sau mỗi lần cài**; `cuda.is_available()` một mình chưa đủ để kiểm tra T4.
""")

code('''import os, subprocess
subprocess.run(["bash", os.path.join(os.environ["REPO_DIR"], "colab/setup_forge.sh"), "torch"], check=True)''')

md("""## Ô 6 — Tải WAI-illustrious-SDXL v17.0 (6,5 GB)

Tải từ mirror HuggingFace (không cần token), có **tải tiếp nếu đứt giữa chừng** và
**kiểm SHA256** sau khi tải. Nếu mirror hỏng, script tự thử mirror thứ hai, rồi
báo lỗi nếu cả hai mirror đều không tải được. Không tự đổi checkpoint/phiên bản.
""")

code('''import os, subprocess
subprocess.run(["bash", os.path.join(os.environ["REPO_DIR"], "colab/setup_forge.sh"), "model"], check=True)''')

md("""## Ô 7 — Cắm kho prompt tiếng Việt vào Forge

Ô này làm 6 việc:
1. Tải upscaler `RealESRGAN_x4plus_anime_6B.pth` (thẻ model khuyên dùng cho hires fix).
2. Sinh `wai-illustrious-system-tags.csv` — các tag hệ thống Illustrious/WAI mà danh sách
   Danbooru **không có** (`rating_general`, `rating_explicit`, `masterpiece`, `newest`,
   `very awa`, `source_anime`…) để chúng vẫn được gợi ý khi gõ.
3. Sinh `danbooru_e621_vi_translation_wai.csv` — bản dịch của kho + tag hệ thống.
4. Cài `sd-webui-tagcomplete` và chép 3 file CSV vào thư mục `tags/` của nó.
5. Ghi sẵn `config.json`: chọn tag file, file dịch tiếng Việt, bật tìm bằng tiếng Việt,
   bật hiện nghĩa tiếng Việt dưới ô prompt, và đặt **CLIP stop = 2**.
6. Cài extension **Prompt VN** và tạo `styles.csv` với 4 mức phân loại.
""")

code('''import os, subprocess
subprocess.run(["bash", os.path.join(os.environ["REPO_DIR"], "colab/setup_forge.sh"), "extras"], check=True)''')

md("""## Ô 8 — Chạy Forge (ô này sẽ chạy liên tục, đừng ngắt)

Đợi tới khi thấy dòng `Running on public URL: https://xxxx.gradio.live` thì bấm link đó.
Lần khởi động đầu mất 3–8 phút vì Forge tự cài nốt `requirements.txt`.

**Sau khi mở giao diện:**
- Tab **`Prompt VN`** — bộ dựng prompt tiếng Việt (tra tag, xếp thứ tự, sinh negative,
  sinh ảnh ngay trong tab).
- Ô prompt của **txt2img** — gõ thử `áo dài`, `tóc dài`, `đồng phục học sinh`: tagcomplete
  sẽ gợi ý tag tiếng Anh kèm nghĩa tiếng Việt.
- Nút **Styles** — chọn `WAI v17 — An toàn — general` để nạp cả positive lẫn negative mẫu.

Tham số mặc định nên dùng (theo thẻ model): **Euler a · 25 bước · CFG 6 · 1024×1344 ·
Hires fix 1.5× với `RealESRGAN_x4plus_anime_6B`, 20 bước, denoise 0.4 · CLIP stop 2**.
""")

code('''import os, subprocess
subprocess.run(["bash", os.path.join(os.environ["REPO_DIR"], "colab/setup_forge.sh"), "launch"], check=True)''')

md("""---
## 🔧 Ô 9 (tuỳ chọn) — Chạy Forge ở chế độ nền

Muốn dùng thêm ô khác trong khi Forge đang chạy (ví dụ sinh ảnh bằng API từ notebook,
hoặc mở app dựng prompt riêng) thì dùng ô này **thay cho Ô 8**.
""")

code('''import os, subprocess
subprocess.run(["bash", os.path.join(os.environ["REPO_DIR"], "colab/setup_forge.sh"), "launch-bg"], check=True)''')

md("""## 🔧 Ô 10 (tuỳ chọn) — Sinh ảnh thẳng từ notebook bằng API

Không cần mở giao diện: dựng prompt bằng `prompt_lib` rồi gọi `/sdapi/v1/txt2img`.
Chỉ chạy được khi Forge đang chạy (Ô 8 hoặc Ô 9).
""")

code('''import os, sys, base64, requests
from pathlib import Path

REPO = os.environ["REPO_DIR"]
sys.path.insert(0, os.path.join(REPO, "colab"))
from prompt_lib import PromptBuilder, TagIndex          # noqa: E402

index   = TagIndex(REPO)
builder = PromptBuilder(index)

# 1) Tra tag bằng tiếng Việt
for q in ("áo dài", "tóc dài", "hoa anh đào", "nhìn vào người xem"):
    hits = index.search(q, limit=1)
    print(f"   {q:<22} -> {hits[0].tag if hits else '(không thấy)'}")

# 2) Dựng prompt đúng thứ tự Illustrious/WAI
out = builder.assemble(
    "1girl, ao_dai, long_hair, red_eyes, looking_at_viewer, holding_sword, "
    "cherry_blossoms, simple_background",
    description="Một cô gái mặc áo dài đứng dưới cơn mưa hoa anh đào",
    rating_id="general",
    quality_preset="WAI khuyến nghị (đầy đủ)",
)
negative = builder.negative("general", "Chuẩn cộng đồng (đầy đủ)")
print("\\nPROMPT :", out["prompt"])
print("NEGATIVE:", negative[:110], "...")

# 3) Gọi API của Forge (tham số đúng thẻ model v17.0)
url = f'http://127.0.0.1:{os.environ.get("PORT", 7860)}'
available = [u["name"] for u in requests.get(url + "/sdapi/v1/upscalers", timeout=30).json()]
payload = builder.payload(out["prompt"], negative, {
    "steps": 25, "cfg_scale": 6.0, "sampler_name": "Euler a", "seed": -1,
    "width": 1024, "height": 1344, "enable_hr": True, "hr_scale": 1.5,
    "hr_second_pass_steps": 20, "denoising_strength": 0.4,
    "override_settings": {"clip_stop_at_last_layers": 2},
})
builder.fix_upscaler(payload, available)     # Forge Neo đặt tên upscaler theo tên file
print("UPSCALER:", payload["hr_upscaler"])

r = requests.post(url + "/sdapi/v1/txt2img", json=payload, timeout=1800)
r.raise_for_status()
out_dir = Path(REPO) / "colab" / "outputs"; out_dir.mkdir(parents=True, exist_ok=True)
info = r.json()["info"]
for i, b64 in enumerate(r.json()["images"]):
    path = out_dir / f'wai17_seed{info["seed"]}_{i}.png'
    path.write_bytes(base64.b64decode(b64.split(",", 1)[-1]))
    print("   đã lưu", path)''')

md("""## 🔧 Ô 11 (tuỳ chọn) — Mở app dựng prompt tiếng Việt thành giao diện riêng

App này là bản độc lập của tab **Prompt VN**, chạy ở cổng 7861 và gọi API của Forge.
Dùng khi bạn muốn một cửa sổ riêng chỉ để soạn prompt. Cần Forge đang chạy nền (Ô 9).
""")

code('''import os, time

forge_py = os.path.join(os.environ["FORGE_DIR"], "venv", "bin", "python")
if not os.path.exists(forge_py):
    raise SystemExit("✖ Chưa có Forge. Hãy chạy Ô 4 (forge) và Ô 9 (launch-bg) trước.")

# app dùng chung môi trường của Forge (đã có sẵn gradio + requests), không cần cài thêm
log = "/content/prompt_builder.log"
get_ipython().system(
    f'cd "{os.environ["REPO_DIR"]}" && '
    f'VI_PROMPT_ROOT="{os.environ["REPO_DIR"]}" nohup "{forge_py}" colab/prompt_builder.py '
    f'--forge-url "http://127.0.0.1:{os.environ.get("PORT", 7860)}" '
    f'--port 7861 --share > {log} 2>&1 &'
)

for _ in range(90):
    txt = open(log, encoding="utf-8", errors="ignore").read()
    if "gradio.live" in txt:
        link = next(l for l in txt.splitlines() if "gradio.live" in l)
        print("✔ Link app dựng prompt tiếng Việt:")
        print("   ", link.strip())
        break
    if "Traceback" in txt:
        print("✖ App lỗi:\\n", txt[-2000:]); break
    time.sleep(2)
else:
    print("Chưa thấy link, log hiện tại:\\n", open(log, encoding="utf-8", errors="ignore").read()[-1500:])''')

md("""---
## 🚑 Xử lý sự cố

| Triệu chứng | Nguyên nhân / cách xử lý |
|---|---|
| `Không thấy nvidia-smi` | Chưa bật GPU: **Runtime → Change runtime type → T4 GPU** |
| `PyTorch is not able to access any compute device` | Driver cũ hơn bản torch: chạy lại Ô 5 (script tự lùi `cu128`/`cu126`), hoặc đặt `os.environ["TORCH_INDEX"]="cu126"` rồi chạy lại Ô 5 |
| Tải model báo `SHA256 KHÔNG khớp` | Mirror trả file hỏng; script tự thử mirror kế. Muốn chắc chắn, điền `CIVITAI_TOKEN` ở Ô 1 |
| Không đủ ổ đĩa | FP16 cần ~7 GB model + ~12 GB Forge/venv. Dọn file không dùng; muốn đổi precision dùng notebook một ô, **không chỉ đổi MODEL_FILE** |
| Ô Checkpoint trống dù file tồn tại | Cập nhật bộ cài 1.0.2: preset `xl` cần cả `sd_model_checkpoint` và `forge_checkpoint_xl`; xem `colab/INSTALL.md` |
| Link `gradio.live` không mở được | Đổi `os.environ["TUNNEL"]="cloudflared"` ở Ô 1 rồi chạy lại Ô 8 |
| Tab **Prompt VN** báo “Không tìm thấy prompt_lib” | Ô 2 chưa chạy thành công: kiểm tra `ls /content/ai-anime3`, hoặc đặt `os.environ["VI_PROMPT_ROOT"]` rồi chạy lại Ô 7 + Ô 8 |
| Gõ tiếng Việt không ra gợi ý | Vào **Settings → Tag autocomplete** kiểm tra *Tag filename* = `danbooru_e621.csv`, *Translation filename* = `danbooru_e621_vi_translation_wai.csv`, và **bỏ** tuỳ chọn “old 3-column format” |
| Ảnh bị mờ/vỡ nét khi hires fix | Đổi upscaler sang `RealESRGAN_x4plus_anime_6B` (Ô 7 đã tải sẵn); hạ denoising còn 0.35 |
| Tràn VRAM khi hires fix ở 1024×1344 | Đặt `os.environ["VRAM_FLAG"]="--lowvram"` ở Ô 1, chạy lại Ô 7 → Ô 8; hoặc tắt hires fix |
| Mất hết khi ngắt phiên | Dữ liệu `/content` không được giữ qua phiên. Tải ảnh về trước khi ngắt; phiên mới phải cài/tải lại. Notebook không mount Drive |

## 📌 Ghi chú về kho prompt
- Tag file dùng cho tagcomplete là **bản tiếng Anh có dấu `_`** (`danbooru_e621.csv`),
  vì chính extension sẽ thay `_` bằng khoảng trắng lúc chèn tag — và nó đã có sẵn danh
  sách loại trừ cho emoticon (`^_^`, `o_o`, `|_|`…), trùng với cách repo này xử lý.
- File dịch là **2 cột** đúng chuẩn mới của tagcomplete, nên phải **để tắt** tuỳ chọn
  “old 3-column format”.
- 45.513 tag có nghĩa tiếng Việt; phần còn lại là tên riêng (hoạ sĩ, nhân vật, series)
  vốn không dịch.
""")

# =============================================================================
notebook = {
    "nbformat": 4,
    "nbformat_minor": 0,
    "metadata": {
        "colab": {
            "provenance": [],
            "gpuType": "T4",
            "name": "WAI-Illustrious v17 + kho prompt tiếng Việt",
            "collapsed_sections": [],
        },
        "kernelspec": {"name": "python3", "display_name": "Python 3"},
        "language_info": {"name": "python"},
        "accelerator": "GPU",
    },
    "cells": cells,
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(notebook, f, ensure_ascii=False, indent=1)
    f.write("\n")

code_cells = sum(1 for c in cells if c["cell_type"] == "code")
print(f"Đã sinh {OUT}")
print(f"   {len(cells)} ô ({code_cells} ô code, {len(cells) - code_cells} ô markdown), "
      f"{os.path.getsize(OUT):,} byte")
