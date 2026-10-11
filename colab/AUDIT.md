# Rà soát toàn dự án — bộ cài 1.0.6

## Bổ sung 1.0.6 — Gradio share mặc định cho cài mới — 12/10/2026

**Bằng chứng runtime sau 1.0.5:** diagnostics `2026-10-11T18:20:25Z` xác nhận
process Forge dùng Agg, không còn traceback startup, WAI đã chọn và dropdown/API
local hợp lệ. Người dùng xác nhận ảnh đã sinh xong nhưng gallery/mở ảnh chậm,
rồi báo `Could not parse server response: SyntaxError: Unexpected token '<'`.
Đây là HTML thay JSON; không có request path/status/Content-Type/timing để xác
định HTTP 502/524, timeout cụ thể, kích thước ảnh hay tầng trả HTML.

**Thử nghiệm do người dùng thực hiện:** chỉ đổi sang `--tunnel share` và restart
launch/verify, không cài lại model/Torch. Phản hồi: **“gradio hiển thị nhanh hơn
và chưa thấy lỗi”**. Kết quả ủng hộ ưu tiên đường Gradio share cho phiên này,
không phải benchmark/tuyên bố hết lỗi lâu dài hoặc chứng minh lỗi Cloudflare cụ thể.

- Bộ cài và cả hai notebook **1.0.6** mặc định `share` cho **cài mới**, in link
  `gradio.live`. Giữ lựa chọn `cloudflared`/`none`; không fallback tự động.
- Giữ cấu hình tunnel đã lưu. Thứ tự ưu tiên không đổi: **cờ CLI > environment >
  settings.json > mặc định**. Notebook cũ có thể vẫn truyền `cloudflared` qua form;
  hướng dẫn đổi `TUNNEL` rõ ràng, không âm thầm ghi đè lựa chọn của người dùng.
- Bootstrap ≥1.0.6, kiểm syntax/cache như trước; không chạy cache cũ của bản cài mới.
  **Phiên share đang ổn không cần cập nhật/cài lại/restart.** Lệnh chuyển tunnel
  đã có trong 1.0.5; đợi sinh ảnh kết thúc và mở link mới khi thật sự cần restart.
- Không sửa gallery/độ phân giải/nén ảnh gốc/metadata/seed, model, Torch, Agg,
  compat/schema/dropdown, prompt replacement, corpus hoặc quy trình sampling.

### Kiểm tra 1.0.6

- **Installer: 111 đạt**, gồm 13 kiểm tra mới offline cho mặc định share, không sửa
  lựa chọn đã lưu, ưu tiên environment/CLI, nhớ share lần sau, cờ Neo `--share`
  chỉ bật khi chọn share và không tải/chạy Cloudflare trong chế độ share.
- **Notebook: 14 nhóm đạt**, gồm fresh Run all ở cả hai notebook dùng share, giữ
  stage order/FP16/noDrive/no automatic generation, từ chối cache 1.0.5 và cho phép
  chọn thủ công Cloudflare/none. Generator tái tạo đúng byte; không output/secret.
- **Headless: 4 nhóm đạt** với matrix FastAPI **0.127.1** / Starlette **0.50.0**,
  Gradio **4.40.0** / Pydantic **2.10.6** giống runtime, Python **3.11** CPU.
  Chạy bằng `FASTAPI_PROBE_PATH=tools/work/fastapi127-probe`; không thay venv/runtime.
  Baseline sandbox FastAPI 0.115.14/Starlette 0.46.2 khác matrix gặp schema
  `starlette.requests.Request` ở POST probe (3/4); không coi đó là lỗi runtime
  người dùng hoặc lý do hạ/nâng dependency trong bản thay default tunnel này.

- Chạy lại **checkpoint 16**, **compat 10**, **diagnostics 8** đạt; không sửa mã
  các module này. Python/notebook AST, Bash syntax và `git diff --check` đạt.

**Giới hạn:** không có GPU/model weights hoặc browser native Colab trong sandbox;
không tự đo latency/download ảnh hay kiểm public tunnel của người dùng. Phản hồi
nhanh hơn/chưa thấy lỗi là quan sát người dùng, không thay thế benchmark/HTTP trace.
Các phần dưới là lịch sử kiểm tra trước phản hồi runtime mới.

---


## Bổ sung 1.0.5 — backend headless Matplotlib — 12/10/2026

**Diagnostics runtime mới:** compat source true, `/cmd-flags` đúng port integer,
WAI SDXL có trong registry/chọn XL, config UI có 1 choice/value đúng. Local
`/`, `/config`, `/info` HTTP 200. LoRA/TI HTTP 200/count 0 (hợp lệ). Public
URLError chưa rõ loại, không chứng minh tunnel chết. Hai stack import ControlNet
và Gradio Dataframe/pandas Styler đi tới Matplotlib `__init__.py:1292` / `__setitem__:784`.
Không có bằng chứng thiếu model, hoặc sinh ảnh GPU thành công.

