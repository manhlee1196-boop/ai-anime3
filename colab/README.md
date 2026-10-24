# Hệ thống tạo ảnh WAI-Illustrious v17 trên Google Colab
### dùng kho prompt tiếng Việt của repo này làm bộ nhắc

Mục này biến danh sách tag Danbooru + e621 đã dịch (349.714 tag, 45.557 bản dịch
tiếng Việt) thành **bộ nhắc prompt** cho một hệ sinh ảnh chạy trên Colab.

```
colab/
  WAI_v17_1click.ipynb          ← BỘ CÀI MỘT Ô, CHỌN MODEL (khuyên dùng)
  install.sh                    bộ cài một lệnh, kiểm tra/resume/chọn model
  INSTALL.md                    hướng dẫn bộ cài + xử lý sự cố
  make_install_notebook.py      sinh notebook một ô
  notebook_support.py           bootstrap/version guard và nội dung ô dùng chung
  checkpoint_tools.py           xác minh container/hash, alias, preset XL, API, sinh thử
  diagnostics.py                chẩn đoán checkpoint/venv/GPU/API/config UI chỉ đọc
  forge_compat.py               vá schema cmd-flags và choices/value Checkpoint (có guard/backup)
  AUDIT.md                      báo cáo album 1.0.7 + tunnel 1.0.6 + headless 1.0.5 + compat 1.0.4 + quy trình 1.0.3 + checkpoint 1.0.2
  WAI_Illustrious_v17_vi.ipynb    notebook chi tiết, chạy từng bước
  setup_forge.sh                 script cài đặt theo từng bước (notebook gọi dần)
  make_notebook.py               script sinh ra file .ipynb ở trên
  make_tagcomplete_assets.py     sinh file tag hệ thống + bản dịch gộp cho tagcomplete
  prompt_builder.py              app Gradio độc lập (chạy được cả ngoài Colab)
  prompt_lib/                    thư viện lõi: tra cứu, phân nhóm, ghép prompt
    index.py                       mục lục tra cứu 2 chiều Việt <-> Anh
    groups.py                      phân loại tag + thứ tự prompt chuẩn Illustrious
    builder.py                     ghép prompt / negative / payload cho API
    editing.py                     thay Việt → Anh, giữ cú pháp/mục khác
    workflow.py                    preset, validation, metadata seed theo ảnh
    system_tags.py                 tag hệ thống WAI-Illustrious + preset tham số
  extension/vi-prompt-builder/   extension Forge: thêm tab "Prompt VN"
    scripts/vi_prompt_tab.py
    javascript/vi_prompt.js        điền prompt vào ô txt2img ngay trong trình duyệt
  tests/test_prompt_lib.py       bộ kiểm tra hồi quy (16 nhóm kiểm tra)
  tests/test_install_sh.py       98 kiểm tra bộ cài (không cần GPU/mạng)
  tests/test_prompt_ui.py        smoke test cả hai UI, API/Forge host giả lập
  tests/test_prompt_workflow.py  10 nhóm thay tag/tham số/seed/quy trình
  tests/test_notebooks.py        13 nhóm bootstrap/Run all/API (requests/Pillow, CPU)
  tests/test_vi_prompt_js.cjs    bridge + TAC đa từ, có tùy chọn mã upstream thật
  tests/test_headless_backend.py  4 nhóm Agg/Matplotlib/Dataframe/callback Gradio (CPU)
  tests/test_ui_diagnostics.py    8 nhóm HTTP/log/env chỉ đọc, không dump prompt/auth
  tests/test_forge_compat.py      10 nhóm compat trên Neo/FastAPI/Gradio (CPU)
  tests/test_checkpoint_flow.py  16 nhóm checkpoint/preset/alias/API
  tests/test_data_integrity.py   4 nhóm toàn vẹn CSV (349.714 dòng)
  assets/                        file sinh ra khi chạy (không đưa vào git)
  outputs/                       ảnh sinh ra từ notebook (không đưa vào git)
```

## Bộ cài một lệnh / notebook một ô (khuyên dùng)

Mở [`WAI_v17_1click.ipynb`](WAI_v17_1click.ipynb) trong Colab, bật GPU, chọn model
trong dropdown rồi chạy ô cài duy nhất. Mặc định **FP16 bản gốc**, lưu trong `/content`,
không mount Drive; **Gradio share** mặc định (`gradio.live`), Cloudflare tùy chọn; có thêm FP8/INT8/HSWQ cộng đồng ở chế độ **thử nghiệm**.

