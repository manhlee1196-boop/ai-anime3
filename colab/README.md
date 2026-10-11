# Hệ thống tạo ảnh WAI-Illustrious v17 trên Google Colab
### dùng kho prompt tiếng Việt của repo này làm bộ nhắc

Mục này biến danh sách tag Danbooru + e621 đã dịch (349.714 tag, 45.513 bản dịch
tiếng Việt) thành **bộ nhắc prompt** cho một hệ sinh ảnh chạy trên Colab.

```
colab/
  WAI_Illustrious_v17_vi.ipynb   ← MỞ FILE NÀY TRONG COLAB
  setup_forge.sh                 script cài đặt theo từng bước (notebook gọi dần)
  make_notebook.py               script sinh ra file .ipynb ở trên
  make_tagcomplete_assets.py     sinh file tag hệ thống + bản dịch gộp cho tagcomplete
  prompt_builder.py              app Gradio độc lập (chạy được cả ngoài Colab)
  prompt_lib/                    thư viện lõi: tra cứu, phân nhóm, ghép prompt
    index.py                       mục lục tra cứu 2 chiều Việt <-> Anh
    groups.py                      phân loại tag + thứ tự prompt chuẩn Illustrious
    builder.py                     ghép prompt / negative / payload cho API
    system_tags.py                 tag hệ thống WAI-Illustrious + preset tham số
  extension/vi-prompt-builder/   extension Forge: thêm tab "Prompt VN"
    scripts/vi_prompt_tab.py
    javascript/vi_prompt.js        điền prompt vào ô txt2img ngay trong trình duyệt
  tests/test_prompt_lib.py       bộ kiểm tra hồi quy (14 nhóm kiểm tra)
  assets/                        file sinh ra khi chạy (không đưa vào git)
  outputs/                       ảnh sinh ra từ notebook (không đưa vào git)
```

## Chạy nhanh

1. Mở [`WAI_Illustrious_v17_vi.ipynb`](WAI_Illustrious_v17_vi.ipynb) trong
   [Google Colab](https://colab.research.google.com), **Runtime → Change runtime type → T4 GPU**.
2. Xem lại **Ô 1 (Cấu hình)** — mặc định đã đúng theo thẻ model v17.0.
3. Chạy lần lượt Ô 2 → Ô 7 (mất 8–15 phút, phần lớn là tải model 6,5 GB).
4. Chạy **Ô 8** rồi bấm link `https://xxxx.gradio.live`.
5. Trong Forge: dùng tab **Prompt VN**, hoặc gõ thẳng tiếng Việt vào ô prompt
   (tagcomplete đã được cấu hình sẵn).

Nếu repo để **private**, điền `GITHUB_TOKEN` (quyền đọc là đủ) vào Ô 1.

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
- Bấm một dòng kết quả → tag tự thêm vào danh sách, **không trùng lặp**.
- Ghép prompt theo thứ tự Illustrious/WAI, sinh negative theo mức phân loại đã chọn.
- Hai lối ra: **📋 Đưa vào txt2img** (điền thẳng vào ô prompt bằng JS, không cần API)
  hoặc **🖼️ Sinh ảnh** (gọi `/sdapi/v1/txt2img` với đúng tham số v17).
- Có công tắc ẩn/hiện tag 18+ khi tìm, duyệt và bốc ngẫu nhiên.

### 3. App Gradio độc lập
```bash
python3 colab/prompt_builder.py --forge-url http://127.0.0.1:7860 --port 7861 --share
python3 colab/prompt_builder.py --demo          # không cần Forge/GPU, chỉ dựng prompt
```
Có thêm tab **“Dịch prompt Anh → Việt”**: dán một prompt bất kỳ để xem nghĩa tiếng Việt
của từng tag, tra từ chính kho 45.513 bản dịch.

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

### Hai chỗ dễ cài sai (đã xử lý sẵn trong code)
- **Upscaler:** Forge Neo *không* có scaler tên `R-ESRGAN 4x+ Anime6B`. Lớp
  `UpscalerESRGAN` của nó quét `models/ESRGAN/` và đặt tên scaler **theo tên file**
  (`friendly_name()` giữ nguyên basename), nên tên đúng là `RealESRGAN_x4plus_anime_6B`.
  `pick_upscaler()` hỏi `/sdapi/v1/upscalers` rồi tự chọn bản anime tốt nhất mà backend
  thực sự có, nên payload không bao giờ trỏ tới upscaler không tồn tại.
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
python3 colab/tests/test_prompt_lib.py     # 14 nhóm kiểm tra, in ✓/✗ từng dòng
python3 colab/make_tagcomplete_assets.py   # sinh lại assets/, tự assert không trùng khoá
bash -n colab/setup_forge.sh               # kiểm tra cú pháp script
```

## Nội dung và trách nhiệm
Model này có khả năng tạo nội dung người lớn. Mặc định hệ thống đặt mức **general** và
tự đẩy `sensitive / questionable / explicit / nsfw` sang negative prompt (đúng hướng dẫn
trên thẻ model). Bạn phải tự tuân thủ pháp luật nơi mình ở, điều khoản dịch vụ của
Google Colab, và **tuyệt đối không** tạo nội dung tình dục hoá trẻ vị thành niên —
mọi tag loại đó đều bị cấm.