**Reproduction:** Matplotlib **3.11.2**, venv không có matplotlib-inline, đặt
`MPLBACKEND=module://matplotlib_inline.backend_inline` tái hiện ValueError `Key backend`
với chính hai dòng đó. Agg import Matplotlib, pandas Styler và dựng Gradio Dataframe
đạt. Không cần cài/hạ dependency; đặt Agg chỉ cho process Forge con trong
`prepare_launch`, dùng chung foreground/background.

- Verify CPU probe pandas Styler/Dataframe dưới Agg. Notebook cha giữ backend inline.
- Diagnostics thêm package Matplotlib/inline/pandas, nhận exception thụt đầu dòng
  (parser cũ bỏ sót exception Forge), signature backend invalid, phân loại lỗi
  mạng DNS/TLS/timeout/refused mà không dump message/body. Kiểm PID ownership trước
  khi đọc MPLBACKEND, không in cmdline/environ/credential khác.
- Bootstrap notebook ≥1.0.5; setup API **2** và prompt_lib **1.1.0** không đổi.
  Cập nhật chỉ launch/verify + restart, không model/Torch/extras.

### Kiểm tra 1.0.5

| Kiểm tra | Kết quả/phạm vi |
|---|---|
| Headless backend | **4 nhóm đạt**: reproduction inline 3.11, Agg/real Gradio Dataframe, callback Settings AST Neo với HTTP 200, installer probe không đổi env cha |
| Matrix callback | Gradio **4.40.0**, Pydantic **2.10.6**, FastAPI **0.127.1**, Starlette **0.50.0** (giống package runtime); Python **3.11** trên sandbox, không Python 3.13/GPU. Không có bằng chứng cần hạ FastAPI/Starlette |
| Diagnostics | **8 nhóm đạt**; có indent/Matplotlib signature, network reason và đọc env PID sở hữu/ẩn secret |
| Installer / checkpoint / compat / notebook | **98 + 16 + 10 + 13 đạt**, source Neo/UID/preset/scanner nguyên bản cho các test tương ứng |
| Prompt / workflow / UI / JS / data | **15 + 10**, UI thật Gradio 4.40/API host giả lập, JS **9** TAC pinned, dữ liệu **3 đạt + 1 bỏ qua** nguồn tải lại |

**Giới hạn:** đã sửa lỗi import tái hiện được, chưa chứng minh mọi badge Error trong
ảnh đều do nó. GET 200 không chứng minh mọi POST/callback/queue native đạt. Cần người
dùng mở link mới sau restart, xác nhận process Agg/UI và nếu cần test GPU riêng.
Không có model weights/GPU trong sandbox, không tuyên bố benchmark hay hoàn thành
sửa runtime trước khi người dùng chạy cập nhật.

---

## Bổ sung chẩn đoán UI/tunnel sau 1.0.4 — 12/10/2026

Người dùng báo vẫn lỗi hàng loạt checkpoint/LoRA/textual inversion. Link public
không đọc được bằng công cụ ngoài runtime; chưa có nguyên văn lỗi/traceback mới,
**không kết luận tunnel hỏng, không tuyên bố đã sửa UI/GPU**. Không tải lại model,
Torch hoặc cài LoRA/embedding chỉ để làm mất thông báo.

Chẩn đoán chỉ đọc thêm HTTP status local và tunnel (opt-in `--public-url`), Gradio
client/Pydantic/FastAPI/Starlette metadata, số lượng tài nguyên phụ và stack lỗi
cuối log (bỏ message/source/private data). URL public chỉ nhận origin HTTPS
trycloudflare/gradio, không auth/query/path; không theo redirect. Không in body API
UI. LoRA/TI count 0 là hợp lệ, HTTP error không được đánh đồng với count 0.

**6 nhóm stdlib/HTTP giả lập đạt**, gồm URL guard, redirect/body privacy, chỉ GET,
counts 0/ẩn tên, bounded-tail/stack privacy và invalid URL không I/O. Chạy lại
installer **98**, checkpoint **16** (AST Neo), compat **10** (real FastAPI/Gradio)
và notebook **13** đạt. Source compat/version bộ cài vẫn 1.0.4; đây là bổ sung
bằng chứng chẩn đoán, không phải một bản vá runtime được xác nhận mới.

---

## Bổ sung 1.0.4 — model đã đăng ký, nhưng dropdown trống

Ngày **11/10/2026** · setup API **2**, thư viện prompt **1.1.0** giữ nguyên.