[**Mở notebook cài mới 1.0.7 trong Colab**](https://colab.research.google.com/github/manhlee1196-boop/ai-anime3/blob/arena%2Fec9855a4-ai-anime3/colab/WAI_v17_1click.ipynb)
→ chọn GPU T4 → **Run all**. Ô cài từ chối cache cũ hơn 1.0.7.
**Bảng ảnh đã tạo:** [cập nhật phần mềm 1.0.7](INSTALL.md#bảng-ảnh-đã-tạo-107), giữ model/Torch/ảnh; mở mục **Ảnh đã tạo** trong Prompt VN rồi bấm **Làm mới**.
**Ảnh chậm / HTML thay JSON khi dùng Cloudflare:** [đổi sang Gradio share](INSTALL.md#ảnh-hiển-thị-chậm--unexpected-token--106), chỉ launch/verify sau khi sinh xong. Phiên share đang ổn không cần chạy lại.
**Hàng loạt ô hiện Error / stack Matplotlib:** xem [sửa backend headless 1.0.5](INSTALL.md#error-hàng-loạt--matplotlib-backend-inline-colab-105), chỉ cập nhật/restart Forge, giữ venv/trọng số/notebook inline.
**API đã có WAI nhưng dropdown trống:** dùng [ô cập nhật 1.0.4](INSTALL.md#api-đã-có-wai-nhưng-dropdown-trống--cmd-flags-500-104), chỉ cập nhật phần mềm và restart; không xóa runtime/tải lại weights.
Nếu muốn runtime hoàn toàn mới: tải ảnh về trước rồi **Disconnect and delete runtime**,
kết nối lại/bật GPU. Notebook không tự xóa dữ liệu cũ.

Hoặc dán một dòng vào Colab:

```python
!curl -fsSL --retry 3 "https://raw.githubusercontent.com/manhlee1196-boop/ai-anime3/arena/ec9855a4-ai-anime3/colab/install.sh" -o /content/install.sh && bash /content/install.sh --model fp16
```

Model tải vào `.part`, chỉ nhận khi SHA256 khớp; chạy lại không cài/khởi động trùng.
Chẩn đoán: `!bash /content/install.sh --doctor`. Chi tiết chọn model, Secrets, sửa lỗi:
**[`INSTALL.md`](INSTALL.md)**.

Nếu bản cài cũ dừng ở `verify_version()` với `EOFError`, xem
[ô sửa VERSION_UID](INSTALL.md#eoferror-tại-verify_version--press-enter-to-continue):
bộ cài 1.0.1 chỉ cần cập nhật script và mở lại UI, không tải lại checkpoint.

Nếu ô **Checkpoint** trống dù file đã có, xem
[ô sửa checkpoint 1.0.2](INSTALL.md#không-nhận-checkpoint--ô-checkpoint-trống-dù-file-đã-tải).
Bản mới đặt đúng preset XL, đăng ký model và đối chiếu đường dẫn/lựa chọn thực từ API.
Có `--smoke-test` để thử nạp trọng số bằng một ảnh trên GPU và `--diagnostics` chỉ đọc.

## Notebook chi tiết — chạy từng bước

1. Mở [`WAI_Illustrious_v17_vi.ipynb`](WAI_Illustrious_v17_vi.ipynb) trong
   [Google Colab](https://colab.research.google.com), **Runtime → Change runtime type → T4 GPU**.
2. **Ô 1**: chọn model; mặc định FP16, `/content/models`, tunnel **Gradio share** (`gradio.live`); Cloudflare tùy chọn.
3. **Run all** hoặc lần lượt Ô 1 → Ô 8 (khoảng 10–25 phút tùy runtime/mạng).
   Các stage dùng cùng `install.sh` mới, không trộn script cũ hay cài theo đường khác.
4. **Ô 8** khởi chạy nền + verify, in link `gradio.live` (mặc định)/`trycloudflare.com` (khi chọn) và kết thúc;
   không chặn các ô sau ở một lệnh launch chạy mãi.
5. Dùng **Prompt VN** để chọn tag/thử bố cục/seed. Ô 9 chẩn đoán/smoke test,
   Ô 10 API và Ô 11 app riêng **mặc định tắt**; Run all không tự sinh ảnh/mở server phụ.
   Bật riêng khi cần. Ví dụ API dùng profile model, Hires tắt ở Nháp/Chuẩn,
   decoder JSON-string/PIL và seed đúng từng ảnh, không dùng ví dụ CFG FP16 cố định cũ.

Repo public không cần GitHub token. Nếu dùng repo private, bật `USE_GITHUB_SECRET`
ở Ô 1 và đọc token từ **Colab Secrets**; không dán token vào source/URL clone.

## 🗂️ Bảng ảnh đã tạo (1.0.7)

Mở **Prompt VN → Ảnh đã tạo → Làm mới**, hoặc tab **Ảnh đã tạo** trong app độc lập.
Gallery + bảng phân trang 12/24 ảnh: thời gian lưu UTC+7, tên, seed, kích thước,
dung lượng. Chọn ảnh/dòng để xem/tải bản gốc, bấm **Dùng seed ảnh lịch sử** khi cần.
Chỉ điền seed; không tự chuyển prompt hoặc sampling. Ảnh lưới/không có seed thì không dùng.
Đọc cả ảnh txt2img/img2img đã lưu trước khi cập nhật; không cần tạo lại.

Lịch sử/thumbnail ở `FORGE_DIR/outputs/.wai-history/` trên đĩa, State chỉ giữ id nhỏ,
không thêm tất cả PIL/base64 vào RAM. Thumbnail WebP tối đa 384px; file gốc và PNG
metadata không bị sửa. Khởi động lại Forge vẫn đọc được; xóa runtime Colab vẫn mất
`/content`. Album không tự mount Drive và không phải bản vá đã xác định cho RAM tăng.
Người có link UI cũng xem được album. [Ô cập nhật chỉ phần mềm](INSTALL.md#bảng-ảnh-đã-tạo-107).
App riêng có `--forge-dir`/`--history-dir` để trỏ file trên máy chạy app, không tải ảnh
qua URL của Forge ở máy khác. Không theo symlink ra ngoài thư mục output.

## Ba cách dùng kho prompt

| Cách | Ở đâu | Hợp với |
|---|---|---|
| **Gõ tiếng Việt ngay trong ô prompt** | tab txt2img của Forge (tagcomplete) | vừa vẽ vừa thêm tag nhanh |
| **Tab “Prompt VN”** | tab riêng trong Forge | dựng prompt có cấu trúc, xem nghĩa tiếng Việt, sinh ảnh ngay |
| **Gọi API từ notebook** | Ô 10 | sinh ảnh hàng loạt, tự động hoá |

### 1. tagcomplete — gõ tiếng Việt ra tag tiếng Anh
Ô 7 đã ghi sẵn vào `config.json` của Forge:

| Khoá | Giá trị | Ý nghĩa |
|---|---|---|
| `tac_tagFile` | `danbooru_e621.csv` | danh sách tag tiếng Anh (bản gốc có `_`) |
| `tac_extra.extraFile` | `wai-illustrious-system-tags.csv` | tag hệ thống mà Danbooru không có |
| `tac_extra.addMode` | `Insert before` | tag hệ thống hiện trước trong gợi ý |
| `tac_translation.translationFile` | `danbooru_e621_vi_translation_wai.csv` | bản dịch 2 cột |
| `tac_translation.searchByTranslation` | `true` | **cho phép tìm bằng tiếng Việt** |
| `tac_translation.liveTranslation` | `true` | hiện nghĩa tiếng Việt dưới ô prompt |
| `tac_translation.oldFormat` | `false` | file của ta là chuẩn 2 cột mới |
| `clip_stop_at_last_layers` | `2` | CLIP stop theo khuyến nghị họ Illustrious |

Vì sao dùng bản tag **có** dấu `_`: chính tagcomplete thay `_` bằng khoảng trắng lúc
chèn tag, và nó có sẵn danh sách loại trừ cho emoticon
(`0_0,(o)_(o),+_+,._.,<o>_<o>,<|>_<|>,=_=,>_<,3_3,6_9,>_o,@_@,^_^,o_o,u_u,x_x,|_|,…`) —
trùng khớp với `EMOTICON_KEEP` mà repo này dùng khi bỏ dấu `_`.

### 2. Tab “Prompt VN”
- Tra tag bằng tiếng Việt, **không cần gõ dấu** (`ao dai` vẫn ra `ao_dai`);
  từ có dấu được ưu tiên khớp chính xác nên “váy” không bị lẫn với “vảy”, “vây”.
- Khớp đủ mọi từ theo bất kỳ thứ tự nào: “nhìn người xem” vẫn ra `looking_at_viewer`
  dù bản dịch là “nhìn vào người xem”.
- Duyệt theo 18 nhóm (Trang phục, Ngoại hình, Tư thế, Bối cảnh, Góc máy, 18+…).
- **Mục chọn phong cách vẽ**: 506 tag phong cách / 9 nhóm (chất liệu truyền thống, chất liệu
  số, kỹ thuật hoàn thiện, ánh sáng, trường phái, thể loại, thời kỳ, tác giả `_(style)`).
  Danh sách tick mặc định là **Tất cả (506 tag — mọi nhóm)** nên **không tag nào bị ẩn**;
  chọn một nhóm hoặc gõ ô tìm không dấu mới lọc lại (tag đang tick vẫn được giữ). Có
  **12 công thức sẵn** (màu nước, cel-shading, anime 1990, ukiyo-e, Art Nouveau, sơn dầu, 3D,
  pixel art, truyện đen trắng, phác thảo chì, anime chi tiết, hoạt hình cổ) — chọn là tick sẵn
  cả bộ ở đầu danh sách (các tag khác vẫn hiện), bấm **Thêm tag phong cách** để ghép vào
  prompt. Bảng bên dưới cho biết từng tag mạnh hay yếu theo số bài đăng. Dữ liệu lấy từ
  `style_tags.csv`; chi tiết và công thức ở [`STYLE_TAGS.md`](../STYLE_TAGS.md).
  Ô **Styles** của Forge cũng có 12 style `Phong cách — …` bấm là ăn ngay.
- **Prompt dài (CLIP 75 token/cửa sổ)**: mục **📏 Prompt dài** trong app đo token, chia cửa sổ
  và chỉ ra tag nào rơi vào vùng loãng (>150 token); nút **✂️ Nén** bỏ tag trùng nghĩa
  (`eyes` khi đã có `blue_eyes`). Ghi chú dưới ô positive hiện `🟢/🟡/🔴 N token · M cửa sổ`.
  Cách giữ chi tiết khi prompt rất dài: [`PROMPT_DAI.md`](../PROMPT_DAI.md).
- Bấm một dòng kết quả: nếu đã có mục Việt tương ứng thì **thay tại chỗ**,
  nếu chưa có thì thêm tag. Ví dụ `1girl, (áo dài:1.2), long_hair` →
  `1girl, (ao_dai:1.2), long_hair`; không còn cả Việt + Anh.
- Có nút **Thay mục Việt → tag Anh** để chuyển nhiều mục đã biết một lần;
  mục chưa xác định, LoRA, wildcard và trọng số được giữ nguyên, không tự đoán fuzzy.
- Nếu mục Việt và tag Anh cùng tồn tại, chỉ bỏ bản trùng đúng mục đã chuyển
  với cùng trọng số; không khử trùng các mục khác trong ô nhập. Tag Anh có sẵn
  được ưu tiên giữ đúng nghĩa (`hat` không bị hiểu thành “hát”).
- Tagcomplete trong txt2img/img2img có adapter lấy toàn cụm Việt ở con trỏ,
  không chỉ từ cuối; không chỉnh sửa mã của extension tagcomplete.
- Ghép prompt theo thứ tự Illustrious/WAI, sinh negative theo mức phân loại đã chọn.
- Hai lối ra: **Đưa vào txt2img** mặc định ghép/thay mục tương ứng, giữ mục khác;
  **Thay toàn bộ** phải bật rõ ràng, có **Hoàn tác** trong phiên trình duyệt.
  Nút chỉ chuyển prompt, **không chuyển tham số sampling**; chỉnh chúng tại txt2img.
- **Sinh ảnh** ngay trong tab dùng quy trình/seed và tham số API đã chọn.
  Chỉ một tác vụ API của app/tab chạy đồng thời; không chặn được người dùng khác
  gọi API trực tiếp hoặc một app độc lập khác.
- Có công tắc ẩn/hiện tag 18+ khi tìm, duyệt và bốc ngẫu nhiên.

### 3. App Gradio độc lập
```bash
python3 colab/prompt_builder.py --forge-url http://127.0.0.1:7860 --port 7861 --share
python3 colab/prompt_builder.py --demo          # không cần Forge/GPU, chỉ dựng prompt
```
Có thêm tab **“Dịch prompt Anh → Việt”**: dán một prompt bất kỳ để xem nghĩa tiếng Việt
của từng tag, tra từ chính kho 45.557 bản dịch.

## Thứ tự prompt mà hệ thống tạo ra

```
[câu mô tả tự nhiên]
→ chất lượng → phân loại → nguồn/phong cách → số lượng & chủ thể
→ nhân vật → series → cốt truyện → loài → ngoại hình → trang phục
→ biểu cảm → tư thế → hành động → 18+ → đạo cụ → bối cảnh → góc máy
→ hoạ sĩ → meta
```

Ví dụ với đầu vào `1girl, ao_dai, long_hair, red_eyes, holding_sword, cherry_blossoms,
from_behind` và mô tả “Một cô gái đứng dưới cơn mưa hoa anh đào”:

```
Một cô gái đứng dưới cơn mưa hoa anh đào, masterpiece, best quality, amazing quality,
newest, highres, absurdres, rating_general, general, 1girl, long_hair, red_eyes,
ao_dai, holding_sword, cherry_blossoms, from_behind
```

## Quy trình tối ưu (bản 1.0.3)

| Mức | FP16 gốc | FP8/INT8 | HSWQ turbo | Hires |
|---|---|---|---|---|
| Nháp | 18 bước / CFG 6 | 18 / CFG 6.5 | 10 / CFG 1 | Tắt |
| Chuẩn | 25 / CFG 6 | 25 / CFG 6.5 | 10 / CFG 1 | Tắt |
| Hoàn thiện | 25 / CFG 6 | 25 / CFG 6.5 | 10 / CFG 1 | 1.5×, denoise .35; 20 bước (HSWQ 10) |

Các số trên là preset ứng dụng, **không phải benchmark/đo chất lượng tối ưu tuyệt đối**.
Biến môi trường profile đã tinh chỉnh được ưu tiên. Không đổi model hoặc bật dtype FP8 tự động.

1. Dựng prompt ngắn; tiếng Việt là đầu vào tra tag, câu tự nhiên nên viết tiếng Anh.
2. Thử bố cục ở **Nháp**, mặc định 832×1216 (dọc, gần 1 megapixel).
   Có thể chọn 1024×1024 hoặc 1024×1344 khi còn VRAM.
3. Chọn ảnh trong Gallery → **Dùng seed của ảnh đã chọn**. Không dùng seed của ảnh lưới.
4. Chuyển **Chuẩn** hoặc **Hoàn thiện**; giữ cùng prompt, kích thước gốc và seed.
   Khi đổi mức, app giữ sampler bạn chọn; Hoàn thiện tự đặt **1 ảnh/lượt**.
   Preset áp lại steps/CFG; thay steps/Hires vẫn có thể đổi chi tiết.
   Đổi kích thước có thể đổi bố cục dù cùng seed.
5. Hires 1.5× chỉ cho ảnh đã chọn; tránh Hires ngay từ mọi bản nháp. Ngân sách app
   chặn ảnh Hires >4 megapixel, không phải bảo đảm T4 sẽ không OOM.

Nhiều ảnh gửi `batch_size=1, n_iter=N` (tuần tự). Có hàng đợi riêng cho sinh ảnh;
không hỏi danh sách upscaler khi Hires tắt. Ảnh API được lưu theo thiết lập outputs
của Forge; mặc định dự án vẫn `/content`. Có cảnh báo tham số không hợp lệ và lỗi hết VRAM.
Chưa kiểm chứng tốc độ/chất lượng WAI thật vì sandbox không có GPU/trọng số.
Phạm vi kiểm thử và giới hạn tích hợp native: [AUDIT.md](AUDIT.md#bổ-sung-103--quy-trình-và-sửa-prompt).

## Tham số WAI-Illustrious v17.0 (từ thẻ model)

| Tham số | Giá trị |
|---|---|
| File | `waiIllustriousSDXL_v170.safetensors` — 6,5 GB, VAE **tích hợp sẵn** |
| SHA256 | `f116b0c78ff441467b0cdc8f1936e1ed18ea31e9997c7b132b1b8db533f0bd04` |
| Nguồn tải | mirror HuggingFace `LyliaEngine/waiIllustriousSDXL_v170` (không cần token) |
| Sampler / Steps / CFG | Euler a · 15–30 (mặc định 25) · 5–7 (mặc định 6) |
| Kích thước | > 1024×1024 (mặc định 1024×1344) |
| Hires. fix | scale 1.5 · 20 bước · denoising 0.35–0.5 |
| Upscaler | `RealESRGAN_x4plus_anime_6B` |
| CLIP stop | 2 |
| Backend | **forge-neo** (khuyến nghị của tác giả model) |
| Phân loại | 4 mức `general / sensitive / nsfw / explicit` |

### Các chỗ dễ cài sai (đã xử lý trong code)
- **Upscaler:** Forge Neo *không* có scaler tên `R-ESRGAN 4x+ Anime6B`. Lớp
  `UpscalerESRGAN` của nó quét `models/ESRGAN/` và đặt tên scaler **theo tên file**
  (`friendly_name()` giữ nguyên basename), nên tên đúng là `RealESRGAN_x4plus_anime_6B`.
  `pick_upscaler()` hỏi `/sdapi/v1/upscalers` rồi tự chọn bản anime tốt nhất mà backend
  thực sự có, nên payload không bao giờ trỏ tới upscaler không tồn tại.
- **Checkpoint/preset:** Neo dùng cả `sd_model_checkpoint` và `forge_checkpoint_xl`.
  Bộ cài chọn preset `xl`, tạo alias có quản lý khi model nằm ngoài Forge và không chỉ
  so basename API (tránh nhận nhầm một model cùng tên ở thư mục khác).
- **Cờ dòng lệnh:** nhánh `neo` **không có** `--medvram`, `--no-download-sd-model`,
  `--precision`; thay vào đó là `--lowvram`, `--expandable-segments`, `--reserve-vram`.
  `setup_forge.sh` chỉ dùng các cờ đã kiểm tra là tồn tại trong
  `modules/cmd_args.py` và `backend/args.py` của nhánh này.

### Tag hệ thống không có trong danh sách Danbooru
`rating_*`, `masterpiece`, `newest`, `very awa`, `source_anime`… đến từ cột rating/score
của Danbooru và quy ước prompt của cộng đồng Illustrious, **không nằm** trong
`danbooru_e621.csv`. `prompt_lib/system_tags.py` cấp riêng 81 tag này kèm nghĩa tiếng Việt,
và `make_tagcomplete_assets.py` xuất chúng thành extra file để vẫn được gợi ý khi gõ.

## Kiểm tra
```bash
python3 colab/tests/test_prompt_lib.py     # 16 nhóm kiểm tra, in ✓/✗ từng dòng
python3 colab/tests/test_install_sh.py      # 98 kiểm tra bộ cài, fixture/offline
python3 colab/tests/test_checkpoint_flow.py # 16 nhóm checkpoint/preset/API
python3 colab/tests/test_data_integrity.py  # 4 nhóm toàn vẹn toàn bộ CSV
python3 colab/tests/test_prompt_ui.py       # cần Gradio/requests/Pillow; không cần GPU
python3 colab/tests/test_prompt_workflow.py # 10 nhóm CPU, không cần Gradio
python3 colab/tests/test_notebooks.py       # 13 nhóm CPU; cần requests/Pillow (venv Forge/demo)
node colab/tests/test_vi_prompt_js.cjs      # DOM stub/bridge/token, không cần browser
# Có source TAC đã tải: TAC_AUDIT_SOURCE=/path/tagAutocomplete.js node colab/tests/test_vi_prompt_js.cjs
python3 colab/make_tagcomplete_assets.py   # sinh lại assets/, tự assert không trùng khoá
bash -n colab/setup_forge.sh               # kiểm tra cú pháp script
```

## Nội dung và trách nhiệm
Model này có khả năng tạo nội dung người lớn. Mặc định hệ thống đặt mức **general** và
tự đẩy `sensitive / questionable / explicit / nsfw` sang negative prompt (đúng hướng dẫn
trên thẻ model). Bạn phải tự tuân thủ pháp luật nơi mình ở, điều khoản dịch vụ của
Google Colab, và **tuyệt đối không** tạo nội dung tình dục hoá trẻ vị thành niên —
đây là giới hạn sử dụng, không phải cam kết rằng negative prompt lọc được mọi nội dung.
