# Bộ cài Colab một lệnh — WAI-Illustrious v17

Cài **Forge Neo + checkpoint WAI v17 + tagcomplete + kho prompt tiếng Việt + tab Prompt VN**.
Có chọn model, chọn thư mục lưu, xác minh SHA256 và chạy lại để tiếp tục phần còn dở.
Mặc định model/ảnh/log đều ở `/content`. **Không có bước mount Google Drive.**
Bản hiện tại **1.0.7**; xem [báo cáo rà soát toàn dự án](AUDIT.md).

## 1. Cách dễ nhất: notebook một ô

[**Mở bộ cài trong Google Colab**](https://colab.research.google.com/github/manhlee1196-boop/ai-anime3/blob/arena%2Fec9855a4-ai-anime3/colab/WAI_v17_1click.ipynb)

Hoặc tải [`WAI_v17_1click.ipynb`](WAI_v17_1click.ipynb), rồi Colab → File → Upload notebook.

1. **Runtime → Change runtime type → GPU T4** (hoặc L4/A100).
2. Chọn `MODEL` ở dropdown; mặc định **fp16**, `MODEL_DIR=/content/models`, **`TUNNEL="share"`** (Gradio).
3. Chọn **Runtime → Run all**, chờ kiểm tra đạt rồi mở link public được in ra.
4. Trong Forge, dùng **Prompt VN**: đổi tag Việt tại chỗ, thử Nháp/Chuẩn trước,
   chọn ảnh/seed rồi mới Hoàn thiện Hires. Không tự sinh ảnh thử khi cài mặc định.

**Muốn chạy mới hoàn toàn:** tải ảnh cần giữ về trước, rồi **Runtime → Disconnect
and delete runtime**, kết nối lại/bật GPU và mở notebook mới từ link phía trên.
Đừng dùng bản notebook cũ đã lưu trong Drive nếu muốn nhận các ô mới. Notebook
không tự xóa repo/model/ảnh hoặc mount Drive.

Cả hai notebook dùng bootstrap có **version guard ≥1.0.7 + Bash syntax check**.
Mất mạng chỉ dùng cache đủ mới và hợp lệ; không âm thầm chạy cache <1.0.7.

Cần khoảng **25 GB trống**. Lần đầu có thể mất **10–25 phút**, tùy mạng và runtime.
Notebook có đúng **1 ô code**, cùng 2 ô hướng dẫn; không cần chạy lần lượt các stage.

> Nhánh hiện tại là `arena/ec9855a4-ai-anime3`, vì bộ cài chưa nằm trên `main`.
> Chỉ đổi nhánh trong link/lệnh khi thay đổi đã được gộp vào nhánh đó.

## 2. Dán một dòng vào Colab

Sau khi bật GPU, dán vào một ô code:

```python
!curl -fsSL --retry 3 "https://raw.githubusercontent.com/manhlee1196-boop/ai-anime3/arena/ec9855a4-ai-anime3/colab/install.sh" -o /content/install.sh && bash /content/install.sh --model fp16
```

Đổi `--model fp16` thành `--model fp8`, `--model int8` hoặc `--model hswq` để chọn biến thể.
Thư mục tùy chọn, ví dụ `--model-dir /content/wai-models`.
Các bản cộng đồng có thể cần quyền tải/token Civitai; nên dùng notebook và Colab Secrets
nếu cần token. **Không dán token vào lệnh hoặc URL.**

Nếu raw GitHub không truy cập được, lấy script qua API:

```python
!curl -fsSL -H "Accept: application/vnd.github.raw" "https://api.github.com/repos/manhlee1196-boop/ai-anime3/contents/colab/install.sh?ref=arena%2Fec9855a4-ai-anime3" -o /content/install.sh && bash /content/install.sh --model fp16
```

Cài mới mặc định dùng **Gradio share** (`gradio.live`). Có thể chọn `--tunnel cloudflared`
hoặc `--tunnel none`; không tự đổi tunnel khi lỗi. Với phiên đã có, bộ cài giữ lựa chọn
trong `settings.json`; environment ghi đè file và cờ `--tunnel` ghi đè cả hai. Form
notebook cũ vẫn có thể truyền `cloudflared`: chọn `share` trước khi chạy lại nếu muốn giữ Gradio.

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
| In chẩn đoán checkpoint/preset/đường dẫn API | `!bash /content/install.sh --diagnostics` |
| Buộc nạp trọng số và sinh 1 ảnh thử | `!bash /content/install.sh --only verify --smoke-test` (API phải đang chạy) |
| Cài xong nhưng chưa mở UI | `!bash /content/install.sh --no-launch` |
| Tải/cắm lại model và kho prompt | `!bash /content/install.sh --only model,extras` |
| Đổi sang Gradio share | `!bash /content/install.sh --tunnel share --only launch,verify --restart` (đợi sinh xong, mở link mới) |
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
- Trước launch: xác minh SHA256 + header safetensors, đặt preset `xl` và **cả hai**
  `sd_model_checkpoint`/`forge_checkpoint_xl`. Không mặc định bật FP8 dtype trên T4.
- Tạo alias symlink nhỏ trong `models/Stable-diffusion` khi model nằm ngoài Forge;
  giữ file gốc tại MODEL_DIR, không copy hàng GB, không ghi đè file/link không rõ nguồn.
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
  checkpoint-smoke.png       ảnh thử khi bật --smoke-test
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

### Cập nhật quy trình/đổi Việt → Anh (1.0.3)

Bản mới dùng toàn cụm Việt ở con trỏ của tagcomplete và thay mục tương ứng khi
chọn tag trong tab Prompt VN. Có nút đổi nhiều tag, hoàn tác điền txt2img, ba mức
Nháp/Chuẩn/Hoàn thiện và dùng lại seed. Không chỉnh sửa mã tagcomplete upstream.

```bash
%%bash
set -euo pipefail
git -C /content/ai-anime3 pull --ff-only origin arena/ec9855a4-ai-anime3
cp /content/ai-anime3/colab/{install,setup_forge}.sh /content/
bash /content/install.sh --only extras,launch,verify --restart
```

Không tải lại checkpoint/Torch; bộ cài đọc lại biến thể/thư mục đã lưu.
**Reload cứng trang Forge** sau restart để nạp JS mới. Nếu dùng `REPO_DIR` khác,
thay `/content/ai-anime3` bằng đường dẫn repo của bạn.
Các tham số mới áp dụng cho nút Sinh ảnh trong Prompt VN/app. Nút Đưa vào txt2img
chỉ chuyển prompt; sampling tại txt2img vẫn do bạn đặt. Xem [quy trình](README.md#quy-trình-tối-ưu-bản-103).


### Bảng ảnh đã tạo (1.0.7)

**Prompt VN → Ảnh đã tạo** (phía dưới bộ dựng prompt) có:

- Gallery thumbnail **12/24 ảnh mỗi trang**, mới nhất trước; bảng thời gian lưu
  (UTC+7), tên file, seed, kích thước và dung lượng. Bấm thumbnail **hoặc dòng bảng**.
- **Xem ảnh gốc / Tải ảnh gốc**: đọc file đã lưu, không nén/sửa ảnh gốc hoặc metadata.
- **Dùng seed ảnh lịch sử**: chỉ điền seed vào ô sinh hiện tại, không thay prompt,
  sampler/steps/CFG/Hires. Không dùng seed ảnh lưới hoặc ảnh thiếu seed xác định.
- Đọc cả ảnh txt2img/img2img/Prompt VN đã tồn tại trong thư mục output cấu hình,
  cùng ảnh của ví dụ API notebook. Ảnh mới từ Prompt VN tự làm mới lịch sử sau callback;
  sinh trong txt2img/img2img thì bấm **Làm mới**. Không cần sinh lại ảnh cũ.

**Lưu trên đĩa:** chỉ mục/preview trong `FORGE_DIR/outputs/.wai-history/`;
State chỉ có id/trang/signature nhỏ, không tích luỹ toàn bộ PIL/base64. Mỗi preview
đọc một ảnh, WebP tối đa 384px; ảnh trên 16 megapixel dùng placeholder để tránh
thumbnail decode quá lớn. Ảnh gốc chỉ được đưa tới viewer/download khi chọn.
Có thể đọc lại sau restart Forge; `/content` vẫn mất khi xóa runtime. Không mount Drive.
Đây là thiết kế album nhẹ, **không phải kết luận/bản vá rò rỉ RAM của Forge**.
Người có link public UI cũng có thể xem album; không chia sẻ link công khai.

#### Cập nhật phiên Colab đang chạy, không tải lại model/Torch

Đợi tác vụ sinh ảnh kết thúc. Repo cần sạch và đang ở đúng nhánh; không reset/xóa
repo nếu có thay đổi riêng. Chạy một ô Colab mới:

```bash
%%bash
set -euo pipefail
repo=/content/ai-anime3
[[ "$(git -C "$repo" branch --show-current)" == "arena/ec9855a4-ai-anime3" ]] || { echo "Repo khác nhánh; dừng để giữ thay đổi của bạn."; exit 1; }
git -C "$repo" pull --ff-only origin arena/ec9855a4-ai-anime3
cp "$repo/colab/install.sh" /content/install.sh
cp "$repo/colab/setup_forge.sh" /content/setup_forge.sh
bash /content/install.sh --version
bash /content/install.sh --tunnel share --only extras,launch,verify --restart
```

Phiên bản phải **1.0.7 hoặc mới hơn**. Chỉ cắm extension/verify/restart process do
bộ cài quản lý, không chạy stage model/torch. Giữ lựa chọn model/thư mục/VRAM đã lưu;
đặt rõ `share` để không quay lại Cloudflare. Mở **link Gradio mới**, vào **Prompt VN →
Ảnh đã tạo → Làm mới**. Nếu dùng `REPO_DIR` khác, thay đường dẫn repo cho đúng.

App độc lập có tab **Ảnh đã tạo**, đọc file cục bộ. Có thể truyền
`--forge-dir /path/to/Forge` hoặc `--history-dir /path/to/images`. Forge ở máy
khác không có filesystem chung thì cần ảnh cục bộ; album không âm thầm tải ảnh
qua URL hoặc đọc tuỳ ý toàn bộ `/content`/thư mục nhà. Không theo symlink ra ngoài output.


### Ảnh hiển thị chậm / Unexpected token < (1.0.6)

Khi Forge đã sinh xong nhưng gallery/mở ảnh chậm và giao diện báo
`Could not parse server response: SyntaxError: Unexpected token '<'`, trình duyệt
đã nhận **HTML thay vì JSON**. Chưa có URL/status/Content-Type của request lỗi
thì không thể khẳng định Cloudflare 502/524, timeout cụ thể hay kích thước ảnh là nguyên nhân.
Local API HTTP 200 không chứng minh đường public/callback/file ảnh hoạt động tốt.

**Bằng chứng phiên người dùng:** sau đổi từ Cloudflare sang Gradio share, ảnh hiển thị
nhanh hơn và chưa thấy lỗi lặp lại. Vì vậy 1.0.6 chọn `share` làm mặc định **cài mới**,
không thay lựa chọn đã lưu. Đây không phải benchmark hay bảo đảm mọi phiên/mạng.

**Nếu phiên share hiện tại đang ổn: tiếp tục dùng link đó, không cần cập nhật/restart.**
Với phiên đang lỗi trên Cloudflare, đợi tác vụ sinh ảnh kết thúc rồi chạy ô Colab:

```bash
%%bash
set -euo pipefail
bash /content/install.sh --tunnel share --only launch,verify --restart
```

Mở **link `gradio.live` mới** được in ra, đóng link Cloudflare cũ. Lệnh đã hỗ trợ
trong 1.0.5; không cần tải lại model/Torch. Chỉ restart process Forge do bộ cài quản lý,
giữ model, ảnh đã lưu và cấu hình; không đổi độ phân giải/chất lượng hay metadata/seed ảnh.
Không bấm Sinh liên tiếp sau lỗi frontend vì backend có thể vẫn đang chạy/lưu ảnh.

Bộ cài nhớ `share` cho lần sau. Nếu chạy lại **notebook cũ**, đổi `TUNNEL` trong form
thành `share` trước (form truyền cờ, có ưu tiên cao hơn cấu hình đã lưu).
Nếu Gradio share không tạo được link, có thể chọn thủ công Cloudflare dự phòng bằng
`--tunnel cloudflared --only launch,verify --restart`, cũng đợi tác vụ sinh xong trước.

Nếu lỗi còn trên share, lấy **path, HTTP status, Content-Type và thời gian** của
request lỗi trong Browser DevTools → Network; không gửi cookie/token/query string,
request payload/prompts hoặc toàn bộ response body. Không đoán lỗi checkpoint và
không cài lại dependencies chỉ vì trình duyệt nhận HTML.


### Error hàng loạt / Matplotlib backend inline Colab (1.0.5)

Trường hợp đã tái hiện: WAI có trong registry/dropdown, local `/config` và `/info`
đạt, nhưng log import ControlNet/Gradio Dataframe kết thúc ở Matplotlib
`__init__.py:1292` và `__setitem__:784`. Đây là hai dòng đọc/validate `MPLBACKEND`
trong Matplotlib 3.11. Colab có thể truyền `module://matplotlib_inline.backend_inline`
vào process venv không có backend inline; tái hiện được `ValueError: Key backend`.

Bản 1.0.5 đặt **`MPLBACKEND=Agg` chỉ trong shell khởi động Forge con**, trước khi
import các extension. Không cài thêm inline backend, không hạ Matplotlib/Gradio/
FastAPI/Torch, không sửa model hoặc backend hiển thị của notebook cha. Verify thêm
CPU probe pandas Styler/Gradio Dataframe; probe không chứng minh mọi callback native
hoặc sinh ảnh GPU đã đạt.

Chạy **trong runtime hiện tại**, không xóa runtime:

```bash
%%bash
set -euo pipefail
git -C /content/ai-anime3 pull --ff-only origin arena/ec9855a4-ai-anime3
cp /content/ai-anime3/colab/{install,setup_forge}.sh /content/
bash /content/install.sh --version
bash /content/install.sh --only launch,verify --restart
```

Phiên bản cần **≥1.0.5** (hiện tại **1.0.7**). Chỉ launch/verify; không chạy model/torch/extras/forge.
Mở **link public mới**, đóng trang cũ và reload cứng. Log khởi động in
`MPLBACKEND=Agg`; chẩn đoán mới có `graphics_env.forge_process: Agg` và metadata
Matplotlib/inline/pandas. `graphics_env.diagnostics_parent: inline_notebook` vẫn
có thể xuất hiện, vì notebook cha không bị thay đổi — không phải lỗi của Forge con.

Nếu Error còn xuất hiện, chạy `!bash /content/install.sh --diagnostics` và gửi
`graphics_env`, `forge_log_errors`, `venv`, trạng thái local/public với **link mới**.
Diagnostic đã đọc được exception thụt đầu dòng của Forge và phân loại
`matplotlib_backend_invalid`. `URLError` thêm DNS/TLS/timeout/refused nhưng vẫn bỏ
raw exception/URL/body có thể chứa secret. Không suy ra tunnel chết hoặc mọi lỗi
Error đều do Matplotlib; cần kiểm tra runtime sau restart, không tải lại weights.

### API đã có WAI nhưng dropdown trống / cmd-flags 500 (1.0.4)

Nếu diagnostics cho thấy file SDXL hợp lệ, alias đúng và
`checkpoint_da_dang_ky_va_chon: true`, **model không bị thiếu trong backend**.
Không tải lại weights/Torch, không xóa runtime. Hash API null/`sd_checkpoint_hash` rỗng
không tự chứng minh model bị thiếu; đăng ký/chọn cũng chưa chứng minh sinh ảnh GPU.

Trên Neo `ede60e1…`, schema `FlagsModel` suy kiểu từ default `None`, làm `--port`
bị khai báo string dù argparse trả integer `7860`. Đã tái hiện HTTP 500 bằng FastAPI/
Pydantic thật. Bản 1.0.4 giữ kiểu primitive đã khai báo khi default None; **không tắt
response validation**. Ngoài ra, dropdown native trước đây dựng với `choices=None,
value=None`; bản vá lấy choices/value từ registry trước callback trình duyệt, giữ
chế độ tên dài/ngắn. **Chưa chứng minh lỗi cmd-flags là nguyên nhân UI trống của
mọi runtime**; khởi tạo sẵn là biện pháp gia cố, chưa phải kiểm thử native/GPU.

Dán **một ô mới trong runtime hiện tại**:

```bash
%%bash
set -euo pipefail
git -C /content/ai-anime3 pull --ff-only origin arena/ec9855a4-ai-anime3
cp /content/ai-anime3/colab/{install,setup_forge}.sh /content/
bash /content/install.sh --only launch,verify --restart
```

Chỉ launch/verify, không chạy model/torch/forge/extras; model/ảnh/venv được giữ nguyên.
Helper vá đúng snippet đã biết, kiểm AST cả hai file trước khi ghi, backup
`.wai-compat-<sha>.bak`, rollback nếu ghi lỗi. Source Neo khác/từng bị sửa thì dừng
thay vì vá mù. Verify kiểm marker, `/cmd-flags` HTTP 200 và port integer. Bộ cài vẫn
xác minh header/SHA256 và registry/preset, không tự sinh ảnh khi thiếu `--smoke-test`.
Nếu Git báo thay đổi/xung đột, giữ nguyên và gửi lỗi; không dùng `reset --hard`.
Đường dẫn repo khác thì thay `/content/ai-anime3` tương ứng.

Sau restart, **đóng trang Forge cũ, mở link public mới**, nhấn Ctrl+Shift+R rồi chọn
UI Preset **XL** nếu cần. Nếu vẫn trống, gửi:

```python
!bash /content/install.sh --diagnostics
```

Báo cáo mới có `checkpoint_ui_initial_config` (choices/value từ `/config`, không
in prompt/auth/config khác) và trạng thái source compat. Nếu config server đã có
choices/value mà browser vẫn trống, cần xem callback/UI: thử nút refresh cạnh
Checkpoint, ghi lại nó có hiện model không và gửi traceback gắn với thao tác đó
trong `forge.log` sau khi che thông tin riêng. Không gửi toàn bộ config/log/token.

### Link mở được nhưng báo lỗi hàng loạt Checkpoint / LoRA / textual inversion

**Đừng tải thêm tài nguyên để che lỗi.** LoRA và textual inversion là tùy chọn;
API trả danh sách rỗng (HTTP 200, count 0) chỉ có nghĩa chưa cài tài nguyên phụ.
WAI v17 FP16 không bắt buộc LoRA/textual inversion riêng. HTTP 500/404 hoặc lỗi
callback đỏ lại là vấn đề cần xác định; không được coi mọi lỗi là bình thường.

Nếu UI vẫn không dùng được sau 1.0.4, **chụp thông báo lỗi nguyên văn**. Mở trang
Forge và bấm refresh Checkpoint một lần để có traceback mới, rồi chạy một ô sau
(thay link nếu tunnel đã đổi). Không restart/cài Torch/tải model/sinh ảnh:

```bash
%%bash
set -euo pipefail
git -C /content/ai-anime3 pull --ff-only origin arena/ec9855a4-ai-anime3
python3 /content/ai-anime3/colab/diagnostics.py \
  --public-url "https://YOUR-LINK.trycloudflare.com/"
```

- `ui_transport_local/public`: HTTP status `/`, `/config`, `/info?all_endpoints=True`,
  không in response body/header/auth/prompt hoặc theo redirect. Nếu `/info` lỗi dù
  `/sd-models` đạt thì lỗi API giao diện vẫn tồn tại, chưa thể coi Forge sử dụng được.
- `venv`: thêm gradio-client/Pydantic/pydantic-core/FastAPI/Starlette để đối chiếu
  dependency; **không tự hạ/nâng phiên bản dựa trên tên lỗi chung**.
- `optional_assets`: chỉ đếm LoRA/loaded/skipped embeddings, không in tên riêng.
- `forge_log_errors`: tối đa 6 traceback trong 256 KiB cuối log, chỉ loại exception,
  stack và signature có danh mục; bỏ message/source/token/prompt. Không có traceback
  không chứng minh UI không lỗi: lỗi JavaScript có thể chỉ có ở trình duyệt.

Gửi báo cáo và ảnh thông báo lỗi. Link không mở được từ một công cụ bên ngoài
không đủ chứng minh tunnel hỏng; so sánh local/public từ chính runtime Colab.
Nếu dùng đường dẫn/port khác mặc định, truyền `--runtime-dir`, `--forge-dir`,
`--repo-dir`, `--model-dir`, `--state-dir`, `--port` tương ứng.

### Không nhận Checkpoint / ô Checkpoint trống dù file đã tải

**Trường hợp cấu hình thiếu key được sửa ở 1.0.2 (giữ trong 1.0.5).** Forge Neo còn lưu checkpoint riêng theo preset:
`forge_checkpoint_xl` mặc định là `None`. Chỉ ghi `sd_model_checkpoint` không đủ:
`on_preset_change()` có thể đặt lại ô Checkpoint thành trống khi mở UI.

Chạy trong **runtime hiện tại**, không reset và không tải lại model:

```bash
%%bash
set -euo pipefail
git -C /content/ai-anime3 pull --ff-only origin arena/ec9855a4-ai-anime3
cp /content/ai-anime3/colab/{install,setup_forge}.sh /content/
bash /content/install.sh --only extras,launch,verify --restart --smoke-test
```

Ô này cập nhật kho prompt/extension, kiểm header + SHA256 của checkpoint đang có,
đăng ký alias có quản lý và chọn đúng **preset `xl` / checkpoint**. Không chạy stage
model/torch/forge; không xóa ảnh, trọng số hay venv. Config được sao lưu trước khi sửa.
Nếu đổi tùy chọn UI trước đây, bản sửa chỉ sửa key **UI Preset** trong `ui-config.json`,
không đặt lại prompt/kích thước/key UI khác. Các tùy chọn WAI/preset XL được áp dụng
lại theo model đã chọn; preset của model khác được giữ nguyên.

`--smoke-test` dùng GPU để tạo **1 ảnh 256×256, 1 step, không hires** tại
`/content/checkpoint-smoke.png`. Mục tiêu là buộc Forge nạp trọng số và đối chiếu hash,
**không đánh giá chất lượng/benchmark**. Lần nạp đầu có thể mất vài phút.
Nếu chưa muốn sinh ảnh, bỏ `--smoke-test`; verify khi đó chỉ chứng minh container,
đăng ký và lựa chọn checkpoint — **không chứng minh weights đã nạp vào GPU**.

Nếu vẫn lỗi, chạy và gửi output chẩn đoán (không có token/config đầy đủ):

```python
!bash /content/install.sh --diagnostics
```

Công cụ in đường dẫn thực/symlink/kích thước/header, phiên bản venv/GPU, UID, `ckpt_dirs`
của process đang chạy, danh sách model API và preset đang chọn. Có file `.part` không
đồng nghĩa tải xong; Forge không nhận nó. Có hai file khác nhau trùng tên thì bộ cài
dừng thay vì ghi đè/chọn nhầm. Không tự đổi precision/phiên bản khi model lỗi.

### Cờ bổ sung và credential

`--forge-args` không được ghi đè `--data-dir`, `--model-ref`, `--ui-settings-file`,
`--ui-config-file`, `--port`, chế độ API-only/debug hoặc tắt extension. Những cờ này
làm thư mục scan/config của Forge lệch khỏi nơi bộ cài đang quản lý. `--ckpt-dirs`
bổ sung vẫn được phép vì Neo dùng `action=append`.

Không truyền `--api-auth`/`--gradio-auth`/token ngrok trong `--forge-args`: cấu hình
bổ sung được lưu để resume nên bộ cài **từ chối** credential trong trường này.
Bộ cài mặc định chưa quản lý auth UI/API; hãy bảo vệ link public như phần cảnh báo.
Token tải model/clone dùng Colab Secrets/header riêng, không nằm trong origin Git.

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
git -C /content/ai-anime3 pull --ff-only origin arena/ec9855a4-ai-anime3
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
| Error ở nhiều ô / traceback Matplotlib 1292→784 | Cập nhật 1.0.5 + restart, backend Agg chỉ cho Forge con; không cài lại Torch/weights |
| Forge không thấy model / Checkpoint trống | Cập nhật 1.0.4; API đã có model thì dùng ô software-only ở trên. Kiểm preset `xl` / `forge_checkpoint_xl` và config UI, không tải lại weights theo tên/hash null |
| Cổng đang bị chiếm | Chọn `--port 7862`; bộ cài không kill process lạ |
| Ảnh chậm / `Unexpected token <` trên Cloudflare | Xem hướng dẫn tunnel ở trên; đợi sinh xong, đổi share và mở link mới; không giảm chất lượng ảnh |
| Gradio share không tạo link | Thử `--tunnel cloudflared --only launch,verify --restart` sau khi tác vụ sinh kết thúc; không tải lại model/Torch |
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
python3 colab/tests/test_install_sh.py       # CLI/fixture/vòng đời + source guards
python3 colab/tests/test_checkpoint_flow.py  # 16 nhóm checkpoint/preset/API/alias
python3 colab/tests/test_data_integrity.py   # 4 nhóm, kiểm toàn bộ 349.714 dòng CSV
python3 colab/tests/test_prompt_lib.py       # 15 nhóm hồi quy thư viện prompt
python3 colab/make_install_notebook.py       # sinh lại notebook một ô
bash -n colab/install.sh
bash -n colab/setup_forge.sh
shellcheck colab/install.sh colab/setup_forge.sh
# Trong venv có Gradio/requests/Pillow:
python colab/tests/test_prompt_ui.py         # UI thật, API và Forge host giả lập
python colab/tests/test_image_history.py     # SQLite/header/seed/paging, không sửa ảnh gốc
python colab/tests/test_image_history_ui.py  # bảng/gallery/seed + HTTP tải PNG nguyên byte
```

**Đã kiểm tra:** luồng cài/resume bằng stage stub, tải/checksum model nhỏ qua HTTP cục bộ,
CUDA fallback bằng venv giả lập, header/checksum/alias/preset, hồi quy VERSION_UID/EOF
với stdin đóng, toàn bộ CSV, đường giải mã ảnh của cả hai UI, và UI trên
Gradio **4.40.0 / 6.30.0**. Test UID có fixture offline; cũng đã chạy lại cùng hàm
`verify_version()` nguyên bản lấy từ Forge Neo, chỉ trích AST, không import engine.
Muốn kiểm tra bằng mã upstream đã tải về (bản rà soát: Neo 2.30,
commit `ede60e1aefd30ce0f7341c8ff538f48e0fd047c9`):

```bash
FORGE_VERSION_GUARD_SOURCE=/path/to/Forge/modules/launch_utils.py \
  python3 colab/tests/test_install_sh.py
# Thư mục snapshot có audit_modules_{sd_models,modelloader,util,options}.py
# và audit_modules_forge_{main_entry,presets}.py:
FORGE_AUDIT_SOURCE_DIR=tools/work python3 colab/tests/test_checkpoint_flow.py
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