**Bằng chứng runtime người dùng:** file WAI FP16 6.938.040.682 byte, header SDXL
hợp lệ, alias cùng file vật lý; `/sd-models` đã đăng ký, `/options` chọn đúng XL/WAI.
Không thiếu weights trong backend; diagnostic không tính SHA mới hoặc sinh ảnh.
`/cmd-flags` HTTP 500. Không đề nghị tải lại model/Torch hoặc xóa runtime.

**Lỗi schema xác định được:** Neo [ede60e1aefd30ce0f7341c8ff538f48e0fd047c9](https://github.com/Haoming02/sd-webui-forge-classic/tree/ede60e1aefd30ce0f7341c8ff538f48e0fd047c9)
suy kiểu flag default `None` thành `str | None`, trong khi argparse `--port` trả
integer. Tái hiện `string_type` với `7860` bằng Pydantic 2.10 và HTTP 500 bằng
FastAPI thật; bản vá dùng `Optional[flag.type]` cho primitive được khai báo.
Không bỏ response model hoặc tắt validation để che lỗi.

**Gia cố UI:** constructor Checkpoint gốc có `choices=None, value=None`, rồi chờ
root-load callbacks. Vá để lấy danh sách/giá trị đã chọn từ registry trước callback,
giữ short/long mode; registry rỗng vẫn để rỗng. Không có bằng chứng rằng cmd-flags
500 gây dropdown trống; CPU test constructor/config không thay thế browser native.

- `forge_compat.py`: stdlib, guard snippet/marker + AST cả hai source, backup có SHA,
  ghi nguyên tử/rollback, idempotent; `--check` chỉ đọc. Extras/prepare-launch áp dụng
  trước import Forge API/Gradio; verify kiểm source và HTTP 200/port integer.
- Diagnostics thêm projection `/config` chỉ lấy checkpoint choices/value, không
  dump prompt/auth/cmdline/log; trạng thái compat giúp tách frontend khỏi registry.
- Notebook bootstrap ≥**1.0.4**, không chạy cache 1.0.3 chưa có compat. Cập nhật
  runtime đang chạy chỉ cần phần mềm/restart; mặc định không sinh ảnh thử.

### Kiểm tra 1.0.4 (CPU, trên source Neo revision nói trên)

| Kiểm tra | Kết quả / giới hạn |
|---|---|
| Compat | **10 nhóm đạt**: guards/idempotency/backup, unknown source không ghi dở, marker tamper, FastAPI 500→200, real Gradio 4.40 long/short choices/value trước callback, registry rỗng, collision, rollback và projection chẩn đoán; UiLoadsave nguyên bản với default None/stale |
| Bộ cài / checkpoint / notebook | **98 + 16 + 13 đạt**; preset/scanner/selector và UID dùng AST upstream nguyên bản; Torch/server trong harness giả lập |

Chạy lại regression: prompt_lib **15 nhóm**, workflow **10 nhóm**, UI thật **Gradio
4.40.0** (API/host giả lập), JS **9 nhóm** với insertion TAC pinned, dữ liệu **3 đạt
+ 1 bỏ qua** nguồn tải lại; AST notebook/Python, Bash/ShellCheck, Node và diff check
đạt. Không chạy lại Gradio 6/browser app độc lập trong đợt 1.0.4.

Chưa thử toàn bộ Forge/TAC trong browser native, Python 3.13 của Colab, hoặc nạp/
sinh ảnh WAI trên GPU thật. Cần người dùng chạy ô update để xác nhận trạng thái UI
của runtime; nếu còn trống, theo dõi callback/refresh/traceback thay vì tải lại model.
Các kết quả 1.0.3/1.0.2 bên dưới là lịch sử, không suy ra mọi dependency đã chạy
lại trên mọi phiên bản trong đợt compat này.

---

## Bổ sung 1.0.3 — quy trình và sửa prompt

Ngày **11/10/2026** · `prompt_lib` **1.1.0** · setup API **2** giữ nguyên.

- Chọn tag hoặc bấm chuyển Việt → Anh sẽ thay đúng body tại chỗ, giữ trọng số,
  emphasis lồng nhau, khoảng trắng và mục chưa biết. LoRA/wildcard/schedule không
  bị dịch nhầm. Nếu Việt và Anh cùng có sẵn, chỉ bỏ bản target trùng cùng vỏ trọng
  số; không khử trùng các mục không liên quan trong ô nhập.
- Tra chính xác, không dùng prefix/fuzzy để tự dịch. Giữ tag/tên Anh đã biết
  (`hat` ≠ “hát”, `bat` ≠ “bắt”, `may` ≠ “mây”); hỗ trợ Unicode NFC/NFD.
- Adapter tagcomplete dùng toàn cụm Việt ở con trỏ thay vì từ cuối; không sửa mã
  upstream. Giữ sanitizer, underscore/escaping và queue của TAC; tránh chèn dấu
  phẩy vào trong trọng số/emphasis. Hook có retry qua `onUiUpdate`, không dùng timer.
- Điền txt2img mặc định ghép/thay tương ứng; thay toàn bộ phải bật rõ ràng. Hoàn
  tác lưu snapshot cả positive và negative, kể cả khi một ô không đổi ở lần sau.
  **Chỉ chuyển prompt, không chuyển tham số sampling sang txt2img native.**
- Hai UI có Nháp/Chuẩn/Hoàn thiện theo FP16, FP8/INT8 và HSWQ; mặc định Hires tắt,
  832×1216. Đổi mức giữ sampler đang chọn; Hoàn thiện đặt 1 ảnh/lượt. Giữ seed của
  ảnh đã chọn, không dùng seed của ảnh lưới; seed thiếu/hỏng không làm lệch index.
- Sinh nhiều ảnh tuần tự (`batch_size=1, n_iter=N`), concurrency của app/tab là 1.
  Validation từ chối NaN/sai kích thước/seed và Hires >4 megapixel; không bảo đảm
  chống OOM. Giữ clip stop bằng options override/restore, sampler và scheduler riêng.
- Bộ cài kiểm cả thư viện mới và adapter JS; stage extras thiếu source sẽ dừng
  trước khi thay extension. Cập nhật bằng extras/launch/verify, không cài lại model/Torch.

### Đồng bộ notebook cài mới

Cả notebook một ô và từng bước đã được sinh lại cho 1.0.3. Bootstrap kiểm phiên
bản/cú pháp, từ chối cache 1.0.2; notebook từng bước dùng cùng bộ cài, launch nền
và mặc định không sinh ảnh/mở app phụ khi Run all. Ví dụ API dùng profile,
workflow/validation/decoder/seed chung. `test_notebooks.py`: **13 nhóm CPU đạt**,
bao gồm Run all với stage/HTTP giả lập, không phải cài mới trên Colab/GPU thật.
Notebook không có output đã chạy/secret literal. Xóa runtime là thao tác người dùng
chọn trong Colab sau khi tải ảnh về, không phải lệnh xóa dữ liệu tự động.

### Kết quả chạy lại 1.0.3

| Kiểm tra | Kết quả và phạm vi |
|---|---|
| Bộ cài | **98/98**; có guard UID upstream, copy JS/marker và repo thiếu workflow giữ nguyên extension/config |
| Checkpoint | **16 nhóm đạt**; có hàm preset/scanner/selector nguyên bản của Forge ở revision ghi bên dưới; engine/cache vẫn giả lập |
| Prompt library / workflow | **15 + 10 nhóm đạt**; gồm kiểm canonical của toàn bộ index, NFD, giữ tag khác, trọng số lồng nhau, seed/preset/validation |
| Cả hai UI | **Gradio 4.40.0 và 6.30.0 đạt**; dựng UI thật, API/Forge host/PNG giả lập |
| JavaScript | **9 nhóm đạt**, dùng hàm insertion TAC nguyên bản; supporting DOM/globals/queues giả lập. Có NFD/không dấu, weight, paired undo, load-order retry |
| Trình duyệt app độc lập | **Chromium + Gradio thật đạt**: 6 lượt click chuyển tag, gồm bỏ trùng đúng target, giữ tag Anh, NFD, whitespace/weight và LoRA/schedule. Không gọi GPU |
| Dữ liệu | **3 nhóm đạt, 1 bỏ qua** đối chiếu nguồn gốc vì file nguồn tải lại được không có trong checkout; toàn bộ CSV hiện có vẫn được kiểm |
| Cú pháp | Python/notebook AST, Node, Bash/ShellCheck và `git diff --check` |

Mã TAC đối chiếu: [commit 4170882f90b47be130a0ff9314f663c230b9153d](https://github.com/DominikDoom/a1111-sd-webui-tagcomplete/tree/4170882f90b47be130a0ff9314f663c230b9153d).
Đây là revision được kiểm thử, **không phải pin dependency của bộ cài**.

**Giới hạn:** chưa chạy toàn bộ Forge + TAC trong trình duyệt native hoặc sinh ảnh
WAI trên GPU thật; không có benchmark tốc độ/VRAM/chất lượng. Preset là lựa chọn
ứng dụng, không phải tối ưu tuyệt đối. API client độc lập vẫn có thể dùng GPU đồng
thời; thay prompt/kích thước/sampler/steps/Hires có thể đổi kết quả dù giữ seed.

---

## Rà soát checkpoint nền 1.0.2

Phần dưới giữ kết quả/phát hiện của đợt 1.0.2 để đối chiếu; số kiểm tra hiện tại
được ghi ở bảng 1.0.3 phía trên.

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
