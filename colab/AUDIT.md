# Rà soát toàn dự án — bộ cài 1.0.2

Ngày: **11/10/2026**. Phạm vi: bộ cài và resume, tải/checksum checkpoint, cấu hình/scan/
preset Forge Neo, notebook một ô + chi tiết, tagcomplete, thư viện prompt, cả hai UI,
response API, toàn bộ 4 CSV và công cụ build.

## Kết luận về lỗi Checkpoint

Có lỗi xác định được trong bộ cài 1.0.1: chỉ ghi `sd_model_checkpoint`. Forge Neo 2.30
còn có `forge_checkpoint_xl` (default `None`) và `forge_preset` (default `sd`). Trong
`on_preset_change()`, `getattr(opts, "forge_checkpoint_<preset>", opts.sd_model_checkpoint)`
**không fallback** khi option đã tồn tại với giá trị `None`. Kết quả: file có thể nằm
trong registry/API, nhưng dropdown Checkpoint bị đặt trống khi UI khởi tạo.

Đã tái hiện bằng **hàm `on_preset_change()` và class `Options` nguyên bản** của Forge,
không chỉ một mock trả model trong API. Sau sửa, đã đối chiếu bằng scanner `walk_files`,
`modelloader.load_models`, `CheckpointInfo`, `list_models`, `checkpoint_tiles` và
`select_checkpoint` nguyên bản. Phần cache/host Forge được giả lập; không import engine CUDA.

