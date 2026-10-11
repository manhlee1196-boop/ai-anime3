# Bộ cài Colab một lệnh — WAI-Illustrious v17

Cài **Forge Neo + checkpoint WAI v17 + tagcomplete + kho prompt tiếng Việt + tab Prompt VN**.
Có chọn model, chọn thư mục lưu, xác minh SHA256 và chạy lại để tiếp tục phần còn dở.
Mặc định model/ảnh/log đều ở `/content`. **Không có bước mount Google Drive.**

## 1. Cách dễ nhất: notebook một ô

[**Mở bộ cài trong Google Colab**](https://colab.research.google.com/github/manhlee1196-boop/ai-anime3/blob/arena%2F88f01d31-ai-anime3/colab/WAI_v17_1click.ipynb)

Hoặc tải [`WAI_v17_1click.ipynb`](WAI_v17_1click.ipynb), rồi Colab → File → Upload notebook.

1. **Runtime → Change runtime type → GPU T4** (hoặc L4/A100).
2. Chọn `MODEL` ở dropdown; mặc định **fp16**. `MODEL_DIR=/content/models`.
3. Chạy ô cài duy nhất, chờ kiểm tra đạt rồi mở link public được in ra.
4. Trong Forge, dùng **Prompt VN** hoặc gõ tiếng Việt ngay trong ô prompt.

Cần khoảng **25 GB trống**. Lần đầu có thể mất **10–25 phút**, tùy mạng và runtime.
Notebook có đúng **1 ô code**, cùng 2 ô hướng dẫn; không cần chạy lần lượt các stage.

> Nhánh hiện tại là `arena/88f01d31-ai-anime3`, vì bộ cài chưa nằm trên `main`.
> Chỉ đổi nhánh trong link/lệnh khi thay đổi đã được gộp vào nhánh đó.

## 2. Dán một dòng vào Colab

Sau khi bật GPU, dán vào một ô code:

```python
!curl -fsSL --retry 3 "https://raw.githubusercontent.com/manhlee1196-boop/ai-anime3/arena/88f01d31-ai-anime3/colab/install.sh" -o /content/install.sh && bash /content/install.sh --model fp16
```

Đổi `--model fp16` thành `--model fp8`, `--model int8` hoặc `--model hswq` để chọn biến thể.
Thư mục tùy chọn, ví dụ `--model-dir /content/wai-models`.
Các bản cộng đồng có thể cần quyền tải/token Civitai; nên dùng notebook và Colab Secrets
nếu cần token. **Không dán token vào lệnh hoặc URL.**

Nếu raw GitHub không truy cập được, lấy script qua API:

```python
!curl -fsSL -H "Accept: application/vnd.github.raw" "https://api.github.com/repos/manhlee1196-boop/ai-anime3/contents/colab/install.sh?ref=arena%2F88f01d31-ai-anime3" -o /content/install.sh && bash /content/install.sh --model fp16
```

Repo public nên **không cần GitHub token**. Notebook tự thử raw GitHub rồi API; script
tải về được kiểm tra cú pháp và thay thế nguyên tử, không chạy bản tải dở.

## 3. Chọn model

| ID | Dung lượng xấp xỉ | CFG / steps mặc định | Nguồn / trạng thái |
|---|---|---|---|
| **fp16** ⭐ | 6,46 GiB | 6.0 / 25 | **Bản gốc FP16 pruned** của WAI0731; mirror HuggingFace, SHA256 đã biết |
| fp8 | 4,07 GiB | 6.5 / 25 | FP8 e4m3 cộng đồng; Civitai API; **thử nghiệm** |
| int8 | 4,39 GiB | 6.5 / 25 | INT8 convrot cộng đồng; Civitai API; **thử nghiệm** |
| hswq | 4,43 GiB | 1.0 / 10 | HSWQ turbo merge (DMD2/Stabilizer IL/SPO); **thử nghiệm** |

Bản FP16 gốc **đã là pruned**, không tạo một lựa chọn “pruned” giả khác.
Dung lượng chính xác được lấy từ metadata API, không dùng kích thước file để thay thế SHA256.
Các preset dùng Euler a và clip skip 2. Tab Prompt VN/app Gradio tự đổi CFG, steps và
hires steps theo profile đã lưu; bản turbo không dùng mặc định CFG 6 của bản gốc.

- **T4 không có tensor core FP8**. Checkpoint nhỏ hơn không đảm bảo chạy nhanh hơn,
  và một số định dạng lượng tử hóa phụ thuộc backend/GPU. FP16 là mặc định khuyến nghị.
- Bộ cài chỉ chọn **đúng tên file v17**. Không thấy file đó thì báo lỗi, không tự lấy
  v16/v18 hoặc model khác chỉ vì có cùng precision.
- Mặc định **không tự đổi model** nếu metadata Civitai không lấy được.
  Chỉ cho phép fallback khi có `--fallback-fp16` (hoặc bật `FALLBACK_FP16` trong notebook).
- Bộ cài không né paywall, nội dung bị giới hạn, hoặc yêu cầu cấp quyền tải.
  Bạn cần tài khoản/quyền phù hợp ở nhà cung cấp.

Xem catalog mà không cài gì:

```python
!bash /content/install.sh --print-models
```

### Civitai token qua Secrets

Colab → biểu tượng chìa khóa **Secrets** → thêm `CIVITAI_TOKEN` → bật Notebook access.
Trong notebook một ô, đặt `USE_CIVITAI_SECRET=True`.

Nếu chạy một ô Python khác để đổi model:

```python
import os, subprocess
from google.colab import userdata

subprocess.run(
    ["bash", "/content/install.sh", "--model", "fp8", "--only", "model,launch,verify"],
    env={**os.environ, "CIVITAI_TOKEN": userdata.get("CIVITAI_TOKEN")},
    check=True,
)
```

Token truyền bằng environment/header, không được ghi vào URL origin Git, cấu hình
đã lưu hoặc source notebook. Log có che token/query credential; không công khai
notebook có output chứa thông tin riêng. Forge/extension không giữ các token tải/clone.

## 4. Chạy lại, sửa và đổi model

| Nhu cầu | Lệnh trong ô Colab mới |
|---|---|
| Xem trạng thái + link | `!bash /content/install.sh --status` |
| Kiểm tra, không cài/sửa gì | `!bash /content/install.sh --doctor` |
| Cài xong nhưng chưa mở UI | `!bash /content/install.sh --no-launch` |
| Tải/cắm lại model và kho prompt | `!bash /content/install.sh --only model,extras` |
| Khởi động lại + kiểm tra | `!bash /content/install.sh --only launch,verify --restart` |
| Đổi model đã chọn | `!bash /content/install.sh --model hswq --only model,launch,verify` (cần token nếu nhà cung cấp yêu cầu) |
| Cập nhật repo sạch + extension | `!bash /content/install.sh --only repo,extras,launch,verify --restart` |
| Chạy lại các bước | `!bash /content/install.sh --force` |
| Xóa lịch sử stage, không xóa dữ liệu | `!bash /content/install.sh --clean` |
| Xem cờ khác | `!bash /content/install.sh --help` |

`--only` buộc chạy lại các stage được chỉ định, kể cả đã có marker. `--skip torch`
bỏ qua bước torch. `--force` không xóa model đã khớp SHA256 và **không gỡ/xóa ảnh**.

### Cách bộ cài bảo đảm chạy lại an toàn

- Thứ tự: `preflight → repo → forge → torch → model → extras → launch → verify`.
- Một stage chỉ có marker `.ok` khi **thật sự thành công**; mã lỗi được truyền ra notebook.
- Kiểm tra file/cấu hình còn tồn tại trước khi bỏ qua stage; marker cũ không đủ để
  coi model/API đang hoạt động.
- File model tải vào `.safetensors.part`; mất mạng giữ phần tải dở để tải tiếp.
  Chỉ đổi tên thành checkpoint sau khi SHA256 khớp.
- SHA256 được kiểm tra lại khi chạy stage model/verify. Cấu hình giữ biến thể và đường
  dẫn đã chọn, nhưng không lưu token/URL tải riêng.
- Có khóa chống hai bộ cài chạy đồng thời. Không khởi động process Forge thứ hai nếu
  process cũ đang chạy/khởi động cùng cấu hình.
- Đổi model/cấu hình sẽ khởi động lại **chỉ process do bộ cài quản lý**. Cổng bị dịch vụ
  khác chiếm thì báo lỗi, không tự kill nó.
- Repo sạch cùng nhánh được cập nhật **fast-forward only**. Có thay đổi local hoặc khác
  origin/nhánh thì giữ nguyên; **không dùng reset hard, không tự chuyển nhánh**.
- `--doctor` chỉ thăm dò/kiểm tra, không cài dependencies, không thay marker/cấu hình.
  Trả exit 1 khi phát hiện lỗi; không phải một bước cài thất bại mới.

## 5. Thư mục và log

```text
/content/
  install.sh                 bộ cài được tải về
  ai-anime3/                 kho tag + prompt_lib
    colab/assets/            CSV cho tagcomplete + profile model
  sd-webui-forge-neo/         Forge, venv, extension, ảnh outputs/
  models/                    checkpoint (hoặc thư mục bạn chọn)
  .wai_state/                markers, settings.json, model.json, khóa cài
  .wai_torch_env             cấu hình PyTorch phù hợp GPU
  forge.pid  cloudflared.pid PID do bộ cài quản lý
  wai_install.log            log cài đặt
  forge.log                  log Forge
  cloudflared.log            link/log tunnel
  bin/cloudflared            binary tunnel
```

Forge nhận `--ckpt-dirs MODEL_DIR` để nhìn thấy model ở thư mục tùy chọn; checkpoint
đã chọn được ghi vào cấu hình. Không phụ thuộc symlink thủ công hoặc thứ tự quét file.

```python
!tail -50 /content/wai_install.log
!tail -50 /content/forge.log
```

Mọi thứ trong `/content` mất khi runtime kết thúc. Tải ảnh về trước khi ngắt phiên;
phiên mới cần cài/tải lại. Không có thủ thuật giữ runtime luôn hoạt động.

## 6. Xử lý sự cố

### `EOFError` tại `verify_version()` / “Press Enter to Continue…”

**Đã sửa ở bộ cài 1.0.1.** Bản 1.0.0 tạo `config.json` trước lần mở Forge đầu tiên
nhưng thiếu `VERSION_UID`. Forge tưởng đó là cấu hình của bản cũ, yêu cầu Enter;
process chạy nền có stdin đóng nên nhận `EOFError`. Đây không phải lỗi checkpoint.

Trong **runtime đang dùng**, chạy ô dưới đây để cập nhật script và chỉ mở lại UI.
**Không reset runtime, không tải lại model, không cài lại Torch.** Nếu repo có xung đột
Git, dừng và giữ thay đổi local; không dùng `reset --hard`.

```bash
%%bash
set -euo pipefail
git -C /content/ai-anime3 pull --ff-only origin arena/88f01d31-ai-anime3
cp /content/ai-anime3/colab/{install,setup_forge}.sh /content/
bash /content/install.sh --only launch,verify --restart
```

Nếu dùng `REPO_DIR`/`RUNTIME_DIR` khác mặc định, thay hai đường dẫn `/content/ai-anime3`
và `/content` trong ô cho đúng chỗ đã cài. Copy **cả hai** script để không dùng nhầm
`/content/setup_forge.sh` cũ nếu nó còn từ notebook chạy từng bước.

Bản sửa đọc `VERSION_UID` từ `modules/launch_utils.py` của chính Forge đã clone, bằng
AST và không import Torch. Trước cả stage extras và launch, nó khởi tạo cấu hình mới
hoặc bổ sung UID cho cấu hình tối thiểu do bộ cài tạo. Config đã tồn tại được sao lưu
thành `config.json.wai-backup-*` trước khi bổ sung; giữ nguyên tagcomplete/CLIP/checkpoint
và không sửa `ui-config.json`. Không bơm Enter, không vá `input()`, không bỏ guard của Forge.

#### Nếu là cấu hình Forge cũ thật sự

UID khác, UID không hợp lệ hoặc config không UID nhưng có các tùy chọn legacy khác:
bộ cài **dừng thay vì gắn nhãn phiên bản mới**. Chỉ khi bạn muốn đặt lại tùy chọn UI,
sao lưu **hai file cấu hình** như Forge đề nghị; không xóa cả thư mục Forge/venv/model.
Ô sau đổi tên cấu hình vào một thư mục backup rồi cắm lại tagcomplete và mở Forge:

```bash
%%bash
set -euo pipefail
forge=/content/sd-webui-forge-neo
backup=$(mktemp -d "$forge/config-backup.XXXXXXXX")
chmod 700 "$backup"
for name in config.json ui-config.json; do
  if [[ -f "$forge/$name" ]]; then mv -- "$forge/$name" "$backup/$name"; fi
done
printf 'Đã sao lưu cấu hình: %s\n' "$backup"
bash /content/install.sh --only extras,launch,verify --restart
```

Chỉ dùng ô reset này **sau khi đã cập nhật script ở trên**, khi Forge không đang chạy
và bạn chấp nhận đặt lại tùy chọn UI. Với lỗi config mới của bản 1.0.0, **không cần** ô này.
Có thể tra cứu cấu hình trong backup để thiết lập lại bằng UI; không copy nguyên cấu hình
legacy trở lại hay chỉ sửa UID để bỏ qua cảnh báo. Model và ảnh được giữ nguyên.

### Các lỗi khác

| Lỗi | Cách xử lý |
|---|---|
| Không có GPU | Runtime → Change runtime type → GPU T4; script dừng trước khi tải model |
| Driver/wheel CUDA không hợp | Thử `--cuda cu128` hoặc `--cuda cu126`; stage torch kiểm tra kernel thật và lùi dần khi cần |
| Civitai 401/403, metadata rỗng | Kiểm tra quyền tải và Secret `CIVITAI_TOKEN`; hoặc chọn FP16. Không tự chuyển phiên bản |
| SHA256 sai | Stage không nhận file; chạy lại stage model. Nếu dùng mirror riêng, kiểm tra URL + SHA của đúng file |
| Rớt mạng lúc tải | Chạy lại cùng lệnh; `.part` được giữ để tiếp tục |
| Forge không thấy model | `--doctor`; xem `--ckpt-dirs`/MODEL_DIR, chạy `--only launch,verify --restart` |
| Cổng đang bị chiếm | Chọn `--port 7862`; bộ cài không kill process lạ |
| Tunnel cloudflared lỗi | Đổi `--tunnel share --only launch,verify --restart`; tuân thủ điều khoản mạng/dịch vụ |
| Bản lượng tử hóa nạp/sinh ảnh lỗi | Chọn lại `--model fp16`; các biến thể cộng đồng chưa được kiểm chứng sinh ảnh trên Colab |
| `EOFError` tại `verify_version()` | Cập nhật cả hai script lên 1.0.1 rồi chỉ chạy launch/verify; xem ô sửa bên trên |
| `setup_forge.sh` bản cũ | Cập nhật repo sạch cùng nhánh; bộ cài từ chối trộn script không tương thích |
| Thiếu upscaler anime | `--only extras`; lỗi upscaler là cảnh báo, bộ dựng prompt chọn scaler đang có |

Link public có thể cho người biết link truy cập UI/API và dùng GPU của bạn. Không chia sẻ
link công khai; dừng runtime khi dùng xong. Negative prompt không đảm bảo loại bỏ mọi
nội dung không phù hợp. Tuân thủ giấy phép model/pháp luật/điều khoản Colab, tuyệt đối
không tạo nội dung tình dục hóa trẻ vị thành niên.

## 7. Kiểm tra của dự án

Từ thư mục gốc repo:

```bash
python3 colab/tests/test_install_sh.py       # 95 kiểm tra CLI/fixture/vòng đời cài
python3 colab/tests/test_prompt_lib.py       # 15 nhóm hồi quy thư viện prompt
python3 colab/make_install_notebook.py       # sinh lại notebook một ô
bash -n colab/install.sh
bash -n colab/setup_forge.sh
shellcheck colab/install.sh colab/setup_forge.sh
# Trong venv có Gradio/requests/Pillow:
python colab/tests/test_prompt_ui.py         # UI thật, API và Forge host giả lập
```

**Đã kiểm tra:** luồng cài/resume bằng stage stub, tải/checksum model nhỏ qua HTTP cục bộ,
CUDA fallback bằng venv giả lập, hồi quy VERSION_UID/EOF với stdin đóng, và UI trên
Gradio **4.40.0 / 6.30.0**. Test UID có fixture offline; cũng đã chạy lại cùng hàm
`verify_version()` nguyên bản lấy từ Forge Neo, chỉ trích AST, không import engine.
Muốn kiểm tra bằng mã upstream đã tải về:

```bash
FORGE_VERSION_GUARD_SOURCE=/path/to/Forge/modules/launch_utils.py \
  python3 colab/tests/test_install_sh.py
```

**Chưa kiểm tra:** chạy toàn bộ hệ thống và sinh ảnh thật trên GPU Colab; sandbox không có GPU
và không truy cập được nguồn model. Bộ kiểm tra không giả vờ đã benchmark/đã sinh ảnh.

## Nguồn metadata

- FP16 gốc: [Civitai model 827184 / version 2883731](https://civitai.com/models/827184?modelVersionId=2883731),
  mirror [LyliaEngine/waiIllustriousSDXL_v170](https://huggingface.co/LyliaEngine/waiIllustriousSDXL_v170).
- FP8/INT8: [WAI-illustrious-Mix-FP8, model 2451718](https://civitai.com/models/2451718/wai-illustrious-mix-fp8).
- HSWQ: [WAI-illustrious-HSWQ, model 2698106](https://civitai.com/models/2698106/wai-illustrious-hswq).
- API: [tài liệu model/file Civitai](https://developer.civitai.com/site/reference/models).
- Forge Neo: [Haoming02/sd-webui-forge-classic, nhánh neo](https://github.com/Haoming02/sd-webui-forge-classic/tree/neo).