Nguồn đã đối chiếu: [Forge Neo commit ede60e1aefd30ce0f7341c8ff538f48e0fd047c9](https://github.com/Haoming02/sd-webui-forge-classic/tree/ede60e1aefd30ce0f7341c8ff538f48e0fd047c9).
Đây là revision **đã rà soát**, không phải tuyên bố đã chạy GPU/khóa mọi dependency upstream.

## Các phát hiện và sửa chữa

| Phát hiện | Sửa ở 1.0.2 / trạng thái |
|---|---|
| Dropdown trống do checkpoint riêng của preset còn `None` | Chọn preset `xl`, ghi cả `sd_model_checkpoint` và `forge_checkpoint_xl`; áp dụng CFG/steps/sampler/hires theo biến thể |
| Model ngoài Forge chỉ dựa vào cờ scan; đăng ký chưa được kiểm sâu | Giữ `--ckpt-dirs`; thêm symlink có manifest trong `models/Stable-diffusion`, không copy hàng GB/không đè file hoặc symlink của người dùng |
| Verify chỉ so basename/model_name có thể nhận một file khác cùng tên | Đối chiếu đường dẫn canonical/symlink và hash API nếu có; kiểm riêng registry và preset/selection |
| Có API không đồng nghĩa trọng số nạp thành công | Thêm `--smoke-test`: 1 ảnh 256×256, 1 step, không hires; kiểm PNG/CRC và hash checkpoint sau nạp. Mặc định không tự sinh ảnh |
| Chỉ dung lượng/hash chưa chứng minh container đúng định dạng | Kiểm header safetensors có giới hạn, dtype/shape/offset/overlap/EOF; từ chối pointer Git LFS, HTML, file bị cắt/trùng khóa JSON |
| Script `/content/setup_forge.sh` cũ có thể được ưu tiên hơn repo đã cập nhật | Ưu tiên script canonical trong repo; nâng `SETUP_API_VERSION=2`, từ chối trộn v1/v2. Cho repo cũ fast-forward trước khi kiểm file helper mới |
| Cờ `--forge-args` có thể đổi đường dẫn config/scan hoặc lưu credential | Từ chối cờ xung đột chế độ/đường dẫn và auth/token trong trường cấu hình được lưu; vẫn cho thêm `--ckpt-dirs` |
| Khi verify thất bại chỉ có dấu ✖, mất nguyên nhân | Hiển thị error ngắn của helper checkpoint; thêm `--diagnostics` chỉ đọc, whitelist trường công khai, không dump config/args/log đầy đủ |
| App Gradio độc lập vẫn dùng `.get()` trên info JSON-string và trả bytes cho Gallery | Cả app và extension dùng chung bộ giải mã JSON-string/base64 → PIL; báo response rỗng/hỏng, không báo sinh ảnh thành công giả |
| Lựa chọn sampler `DPM++ 2M Karras` không phải tên sampler hợp lệ của API Neo | Tách sampler `DPM++ 2M` / scheduler `Karras` trong payload (tương tự bản SDE) |
| Notebook chi tiết còn token literal, URL clone chứa token, fallback main/master/xóa thư mục | Dùng Colab Secrets và header tạm; clone đúng một nhánh vào thư mục tạm; giữ dữ liệu có sẵn; mỗi stage truyền lỗi thật bằng `check=True` |
| Unicode `ಠ_ಠ` bị `decode("unicode_escape")` lần nữa nên bỏ sai `_` | Bỏ decode thừa, bảo vệ emoticon ở cả tag/alias. Chỉ 1 dòng ở mỗi CSV `_nounderscore` và `_vi` thay đổi; số dòng/dịch/category/post_count không đổi |
| Lỗi EOF của 1.0.0 | Giữ hồi quy UID/stdin đóng; vẫn đọc VERSION_UID từ mã Forge, backup trước khi sửa cấu hình tối thiểu; không stamp cấu hình legacy thành bản mới |

Config được sao lưu dưới `*.wai-checkpoint-backup-*`. Trong `ui-config.json`, chỉ cập
nhật key kết thúc bằng `/UI Preset/value` nếu có; không xóa file, không đặt lại toàn
bộ prompt/kích thước/key khác. Preset WAI/XL được áp dụng lại theo model đã chọn; các
preset model khác không bị xóa. Model, ảnh, venv, repo và thay đổi local được giữ lại.

## Kiểm tra đã thực hiện

| Bộ kiểm tra | Kết quả / phạm vi |
|---|---|
| `test_install_sh.py` | **95/95** kiểm tra; downloader/checksum thật với safetensors nhỏ/HTTP cục bộ, lifecycle stub, resume/cache/exit code/tokens/notebook |
| `test_checkpoint_flow.py` | **16 nhóm đạt**, có subtests: container hỏng, .part, alias/collision/ownership, backup, profile HSWQ, chuẩn bị launch thật, registry/preset/API/PNG, diagnostics chỉ đọc, stale buddy và nâng repo cũ |
| Mã upstream | Chạy lại hồi quy cùng hàm guard UID, preset, scanner và selector nguyên bản từ revision Forge nêu trên; **không import toàn engine** |
| `test_prompt_lib.py` | **15 nhóm đạt**: index, tra tiếng Việt/alias, nhóm, negative, cấu trúc prompt, profile model/payload |
| `test_prompt_ui.py` | UI thật trên **Gradio 4.40.0 và 6.30.0**; API/Forge host giả lập. Đã đi hết đường giải mã ảnh của cả app và extension |
| `test_data_integrity.py` | **4 nhóm đạt**; duyệt toàn bộ **349.714 dòng** ở 3 CSV 4 cột và **45.513** translation; category/count/sort/alias/tên riêng/emoticon, đối chiếu nguồn đã chỉ định nếu có |
| Cú pháp | Python AST toàn bộ mã; 11 ô code notebook chi tiết + 1 ô một lệnh; notebook chưa có output; Bash syntax, ShellCheck, JS syntax |

Asset tagcomplete được sinh từ kho đầy đủ, không thiếu CSV và không trùng khóa.
Không đưa model, venv hay snapshot mã Forge tham khảo vào Git.

## Giới hạn chưa thể xác minh

- Sandbox **không có GPU** và không truy cập được nguồn trọng số HF/Civitai.
- Chưa thực hiện cài mới end-to-end hoặc sinh ảnh WAI v17 thật trên T4/L4/A100.
- Mock PNG trong kiểm tra chỉ kiểm giao thức/giải mã, **không phải ảnh do WAI sinh**.
- Header/SHA/registry/preset đúng vẫn không bảo đảm backend lượng tử hóa, CUDA hoặc
  mọi dependency upstream chạy được. FP8/INT8/HSWQ vẫn là lựa chọn **thử nghiệm**.
- Không truy cập được runtime Colab của người dùng. Log/diagnostics thực từ runtime
  là bước cần thiết để phân biệt lỗi model/preset với lỗi driver/load/dependency tiếp theo.

Vì vậy không gọi toàn bộ hệ thống “đã sinh ảnh trên Colab”. Tùy chọn `--smoke-test`
được cung cấp để **runtime đang có GPU và model** thực hiện bước xác minh cuối cùng.

## Sửa trong Colab đang dùng

Không reset runtime. Dán một ô mới:

```bash
%%bash
set -euo pipefail
git -C /content/ai-anime3 pull --ff-only origin arena/88f01d31-ai-anime3
cp /content/ai-anime3/colab/{install,setup_forge}.sh /content/
bash /content/install.sh --only extras,launch,verify --restart --smoke-test
```

Không chạy stage model/torch/forge. Nếu không muốn sinh ảnh thử, bỏ `--smoke-test`.
Nếu vẫn lỗi, gửi output của:

```python
!bash /content/install.sh --diagnostics
```

Chẩn đoán không in secret/config/log đầy đủ. Không công khai link UI/tunnel, vì người
biết link có thể dùng GPU/API. Mọi dữ liệu `/content` mất khi kết thúc runtime; không
mount Drive và không có thủ thuật giữ phiên luôn hoạt động.
